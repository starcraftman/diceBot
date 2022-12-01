"""
Tests for the turn order functions.
"""
import pytest

import dice.exc
import dice.turn


def test_roll_init():
    rolls = dice.turn.roll_init(init=5, num_dice=2, sides_dice=30)
    assert len(rolls) == 1
    assert rolls[0] >= 7
    assert rolls[0] <= 65


def test_roll_init_many():
    rolls = dice.turn.roll_init(init=5, num_dice=2, sides_dice=30, times=9)
    assert len(rolls) == 9
    assert rolls[-1] >= 7
    assert rolls[-1] <= 65


def test_resolve_tie():
    turns = [
        {'init': 5, 'name': 'Rogue Guy', 'roll': 21.0, 'rolls': [21.0]},
        {'init': 7, 'name': 'Wizard Boy', 'roll': 21.0, 'rolls': [21.0]},
    ]
    result = dice.turn.resolve_tie(turns)
    assert result[0]['roll'] == 21.0
    assert result[0]['name'] == 'Wizard Boy'
    assert result[1]['roll'] == 20.99
    assert result[1]['name'] == 'Rogue Guy'


def test_resolve_tie_roll_off():
    turns = [
        {'init': 5, 'name': 'Rogue Guy', 'roll': 21.0, 'rolls': [21.0]},
        {'init': 5, 'name': 'Wizard Boy', 'roll': 21.0, 'rolls': [21.0]},
        {'init': 5, 'name': 'Fighter Dude', 'roll': 21.0, 'rolls': [21.0]},
    ]
    result = dice.turn.resolve_tie(turns)

    assert result[0]['roll'] == 21.0
    assert result[1]['roll'] == 20.99
    assert result[2]['roll'] == 20.98


def test_roll_off():
    init_and_roll = {26: [
        {'init': 5, 'name': 'Rogue Guy', 'roll': 21.0, 'rolls': [21.0, 26.0]},
        {'init': 5, 'name': 'Wizard Boy', 'roll': 21.0, 'rolls': [21.0, 26.0]},
        {'init': 5, 'name': 'Fighter Dude', 'roll': 21.0, 'rolls': [21.0, 26.0]},
    ]}
    result = dice.turn.roll_off(init_and_roll, 26)
    turns = sorted(result[26], key=lambda x: x['roll'], reverse=True)
    assert turns[0]['roll'] == 21.0
    assert turns[1]['roll'] == 20.99
    assert turns[2]['roll'] == 20.98


def test_order_based_on_rolls():
    turns = [
        {'init': 5, 'name': 'Rogue Guy', 'roll': 21.0, 'rolls': [15]},
        {'init': 5, 'name': 'Wizard Boy', 'roll': 21.0, 'rolls': [14, 12, 10]},
        {'init': 5, 'name': 'Fighter Dude', 'roll': 21.0, 'rolls': [14, 12, 15]},
    ]
    ordered = dice.turn.order_based_on_rolls(turns)
    assert ['Rogue Guy', 'Fighter Dude', 'Wizard Boy'] == [x['name'] for x in ordered]


def test_combat_tracker_generate():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7', 'Fighter Dude/3', 'Rogue Guy/5/21'])
    assert tracker['discord_id'] == 1
    assert tracker['channel_id'] == 1
    wizard = [x for x in tracker['turns'] if x['name'] == 'Wizard Boy'][0]
    assert wizard['roll'] >= 7 and wizard['roll'] <= 27


def test_combat_tracker_break_ties_init():
    tracker = {
        'channel_id': 1,
        'discord_id': 1,
        'turns': [
            {'effects': '', 'init': 5, 'name': 'Rogue Guy', 'roll': 21.0, 'rolls': [21.0]},
            {'effects': '', 'init': 7, 'name': 'Wizard Boy', 'roll': 21.0, 'rolls': [21.0]},
            {'effects': '', 'init': 3, 'name': 'Fighter Dude', 'roll': 5.0, 'rolls': [5.0]}
        ]
    }
    result = dice.turn.combat_tracker_break_ties(tracker)
    result['turns'] = sorted(result['turns'], key=lambda x: x['roll'], reverse=True)
    assert result['turns'][0]['roll'] == 21.0
    assert result['turns'][1]['roll'] == 20.99


def test_combat_tracker_add_chars_empty():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    tracker['turns'] = []
    dice.turn.combat_tracker_add_chars(tracker, ['Wiz2/7/10', 'Druid/-1/15'])
    assert tracker['turns'][0]['name'] == 'Druid'
    assert tracker['turns'][-1]['name'] == 'Wiz2'


def test_combat_tracker_add_chars_tie():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    dice.turn.combat_tracker_add_chars(tracker, ['Wiz2/7/10', 'Druid/-1/15'])
    assert tracker['turns'][1]['name'] == 'Druid'
    assert tracker['turns'][-1]['name'] == 'Wiz2'


def test_combat_tracker_remove_chars():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7', 'Fighter Dude/3', 'Rogue Guy/5/21'])
    dice.turn.combat_tracker_remove_chars(tracker, ['Fighter Dude', 'Rogue Guy'])
    assert len(tracker['turns']) == 1
    assert tracker['turns'][0]['name'] == 'Wizard Boy'


def test_combat_tracker_format():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    result = dice.turn.combat_tracker_format(tracker)
    assert "Rogue Guy    | 5    | 21.0" in result


def test_combat_tracker_move_fwd():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    dice.turn.combat_tracker_move(tracker, 2)
    assert tracker['turns'][0]['name'] == 'Wizard Boy'
    assert tracker['turns'][-1]['name'] == 'Fighter Dude'


def test_combat_tracker_move_back():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    dice.turn.combat_tracker_move(tracker, -1)

    assert tracker['turns'][0]['name'] == 'Wizard Boy'
    assert tracker['turns'][-1]['name'] == 'Fighter Dude'
