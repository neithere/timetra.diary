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


class DriftData(dict):
    def __init__(self, span_days, end_time):
        for i in range(span_days):
            date = (end_time - timedelta(days=i)).date()
            self.ensure_date(date)

    def ensure_date(self, date):
        if date in self:
            return
        self[date] = {
            'marks': [MARKER_EMPTY for x in range(24)],
            'durations': [],
        }

    def add_fact(self, start_time, end_time):
        duration = end_time - start_time
        delta_sec = duration.total_seconds()
        delta_hour = delta_sec / 60 / 60
        # count each fact as 1+ hour long -- multiple facts within the same
        # hour will merge
        delta_hour_rounded = int(round(delta_hour)) or 1
        for hour in range(delta_hour_rounded):
            date_time = (end_time - timedelta(hours=hour))
            date = date_time.date()
            self.ensure_date(date)
            self[date]['marks'][date_time.hour] = MARKER_FACTS
            # FIXME 1 hour accuracy per chunk can result in an error of almost
            # 2 hours (e.g. a 2-minute event starts on 00:59 and ends on 01:01
            # which means two hour-long blocks involved)
            self[date]['durations'].append(1)
        # FIXME this is wrong:
        # facts that span dates are not handled properly
        #self[date]['durations'].append(delta_hour)

        # split the fact by dates
#        fact_dates = {}
#
#        for date, durations in fact_dates.iteritems():
#            self.ensure_date(date)
#            self[date]['durations'].extend(durations)

    def get_marks(self, date, mark_current_hour=True):
        now = datetime.now()
        for hour, mark in enumerate(self[date]['marks']):
            if mark_current_hour and date == now.date() and hour == now.hour:
                yield term.success(MARKER_NOW)
            else:
                yield mark

    def get_total_hours(self, date):
        return sum(x for x in self[date]['durations'])


def collect_drift_data(activity, span_days):
    span_days = span_days - 1  # otherwise it's zero-based
    until = datetime.now()
    since = until - timedelta(days=span_days)

    dates = DriftData(span_days, until)

    facts = storage.get_facts_for_day(since, end_date=until, search_terms=activity)
    for fact in facts:
#        tmpl = u'{time}  {fact.activity}@{fact.category} {tags} {fact.delta}'
#        print tmpl.format(
#            fact = fact,
#            tags = ' '.join(unicode(t) for t in fact.tags),
#            time = fact.start_time.strftime('%Y-%m-%d %H:%M'),
#        )
        dates.add_fact(fact.start_time, fact.end_time)

    return dates


def show_drift(activity='sleeping', span_days=7):
    dates = collect_drift_data(activity=activity, span_days=span_days)

    yield ''

    for date in sorted(dates):
        marks = dates.get_marks(date)
        hours_spent = dates.get_total_hours(date)
        context = {'date': date, 'marks': ''.join(marks), 'spent': hours_spent}
        yield u'{date} {marks} approx. {spent:>4.1f}'.format(**context)


if __name__ == '__main__':
    activity = sys.argv[1] if 1 < len(sys.argv) else 'sleeping'
    print '\n'.join([unicode(x) for x in show_drift(activity)])
