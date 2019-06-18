"""
Tests for dice.music
"""
import re

import aiomock
import pytest

import dice.music

YTDL_REASON = "Uses yotube_dl and is slow. To enable set env ALL_TESTS=True"


def test_run_cmd_with_retries():
    actual = dice.music.run_cmd_with_retries(['echo', 'Hello'], retries=5)
    assert actual == "Hello\n"


@pytest.mark.asyncio
async def test_get_yt_info():
    url = 'https://www.youtube.com/watch?v=O9qUdpgcWVY&list=PLFItFVrQwOi45Y4YlWn1Myz-YQvSZ6MEL'
    expect = ('https://youtu.be/O9qUdpgcWVY', 'Obey the Groove')
    assert expect == (await dice.music.get_yt_info(url))[0]


def test_guild_player__init__(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert isinstance(player, dice.music.GuildPlayer)
    assert player.vids == list(f_songs)


def test_guild_player__getattr__(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert not player.is_connected()
    assert f_vclient.is_connected.called


def test_guild_player__str__(f_songs):
    expect = """__**Player Status**__ :

__Now Playing__:
    **crit**    __<https://youtu.be/IrbCrwtDIUA>__
__State__: Stopped
__Repeat All__: Disabled
__Shuffle__: Disabled
__Video List__:
    **crit**    __<https://youtu.be/IrbCrwtDIUA>__
        Volume: 50/100 Repeat: False
    **pop**    __<https://youtu.be/7jgnv0xCv-k>__
        Volume: 50/100 Repeat: False
    **late**
        Volume: 50/100 Repeat: False
"""
    player = dice.music.GuildPlayer(vids=f_songs)
    assert str(player) == expect


def test_guild_player__repr__(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    expect = "GuildPlayer(cur_vid=Song(id=1, name='crit', folder='/tmp/tmp', url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), vids=[Song(id=1, name='crit', folder='/tmp/tmp', url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), Song(id=2, name='pop', folder='/tmp/tmp', url='https://youtu.be/7jgnv0xCv-k', repeat=False, volume_int=50), Song(id=3, name='late', folder='/tmp/tmp', url=None, repeat=False, volume_int=50)], itr=BIterator(index=0, items=[Song(id=1, name='crit', folder='/tmp/tmp', url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), Song(id=2, name='pop', folder='/tmp/tmp', url='https://youtu.be/7jgnv0xCv-k', repeat=False, volume_int=50), Song(id=3, name='late', folder='/tmp/tmp', url=None, repeat=False, volume_int=50)]), repeat_all=False, shuffle=False, voice_channel=None, text_channel=None)"

    assert re.sub(r'/tmp/\w+', '/tmp/tmp', repr(player)) == expect


def test_guild_player_cur_vid(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert player.cur_vid == f_songs[0]
    player.next()
    assert player.cur_vid == f_songs[1]


def test_guild_player_state(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert player.state == 'stopped'

    f_vclient.is_playing.return_value = True
    f_vclient.is_connected.return_value = True
    assert player.state == 'playing'

    f_vclient.is_playing.return_value = False
    f_vclient.is_paused.return_value = True
    assert player.state == 'paused'


def test_guild_player_is_done(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert not player.is_done()

    player = dice.music.GuildPlayer(vids=[])
    assert player.is_done()


def test_guild_player_is_connected(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert not player.is_connected()

    f_vclient.is_connected.return_value = True
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert player.is_connected()


def test_guild_player_is_playing(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert not player.is_playing()

    f_vclient.is_connected.return_value = True
    f_vclient.is_playing.return_value = True
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert player.is_playing()


def test_guild_player_is_paused(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert not player.is_paused()

    f_vclient.is_connected.return_value = True
    f_vclient.is_paused.return_value = True
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert player.is_paused()


def test_guild_player_set_vids(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs[:1])

    player.set_vids(f_songs[1:])
    assert player.vids == list(f_songs[1:])


def test_guild_player_append_vids(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs[:1], client=f_vclient)

    player.append_vids(f_songs[1:])
    assert player.itr.items == list(f_songs)
    assert player.vids == list(f_songs)


def test_guild_player_set_volume(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    with pytest.raises(dice.exc.InvalidCommandArgs):
        player.set_volume(1000)
    with pytest.raises(dice.exc.InvalidCommandArgs):
        player.set_volume(-1000)

    assert player.cur_vid.volume_int == 50
    player.set_volume(100)
    assert player.cur_vid.volume_int == 100
    assert f_vclient.source.volume == 1.0


def test_guild_player_reset_iterator(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    player.next()
    player.next()
    assert player.cur_vid == f_songs[-1]

    player.reset_iterator()
    assert player.cur_vid == f_songs[0]


def test_guild_player_reset_iterator_last(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert player.cur_vid == f_songs[0]

    player.reset_iterator(to_last=True)
    assert player.cur_vid == f_songs[-1]


def test_guild_player_play_no_connect(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.vid_index = 0

    f_vclient.is_playing.return_value = True
    with pytest.raises(dice.exc.RemoteError):
        player.play()


# TODO: Change this text
def test_guild_player_play(f_songs, f_vclient):
    pass
    #  player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    #  player.vid_index = 0
    #  f_vclient.is_connected.return_value = True
    #  f_vclient.is_playing.return_value = True

    #  player.play()

    #  assert player.vid_index == 0
    #  assert not player.is_done()
    #  assert f_vclient.stop.called
    #  assert f_vclient.play.called


def test_guild_player_play_no_vids(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=[])
    with pytest.raises(dice.exc.InvalidCommandArgs):
        player.play()


def test_guild_player_after_play(f_songs, f_vclient):
    f_vclient.is_connected.return_value = True
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.play = aiomock.Mock()

    player.cur_vid.repeat = True
    player.after_play(None)
    assert player.play.called

    player.cur_vid.repeat = False
    player.play = aiomock.Mock()
    player.next = aiomock.Mock()
    player.after_play(None)
    assert player.next.called


def test_guild_player_next(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)

    assert player.cur_vid == f_songs[0]
    assert not player.is_done()
    assert not f_vclient.stop.called
    assert player.next() == f_songs[1]
    assert player.next() == f_songs[2]
    assert player.cur_vid == f_songs[2]
    assert not player.is_done()
    assert not f_vclient.stop.called

    with pytest.raises(StopIteration):
        player.next()
    assert player.cur_vid == f_songs[2]
    assert player.is_done()
    assert f_vclient.stop.called


def test_guild_player_prev(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.next()
    player.next()

    assert player.cur_vid == f_songs[2]
    assert not player.is_done()
    assert not f_vclient.stop.called
    assert player.prev() == f_songs[1]
    assert player.prev() == f_songs[0]
    assert player.cur_vid == f_songs[0]
    assert not player.is_done()
    assert not f_vclient.stop.called

    with pytest.raises(StopIteration):
        player.prev()
    assert player.cur_vid == f_songs[0]
    assert player.is_done()
    assert f_vclient.stop.called


def test_parse_search_label():
    assert dice.music.parse_search_label(None) == ("", 0)
    assert dice.music.parse_search_label("ago ") == ("", 0)
    assert dice.music.parse_search_label("ago 4 hours 4 views") == ("4:00:00", 4)
    assert dice.music.parse_search_label("ago 1 hour, 2 minutes 4 views") == ("1:02:00", 4)
    assert dice.music.parse_search_label("ago 21 minutes, 43 seconds 40 views") == ("0:21:43", 40)
    assert dice.music.parse_search_label("ago 3 hours, 21 minutes, 1 second 2 views") == ("3:21:01", 2)
    assert dice.music.parse_search_label("ago 3,222,111 views") == ("", 3222111)


@pytest.mark.asyncio
async def test_yt_search():
    expect_url = "https://youtu.be/IrbCrwtDIUA"
    results = await dice.music.yt_search(['critical', 'hit'])
    assert [x for x in results if x['url'] == expect_url]
    assert len(results) > 10
