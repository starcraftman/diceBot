"""
Common exceptions.
"""
from __future__ import absolute_import, print_function

import dice.util


class DiceException(Exception):
    """
    All exceptions subclass this. All exceptions can:
        - Write something useful to the log.
        - Reply to the user with some relevant response.
    """
    def __init__(self, msg=None, lvl='info'):
        super().__init__()
        self.log_level = lvl
        self.message = msg

    def write_log(self, log, *, content, author, channel):
        """
        Log all relevant message about this session.
        """
        log_func = getattr(log, self.log_level)
        header = '\n{}\n{}\n'.format(self.__class__.__name__ + ': ' + self.reply(), '=' * 20)
        log_func(header + log_format(content=content, author=author, channel=channel))

    def reply(self):
        """
        Construct a reponse to user.
        """
        return self.message

    def __str__(self):
        return self.reply()


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
    def __init__(self, sequence, matches, obj_attr=None):
        super().__init__()
        self.sequence = sequence
        self.matches = matches
        self.obj_attr = obj_attr if obj_attr else ''

    def reply(self):
        obj = self.matches[0]
        if not obj or isinstance(obj, type('')):
            cls = 'string'
        else:
            cls = self.matches[0].__class__.__name__

        header = "Resubmit query with more specific criteria."
        header += "\nToo many matches for '{}' in {}s:".format(
            self.sequence, cls)
        matched_strings = [dice.util.emphasize_match(self.sequence, getattr(obj, self.obj_attr, obj))
                           for obj in self.matches]
        matched = "\n    - " + "\n    - ".join(matched_strings)
        return header + matched


class NoMatch(UserException):
    """
    No match was found for sequence.
    """
    def __init__(self, sequence, obj_type):
        super().__init__()
        self.sequence = sequence
        self.obj_type = obj_type

    def reply(self):
        return "No matches for '{}' in {}s.".format(self.sequence, self.obj_type)


class CmdAborted(UserException):
    """ Raised to cancel a multistep command. """


class InternalException(DiceException):
    """
    An internal exception that went uncaught.

    Indicates a severe problem.
    """
    def __init__(self, msg, lvl='exception'):
        super().__init__(msg, lvl)


class ColOverflow(InternalException):
    """ Raise when a column has reached end, increment next column.  """
    def __init__(self):
        super().__init__('Serious problem, uncaught overflow.', 'exception')


class MissingConfigFile(InternalException):
    """ Thrown if a config isn't set properly.  """


class MsgTooLong(InternalException):
    """
    Reached Discord's maximum message length.
    """


class NoMoreTargets(InternalException):
    """
    There are no more fort targets.
    """


class RemoteError(InternalException):
    """
    Can no longer communicate with a remote that is required.
    """


class SheetParsingError(InternalException):
    """
    During sheet parsing, could not determine cell anchors properly.
    """
    def __init__(self):
        super().__init__('Serious problem, this message should not print.')


class NameCollisionError(SheetParsingError):
    """
    During parsing, two cmdr names collided.
    """
    def __init__(self, sheet, name, rows):
        super().__init__()
        self.name = name
        self.sheet = sheet
        self.rows = rows

    def reply(self):
        lines = [
            "**Critical Error**",
            "----------------",
            "CMDR \"{}\" found in rows {} of the {} Sheet".format(self.name, str(self.rows),
                                                                  self.sheet),
            "",
            "To Resolve:",
            "    Delete or rename the cmdr in one of these rows",
            "    Then execute `admin scan` to reload the db",
        ]
        return "\n".join(lines)


def log_format(*, content, author, channel):
    """ Log useful information from discord.py """
    msg = "{aut} sent {cmd} from {cha}/{srv}"
    msg += "\n    Discord ID: " + author.id
    msg += "\n    Username: {}#{}".format(author.name, author.discriminator)
    for role in author.roles[1:]:
        msg += "\n    {} on {}".format(role.name, role.server.name)

    return msg.format(aut=author.display_name, cmd=content,
                      cha=channel, srv=channel.server)
