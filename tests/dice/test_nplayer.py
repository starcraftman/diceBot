"""
Tests for dice.nplayer
"""
import glob
import os

import dice.nplayer

URL = "https://www.youtube.com/watch?v=IrbCrwtDIUA"


def test_yotube_dl():
    try:
        dice.nplayer.youtube_dl(URL, 'song', '/tmp')
        assert os.path.isfile('/tmp/song.opus')
    finally:
        for path in glob.glob('/tmp/nplayer*'):
            os.remove(path)
