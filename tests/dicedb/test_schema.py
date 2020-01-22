"""
Test the schema for the database.
"""
from __future__ import absolute_import, print_function

import dicedb
import dicedb.schema
from dicedb.schema import (DUser, Pun, SavedRoll, TurnOrder, TurnChar, Song, Googly, LastRoll, Movie)


def test_duser__eq__(f_dusers):
    duser = f_dusers[0]
    assert duser != DUser(id='2', display_name='User1')
    assert duser == DUser(id=duser.id, display_name=duser.display_name)


def test_duser__repr__(f_dusers):
    duser = f_dusers[0]
    assert repr(duser) == "DUser(id='{}', display_name='{}')".format(
        duser.id, duser.display_name)
    assert duser == eval(repr(duser))


def test_duser__str__(f_dusers):
    duser = f_dusers[0]
    assert str(duser) == "DUser(id='{}', display_name='{}')".format(
        duser.id, duser.display_name)


def test_duser_mention(f_dusers):
    duser = f_dusers[0]
    assert duser.mention == '<@{}>'.format(duser.id)


def test_savedrolls__eq__(f_saved_rolls):
    roll = f_saved_rolls[0]
    assert roll != SavedRoll(user_id='2', name=roll.name, roll_str=roll.roll_str)
    assert roll == SavedRoll(user_id=roll.user_id, name=roll.name, roll_str=roll.roll_str)


def test_savedrolls__repr__(f_saved_rolls):
    roll = f_saved_rolls[0]
    assert repr(roll) == "SavedRoll(id={}, user_id='1', name='Crossbow', roll_str='d20 + 7, d8')".format(roll.id)
    assert roll == eval(repr(roll))


def test_savedrolls__str__(f_saved_rolls):
    roll = f_saved_rolls[0]
    assert str(roll) == "SavedRoll(id={}, user_id='1', name='Crossbow', roll_str='d20 + 7, d8')".format(roll.id)


def test_pun__repr__(f_puns):
    pun = f_puns[0]
    assert repr(pun) == "Pun(id={}, text='First pun', hits=2)".format(pun.id)


def test_pun__str__(f_puns):
    pun = f_puns[0]
    assert str(pun) == "Pun(id={}, text='First pun', hits=2)".format(pun.id)


def test_pun__eq__(f_puns):
    assert f_puns[0] == Pun(id=9, text='First pun', hits=0)
    assert f_puns[0] == Pun(id=3, text='First pun', hits=0)
    assert f_puns[0] != Pun(id=3, text='Second pun', hits=0)


def test_pun__hash__(f_puns):
    assert f_puns[0] in f_puns


def test_pun__lt__(f_puns):
    assert f_puns[0] < f_puns[1]


def test_turnchar__init__(f_turnchars):
    char = TurnChar(user_key='1', turn_key='turn', name='Wizard', modifier=7)
    assert isinstance(char, TurnChar)
    assert char.name == 'Wizard'


def test_turnchar__repr__(f_turnchars):
    char = f_turnchars[0]
    assert repr(char) == "TurnChar(user_key='1', turn_key='turn', name='Wizard', modifier=7)"


def test_turnchar__str__(f_turnchars):
    char = f_turnchars[0]
    assert str(char) == "Wizard/7"


def test_turnchar__eq__(f_turnchars):
    char = TurnChar(user_key='1', turn_key='turn', name='Wizard', modifier=7)
    assert char != TurnChar(user_key='2', turn_key='turn', name='Wizard', modifier=7)
    assert char == TurnChar(user_key='1', turn_key='turn', name='Guy', modifier=1)


def test_turnorder__init__(f_turnorders):
    turn = TurnOrder(id='guild1-chan1', text='TurnOrder')
    assert isinstance(turn, TurnOrder)
    assert turn.text == 'TurnOrder'


def test_turnorder__repr__(f_turnorders):
    turn = f_turnorders[0]
    assert repr(turn) == "TurnOrder(id='guild1-chan1', text='TurnOrder')"


def test_turnorder__str__(f_turnorders):
    turn = f_turnorders[0]
    assert repr(turn) == "TurnOrder(id='guild1-chan1', text='TurnOrder')"


def test_turnorder__eq__(f_turnorders):
    assert f_turnorders[0] == TurnOrder(id='guild1-chan1', text='TurnOrder')


def test_googly__init__(f_googly):
    assert f_googly[0].total == 100


def test_googly__str__(f_googly):
    expect = """__**Googly Counter**__

    Total: 100
    Used: 0"""
    assert str(f_googly[0]) == expect


def test_googly__repr__(f_googly):
    expect = "Googly(id='1', total=100, used=0)"
    assert repr(f_googly[0]) == expect


def test_googly__eq__(f_googly):
    orig = f_googly[0]
    assert orig == Googly(id=222, total=orig.total, used=orig.used)


def test_googly__add__(f_googly):
    assert f_googly[0] + 4 == Googly(id='1', total=104, used=0)
    assert f_googly[0] + -4 == Googly(id='1', total=96, used=4)
    assert f_googly[0] + -200 == Googly(id='1', total=0, used=100)


def test_googly__sub__(f_googly):
    assert f_googly[0] - 4 == Googly(id='1', total=96, used=4)
    assert f_googly[0] - -4 == Googly(id='1', total=104, used=0)
    assert f_googly[0] - 200 == Googly(id='1', total=0, used=100)


def test_googly__radd__(f_googly):
    assert 4 + f_googly[0] == Googly(id='1', total=104, used=0)
    assert -4 + f_googly[0] == Googly(id='1', total=96, used=4)
    assert -200 + f_googly[0] == Googly(id='1', total=0, used=100)


def test_googly__iadd__(f_googly):
    modified = f_googly[0]
    modified += 4
    assert modified == Googly(id='1', total=104, used=0)

    modified += -4
    assert modified == Googly(id='1', total=100, used=4)

    modified += -200
    assert modified == Googly(id='1', total=0, used=104)


def test_googly__isub__(f_googly):
    modified = f_googly[0]
    modified -= 4
    assert modified == Googly(id='1', total=96, used=4)

    modified -= -4
    assert modified == Googly(id='1', total=100, used=4)

    modified -= 200
    assert modified == Googly(id='1', total=0, used=104)


def test_lastroll__init__(f_lastrolls):
    roll = LastRoll(id=4, id_num=0, roll_str='4d6 + 10')
    assert roll.roll_str == '4d6 + 10'


def test_lastroll__repr__(f_lastrolls):
    assert repr(f_lastrolls[0]) == "LastRoll(id='1', id_num=0, roll_str='4d6 + 1')"


def test_lastroll__eq__(f_lastrolls):
    assert f_lastrolls[0] == LastRoll(id='1', id_num=0, roll_str='4d6 + 1')


def test_lastroll__lt__(f_lastrolls):
    assert repr(f_lastrolls[0]) < f_lastrolls[-1]
    assert repr(f_lastrolls[0]) < f_lastrolls[1]


def test_song__init__(f_songs):
    yt_id = '1234'
    yt_song = Song(id=9, name='youtube_{}'.format(yt_id), folder='/tmp/videos',
                   url='https://youtu.be/' + yt_id, repeat=False, volume_int=50)
    assert isinstance(yt_song, Song)


def test_song_format_menu(f_songs):
    expect = """     **1**)  __crit__
            URL:     __<https://youtu.be/IrbCrwtDIUA>__
            Tags: action, exciting

"""
    assert f_songs[0].format_menu(1) == expect


def test_movie__init__(f_movies):
    movie = Movie(id='1', id_num=0, name='Toy Story')
    assert movie.name == 'Toy Story'


def test_movie__repr__(f_movies):
    assert repr(f_movies[0]) == "Movie(id='1', id_num=0, name='Toy Story')"


def test_movie__eq__(f_movies):
    assert f_movies[0] == Movie(id='1', id_num=0, name='Toy Story')


def test_movie__lt__(f_movies):
    assert repr(f_movies[0]) < f_movies[-1]
    assert repr(f_movies[0]) < f_movies[1]


def test_parse_int():
    assert dicedb.schema.parse_int('') == 0
    assert dicedb.schema.parse_int('2') == 2
    assert dicedb.schema.parse_int(5) == 5


def test_parse_float():
    assert dicedb.schema.parse_float('') == 0.0
    assert dicedb.schema.parse_float('2') == 2.0
    assert dicedb.schema.parse_float(0.5) == 0.5
