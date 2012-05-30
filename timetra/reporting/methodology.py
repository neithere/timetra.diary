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
Methodology
===========

:copyright: Andy Mikhaylenko, 2012
:license: LGPL3

"""
import datetime

from timetra import storage


def check_planning_after_sleep(facts):
    remainder = []
    after_sleep = None
    sleep_fact = None
    for f in reversed(facts):
        if f.activity == 'sleeping':
            sleep_fact = f
            after_sleep = reversed(remainder)
            break
        remainder.append(f)
    message = u'Please plan the day'
    category = 'warning'
    if sleep_fact:
        if 60 * 30 < (datetime.datetime.now() - sleep_fact.end_time).total_seconds():
            category = 'error'
    if after_sleep:
        if any(True for x in after_sleep if x.activity == 'sorting-tasks'):
            message = u'You seem to have planned the day, OK'
            category = 'success'
    return message, category


def analyse_day(date=None):
    """ Returns a generator or messages that give some hints re given day.
    """
    facts = storage.get_facts_for_day(date)
    rules = [check_planning_after_sleep]
    for rule in rules:
        yield rule(facts)
