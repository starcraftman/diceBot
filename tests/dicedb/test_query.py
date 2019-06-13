"""
Test dicedb.query module.
"""
from __future__ import absolute_import, print_function
import pytest

import sqlalchemy.orm.exc as sqla_oexc

import dice.exc
import dice.turn
import dicedb
import dicedb.query
from dicedb.schema import Song, SongTag

from tests.conftest import Member


def test_get_duser(session, f_dusers):
    assert dicedb.query.get_duser(session, '1') == f_dusers[0]
    with pytest.raises(dice.exc.NoMatch):
        dicedb.query.get_duser(session, '99999')


def test_add_duser(session, f_dusers):
    member = Member('NotThere', None, id='99999')
    dicedb.query.add_duser(session, member)

    duser = dicedb.query.get_duser(session, member.id)
    assert duser.display_name == member.display_name
    assert duser.id == member.id


def test_ensure_duser_exists(session, f_dusers):
    duser = f_dusers[0]
    member = Member(duser.id, 'NewName')
    returned = dicedb.query.ensure_duser(session, member)
    assert returned.display_name == member.display_name


def test_ensure_duser_not_exists(session, f_dusers):
    member = Member('NotThereEver', None, id='99999')
    returned = dicedb.query.ensure_duser(session, member)
    assert returned.display_name == member.display_name
    assert returned.id == member.id


def test_find_saved_roll(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    assert dicedb.query.find_saved_roll(session, roll.user_id, roll.name) == roll
    assert dicedb.query.find_saved_roll(session, roll.user_id, 'bow') == roll
    with pytest.raises(dice.exc.NoMatch):
        assert dicedb.query.find_saved_roll(session, roll.user_id, 'Longsword')


def test_find_all_saved_rolls(session, f_saved_rolls):
    rolls = sorted(f_saved_rolls[:2])

    assert sorted(dicedb.query.find_all_saved_rolls(session, rolls[0].user_id)) == rolls


def test_remove_saved_roll(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    assert dicedb.query.find_saved_roll(session, roll.user_id, roll.name)
    dicedb.query.remove_saved_roll(session, roll.user_id, roll.name)
    with pytest.raises(dice.exc.NoMatch):
        dicedb.query.find_saved_roll(session, roll.user_id, roll.name)


def test_update_saved_roll(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    dicedb.query.update_saved_roll(session, roll.user_id, roll.name, 'NewString')
    new_roll = dicedb.query.find_saved_roll(session, roll.user_id, roll.name)
    assert new_roll.name == roll.name
    assert new_roll.user_id == roll.user_id
    assert new_roll.roll_str == 'NewString'


def test_update_saved_roll_raises(session, f_saved_rolls):
    roll = f_saved_rolls[0]

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dicedb.query.update_saved_roll(session, roll.user_id, roll.name, "test" * 400)


def test_all_puns(session, f_puns):
    for ind, pun in enumerate(dicedb.query.all_puns(session)):
        assert pun == f_puns[ind]


def test_add_pun(session, f_puns):
    dicedb.query.add_pun(session, 'A new pun')
    assert dicedb.query.all_puns(session)[-1].text == 'A new pun'


def test_remove_pun(session, f_puns):
    dicedb.query.remove_pun(session, f_puns[-1])
    assert dicedb.query.all_puns(session)[-1] == f_puns[2]


def test_randomly_select_pun(session, f_puns):
    assert 'pun' in dicedb.query.randomly_select_pun(session)


def test_randomly_select_pun_raises(session):
    with pytest.raises(dice.exc.InvalidCommandArgs):
        dicedb.query.randomly_select_pun(session)


def test_check_for_pun_dupe(session, f_puns):
    assert dicedb.query.check_for_pun_dupe(session, f_puns[0].text)
    assert not dicedb.query.check_for_pun_dupe(session, 'Not there.')


def test_update_turn_order(session, f_turnorders):
    order = dice.turn.TurnOrder()
    dicedb.query.update_turn_order(session, 'a_key', order)
    fetched = dicedb.query.get_turn_order(session, 'a_key')
    assert fetched == repr(order)


def test_get_turn_order(session, f_turnorders):
    fetched = dicedb.query.get_turn_order(session, f_turnorders[0].id)
    assert fetched == 'TurnOrder'

    assert dicedb.query.get_turn_order(session, 'a_key') is None


def test_remove_turn_order(session, f_turnorders):
    key = f_turnorders[0].id

    dicedb.query.remove_turn_order(session, key)
    dicedb.query.remove_turn_order(session, key)
    assert dicedb.query.get_turn_order(session, 'key') is None


def test_generate_initial_turn_users(session, f_dusers, f_turnchars):
    assert dicedb.query.generate_inital_turn_users(session, 'turn') == ['Wizard/7', 'Fighter/2', 'Rogue/3']


def test_get_turn_char(session, f_turnchars):
    turn_char = f_turnchars[0]

    assert dicedb.query.get_turn_char(session, turn_char.user_key, 'turn') == turn_char


def test_update_turn_char(session, f_turnchars):
    turn_char = f_turnchars[0]

    dicedb.query.update_turn_char(session, turn_char.user_key, 'turn',
                                  name='NotWizard', modifier=-1)
    up_char = dicedb.query.get_turn_char(session, turn_char.user_key, 'turn')
    assert up_char.modifier == -1
    assert up_char.name == 'NotWizard'


def test_remove_turn_char(session, f_turnchars):
    turn_char = f_turnchars[0]

    dicedb.query.remove_turn_char(session, turn_char.user_key, 'turn')
    assert dicedb.query.get_turn_char(session, turn_char.user_key, 'turn') is None


def test_add_song_with_tags_update_existing(session, f_songs):
    song = f_songs[0]

    dicedb.query.add_song_with_tags(session, song.name, 'testurl', tags=['tag1', 'tag2'])

    new_song = session.query(Song).filter(Song.name == song.name).one()
    assert new_song.url is None
    assert sorted([x.name for x in new_song.tags]) == ['tag1', 'tag2']


def test_add_song_with_tags_new_youtube(session, f_songs):
    dicedb.query.add_song_with_tags(session, 'newsong', 'https://youtu.be/12345', tags=['tag1', 'tag2'])

    new_song = session.query(Song).filter(Song.name == 'newsong').one()
    assert new_song.url == 'https://youtu.be/12345'
    assert sorted([x.name for x in new_song.tags]) == ['tag1', 'tag2']


def test_remove_song_with_tags(session, f_songs):
    name = f_songs[0].name
    sid = f_songs[0].id
    dicedb.query.remove_song_with_tags(session, name)

    with pytest.raises(sqla_oexc.NoResultFound):
        session.query(Song).filter(Song.name == name).one()
    with pytest.raises(sqla_oexc.NoResultFound):
        session.query(Song).filter(SongTag.song_key == sid).one()


def test_search_songs_by_name(session, f_songs):
    assert dicedb.query.search_songs_by_name(session, f_songs[0].name) == [f_songs[0]]
    assert dicedb.query.search_songs_by_name(session, f_songs[0].name[:-2]) == [f_songs[0]]


def test_get_song_by_id(session, f_songs):
    assert dicedb.query.get_song_by_id(session, f_songs[0].id) == f_songs[0]


def test_get_songs_with_tag(session, f_songs):
    assert dicedb.query.get_songs_with_tag(session, f_songs[0].tags[0].name) == [f_songs[0]]


def test_get_song_choices(session, f_songs):
    assert dicedb.query.get_song_choices(session) == sorted(f_songs)


def test_get_tag_choices(session, f_songs):
    expect = []
    for song in f_songs:
        for tag in song.tags:
            expect += [tag.name]
    expect = list(sorted(set(expect)))

    assert dicedb.query.get_tag_choices(session) == expect


def test_validate_videos_not_youtube():
    links = ['https://google.com']

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dicedb.query.validate_videos(links)


def test_validate_videos_youtube_strip_angles():
    links = ['<https://youtube.com/watch?v=1234>']

    expect = [Song(id=None, name='youtube_1234', folder='/tmp/videos',
                   url='https://youtu.be/1234', repeat=False, volume_int=50)]

    assert dicedb.query.validate_videos(links) == expect


def test_validate_videos_local_not_found():
    links = ['notfound.mp3']

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dicedb.query.validate_videos(links)


def test_validate_videos_local_found(f_songs):
    links = [f_songs[-1].name]
    dicedb.query.validate_videos(links)


def test_get_googly_exists(session, f_googly):
    assert dicedb.query.get_googly(session, '1') == f_googly[0]


def test_get_googly_no_exists(session, f_googly):
    new_googly = dicedb.query.get_googly(session, '5')
    assert new_googly.id == '5'
    assert new_googly.total == 0


def test_get_last_rolls(session, f_lastrolls):
    assert dicedb.query.get_last_rolls(session, '1') == list(f_lastrolls[:3])
    assert dicedb.query.get_last_rolls(session, '9999') == []


def test_add_last_roll_same(session, f_lastrolls):
    last_roll = f_lastrolls[2]
    dicedb.query.add_last_roll(session, last_roll.id, last_roll.roll_str)
    assert len(dicedb.query.get_last_rolls(session, '1')) == 3


def test_add_last_roll_differs(session, f_lastrolls):
    last_roll = f_lastrolls[2]
    dicedb.query.add_last_roll(session, last_roll.id, last_roll.roll_str + " + 10")
    assert len(dicedb.query.get_last_rolls(session, '1')) != 3


def test_add_last_roll_prune(session, f_lastrolls):
    last_roll = f_lastrolls[2]
    dicedb.query.add_last_roll(session, last_roll.id, last_roll.roll_str + " + 10", 1)
    assert len(dicedb.query.get_last_rolls(session, '1')) == 2


def test_add_last_roll_exceeds_length(session, f_lastrolls):
    last_roll = f_lastrolls[2]
    assert len(dicedb.query.get_last_rolls(session, '1')) == 3
    dicedb.query.add_last_roll(session, last_roll.id, "test" * 100)
    assert len(dicedb.query.get_last_rolls(session, '1')) == 3
