"""
Implement a simple turn order manager.
"""
from __future__ import absolute_import, print_function
from functools import total_ordering

import numpy.random as rand

import dice.exc
import dice.tbl

COLLIDE_INCREMENT = 0.01


def break_init_tie(user1, user2, *, increment=COLLIDE_INCREMENT):
    """
    Resolve a tie of two player inits according to Pathfinder rules.
        Highest modifier if they differ goes first.
        If same modifier, keep rolling until different.

    Loser of tie will have their init reduced by increment.

    Args:
        user1: A TurnUser with the same init as user2.
        user2: A TurnUser with the same init as user1.

    Returns:
        (winner, loser) - Ordered tuple, winner won the tie.
    """
    if user1.modifier > user2.modifier:
        winner, loser = user1, user2

    elif user1.modifier < user2.modifier:
        winner, loser = user2, user1

    else:
        old_init = user1.init
        while user1.init == user2.init:
            user1.roll_init()
            user2.roll_init()

        winner, loser = reversed(sorted([user1, user2]))
        user1.init = user2.init = old_init

    loser.init -= increment
    return (winner, loser)


def find_user_by_name(users, name_part):
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


def users_same_init(users):
    """
    Return a list of users that have inits that are the same.

    Args:
        users: A list of TurnUsers.

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
    Parse users based on a textual specification.
    Expected format of parts:
        [name/modifier, name/modifier/premade_roll, ...]

    Raises:
        InvalidCommandArgs - Improper format found.

    Returns:
        A list of TurnUsers that matched the specification.
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
                raise dice.exc.InvalidCommandArgs("Improperly formatted, missing information.")

            users += [dice.turn.TurnUser(name, modifier, roll)]
            parts = parts[1:]
    except ValueError:
        raise dice.exc.InvalidCommandArgs("Improperly formatted, attempted to parse an integer and failed.")

    return users


def parse_order(order_str):
    """
    Given a repr string representing a TurnOrder, return the object.

    Args:
        order_str: A string that contains a pickled TurnOrder object.

    Return:
        If the string is actually a parsable TurnOrder, return the object. Otherwise return None
    """
    if order_str and order_str.startswith('TurnOrder('):
        return eval(order_str)

    return None


@total_ordering
class TurnEffect():
    """
    An effect that expires after a number of turns or combat.

    Attributes:
        text: A string that describes the effect.
        turns: An integer number of turns.
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

    def __add__(self, num):
        return TurnEffect(self.text, self.turns + num)

    def __sub__(self, num):
        return TurnEffect(self.text, self.turns - num)

    def __radd__(self, num):
        return self + num

    def __iadd__(self, num):
        self.turns += num
        return self

    def __isub__(self, num):
        self.turns -= num
        return self

    def is_expired(self):
        """
        An effect is expired if the remaining turns < 1.
        """
        return self.turns < 1


@total_ordering
class TurnUser():
    """
    A user in a TurnOrder.
    Has a unique name and an initiative roll.

    Attributes:
        name: The name of the character.
        modifier: The initiative modifier to be added to the roll.
        init: The rolled initiative, rolled automatically on creation.
        effects: A list of TurnEffects active on the character.
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
        Roll d20 + init modifier to determine character initiative.
        Sets the result before returning it.

        Returns:
            The character's rolled initiative, an integer.
        """
        self.init = rand.randint(1, 21) + self.modifier

        return self.init

    def add_effect(self, text, turns):
        """
        Add an effect to user for a number of turns.

        Args:
            text: An arbitrary name for the effect, should be unique.
            turns: An integer number of turns >= 1.

        Raises:
            InvalidCommandArgs: Malformed user input.
        """
        if turns < 1:
            raise dice.exc.InvalidCommandArgs('Turn amount must be > 0.')
        if text in [x.text for x in self.effects]:
            raise dice.exc.InvalidCommandArgs('Please choose a unique text for effect.')

        self.effects += [TurnEffect(text, turns)]

    def update_effect(self, find_text, new_turns):
        """
        Update any matching name for new amount of turns.

        Args:
            find_text: The text that matches TurnEffect.text
            new_turns: The new amount of turns for the effect.
        """
        for effect in self.effects:
            if effect.text == find_text:
                effect.turns = new_turns

    def remove_effect(self, find_text):
        """
        Remove an effect from the user.

        Args:
            find_text: The text that matches TurnEffect.text
        """
        self.effects = [x for x in self.effects if x.text != find_text]

    def decrement_effects(self):
        """
        Turn has finished, decrement all effect counters.

        Returns:
            A list of all TurnEffects that expired.
        """
        finished = []
        for effect in self.effects:
            effect -= 1
            if effect.is_expired():
                finished += [effect]

        for effect in finished:
            self.effects.remove(effect)

        return finished


class TurnOrder():
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
        """
        The current user who should take their turn.

        Returns:
            None if no users set, else the current TurnUser who is active.
        """
        if not self.users:
            return None

        return self.users[self.user_index]

    def add(self, user):
        """
        Add a user to the turn order, resolve any collisions with initiative.

        Args:
            user: TurnUser to add to the list of users.

        Raises:
            InvalidCommandArgs: The new user would have same name as an existing one.
        """
        if user.name in [x.name for x in self.users]:
            raise dice.exc.InvalidCommandArgs("Cannot have two users with same name.")

        self.users.append(user)

        conflicts = users_same_init(self.users)
        while conflicts:
            self.__resolve_collision(conflicts)
            conflicts = users_same_init(self.users)

        self.users = list(reversed(sorted(self.users)))

    def add_all(self, users):
        """
        Add all users to the turn order.

        Args:
            users: A list of TurnUsers to add to the users list.

        See TurnUser.add() for details.
        """
        for user in users:
            self.add(user)

    def remove(self, name_part):
        """
        Remove a user from the turn order.

        Args:
            name_part: A substring of a TurnUser.name to look for.

        Raises:
            InvalidCommandArgs: name_part was not found in the users or too many names matched.

        Returns:
            The removed user.
        """
        ind, user = find_user_by_name(self.users, name_part)

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
            name_part: A substring of a TurnUser.name to look for.
            new_init: The new initiative to give the selected TurnUser.

        Raises:
            InvalidCommandArgs: name_part was not found in the users or too many names matched.

        Returns:
            The user that was updated.
        """
        _, matched = find_user_by_name(self.users, name_part)

        try:
            matched.init = int(new_init)
            self.users = list(reversed(sorted(self.users)))
            return matched
        except ValueError:
            raise dice.exc.InvalidCommandArgs("Unable to update init, provide valid integer.")

    def next(self):
        """
        Advance to the next user in the order.

        Raises:
            InvalidCommandArgs: No users in the turn order.

        Returns:
            The TurnUser who should take their turn.
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
        break_init_tie(*conflicts)

        conflicts = users_same_init(self.users)
        while conflicts:
            self.__resolve_collision(conflicts)
            conflicts = users_same_init(self.users)
