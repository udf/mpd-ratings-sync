import os
import json
import socket
import re
import sqlite3
from collections import namedtuple

from mpd import MPDClient

RATING_RE = re.compile(r'rating=(\d+)')
RATINGS_DB = f'{socket.gethostname()}_ratings.sql'
RatingValue = namedtuple('RatingValue', ('rating', 'updated'))

mpd_client = MPDClient()
mpd_client.connect('localhost', 6600)
if 'PASSWORD' in os.environ:
  mpd_client.password(os.environ['PASSWORD'])

# sticker.sql change -> dump db (if changed)
# dir change -> load

def get_current_ratings() -> dict[str, int]:
  cur_ratings = {}
  #TODO: maybe read from mpd sticker database directly
  for t in mpd_client.sticker_find('song', '', 'rating', '>', 0):
    match = RATING_RE.match(t['sticker'])
    if match:
      cur_ratings[t['file']] = int(match[1])
  return cur_ratings


def load_db(filepath, fetch_date=True) -> dict[str, RatingValue] | dict[str, int]:
  if not os.path.exists(filepath):
    return {}
  con = sqlite3.connect(filepath)
  cur = con.cursor()
  if fetch_date:
    cur.execute('SELECT path, rating, updated FROM ratings;')
    return {r[0]: RatingValue(r[1], r[2]) for r in cur.fetchall()}
  cur.execute('SELECT path, rating FROM ratings;')
  return {r[0]: r[1] for r in cur.fetchall()}


def update_ratings_db(ratings: dict[str, int]):
  old_ratings = load_db(RATINGS_DB, fetch_date=False)

  updated = {}
  for path, rating in ratings.items():
    old_rating = old_ratings.get(path, 0)
    if rating != old_rating:
      updated[path] = rating
  to_delete = []
  for path in set(old_ratings) - set(ratings):
    if mpd_client.find('file', path):
      # set removed ratings to 0 if they changed
      if old_ratings[path] != 0:
        updated[path] = 0
      continue
    # stop tracking deleted files
    to_delete.append(path)

  if to_delete:
    print(f'Deleting {len(to_delete)} rating(s):', to_delete)
    con = sqlite3.connect(RATINGS_DB)
    with con:
      con.executemany(
        "DELETE FROM ratings WHERE path=?;",
        ((v,) for v in to_delete)
      )

  if not updated:
    return updated

  print(f'Updating {len(updated)} rating(s):', updated)
  con = sqlite3.connect(RATINGS_DB)
  with con:
    con.execute('''
      CREATE TABLE IF NOT EXISTS ratings(
        path TEXT PRIMARY KEY,
        rating INTEGER,
        updated INTEGER DEFAULT (UNIXEPOCH('now'))
      );
    ''')
    con.executemany(
      '''
        INSERT INTO ratings (path, rating) VALUES (?, ?)
        ON CONFLICT(path) DO UPDATE
        SET
          rating = EXCLUDED.rating,
          updated = UNIXEPOCH('now')
        ;
      ''',
      updated.items()
    )

  return updated
