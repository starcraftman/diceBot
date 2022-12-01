# pylint: disable=redefined-outer-name,missing-function-docstring,unused-argument
"""
Test dicedb.query module.
"""
from __future__ import absolute_import, print_function
import pytest

import dice.exc
import dice.turn
import dicedb
import dicedb.query

NEW_DISCORDID = 99999


@pytest.mark.asyncio
async def test_get_duser(test_db, f_dusers):
    assert (await dicedb.query.get_duser(test_db, 1))['display_name'] == 'User1'
    assert not await dicedb.query.get_duser(test_db, NEW_DISCORDID)


@pytest.mark.asyncio
async def test_ensure_duser_exists(test_db, f_dusers):
    duser = f_dusers[0]

    returned = await dicedb.query.ensure_duser(test_db, duser['discord_id'], 'NewName')
    assert duser['discord_id'] == returned['discord_id']
    assert 'NewName' == returned['display_name']


@pytest.mark.asyncio
async def test_ensure_duser_not_exists(test_db, f_dusers):
    returned = await dicedb.query.ensure_duser(test_db, NEW_DISCORDID, 'NotThereEver')
    assert NEW_DISCORDID == returned['discord_id']
    assert 'NotThereEver' == returned['display_name']


@pytest.mark.asyncio
async def test_find_saved_roll(test_db, f_dusers, f_saved_rolls):
    roll = f_saved_rolls[0]

    assert await dicedb.query.find_saved_roll(test_db, roll['discord_id'], 'Staff')
    assert await dicedb.query.find_saved_roll(test_db, roll['discord_id'], 'bow')
    assert not await dicedb.query.find_saved_roll(test_db, roll['discord_id'], 'NOTTHERE')
    assert not await dicedb.query.find_saved_roll(test_db, NEW_DISCORDID, 'Longsword')


@pytest.mark.asyncio
async def test_find_all_saved_rolls(test_db, f_dusers, f_saved_rolls):
    results = [x['name'] for x in await dicedb.query.find_all_saved_rolls(test_db, 1)]

    assert 'Crossbow' in results
    assert 'Staff' in results


@pytest.mark.asyncio
async def test_remove_saved_roll(test_db, f_dusers, f_saved_rolls):
    roll = f_saved_rolls[0]

    assert await dicedb.query.find_saved_roll(test_db, roll['discord_id'], roll['name'])
    assert await dicedb.query.remove_saved_roll(test_db, roll['discord_id'], roll['name'])
    assert not await dicedb.query.find_saved_roll(test_db, roll['discord_id'], roll['name'])


@pytest.mark.asyncio
async def test_update_saved_roll(test_db, f_dusers, f_saved_rolls):
    await dicedb.query.update_saved_roll(test_db, 1, 'Crossbow', 'd20 + 12, d8')
    new_roll = await dicedb.query.find_saved_roll(test_db, 1, 'Crossbow')
    assert new_roll['name'] == 'Crossbow'
    assert new_roll['discord_id'] == 1
    assert new_roll['roll'] == 'd20 + 12, d8'


@pytest.mark.asyncio
async def test_update_saved_roll_not_exists(test_db, f_saved_rolls):
    await dicedb.query.update_saved_roll(test_db, 5, 'Crossbow', 'd20 + 12, d8')
    new_roll = await dicedb.query.find_saved_roll(test_db, 5, 'Crossbow')

    assert new_roll['name'] == 'Crossbow'
    assert new_roll['discord_id'] == 5
    assert new_roll['roll'] == 'd20 + 12, d8'


@pytest.mark.asyncio
async def test_add_pun(test_db, f_dusers, f_puns):
    await dicedb.query.add_pun(test_db, 1, 'A new pun')
    existing = await dicedb.query.get_all_puns(test_db, 1)
    assert 'A new pun' == existing['puns'][-1]['text']


@pytest.mark.asyncio
async def test_get_all_puns(test_db, f_dusers, f_puns):
    puns = await dicedb.query.get_all_puns(test_db, 1)
    assert {'hits': 2, 'text': 'Second pun'} in puns['puns']
    assert len(puns['puns']) == 3

    assert not (await dicedb.query.get_all_puns(test_db, NEW_DISCORDID))['puns']


@pytest.mark.asyncio
async def test_remove_pun(test_db, f_dusers, f_puns):
    assert len(await dicedb.query.get_all_puns(test_db, 1)) == 3
    await dicedb.query.remove_pun(test_db, 1, 'Third pun')
    left = await dicedb.query.get_all_puns(test_db, 1)
    assert len(left['puns']) == 2
    assert 'Second pun' == left['puns'][-1]['text']


@pytest.mark.asyncio
async def test_randomly_select_pun(test_db, f_dusers, f_puns):
    assert 'pun' in await dicedb.query.randomly_select_pun(test_db, 1)
    after = await dicedb.query.get_all_puns(test_db, 1)
    assert f_puns[0]['puns'] != after['puns']


@pytest.mark.asyncio
async def test_randomly_select_pun_raises(test_db, f_dusers):
    with pytest.raises(dice.exc.InvalidCommandArgs):
        await dicedb.query.randomly_select_pun(test_db, NEW_DISCORDID)


@pytest.mark.asyncio
async def test_check_for_pun_dupe(test_db, f_dusers, f_puns):
    assert await dicedb.query.check_for_pun_dupe(test_db, 1, 'First pun')
    assert not await dicedb.query.check_for_pun_dupe(test_db, 1, 'Not there.')


@pytest.mark.asyncio
async def test_get_roll_history(test_db, f_dusers, f_lastrolls):
    rolls = await dicedb.query.get_roll_history(test_db, 1)
    assert len(rolls['history']) == 3

    rolls = await dicedb.query.get_roll_history(test_db, NEW_DISCORDID)
    assert not rolls['history']


@pytest.mark.asyncio
async def test_add_roll_history(test_db, f_dusers, f_lastrolls):
    entries = [{'roll': 'd20 + 5, d10 + 2', 'result': '19, 11'},
               {'roll': 'd20 + 5, d10 + 2', 'result': '19, 11'}]
    await dicedb.query.add_roll_history(test_db, 1, entries=entries)
    found = await dicedb.query.get_roll_history(test_db, 1)

    assert entries[0] == found['history'][-1]
    assert entries[0] != found['history'][-2]


@pytest.mark.asyncio
async def test_add_last_roll_differs(test_db, f_dusers, f_lastrolls):
    entries = [{'roll': 'd20 + 5, d10 + 2', 'result': '19, 11'},
               {'roll': '3: 4d6kh3', 'result': '18, 15, 17'}]
    await dicedb.query.add_roll_history(test_db, 1, entries=entries)
    found = await dicedb.query.get_roll_history(test_db, 1)

    assert entries[1] == found['history'][-1]
    assert entries[0] == found['history'][-2]


@pytest.mark.asyncio
async def test_add_last_roll_prune(test_db, f_lastrolls):
    entries = [{'roll': 'd20 + 5, d10 + 2', 'result': '19, 11'},
               {'roll': '3: 4d6kh3', 'result': '18, 15, 17'}]
    await dicedb.query.add_roll_history(test_db, 1, entries=entries, limit=2)
    found = await dicedb.query.get_roll_history(test_db, 1)

    assert len(found['history']) == 2
    assert entries[1] == found['history'][-1]
    assert entries[0] == found['history'][-2]


@pytest.mark.asyncio
async def test_get_googly_exists(test_db, f_googly):
    found = await dicedb.query.get_googly(test_db, 1)
    assert 95 == found['total']


@pytest.mark.asyncio
async def test_get_googly_no_exists(test_db, f_googly):
    new_googly = await dicedb.query.get_googly(test_db, 5)
    assert new_googly['discord_id'] == 5
    assert new_googly['total'] == 100


@pytest.mark.asyncio
async def test_update_googly(test_db, f_googly):
    found = await dicedb.query.get_googly(test_db, 1)
    found['total'] -= 10
    found['used'] += 10

    await dicedb.query.update_googly(test_db, found)
    found = await dicedb.query.get_googly(test_db, 1)
    assert found['total'] == 85


@pytest.mark.asyncio
async def test_get_list(test_db, f_movies):
    db_movies = await dicedb.query.get_list(test_db, 1, 'Movies')
    assert len(db_movies['entries']) == 3


@pytest.mark.asyncio
async def test_add_list_entries_exists(test_db, f_movies):
    await dicedb.query.add_list_entries(test_db, 1, 'Movies', ['Bad Boys'])
    all_movies = await dicedb.query.get_list(test_db, 1, 'Movies')
    assert len(all_movies['entries']) == 4
    assert all_movies['entries'][-1] == 'Bad Boys'


@pytest.mark.asyncio
async def test_add_list_entries_not_exists(test_db, f_movies):
    await dicedb.query.add_list_entries(test_db, NEW_DISCORDID, 'Movies', ['Star Trek', 'Bad Boys'])
    all_movies = await dicedb.query.get_list(test_db, NEW_DISCORDID, 'Movies')
    assert len(all_movies['entries']) == 2
    assert all_movies['entries'][-1] == 'Bad Boys'
    assert all_movies['discord_id'] == NEW_DISCORDID


@pytest.mark.asyncio
async def test_remove_list_entries(test_db, f_movies):
    await dicedb.query.remove_list_entries(test_db, 1, 'Movies', ['Toy Story', 'Bad Boys'])
    all_movies = await dicedb.query.get_list(test_db, 1, 'Movies')

    assert len(all_movies['entries']) == 2
    assert 'Toy Story' not in all_movies['entries']


@pytest.mark.asyncio
async def test_replace_list_entries(test_db, f_movies):
    await dicedb.query.replace_list_entries(test_db, NEW_DISCORDID, 'movies', ['Toy Story', 'Bad Boys'])
    all_movies = await dicedb.query.get_list(test_db, NEW_DISCORDID, 'movies')
    assert len(all_movies['entries']) == 2
    assert all_movies['entries'][-1] == 'Bad Boys'


@pytest.mark.asyncio
async def test_get_turn_order(test_db, f_turnorders):
    combat = await dicedb.query.get_turn_order(test_db, discord_id=1, channel_id=1)
    assert combat['tracker'][0]['name'] == 'orc'


@pytest.mark.asyncio
async def test_update_turn_order(test_db, f_turnorders):
    combat = await dicedb.query.get_turn_order(test_db, discord_id=1, channel_id=1)
    combat['tracker'] = [{'name': 'alex', 'init': -3, 'roll': 15, 'effets': ''}]
    await dicedb.query.update_turn_order(test_db, discord_id=1, channel_id=1, combat_tracker=combat)

    combat = await dicedb.query.get_turn_order(test_db, discord_id=1, channel_id=1)
    assert combat['tracker'][0]['name'] == 'alex'


@pytest.mark.asyncio
async def test_remove_turn_order(test_db, f_turnorders):
    await dicedb.query.remove_turn_order(test_db, discord_id=1, channel_id=1)
    await dicedb.query.remove_turn_order(test_db, discord_id=1, channel_id=1)
    assert await dicedb.query.get_turn_order(test_db, discord_id=1, channel_id=1) is None


#  def test_add_song_with_tags_update_existing(session, f_songs):
    #  song = f_songs[0]

    #  dicedb.query.add_song_with_tags(session, song.name, 'testurl', tags=['tag1', 'tag2'])

    #  new_song = session.query(Song).filter(Song.name == song.name).one()
    #  assert new_song.url is None
    #  assert sorted([x.name for x in new_song.tags]) == ['tag1', 'tag2']


#  def test_add_song_with_tags_new_youtube(session, f_songs):
    #  dicedb.query.add_song_with_tags(session, 'newsong', 'https://youtu.be/12345', tags=['tag1', 'tag2'])

    #  new_song = session.query(Song).filter(Song.name == 'newsong').one()
    #  assert new_song.url == 'https://youtu.be/12345'
    #  assert sorted([x.name for x in new_song.tags]) == ['tag1', 'tag2']


#  def test_remove_song_with_tags(session, f_songs):
    #  name = f_songs[0].name
    #  sid = f_songs[0].id
    #  dicedb.query.remove_song_with_tags(session, name)

    #  with pytest.raises(sqla_oexc.NoResultFound):
        #  session.query(Song).filter(Song.name == name).one()
    #  with pytest.raises(sqla_oexc.NoResultFound):
        #  session.query(Song).filter(SongTag.song_key == sid).one()


#  def test_search_songs_by_name(session, f_songs):
    #  assert dicedb.query.search_songs_by_name(session, f_songs[0].name) == [f_songs[0]]
    #  assert dicedb.query.search_songs_by_name(session, f_songs[0].name[:-2]) == [f_songs[0]]


#  def test_get_song_by_id(session, f_songs):
    #  assert dicedb.query.get_song_by_id(session, f_songs[0].id) == f_songs[0]


#  def test_get_songs_with_tag(session, f_songs):
    #  assert dicedb.query.get_songs_with_tag(session, f_songs[0].tags[0].name) == [f_songs[0]]


#  def test_get_song_choices(session, f_songs):
    #  assert dicedb.query.get_song_choices(session) == sorted(f_songs)


#  def test_get_tag_choices(session, f_songs):
    #  expect = []
    #  for song in f_songs:
        #  for tag in song.tags:
            #  expect += [tag.name]
    #  expect = list(sorted(set(expect)))

    #  assert dicedb.query.get_tag_choices(session) == expect


#  def test_validate_videos_not_youtube():
    #  links = ['https://google.com']

    #  with pytest.raises(dice.exc.InvalidCommandArgs):
        #  dicedb.query.validate_videos(links)


#  def test_validate_videos_youtube_strip_angles():
    #  links = ['<https://youtube.com/watch?v=1234>']

    #  expect = [Song(id=None, name='youtube_1234', folder='/tmp/videos',
                   #  url='https://youtu.be/1234', repeat=False, volume_int=50)]

    #  assert dicedb.query.validate_videos(links) == expect


#  def test_validate_videos_local_not_found():
    #  links = ['notfound.mp3']

    #  with pytest.raises(dice.exc.InvalidCommandArgs):
        #  dicedb.query.validate_videos(links)


#  def test_validate_videos_local_found(f_songs):
    #  links = [f_songs[-1].name]
    #  dicedb.query.validate_videos(links)
