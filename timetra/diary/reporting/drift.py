#!/usr/bin/env python2
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
Displays daily activity drift.

:copyright: Andy Mikhaylenko, 2012—2015
:license: LGPL3
"""
import math
from datetime import datetime, timedelta

from colorclass import Color
from terminaltables import SingleTable

from .. import utils


MARKER_EMPTY = '‧'
MARKER_FACTS = '■'
MARKER_NOW = '▹'  #'◉'  #'◗'
MARKER_NOW = '{autored}' + MARKER_NOW + '{/autored}'

WEEKDAYS = (
    'Mo',
    'Tu',
    'We',
    'Th',
    'Fr',
    '{autored}Sa{/autored}',
    '{autored}Su{/autored}',
)

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

    def __str__(self):
        if self.is_current:
            return MARKER_NOW
        if timedelta(minutes=MIN_HOURLY_DURATION) < self.duration:
            return MARKER_FACTS
        return MARKER_EMPTY

    def __unicode__(self):
        return str(self)

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
        self.fact_cnt = 0
        self.min_start = None
        self.max_end = None

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
        date = start_time.date()
        pos = start_time.replace(minute=0, second=0, microsecond=0)
        while pos <= end_time:
            date = pos.date()
            self.ensure_date(date)
            if pos < start_time:
                # the fact starts somewhere between the edges
                right_edge = pos + timedelta(hours=1)
                if end_time <= right_edge:
                    # the fact completely fits this box
                    duration = end_time - start_time
                else:
                    # the fact overlaps the right edge
                    duration = right_edge - start_time
            else:
                # fact starts exactly at the hour edge
                duration = timedelta(hours=1)
                if end_time < pos + duration:
                    duration = end_time - pos
            self[date][pos.hour].duration += duration
            pos += timedelta(hours=1)

        day = self[date]
        day.fact_cnt += 1
        if not day.min_start or start_time < day.min_start:
            day.min_start = start_time
        if not day.max_end or day.max_end < end_time:
            if start_time.date() == end_time.date():
                day.max_end = end_time
            else:
                day.max_end = start_time.replace(
                    hour=23, minute=59, second=59, microsecond=0)


def collect_drift_data(storage, activity, span_days):
    span_days = span_days - 1  # otherwise it's zero-based
    until = datetime.now()
    since = until - timedelta(days=span_days)

    dates = DriftData(span_days, until)

    facts = storage.find(since, until=until, activity=activity)
    for fact in facts:
        dates.add_fact(fact.since, fact.until)

    return dates


def show_drift(storage, activity, days=7, shift=False):
    """Displays hourly chart for given activity for a number of days.
    Primary use: evaluate regularity of certain activity, detect deviations,
    trends, cycles. Initial intention was to find out my sleeping drift.
    """
    dates = collect_drift_data(storage, activity=activity, span_days=days)


    fields = [
        'date',
        'wd',
        'hourly drift',
        'total',
        'total graph',
    ]
    if shift:
        # diffs against previous day
        fields += ['qt', 'start', 'end']

    # prettytable would break if we appended items directly to this attr

    data = [fields]

    prev_day = None

    for date in sorted(dates):
        marks = dates[date]
        day = dates[date]
        spent = utils.format_delta(day.duration,
                                   fmt='{hours}:{minutes:0>2}')
        spent_graph = MARKER_FACTS * int(round(day.duration.total_seconds() / 60 / 60))

        if shift:
            shift_cnt = None
            shift_cnt_msg = shift_start_msg = shift_end_msg = ''
            if prev_day:
                shift_cnt = day.fact_cnt - prev_day.fact_cnt or ''
                if shift_cnt:
                    char = '+' if 0 < shift_cnt else '-'
                    shift_cnt_msg = char * int(math.copysign(shift_cnt, 1))

                shift_start_msg = get_shift_msg(day.min_start, prev_day.min_start)
                shift_end_msg = get_shift_msg(day.max_end, prev_day.max_end)

            shift_cells = [
                shift_cnt_msg,
                shift_start_msg or '',
                shift_end_msg or '',
            ]
        else:
            shift_cells = []

        row = [
            str(date),
            WEEKDAYS[date.weekday()],
            Color(''.join((str(m) for m in marks))),
            spent,
            spent_graph,
        ] + shift_cells
        data.append([Color(cell) for cell in row])

        prev_day = day

    table = SingleTable(data, 'Daily Activity Drift')
    return table.table


def show_weekly_averages(storage, activity, weeks=4):

    # TODO: option: always start with Monday -> incomplete last week

    dates = collect_drift_data(storage, activity=activity, span_days=7*weeks)


    fields = ['since', 'until', 'avg', 'total', 'days']

    # prettytable would break if we appended items directly to this attr

    #table.align['total graph'] = 'l'

    data = []

    data.append(fields)


    since = None
    spent = timedelta()
    collected = 0
    for date in sorted(dates):
        if not since:
            since = date
        #print(dates[date])
        #marks = dates[date]
        #day = dates[date]


        collected += 1
        spent += dates[date].duration
        if collected >= 7 or date == sorted(dates)[-1]:
            avg = spent / collected
            avg_fmt = utils.format_delta(avg, fmt='{hours}h {minutes:0>2}m')
            spent_fmt = utils.format_delta(spent, fmt='{days}d {hours}h {minutes:0>2}m')

            data.append([str(x) for x in (since, date, avg_fmt, spent_fmt, collected)])

            since = None
            spent = timedelta()
            collected = 0
    else:
        print('remainder?')

    table = SingleTable(data)
    return table.table


def get_shift_msg(dt1, dt2):
    if not dt1 or not dt2:
        return

    # we only need to compare time, not days
    dt2 = datetime.combine(dt1.date(), dt2.time())

    if dt1 < dt2:
        dt1, dt2 = dt2, dt1
        char = '◂'
    else:
        char = '▸'

    delta = dt1 - dt2

    if not delta:
        return

    delta_formatted = char * int(round(delta.total_seconds() // 60 / 60))
    return delta_formatted
