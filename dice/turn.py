"""
Implement a simple turn order manager.
"""
from __future__ import absolute_import, print_function
from functools import total_ordering

import numpy.random as rand

import dice.exc
import dice.tbl

COLLIDE_INCREMENT = 0.01


def break_init_tie(user1, user2):
    """
    Resolve a tie of two player inits according to Pathfinder rules.
    - Highest offset if they differ goes first.
    - If same offset, keep rolling until different.

    Returns:
        (winner, loser) - Ordered tuple, winner takes old init. Loser moves back.
    """
    winner, loser = None, None
    if user1.offset > user2.offset:
        winner, loser = user1, user2
    elif user1.offset < user2.offset:
        winner, loser = user2, user1

    if not winner:
        while user1.init == user2.init:
            user1.roll_init()
            user2.roll_init()

        winner = user1 if user1 > user2 else user2
        loser = user1 if user1 < user2 else user2

    return (winner, loser)


def parse_turn_users(parts):
    """
    Parse usrs based on possible specification.
    Expected parts: [username, offset, username, offset/premade_roll, ...]

    Raises:
        InvalidCommandArgs - Improper parts.

    Returns:
        Parsed TurnUsers in a list.
    """
    if len(parts) % 2:
        raise dice.exc.InvalidCommandArgs("Improperly formatted turn command.")

    users = []
    while parts:
        try:
            name = parts[0].strip()
            roll = None
            offset = int(parts[1])
        except ValueError:
            offset, roll = [int(x) for x in parts[1].split('/')]

        parts = parts[2:]
        users += [dice.turn.TurnUser(name, offset, roll)]

    return users


@total_ordering
class TurnUser(object):
    """
    A user in a TurnOrder.
    Has a unique name and an initiative roll.
    """
    def __init__(self, name, offset, init=None):
        self.name = name
        self.offset = offset
        self.init = init
        if not init:
            self.init = self.roll_init()

    def __str__(self):
        return '{} ({}): {:.2f}'.format(self.name, self.offset, self.init)

    def __repr__(self):
        return 'TurnUser(name={}, offset={}, init={})'.format(
            self.name, self.offset, self.init)

    def __eq__(self, other):
        return (self.name, self.offset, self.init) == (other.name, other.offset, other.init)

    def __ne__(self, other):
        return (self.name, self.offset, self.init) != (other.name, other.offset, other.init)

    def __lt__(self, other):
        return self.init < other.init

    @property
    def last_roll(self):
        """ The last roll of d20 dice. """
        return self.init - self.offset

    def roll_init(self):
        """
        A person rolls d20 + init offset.
        """
        self.init = rand.randint(1, 21) + self.offset

        return self.init


class TurnOrder(object):
    """
    Model the turn order for combat in Pathfinder.
    A turn order is composed of TurnUser objects.
    """
    def __init__(self, users=None, cur_user=None):
        """
        Unless recreating an object, always use add() or add_all().
        """
        if not users:
            users = []
        self.users = users
        self.cur_user = cur_user

    def __str__(self):
        msg = '__**Turn Order**__\n\n'

        rows = [['name', 'mod.', 'init']]
        for user in self.users:
            name = '> {} <'.format(user.name) if self.cur_user and user == self.cur_user else user.name
            offset = '{}{}'.format('+' if user.offset >= 0 else '-', user.offset)
            init = '{:0.2f}'.format(user.init)
            rows += [[name, offset, init]]

        msg += dice.tbl.wrap_markdown(dice.tbl.format_table(rows, header=True))

        return msg

    def __repr__(self):
        return 'TurnOrder(users={}, cur_user={})'.format(self.users, self.cur_user)

    def does_name_exist(self, new_name):
        """
        Sanity check for name collision.
        """
        return new_name in [x.name for x in self.users]

    def duplicate_inits(self, other=None):
        """
        Return which init values are duplicated, an empty list means all unique.

        Args:
            other - A user to consider that isn't yet in self.users

        Returns:
            [] - No duplicates.
            [dupe_init] - At least 2 duplicates exist.
        """
        inits = [x.init for x in self.users]
        if other:
            inits += [other.init]

        for init in set(inits):
            inits.remove(init)

        return inits

    def resolve_collision(self, user, dupe_inits):
        """
        Find existing user with same init, roll both until we can differentiate.

        Returns:
            user - With new init if needed changing.
        """
        dupe_init = dupe_inits[0]
        conflict = [x for x in self.users if x.init == dupe_init and x != user][0]

        winner, loser = break_init_tie(user, conflict)

        winner.init = dupe_init
        loser.init = dupe_init - COLLIDE_INCREMENT

        new_dupes = self.duplicate_inits()
        while new_dupes:
            self.resolve_collision(loser, new_dupes)
            new_dupes = self.duplicate_inits()

        return user

    def add(self, user):
        """
        Add a user to the turn order, resolve if collision.
        """
        if self.does_name_exist(user.name):
            raise dice.exc.InvalidCommandArgs("Cannot have two users with same name.")

        dupes = self.duplicate_inits(user)
        while dupes:
            self.resolve_collision(user, dupes)
            dupes = self.duplicate_inits(user)

        self.users.append(user)
        self.users = list(reversed(sorted(self.users)))

    def add_all(self, users):
        """
        Convenience bulk addition of users.
        """
        for user in users:
            self.add(user)

    def remove(self, name):
        """
        Remove a user from the turn order and adjust index.
        """
        if self.cur_user and self.cur_user.name == name:
            self.next()

        cnt = 0
        for user in self.users:
            if user.name == name:
                break
            cnt += 1

        if cnt == len(self.users):
            raise dice.exc.InvalidCommandArgs("User not found: " + name)

        del self.users[cnt]

    def next(self):
        """
        Set the next user to take a turn.
        """
        if not self.users:
            raise dice.exc.InvalidCommandArgs("Add some users first!")

        if not self.cur_user or self.cur_user == self.users[-1]:
            self.cur_user = self.users[0]
        else:
            last_user = self.users[0]
            for user in self.users[1:]:
                if last_user == self.cur_user:
                    self.cur_user = user
                    break
                last_user = user

        return self.cur_user
