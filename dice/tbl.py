#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Any logic having to do with formatting an ASCII table.

String formatting reference:
  https://pyformat.info/#string_pad_align
"""
from __future__ import absolute_import, print_function


def wrap_markdown(text):
    """
    Wraps text in multiline markdown quotes.
    """
    return '```' + text + '```'


def max_col_width(lines):
    """
    Iterate all lines and entries.

    Returns: A list of numbers, the max width required for each
             column given the data.
    """
    lens = [[] for _ in lines[0]]

    for line in lines:
        for ind, data in enumerate(line):
            lens[ind].append(len(data))

    return [max(len_list) for len_list in lens]


def format_header(line, sep=' | ', pads=None, center=True):
    """
    Format a simple table header and return as string.
    """
    header = format_line(line, sep=sep, pads=pads, center=center)
    divider = format_line(['-' * pad for pad in pads], sep=sep)
    return header + '\n' + divider + '\n'


def format_table(lines, sep=' | ', center=False, header=False):
    """
    This function formats a table that fits all data evenly.
    It will go down columns and choose spacing that fits largest data.

    args:
        lines: Each top level element is a line composed of data in a list.
        sep: String to separate data with.
        center: Center the entry, otherwise left aligned.
        header: If true, format first line as pretty header.
    """
    # Guarantee all strings
    lines = [[str(data) for data in line] for line in lines]

    pads = max_col_width(lines)

    if header:
        header, lines = lines[0], lines[1:]
        ret_line = format_header(header, sep=sep, pads=pads, center=True)
    else:
        ret_line = ''

    for line in lines:
        ret_line += format_line(line, sep=sep, pads=pads, center=center) + '\n'

    return ret_line[:-1]


def format_line(entries, sep=' | ', pads=None, center=False):
    """
    Format data for use in a simple table output to text.

    args:
        entries: List of data to put in table, left to right.
        sep: String to separate data with.
        pad: List of numbers, pad each entry as you go with this number.
        center: Center the entry, otherwise left aligned.
    """
    line = ''
    align = '^' if center else ''

    if pads:
        pads = [align + str(pad) for pad in pads]
    else:
        pads = [align for ent in entries]

    ents = []
    for ind, ent in enumerate(entries):
        fmt = "{:" + str(pads[ind]) + "}"
        ents += [fmt.format(str(ent))]

    line = sep.join(ents)

    return line.rstrip()
