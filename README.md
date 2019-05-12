# DiceBot

Implements a bot with useful commands for playing pen and paper games over discord.
Examples of features:
    - Roll dice with `!roll`
    - Play music from youtube and lookup from db with `!play` and `!songs`
    - Implements a simple turn order manager for turn based combat.
    - Simple ability to set per user timers for reminders.

## Required Permissions

The bot doesn't need any perms for core functions other than read/send to channel.
Optionally provide manage channel permission so it can clean up bad invocations and help requests.

## Commands

See a full list of commands with `!help`. For each top level command see specific help,
for instance for help with `!roll`, try `!roll --help`.

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
sudo apt-get install mysql-server mysql-client ffmpeg google-chrome-stable
```
Do :s/mysql/mariadb/g if you want the latter.

After that get the corresponding chromedriver for the current version of chrome.
Varies by changes to chrome itself.


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
