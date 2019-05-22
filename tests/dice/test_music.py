"""
Tests for dice.music
"""
import os
import re
import tempfile
import time

import aiomock
import discord
import mock
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


@pytest.mark.skipif(not os.environ.get('ALL_TESTS'), reason=YTDL_REASON)
def test_get_yt_video(f_songs):
    try:
        tdir = tempfile.TemporaryDirectory()
        dice.music.get_yt_video(f_songs[0].url, 'song', tdir.name)
        assert os.path.isfile(os.path.join(tdir.name, 'song.opus'))
    finally:
        tdir.cleanup()


def test_prune_cache():
    try:
        now = time.time()
        tdir = tempfile.TemporaryDirectory()
        for num in range(5):
            tfile = os.path.join(tdir.name, '{}.file'.format(num))
            with open(tfile, 'w') as fout:
                fout.write(1024 ** 2 * str(num))
                os.utime(tfile, (now, now))
                now += 1
        dice.music.prune_cache(tdir.name, limit=2 * 1024 ** 2)
        assert os.listdir(tdir.name) == ['3.file', '4.file']
    finally:
        tdir.cleanup()


def test_prune_cache_prefix():
    try:
        now = time.time()
        tdir = tempfile.TemporaryDirectory()
        for num in range(5):
            tfile = os.path.join(tdir.name, 'yt{}.file'.format(num))
            with open(tfile, 'w') as fout:
                fout.write(1024 ** 2 * str(num))
                os.utime(tfile, (now, now))
                now += 1
            with open(tfile.replace('yt', ''), 'w') as fout:
                fout.write(1024 ** 2 * str(num))
                os.utime(tfile, (now, now))
                now += 1

        dice.music.prune_cache(tdir.name, prefix='yt', limit=2 * 1024 ** 2)
        fnames = os.listdir(tdir.name)
        assert 'yt2.file' not in fnames
        assert '2.file' in fnames
        assert len(fnames) == 7
    finally:
        tdir.cleanup()


def test_make_stream(f_songs):
    try:
        with open(f_songs[0].fname, 'w') as fout:
            fout.write('a')
        stream = dice.music.make_stream(f_songs[0])
        assert isinstance(stream, discord.PCMVolumeTransformer)
        assert len(os.listdir(f_songs[0].folder)) == 1
    finally:
        try:
            os.remove(f_songs[0].fname)
        except OSError:
            pass


def test_make_stream_not_exists(f_songs):
    with pytest.raises(dice.exc.InternalException):
        dice.music.make_stream(f_songs[0])


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
    expect = "GuildPlayer(cur_vid=Song(id=1, name='crit', folder='/tmp/tmp', url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), vids=[Song(id=1, name='crit', folder='/tmp/tmp', url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), Song(id=2, name='pop', folder='/tmp/tmp', url='https://youtu.be/7jgnv0xCv-k', repeat=False, volume_int=50), Song(id=3, name='late', folder='/tmp/tmp', url=None, repeat=False, volume_int=50)], itr=BIterator(index=0, items=[Song(id=1, name='crit', folder='/tmp/tmp', url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), Song(id=2, name='pop', folder='/tmp/tmp', url='https://youtu.be/7jgnv0xCv-k', repeat=False, volume_int=50), Song(id=3, name='late', folder='/tmp/tmp', url=None, repeat=False, volume_int=50)]), repeat_all=False, shuffle=False, target_channel=None)"

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


def test_guild_player_set_vids(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs[:1])

    player.set_vids(f_songs[1:])
    assert player.vids == list(f_songs[1:])


def test_guild_player_append_vids(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs[:1])

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


def test_guild_player_toggle_pause(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)

    assert not f_vclient.pause.called
    assert not f_vclient.resume.called

    f_vclient.is_connected.return_value = True
    f_vclient.is_playing.return_value = True
    player.toggle_pause()
    assert f_vclient.pause.called

    f_vclient.is_playing.return_value = False
    f_vclient.is_paused.return_value = True
    player.toggle_pause()
    assert f_vclient.resume.called


@mock.patch('dice.music.get_yt_video', lambda x, y, z: x)
def test_guild_player_play_no_connect(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.vid_index = 0

    f_vclient.is_playing.return_value = True
    with pytest.raises(dice.exc.RemoteError):
        player.play()


@mock.patch('dice.music.get_yt_video', lambda x, y, z: x)
@mock.patch('dice.music.make_stream', lambda x: x)
def test_guild_player_play(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.vid_index = 0
    f_vclient.is_connected.return_value = True
    f_vclient.is_playing.return_value = True

    player.play()

    assert player.vid_index == 0
    assert not player.is_done()
    assert f_vclient.stop.called
    assert f_vclient.play.called


def test_guild_player_play_no_vids(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=[])
    with pytest.raises(dice.exc.InvalidCommandArgs):
        player.play()


def test_guild_player_after_call(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.play = aiomock.Mock()

    player.cur_vid.repeat = True
    player.after_call(None)
    assert player.play.called

    player.cur_vid.repeat = False
    player.play = aiomock.Mock()
    player.next = aiomock.Mock()
    player.after_call(None)
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

    assert player.next() is None
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

    assert player.prev() is None
    assert player.cur_vid == f_songs[0]
    assert player.is_done()
    assert f_vclient.stop.called


@pytest.mark.asyncio
async def test_guild_player_replace_and_play(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=[], client=f_vclient)
    player.play = aiomock.Mock()
    f_vclient.is_connected.return_value = True

    await player.replace_and_play(list(f_songs))
    assert player.vids == list(f_songs)
    assert player.itr.index == 0
    assert not player.is_done()
    assert not f_vclient.stop.called
    assert os.path.exists(f_songs[0].fname)
