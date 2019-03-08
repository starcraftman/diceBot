"""
Used for pytest fixtures and anything else test setup/teardown related.
"""
from __future__ import absolute_import, print_function
import datetime
import sys

import aiomock
import discord
import pytest
import sqlalchemy.exc

try:
    import uvloop
    LOOP = uvloop.new_event_loop()
    LOOP.set_debug(True)
    print("Test loop policy:", str(LOOP))
    del LOOP
except ImportError:
    print("Run: python setup.py deps")
    sys.exit(1)

import dicedb
import dicedb.schema
from dicedb.schema import (DUser, SavedRoll, Pun, StoredTurn)


#  @pytest.yield_fixture(scope='function', autouse=True)
#  def around_all_tests(session):
    #  """
    #  Executes before and after EVERY test.

    #  Can be helpful for tracking bugs, like dirty database after test.
    #  Disabled unless needed. Non-trivial overhead.
    #  """
    #  classes = [DUser, SavedRoll]
    #  for cls in classes:
        #  print('Before', cls.__name__, session.query(cls).all())

    #  yield

    #  classes = [DUser, SavedRoll]
    #  for cls in classes:
        #  print('After', cls.__name__, session.query(cls).all())


@pytest.fixture
def event_loop():
    """
    Provide a a new test loop for each test.
    Save system wide loop policy, and use uvloop if available.

    To test either:
        1) Mark with pytest.mark.asyncio
        2) event_loop.run_until_complete(asyncio.gather(futures))
    """
    loop = uvloop.new_event_loop()
    loop.set_debug(True)

    yield loop

    loop.close()


# Fake objects look like discord data classes
class FakeObject(object):
    """
    A fake class to impersonate Data Classes from discord.py
    """
    oid = 0

    @classmethod
    def next_id(cls):
        cls.oid += 1
        return '{}-{}'.format(cls.__name__, cls.oid)

    def __init__(self, name, id=None):
        if not id:
            id = self.__class__.next_id()
        self.id = id
        self.name = name

    def __repr__(self):
        return "{}: {} {}".format(self.__class__.__name__, self.id, self.name)

    def __str__(self):
        return "{}: {}".format(self.__class__.__name__, self.name)


class Server(FakeObject):
    def __init__(self, name, id=None):
        super().__init__(name, id)
        self.channels = []

    def add(self, channel):
        self.channels.append(channel)

    # def __repr__(self):
        # channels = "\n  Channels: " + ", ".join([cha.name for cha in self.channels])
        # return super().__repr__() + channels


class Channel(FakeObject):
    def __init__(self, name, *, srv=None, type=0, id=None):
        super().__init__(name, id)
        self.server = srv
        self.type = discord.ChannelType(type)

    # def __repr__(self):
        # return super().__repr__() + ", Server: {}".format(self.server.name)


class VoiceState(FakeObject):
    def __init__(self, name, *, is_afk=False, voice_channel=None, id=None):
        super().__init__(name, id)
        self.is_afk = is_afk
        self.voice_channel = voice_channel


class Member(FakeObject):
    def __init__(self, name, roles, *, id=None, voice=None):
        super().__init__(name, id)
        self.discriminator = '12345'
        self.display_name = self.name
        self.roles = roles
        self.voice = VoiceState('Voice ' + name, is_afk=False, voice_channel=None)
        if voice:
            self.voice = voice

    @property
    def mention(self):
        return self.display_name

    # def __repr__(self):
        # roles = "Roles:  " + ", ".join([rol.name for rol in self.roles])
        # return super().__repr__() + ", Display: {} ".format(self.display_name) + roles


class Role(FakeObject):
    def __init__(self, name, srv=None, *, id=None):
        super().__init__(name, id)
        self.server = srv

    # def __repr__(self):
        # return super().__repr__() + "\n  {}".format(self.server)


class Message(FakeObject):
    def __init__(self, content, author, srv, channel, mentions, *, id=None):
        super().__init__(None, id)
        self.author = author
        self.channel = channel
        self.content = content
        self.mentions = mentions
        self.server = srv

    @property
    def timestamp(self):
        return datetime.datetime.utcnow()

    # def __repr__(self):
        # return super().__repr__() + "\n  Content: {}\n  Author: {}\n  Channel: {}\n  Server: {}".format(
            # self.content, self.author, self.channel, self.server)


def fake_servers():
    """ Generate fake discord servers for testing. """
    srv = Server("Gears' Hideout")
    channels = [
        Channel("feedback", srv=srv),
        Channel("live_hudson", srv=srv),
        Channel("private_dev", srv=srv),
        Channel("voice1", srv=srv, type=discord.enums.ChannelType.voice),
    ]
    for cha in channels:
        srv.add(cha)

    return [srv]


def fake_msg_gears(content):
    """ Generate fake message with GearsandCogs as author. """
    srv = fake_servers()[0]
    roles = [Role('Everyone', srv), Role('Cookie Lord', srv)]
    aut = Member("GearsandCogs", roles, id="1000")
    return Message(content, aut, srv, srv.channels[1], None)


def fake_msg_newuser(content):
    """ Generate fake message with GearsandCogs as author. """
    srv = fake_servers()[0]
    roles = [Role('Everyone', srv), Role('Fighter', srv)]
    aut = Member("newuser", roles, id="1003")
    return Message(content, aut, srv, srv.channels[1], None)


def fake_msg(content, user_id='1', name='User1', voice=False):
    """ Generate fake message with GearsandCogs as author. """
    srv = fake_servers()[0]
    roles = [Role('Everyone', srv), Role('Fighter', srv)]
    aut = Member(name, roles, id=user_id)
    if voice:
        aut.voice = VoiceState('Voice ' + aut.name, is_afk=False, voice_channel=srv.channels[-1])

    return Message(content, aut, srv, srv.channels[1], None)


def fixed_id_fake_msg(content, user_id='1', name='User1', voice=False):
    """ Generate fake message with GearsandCogs as author. """
    srv = fake_servers()[0]
    roles = [Role('Everyone', srv), Role('Fighter', srv)]
    aut = Member(name, roles, id=user_id)
    if voice:
        aut.voice = VoiceState('Voice ' + aut.name, is_afk=False, voice_channel=srv.channels[-1])

    srv.id = 'a_server'
    for ind, chan in enumerate(srv.channels):
        chan.id = 'a_channel_{}'.format(ind)
    return Message(content, aut, srv, srv.channels[1], None)


@pytest.fixture
def f_bot():
    """
    Return a mocked bot.

    Bot must have methods:
        bot.send_message
        bot.send_long_message
        bot.send_ttl_message
        bot.delete_message
        bot.emoji.fix - EmojiResolver tested elsewhere
        bot.loop.run_in_executor, None, func, *args

    Bot must have attributes:
        bot.uptime
        bot.prefix
    """
    member = aiomock.Mock()
    member.mention = "@GearsandCogs"
    fake_bot = aiomock.AIOMock(uptime=5, prefix="!")
    fake_bot.send_message.async_return_value = None
    fake_bot.send_ttl_message.async_return_value = None
    fake_bot.send_long_message.async_return_value = None
    fake_bot.get_member_by_substr.return_value = member
    fake_bot.delete_message.async_return_value = None
    fake_bot.emoji.fix = lambda x, y: x
    fake_bot.servers = fake_servers()
    fake_bot.join_voice_channel.async_return_value = 'joined'

    def fake_exec(_, func, *args):
        return func(*args)
    fake_bot.loop.run_in_executor.async_side_effect = fake_exec

    yield fake_bot


@pytest.fixture
def f_mplayer_db():
    """
    Return a simple mplayer db sample.
    """
    fake_mplayer_db = {
        'exists': {
            'name': 'exists_local',
            'tags': [
                'classical',
                'chopin',
            ],
            'url': 'nocturne1.mp3',
        },
        'not_exists': {
            'name': 'not_exists',
            'tags': [
                'classical',
                'chopin',
            ],
            'url': 'ballade1.mp3',
        },
        'the_oddyssey': {
            'name': 'the_oddyssey',
            'tags': [
                'prog metal',
                'symphony x',
            ],
            'url': 'https://www.youtube.com/watch?v=M3nkuJO2y5I',
        },
        'bad_url': {
            'name': 'bad_url',
            'tags': [
                'invalid',
                'will not pass',
            ],
            'url': 'https://www.google.com/videos/24002',
        },
    }

    yield fake_mplayer_db


@pytest.fixture
def session():
    session = dicedb.Session()

    yield dicedb.Session()

    session.close()


@pytest.fixture
def db_cleanup():
    """ Nuke anything left in db after test. """
    yield

    dicedb.schema.empty_tables(dicedb.Session())


@pytest.fixture
def f_dusers(session):
    """
    Fixture to insert some test DUsers.
    """
    dusers = (
        DUser(id='1', display_name='User1', character='Wizard', init=7),
        DUser(id='2', display_name='User2', character='Fighter', init=2),
        DUser(id='3', display_name='User3', character='Rogue', init=3),
    )
    try:
        session.add_all(dusers)
        session.commit()
    except sqlalchemy.exc.IntegrityError:
        pass

    yield dusers

    for matched in session.query(DUser):
        session.delete(matched)
    session.commit()


@pytest.fixture
def f_saved_rolls(session, f_dusers):
    """
    Fixture to insert some test SavedRolls.

    Remember to put DUsers in.
    """
    rolls = (
        SavedRoll(name='Crossbow', roll_str='d20 + 7, d8', user_id=f_dusers[0].id),
        SavedRoll(name='Staff', roll_str='d20 + 2, d6', user_id=f_dusers[0].id),
        SavedRoll(name='LongSword', roll_str='d20 + 7, d8+4', user_id=f_dusers[1].id),
        SavedRoll(name='Dagger', roll_str='d20 + 5, d4 + 3', user_id=f_dusers[2].id),
    )
    session.add_all(rolls)
    session.commit()

    yield rolls

    for matched in session.query(SavedRoll):
        session.delete(matched)
    session.commit()


@pytest.fixture
def f_puns(session):
    """
    Fixture to insert some test Puns.
    """
    puns = (
        Pun(text='First pun', hits=2),
        Pun(text='Second pun', hits=0),
        Pun(text='Third pun', hits=1),
        Pun(text='Fourth pun', hits=0),
    )
    session.add_all(puns)
    session.commit()

    yield puns

    for matched in session.query(Pun):
        session.delete(matched)
    session.commit()


@pytest.fixture
def f_storedturns(session):
    """
    Fixture to insert some test Puns.
    """
    turns = (
        StoredTurn(id='server1-chan1', text='TurnOrder'),
        StoredTurn(id='server1-chan2', text='TurnOrder'),
    )
    session.add_all(turns)
    session.commit()

    yield turns

    for matched in session.query(StoredTurn):
        session.delete(matched)
    session.commit()
