# pylint: disable=redefined-outer-name,missing-function-docstring,unused-argument,redefined-builtin
"""
Used for pytest fixtures and anything else test setup/teardown related.
"""
from __future__ import absolute_import, print_function
import datetime
import sys

import aiomock
import discord
import pytest
import pytest_asyncio

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
        2) event_loop.run_until_complete(asyncio.gather(futures))
    """
    loop = uvloop.new_event_loop()
    loop.set_debug(True)

    yield loop

    loop.close()


# Fake objects look like discord data classes
class FakeObject():
    """
    A fake class to impersonate Data Classes from discord.py
    """
    oid = 0

    @classmethod
    def next_id(cls):
        cls.oid += 1
        return f'{cls.__name__}-{cls.oid}'

    def __init__(self, name, id=None):
        if not id:
            id = self.__class__.next_id()
        self.id = id
        self.name = name

    def __repr__(self):
        return f"{self.__class__.__name__}: {self.id} {self.name}"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name}"


class Guild(FakeObject):
    """
    A fake guild object for discord testing.
    """
    def __init__(self, name, id=None):
        super().__init__(name, id)
        self.channels = []

    def add(self, channel):
        self.channels.append(channel)

    # def __repr__(self):
        # channels = "\n  Channels: " + ", ".join([cha.name for cha in self.channels])
        # return super().__repr__() + channels


class Channel(FakeObject):
    """
    A fake channel for text.
    """
    def __init__(self, name, *, guild=None, type=0, id=None):
        super().__init__(name, id)
        self.guild = guild
        self.type = type

    # def __repr__(self):
        # return super().__repr__() + ", guild: {}".format(self.guild.name)


class VoiceState(FakeObject):
    """
    The voice state.
    """
    def __init__(self, name, *, is_afk=False, voice_channel=None, id=None):
        super().__init__(name, id)
        self.is_afk = is_afk
        self.voice_channel = voice_channel


class Member(FakeObject):
    """
    The member of a channel.
    """
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
    """
    A role of a member.
    """
    def __init__(self, name, guild=None, *, id=None):
        super().__init__(name, id)
        self.guild = guild

    # def __repr__(self):
        # return super().__repr__() + "\n  {}".format(self.guild)


class Message(FakeObject):
    """
    A message itself.
    """
    def __init__(self, content, author, guild, channel, mentions, *, id=None):
        super().__init__(None, id)
        self.author = author
        self.channel = channel
        self.content = content
        self.mentions = mentions
        self.guild = guild
        self.__mock = aiomock.AIOMock()
        self.__mock.delete.async_return_value = True
        self.delete = self.__mock.delete

    @property
    def timestamp(self):
        return datetime.datetime.utcnow()

    @property
    def mock(self):
        return self.__mock

    # def __repr__(self):
        # return super().__repr__() + "\n  Content: {}\n  Author: {}\n  Channel: {}\n  guild: {}".format(
            # self.content, self.author, self.channel, self.guild)


def fake_guilds():
    """ Generate fake discord guilds for testing. """
    guild = Guild("Gears' Hideout")
    channels = [
        Channel("general", id=4, guild=guild),
        Channel("dev", id=1, guild=guild),
        Channel("gaming", id=2, guild=guild),
        Channel("voice1", id=3, guild=guild, type=discord.ChannelType.voice),
    ]
    for cha in channels:
        guild.add(cha)

    return [guild]


def fake_msg_gears(content):
    """ Generate fake message with GearsandCogs as author. """
    guild = fake_guilds()[0]
    roles = [Role('Everyone', guild), Role('Cookie Lord', guild)]
    aut = Member("GearsandCogs", roles, id=1000)
    return Message(content, aut, guild, guild.channels[1], None)


def fake_msg_newuser(content):
    """ Generate fake message with GearsandCogs as author. """
    guild = fake_guilds()[0]
    roles = [Role('Everyone', guild), Role('Fighter', guild)]
    aut = Member("newuser", roles, id=1003)
    return Message(content, aut, guild, guild.channels[1], None)


def fake_msg(content, user_id=1, name='User1', voice=False):
    """ Generate fake message with GearsandCogs as author. """
    guild = fake_guilds()[0]
    roles = [Role('Everyone', guild), Role('Fighter', guild)]
    aut = Member(name, roles, id=user_id)
    if voice:
        aut.voice = VoiceState('Voice ' + aut.name, is_afk=False, voice_channel=guild.channels[-1])

    return Message(content, aut, guild, guild.channels[1], None)


def fixed_id_fake_msg(content, user_id=1, name='User1', voice=False):
    """ Generate fake message with GearsandCogs as author. """
    guild = fake_guilds()[0]
    roles = [Role('Everyone', guild), Role('Fighter', guild)]
    aut = Member(name, roles, id=user_id)
    if voice:
        aut.voice = VoiceState('Voice ' + aut.name, is_afk=False, voice_channel=guild.channels[-1])

    for ind, chan in enumerate(guild.channels):
        chan.id = ind
    return Message(content, aut, guild, guild.channels[1], None)


@pytest.fixture
def f_bot():
    """
    Return a mocked bot.

    Bot must have methods:
        bot.send
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
    fake_bot.send.async_return_value = None
    fake_bot.get_member_by_substr.return_value = member
    fake_bot.delete_message.async_return_value = None
    fake_bot.emoji.fix = lambda x, y: x
    fake_bot.guilds = fake_guilds()
    fake_bot.join_voice_channel.async_return_value = 'joined'

    def fake_exec(_, func, *args):
        return func(*args)
    fake_bot.loop.run_in_executor.async_side_effect = fake_exec

    yield fake_bot


#  @pytest.fixture
#  def f_mplayer_db():
    #  """
    #  Return a simple mplayer db sample.
    #  """
    #  fake_mplayer_db = {
        #  'exists': {
            #  'name': 'exists_local',
            #  'tags': [
                #  'classical',
                #  'chopin',
            #  ],
            #  'url': 'nocturne1.mp3',
        #  },
        #  'not_exists': {
            #  'name': 'not_exists',
            #  'tags': [
                #  'classical',
                #  'chopin',
            #  ],
            #  'url': 'ballade1.mp3',
        #  },
        #  'the_oddyssey': {
            #  'name': 'the_oddyssey',
            #  'tags': [
                #  'prog metal',
                #  'symphony x',
            #  ],
            #  'url': 'https://www.youtube.com/watch?v=M3nkuJO2y5I',
        #  },
        #  'bad_url': {
            #  'name': 'bad_url',
            #  'tags': [
                #  'invalid',
                #  'will not pass',
            #  ],
            #  'url': 'https://www.google.com/videos/24002',
        #  },
    #  }

    #  yield fake_mplayer_db


@pytest.fixture
def test_db():
    client = dicedb.get_db_client('test_dice')

    yield client


@pytest_asyncio.fixture()
async def db_cleanup(test_db):
    """ Nuke anything left in db after test. """
    yield

    for info in await test_db.list_collections():
        coll = await test_db.get_collection(info['name'])
        await coll.drop()


@pytest_asyncio.fixture
async def f_dusers(test_db):
    """
    Fixture to insert some test DUsers.
    """
    dusers = [
        {'discord_id': 1, 'display_name': 'User1'},
        {'discord_id': 2, 'display_name': 'User2'},
        {'discord_id': 3, 'display_name': 'User3'},
    ]
    await test_db.discord_users.insert_many(dusers)

    yield dusers

    await test_db.discord_users.delete_many({})


@pytest_asyncio.fixture
async def f_puns(test_db):
    """
    Fixture to insert some test Puns.
    """
    puns = (
        {'discord_id': 1, 'puns': [
            {'text': "First pun", 'hits': 0},
            {'text': 'Second pun', 'hits': 2},
            {'text': 'Third pun', 'hits': 7},
        ]},
    )
    await test_db.puns.insert_many(puns)

    yield puns

    await test_db.puns.delete_many({})


@pytest_asyncio.fixture
async def f_saved_rolls(test_db):
    """
    Fixture to insert some test SavedRolls.

    Remember to put DUsers in.
    """
    rolls = [
        {'name': 'Crossbow', 'roll': 'd20 + 7, d8', 'discord_id': 1},
        {'name': 'Staff', 'roll': 'd20 + 3, d8 - 2', 'discord_id': 1},
        {'name': 'LongSword', 'roll': 'd20 + 7, d8', 'discord_id': 2},
        {'name': 'Dagger', 'roll': 'd20 + 7, d8', 'discord_id': 3},
    ]
    await test_db.rolls_saved.insert_many(rolls)

    yield rolls

    await test_db.rolls_saved.delete_many({})


@pytest_asyncio.fixture
async def f_lastrolls(test_db):
    """
    Fixture to insert some test Googly objects.
    """
    rolls = (
        {'discord_id': 1, 'history': [
            {'roll': '4d6 + 1', 'result': '13'},
            {'roll': '4d6 + 2', 'result': '22'},
            {'roll': 'd20 + 5, 3d10 + 4', 'result': '22, 28'},
        ]},
        {'discord_id': 2, 'history': [
            {'roll': '3d6 + 3', 'result': '20'},
        ]},
    )
    await test_db.rolls_made.insert_many(rolls)

    yield rolls

    await test_db.rolls_made.delete_many({})


@pytest_asyncio.fixture
async def f_movies(test_db):
    """
    Fixture to insert some test Googly objects.
    """
    movies = (
        {"discord_id": 1, "name": "Movies", "entries": ["Toy Story", "Forest Gump", "A New Hope"]},
        {"discord_id": 2, "name": "Movies", "entries": ["Star Trek"]},
    )
    await test_db.lists.insert_many(movies)

    yield movies

    await test_db.lists.delete_many({})


@pytest_asyncio.fixture
async def f_googly(test_db):
    """
    Fixture to insert some test Googly objects.
    """
    googlys = (
        {'discord_id': 1, 'total': 95, 'used': 0},
        {'discord_id': 2, 'total': 40, 'used': 10},
        {'discord_id': 3, 'total': 55, 'used': 22},
    )
    await test_db.googly_eyes.insert_many(googlys)

    yield googlys

    await test_db.googly_eyes.delete_many({})


@pytest_asyncio.fixture
async def f_turnorders(test_db):
    """
    Fixture to insert some test Puns.
    """
    turns = (
        {'discord_id': 1, 'channel_id': 1, 'tracker': [
            {'name': 'orc', 'init': 4, 'roll': 21, 'effects': ''},
            {'name': 'chris', 'init': 9, 'roll': 20, 'effects': ''},
            {'name': 'hammy', 'init': 7, 'roll': 18, 'effects': ''},
        ]},
        {'discord_id': 1, 'channel_id': 2, 'tracker': [
            {'name': 'orc1', 'init': 4, 'roll': 15, 'effects': ''},
            {'name': 'orc2', 'init': 4, 'roll': 12, 'effects': ''},
            {'name': 'figher', 'init': 5, 'roll': 16, 'effects': ''},
        ]},
    )
    await test_db.combat_trackers.insert_many(turns)

    yield turns

    await test_db.combat_trackers.delete_many({})


#  @pytest_asyncio.fixture
#  def f_turnchars(test_db, f_dusers):
    #  """
    #  Fixture to insert some test Puns.
    #  """
    #  chars = (
        #  {'discord_id': 1, '
        #  TurnChar(user_key='1', turn_key='turn', name='Wizard', modifier=7),
        #  TurnChar(user_key='2', turn_key='turn', name='Fighter', modifier=2),
        #  TurnChar(user_key='3', turn_key='turn', name='Rogue', modifier=3),
    #  )
    #  session.add_all(chars)
    #  session.commit()

    #  yield chars

    #  for matched in session.query(TurnChar):
        #  session.delete(matched)
    #  session.commit()


#  @pytest_asyncio.fixture
#  def f_songs(session):
    #  """
    #  Fixture to insert some test Songs and SongTags.
    #  """
    #  tdir = tempfile.TemporaryDirectory()

    #  try:
        #  os.mkdir('/tmp/tmp')
    #  except OSError:
        #  pass

    #  with open('/tmp/tmp/late.opus', 'wb') as fout:
        #  fout.write(b'1')

    #  songs = (
        #  Song(id=1, name="crit", folder=tdir.name,
             #  url="https://youtu.be/IrbCrwtDIUA", repeat=False, volume_int=50),
        #  Song(id=2, name="pop", folder=tdir.name,
             #  url="https://youtu.be/7jgnv0xCv-k", repeat=False, volume_int=50),
        #  Song(id=3, name="late", folder='/tmp/tmp',
             #  url=None, repeat=False, volume_int=50),
    #  )
    #  tags = (
        #  SongTag(id=1, song_key=1, name='exciting'),
        #  SongTag(id=2, song_key=1, name='action'),
        #  SongTag(id=3, song_key=2, name='pop'),
        #  SongTag(id=4, song_key=2, name='public'),
        #  SongTag(id=5, song_key=3, name='late'),
        #  SongTag(id=6, song_key=3, name='lotr'),
    #  )
    #  session.add_all(songs + tags)
    #  session.commit()

    #  yield songs

    #  for matched in session.query(Song):
        #  session.delete(matched)
    #  for matched in session.query(SongTag):
        #  session.delete(matched)
    #  session.commit()
    #  tdir.cleanup()


#  @pytest.fixture
#  def f_vclient():
    #  mock = aiomock.AIOMock()
    #  mock.channel = Channel("VoiceChannel")
    #  mock.source = aiomock.AIOMock()  # The AudioStream
    #  mock.source.volume = 0.5
    #  mock.is_connected.return_value = False
    #  mock.is_playing.return_value = False
    #  mock.is_paused.return_value = False
    #  mock.play.return_value = True
    #  mock.stop.return_value = True
    #  mock.pause.return_value = True
    #  mock.resume.return_value = True
    #  mock.disconnect.async_return_value = True  # Async
    #  mock.move_to.async_return_value = True  # Async

    #  yield mock
