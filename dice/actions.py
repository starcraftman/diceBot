"""
To facilitate complex actions based on commands create a
hierarchy of actions that can be recombined in any order.
All actions have async execute methods.
"""
from __future__ import absolute_import, print_function
import asyncio
import logging
import re
import sys

import dice.tbl
import dice.util


async def bot_shutdown(bot, delay=30):  # pragma: no cover
    """
    Shutdown the bot. Not ideal, I should reconsider later.
    """
    await asyncio.sleep(delay)
    await bot.logout()
    await asyncio.sleep(3)
    sys.exit(0)


class Action(object):
    """
    Top level action, contains shared logic.
    """
    def __init__(self, **kwargs):
        self.args = kwargs['args']
        self.bot = kwargs['bot']
        self.msg = kwargs['msg']
        self.log = logging.getLogger('dice.actions')

    async def execute(self):
        """
        Take steps to accomplish requested action, including possibly
        invoking and scheduling other actions.
        """
        raise NotImplementedError


class Help(Action):
    """
    Provide an overview of help.
    """
    async def execute(self):
        prefix = self.bot.prefix
        over = [
            'Here is an overview of my commands.',
            '',
            'For more information do: `{}Command -h`'.format(prefix),
            '       Example: `{}drop -h`'.format(prefix),
            '',
        ]
        lines = [
            ['Command', 'Effect'],
            ['{prefix}math', 'Do some math operations'],
            ['{prefix}roll', 'Roll a dice like: 2d6 + 5'],
            ['{prefix}status', 'Show status of bot including uptime'],
            ['{prefix}help', 'This help message'],
        ]
        lines = [[line[0].format(prefix=prefix), line[1]] for line in lines]

        response = '\n'.join(over) + dice.tbl.wrap_markdown(dice.tbl.format_table(lines, header=True))
        await self.bot.send_ttl_message(self.msg.channel, response)
        await self.bot.delete_message(self.msg)


class Math(Action):
    """
    Who is request to Inara for CMDR info.

    """
    async def execute(self):
        resp = ['__Math Calculations__', '']
        for line in ' '.join(self.args.spec).split(','):
            line = line.strip()
            if re.match(r'[^0-9 +-/*]', line):
                resp += [line + " looks suspicious, I won't evaluate."]
                continue

            # FIXME: Dangerous, but re blocking anything not simple maths.
            resp += [line + " = " + str(eval(line))]

        await self.bot.send_message(self.msg.channel, '\n'.join(resp))


class Roll(Action):
    """
    Who is request to Inara for CMDR info.

    """
    async def execute(self):
        await self.bot.send_message(self.msg.channel, 'Do your own rolls!')


class Status(Action):
    """
    Display the status of this bot.
    """
    async def execute(self):
        lines = [
            ['Created By', 'GearsandCogs'],
            ['Uptime', self.bot.uptime],
            ['Version', '{}'.format(dice.__version__)],
        ]

        await self.bot.send_message(self.msg.channel,
                                    dice.tbl.wrap_markdown(dice.tbl.format_table(lines)))
