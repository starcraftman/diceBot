"""
Text matching functions.
"""


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
    start, end = substr_ind(seq, line)
    matched = line[start:end]
    return line.replace(matched, fmt.format(matched))


def emphasize_match_one(seq, line, fmt='__{}__'):
    """
    Emphasize the matched portion of string once.

    Went in a different direction, keeping for posterity.
    """
    prefix = fmt[:fmt.index('{')]
    search_line = line
    while substr_ind(seq, search_line):
        start, end = substr_ind(seq, search_line)
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
