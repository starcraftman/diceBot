# DiceBot

Implements a bot with useful commands for playing pen and paper games over discord.
There are a few other misc commands that were requested by users.

See the `!help` command (sample output below) and every subcommands help (i.e. !roll --help).

Command |                   Effect
------- | -------------------------------------------
!d5     | Search on the D&D 5e wiki
!effect | Add an effect to a user in turn order
!e      | Alias for `!effect`
!math   | Do some math operations
!music  | Play songs from server or youtube.
!m      | Alias for `!music`
!n      | Alias for `!turn --next`
!pf     | Search on the Pathfinder wiki
!poni   | Pony?!?!
!pun    | Prepare for pain!
!roll   | Roll a dice like: 2d6 + 5
!r      | Alias for `!roll`
!songs  | Create manage song lookup.
!star   | Search on the Starfinder wiki.
!status | Show status of bot including uptime
!timer  | Set a timer for HH:MM:SS in future
!timers | See the status of all YOUR active timers
!turn   | Manager turn order for pen and paper combat
!help   | This help message
!o.o    | Funny eyes ?!?

Support for discord.py <= 1.0.0 is discontinued.

## Required Permissions

The bot doesn't need any perms for core functions other than read/send to channel.
Optionally provide manage messages permission so it can clean up bad invocations and help requests.

## Setup

This bot requires python3 >= 3.5.x, if you don't have that available use pyenv + build-tools
to install it locally in your home.

Explaination of other requirements:
- A working mysql database (install mysql or mariadb packages from your local packages).
- I suggest a limited user for bot to use db with access to a table named 'dice'.
- FFMpeg is required for streaming youtube links.
- You require chromedriver on your path for selenium to get the
  the wiki results for commands like `!d5` or `!pf`.

For example on a debian machine, the following commands will suffice ...

```
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt-get update
sudo apt-get install mysql-server mysql-client ffmpeg chromium-browser
```
Do :s/mysql/mariadb/g if you want the latter.

After that get the corresponding chromedriver for the current version of chrome.
Varies by changes to chrome itself.

### Chrome & Chromedriver

If you do not have chrome/chromium available in packages
and want the latest stable use below PPA:
Google Chrome PPA:
    https://www.ubuntuupdates.org/ppa/google_chrome

Select the version that matches your installed chromium/chrome version.
Chromedriver Site:
    http://chromedriver.chromium.org/

### Config File

Copy this template config to `data/config.yml`

```
discord:
  dev: DISCORD_TOKEN  # Token of bot account to use.
dbs:
  main:
    db: dice  # Replace with the db you made for bot if you prefer another name
    host: localhost
    pass: DB_PASSWORD
    user: DB_USERNAME
music:
  cache_limit: 100  # This many Mbs of recent songs will be cached
  default_volume: 20  # Default volume songs will play at, stored in db if added.
  player_timeout: 120  # Timeout before bot quits empty voice channel
  voice_join_timeout: 5  # Seconds to wait before aborting join voice channel, sometimes does not complete
paths:
  log_conf: data/log.yml
  music: extras/music  # Any permanent songs you want local store here. Free to change path relative to root.
  youtube: /tmp/videos  # Youtube videos cache here, <= cache_limit MB above
ttl: 60  # Self deleting messages last this long

# vim: set ft=yaml :
```


[pyenv]: https://github.com/pyenv/pyenv
[chromedriver]:(http://chromedriver.chromium.org/downloads)
