#!/usr/bin/env python2
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
Displays daily activity drift.

:copyright: Andy Mikhaylenko, 2012
:license: LGPL3
"""
import sys
from datetime import datetime, timedelta

from timetra import storage, term


MARKER_EMPTY = '‧'
MARKER_FACTS = '■'
MARKER_NOW = '◗'

MIN_HOURLY_DURATION = 10
""" Minimum duration (in minutes) per hour. If the total duration of an
activity within given hour-long period is lower than this threshold, such
period is considered empty in regard to given activity.

.. note::

   "Within an hour-long period" != "within an hour".
   If a fact is split between two periods, it may disappear from results even
   if its total length exceeds the threshold.

"""


class HourData(object):
    def __init__(self, date, hour):
        self.date = date
        self.hour = hour
        self.duration = timedelta()

    def __repr__(self):
        return ('<{0.__class__.__name__} {0.date} '
                '{0.hour}h ({0.duration})>').format(self)

    def __unicode__(self):
        if self.is_current:
            return MARKER_NOW
        if timedelta(minutes=MIN_HOURLY_DURATION) < self.duration:
            return MARKER_FACTS
        return MARKER_EMPTY

    @property
    def is_current(self):
        now = datetime.now()
        if self.date == now.date() and self.hour == now.hour:
            return True
        else:
            return False


class DayData(list):
    "A list of hours (0..23) within a certain date."
    def __init__(self, date):
        self.date = date
        self[:] = [HourData(date, x) for x in range(24)]

    @property
    def duration(self):
        hourly_durations = (x.duration for x in self)
        return sum(hourly_durations, timedelta())


class DriftData(dict):
    def __init__(self, span_days, end_time):
        for i in range(span_days):
            date = (end_time - timedelta(days=i)).date()
            self.ensure_date(date)

    def ensure_date(self, date):
        if date in self:
            return
        self[date] = DayData(date)

    def add_fact(self, start_time, end_time):
        pos = start_time.replace(minute=0, second=0, microsecond=0)
        while pos <= end_time:
            date = pos.date()
            self.ensure_date(date)
            if pos < start_time:
                duration = pos + timedelta(hours=1) - start_time
            else:
                duration = timedelta(hours=1)
                if end_time < pos + duration:
                    duration = end_time - pos
            self[date][pos.hour].duration += duration
            pos += timedelta(hours=1)


def collect_drift_data(activity, span_days):
    span_days = span_days - 1  # otherwise it's zero-based
    until = datetime.now()
    since = until - timedelta(days=span_days)

    dates = DriftData(span_days, until)

    facts = storage.get_facts_for_day(since, end_date=until, search_terms=activity)
    for fact in facts:
        dates.add_fact(fact.start_time, fact.end_time)

    return dates


def show_drift(activity='sleeping', span_days=7):
    dates = collect_drift_data(activity=activity, span_days=span_days)

    yield ''

    for date in sorted(dates):
        marks = dates[date]
        marks = (term.success(m) if unicode(m) == MARKER_NOW else m
                 for m in marks)
        hours_spent = dates[date].duration
        context = {'date': date,
                   'marks': ''.join((unicode(m) for m in marks)),
                   'spent': hours_spent}
        yield u'{date} {marks} {spent:>8}'.format(**context)


if __name__ == '__main__':
    activity = sys.argv[1] if 1 < len(sys.argv) else 'sleeping'
    print '\n'.join([unicode(x) for x in show_drift(activity)])
