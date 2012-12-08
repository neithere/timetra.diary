# -*- coding: utf-8 -*-
#
#    Timetra is a time tracking application and library.
#    Copyright © 2010-2012  Andrey Mikhaylenko
#
#    This file is part of Timetra.
#
#    Timetra is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Timetra is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Timer.  If not, see <http://gnu.org/licenses/>.
#
"""
Utility functions
=================
"""
import datetime


def format_delta(delta, fmt='{hours}:{minutes}'):
    """ Formats timedelta. Allowed variable names are: `days`, `hours`,
    `minutes`, `seconds`.
    """
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return fmt.format(days=delta.days, hours=hours, minutes=minutes,
                      seconds=seconds)


def split_time(string):
    """ Returns a pair of integers `(hours, minutes)` for given string::

        >>> _split_time('02:15')
        (2, 15)
        >>> _split_time('2:15')
        (2, 15)
        >>> _split_time(':15')
        (0, 15)
        >>> _split_time('15')
        (0, 15)

    """
    def _split(s):
        if ':' in s:
            return s.split(':')
        if len(s) <= 2:
            # "35" -> 00:35
            return 0, s
        return s[:-2], s[-2:]

    return tuple(int(x or 0) for x in _split(string))


def parse_time(string):
    """
    Returns a datetime.time object and a boolean that tells whether given time
    should be substracted from the start time.

        >>> parse_time('20')
        (time(0, 20), False)
        >>> parse_time('-1:35')
        (time(1, 35), True)
        >>> parse_time('now')
        datetime.now().time()
        >>> parse_time('now-5')
        datetime.now().time() - timedelta(minutes=5)

    """
    substract = False

    if string == 'now':
        return datetime.datetime.now().time(), substract

    if string.startswith('now-'):
        # "now-150"
        now = datetime.datetime.now()
        _, substring = string.split('-')
        delta, _ = parse_time(substring)
        start = now - datetime.timedelta(hours=delta.hour, minutes=delta.minute)
        return start.time(), substract

    if string.startswith('-'):
        # "-2:58"
        substract = True
        string = string[1:]

    hours, minutes = split_time(string)

    return datetime.time(hours, minutes), substract


def parse_time_to_datetime(string, relative_to=None, ensure_past_time=True):
    """ Parses string to a datetime, relative to given date (or current one):

    CURRENT FORMAT:
        12:05 = DATE, at 12:05
    TODO:
         1205 = DATE, at 12:05
          205 = DATE, at 02:05
           05 = DATE, at 00:05
            5 = DATE, at 00:05
           -5 = DATE - 5 minutes
    """
    if not string:
        return
    base_date = relative_to or datetime.datetime.now()
    parsed_time, _ = parse_time(string)
    date_time = datetime.datetime.combine(base_date, parsed_time)

    # microseconds are not important but may break the comparison below
    base_date = base_date.replace(microsecond=0)
    date_time = date_time.replace(microsecond=0)

    if ensure_past_time and base_date < date_time:
        return date_time - datetime.timedelta(days=1)
    else:
        return date_time


def parse_delta(string):
    """ Parses string to timedelta.
    """
    if not string:
        return
    hours, minutes = split_time(string)
    return datetime.timedelta(hours=hours, minutes=minutes)
