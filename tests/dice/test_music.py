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
    assert player.vids == f_songs


def test_guild_player__getattr__(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert not player.is_connected()
    assert f_vclient.is_connected.called


def test_guild_player__str__(f_songs):
    expect = """__**Player Status**__ :

__Now Playing__:
    **crit**    __<https://youtu.be/IrbCrwtDIUA>__
__Status__: Stopped
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
    expect = "GuildPlayer(vid_index=0, vids=(Song(id=1, name='crit', folder='/tmp/tmp', \
url='https://youtu.be/IrbCrwtDIUA', repeat=False, volume_int=50), Song(id=2, name='pop', \
folder='/tmp/tmp', url='https://youtu.be/7jgnv0xCv-k', repeat=False, volume_int=50), \
Song(id=3, name='late', folder='/home/starcraftman/prog/extras/music', url=None, repeat=False, \
volume_int=50)), repeat_all=False, shuffle=None, finished=False, now_playing=None, target_channel=None)"

    assert re.sub(r'/tmp/\w+', '/tmp/tmp', repr(player)) == expect


def test_guild_player_cur_vid(f_songs):
    player = dice.music.GuildPlayer(vids=f_songs)
    assert player.cur_vid == f_songs[0]
    player.vid_index = 1
    assert player.cur_vid == f_songs[1]


def test_guild_player_status(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    assert player.status() == 'stopped'

    f_vclient.is_playing.return_value = True
    f_vclient.is_connected.return_value = True
    assert player.status() == 'playing'

    f_vclient.is_playing.return_value = False
    f_vclient.is_paused.return_value = True
    assert player.status() == 'paused'


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
    assert not player.finished
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
    player.play = aiomock.Mock()

    assert player.vid_index == 0
    assert not player.finished
    assert not f_vclient.stop.called
    player.next()
    player.next()
    assert player.vid_index == 2
    assert not player.finished
    assert not f_vclient.stop.called
    player.next()
    assert player.vid_index == 2
    assert player.finished
    assert f_vclient.stop.called


def test_guild_player_prev(f_songs, f_vclient):
    player = dice.music.GuildPlayer(vids=f_songs, client=f_vclient)
    player.vid_index = 2
    player.play = aiomock.Mock()

    assert player.vid_index == 2
    assert not player.finished
    assert not f_vclient.stop.called
    player.prev()
    player.prev()
    assert player.vid_index == 0
    assert not player.finished
    assert not f_vclient.stop.called
    player.prev()
    assert player.vid_index == 0
    assert player.finished
    assert f_vclient.stop.called
