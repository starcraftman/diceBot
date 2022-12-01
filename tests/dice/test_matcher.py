# pylint: disable=redefined-outer-name,missing-function-docstring,unused-argument
"""
Test dice.matcher
"""
import dice.matcher


def test_substr_ind():
    assert dice.matcher.substr_ind('ale', 'alex') == [0, 3]
    assert dice.matcher.substr_ind('ALEX', 'Alexander') == [0, 4]
    assert dice.matcher.substr_ind('nde', 'Alexander') == [5, 8]

    assert not dice.matcher.substr_ind('ALe', 'Alexander', ignore_case=False)
    assert not dice.matcher.substr_ind('not', 'alex')
    assert not dice.matcher.substr_ind('longneedle', 'alex')

    assert dice.matcher.substr_ind('16 cyg', '16 c y  gni') == [0, 9]


def test_substr_match():
    assert dice.matcher.substr_match('ale', 'alex')
    assert dice.matcher.substr_match('ALEX', 'Alexander')
    assert dice.matcher.substr_match('nde', 'Alexander')

    assert not dice.matcher.substr_match('ALe', 'Alexander', ignore_case=False)
    assert not dice.matcher.substr_match('not', 'alex')
    assert not dice.matcher.substr_match('longneedle', 'alex')

    assert dice.matcher.substr_ind('16 cyg', '16 c y  gni') == [0, 9]


def test_emphasize_match():
    result = dice.matcher.emphasize_match('match', 'A line that should match somewhere')

    assert result == 'A line that should __match__ somewhere'
