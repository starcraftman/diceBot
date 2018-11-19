"""
Everything related to parsing arguements from the received text.

By setting defaults passed on the parser (cmd, subcmd) can differeciate
what action to be invoked.
"""
from __future__ import absolute_import, print_function

import argparse
from argparse import RawDescriptionHelpFormatter as RawHelp

import dice.exc

PARSERS = []


class ThrowArggumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass that does NOT terminate the program.
    """
    def print_help(self, file=None):  # pylint: disable=redefined-builtin
        formatter = self._get_formatter()
        formatter.add_text(self.description)
        raise dice.exc.ArgumentHelpError(formatter.format_help())

    def error(self, message):
        raise dice.exc.ArgumentParseError(message)

    def exit(self, status=0, message=None):
        """
        Suppress default exit behaviour.
        """
        raise dice.exc.ArgumentParseError(message)


def make_parser(prefix):
    """
    Returns the bot parser.
    """
    parser = ThrowArggumentParser(prog='', description='simple discord bot')

    subs = parser.add_subparsers(title='subcommands',
                                 description='The subcommands of dice')

    for func in PARSERS:
        func(subs, prefix)

    return parser


def register_parser(func):
    """ Simple registration function, use as decorator. """
    PARSERS.append(func)
    return func


@register_parser
def subs_help(subs, prefix):
    """ Subcommand parsing for help """
    sub = subs.add_parser(prefix + 'help', description='Show overall help message.')
    sub.set_defaults(cmd='Help')


@register_parser
def subs_math(subs, prefix):
    """ Subcommand parsing for math """
    desc = """Evaluate some simple math operations.

{prefix}math 1 + 2
        Do simple math operations.
{prefix}math 1 + 2, 55/5, 5 * 10
        Do several math operations.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'math', aliases=[prefix + 'm'], description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Math')
    sub.add_argument('spec', nargs='+', help='The math operations.')


@register_parser
def subs_play(subs, prefix):
    """ Subcommand parsing for timers """
    desc = """A simple music player for games.

{prefix}play youtube_link youtube_link2 local_name ...
        Play one or more youtube links or local files on server.
{prefix}play -p
{prefix}play --pause
        Pause or resume playing the music.
{prefix}play -s
{prefix}play --stop
        Stop playing the music.
{prefix}play -r
{prefix}play --restart
        Play the current song from the beginning.
{prefix}play -n
{prefix}play --next
        Play the next song.
{prefix}play -v
{prefix}play --prev
        Play the previous song.
{prefix}play -a youtube_link_1 local_name_1
{prefix}play --append youtube_link_1 local_name_1
        Append the following songs to the list.
{prefix}play -o
{prefix}play --volume
        Set the volume: [0, 100]')
{prefix}play --db
        Play something stored in song db.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'play', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Play')
    sub.add_argument('-a', '--append', action="store_true", help='Append songs to playlist.')
    sub.add_argument('-l', '--loop', action="store_true", help='Toggle looping the music.')
    sub.add_argument('-p', '--pause', action="store_true", help='Toggle pausing the player.')
    sub.add_argument('-r', '--restart', action="store_true", help='Restart current song.')
    sub.add_argument('-s', '--stop', action="store_true", help='Stop the music!')
    sub.add_argument('-n', '--next', action="store_true", help='Next song in list.')
    sub.add_argument('-v', '--prev', action="store_true", help='Previous song in list.')
    sub.add_argument('-o', '--volume', type=int, help='Set the volume: [0, 100]')
    sub.add_argument('--db', action='store_true', help='Play song from db.')
    sub.add_argument('vids', nargs="*", default=[], help='A single youtube link to play.')


@register_parser
def subs_roll(subs, prefix):
    """ Subcommand parsing for roll """
    desc = """Evaluate some simple math operations.

{prefix}roll 2d6 + 5, d20 + 4
        Perform the stated rolls and return results.
{prefix}roll 4d6kh3
{prefix}roll 4d6k3
        Roll 4d6, keep the 3 __highest__ rolls.
{prefix}roll 4d6kl2
        Roll 4d6, keep the 2 __lowest__ rolls.
{prefix}roll 6 * (4d6)
        Roll 4d6, __6__ times.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'roll', aliases=[prefix + 'r'], description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Roll')
    sub.add_argument('spec', nargs='+', help='The dice rolls specified.')


@register_parser
def subs_poni(subs, prefix):
    """ Subcommand parsing for timers """
    desc = """Be magical!

{prefix}poni tag_1, tag 2, tag of words
        Do something poniful!
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'poni', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Poni')
    sub.add_argument('tags', nargs='+', help='To search.')


@register_parser
def subs_songs(subs, prefix):
    """ Subcommand parsing for songs """
    desc = """Manage the song lookup.

{prefix}songs --add name, youtube_link, tag1, tag2, tag3
{prefix}songs -a name, youtube_link, tag1, tag2, tag3
{prefix}songs --add name, local_path_name, tag1, tag2
{prefix}songs -a name, local_path_name, tag1, tag2
        Add all names into the songs mapping.
{prefix}songs --list
{prefix}songs -l
        List everything in the db.
{prefix}songs --manage name/youtube_link name/local_name1
{prefix}songs -m name/youtube_link name/local_name1
        Manage the songs in the db interactively.
{prefix}songs --searche name_song
{prefix}songs -s name_song
        Search for a name of song (loose match).
{prefix}songs --tag tag_name
{prefix}songs -t tag_name
        Search for a tag (loose match).
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'songs', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Songs')
    sub.add_argument('-a', '--add', nargs='+', help='Add a song to the mappings.')
    sub.add_argument('-l', '--list', action='store_true', help='Show all mappings.')
    sub.add_argument('-m', '--manage', action='store_true', help='Manage the mappings.')
    sub.add_argument('-s', '--search', nargs='+', help='Search the song names.')
    sub.add_argument('-t', '--tag', nargs='+', help='Search the song names.')


@register_parser
def subs_status(subs, prefix):
    """ Subcommand parsing for status """
    sub = subs.add_parser(prefix + 'status', description='Info about this bot.')
    sub.set_defaults(cmd='Status')


@register_parser
def subs_timer(subs, prefix):
    """ Subcommand parsing for timer """
    desc = """Set timers to remind you of things later!

    Default warnings if timer greater than vvalue:
        Warn at 60 minutes to finish.
        Warn at 15 minutes to finish.
        Warn at 5 minutes to finish.
        Warn at 1 minute to finish.

    Time specification: HH:MM:SS

{prefix}timer 1:15:00
        Wait for 1:15:00 and then mention user. Default warnings will warn user as approached.
{prefix}timer 3:30 -d Tea timer
        Wait for HH:MM:SS seconds and then mention user. Tea timer is set as the descritpion.
{prefix}timer 3:30 -w 60 -w 30 -d Tea timer
        Wait for 3:30 then mention user. Tea timer is set as the descritpion.
        User will be warned at 60 seconds and 30 seconds left.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'timer', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Timer')
    sub.add_argument('time', help='The time to wait.')
    sub.add_argument('-w', '--warn', dest="offsets", action="append",
                     help='The number of offsets to warn user from end.')
    sub.add_argument('-d', '--description', nargs="+", help='The description of timer.')


@register_parser
def subs_timers(subs, prefix):
    """ Subcommand parsing for timers """
    desc = """Manage your timers.

{prefix}timers
        Print all active timers you've started.
{prefix}timers --clear
        Clear all active timers you've started.
{prefix}timers --manage
        Interactively manage timers. Write 'done' to stop.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'timers', description=desc, formatter_class=RawHelp)
    sub.add_argument('-c', '--clear', action="store_true", help='Clear all timers.')
    sub.add_argument('-m', '--manage', action="store_true", help='Manage timers selectively.')
    sub.set_defaults(cmd='Timers')
