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
    """ Subcommand parsing for hold """
    desc = """Evaluate some simple math operations.

{prefix}m 1 + 2
        Do simple math operations.
{prefix}m 1 + 2, 55/5, 5 * 10
        Do several math operations.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'math', aliases=[prefix + 'm'], description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Math')
    sub.add_argument('spec', nargs='+', help='The math operations.')


@register_parser
def subs_roll(subs, prefix):
    """ Subcommand parsing for hold """
    desc = """Evaluate some simple math operations.

{prefix}r 2d6 + 5, d20 + 4
        Perform the stated rolls and return results.
    """.format(prefix=prefix)
    sub = subs.add_parser(prefix + 'roll', aliases=[prefix + 'r'], description=desc, formatter_class=RawHelp)
    sub.set_defaults(cmd='Roll')
    sub.add_argument('spec', nargs='+', help='The dice rolls specified.')


@register_parser
def subs_status(subs, prefix):
    """ Subcommand parsing for status """
    sub = subs.add_parser(prefix + 'status', description='Info about this bot.')
    sub.set_defaults(cmd='Status')
