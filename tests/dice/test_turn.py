"""
Tests for the turn order functions.
"""
import pytest

import dice.exc
import dice.turn


BASIC_TRACKER = {
    'channel_id': 1,
    'discord_id': 1,
    'turns': [
        {
            'init': 5,
            'name': 'Rogue Guy',
            'roll': 21.0,
            'rolls': [21.0, 26.0, 10.0, 12.0, 21.0, 24.0, 24.0, 18.0, 8.0, 13.0]
        }, {
            'init': 3,
            'name': 'Fighter Dude',
            'roll': 20.0,
            'rolls': [20.0, 23.0, 6.0, 16.0, 21.0, 14.0, 13.0, 10.0, 10.0, 20.0]
        }, {
            'init': 7,
            'name': 'Wizard Boy',
            'roll': 10.0,
            'rolls': [10.0, 17.0, 14.0, 25.0, 25.0, 13.0, 20.0, 15.0, 19.0, 12.0]
        }
    ]
}


def test_merge_turns():
    left = [
        {
            'init': 5,
            'name': 'Rogue Guy',
            'roll': 21.0,
            'rolls': [21.0, 26.0, 10.0, 12.0],
        }, {
            'init': 3,
            'name': 'Fighter Dude',
            'roll': 20.0,
            'rolls': [20.0, 23.0, 6.0, 16.0],
        }, {
            'init': 7,
            'name': 'Wizard Boy',
            'roll': 10.0,
            'rolls': [10.0, 17.0, 14.0, 25.0],
        }
    ]
    right = [
        {
            'init': 7,
            'name': 'Wiz2',
            'roll': 10.0,
            'rolls': [10.0, 17.0, 14.0, 25.0],
        }
    ]
    result = dice.turn.merge_turn_lists(left, right)
    assert result[-1]['name'] == 'Wiz2'
    assert result[-1]['roll'] == 9.99


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


def test_combat_tracker_generate():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7', 'Fighter Dude/3', 'Rogue Guy/5/21'])

    assert tracker['discord_id'] == 1
    assert tracker['channel_id'] == 1
    wizard = [x for x in tracker['turns'] if x['name'] == 'Wizard Boy'][0]
    assert wizard['roll'] >= 7 and wizard['roll'] <= 27


def test_combat_tracker_add_chars_empty():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    tracker['turns'] = []
    dice.turn.combat_tracker_add_chars(tracker, ['Wiz2/7/10', 'Druid/-1/15'])
    assert tracker['turns'][0]['name'] == 'Druid'
    assert tracker['turns'][-1]['name'] == 'Wiz2'


def test_combat_tracker_add_chars_tie():
    tracker = dice.turn.combat_tracker_generate(1, 1, ['Wizard Boy/7/10', 'Fighter Dude/3/12', 'Rogue Guy/5/21'])
    dice.turn.combat_tracker_add_chars(tracker, ['Wiz2/7/10', 'Druid/-1/15'])
    assert tracker['turns'][-2]['roll'] == 10.0
    assert tracker['turns'][-1]['roll'] == 9.99


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
