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
import os
import subprocess

import argh
import blessings
import yaml

import timetra.storage
import timetra.utils


t = blessings.Terminal()


CONF_FILE = os.getenv('TIMETRA_CONFIG', 'conf.yaml')
FACT_FORMAT = ('{since.year}-{since.month:0>2}-{since.day:0>2} '
               '{since.hour:0>2}:{since.minute:0>2}-'
               '{until.hour:0>2}:{until.minute:0>2} '
               '{activity} {duration} {description}')


def _init_storage():
    with open(CONF_FILE) as f:
        conf = yaml.load(f)
    backend = timetra.storage.YamlBackend(**conf['backend'])
    storage = timetra.storage.Storage(backend)
    return storage


storage = _init_storage()


def find(since=None, until=None, activity=None, note=None, tag=None,
         fmt=FACT_FORMAT):

    if since:
        since = datetime.datetime.strptime(since, '%Y-%m-%d')
    if until:
        until = datetime.datetime.strptime(until, '%Y-%m-%d')

    facts = storage.find(since=since, until=until, activity=activity,
                         description=note, tag=tag)
    for fact in facts:
        fact['activity'] = t.yellow(fact['activity'])
        # avoid "None" in textual representation
        fact['description'] = t.blue(fact['description'] or '')
        try:
            delta = fact['until'] - fact['since']
            fact['duration'] = '{:.0f}m'.format(delta.total_seconds() / 60)
        except:
            fact['duration'] = ''

        yield fmt.format(**fact)


def today():
    date = datetime.datetime.today().strftime('%Y-%m-%d')
    return find(since=date)


def yesterday():
    date = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return find(since=date)


def edit(date=None):
    if isinstance(date, (datetime.date, datetime.datetime)):
        pass
    elif date:
        date = datetime.datetime.strptime(date, '%Y-%m-%d')
    else:
        date = datetime.date.today()

    path = storage.backend.get_file_path_for_day(date)
    print('opening', path, 'in editor...')
    subprocess.Popen(['vim', path]).wait()
    print('editor finished.')


@argh.wrap_errors([AssertionError])
def add(activity, since, until=None, duration=None, note=None, tags=None,
        open_editor=False):
    if since == 'thru':
        prev = storage.get_latest()
        since = prev['until']
    else:
        since = timetra.utils.parse_time_to_datetime(since)

    if until:
        assert not duration
        until = timetra.utils.parse_time_to_datetime(until)
    elif duration:
        until = since + datetime.timedelta(minutes=int(duration))
    else:
        until = datetime.datetime.now()

    assert since < until, '--since must be earlier than --until'

    fact = {
        'activity': activity,
        'since': since,
        'until': until,
        'description': note,
        'tags': tags.split(',') if tags else [],
    }
    file_path = storage.add(fact)

    print('Added {} +{:.0f}m to {}'.format(since.strftime('%Y-%m-%d %H:%M'),
                                  (until - since).total_seconds() / 60,
                                  file_path))

    if open_editor:
        edit(since)


def main():
    p = argh.ArghParser()

    from timetra.reporting import Reporting
    from timetra.timer import Timing
    from timetra.curses import TUI
    #from timetra.cli_old import LegacyCLI

    reporting = Reporting({'storage': storage})
    timing = Timing({'storage': storage})
    tui = TUI({'storage': storage})
    #old_cli = LegacyCLI({'storage': storage})

    command_tree = {
        None:     [find, add, edit, today, yesterday],
        'report': [reporting.drift],
        'timing': [timing.pomodoro],
        'tui':    [tui.run],
        #'old':    old_cli.commands,
    }
    for namespace, commands in command_tree.items():
        p.add_commands(commands, namespace=namespace)

    p.dispatch()
