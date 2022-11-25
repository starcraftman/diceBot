"""
All database related code resides under this module.
This database uses motor python library, an async version of pymongo.

Followed simple tutorial for tutorial on motor.

See: https://motor.readthedocs.io/en/stable/tutorial-asyncio.html
"""
import motor.motor_asyncio

LOCAL_URL = 'mongodb://localhost:31000'


def get_db_client(with_database='dice'):
    """
    Returns the db client to mongo, after selecting the database first.
    If you want raw client, pass None.

    Store the access line locally in atlas.private in root of project.
    """
    with open('atlas.private', encoding='utf-8') as fin:
        atlas_url = fin.read().strip()
        client = motor.motor_asyncio.AsyncIOMotorClient(atlas_url)

    if with_database:
        client = client[with_database]

    return client
