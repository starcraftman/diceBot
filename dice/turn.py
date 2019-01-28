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
    if user1.offset > user2.offset:
        winner, loser = user1, user2

    elif user1.offset < user2.offset:
        winner, loser = user2, user1

    else:
        while user1.init == user2.init:
            user1.roll_init()
            user2.roll_init()

        winner, loser = reversed(sorted([user1, user2]))

    return (winner, loser)


def parse_turn_users(parts):
    """
    Parse users based on possible specification.
    Expected parts: [username/offset, username/offset/premade_roll, ...]

    Raises:
        InvalidCommandArgs - Improper parts input.

    Returns:
        Parsed TurnUsers in a list.
    """
    users = []
    try:
        while parts:
            roll = None
            subparts = parts[0].split('/')

            if len(subparts) == 3:
                name, offset, roll = subparts[0].strip(), int(subparts[1]), int(subparts[2])
            elif len(subparts) == 2:
                name, offset = subparts[0].strip(), int(subparts[1])
            else:
                raise dice.exc.InvalidCommandArgs("Improperly formatted turn, missing information.")

            users += [dice.turn.TurnUser(name, offset, roll)]
            parts = parts[1:]
    except ValueError:
        raise dice.exc.InvalidCommandArgs("Improperply formatted turn, possible value error.")

    return users


@total_ordering
class TurnEffect(object):
    """
    An effect that expires after a number of turns or combat.
    """
    def __init__(self, text, turns):
        self.text = text
        self.turns = turns

    def __str__(self):
        return '{}: {}'.format(self.text, self.turns)

    def __repr__(self):
        return "TurnEffect(text={!r}, turns={!r})".format(self.text, self.turns)

    def __eq__(self, other):
        return self.text == other.text

    def __lt__(self, other):
        return self.text < other.text

    def __hash__(self):
        return hash(self.text)

    @property
    def is_expired(self):
        return self.turns < 1

    def decrement(self):
        self.turns -= 1


@total_ordering
class TurnUser(object):
    """
    A user in a TurnOrder.
    Has a unique name and an initiative roll.
    """
    def __init__(self, name, offset, init=None, effects=None):
        self.name = name
        self.offset = offset
        self.init = init
        self.effects = []

        if not init:
            self.init = self.roll_init()
        if effects:
            self.effects = effects

    def __str__(self):
        effects = ''
        if self.effects:
            pad = '\n' + ' ' * 8
            effects = pad + pad.join(str(x) for x in self.effects)
        return '{} ({}): {:.2f}{}'.format(self.name, self.offset, self.init, effects)

    def __repr__(self):
        return 'TurnUser(name={!r}, offset={!r}, init={!r}, effects={!r})'.format(
            self.name, self.offset, self.init, self.effects)

    def __eq__(self, other):
        return (self.name, self.offset, self.init) == (other.name, other.offset, other.init)

    def __ne__(self, other):
        return (self.name, self.offset, self.init) != (other.name, other.offset, other.init)

    def __lt__(self, other):
        return self.init < other.init

    def roll_init(self):
        """
        A person rolls d20 + init offset.
        """
        self.init = rand.randint(1, 21) + self.offset

        return self.init

    def add_effect(self, text, turns):
        """
        Add an effect to user for turns.
        """
        if turns < 1:
            raise dice.exc.InvalidCommandArgs('Turn amount must be > 0.')
        if text in [x.text for x in self.effects]:
            raise dice.exc.InvalidCommandArgs('Please choose a unique text for effect.')

        self.effects += [TurnEffect(text, turns)]

    def update_effect(self, find_text, new_turns):
        """
        Update any matching name for new amount of turns.
        """
        for effect in self.effects:
            if effect.text == find_text:
                effect.turns = new_turns

    def remove_effect(self, find_text):
        """
        Remove an effect from the user.
        """
        self.effects = [x for x in self.effects if x.text != find_text]

    def decrement_effects(self):
        """
        Turn has finished, decrement effect counters.

        Returns: Any effects that expired in form [name, name2, name3, ...]
        """
        finished = []
        for effect in self.effects:
            effect.decrement()
            if effect.is_expired:
                finished += [effect]

        for effect in finished:
            self.effects.remove(effect)

        return [effect.text for effect in finished]


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
            name = user.name
            if self.cur_user and user == self.cur_user:
                name = '> {} <'.format(user.name)
            offset = '{}{}'.format('+' if user.offset >= 0 else '', user.offset)
            init = '{:0.2f}'.format(user.init)
            rows += [[name, offset, init]]

        msg += dice.tbl.wrap_markdown(dice.tbl.format_table(rows, header=True))

        return msg

    def __repr__(self):
        return 'TurnOrder(users={!r}, cur_user={!r})'.format(self.users, self.cur_user)

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
            [dupe_init, ...] - There exists a duplicate for every number present in the list.
        """
        inits = [x.init for x in self.users]
        if other:
            inits += [other.init]

        for init in set(inits):
            inits.remove(init)

        return inits

    def resolve_collision(self, user, dupe_init):
        """
        Find existing user with same init, roll both until we can differentiate.

        Returns:
            user - With new init if needed changing.
        """
        conflict = [x for x in self.users if x.init == dupe_init and x != user][0]

        winner, loser = break_init_tie(user, conflict)
        winner.init = dupe_init
        loser.init = dupe_init - COLLIDE_INCREMENT

        new_dupes = self.duplicate_inits()
        while new_dupes:
            self.resolve_collision(loser, new_dupes[0])
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
            self.resolve_collision(user, dupes[0])
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

        user_to_remove = None
        for user in self.users:
            if user.name == name:
                user_to_remove = user
                break

        if not user_to_remove:
            raise dice.exc.InvalidCommandArgs("User not found: " + name)

        self.users.remove(user_to_remove)

    def next(self):
        """
        Set the next user to take a turn.
        """
        if not self.users:
            raise dice.exc.InvalidCommandArgs("Add some users first!")

        if not self.cur_user or self.cur_user == self.users[-1]:
            self.cur_user = self.users[0]
        else:
            for ind, user in enumerate(self.users[1:]):
                if self.users[ind] == self.cur_user:
                    self.cur_user = user
                    break

        return self.cur_user

    def update_user(self, name_part, new_init):
        """
        Update a user's init if modified post roll.
        """
        possible = []
        for user in self.users:
            if name_part in user.name:
                possible += [user]

        if len(possible) != 1:
            raise dice.exc.InvalidCommandArgs("Unable to match exactly 1 user.")

        try:
            possible[0].init = int(new_init)
            self.users = list(reversed(sorted(self.users)))
        except ValueError:
            raise dice.exc.InvalidCommandArgs("Unable to update init, provide valid integer.")
