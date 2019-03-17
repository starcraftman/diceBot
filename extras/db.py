"""
Backup the database extries that are important.
"""
import os
import sys

import dicedb
from dicedb.schema import DUser, Pun, SavedRoll, TurnChar, TurnOrder, Song, SongTag, DB_CLASSES

CUR_DIR = os.path.abspath(os.path.dirname(__file__))
if os.path.dirname(__file__) == '':
    CUR_DIR = os.getcwd()
WARNING = """
    STOP AND THINK! STOP AND THINK!

Proceeding has consequences for the above db ...

    Recreate all tables in the database (erasing existing data).
    Import into the db entries found in `extras/*.sql`.
    These backups should be verified by the user,
        the code within will be **EVAL**ed to make db objects.

    Continue? Y/n """.format(dicedb.engine)

try:
    input = raw_input
except NameError:
    pass


def db_dump(session, classes, file_template):
    """
    Dump all classes to their repr to a file of cls_name.sql in extras.
    """
    for cls in classes:
        fname = file_template.format(cls.__name__)
        objs = session.query(cls).all()

        if objs:
            print('Creating backup for {} at: {}'.format(cls, fname))
            with open(fname, 'w') as fout:
                for obj in objs:
                    fout.write(repr(obj) + '\n')
        else:
            print('No entries for {}, skipping: {}'.format(cls, fname))


def db_restore(session, classes, file_template):
    """
    Will recreate the tables (i.e. drop all data currently there).

    Then restore classes from dumps created by db_dump.
    """
    dicedb.schema.recreate_tables()
    for cls in classes:
        fname = file_template.format(cls.__name__)
        print('Restoring backup from:', fname)
        try:
            with open(fname, 'r') as fin:
                objs = [eval(line) for line in fin.readlines()]

            print('Restoring:')
            for obj in objs:
                print('    ' + repr(obj))

            session.add_all(objs)
            session.commit()
        except FileNotFoundError:
            print('No backup for {} found at: {}'.format(cls, fname))


def main():
    """ Main """
    session = dicedb.Session()

    try:
        prefix = sys.argv[2]
    except IndexError:
        prefix = ''
    file_template = os.path.join(CUR_DIR, prefix + '{}.sql')

    try:
        if sys.argv[1].lower()[0] == 'b':
            db_dump(session, DB_CLASSES, file_template)
        elif sys.argv[1].lower()[0] == 'r':
            resp = input(WARNING)
            print()
            if resp.lower()[0] == 'y':
                DB_CLASSES.reverse()
                db_restore(session, DB_CLASSES, file_template)
            else:
                print('aborting')
        else:
            raise IndexError
    except IndexError:
        mod = '.'.join([os.path.basename(os.path.dirname(sys.argv[0])),
                        os.path.basename(sys.argv[0].replace('.py', '')),
                        ])
        invoke = 'python -m ' + mod
        print('\nUsage:\n     {} backup|restore [file_prefix]'.format(invoke))


if __name__ == "__main__":
    main()
