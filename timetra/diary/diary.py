#!/usr/bin/env python
# coding: utf-8
# PYTHON_ARGCOMPLETE_OK
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
#    along with Timetra.  If not, see <http://gnu.org/licenses/>.
#
"""
~~~~~~~~~~~~~~~~~~~
Simple Diary Script
~~~~~~~~~~~~~~~~~~~

A simple temporary frontend for the YAML backend.

:author: Andrey Mikhaylenko

"""
import datetime
import subprocess

import argh
import blessings
from confu import Configurable

from .storage import Storage
from . import utils


t = blessings.Terminal()


FACT_FORMAT = ('{since.year}-{since.month:0>2}-{since.day:0>2} '
               '{since.hour:0>2}:{since.minute:0>2}-'
               '{until.hour:0>2}:{until.minute:0>2} '
               '{activity} {duration} {description}')
FISHY_FACT_DURATION_THRESHOLD = 6 * 60 * 60   # 6 hours is a lot


class Diary(Configurable):
    needs = {
        'storage': Storage,
    }

    def find(self, since=None, until=None, activity=None, note=None, tag=None,
             fmt=FACT_FORMAT, count=False):

        if since:
            since = datetime.datetime.strptime(since, '%Y-%m-%d')
        if until:
            until = datetime.datetime.strptime(until, '%Y-%m-%d')

        facts = self.storage.find(since=since, until=until, activity=activity,
                                  description=note, tag=tag)
        total_hours = 0
        for fact in facts:
            fact['activity'] = t.yellow(fact['activity'])
            # avoid "None" in textual representation
            fact['description'] = t.blue(fact['description'] or '')
            try:
                delta = fact['until'] - fact['since']
                fact['duration'] = '{:.0f}m'.format(delta.total_seconds() / 60)
                if count:
                    total_hours += delta.total_seconds() / 60. / 60.
            except:
                fact['duration'] = ''

            yield fmt.format(**fact)

        if count:
            yield ''
            yield 'TOTAL {:.1f}h'.format(total_hours)

    def today(self):
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        return self.find(since=date)

    def yesterday(self):
        date = datetime.datetime.today() - datetime.timedelta(days=1)
        return self.find(since=date.strftime('%Y-%m-%d'))

    def edit(self, date=None):
        if isinstance(date, (datetime.date, datetime.datetime)):
            pass
        elif date:
            date = datetime.datetime.strptime(date, '%Y-%m-%d')
        else:
            date = datetime.date.today()

        path = self.storage.backend.get_file_path_for_day(date)
        print('opening', path, 'in editor...')
        subprocess.Popen(['vim', path]).wait()
        print('editor finished.')

    @argh.wrap_errors([AssertionError])
    @argh.arg('note', nargs='*', default='')
    def add(self, when, what, tags=None, yes_to_all=False, *note):
        prev = self['storage'].get_latest()
        last = prev.until
        since, until = utils.parse_date_time_bounds(when, last)
        fact = {
            'activity': what,
            'since': since,
            'until': until,
            'description': ' '.join(note) if note else None,
            'tags': tags.split(',') if tags else [],
        }

        # sanity check
        delta_sec = (until - since).total_seconds()
        if not yes_to_all and FISHY_FACT_DURATION_THRESHOLD <= delta_sec:
            msg = 'Did you really {} for {:.1f}h'.format(what, delta_sec / 60 / 60.)
            if not argh.confirm(t.yellow(msg)):
                return t.red('CANCELLED')

        file_path = self.storage.add(fact)

        return ('Added {} +{:.0f}m to {}'.format(since.strftime('%Y-%m-%d %H:%M'),
                                                 delta_sec / 60,
                                                 file_path))
