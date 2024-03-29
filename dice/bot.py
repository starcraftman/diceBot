"""
This is the main bot. Everything is started upon main() execution. To invoke from root:
    python -m dice.bot

Some useful docs on libraries
-----------------------------
Python 3.5 async tutorial:
    https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/

asyncio (builtin package):
    https://docs.python.org/3/library/asyncio.html

discord.py: The main discord library, hooks events.
    https://discordpy.readthedocs.io/en/latest/api.html
"""
from __future__ import absolute_import, print_function
import asyncio
import datetime
import logging
import os
import pprint
import re
import signal
import sys

import discord
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.get_event_loop().set_debug(True)
except ImportError:
    print("Falling back to default python loop.")
finally:
    print("Default event loop:", asyncio.get_event_loop())

import dice.actions
import dice.exc
import dice.parse
import dice.util
import dice.music

LIVE_TASKS = []


class EmojiResolver():
    """
    Map emoji embeds onto the text required to make them appear.
    """
    def __init__(self):
        # For each server, store a dict of emojis on that server
        self.emojis = {}

    def __str__(self):
        """ Just dump the emoji db. """
        return pprint.pformat(self.emojis, indent=2)

    def update(self, guilds):
        """
        Update the emoji dictionary. Call this in on_ready.
        """
        for guild in guilds:
            emoji_names = [emoji.name for emoji in guild.emojis]
            self.emojis[guild.name] = dict(zip(emoji_names, guild.emojis))

    def fix(self, content, guild):
        """
        Expand any emojis for bot before sending, based on guild emojis.

        Embed emojis into the content just like on guild surrounded by ':'. Example:
            Status :Fortifying:
        """
        emojis = self.emojis[guild.name]
        for embed in list(set(re.findall(r':\S+:', content))):
            try:
                emoji = emojis[embed[1:-1]]
                content = content.replace(embed, str(emoji))
            except KeyError:
                logging.getLogger('dice.bot').warning(
                    'EMOJI: Could not find emoji %s for guild %s', embed, guild.name)

        return content


class DiceBot(discord.Client):
    """
    The main bot, hooks onto on_message primarily and waits for commands.
    """
    def __init__(self, prefix, **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix
        self.emoji = EmojiResolver()
        self.parser = dice.parse.make_parser(prefix)
        self.start_date = datetime.datetime.utcnow().replace(microsecond=0)
        self.player = None

    @property
    def uptime(self):  # pragma: no cover
        """
        Return the uptime since bot was started.
        """
        return str(datetime.datetime.utcnow().replace(microsecond=0) - self.start_date)

    def get_member_by_substr(self, name):
        """
        Given a (substring of a) member name, find the first member that has a similar name.
        Not case sensitive.

        Returns: The discord.Member object or None if nothing found.
        """
        name = name.lower()
        for member in self.get_all_members():
            if name in member.display_name.lower():
                return member

        return None

    def get_channel_by_name(self, name):
        """
        Given channel name, get the Channel object requested.
        There shouldn't be any collisions.

        Returns: The discord.Channel object or None if nothing found.
        """
        return discord.utils.get(self.get_all_channels(), name=name)

    # Events hooked by bot.
    async def on_member_join(self, member):
        """ Called when member joins guild (login). """
        log = logging.getLogger('dice.bot')
        log.info('Member has joined: %s', member.display_name)

    async def on_member_leave(self, member):
        """ Called when member leaves guild (logout). """
        log = logging.getLogger('dice.bot')
        log.info('Member has left: %s', member.display_name)

    async def on_guild_emojis_update(self, *_):
        """ Called when emojis change, just update all emojis. """
        self.emoji.update(self.guilds)

    async def on_ready(self):
        """
        Event triggered when connection established to discord and bot ready.
        """
        log = logging.getLogger('dice.bot')
        log.info('Logged in as: %s', self.user.name)
        log.info('Available on following guilds:')
        for guild in self.guilds:
            log.info('  "%s" with id %s', guild.name, guild.id)

        self.emoji.update(self.guilds)
        await self.change_presence(activity=discord.Game("Rolling dice vigorously."))

        print('DiceBot Ready!')

    async def on_message(self, message):
        """
        Intercepts every message sent to guild!

        Notes:
            message.author - Returns member object
                roles -> List of Role objects. First always @everyone.
                    roles[0].name -> String name of role.
            message.channel - Channel object.
                name -> Name of channel
                guild -> Guild of channel
                    members -> Iterable of all members
                    channels -> Iterable of all channels
                    get_member_by_name -> Search for user by nick
            message.content - The text
        """
        content = message.content
        author = message.author
        channel = message.channel

        if message.author.bot or not message.content.startswith(self.prefix):
            return

        log = logging.getLogger('dice.bot')
        log.info("Guild: '%s' Channel: '%s' User: '%s' | %s",
                 channel.guild, channel.name, author.name, content)

        try:
            content = re.sub(r'<[#@]\S+>', '', content).strip()  # Strip mentions from text
            args = self.parser.parse_args(re.split(r'\s+', content))
            await self.dispatch_command(args=args, bot=self, msg=message)

        except dice.exc.ArgumentParseError as exc:
            log.exception("Failed to parse command. '%s' | %s", author.name, content)
            dice.exc.write_log(exc, log, content=content, author=author, channel=channel)
            if 'invalid choice' not in str(exc):
                try:
                    self.parser.parse_args(content.split(' ')[0:1] + ['--help'])
                except dice.exc.ArgumentHelpError as exc2:
                    args = list(exc.args)
                    args += ['Invalid command use. Check the command help.']
                    args += [f"\n{len(str(exc)) * '-'}\n{str(exc2)}"]
            await self.send(channel, str(exc), ttl=True)
            try:
                await message.delete()
            except discord.DiscordException:
                pass

        except (dice.exc.UserException, dice.exc.InternalException, IOError, OSError) as exc:
            dice.exc.write_log(exc, log, content=content, author=author, channel=channel)
            await self.send(channel, str(exc))
            raise exc

        except discord.DiscordException as exc:
            if exc.args[0].startswith("BAD REQUEST (status code: 400"):
                await self.send(channel, "It appears Response would be > 2000 chars, cannot transmit.", ttl=True)
                try:
                    await message.delete()
                except discord.DiscordException:
                    pass
            else:
                owner = channel.guild.owner.mention
                await self.send(channel, f"A critical discord error occurred, see log {owner}.")
            line = "Discord.py Library raised an exception"
            line += dice.exc.log_format(content=content, author=author, channel=channel)
            log.exception(line)

    async def dispatch_command(self, **kwargs):
        """
        Simply inspect class and dispatch command. Guaranteed to be valid.
        """
        args = kwargs.get('args')
        cls = getattr(dice.actions, args.cmd)

        await cls(**kwargs).execute()

    async def send(self, channel, content=None, *, ttl=False, **kwargs):
        """
        Almost identical to discord.Client.send

        Differences:

            By default, messages longer than 2k will be split on new lines and sent
            sequentially automatically. If message contains no new lines, truncate at limit.

            To send a TTL message with default time, set ttl=True
            To send a TTL with non-standard time, use delete_after like normal.

            Log any sending errors to trace cause.

        Raises:
            Anything discord.Client.send can.

        Returns:
            Always returns a list of dice.Messages sent to the user.
        """
        if ttl:
            kwargs.update({'delete_after': dice.util.get_config('ttl')})

        sent = []
        for part in dice.util.msg_splitter(content):
            try:
                sent += [await channel.send(part, **kwargs)]
            except discord.DiscordException as exc:
                # Monitor any errors on sending to log
                logging.getLogger('dice.bot').error(exc)
                raise

        return sent

    async def broadcast(self, content, ttl=False, channels=None, **kwargs):
        """
        By default, broadcast a normal message to all channels bot can see.

        args:
            content: The message.
            ttl: If true, send a message that deletes itself.
            channels: A list of channel names (strings) to broadcast to.
         """
        if ttl:
            kwargs.update({'delete_after': dice.util.get_config('ttl')})

        if channels:
            channels = [self.get_channel_by_name(name) for name in channels]
        else:
            channels = list(self.get_all_channels())

        messages = []
        for channel in channels:
            if channel.permissions_for(channel.guild.me).send_messages and \
               channel.type == discord.ChannelType.text:
                messages += [self.send(channel, "**Broadcast**\n\n" + content, **kwargs)]

        await asyncio.gather(*messages)


async def presence_task(bot, delay=3):
    """
    Update the bot's activity at regular intervals.
    """
    print('Presence task started')
    while True:
        try:
            activity = discord.Activity(name=bot.status, type=discord.ActivityType.streaming)
            await bot.change_presence(activity=activity)
        except discord.DiscordException:
            pass

        await asyncio.sleep(delay)


def sig_handle(sig, frame, *rest):
    """ Force cleanup on systemd SIGTERM by pretending Ctrl + c """
    raise KeyboardInterrupt('Shut it all down!')


def main():  # pragma: no cover
    """ Entry here! """
    try:
        dice.util.init_logging()
        seeded = dice.util.seed_random()
        logging.getLogger('dice.bot').warning('Seeding numpy/random with: %s', str(seeded))
        print(f'Seeding numpy/random with: {seeded:,}')

        # Intents for: member info, dms and message.content access
        intents = discord.Intents.default()
        intents.members = True  # pylint: disable=assigning-non-slot
        intents.messages = True  # pylint: disable=assigning-non-slot
        intents.message_content = True  # pylint: disable=assigning-non-slot
        bot = DiceBot("!", intents=intents)
        dice.util.BOT = bot

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGTERM, sig_handle)
        signal.signal(signal.SIGTERM, sig_handle)

        token = dice.util.get_config('discord', os.environ.get('TOKEN', 'dev'))
        # BLOCKING: N.o. e.s.c.a.p.e.
        loop.run_until_complete(bot.start(token))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.close())
    finally:
        print('\nFinished Logging out.\n\nGoodbye human!')


if __name__ == "__main__":  # pragma: no cover
    main()
