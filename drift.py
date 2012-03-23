#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Displays daily activity drift.

:copyright: Andy Mikhaylenko, 2012
:license: LGPL3
"""
import sys
from datetime import datetime, timedelta

import timer


MARKER_EMPTY = '‧'
MARKER_FACTS = '■'
MARKER_NOW = '◗'


class DriftData(dict):
    def __init__(self, span_days, end_time):
        for i in range(span_days):
            date = (end_time - timedelta(days=i)).date()
            self.prepopulate_date(date)

    def prepopulate_date(self, date):
        self[date] = [MARKER_EMPTY for x in range(24)]

    def add_fact(self, start_time, end_time):
        duration = end_time - start_time
        delta_sec = duration.total_seconds()
        # count each fact as 1+ hour long -- multiple facts within the same
        # hour will merge
        delta_hour = int(round(delta_sec / 60 / 60)) or 1
        for hour in range(delta_hour):
            date_time = (end_time - timedelta(hours=hour))
            date = date_time.date()
            if date not in self:
                self.prepopulate_date(date)
            self[date][date_time.hour] = MARKER_FACTS


def collect_drift_data(activity, span_days):
    span_days = span_days - 1  # otherwise it's zero-based
    until = datetime.now()
    since = until - timedelta(days=span_days)

    dates = DriftData(span_days, until)

    facts = timer.get_facts_for_day(since, end_date=until, search_terms=activity)
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

    now = datetime.now()
    for date in sorted(dates):
        marks = []
        for hour, mark in enumerate(dates[date]):
            if date == now.date() and hour == now.hour:
                mark = MARKER_NOW #if mark == MARKER_EMPTY else mark
                mark = timer.COLOR_GREEN + mark + timer.COLOR_ENDC
            marks.append(mark)

        context = {'date': date, 'marks': ''.join(marks)}
        yield u'{date} {marks}'.format(**context)


if __name__ == '__main__':
    activity = sys.argv[1] if 1 < len(sys.argv) else 'sleeping'
    print '\n'.join([unicode(x) for x in show_drift(activity)])
