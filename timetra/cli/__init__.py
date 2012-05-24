#!/usr/bin/env python
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
#    along with Timetra.  If not, see <http://gnu.org/licenses/>.
#
"""
======================
Command-Line Interface
======================

:author: Andrey Mikhaylenko

"""
from argh import alias, arg, confirm, ArghParser
import datetime

from timetra.reporting import drift
from timetra.term import success, warning, failure
from timetra import storage, timer, utils


HAMSTER_TAG = 'auto-timed'
HAMSTER_TAG_LOG = 'auto-logged'


@arg('periods', nargs='+')
@arg('--silent', default=False)
def cycle(args):
    timer._cycle(*[timer.Period(x, silent=args.silent) for x in args.periods])


@arg('periods', nargs='+')
@arg('--silent', default=False)
def once(args):
    timer._once(*[timer.Period(x, silent=args.silent) for x in args.periods])


@arg('activity', default='work')
@arg('--silent', default=False)
@arg('-w', '--work-duration', default=30, help='period length in minutes')
@arg('-r', '--rest-duration', default=10, help='period length in minutes')
@arg('-d', '--description', default='', help='description for work periods')
def pomodoro(args):
    yield 'Running Pomodoro timer'
    work_activity, work_category = storage.parse_activity(args.activity)
    tags = ['pomodoro', HAMSTER_TAG]

    work = timer.Period(args.work_duration, name=work_activity,
                        category_name=work_category, hamsterable=True,
                        tags=tags, silent=args.silent,
                        description=args.description)
    relax = timer.Period(args.rest_duration, name='relax', hamsterable=True,
                         tags=tags, silent=args.silent)

    timer._cycle(work, relax)


@alias('in')
@arg('activity')
@arg('-c', '--continued', default=False, help='continue from last stop')
@arg('-i', '--interactive', default=False)
def punch_in(args):
    """Starts tracking given activity in Hamster. Stops tracking on C-c.

    :param continued:

        The start time is taken from the last logged fact's end time. If that
        fact is not marked as finished, it is ended now. If it describes the
        same activity and is not finished, it is continued; if it is already
        finished, user is prompted for action.

    :param interactive:

        In this mode the application prompts for user input, adds it to the
        fact description (with timestamp) and displays the prompt again. The
        first empty comment stops current activitp and terminates the app.

        Useful for logging work obstacles, decisions, ideas, etc.

    """
    # TODO:
    # * smart "-c":
    #   * "--upto DURATION" modifier (avoids overlapping)
    assert storage.hamster_storage
    activity, category = storage.parse_activity(args.activity)
    h_act = u'{activity}@{category}'.format(**locals())
    start = None
    fact = None
    if args.continued:
        prev = storage.get_latest_fact()
        if prev:
            if prev.activity == activity and prev.category == category:
                do_cont = True
                #comment = None
                if prev.end_time:
                    delta = datetime.datetime.now() - prev.end_time
                    question = (u'Merge with previous entry filling {0} of '
                                 'inactivity'.format(utils.format_delta(delta)))
                    if not confirm(question, default=True):
                        do_cont = False
                    #comment = question

                if do_cont:
                    fact = prev
                    storage.update_fact(fact, end_time=None)#, extra_description=comment)

            # if the last activity has not ended yet, it's ok: the `start`
            # variable will be `None`
            start = prev.end_time
            if start:
                yield u'Logging activity as started at {0}'.format(start)

    if not fact:
        fact = storage.Fact(h_act, tags=[HAMSTER_TAG], start_time=start)
        storage.hamster_storage.add_fact(fact)
        yield success(u'Started {0}'.format(h_act))

    if not args.interactive:
        return

    yield u'Type a comment and hit Enter. Empty comment ends activity.'
    try:
        while True:
            comment = raw_input(u'-> ').strip()
            if not comment:
                break
            fact = storage.get_current_fact()
            assert fact, 'all logged activities are already closed'
            storage.update_fact(fact, extra_description=comment)
    except KeyboardInterrupt:
        pass
    fact = storage.get_current_fact()
    storage.hamster_storage.stop_tracking()
    yield success(u'Stopped (total {0.delta}).'.format(fact))


@alias('out')
@arg('-d', '--description', help='comment')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('--ppl', help='--ppl john,mary = -t with-john,with-mary')
def punch_out(args):
    "Stops an ongoing activity tracking in Hamster."
    assert storage.hamster_storage

    kwargs = {}

    if args.description:
        kwargs.update(extra_description=args.description)

    # tags
    extra_tags = []
    if args.tags:
        extra_tags.extend(args.tags.split(','))
    if args.ppl:
        extra_tags.extend(['with-{0}'.format(x) for x in args.ppl.split(',')])
    if extra_tags:
        kwargs.update(extra_tags=extra_tags)

    if kwargs:
        fact = storage.get_current_fact()
        assert fact
        storage.update_fact(fact, **kwargs)

    storage.hamster_storage.stop_tracking()
    yield success(u'Stopped.')


@alias('log')
@arg('activity')
@arg('-d', '--description')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('-s', '--since', help='activity start time (HH:MM)')
@arg('-u', '--until', help='activity end time (HH:MM)')
@arg('--duration', help='activity duration (HH:MM)')
@arg('-b', '--between', help='HH:MM-HH:MM')
@arg('--ppl', help='--ppl john,mary = -t with-john,with-mary')
def log_activity(args):
    "Logs a past activity (since last logged until now)"
    assert storage.hamster_storage
    since = args.since
    until = args.until
    duration = args.duration

    if args.between:
        assert not (since or until or duration), (
            '--since, --until and --duration must not be used with --between')
        since, until = args.between.split('-')

    since = utils.parse_time_to_datetime(since)
    until = utils.parse_time_to_datetime(until)
    delta = utils.parse_delta(duration)

    start, end = storage.get_start_end(since, until, delta)
    assert start < end < datetime.datetime.now()

    # check if we aren't going to overwrite any previous facts
    todays_facts = storage.get_facts_for_day()
    def overlaps(fact, start_time, end_time):
        if not fact.end_time:
            # previous activity is still open
            return True
        if start_time >= fact.end_time or end_time <= fact.start_time:
            return False
        return True
    overlap = [f for f in todays_facts if overlaps(f, start, end)]
    if overlap:
        # TODO: display (non-)overlapping duration
        overlap_str = ', '.join(u'{0.activity}'.format(f) for f in overlap)
        yield warning(u'Given time overlaps earlier facts '
                      u'({0}).'.format(overlap_str))
        yield u'Latest activity ended at {0.end_time}.'.format(overlap[-1])
        if 1 == len(overlap) and overlap[0].start_time and overlap[0].start_time < start:
            action = u'Fix previously logged activity'
        else:
            action = u'Add a parallel activity'
        action = warning(action)
        if not confirm(action, default=False):
            yield failure(u'Operation cancelled.')
            return

    activity, category = storage.parse_activity(args.activity)
    h_act = u'{activity}@{category}'.format(**locals())

    tags = [HAMSTER_TAG_LOG]
    if args.tags:
        tags = list(set(tags + args.tags.split(',')))
    if args.ppl:
        tags.extend(['with-{0}'.format(x) for x in args.ppl.split(',')])

    fact = storage.Fact(h_act, tags=tags, description=args.description,
                        start_time=start, end_time=end)
    storage.hamster_storage.add_fact(fact)

    # report
    delta = fact.end_time - start  # почему-то сам факт "не знает" времени начала
    delta_minutes = delta.seconds / 60
    template = u'Logged {h_act} ({delta_minutes} min)'
    yield success(template.format(h_act=h_act, delta_minutes=delta_minutes))


@alias('ps')
@arg('text', nargs='+')
def add_post_scriptum(args):
    "Adds given text to the last logged (or current) fact."
    assert storage.hamster_storage
    fact = storage.get_latest_fact()
    assert fact
    text = ' '.join(args.text)
    storage.update_fact(fact, extra_description=text)


@alias('find')
@arg('query', help='"," = OR, " " = AND')
# NOTE: alas, Hamster does not support precise search by fields
#@arg('-c', '--category')
#@arg('-a', '--activity')
#@arg('-d', '--description')
#@arg('-t', '--tags')
@arg('--days', default=1, help='number of days to examine')
@arg('--summary', default=False, help='display only summary')
def find_facts(args):
    until = datetime.datetime.now()
    since = until - datetime.timedelta(days=args.days)
    print 'Facts with "{args.query}" in {since}..{until}'.format(**locals())
    facts = storage.get_facts_for_day(since, end_date=until,
                                      search_terms=args.query)
    total_spent = datetime.timedelta()
    total_found = 0
    seen_workdays = {}
    for fact in facts:
        tmpl = u'{time}  {fact.activity}@{fact.category} {tags} {fact.delta}'
        if not args.summary:
            yield tmpl.format(
                fact = fact,
                tags = ' '.join(unicode(t) for t in fact.tags),
                time = fact.start_time.strftime('%Y-%m-%d %H:%M'),
            )
            if fact.description:
                yield fact.description
            yield '---'
        total_spent += fact.delta
        total_found += 1
        seen_workdays[fact.start_time.date()] = 1
    total_workdays = len(seen_workdays)
    yield u'Total facts found: {0}'.format(total_found)
    yield u'Total time spent: {0}'.format(total_spent)
    total_minutes = total_spent.total_seconds() / 60
    total_hours = total_minutes / 60
    yield u'Avg duration: {0:.0f} minutes ({1:.1f} hours)'.format(
        total_minutes / (total_found or 1), total_hours / (total_found or 1))
    yield u'Avg duration per day: {0:.0f} minutes ({1:.1f} hours)'.format(
        total_minutes / args.days, total_hours / args.days)
    # "workdays" here are dates when given activity was started at least once.
    yield u'Avg duration per workday: {0:.0f} minutes ({1:.1f} hours)'.format(
        total_minutes / (total_workdays or 1),
        total_hours / (total_workdays or 1))


def show_last(args):
    "Displays detailed information on latest fact."
    fact = storage.get_latest_fact()
    if not fact:
        return
    padding = max(len(k) for k in fact.__dict__)
    field_template = u'{key:>{padding}}: {value}'
    for k in fact.__dict__:
        value = getattr(fact, k)
        if k == 'tags':
            value = ', '.join(unicode(tag) for tag in value)
        yield field_template.format(key=k, value=value, padding=padding)


def now(args):
    "Displays short note about current activity, if any."
    fact = storage.get_latest_fact()
    if fact:
        yield fact.activity
        yield '    {0} +{1}'.format(fact.start_time.strftime('%H:%M'), fact.delta)
        if fact.end_time:
            gap = datetime.datetime.now() - fact.end_time
            yield u'    Ended -{0} ago'.format(utils.format_delta(gap))
        else:
            yield u'    RUNNING'
    else:
        yield u'--'


@arg('-n', '--number', default=1,
     help='number of the fact: latest is 1, previous is 2, etc.')
@arg('--set-activity')
def update_fact(args):
    latest_facts = storage.get_facts_for_day()
    fact = latest_facts[-args.number]
    kwargs = {}
    if args.set_activity:
        yield u'Updating fact {0}'.format(fact)
        activity, category = storage.parse_activity(args.set_activity)
        kwargs['activity'] = activity
        kwargs['category'] = category
        storage.update_fact(fact, **kwargs)
    else:
        yield failure(u'No arguments given.')


@alias('drift')
@arg('activity')
@arg('-d', '--days', default=7)
def show_drift(args):
    """Displays hourly chart for given activity for a number of days.
    Primary use: evaluate regularity of certain activity, detect deviations,
    trends, cycles. Initial intention was to find out my sleeping drift.
    """
    return drift.show_drift(activity=args.activity, span_days=args.days)


commands = [once, cycle, pomodoro, punch_in, punch_out, log_activity, now,
            add_post_scriptum, find_facts, show_last, update_fact, show_drift]


def main():
    parser = ArghParser()
    parser.add_commands(commands)
    parser.dispatch()


if __name__=='__main__':
    main()
