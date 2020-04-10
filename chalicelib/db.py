from functools import partial

import gino
from config import DATABASE_URI

db: gino.Gino = gino.Gino()
db.url = DATABASE_URI
db.with_bind = partial(db.with_bind, bind=DATABASE_URI)
