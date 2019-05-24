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
    - Highest modifier if they differ goes first.
    - If same modifier, keep rolling until different.

    Returns:
        (winner, loser) - Ordered tuple, winner takes old init. Loser moves back.
    """
    if user1.modifier > user2.modifier:
        winner, loser = user1, user2

    elif user1.modifier < user2.modifier:
        winner, loser = user2, user1

    else:
        while user1.init == user2.init:
            user1.roll_init()
            user2.roll_init()

        winner, loser = reversed(sorted([user1, user2]))

    return (winner, loser)


def loose_match_users(users, name_part):
    """
    Loosely match against all users names name_part.
    Return the one user that matches exactly.

    Raises:
        InvalidCommandArgs: No user matched, or too many matched due to looseness.

    Returns:
        [ind, user]

        ind: The position in the users list.
        user: The TurnUser that matched.
    """
    possible = []
    for ind, user in enumerate(users):
        if name_part in user.name:
            possible += [(ind, user)]

    if len(possible) != 1:
        if not possible:
            msg = "No user matches: " + name_part
        else:
            msg = "Unable to match exactly 1 user. Be more specific."

        raise dice.exc.InvalidCommandArgs(msg)

    return possible[0]


def duplicate_users(users):
    """
    Return a list of users that have inits that are the same.

    Returns:
        Returns a list of different TurnUsers with the same init.
    """
    inits = [x.init for x in users]
    for init in set(inits):
        inits.remove(init)
    inits = list(set(inits))

    return [x for x in users if x.init in inits]


def parse_turn_users(parts):
    """
    Parse users based on possible specification.
    Expected parts: [username/modifier, username/modifier/premade_roll, ...]

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
                name, modifier, roll = subparts[0].strip(), int(subparts[1]), int(subparts[2])
            elif len(subparts) == 2:
                name, modifier = subparts[0].strip(), int(subparts[1])
            else:
                raise dice.exc.InvalidCommandArgs("Improperly formatted turn, missing information.")

            users += [dice.turn.TurnUser(name, modifier, roll)]
            parts = parts[1:]
    except ValueError:
        raise dice.exc.InvalidCommandArgs("Improperply formatted turn, possible value error.")

    return users


def parse_order(order_str):
    """
    Given a repr string representing a TurnOrder, return the object.

    Return:
        If the string is actually a parsable TurnOrder, return the object. Otherwise return None
    """
    if order_str and order_str.startswith('TurnOrder('):
        return eval(order_str)

    return None


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
    def __init__(self, name, modifier, init=None, effects=None):
        self.name = name
        self.modifier = modifier
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
        return '{} ({}): {:.2f}{}'.format(self.name, self.modifier, self.init, effects)

    def __repr__(self):
        return 'TurnUser(name={!r}, modifier={!r}, init={!r}, effects={!r})'.format(
            self.name, self.modifier, self.init, self.effects)

    def __eq__(self, other):
        return (self.name, self.modifier, self.init) == (other.name, other.modifier, other.init)

    def __ne__(self, other):
        return (self.name, self.modifier, self.init) != (other.name, other.modifier, other.init)

    def __lt__(self, other):
        return self.init < other.init

    def roll_init(self):
        """
        A person rolls d20 + init modifier.
        """
        self.init = rand.randint(1, 21) + self.modifier

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

    Attributes:
        user: The list of TurnUsers that are egaged in the encounter.
        user_index: The index that points to the current user.
    """
    def __init__(self, users=None, user_index=0):
        """
        Unless recreating an object, always use add() or add_all().
        """
        if not users:
            users = []
        self.users = users
        self.user_index = user_index

    def __str__(self):
        msg = '__**Turn Order**__\n\n'

        rows = [['name', 'mod.', 'init']]
        for user in self.users:
            name = user.name
            if self.cur_user and user == self.cur_user:
                name = '> {} <'.format(user.name)
            modifier = '{}{}'.format('+' if user.modifier >= 0 else '', user.modifier)
            init = '{:0.2f}'.format(user.init)
            rows += [[name, modifier, init]]

        msg += dice.tbl.wrap_markdown(dice.tbl.format_table(rows, header=True))

        return msg

    def __repr__(self):
        return 'TurnOrder(users={!r}, user_index={!r})'.format(self.users, self.user_index)

    @property
    def cur_user(self):
        """ The current user who should take their turn. """
        if not self.users:
            return None

        return self.users[self.user_index]

    def add(self, user):
        """
        Add a user to the turn order, resolve if collision.

        Args:
            user: TurnUser to add to the list of users.

        Raises:
            InvalidCommandArgs: The new user would have same name as an existing one.
        """
        if user.name in [x.name for x in self.users]:
            raise dice.exc.InvalidCommandArgs("Cannot have two users with same name.")

        self.users.append(user)

        conflicts = duplicate_users(self.users)
        while conflicts:
            self.__resolve_collision(conflicts)
            conflicts = duplicate_users(self.users)

        self.users = list(reversed(sorted(self.users)))

    def add_all(self, users):
        """
        Convenience bulk addition of users.

        Args:
            users: A list of TurnUsers to add to the users list.

        See TurnUser.add()
        """
        for user in users:
            self.add(user)

    def remove(self, name_part):
        """
        Remove a user from the turn order and adjust index.

        Args:
            name_part: A substring of a user name to look for.

        Raises:
            InvalidCommandArgs: name_part was not found in the users or too many names matched.

        Returns:
            The removed user.
        """
        ind, user = loose_match_users(self.users, name_part)

        if user == self.users[-1]:
            self.user_index = 0
        elif ind < self.user_index:
            self.user_index -= 1
        self.users.remove(user)

        return user

    def update_user(self, name_part, new_init):
        """
        Update a user's final init, will retain the same modifier.

        Args:
            name_part: A substring of a user name to look for.
            new_init: The new init to give the selected user.

        Raises:
            InvalidCommandArgs: name_part was not found in the users or too many names matched.

        Returns:
            The user that was updated.
        """
        _, matched = loose_match_users(self.users, name_part)

        try:
            matched.init = int(new_init)
            self.users = list(reversed(sorted(self.users)))
            return matched
        except ValueError:
            raise dice.exc.InvalidCommandArgs("Unable to update init, provide valid integer.")

    def next(self):
        """
        Set the next user to take a turn.

        Raises:
            InvalidCommandArgs: No users in the turn order.

        Returns:
            The user who should take their turn.
        """
        if not self.users:
            raise dice.exc.InvalidCommandArgs("Add some users first!")

        self.user_index = (self.user_index + 1) % len(self.users)

        return self.cur_user

    def __resolve_collision(self, conflicts):
        """
        Resolve a collision of inits amongst conflicts.

        Args:
            conflicts: A list of TurnUsers with the same inits.
        """
        _, loser = break_init_tie(*conflicts)
        loser.init -= COLLIDE_INCREMENT

        conflicts = duplicate_users(self.users)
        while conflicts:
            self.__resolve_collision(conflicts)
            conflicts = duplicate_users(self.users)
