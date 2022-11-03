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
import sqlalchemy.orm.exc as sqla_oexc
from sqlalchemy import func

import dice.exc
import dicedb

DEFAULT_VOLUME = dice.util.get_config('music', 'default_volume', default=20)


async def dump_db():  # pragma: no cover
    """
    Purely debug function, shunts db contents into file for examination.
    """
    client = dicedb.get_db_client()
    fname = os.path.join(tempfile.gettempdir(), 'dbdump_' + os.environ.get('COG_TOKEN', 'dev'))
    print("Dumping db contents to:", fname)
    with open(fname, 'w') as fout:
        for info in await client.list_collections():
            coll = await client.get_collection(info['name'])
            all_objs = await coll.find_many({})
            fout.write(f"---- {info['name']} ----\n")
            pprint.pprint(all_objs, fout)


async def get_duser(client, discord_id):
    """
    Return the DUser that has the same discord_id. None if nothing found for users.
    """
    return await client.discord_users.find_one({'discord_id': discord_id})


async def ensure_duser(client, discord_id, display_name):
    """
    Ensure a member has an entry in the discord_users table.

    Returns: The DUser
    """
    await client.discord_users.replace_one(
        {'discord_id': discord_id},
        {'discord_id': discord_id, 'display_name': display_name},
        True
    )

    return await client.discord_users.find_one({'discord_id': discord_id})


async def find_saved_roll(client, discord_id, name):
    """
    Find a loosely matching SavedRoll IFF there is exactly one match.

    Returns: The saved roll object. If nothing found None.
    """
    name_re = re.compile(r'^.*' + name + r'.*', re.IGNORECASE)
    return await client.rolls_saved.find_one({
        'discord_id': discord_id,
        'name': name_re,
    })


async def find_all_saved_rolls(client, discord_id, *, limit=None):
    """
    Find all SavedRolls for a given user_id. Empty list if none set.

    Returns: [SavedRoll, SavedRoll, ...]
    """
    return await client.rolls_saved.find({'discord_id': discord_id}).\
        sort([('name', 1)]).\
        to_list(limit)


async def update_saved_roll(client, discord_id, name, roll_str):
    """
    Update the saved named roll in the database.

    Returns:
        new_roll: The update object in the db.
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
    result = await client.rolls_saved.delete_one(
        {'discord_id': discord_id, 'name': name},
    )

    return result.deleted_count != 0


#  def add_pun(session, new_pun):
    #  """
    #  Add a pun to the pun database.
    #  """
    #  session.add(Pun(text=new_pun))
    #  session.commit()


#  def all_puns(session):
    #  """
    #  Get a complete list of puns.
    #  """
    #  return session.query(Pun).all()


#  def remove_pun(session, pun):
    #  """
    #  Remove a pun from the database.
    #  """
    #  session.delete(pun)
    #  session.commit()


#  def randomly_select_pun(session):
    #  """
    #  Get a random pun from the database.
    #  While selection is random, will evenly visit all puns before repeats.

    #  Raises:
        #  dice.exc.InvalidCommandArgs - No puns exist to choose.
    #  """
    #  try:
        #  lowest_hits = session.query(func.min(Pun.hits)).scalar()
        #  pun = numpy.random.choice(session.query(Pun).filter(Pun.hits == lowest_hits).all())

        #  pun.hits += 1
        #  session.add(pun)
        #  session.commit()

        #  return pun.text
    #  except (IndexError, ValueError):
        #  raise dice.exc.InvalidCommandArgs('You must add puns first!')


#  def check_for_pun_dupe(session, text):
    #  """
    #  Returns true if the text already contained in a Pun.
    #  """
    #  return session.query(Pun).filter(Pun.text == text).all()


#  def update_turn_order(session, key, turnorder):
    #  """
    #  Add an existing turn order for a given server/channel combination.
    #  """
    #  try:
        #  stored = session.query(TurnOrder).filter(TurnOrder.id == key).one()
        #  stored.text = repr(turnorder)
        #  session.add(stored)
    #  except sqla_oexc.NoResultFound:
        #  session.add(TurnOrder(id=key, text=repr(turnorder)))
    #  session.commit()


#  def get_turn_order(session, key):
    #  """
    #  Fetch an existing turn order for a given server/channel combination.
    #  """
    #  try:
        #  return session.query(TurnOrder).filter(TurnOrder.id == key).one().text
    #  except sqla_oexc.NoResultFound:
        #  return None


#  def remove_turn_order(session, key):
    #  """
    #  Remove the turn order from the db.
    #  """
    #  try:
        #  stored = session.query(TurnOrder).filter(TurnOrder.id == key).one()
        #  session.delete(stored)
        #  session.commit()
    #  except sqla_oexc.NoResultFound:
        #  pass


#  def generate_inital_turn_users(session, turn_key):
    #  """
    #  Find all potential turn order users for that turn_key.
    #  """
    #  chars = session.query(TurnChar).filter(TurnChar.turn_key == turn_key,
                                           #  TurnChar.modifier is not None,
                                           #  TurnChar.name is not None).all()
    #  return ['{}/{}'.format(char.name, char.modifier) for char in chars]


#  def get_turn_char(session, user_key, turn_key):
    #  """
    #  Fetch the character identified by the combination user_key & turn_key.
    #  """
    #  try:
        #  return session.query(TurnChar).filter(TurnChar.user_key == user_key,
                                              #  TurnChar.turn_key == turn_key).one()
    #  except sqla_oexc.NoResultFound:
        #  return None


#  def update_turn_char(session, user_key, turn_key, *, name=None, modifier=None):
    #  """
    #  Given user and turn ids, set a character and/or init value.
    #  """
    #  try:
        #  char = session.query(TurnChar).filter(TurnChar.user_key == user_key,
                                              #  TurnChar.turn_key == turn_key).one()
        #  if name:
            #  char.name = name
        #  if modifier:
            #  char.modifier = modifier

    #  except sqla_oexc.NoResultFound:
        #  char = TurnChar(user_key=user_key, turn_key=turn_key, name=name, modifier=modifier)

    #  session.add(char)
    #  session.commit()


#  def remove_turn_char(session, user_key, turn_key):
    #  """
    #  Delete the turn character from db.
    #  """
    #  try:
        #  char = session.query(TurnChar).filter(TurnChar.user_key == user_key,
                                              #  TurnChar.turn_key == turn_key).one()
        #  session.delete(char)
        #  session.commit()
    #  except sqla_oexc.NoResultFound:
        #  pass


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


#  def get_googly(session, user_id):
    #  """
    #  Get a Googly from the db for the given user.
    #  If none set, create one.

    #  Returns:
        #  A Googly for user.
    #  """
    #  try:
        #  googly = session.query(Googly).filter(Googly.id == user_id).one()
    #  except sqla_oexc.NoResultFound:
        #  googly = Googly(id=user_id)
        #  session.add(googly)
        #  session.commit()

    #  return googly


#  def get_last_rolls(session, user_id):
    #  """
    #  Simply get all previous rolls by a user.

    #  Args:
        #  session: An SQLAlchemy session.
        #  user_id: A discord user id.

    #  Returns:
        #  [LastRoll(), LastRoll(), ...]
    #  """
    #  return session.query(LastRoll).filter(LastRoll.id == user_id).order_by(LastRoll.id_num).all()


#  def add_last_roll(session, user_id, roll_str, limit=20):
    #  """
    #  A user has made a new roll. Store only if the spec differs from last one.
    #  Will not store two following rolls that are exactly the same.
    #  Rolls that exceed storage limit will be ignored rather than truncated.

    #  Args:
        #  user_id: A discord user ID.
        #  roll_str: A dice specification.
        #  limit: The limit of dice to keep.
    #  """
    #  if len(roll_str) > dicedb.schema.LEN_ROLLSTR:
        #  return

    #  rolls = get_last_rolls(session, user_id)
    #  try:
        #  last_roll = rolls[-1]
        #  if last_roll.roll_str == roll_str:
            #  return
        #  next_id_num = last_roll.id_num + 1 % 1000
    #  except (AttributeError, IndexError):
        #  next_id_num = 0

    #  for roll in rolls[:-limit]:
        #  session.delete(roll)

    #  new_roll = LastRoll(id=user_id, id_num=next_id_num, roll_str=roll_str)
    #  session.add(new_roll)
    #  session.commit()


#  def get_movies(session, user_id):
    #  """
    #  Return all Movies a user has added for later.
    #  """
    #  return session.query(Movie).filter(Movie.id == user_id).order_by(Movie.id_num).all()


#  def add_movies(session, user_id, movie_names):
    #  """
    #  Add a movie after the current selection.
    #  """
    #  movies = get_movies(session, user_id)
    #  if not movies:
        #  id_num = 0
    #  else:
        #  id_num = movies[-1].id_num + 1

    #  for movie_name in movie_names:
        #  session.add(Movie(id=user_id, id_num=id_num, name=movie_name))
        #  id_num += 1
    #  session.commit()


#  def replace_all_movies(session, user_id, movie_names):
    #  """
    #  Remove all current movies and replace the list with the new list of movie names.

    #  Args:
        #  session: A session object.
        #  user_id: Discord id.
        #  movie_names: A list of movie names, no string bigger than 200 chars.
    #  """
    #  for movie in get_movies(session, user_id):
        #  session.delete(movie)
    #  session.commit()

    #  cnt = 0
    #  movies = []
    #  for movie_name in movie_names:
        #  movies += [Movie(id=user_id, id_num=cnt, name=movie_name)]
        #  cnt += 1

    #  session.add_all(movies)
    #  session.commit()
