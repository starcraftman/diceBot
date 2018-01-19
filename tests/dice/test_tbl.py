"""
Test table formatting logic
"""
from __future__ import absolute_import, print_function

import dice.tbl


def test_wrap_markdown():
    assert dice.tbl.wrap_markdown('text') == '```text```'


def test_max_col_width():
    lines = [
        ['aa', 'aaa', 'aa', 'aa'],
        ['a', 'aa', 'aa', 'aaaa'],
    ]
    assert dice.tbl.max_col_width(lines) == [2, 3, 2, 4]


def test_format_header():
    header = ['Header1', 'Head 2', 'Header 3']
    expect = """Header1 | Head 2 | Header 3
------- | ------ | --------
"""
    assert dice.tbl.format_header(header, pads=dice.tbl.max_col_width([header])) == expect


def test_format_line_simple():
    data = ['a phrase', 3344, 5553, 'another phrase']
    expect = 'a phrase | 3344 | 5553 | another phrase'
    assert dice.tbl.format_line(data) == expect


def test_format_line_separator():
    data = ['a phrase', 3344, 5553, 'another phrase']
    expect = 'a phrase$$3344$$5553$$another phrase'
    assert dice.tbl.format_line(data, sep='$$') == expect


def test_format_line_pad_same():
    data = ['a phrase', 3344, 5553, 'another phrase']
    pads = [10, 10, 10, 10]
    expect = 'a phrase   | 3344       | 5553       | another phrase'
    assert dice.tbl.format_line(data, pads=pads) == expect


def test_format_line_pad_different():
    data = ['a phrase', 3344, 5553, 'another phrase']
    pads = [15, 7, 7, 20]
    expect = 'a phrase        | 3344    | 5553    | another phrase'
    assert dice.tbl.format_line(data, pads=pads) == expect


def test_format_line_pad_center():
    data = ['a phrase', 3344, 5553, 'another phrase']
    pads = [15, 7, 7, 20]
    expect = '   a phrase     |  3344   |  5553   |    another phrase'
    assert dice.tbl.format_line(data, pads=pads, center=True) == expect


def test_format_table():
    lines = [
        ['Name', 'Number 1', 'Num2', 'Notes'],
        ['John', 5831, 5, 'He is good.'],
        ['Fareed', 23752, 322, 'Likes smoking.'],
        ['Rosalie', 34, 7320, 'Bit lazy.'],
    ]
    expect = """Name    | Number 1 | Num2 | Notes
John    | 5831     | 5    | He is good.
Fareed  | 23752    | 322  | Likes smoking.
Rosalie | 34       | 7320 | Bit lazy."""
    assert dice.tbl.format_table(lines) == expect


def test_format_table_header():
    lines = [
        ['Name', 'Number 1', 'Num2', 'Notes'],
        ['John', 5831, 5, 'He is good.'],
        ['Fareed', 23752, 322, 'Likes smoking.'],
        ['Rosalie', 34, 7320, 'Bit lazy.'],
    ]
    expect = """ Name   | Number 1 | Num2 |     Notes
------- | -------- | ---- | --------------
John    | 5831     | 5    | He is good.
Fareed  | 23752    | 322  | Likes smoking.
Rosalie | 34       | 7320 | Bit lazy."""
    assert dice.tbl.format_table(lines, header=True) == expect


def test_format_table_separator():
    lines = [
        ['Name', 'Number 1', 'Num2', 'Notes'],
        ['John', 5831, 5, 'He is good.'],
        ['Fareed', 23752, 322, 'Likes smoking.'],
        ['Rosalie', 34, 7320, 'Bit lazy.'],
    ]
    expect = """Name   !Number 1!Num2!Notes
John   !5831    !5   !He is good.
Fareed !23752   !322 !Likes smoking.
Rosalie!34      !7320!Bit lazy."""
    assert dice.tbl.format_table(lines, sep='!') == expect


def test_format_table_ragged():
    lines = [
        ['Name', 'Number 1', 'Num2', 'Notes'],
        ['John', 5831, 5, 'He is good.'],
        ['Fareed', 23752]
    ]
    expect = """Name   | Number 1 | Num2 | Notes
John   | 5831     | 5    | He is good.
Fareed | 23752"""
    assert dice.tbl.format_table(lines) == expect
