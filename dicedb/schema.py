"""
Define the database schema and some helpers.

N.B. Schema defaults only applied once object commited.
"""
from __future__ import absolute_import, print_function
from functools import total_ordering

import sqlalchemy as sqla
import sqlalchemy.orm as sqla_orm
import sqlalchemy.ext.declarative

import dice.exc
import dice.tbl
import dicedb


LEN_DID = 30
LEN_NAME = 100
LEN_ROLLSTR = 200
Base = sqlalchemy.ext.declarative.declarative_base()


@total_ordering
class DUser(Base):
    """
    Table to store discord users and their permanent preferences.
    """
    __tablename__ = 'discord_users'

    id = sqla.Column(sqla.String(LEN_DID), primary_key=True)  # Discord id
    display_name = sqla.Column(sqla.String(LEN_NAME))

    def __repr__(self):
        keys = ['id', 'display_name']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "DUser({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, DUser) and self.id == other.id

    def __lt__(self, other):
        return self.id < other.id

    @property
    def mention(self):
        """ Mention this user in a response. """
        return "<@" + self.id + ">"


@total_ordering
class SavedRoll(Base):
    __tablename__ = 'saved_rolls'

    id = sqla.Column(sqla.Integer, primary_key=True)
    name = sqla.Column(sqla.String(LEN_NAME))
    roll_str = sqla.Column(sqla.String(LEN_ROLLSTR))
    user_id = sqla.Column(sqla.String(LEN_DID), sqla.ForeignKey('discord_users.id'), nullable=False)

    def __repr__(self):
        keys = ['id', 'user_id', 'name', 'roll_str']
        kwargs = ['{}={!r}'.format(key, getattr(self, key)) for key in keys]

        return "SavedRoll({})".format(', '.join(kwargs))

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return isinstance(other, SavedRoll) and (
            self.user_id, self.name, self.roll_str) == (other.user_id, other.name, other.roll_str)

    def __lt__(self, other):
        return (self.user_id, self.name) < (other.user_id, other.name)


def parse_int(word):
    """ Parse into int, on failure return 0 """
    try:
        return int(word)
    except ValueError:
        return 0


def parse_float(word):
    """ Parse into float, on failure return 0.0 """
    try:
        return float(word)
    except ValueError:
        return 0.0


def empty_tables(session):
    """
    Drop all tables.
    """
    classes = [SavedRoll, DUser]

    for cls in classes:
        for matched in session.query(cls):
            session.delete(matched)
    session.commit()


def recreate_tables(engine=dicedb.engine):
    """
    Recreate all tables in the database, mainly for schema changes and testing.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


# Relationships
DUser.rolls = sqla_orm.relationship('SavedRoll',
                                    cascade='all, delete, delete-orphan',
                                    back_populates='user',
                                    lazy='select')
SavedRoll.user = sqla_orm.relationship('DUser', uselist=False, back_populates='rolls',
                                       lazy='select')

if dicedb.TEST_DB:
    recreate_tables()
else:
    Base.metadata.create_all(dicedb.engine)


def main():  # pragma: no cover
    """
    This continues to exist only as a sanity test for schema and relations.
    """
    print('Schema Main: Forcing DB to use \'test\'')
    creds = dice.util.get_config('dbs', 'main')
    creds['db'] = 'test_dice'
    engine = sqla.create_engine(dicedb.MYSQL_SPEC.format(**creds), echo=False, pool_recycle=3600)
    session = sqla_orm.sessionmaker(bind=engine)()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    dusers = (
        DUser(id='1234', display_name='User1'),
        DUser(id='2345', display_name='User2'),
        DUser(id='3456', display_name='User3'),
    )
    session.add_all(dusers)
    session.commit()

    rolls = (
        SavedRoll(name='Bow', roll_str='d20 + 7, d8', user_id=dusers[0].id),
        SavedRoll(name='Staff', roll_str='d20 + 2, d6', user_id=dusers[0].id),
        SavedRoll(name='LongSword', roll_str='d20 + 7, d8+4', user_id=dusers[1].id),
    )
    session.add_all(rolls)
    session.commit()

    def mprint(*args):
        """ Padded print. """
        args = [str(x) for x in args]
        print(*args)

    pad = ' ' * 3

    print('DiscordUsers----------')
    for user in session.query(DUser):
        mprint(user)
        mprint(pad, user.rolls)

    print('SavedRolls----------')
    for roll in session.query(SavedRoll):
        mprint(roll)
        mprint(pad, roll.user)
    session.close()

    Base.metadata.drop_all(engine)


if __name__ == "__main__":  # pragma: no cover
    main()
