"""
Tests for the dice.music music player
"""
import aiomock
import pytest

import dice.music
from dice.music import MPlayer, MPlayerState

from tests.conftest import fake_msg


@pytest.fixture
def f_d_voice():
    mock = aiomock.AIOMock()
    mock.channel = 'MockVoice'
    mock.disconnect.async_return_value = True  # Async
    mock.move_to.async_return_value = True  # Async
    mock.create_ytdl_player.async_return_value = True  # Async
    mock.create_ffmpeg_player.return_value = True

    return mock


@pytest.fixture
def f_d_player():
    mock = aiomock.AIOMock()
    mock.volume = 55
    mock.start.return_value = True
    mock.stop.return_value = True
    mock.pause.return_value = True
    mock.resume.return_value = True
    mock.is_done.return_value = False

    return mock


def test_mplayer__str__(f_bot):
    mplayer = MPlayer(f_bot)
    mplayer.vids = ['video1', 'www.google.ca']

    expect = """__**Player Status**__ :

        Queue: ['video1', '<www.google.ca>']
        Index: 0
        Volume: 50/100
        Loop: True
        Status: Stopped
"""
    assert str(mplayer) == expect


def test_mplayer__repr__():
    mplayer = MPlayer(True)

    expect = "MPlayer(bot=True, target_voice_channel=None, err_channel=None, "\
             "d_voice=None, d_player=None, vids=[], vid_index=0, loop=True, volume=50, state=0)"
    assert repr(mplayer) == expect


def test_mplayer_status(f_bot):
    mplayer = MPlayer(f_bot)
    assert mplayer.status == 'Stopped'


def test_mplayer_set_volume_bounds(f_bot):
    mplayer = MPlayer(f_bot)
    assert mplayer.volume == 50

    with pytest.raises(dice.exc.InvalidCommandArgs):
        mplayer.set_volume('a')

    with pytest.raises(dice.exc.InvalidCommandArgs):
        mplayer.set_volume(1000)

    mplayer.set_volume(0)
    assert mplayer.volume == 0

    mplayer.set_volume(1)
    assert mplayer.volume == 1

    mplayer.set_volume(100)
    assert mplayer.volume == 100


def test_mplayer_set_volume_d_player(f_bot, f_d_player):
    mplayer = MPlayer(f_bot, d_player=f_d_player)
    mplayer.set_volume(95)
    mplayer.set_volume()
    assert mplayer.volume == 95
    assert f_d_player.volume == 0.95


def test_mplayer_initialize_settings(f_bot, f_d_player):
    msg = fake_msg('!play vid1, vid2', voice=True)
    mplayer = MPlayer(f_bot, d_player=f_d_player)
    mplayer.initialize_settings(msg, ['vid1', 'vid2'])

    assert mplayer.vids == ['vid1', 'vid2']
    assert mplayer.vid_index == 0
    assert mplayer.target_voice_channel == msg.author.voice.voice_channel
    assert mplayer.err_channel == msg.channel


def test_mplayer_initialize_settings_default_voice(f_bot, f_d_player):
    msg = fake_msg('!play vid1, vid2', voice=False)
    mplayer = MPlayer(f_bot, d_player=f_d_player)
    mplayer.initialize_settings(msg, ['vid1', 'vid2'])

    assert mplayer.vids == ['vid1', 'vid2']
    assert mplayer.vid_index == 0
    assert str(mplayer.target_voice_channel) == 'Channel: voice1'
    assert mplayer.err_channel == msg.channel


def test_mplayer_stop(f_bot, f_d_player):
    mplayer = MPlayer(f_bot, d_player=f_d_player)
    mplayer.stop()

    assert mplayer.state == MPlayerState.STOPPED
    assert f_d_player.stop.called


def test_mplayer_stop_no_player(f_bot):
    mplayer = MPlayer(f_bot)
    mplayer.stop()

    assert mplayer.state == MPlayerState.STOPPED


def test_mplayer_pause(f_bot, f_d_player):
    mplayer = MPlayer(f_bot, d_player=f_d_player)
    mplayer.state = MPlayerState.PLAYING

    mplayer.pause()
    assert mplayer.state == MPlayerState.PAUSED
    assert f_d_player.pause.called

    mplayer.pause()
    assert mplayer.state == MPlayerState.PLAYING
    assert f_d_player.resume.called


@pytest.mark.asyncio
async def test_mplayer_join_voice_channel_already_joined(f_bot, f_d_voice):
    mplayer = MPlayer(f_bot, d_voice=f_d_voice)
    mplayer.target_voice_channel = 'NewVoice'
    await mplayer.join_voice_channel()

    f_d_voice.move_to.assert_called_with(mplayer.target_voice_channel)


@pytest.mark.asyncio
async def test_mplayer_join_voice_channel_not_joined(f_bot):
    mplayer = MPlayer(f_bot)
    await mplayer.join_voice_channel()

    assert mplayer.d_voice
    f_bot.join_voice_channel.assert_called_with(mplayer.target_voice_channel)


@pytest.mark.asyncio
async def test_mplayer_quit(f_bot, f_d_player, f_d_voice):
    mplayer = MPlayer(f_bot, d_player=f_d_player, d_voice=f_d_voice)
    await mplayer.quit()

    assert f_d_player.stop.called
    assert f_d_voice.disconnect.called
    assert mplayer.state == MPlayerState.STOPPED
    assert not mplayer.d_player
    assert not mplayer.d_voice


@pytest.mark.asyncio
async def test_mplayer_quit_no_player(f_bot):
    mplayer = MPlayer(f_bot)
    await mplayer.quit()

    assert mplayer.state == MPlayerState.STOPPED
    assert not mplayer.d_player
    assert not mplayer.d_voice


#  @pytest.mark.asyncio
#  async def test_mplayer_start(f_bot, f_d_player):
    #  msg = fake_msg('!play vid1, vid2', voice=True)
    #  mplayer = MPlayer(f_bot, d_player=f_d_player)
    #  print(msg)
    #  mplayer.initialize_settings(msg, ['vid1', 'vid2'])
    #  await mplayer.start()

    #  assert mplayer.vids == ['vid1', 'vid2']
    #  assert mplayer.vid_index == 0
    #  assert mplayer.target_voice_channel == msg.author.voice.voice_channel
    #  assert mplayer.err_channel == msg.channel


#  @pytest.mark.asyncio
#  async def test_mplayer_next_loop(f_bot, f_d_player):
    #  mplayer = MPlayer(f_bot, d_player=f_d_player)
    #  await mplayer.next()


#  @pytest.mark.asyncio
#  async def test_mplayer_next_stop(f_bot, f_d_player):
    #  mplayer = MPlayer(f_bot, d_player=f_d_player)
    #  mplayer.state = MPlayerState.PLAYING
    #  await mplayer.next()


#  @pytest.mark.asyncio
#  async def test_mplayer_prev_loop(f_bot, f_d_player):
    #  mplayer = MPlayer(f_bot, d_player=f_d_player)
    #  await mplayer.prev()


#  @pytest.mark.asyncio
#  async def test_mplayer_prev_stop(f_bot, f_d_player):
    #  mplayer = MPlayer(f_bot, d_player=f_d_player)
    #  await mplayer.prev()


#  @pytest.mark.asyncio
#  async def test_mplayer_monitor(f_bot, f_d_player, f_loop):
    #  mplayer = MPlayer(f_bot, d_player=f_d_player)
    #  await mplayer.monitor()
