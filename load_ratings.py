import glob
import os
from collections import defaultdict
from pathlib import Path

from common import mpd_client, RATINGS_DB, load_db, RatingValue


def strip_ext(path):
  return os.path.splitext(path)[0]


def strip_rating_exts(rating_dict):
  ratings = {}
  for path, rating in rating_dict.items():
    path = strip_ext(path)
    if path not in ratings or rating.updated > ratings[path].updated:
      ratings[path] = rating
  return ratings


default_file_rating = RatingValue(0, 0)
# find all ratings that are newer than our ratings
our_ratings = strip_rating_exts(load_db(RATINGS_DB))
changed_ratings = {}
path_src = {}
for db_file in glob.glob('*_ratings.sql'):
  if db_file == RATINGS_DB:
    continue
  db_shortname = Path(db_file).stem
  for path, rating in load_db(db_file).items():
    path = strip_ext(path)
    current_rating = changed_ratings.get(
      path,
      our_ratings.get(path, default_file_rating)
    )
    if rating.updated > current_rating.updated and rating.rating != current_rating.rating:
      changed_ratings[path] = rating
      path_src[path] = db_shortname

if changed_ratings:
  print(len(changed_ratings), 'rating(s) to update')

path_mapping = defaultdict(list)
for res in mpd_client.listall():
  if path := res.get('file', None):
    path_mapping[strip_ext(path)].append(path)
find_files = lambda path: path_mapping[path]

for path, rating in changed_ratings.items():
  real_paths = find_files(path)
  for real_path in real_paths:
    print(f'rating={rating.rating}', real_path, path_src.get(path))
    mpd_client.sticker_set('song', real_path, 'rating', rating.rating)
  if not real_paths:
    print('Not found', f'rating={rating.rating}', path, {path_src.get(path)})
