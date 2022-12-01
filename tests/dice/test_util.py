# pylint: disable=redefined-outer-name,missing-function-docstring,unused-argument
"""
Test util the grab all module.
"""
from __future__ import absolute_import, print_function
import math
import os

import mock
import pytest
import selenium.webdriver

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
    with pytest.raises(KeyError):
        dice.util.get_config('zzzzz', 'not_there')


def test_get_config_default():
    assert dice.util.get_config('zzzzz', 'not_there', default=True) is True


def test_rel_to_abs():
    expect = os.path.join(dice.util.ROOT_DIR, 'data', 'log.yml')
    assert dice.util.rel_to_abs('data', 'log.yml') == expect


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
    text = """This is a long line to send to the line.
This is another line to send to the users.
This line talks about how it would be nice if there was peace.
This talks about how the podcasts are cool and fun.
Sitting in bed is fun."""
    expect = [
        "This is a long line to send to the line.\nThis is another line to send to the users.",
        "This line talks about how it would be nice if there was peace.",
        "This talks about how the podcasts are cool and fun.\nSitting in bed is fun.",
    ]
    assert dice.util.msg_splitter(text, 100) == expect


def test_msg_splitter_no_newline():
    text = "This is a long line to send to the line."
    expect = ['This is a ', 'long line ', 'to send to', ' the line.']
    assert dice.util.msg_splitter(text, 10) == expect


def test_generate_seed():
    seed = dice.util.generate_seed()
    assert seed > 0
    assert seed < math.pow(2, 32)


def test_seed_random_derived():
    derived = dice.util.seed_random()
    assert derived > 0
    assert derived < math.pow(2, 32)


def test_seed_random_fixed():
    assert dice.util.seed_random(5.0) == 5


def test_is_valid_yt():
    links = ['https://www.youtube.com/watch?v=j4dMnAPZu70', 'https://youtube.com/watch?v=j4dMnAPZu70',
             'https://youtu.be/j4dMnAPZu70', 'https://y2u.be/j4dMnAPZu70']
    for link in links:
        assert dice.util.is_valid_yt(link)


def test_is_valid_playlist():
    links = ['https://www.youtube.com/watch?v=oyvOJlX4ZkE&list=PLC4ahUUtnTVBNotg5DWbRwSZ2DX_A8aVs',
             'https://youtu.be/oyvOJlX4ZkE?list=PLC4ahUUtnTVBNotg5DWbRwSZ2DX_A8aVs']
    for link in links:
        assert dice.util.is_valid_playlist(link)


def test_is_valid_url():
    valid = ['http://www.google.ca', 'https://www.google.ca', 'https://google.ca', 'google.ca',
             'google.ca/subdomain']
    for link in valid:
        assert dice.util.is_valid_url(link)

    not_valid = ['word', 'word/sub', 'extras/music/no.mp3', '.com', '/tmp/music/found.mp3']
    for link in not_valid:
        assert not dice.util.is_valid_url(link)


def test_get_chrome_driver():
    with dice.util.get_chrome_driver() as browser:
        assert isinstance(browser, selenium.webdriver.Chrome)


def test_biterator__init__():
    itr = dice.util.BIterator([0, 1, 2, 3, 4])
    assert itr.items == [0, 1, 2, 3, 4]


# Also covers __next__
def test_biterator_next():
    itr = dice.util.BIterator([0, 1, 2])
    assert itr.next() == 0
    assert itr.next() == 1
    assert itr.next() == 2

    with pytest.raises(StopIteration):
        itr.next()
    with pytest.raises(StopIteration):
        itr.next()
    assert itr.index == len(itr.items)


def test_biterator_prev_():
    itr = dice.util.BIterator([0, 1, 2])
    itr.index = 3
    assert itr.prev() == 2
    assert itr.prev() == 1
    assert itr.prev() == 0

    with pytest.raises(StopIteration):
        itr.prev()
    with pytest.raises(StopIteration):
        itr.prev()
    assert itr.index == -1


def test_biterator_is_finished():
    itr = dice.util.BIterator([0, 1, 2])
    assert itr.is_finished()

    itr.next()
    assert not itr.is_finished()
    itr.next()
    assert not itr.is_finished()
    itr.next()
    assert not itr.is_finished()

    with pytest.raises(StopIteration):
        itr.next()
    assert itr.is_finished()


def test_biterator_finish():
    itr = dice.util.BIterator([0, 1, 2])
    assert itr.is_finished()

    itr.next()
    assert not itr.is_finished()
    itr.finish()
    assert itr.is_finished()
    assert itr.index == len(itr.items)


def test_biterator_current():
    itr = dice.util.BIterator([0, 1, 2])
    assert itr.current is None

    itr.next()
    assert itr.current == 0
    itr.next()
    itr.next()
    assert itr.current == 2

    with pytest.raises(StopIteration):
        itr.next()
    assert itr.current is None
