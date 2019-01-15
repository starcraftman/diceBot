"""
Tests for the dice.music music player
"""
import mock
import aiomock
import pytest

import dice.music
from dice.music import MPlayer, MPlayerState


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

    expect = "MPlayer(bot=True, cur_channel=None, err_channel=None, "\
             "d_voice=None, d_player=None, vids=[], vid_index=0, loop=True, volume=50, state=0)"
    assert repr(mplayer) == expect


def test_mplayer_status(f_bot):
    mplayer = MPlayer(f_bot)
    assert mplayer.status == 'Stopped'


def test_mplayer_set_volume(f_bot):
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

    mock_player = mock.MagicMock()
    mock_player.set
    mplayer.set_volume()
    assert mplayer.volume == 100


def test_mplayer_pause(f_bot):
    mock_player = mock.Mock()
    mplayer = MPlayer(f_bot)
    mplayer.__player = mock_player
    print(mock_player.pause.called)
    mplayer.pause()


def test_mplayer_stop(f_bot):
    mplayer = MPlayer(f_bot)
    mplayer.stop()

    assert mplayer.state == MPlayerState.STOPPED


@pytest.mark.asyncio
async def test_mplayer_quit(f_bot):
    mplayer = MPlayer(f_bot)
    await mplayer.quit()


def mock_dvoice():
    mock_dvoice = mock.MagicMock()
    mock_dvoice.channel = None
    mock_dvoice.disconnect.return_value = True  # Async
    mock_dvoice.move_to.return_value = True  # Async

    # Returns mocked player below
    mock_dvoice.create_ytdl_player.return_value = True  # Async
    mock_dvoice.create_ffmpeg_player.return_value = True

    return mock_dvoice


def mock_dplayer():
    mock_dplayer = mock.MagicMock()
    mock_dplayer.volume = 0
    mock_dplayer.start.return_value = True
    mock_dplayer.stop.return_value = True
    mock_dplayer.pause.return_value = True
    mock_dplayer.resume.return_value = True
    mock_dplayer.is_done.return_value = False

    return mock_dplayer
