"""
Test any shared logic
"""
from __future__ import absolute_import, print_function

import pytest

import dice.exc
import dice.parse
import dice.util


def test_throw_argument_parser():
    parser = dice.parse.ThrowArggumentParser()
    with pytest.raises(dice.exc.ArgumentHelpError):
        parser.print_help()
    with pytest.raises(dice.exc.ArgumentParseError):
        parser.error('blank')
    with pytest.raises(dice.exc.ArgumentParseError):
        parser.exit()


def test_make_parser_throws():
    parser = dice.parse.make_parser('!')
    with pytest.raises(dice.exc.ArgumentParseError):
        parser.parse_args(['!not_cmd'])
    with pytest.raises(dice.exc.ArgumentHelpError):
        parser.parse_args('!m --help'.split())
    with pytest.raises(dice.exc.ArgumentParseError):
        parser.parse_args('!m --invalidflag'.split())


def test_make_parser():
    """
    Simply verify it works, not all parser paths.
    """
    parser = dice.parse.make_parser('!')
    args = parser.parse_args('!m 1 + 1'.split())
    args.cmd == 'Math'
