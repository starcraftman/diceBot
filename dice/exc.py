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


class MoreThanOneMatch(UserException):
    """ Too many matches were found for sequence.  """
    def __init__(self, needle, matches, cls, *, obj_attr=None):
        super().__init__()
        self.needle = needle
        self.matches = matches
        self.cls = cls
        self.obj_attr = obj_attr if obj_attr else ''

    def __str__(self):
        header = """Resubmit query with more specific criteria.
Too many matches for '{}' in {}s:
""".format(self.needle, self.cls)
        matched_strings = [dice.matcher.emphasize_match(self.needle, getattr(obj, self.obj_attr, obj))
                           for obj in self.matches]
        matched = "\n    - " + "\n    - ".join(matched_strings)
        return header + matched


class NoMatch(UserException):
    """ No match was found for sequence. """
    def __init__(self, needle, search_type):
        super().__init__()
        self.needle = needle
        self.search_type = search_type

    def __str__(self):
        return "No matches for '{}' in {}s.".format(self.needle, self.search_type)


class CmdAborted(UserException):
    """ Raised to cancel a multistep command. """


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
