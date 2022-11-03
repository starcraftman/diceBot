"""
Common exceptions.
"""
# TODO: Has become messy, cleanup hierarchy and flow.
from __future__ import absolute_import, print_function

import dice.matcher


class DiceException(Exception):
    """
    All project exceptions subclass this.
    """
    def __init__(self, msg=None, lvl='info'):
        super().__init__(msg)
        self.log_level = lvl


class UserException(DiceException):
    """
    Exception occurred usually due to user error.

    Not unexpected but can indicate a problem.
    """


class ArgumentParseError(UserException):
    """ Error raised on failure to parse arguments. """


class ArgumentHelpError(UserException):
    """ Error raised on request to print help for command. """


class InvalidCommandArgs(UserException):
    """ Unable to process command due to bad arguements.  """


class InvalidPerms(UserException):
    """ Unable to process command due to insufficient permissions.  """


class CmdAborted(UserException):
    """ Raised to cancel a multistep command. """


class DBException(DiceException):
    """
    Exception occurred usually due to user error.

    Not unexpected but can indicate a problem.
    """


class MoreThanOneMatch(DBException):
    """ Too many matches were found for sequence.  """


class NoMatch(DBException):
    """ No match was found for sequence. """


class InternalException(DiceException):
    """
    An internal exception that went uncaught.

    Indicates a severe problem.
    """
    def __init__(self, msg, lvl='exception'):
        super().__init__(msg, lvl)


class RemoteError(InternalException):
    """
    Can no longer communicate with a remote that is required.
    """


def log_format(*, content, author, channel):
    """ Log useful information from discord.py """
    msg = "{aut} sent {cmd} from {cha}/{srv}"
    msg += "\n    Discord ID: " + str(author.id)
    msg += "\n    Username: {}#{}".format(author.name, author.discriminator)
    for role in author.roles[1:]:
        msg += "\n    {} on {}".format(role.name, role.guild.name)

    return msg.format(aut=author.display_name, cmd=content,
                      cha=channel, srv=channel.guild)


def write_log(exc, log, *, lvl='info', content, author, channel):
    """
    Log all relevant message about this session.
    """
    log_func = getattr(log, getattr(exc, 'lvl', lvl), lvl)
    header = '\n{}\n{}\n'.format(exc.__class__.__name__ + ': ' + str(exc), '=' * 20)
    log_func(header + log_format(content=content, author=author, channel=channel))
