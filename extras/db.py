"""
Backup the database extries that are important.
"""
import os
import sys

import dicedb
from dicedb.schema import DUser, SavedRoll

ALL_CLASSES = [SavedRoll, DUser]
CUR_DIR = os.path.abspath(os.path.dirname(__file__))
if os.path.dirname(__file__) == '':
    CUR_DIR = os.getcwd()

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
            for obj in objs:
                with open(fname, 'w') as fout:
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
                lines = fin.read()
            objs = [eval(line) for line in lines.split('\n')]

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
            db_dump(session, ALL_CLASSES, file_template)
        elif sys.argv[1].lower()[0] == 'r':
            resp = input('Warning: This will recreate tables and restore backups. Continue? Y/n ')
            if resp.lower()[0] == 'y':
                ALL_CLASSES.reverse()
                db_restore(session, ALL_CLASSES, file_template)
            else:
                print('aborting')
    except IndexError:
        print('Do: {} {}|{} [file_prefix]'.format(sys.argv[0], 'backup', 'restore'))


if __name__ == "__main__":
    main()
