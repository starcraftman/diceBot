"""
Test util the grab all module.
"""
from __future__ import absolute_import, print_function
import os

import mock
import pytest

import dice.util


def test_modformatter_record():
    record = mock.Mock()
    record.__dict__['pathname'] = dice.util.rel_to_abs('dice', 'util.py')
    with pytest.raises(TypeError):
        dice.util.ModFormatter().format(record)
    assert record.__dict__['relmod'] == 'dice/util'


def test_dict_to_columns():
    data = {
        'first': [1, 2, 3],
        'more': [100],
        'second': [10, 30, 50],
        'three': [22, 19, 26, 23],
    }
    expect = [
        ['first (3)', 'more (1)', 'second (3)', 'three (4)'],
        [1, 100, 10, 22],
        [2, '', 30, 19],
        [3, '', 50, 26],
        ['', '', '', 23]
    ]
    assert dice.util.dict_to_columns(data) == expect


def test_get_config():
    assert dice.util.get_config('paths', 'log_conf') == 'data/log.yml'


def test_rel_to_abs():
    expect = os.path.join(dice.util.ROOT_DIR, 'data', 'log.yml')
    assert dice.util.rel_to_abs('data', 'log.yml') == expect


def test_substr_ind():
    assert dice.util.substr_ind('ale', 'alex') == [0, 3]
    assert dice.util.substr_ind('ALEX', 'Alexander') == [0, 4]
    assert dice.util.substr_ind('nde', 'Alexander') == [5, 8]

    assert not dice.util.substr_ind('ALe', 'Alexander', ignore_case=False)
    assert not dice.util.substr_ind('not', 'alex')
    assert not dice.util.substr_ind('longneedle', 'alex')

    assert dice.util.substr_ind('16 cyg', '16 c y  gni') == [0, 9]


def test_substr_match():
    assert dice.util.substr_match('ale', 'alex')
    assert dice.util.substr_match('ALEX', 'Alexander')
    assert dice.util.substr_match('nde', 'Alexander')

    assert not dice.util.substr_match('ALe', 'Alexander', ignore_case=False)
    assert not dice.util.substr_match('not', 'alex')
    assert not dice.util.substr_match('longneedle', 'alex')

    assert dice.util.substr_ind('16 cyg', '16 c y  gni') == [0, 9]


def test_complete_block():
    test1 = ["```Test```"]
    assert dice.util.complete_blocks(test1) == test1

    test1 = ["```Test"]
    assert dice.util.complete_blocks(test1) == [test1[0] + "```"]

    test1 = ["```Test", "Test```"]
    assert dice.util.complete_blocks(test1) == [test1[0] + "```", "```" + test1[1]]

    test1 = ["```Test", "Test", "Test```"]
    assert dice.util.complete_blocks(test1) == ["```Test```", "```Test```", "```Test```"]


def test_msg_splitter():
    try:
        old_limit = dice.util.MSG_LIMIT
        dice.util.MSG_LIMIT = 50

        line = "A short message to"  # 19 char line, 20 with \n
        test1 = line + "\n" + line + "\n"
        assert dice.util.msg_splitter(test1) == [test1[:-1]]

        test2 = test1 + "stop here\n" + test1
        assert dice.util.msg_splitter(test2) == [test1 + "stop here", test1[:-1]]
    finally:
        dice.util.MSG_LIMIT = old_limit
