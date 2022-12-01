"""
Implement a simple turn order manager.
"""
from __future__ import absolute_import, print_function

import numpy.random as rand

import dice.tbl

COLLIDE_INCREMENT = 0.01
ROLL_LIMIT = 8


def compare_turns(left, right):
    """
    Comparison function to compare two roll objects. Assumed to have the same number of rolls.
    """
    return left['rolls'] <= right['rolls']


def merge_turn_lists(left, right):
    """
    Merge two list of turn objects (i.e. turns from combat tracker).
    Left list will be used as a base and right merged in. Hence left has slightly higher priority.

    :param left [TODO:type]: [TODO:description]
    :param right [TODO:type]: [TODO:description]
    """
    merged = []
    base = sorted(left, key=compare_turns, reverse=True)
    to_add = sorted(right, key=compare_turns, reverse=True)

    while to_add or base:
        if to_add and base and to_add[0]['rolls'] > base[0]['rolls']:
            merged += [to_add[0]]
            to_add = to_add[1:]

        elif to_add and base and to_add[0]['rolls'] < base[0]['rolls']:
            merged += [base[0]]
            base = base[1:]

        # When new characters roll equal, depriorize adding characters
        elif to_add and base and to_add[0]['rolls'] == base[0]['rolls']:
            merged += [base[0]]
            base = base[1:]
            to_add[0]['roll'] -= COLLIDE_INCREMENT

        elif to_add and not base:
            merged += [to_add[0]]
            to_add = to_add[1:]

        elif base and not to_add:
            merged += [base[0]]
            base = base[1:]

    return merged


def roll_init(*, init, num_dice=1, sides_dice=20, times=1):
    """
    Roll initiative for a particular user. Default 1d20 + init

    :param init int: The initiative modifier for a character.
    :param dice int: The amount of dice to roll for initiative. A spec of form: mdn where m number of dice, n sides. Default d20
    :param times int: The number of init rolls to make.
    :returns: A list of rolled initiatives as floats.
    :rtype: [float]
    """
    if num_dice < 1 or sides_dice < 2 or times < 1:
        raise ValueError(f"Please select a valid num_dice and sides_dice. Rejecting: {times} x {num_dice}d{sides_dice}")

    values = []
    while times:
        value = init
        for _ in range(0, num_dice):
            value += rand.randint(1, sides_dice)

        values += [float(value)]
        times -= 1

    return values


def order_based_on_rolls(turns):
    """
    Order a list of turn objects by the rolls made.
    It will pad up the rolls made to match the most made rolls.
    Last roll will be repeated until pad finished.

    :param turns [turn, turn, ...]: A list of turn objects with 'rolls' field, a list of integers.
    :returns: The turns list passed in sorted in order of initiative.
    :rtype: [turn, turn, ...]
    """
    pad = max(len(x['rolls']) for x in turns)
    for turn in turns:
        roll_diff = pad - len(turn['rolls'])
        if roll_diff:
            turn['rolls'] += roll_init(init=turn['init'], times=roll_diff)

    return sorted(turns, key=compare_turns, reverse=True)


def combat_tracker_generate(discord_id, channel_id, chars):
    """
    Generate an initial turn order for combat trackers

    The list of chars comes in following form:
        - Rogue Guy/7 -> Character named Rogue Guy, has init of 7.
        - Rogue Guy/7/21 -> Character named Rogue Guy, has init of 7 and rolled 21 elsewhere.

    :param client motor.motor_asyncio.AsyncIOMotorClient: The client onto the db
    :param discord_id int: The discord id of controlling user
    :param channel_id int: The channel id of where command was invoked
    :param chars [str]: A list of strings defining the initial users
    :returns: The combat tracker of the chracters with fully rolled results.
    :rtype: A dictionary object.
    """
    tracker = {'discord_id': discord_id, 'channel_id': channel_id, 'turns': []}
    combat_tracker_add_chars(tracker, chars)
    tracker['turns'] = sorted(tracker['turns'], key=lambda x: x['roll'], reverse=True)

    return tracker


def combat_tracker_break_ties(tracker):
    """
    Look through the generated tracker and resolve any intiative ties.

    :param tracker Object: The tracker object.
    :returns: The combat tracker of the chracters with fully rolled results.
    :rtype: A dictionary object.
    """
    conflicts = {}
    for turn in tracker['turns']:
        try:
            conflicts[turn['roll']] += [turn]
        except KeyError:
            conflicts[turn['roll']] = [turn]

    for _, turns in conflicts.items():
        if len(turns) >= 2:
            turns = resolve_tie(turns)

    return tracker


def combat_tracker_add_chars(tracker, chars):
    """
    Given a tracker, add characters to it.
    After adding characters will always resolve ties on added characters.

    The list of chars comes in following form:
        - Rogue Guy/7 -> Character named Rogue Guy, has init of 7.
        - Rogue Guy/7/21 -> Character named Rogue Guy, has init of 7 and rolled 21 elsewhere.

    :param tracker dict: A combat tracker object.
    :param chars [str]: List of characters to add in required specification format.
    """
    to_add = []
    for chara in chars:
        parts = chara.split('/')
        name, init = parts[0], int(parts[1])
        if len(parts) > 2:
            roll = float(parts[2])
            rolls = [roll, init + roll] + roll_init(init=init, times=ROLL_LIMIT)
        else:
            rolls = roll_init(init=init, times=ROLL_LIMIT + 1)
            rolls = rolls[0:1] + [rolls[0] + init] + rolls[1:]
            roll = rolls[0]
        to_add += [{
            'name': name,
            'init': init,
            'roll': roll,
            'rolls': rolls,
        }]

    tracker['turns'] = merge_turn_lists(tracker['turns'], to_add)

    return tracker


def combat_tracker_remove_chars(tracker, chars):
    """
    Given a tracker, remove characters from it.

    :param tracker dict: A combat tracker object.
    :param chars [str]: List of names to remove.
    """
    to_remove = [x.lower() for x in chars]
    tracker['turns'] = [x for x in tracker['turns'] if x['name'].lower() not in to_remove]

    return tracker


def combat_tracker_format(tracker):
    """
    Format the combat tracker for presentation on discord.

    :param tracker dict: The combat tracker.
    """
    lines = [['Name', 'Init', 'Roll']]
    lines += [[x['name'], x['init'], x['roll']] for x in tracker['turns']]
    return dice.tbl.wrap_markdown(dice.tbl.format_table(lines, header=True))


def combat_tracker_move(tracker, steps):
    """
    Move the combat tracker forward or backward by steps.
    A negative integer will move it backward that many steps.

    :param tracker dict: The combat tracker.
    :param steps int: The number of steps to move forward or back.
    """
    if steps > 0:
        while steps:
            tracker['turns'] = tracker['turns'][1:] + [tracker['turns'][0]]
            steps -= 1
    if steps < 0:
        steps = abs(steps)
        while steps:
            tracker['turns'] = [tracker['turns'][-1]] + tracker['turns'][0:-1]
            steps -= 1

    return tracker
