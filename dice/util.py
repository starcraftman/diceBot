"""
Utility functions, mainly matching now.
"""
from __future__ import absolute_import, print_function
import datetime
import logging
import logging.handlers
import logging.config
import os
import math
import random

import numpy.random
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import dice.exc

BOT = None
MSG_LIMIT = 1985  # Number chars before message truncation


class ModFormatter(logging.Formatter):
    """
    Add a relmod key to record dict.
    This key tracks a module relative this project' root.
    """
    def format(self, record):
        relmod = record.__dict__['pathname'].replace(ROOT_DIR + os.path.sep, '')
        record.__dict__['relmod'] = relmod[:-3]
        return super().format(record)


def substr_match(seq, line, *, skip_spaces=True, ignore_case=True):
    """
    True iff the substr is present in string. Ignore spaces and optionally case.
    """
    return substr_ind(seq, line, skip_spaces=skip_spaces,
                      ignore_case=ignore_case) != []


def substr_ind(seq, line, *, skip_spaces=True, ignore_case=True):
    """
    Return the start and end + 1 index of a substring match of seq to line.

    Returns:
        [start, end + 1] if needle found in line
        [] if needle not found in line
    """
    if ignore_case:
        seq = seq.lower()
        line = line.lower()

    if skip_spaces:
        seq = seq.replace(' ', '')

    start = None
    count = 0
    for ind, char in enumerate(line):
        if skip_spaces and char == ' ':
            continue

        if char == seq[count]:
            if count == 0:
                start = ind
            count += 1
        else:
            count = 0
            start = None

        if count == len(seq):
            return [start, ind + 1]

    return []


def emphasize_match(seq, line, fmt='__{}__'):
    """
    Emphasize the matched portion of string.
    """
    start, end = dice.util.substr_ind(seq, line)
    matched = line[start:end]
    return line.replace(matched, fmt.format(matched))


def emphasize_match_one(seq, line, fmt='__{}__'):
    """
    Emphasize the matched portion of string once.

    Went in a different direction, keeping for posterity.
    """
    prefix = fmt[:fmt.index('{')]
    search_line = line
    while dice.util.substr_ind(seq, search_line):
        start, end = dice.util.substr_ind(seq, search_line)
        if line[start - len(prefix):end] == prefix + line[start:end]:
            search_line = search_line[end:]
            continue
        else:
            break

    offset = len(line) - len(search_line)
    start += offset
    end += offset
    line = line[:start] + fmt.format(seq) + line[end:]

    return line


def rel_to_abs(*path_parts):
    """
    Convert an internally relative path to an absolute one.
    """
    return os.path.join(ROOT_DIR, *path_parts)


def get_config(*keys):
    """
    Return keys straight from yaml config.
    """
    try:
        with open(YAML_FILE) as fin:
            conf = yaml.load(fin, Loader=Loader)
    except FileNotFoundError:
        raise dice.exc.MissingConfigFile("Missing config.yml. Expected at: " + YAML_FILE)

    for key in keys:
        conf = conf[key]

    return conf


def init_logging():  # pragma: no cover
    """
    Initialize project wide logging. See config file for details and reference on module.

     - On every start the file logs are rolled over.
     - This must be the first invocation on startup to set up logging.
    """
    log_file = rel_to_abs(get_config('paths', 'log_conf'))
    try:
        with open(log_file) as fin:
            lconf = yaml.load(fin, Loader=Loader)
    except FileNotFoundError:
        raise dice.exc.MissingConfigFile("Missing log.yml. Expected at: " + log_file)

    for handler in lconf['handlers']:
        try:
            os.makedirs(os.path.dirname(lconf['handlers'][handler]['filename']))
        except (OSError, KeyError):
            pass

    with open(log_file) as fin:
        logging.config.dictConfig(yaml.load(fin, Loader=Loader))

    print('See main.log for general traces.')
    print('Enabled rotating file logs:')
    for top_log in ('asyncio', 'dice'):
        for handler in logging.getLogger(top_log).handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                print('    ' + handler.baseFilename)
                handler.doRollover()

    # Can't configure discord without cloberring existing, so manually setting
    dice_rot = logging.getLogger('dice').handlers[0]
    rhand_file = os.path.join(os.path.dirname(dice_rot.baseFilename), 'discord.log')
    handler = logging.handlers.RotatingFileHandler(filename=rhand_file, encoding=dice_rot.encoding,
                                                   backupCount=dice_rot.backupCount,
                                                   maxBytes=dice_rot.maxBytes)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(dice_rot.formatter)
    print('    ' + handler.baseFilename)

    dlog = logging.getLogger('discord')
    dlog.setLevel(logging.DEBUG)
    dlog.addHandler(handler)
    dlog.addHandler(logging.getLogger('dice').handlers[-1])


def dict_to_columns(data):
    """
    Transform the dict into columnar form with keys as column headers.
    """
    lines = []
    header = []

    for col, key in enumerate(sorted(data)):
        header.append('{} ({})'.format(key, len(data[key])))

        for row, item in enumerate(data[key]):
            try:
                lines[row]
            except IndexError:
                lines.append([])
            while len(lines[row]) != col:
                lines[row].append('')
            lines[row].append(item)

    return [header] + lines


def complete_blocks(parts):
    """
    Take a list of message parts, complete code blocks as needed to
    preserve intended formatting.

    Returns:
        List of messages that have been modified.
    """
    new_parts = []
    incomplete = False
    block = "```"

    for part in parts:
        num_blocks = part.count(block) % 2
        if incomplete and not num_blocks:
            part = block + part + block

        elif incomplete and num_blocks:
            part = block + part
            incomplete = not incomplete

        elif num_blocks:
            part = part + block
            incomplete = not incomplete

        new_parts += [part]

    return new_parts


def msg_splitter(msg):
    """
    Take a msg of arbitrary length and split it into parts that respect discord 2k char limit.

    Returns:
        List of messages to send in order.
    """
    parts = []
    part_line = ''

    for line in msg.split("\n"):
        line = line + "\n"

        if len(part_line) + len(line) > MSG_LIMIT:
            parts += [part_line.rstrip("\n")]
            part_line = line
        else:
            part_line += line

    if part_line:
        parts += [part_line.rstrip("\n")]

    return parts


def load_yaml(fname):
    """
    Load a yaml file and return the dict. If not found, return an empty {}.
    Does not raise any possible exception.

    Returns: A dict object.
    """
    try:
        with open(fname) as fin:
            obj = yaml.load(fin, Loader=Loader)
    except FileNotFoundError:
        obj = {}

    return obj


def write_yaml(fname, obj):
    """
    Save a dictionary to a yaml file.

    Raises:
        OSError - Something prevented saving the file.
    """
    with open(fname, 'w') as fout:
        yaml.dump(obj, fout, Dumper=Dumper, encoding='UTF-8', indent=2,
                  explicit_start=True, default_flow_style=False)


def seed_random(seed=None):
    """
    Seed random library and numpy.random with a common seed.

    Args:
        seed: The seed to used, if not passed derive from timestamp.
    """
    if not seed:
        now = datetime.datetime.utcnow().timestamp()
        seconds = int(math.floor(now))
        micro = int((now - seconds) * 1000000)

        if micro > 500000:
            seconds -= micro
        else:
            seconds += micro
        seed = seconds

    numpy.random.seed(seed)
    random.seed(seed)

    return seed


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAML_FILE = rel_to_abs('data', 'config.yml')
