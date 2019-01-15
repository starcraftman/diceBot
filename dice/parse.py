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

{prefix}play youtube_link, song db name, local_name ...
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
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'play', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Play')
    sub.add_argument('-a', '--append', action="store_true", help='Append songs to playlist.')
    sub.add_argument('-l', '--loop', action="store_true", help='Toggle looping the music.')
    sub.add_argument('-p', '--pause', action="store_true", help='Toggle pausing the player.')
    sub.add_argument('-r', '--restart', action="store_true", help='Restart current song.')
    sub.add_argument('--status', action="store_true", help='Show player status.')
    sub.add_argument('-s', '--stop', action="store_true", help='Stop the music!')
    sub.add_argument('-n', '--next', action="store_true", help='Next song in list.')
    sub.add_argument('-v', '--prev', action="store_true", help='Previous song in list.')
    sub.add_argument('-o', '--volume', default='zero', help='Set the volume: [0, 100]')
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
{prefix}roll 6: 4d6, 2: 3d6 + 2d10 + 5
        Roll 4d6, __6__ times, 3d6 + 2d10 + 5 __2__ times.
{prefix}roll -s NameNoSpace 3d6 + 20
        Save to name 'NameNoSpace' the roll: 3d6 + 20. Any valid roll can be saved.
{prefix}roll -r NameNoSpace
        Remove NameNoSpace from saved rolls.
{prefix}roll NameNoSpace
        Roll the saved roll associated with NameNoSpace.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'roll', aliases=[prefix + 'r'], description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Roll')
    sub.add_argument('spec', nargs='*', help='The dice rolls specified.')
    sub.add_argument('-l', '--list', action='store_true', help='List all saved rolls.')
    sub.add_argument('-r', '--remove', help='Remove a saved dice.')
    sub.add_argument('-s', '--save', help='Save roll with this name.')


@register_parser
def subs_pf1(subs, prefix):
    """ Subcommand parsing for timers """
    desc = """Search something on d20PRSD Wiki for pathfinder.

{prefix}pf arcane mark
        Search for "arcane mark" and return first 3 matches.
{prefix}pf --num 5 arcane mark
        Search for "arcane mark" and return first 5 matches.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'pf', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='SearchWiki', base='PF_URL', wiki='Pathfinder Wiki')
    sub.add_argument('-n', '--num', type=int, default=3, help='Number of results.')
    sub.add_argument('terms', nargs='+', help='To search.')


@register_parser
def subs_d5e(subs, prefix):
    """ Subcommand parsing for timers """
    desc = """Search something on d20PRSD Wiki for pathfinder.

{prefix}d5 arcane mark
        Search for "arcane mark" and return first 3 matches.
{prefix}d5 --num 5 arcane mark
        Search for "arcane mark" and return first 5 matches.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'd5', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='SearchWiki', base='D5_URL', wiki='D&D 5e Wiki')
    sub.add_argument('-n', '--num', type=int, default=3, help='Number of results.')
    sub.add_argument('terms', nargs='+', help='To search.')


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
{prefix}songs --play
{prefix}songs -p
        Interactively via menus select a song from db to play.
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
    sub.add_argument('-p', '--play', action='store_true', help='Select a song from db to play.')
    sub.add_argument('-s', '--search', nargs='+', help='Search the song names.')
    sub.add_argument('-t', '--tag', nargs='+', help='Search the song names.')


@register_parser
def subs_status(subs, prefix):
    """ Subcommand parsing for status """
    sub = subs.add_parser(prefix + 'status', description='Info about this bot.')
    sub.set_defaults(cmd='Status')


@register_parser
def subs_turn(subs, prefix):
    """ Subcommand parsing for turn """
    desc = """Manage the turn order.

{prefix}turn
        Show the complete current turn order.
{prefix}turn --add a_name, init_offset/optional_roll, second_name, init_offset, ...
{prefix}turn -a a_name, init_offset/optional_roll, second_name, init_offset, ...
        Add a user to the existing turn order.
{prefix}turn --clear
{prefix}turn -c
        Clear the existing turn order.
{prefix}turn --next
{prefix}turn -n
        Select the next person in order.
{prefix}turn --remove a user, another user
{prefix}turn -r a user, another user
        Remove a user from the turn order.
{prefix}turn --char A name
        Set your character name for turn order.
{prefix}turn --init -5
        Set your character init for turn order.
{prefix}turn --update Chris/1, Noggles/22, ...
        Override the rolls for init for matching characters.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'turn', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Turn')
    sub.add_argument('-a', '--add', nargs='+', help='Add a user to the turn order.')
    sub.add_argument('-c', '--clear', action='store_true', help='Clear the turn order.')
    sub.add_argument('--init', type=int, help='Set turn order init.')
    sub.add_argument('--name', nargs='+', help='Set turn order name.')
    sub.add_argument('-n', '--next', action='store_true', help='Add a user to the turn order.')
    sub.add_argument('-r', '--remove', nargs='+', help='Remove a user.')
    sub.add_argument('--update', nargs='+', help='Update the following users.')


@register_parser
def subs_effect(subs, prefix):
    """ Subcommand parsing for roll """
    desc = """Evaluate some simple math operations.

{prefix}effect --add Poison/3, Stun/3 -t Char1, Char2
        Add the poison and stun effects to the user for 3 turns each.
{prefix}effect --remove Poison, Stun -t Char1
        Remove the poison and stun effects for the user.
{prefix}effect --update Poison/1, Stun/1 -t Char1
        Update the poison effect for the user to 1 turn left.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'effect', aliases=[prefix + 'e'],
                          description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Effect')
    sub.add_argument('effects', nargs='*', help='Update the remaining turns for user.')
    sub.add_argument('-a', '--add', action='store_true', help='Add effects for the user.')
    sub.add_argument('-r', '--remove', action='store_true', help='remove the effect from a user.')
    sub.add_argument('-u', '--update', action='store_true', help='Update the effects turns for user.')
    sub.add_argument('-t', '--targets', nargs='+', help='Users to target with effects.')


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


@register_parser
def subs_n(subs, prefix):
    """ Subcommand parsing for timer """
    desc = """Shortcut for !turn --next

{prefix}n
        Show next turn player.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'n', description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Turn', next=True, clear=False, remove=False, add=False)
