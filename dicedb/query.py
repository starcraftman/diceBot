"""
Module should handle logic related to querying/manipulating tables from a high level.
"""
from __future__ import absolute_import, print_function
import os
import pathlib
import pprint
import re
import tempfile

import numpy.random

import dice.exc
import dicedb

DEFAULT_VOLUME = dice.util.get_config('music', 'default_volume', default=20)


async def dump_db():  # pragma: no cover
    """
    Purely debug function, shunts db contents into file for examination.
    """
    client = dicedb.get_db_client()
    fname = os.path.join(tempfile.gettempdir(), 'dbdump_' + os.environ.get('TOKEN', 'dev'))
    print("Dumping db contents to:", fname)
    with open(fname, 'w', encoding='utf-8') as fout:
        for info in await client.list_collections():
            coll = await client.get_collection(info['name'])
            all_objs = await coll.find_many({})
            fout.write(f"---- {info['name']} ----\n")
            pprint.pprint(all_objs, fout)


async def get_duser(client, discord_id):
    """Get the discord user from the database with any user prefs.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
    """
    return await client.discord_users.find_one({'discord_id': discord_id})


async def ensure_duser(client, discord_id, display_name):
    """Ensure a user is present in the database.

    If they aren't present insert them. If they are, update them.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        display_name: The name of the user on server.
    """
    await client.discord_users.replace_one(
        {'discord_id': discord_id},
        {'discord_id': discord_id, 'display_name': display_name},
        True
    )

    return await client.discord_users.find_one({'discord_id': discord_id})


async def find_saved_roll(client, discord_id, name):
    """Find a saved roll by user under a particular name.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the saved roll. Will be loosely matched on left and right.
    """
    name_re = re.compile(r'^.*' + name + r'.*', re.IGNORECASE)
    return await client.rolls_saved.find_one({
        'discord_id': discord_id,
        'name': name_re,
    })


async def find_all_saved_rolls(client, discord_id):
    """Find __ALL__ saved rolls by user. Sort the results by name.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
    """
    return await client.rolls_saved.find({'discord_id': discord_id}).\
        sort([('name', 1)]).\
        to_list(None)


async def update_saved_roll(client, discord_id, name, roll_str):
    """Update or insert a saved roll for the given user.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the saved roll.
        roll_str: The actual roll string that can be rolled later.
    """
    await client.rolls_saved.replace_one(
        {'discord_id': discord_id, 'name': name},
        {'discord_id': discord_id, 'name': name, 'roll': roll_str},
        True
    )

    return await client.rolls_saved.find_one(
        {'discord_id': discord_id, 'name': name}
    )


async def remove_saved_roll(client, discord_id, name):
    """Remove a single saved roll by user id and name.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the saved roll.
    """
    result = await client.rolls_saved.delete_one(
        {'discord_id': discord_id, 'name': name},
    )

    return result.deleted_count != 0


async def get_roll_history(client, discord_id):
    """Get all rolls made by the user with this bot.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
    """
    exists = await client.rolls_made.find_one({'discord_id': discord_id})
    if not exists:
        await client.rolls_made.insert_one({'discord_id': discord_id, 'history': []})
        exists = await client.rolls_made.find_one({'discord_id': discord_id})

    return exists


async def add_roll_history(client, discord_id, *, entries, limit=100):
    """Add a roll to roll history for a discord user.

    Prune the overall history down to limit upon update.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        entries: A list of objects to add to roll history. Expecting:
            [{'roll': '3d6 + 10', 'result': '22'}, ...]
        limit: The max history to store. Default is 100.
    """
    rolls = await get_roll_history(client, discord_id)

    # Ensure now adjacent repeats, unlikely but prudent
    last_entry = {'roll': '', 'result': ''}
    if rolls['history']:
        last_entry = rolls['history'][-1]
    for entry in entries:
        if entry != last_entry:
            rolls['history'] += [entry]
            last_entry = entry
    rolls['history'] = rolls['history'][-limit:]

    return await client.rolls_made.replace_one(
        {'discord_id': discord_id},
        rolls,
    )


async def check_for_pun_dupe(client, discord_id, pun):
    """Returns True IFF the text already exists in users pun list.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        pun: The pun to look for.
    """
    existing = await get_all_puns(client, discord_id)
    return [x for x in existing['puns'] if x['text'] == pun] != []


async def add_pun(client, discord_id, new_pun):
    """Add a new pun for a given discord user. Will not allow dupes.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        new_pun: The new pun text.
    """
    exists = await client.puns.find_one({'discord_id': discord_id})
    is_dupe = new_pun in [x['text'] for x in exists['puns']]
    if exists and not is_dupe:
        exists['puns'] += [{'text': new_pun, 'hits': 0}]
    else:
        exists = {'discord_id': discord_id, 'puns': [{'text': new_pun, 'hits': 0}]}

    return await client.puns.replace_one(
        {'discord_id': discord_id},
        exists,
        True
    )


async def get_all_puns(client, discord_id):
    """Get the puns object a user has stored. If they have none, return a new entry for them.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
    """
    exists = await client.puns.find_one({'discord_id': discord_id})
    if not exists:
        await client.puns.insert_one({'discord_id': discord_id, 'puns': []})
        exists = await client.puns.find_one({'discord_id': discord_id})

    return exists


async def remove_pun(client, discord_id, pun_text):
    """Remove a pun from a users stored puns. Ignore if none stored.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        pun: The text of the pun to remove.
    """
    exists = await get_all_puns(client, discord_id)

    if exists:
        exists['puns'] = [x for x in exists['puns'] if x['text'] != pun_text]

        return await client.puns.replace_one(
            {'discord_id': discord_id},
            exists,
            True
        )


async def randomly_select_pun(client, discord_id):
    """Randomly select a single pun from a user. Increment hits for the pun.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
    """
    puns = await get_all_puns(client, discord_id)
    if not puns['puns']:
        raise dice.exc.InvalidCommandArgs("Please add some puns first!")

    choice = numpy.random.randint(0, len(puns['puns']))
    puns['puns'][choice]['hits'] += 1
    await client.puns.replace_one(
        {'discord_id': puns['discord_id']},
        puns
    )

    return puns['puns'][choice]['text']


async def get_googly(client, discord_id, default_total=100):
    """Get a googly from the database.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        default_total: The default amount of googly eyes to give.
    """
    exists = await client.googly_eyes.find_one({'discord_id': discord_id})
    if not exists:
        await client.googly_eyes.insert_one({'discord_id': discord_id, 'total': default_total, 'used': 0})
        exists = await client.googly_eyes.find_one({'discord_id': discord_id})

    return exists


async def update_googly(client, googly_eyes):
    """Update a googly from database after usage.

    Args:
        client: A connection onto the db.
        googly_eyes: An existing googly eyes object.
    """
    return await client.googly_eyes.replace_one(
        {'discord_id': googly_eyes['discord_id']},
        googly_eyes
    )


async def get_list(client, discord_id, name):
    """Return all entries in a named list.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the list to retrieve.
    """
    return await client.lists.find_one({'discord_id': discord_id, 'name': name})


async def add_list_entries(client, discord_id, name, to_add):
    """Add entries to an existing list name. If it doesn't exist, create the list.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the list to retrieve.
        to_add: Entries to add to the list.
    """
    exists = await get_list(client, discord_id, name)
    if exists:
        exists['entries'] += to_add
    else:
        exists = {'discord_id': discord_id, 'name': name, 'entries': to_add}

    return await client.lists.replace_one(
        {'discord_id': discord_id, 'name': name},
        exists,
        True
    )


async def remove_list_entries(client, discord_id, name, to_remove):
    """Remove entries from an existing list name. If it doesn't exist, ignore.

    If all entries removed from a list, delete it entirely.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the list to retrieve.
        to_remove: Remove entries that match this text.
    """
    exists = await get_list(client, discord_id, name)
    if exists:
        exists['entries'] = [x for x in exists['entries'] if x not in to_remove]

        if exists['entries']:
            return await client.lists.replace_one(
                {'discord_id': discord_id, 'name': name},
                exists
            )

        return await client.lists.delete_one({'discord_id': discord_id, 'name': name})


async def replace_list_entries(client, discord_id, name, replacement):
    """
    Replace the list with the new entries passed in.

    Args:
        client: A connection onto the db.
        discord_id: The discord id of the user.
        name: The name of the list to retrieve.
        replacement: Entries to replace old list entries with.
    """
    return await client.lists.replace_one(
        {'discord_id': discord_id, 'name': name},
        {'discord_id': discord_id, 'name': name, 'entries': replacement},
        True
    )


async def get_turn_order(client, *, discord_id, channel_id):
    """
    Fetch an existing turn order for a given server/channel combination.
    """
    return await client.combat_trackers.find_one({'discord_id': discord_id, 'channel_id': channel_id})


async def update_turn_order(client, *, discord_id, channel_id, combat_tracker):
    """
    Add an existing turn order for a given server/channel combination.
    """
    return await client.combat_trackers.replace_one(
        {'discord_id': discord_id, 'channel_id': channel_id},
        combat_tracker,
        True
    )


async def remove_turn_order(client, *, discord_id, channel_id):
    """
    Remove the turn order from the db.
    """
    return await client.combat_trackers.delete_one({'discord_id': discord_id, 'channel_id': channel_id})


#  def add_song_with_tags(session, name, url, tags=None):
    #  """
    #  Add a song with many possible tags. If the song exists, delete it and overwrite.
    #  """
    #  try:
        #  existing = session.query(Song).filter(Song.name == name).one()
        #  remove_song_with_tags(session, existing.name)
    #  except sqla_oexc.NoResultFound:
        #  pass

    #  song = Song(name=name, folder=dice.util.get_config('paths', 'music'),
                #  url=None, repeat=False, volume_int=DEFAULT_VOLUME)
    #  if dice.util.is_valid_yt(url):
        #  song_url = 'https://youtu.be/' + dice.util.is_valid_yt(url)
        #  song = Song(name=name, folder=dice.util.get_config('paths', 'youtube'),
                    #  url=song_url, repeat=False, volume_int=DEFAULT_VOLUME)
    #  session.add(song)
    #  session.commit()

    #  song_tags = []
    #  for tag in tags:
        #  song_tags += [SongTag(name=tag, song_key=song.id)]
    #  session.add_all(song_tags)
    #  session.commit()

    #  return song


#  def remove_song_with_tags(session, name):
    #  """
    #  Remove a song and any tags.
    #  """
    #  song = session.query(Song).filter(Song.name.ilike(name)).one()
    #  for tag in song.tags:
        #  session.delete(tag)
    #  session.delete(song)
    #  session.commit()


#  def search_songs_by_name(session, name):
    #  """
    #  Get the possible song by name.
    #  """
    #  try:
        #  return [session.query(Song).filter(Song.name == name).one()]
    #  except sqla_oexc.NoResultFound:
        #  return session.query(Song).filter(Song.name.ilike('%{}%'.format(name))).all()


#  def get_song_by_id(session, id):
    #  """
    #  Get a song that you want by id.
    #  """
    #  return session.query(Song).filter(Song.id == id).one()


#  def get_songs_with_tag(session, tag_name):
    #  """
    #  Get the possible song by name.
    #  """
    #  subq = session.query(SongTag.song_key).filter(SongTag.name == tag_name).subquery()
    #  return session.query(Song).filter(Song.id.in_(subq)).all()


#  def get_song_choices(session):
    #  """
    #  Get all possible choices for song names.

    #  args:
        #  session: session to the database.
    #  """
    #  return session.query(Song).order_by(Song.name).all()


#  def get_tag_choices(session, similar_to=None):
    #  """
    #  Get all possible choices for tag names and their counts.

    #  args:
        #  session: session to the database.
        #  similar_to: Only return tags similar to this.
    #  """
    #  query = session.query(SongTag.name).distinct()
    #  if similar_to:
        #  query = query.filter(SongTag.name.ilike('%{}%'.format(similar_to)))

    #  return [x[0] for x in query.order_by(SongTag.name).all()]


#  def validate_videos(list_vids, session=None):
    #  """
    #  Validate the videos asked to play. Accepted formats:
        #  - youtube links
        #  - names of songs in the song db
        #  - names of files on the local HDD

    #  Raises:
        #  InvalidCommandArgs - A video link or name failed validation.
        #  ValueError - Did not pass a list of videos.
    #  """
    #  if not isinstance(list_vids, type([])):
        #  raise ValueError("Did not pass a list of videos.")

    #  if not session:
        #  session = dicedb.Session()

    #  pat = pathlib.Path(dice.util.get_config('paths', 'music'))
    #  new_vids = []
    #  for vid in list_vids:
        #  match = re.match(r'\s*<\s*(\S+)\s*>\s*', vid)
        #  if match:
            #  vid = match.group(1)

        #  matches = dicedb.query.search_songs_by_name(session, vid)
        #  if matches and len(matches) == 1:
            #  new_vids.append(matches[0])

        #  elif dice.util.is_valid_yt(vid):
            #  yt_id = dice.util.is_valid_yt(vid)
            #  new_vids.append(Song(id=None, name='youtube_{}'.format(yt_id), folder='/tmp/videos',
                                 #  url='https://youtu.be/' + yt_id, repeat=False, volume_int=DEFAULT_VOLUME))

        #  elif dice.util.is_valid_url(vid):
            #  raise dice.exc.InvalidCommandArgs("Only youtube links supported: " + vid)

        #  else:
            #  globbed = list(pat.glob(vid + "*"))
            #  if len(globbed) != 1:
                #  raise dice.exc.InvalidCommandArgs("{} does not match a Song in db or a local file.".format(vid))

            #  name = os.path.basename(globbed[0]).replace('.opus', '')
            #  new_vids.append(Song(id=None, name=name, folder=pat, url=None, repeat=False,
                                 #  volume_int=DEFAULT_VOLUME))

    #  return new_vids
