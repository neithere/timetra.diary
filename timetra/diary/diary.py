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
               '{activity} {duration} {description} '
               '{with_ppl}')
FISHY_FACT_DURATION_THRESHOLD = 6 * 60 * 60   # 6 hours is a lot


class Diary(Configurable):
    needs = {
        'storage': Storage,
    }

    @property
    def commands(self):
        """
        Returns the list of this object's methods that should be exposed
        as CLI commands.
        """
        return [
            self.find, self.add, self.edit, self.today, self.yesterday,
            self.insert, self.list_activities,
        ]

    def _collect_activities(self):
        """
        Returns a dictionary with all known activities defined in facts
        of current storage as keys, and the number of relevant facts as
        values.
        """
        # TODO: cache results and only scan the whole storage if forced
        xs = {}
        for x in self.storage.find():
            if 'activity' not in x:
                continue
            activity = x['activity']
            xs[activity] = xs.get(activity, 0) + 1
        return xs

    def find(self, when=None, days=0, since=None, until=None, activity=None,
             note=None, tag=None, fmt=FACT_FORMAT, count=False):

        if since:
            since = utils.parse_date(since)
        if until:
            until = utils.parse_date(until)

        if days:
            assert not since, '--days replaces --since'
            since = datetime.datetime.now() - datetime.timedelta(days=days)

        if when:
            assert not any([since, until, days]), \
                '--date replaces --since/--until/--days'
            since = utils.parse_date(when)
            until = utils.parse_date(when)

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

            with_ppl_tags = [tag[5:] for tag in fact.get('tags',[])
                             if tag.startswith('with-')]
            if with_ppl_tags:
                with_ppl = t.blue('😊 '+' & '.join(with_ppl_tags))
            else:
                with_ppl = ''

            yield fmt.format(with_ppl=with_ppl, **fact)

        if count:
            yield ''
            yield 'TOTAL {:.1f}h'.format(total_hours)

    def today(self, activity=None, count=False):
        kwargs = {
            'since': datetime.datetime.today().strftime('%Y-%m-%d'),
        }
        if activity:
            kwargs.update(activity=activity)
        if count:
            kwargs.update(count=count)
        return self.find(**kwargs)

    def yesterday(self):
        date = datetime.datetime.today() - datetime.timedelta(days=1)
        return self.find(since=date.strftime('%Y-%m-%d'))

    def edit(self, date=None):
        if isinstance(date, (datetime.date, datetime.datetime)):
            pass
        elif date:
            date = utils.parse_date(date)
        else:
            date = datetime.date.today()

        path = self.storage.backend.get_file_path_for_day(date)
        print('opening', path, 'in editor...')
        subprocess.Popen(['vim', path]).wait()
        print('editor finished.')


    def _validate_activity_interactively(self, pattern):
        known_activities = self._collect_activities()
        if pattern in known_activities:
            return pattern
        candidates = [x for x in known_activities if pattern in x]
        if len(candidates) == 1:
            candidate = candidates[0]
            if argh.confirm('Did you mean {}'.format(t.yellow(candidate))):
                return candidate
        elif candidates:
            print('You probably mean one of these:\n * {}'.format('\n * '.join(candidates)))

        if argh.confirm('Add {} as a new kind of activity'
                        .format(t.red(pattern))):
            return pattern
        return None

    @argh.wrap_errors([AssertionError])
    @argh.arg('note', nargs='*', default='')
    def add(self, when, what, tags=None, yes_to_all=False, *note):
        """
        Adds a fact somewhere near the end of the timeline.
        """
        what = self._validate_activity_interactively(what)
        if not what:
            return t.red('CANCELLED')

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

    @argh.arg('note', nargs='*', default='')
    def insert(self, date, when, what, tags=None, yes_to_all=False, *note):
        """
        Inserts a fact starting on given date.  Different from `add` in that
        it seeks a gap in existing facts instead of relating to the tail of the
        timeline.

        The timespec is also interpreted in a specific manner:

        * instead of the previous fact's end, given `date` is used at 00:00;
        * instead of `now`, the date next to given one is used at 00:00.

        After the `since` and `until` are obtained from the parser, the storage
        is checked for overlapping facts.  If they exist, the user is asked for
        confirmation.
        """
        date_parsed = utils.parse_date(date)
        date_time = datetime.datetime.combine(date_parsed, datetime.time())
        now = date_time + datetime.timedelta(days=1)
        last = date_time
        since, until = utils.parse_date_time_bounds(when, last, now=now)
        fact = {
            'activity': what,
            'since': since,
            'until': until,
            'description': ' '.join(note) if note else None,
            'tags': tags.split(',') if tags else [],
        }

        delta_sec = (until - since).total_seconds()

        ## sanity checks:

        # 1. ask for confirmation if the fact duration is over a threshold
        # (XXX code copied and pasted from add(), refactoring needed)
        if not yes_to_all and FISHY_FACT_DURATION_THRESHOLD <= delta_sec:
            msg = 'Did you really {} for {:.1f}h'.format(what, delta_sec / 60 / 60.)
            if not argh.confirm(t.yellow(msg)):
                return t.red('CANCELLED')

        # 2. search for overlapping facts (incl. prev or next day if the newly
        #    created fact doesn't fit one day)
        overlaps = list(self.storage.find_overlapping_facts(since, until))
        if overlaps:
            _item_tmpl = '{f.since} +{f.duration} {f.activity}'
            _items = '\n* '.join(_item_tmpl.format(f=f) for f in overlaps)
            msg = ('This fact would overlap {} existing records:\n* {}\n'
                   'Are you sure to add it'.format(len(overlaps), _items))
            if not argh.confirm(t.yellow(msg)):
                return t.red('CANCELLED')

        file_path = self.storage.add(fact)

        return ('Added {} +{:.0f}m to {}'.format(since.strftime('%Y-%m-%d %H:%M'),
                                                 delta_sec / 60,
                                                 file_path))

    def list_activities(self):
        for k, v in sorted(self._collect_activities().items(),
                           key=lambda kv: kv[1],
                           reverse=True):
            yield '{:>5}× {}'.format(v, k)
