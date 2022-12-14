"""
All database related code resides under this module.
This database uses motor python library, an async version of pymongo.

Followed simple tutorial for tutorial on motor.

See: https://motor.readthedocs.io/en/stable/tutorial-asyncio.html
"""
import os
import pathlib
import sys

import certifi
import motor.motor_asyncio

LOCAL_URL = 'mongodb://localhost:31000'
ROOT = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
CERT_URL = pathlib.Path(os.path.join(ROOT, 'atlasCert.url.private'))
CERT_PAT = pathlib.Path(os.path.join(ROOT, 'atlasCert.private'))
PASS_PAT = pathlib.Path(os.path.join(ROOT, 'atlasPass.private'))

DEFAULT_DB = 'dice'
TEST_DB = False
if 'pytest' in sys.modules:
    TEST_DB = True


def get_db_client(with_database=DEFAULT_DB):
    """
    Returns the db client to mongo, after selecting the database first.
    If you want raw client, pass None.

    When X509 cert found at CERT_PAT, authenticate via X509.
    CERT_URL will hold the url to authenticate against with cert.
    Otherwise fallback to authentication via URL user/pass login found in PASS_PAT

    Args:
        with_database: Return this collection from top level client. Default dice
    """
    if CERT_PAT.exists() and CERT_URL.exists():
        with open(CERT_URL, encoding='utf-8') as fin:
            client = motor.motor_asyncio.AsyncIOMotorClient(
                fin.read().strip(),
                authMechanism="MONGODB-X509",
                tls=True,
                tlsCertificateKeyFile=str(CERT_PAT),
                tlsCAFile=certifi.where(),
            )
    else:
        with open(PASS_PAT, encoding='utf-8') as fin:
            client = motor.motor_asyncio.AsyncIOMotorClient(fin.read().strip())

    if with_database and TEST_DB:  # Bit of a hack to send all tests to different top level
        with_database = 'test_' + with_database
    if with_database:
        client = client[with_database]

    return client
