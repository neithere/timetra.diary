# -*- coding: utf-8 -*-
#
#    Timetra is a time tracking application and library.
#    Copyright © 2010-2014  Andrey Mikhaylenko
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
from datetime import date, datetime, time, timedelta
import re


try:
    basestring
except NameError:
    # Python3
    basestring = str


def to_date(obj):
    if isinstance(obj, datetime):
        return obj.date()
    if isinstance(obj, date):
        return obj
    raise TypeError('expected date or datetime, got {0}'.format(obj))


def to_datetime(obj):
    if isinstance(obj, datetime):
        return obj
    if isinstance(obj, date):
        return datetime.combine(obj, time(0))
    raise TypeError('expected date or datetime, got {0}'.format(obj))



# TODO: use  https://bitbucket.org/russellballestrini/ago/src
#        or  https://github.com/tantalor/pretty_timedelta

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


def parse_date(string):
    """
    Expects a date string in ``YYYY-MM-DD`` format.
    Returns a corresponding `datetime.date` object.
    """
    return datetime.strptime(string, '%Y-%m-%d').date()


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
        return datetime.now().time(), substract

    if string.startswith('now-'):
        # "now-150"
        now = datetime.now()
        _, substring = string.split('-')
        delta, _ = parse_time(substring)
        start = now - timedelta(hours=delta.hour, minutes=delta.minute)
        return start.time(), substract

    if string.startswith('-'):
        # "-2:58"
        substract = True
        string = string[1:]

    hours, minutes = split_time(string)

    return time(hours, minutes), substract


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
    base_date = relative_to or datetime.now()
    parsed_time, _ = parse_time(string)
    date_time = datetime.combine(base_date, parsed_time)

    # microseconds are not important but may break the comparison below
    base_date = base_date.replace(microsecond=0)
    date_time = date_time.replace(microsecond=0)

    if ensure_past_time and base_date < date_time:
        return date_time - timedelta(days=1)
    else:
        return date_time


def parse_delta(string):
    """ Parses string to timedelta.
    """
    if not string:
        return
    hours, minutes = split_time(string)
    return timedelta(hours=hours, minutes=minutes)


def extract_date_time_bounds(spec):
    spec = spec.strip()
    rx_time = r'[0-9]{0,2}:?[0-9]{1,2}'
    rx_rel = r'[+-]\d+'
    rx_component = r'{time}|{rel}'.format(time=rx_time, rel=rx_rel)
    rx_separator = r'\.\.'
    rxs = tuple(re.compile(x) for x in [
        # all normal cases
        r'^(?P<since>{component}){sep}(?P<until>{component})$'.format(
            component=rx_component, sep=rx_separator),
        # since last until given
        r'^\.\.(?P<until>{component})$'.format(component=rx_component),
        # since given until now
        r'^(?P<since>{component})\.\.$'.format(component=rx_component),
        # since last until now
        r'^(\.\.|)$'.format(time=rx_time),
        # ultrashortcut "1230+5"
        r'^(?P<since>{time})(?P<until>\+\d+)$'.format(time=rx_time),
        # ultrashortcut "+5" / "-5"
        r'^(?P<since>{rel})$'.format(rel=rx_rel),
    ])
    for rx in rxs:
        match = rx.match(spec)
        if match:
            return match.groupdict()
    raise ValueError(u'Could not parse "{}" to time bounds '.format(spec))


def string_to_time_or_delta(value):
    if value is None:
        return None

    assert isinstance(value, basestring)

    if value.startswith(('+', '-')):
        hours, minutes = split_time(value[1:])
        assert minutes <= 60
        delta = timedelta(hours=hours, minutes=minutes)
        return delta if value[0] == '+' else -delta
    else:
        hours, minutes = split_time(value)
        return time(hour=hours, minute=minutes)


def round_fwd(time):
    if not time.second and not time.microsecond:
        return time

    if time.microsecond:
        time += timedelta(seconds=+1, microseconds=-time.microsecond)

    if time.second:
        if time.second <= 30:
            time += timedelta(seconds=30-time.second)
        else:
            time += timedelta(seconds=60-time.second)

    return time


def _normalize_since(last, since, now):
    if isinstance(since, datetime):
        return since

    if isinstance(since, time):
        if since < now.time():
            # e.g. since 20:00, now is 20:30, makes sense
            reftime = round_fwd(now)
        else:
            # e.g. since 20:50, now is 20:30 → can't be today;
            # probably yesterday (allowing earlier dates can be confusing)
            reftime = round_fwd(now) - timedelta(days=1)
        return reftime.replace(hour=since.hour, minute=since.minute, second=0, microsecond=0)

    if isinstance(since, timedelta):
        # relative...
        if since.total_seconds() < 0:
            # ...to `until`
            #
            # "-5..until" → "{until-5}..until"; `until` is not normalized yet
            return since    # unchanged timedelta
        else:
            # ...to `last`
            #
            # "+5.." → "{last+5}.."; `last` is already known
            return round_fwd(last) + since

    raise TypeError('since')


def _normalize_until(last, until, now):

    if isinstance(until, datetime):
        return until

    if isinstance(until, time):
        if until < now.time():
            # e.g. until 20:00, now is 20:30, makes sense
            reftime = round_fwd(now)
        else:
            # e.g. until 20:50, now is 20:30 → can't be today;
            # probably yesterday (allowing earlier dates can be confusing)
            reftime = round_fwd(now) - timedelta(days=1)
        return reftime.replace(hour=until.hour, minute=until.minute, second=0, microsecond=0)

    if isinstance(until, timedelta):
        # relative...
        if until.total_seconds() < 0:
            # ...to `now`
            #
            # "since..-5" → "since..{now-5}"; `now` is already known
            return round_fwd(now) + until
        else:
            # ...to `since`
            #
            # "since..+5" → "since..{since+5}"; `since` is not normalized yet
            # (or it is but we want to keep the code refactoring-friendly)
            return until    # unchanged timedelta

    raise TypeError('until')


def normalize_group(last, since, until, now):
    assert since or last
    assert until or now

    if since is None:
        # NOTE: "if not since" won't work for "00:00"
        # because `bool(time(0,0)) == False`
        since = round_fwd(last)
    if until is None:
        until = now

    # since
    since = _normalize_since(last, since, now)
    #if isinstance(since, datetime):
    #    # XXX TODO this should be only raised in some special circumstances
    #    # it's not a good idea to prevent adding facts between existing ones
    #    # so an overlapping check would be a good idea (but on a later stage)
    #    assert last <= since, 'since ({}) must be ≥ last ({})'.format(since, last)

    # until
    until = _normalize_until(last, until, now)
    if isinstance(until, datetime):
        assert until <= now, 'until ({}) must be ≤ now ({})'.format(until, now)

    # some components could not be normalized individually

    if isinstance(since, timedelta) and isinstance(until, timedelta):
        # "-10..+5" → "{now-10}..{since+5}"
        assert since.total_seconds() < 0
        assert until.total_seconds() >= 0
        since = round_fwd(now + since)    # actually: now -since
        until = since + until
    elif isinstance(since, timedelta):
        # "-5..21:30" → "{until-5}..21:30"
        assert since.total_seconds() < 0
        since = round_fwd(until + since)    # actually: until -since
    elif isinstance(until, timedelta):
        # "21:30..+5" → "21:30..{since+5}"
        assert until.total_seconds() >= 0
        until = since + until

    assert since < until, 'since ({}) must be < until ({})'.format(since, until)

    return since, until


def parse_date_time_bounds(spec, last, now=None):
    groups = extract_date_time_bounds(spec)

    raw_since = groups.get('since')
    raw_until = groups.get('until')

    since = string_to_time_or_delta(raw_since)
    until = string_to_time_or_delta(raw_until)

    if not now:
        now = datetime.now()

    return normalize_group(last, since, until, now)
