"""
Used for pytest fixtures and anything else test setup/teardown related.
"""
from __future__ import absolute_import, print_function
import datetime
import sys

import aiomock
import pytest

try:
    import uvloop
    LOOP = uvloop.new_event_loop
    loop = LOOP()
    loop.set_debug(True)
    print("Test loop policy:", str(loop))
except ImportError:
    print("Missing: uvloop")
    sys.exit(1)


# @pytest.yield_fixture(scope='function', autouse=True)
# def around_all_tests(session):
    # """
    # Executes before and after EVERY test.

    # Can be helpful for tracking bugs, like dirty database after test.
    # Disabled unless needed. Non-trivial overhead.
    # """

    # yield

    # classes = [DUser, SheetRow, System, SystemUM, Drop, Hold]
    # for cls in classes:
        # assert not session.query(cls).all()


@pytest.fixture
def event_loop():
    """
    Provide a a new test loop for each test.
    Save system wide loop policy, and use uvloop if available.

    To test either:
        1) Mark with pytest.mark.asyncio
        2) event_loop.run_until_complete(asyncio.gather(futures))
    """
    loop = LOOP()
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
    def __init__(self, name, *, srv=None, id=None):
        super().__init__(name, id)
        self.server = srv

    # def __repr__(self):
        # return super().__repr__() + ", Server: {}".format(self.server.name)


class Member(FakeObject):
    def __init__(self, name, roles, *, id=None):
        super().__init__(name, id)
        self.discriminator = '12345'
        self.display_name = self.name
        self.roles = roles

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
        Channel("private_dev", srv=srv)
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

    def fake_exec(_, func, *args):
        return func(*args)
    fake_bot.loop.run_in_executor.async_side_effect = fake_exec

    yield fake_bot
