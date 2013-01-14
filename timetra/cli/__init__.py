#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
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
from argh import (aliases, arg, confirm, CommandError, expects_obj,
                  dispatch_commands, wrap_errors)
import datetime
import textwrap

from timetra.reporting import drift
from timetra.term import success, warning, failure
from timetra import storage, timer, utils


HAMSTER_TAG = 'timetra'
HAMSTER_TAG_LOG = 'timetra-log'


class NotFoundError(Exception):
    pass


def parse_activity(loose_name):
    try:
        return storage.parse_activity(loose_name)
    except storage.ActivityMatchingError as e:
        raise CommandError(failure(e))


def _get_last_fact(activity_mask=None, days=2):
    if not activity_mask:
        return storage.get_latest_fact()

    activity, _ = parse_activity(activity_mask)
    if '-' in activity:
        # XXX this is absolutely crazy, but Hamster's search engine cannot
        # search by activity name, only by words.  Facts for activity
        # "tweak-soft@maintenance" can be found by "tweak" or "soft" but
        # not "tweak-soft".
        search_term = activity.partition('-')[0]
    else:
        search_term = activity

    until = datetime.datetime.now()
    since = until - datetime.timedelta(days=days)
    facts = storage.get_facts_for_day(since, until,
                                      search_terms=search_term)

    # additional filtering because Hamster gives many false positives
    # (as long as ignoring obvious matches, yep)
    facts_filtered = [f for f in facts if f.activity == activity]

    fact = facts_filtered[-1] if facts_filtered else None

    if fact:
        assert fact.activity == activity, fact.activity + '|'+ activity
    else:
        obj = 'a "{0}" fact'.format(activity) if activity else 'a fact'
        raise NotFoundError('Could not find {0} within last '
                            '{1} days'.format(obj, days))
    return fact


@arg('periods', nargs='+')
def cycle(periods, silent=False):
    timer._cycle(*[timer.Period(x, silent=silent) for x in periods])


@arg('periods', nargs='+')
def once(periods, silent=False):
    timer._once(*[timer.Period(x, silent=silent) for x in periods])


@arg('-w', '--work-duration', help='period length in minutes')
@arg('-r', '--rest-duration', help='period length in minutes')
@arg('-d', '--description', help='description for work periods')
def pomodoro(activity='work', silent=False, work_duration=30, rest_duration=10,
             description=''):
    yield 'Running Pomodoro timer'
    work_activity, work_category = parse_activity(activity)
    tags = ['pomodoro', HAMSTER_TAG]

    work = timer.Period(work_duration, name=work_activity,
                        category_name=work_category, hamsterable=True,
                        tags=tags, silent=silent,
                        description=description)
    relax = timer.Period(rest_duration, name='relax', hamsterable=True,
                         tags=tags, silent=silent)

    timer._cycle(work, relax)


@aliases('in')
@arg('-c', '--continued', help='continue from last stop')
def punch_in(activity, continued=False, interactive=False):
    """Starts tracking given activity in Hamster. Stops tracking on C-c.

    :param continued:

        The start time is taken from the last logged fact's end time. If that
        fact is not marked as finished, it is ended now. If it describes the
        same activity and is not finished, it is continued; if it is already
        finished, user is prompted for action.

    :param interactive:

        In this mode the application prompts for user input, adds it to the
        fact description (with timestamp) and displays the prompt again. The
        first empty comment stops current activity and terminates the app.

        Useful for logging work obstacles, decisions, ideas, etc.

    """
    # TODO:
    # * smart "-c":
    #   * "--upto DURATION" modifier (avoids overlapping)
    assert storage.hamster_storage
    activity, category = parse_activity(activity)
    h_act = u'{activity}@{category}'.format(**locals())
    start = None
    fact = None
    if continued:
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
        for line in show_last_fact():
            yield line

    if not interactive:
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
    for line in show_last_fact():
        yield line


@aliases('out')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('-p', '--ppl', help='--ppl john,mary = -t with-john,with-mary')
def punch_out(description=None, tags=None, ppl=None):
    "Stops an ongoing activity tracking in Hamster."
    assert storage.hamster_storage

    kwargs = {}

    if description:
        kwargs.update(extra_description=description)

    # tags
    extra_tags = []
    if tags:
        extra_tags.extend(tags.split(','))
    if ppl:
        extra_tags.extend(['with-{0}'.format(x) for x in ppl.split(',')])
    if extra_tags:
        kwargs.update(extra_tags=extra_tags)

    fact = storage.get_current_fact()

    if not fact:
        raise CommandError(failure(u'No activity is running.'))

    if kwargs:
        storage.update_fact(fact, **kwargs)

    storage.hamster_storage.stop_tracking()

    for line in show_last_fact():
        yield line


@aliases('log')
@arg('activity', nargs='?', help='must be specified unless --amend is set')
@arg('-a', '--amend', default=False,
     help='update last fact instead of creating a new one')
@arg('-d', '--description')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('-s', '--since', help='activity start time (HH:MM)')
@arg('-u', '--until', help='activity end time (HH:MM)')
@arg('--duration', help='activity duration (HH:MM)')
@arg('-b', '--between', help='HH:MM-HH:MM')
@arg('--ppl', help='--ppl john,mary = -t with-john,with-mary')
@arg('--dry-run', default=False, help='do not alter the database')
@arg('--pick', default=None, help='last activity name to pick if --amend flag '
     'is set (if not given, last activity is picked, regardless of its name)')
@wrap_errors([storage.StorageError, NotFoundError], processor=failure)
@expects_obj
def log_activity(args):
    "Logs a past activity (since last logged until now)"

    # TODO: split all changes into steps and apply each using a separate,
    # well-tested function

    assert storage.hamster_storage
    since = args.since
    until = args.until
    duration = args.duration

    if not args.activity and not args.amend:
        raise CommandError(failure('activity must be specified '
                                   'unless --amend is set'))

    if args.between:
        assert not (since or until or duration), (
            '--since, --until and --duration must not be used with --between')
        since, until = args.between.split('-')

    since = utils.parse_time_to_datetime(since)
    until = utils.parse_time_to_datetime(until)
    delta = utils.parse_delta(duration)

    tags = [HAMSTER_TAG_LOG]
    if args.tags:
        tags = list(set(tags + args.tags.split(',')))
    if args.ppl:
        tags.extend(['with-{0}'.format(x) for x in args.ppl.split(',')])

    if args.pick and not args.amend:
        raise CommandError(failure('--pick only makes sense with --amend'))

    prev = _get_last_fact(args.pick)

    if args.amend:
        if not prev:
            raise CommandError('Cannot amend: no fact found')

        # FIXME this disables --duration
        since = since or prev.start_time
        until = until or prev.end_time

    start, end = storage.get_start_end(since, until, delta)

    if end < start:
        raise CommandError('--since must be earlier than --until')

    if datetime.datetime.now() < end:
        raise CommandError('--until must not be in the future')

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
    if args.amend:
        # do not count last fact as overlapping if we are about to change it.
        # using unicode(fact) because Hamster's Fact objects cannot be compared
        # directly for some reason.
        overlap = [f for f in overlap if not unicode(f) == unicode(prev)]
    if overlap:
        if 1 < len(overlap):
            yield failure('FAIL: too many overlapping facts')
            return

        prev_fact = overlap[-1]

        if start <= prev_fact.start_time and prev_fact.end_time <= end:
            # new fact devours an older one; this cannot be handled "properly"
            # FIXME: should count deltas <1min as equality
            yield failure('FAIL: new fact would replace an older one')
            return

        # FIXME: probably time should be rounded to seconds or even minutes
        #        for safer comparisons (i.e. 15:30:15 == 15:30:20)

        #--- begin vision   (pure visualization; backend will make decisions
        #                    on its own, hopefully in the same vein)

        outcome = []
        old = prev_fact.activity
        new = args.activity

        if prev_fact.start_time < start:
            outcome.append((warning(old), start - prev_fact.start_time))
        outcome.append((success(new), end - start))
        if end < prev_fact.end_time:
            outcome.append((warning(old), prev_fact.end_time - end))

        vision = '  '.join(u'[{0} +{1}]'.format(x[0], utils.format_delta(x[1])) for x in outcome)

        yield u'Before:  [{0} +{1}]'.format(failure(prev_fact.activity),
                                            utils.format_delta(prev_fact.delta))
        yield u' After:  {0}'.format(vision)

        #
        #--- end vision

        if not confirm(u'OK', default=False):
            yield failure(u'Operation cancelled.')
            return

    if args.amend:
        #template = u'Updated {fact.activity}@{fact.category} ({delta_minutes} min)'
        assert prev
        fact = prev

        kwargs = dict(
            start_time=start,
            end_time=end,
            dry_run=args.dry_run,
        )
        if args.activity:
            activity, category = parse_activity(args.activity)
            kwargs.update(activity=activity, category=category)
        if args.description is not None:
            kwargs.update(description=args.description)
        if args.tags is not None or args.ppl is not None:
            kwargs.update(tags=tags)

        changed = []
        for key, value in kwargs.iteritems():
            if hasattr(fact, key) and getattr(fact, key) != kwargs[key]:
                changed.append(key)
                old_value = getattr(fact, key)
                if hasattr(old_value, '__iter__'):
                    # convert DBus strings to proper pythonic ones (for tags)
                    old_value = [str(x) for x in old_value]
                note = u''
                if isinstance(old_value, datetime.datetime) and value:
                    if old_value < value:
                        note = u'(+{0})'.format(value - old_value)
                    else:
                        note = u'(-{0})'.format(old_value - value)
                yield u'* {0}: {1} →  {2} {3}'.format(
                    key,
                    failure(unicode(old_value)),
                    success(unicode(value)),
                    note)

        if not changed:
            yield failure(u'Nothing changed.')
            return

        storage.update_fact(fact, **kwargs)
    else:
        #template = u'Logged {fact.activity}@{fact.category} ({delta_minutes} min)'
        try:
            fact = storage.add_fact(
                args.activity,
                start_time=start,
                end_time=end,
                description=args.description,
                tags=tags,
                dry_run=args.dry_run)
        except (storage.ActivityMatchingError, storage.CannotCreateFact) as e:
            raise CommandError(failure(e))

    # report
    #delta = fact.end_time - start  # почему-то сам факт "не знает" времени начала
    #delta_minutes = delta.seconds / 60
    #yield success(template.format(fact=fact, delta_minutes=delta_minutes))

    for output in show_last_fact(args.activity or args.pick):
        yield output

    if args.dry_run:
        yield warning(u'(Dry run, nothing changed.)')


@aliases('ps')
def add_post_scriptum(*text):
    "Adds given text to the last logged (or current) fact."
    assert text
    assert storage.hamster_storage
    fact = storage.get_latest_fact()
    assert fact
    text = ' '.join(text)
    storage.update_fact(fact, extra_description=text)

    for output in show_last_fact():
        yield output


@aliases('find')
@arg('query', help='"," = OR, " " = AND')
# NOTE: alas, Hamster does not support precise search by fields
#@arg('-c', '--category')
#@arg('-a', '--activity')
#@arg('-d', '--description')
#@arg('-t', '--tags')
@arg('--days', help='number of days to examine')
@arg('--summary', help='display only summary')
def find_facts(query, days=1, summary=False):
    "Queries the fact database."
    until = datetime.datetime.now()
    since = until - datetime.timedelta(days=days)
    yield '# query "{0}"'.format(query)
    yield '# since {0}'.format(since)
    yield '# until {0}'.format(until)
    yield ''
    facts = storage.get_facts_for_day(since, end_date=until,
                                      search_terms=query)
    total_spent = datetime.timedelta()
    total_found = 0
    min_duration = None
    min_duration_event = None
    max_duration = None
    max_duration_event = None
    seen_workdays = {}
    for fact in facts:
        tmpl = u'{since}  [ {activity} +{fact.delta} ]  {until}  |  {fact.category}'
        if not summary:
            yield tmpl.format(
                fact = fact,
                activity = warning(fact.activity),
                since = success(fact.start_time.strftime('%Y-%m-%d %H:%M')),
                until = fact.end_time.strftime('%Y-%m-%d %H:%M'),
            )
            tags = (unicode(t) for t in fact.tags)
            tags = [x for x in tags if not x in (HAMSTER_TAG, HAMSTER_TAG_LOG)]

            if fact.description:
                yield textwrap.fill(fact.description, initial_indent='    ',
                                    subsequent_indent='    ')
                #yield fact.description
            if tags:
                yield u'    #{0}'.format(' #'.join(tags))
        total_spent += fact.delta
        total_found += 1
        if min_duration is None or (datetime.timedelta(minutes=1) < fact.delta and fact.delta < min_duration):
            min_duration = fact.delta
            min_duration_event = fact
        if max_duration is None or max_duration < fact.delta:
            max_duration = fact.delta
            max_duration_event = fact
        seen_workdays[fact.start_time.date()] = 1

    if not total_found:
        yield failure(u'No facts found.')
        return

    total_workdays = len(seen_workdays)
    yield ''
    yield u'# Summary'
    yield u''
    yield u'* {0} facts'.format(warning(total_found))
    yield u'* {0} spent in total'.format(warning(total_spent))
    total_minutes = total_spent.total_seconds() / 60
    total_hours = total_minutes / 60
    yield u'* duration:'
    yield u'  {0:.0f} minutes ({1:.1f} hours)  per event'.format(
        total_minutes / (total_found or 1), total_hours / (total_found or 1))
    yield u'  {0:.0f} minutes ({1:.1f} hours)  per day'.format(
        total_minutes / days, total_hours / days)
    # "workdays" here are dates when given activity was started at least once.
    yield u'  {0:.0f} minutes ({1:.1f} hours)  per workday'.format(
        total_minutes / (total_workdays or 1),
        total_hours / (total_workdays or 1))
    if min_duration:
        yield u'  {0}  min event duration ({1.start_time})'.format(
            utils.format_delta(min_duration), min_duration_event)
    if max_duration:
        yield u'  {0}  max event duration ({1.start_time})'.format(
            utils.format_delta(max_duration), max_duration_event)


@aliases('last')
@arg('activity_mask', nargs='?', help='activity name (short form)')
@arg('--days', help='if `activity` is given, search this deep')
@arg('-v', '--verbose', default=False)
def show_last_fact(activity_mask=None, days=365, verbose=False):
    "Displays short note about current or latest activity, if any."

    fact = _get_last_fact(activity_mask, days=days)

    if not fact:
        yield u'--'
        return

    if fact.end_time:
        gap = datetime.datetime.now() - fact.end_time
        if gap.total_seconds() < 60:
            chart_right = u']  just finished'
        elif gap.total_seconds() < 60*24:
            chart_right = u']  ... +{0}'.format(utils.format_delta(gap))
        else:
            chart_right = u']  ... +{0}'.format(gap)
    else:
        chart_right = u'...>'
    yield u'{start}  [ {name}  +{duration} {right}'.format(
        name=warning(fact.activity),
        start=fact.start_time.strftime('%H:%M'),
        duration=fact.delta,
        right=chart_right
    )
    if fact.description:
        yield u''
        yield u'\n'.join(u'       {0}'.format(x) for x in fact.description.split('\n'))

    if not verbose:
        return

    yield u''
    padding = max(len(k) for k in fact.__dict__)
    field_template = u'{key:>{padding}}: {value}'
    for k in sorted(fact.__dict__):
        value = getattr(fact, k)
        if k == 'tags':
            value = ', '.join(unicode(tag) for tag in value)
        yield field_template.format(key=k, value=value, padding=padding)


@arg('-n', '--number', help='number of the fact: latest is 1, previous 2, etc')
def update_fact(number=1, activity=None):
    latest_facts = storage.get_facts_for_day()
    fact = latest_facts[-number]
    kwargs = {}
    if activity:
        yield u'Updating fact {0}'.format(fact)
        activity, category = parse_activity(activity)
        kwargs['activity'] = activity
        kwargs['category'] = category
        storage.update_fact(fact, **kwargs)
    else:
        yield failure(u'No arguments given.')


@aliases('drift')
def show_drift(activity, days=7):
    """Displays hourly chart for given activity for a number of days.
    Primary use: evaluate regularity of certain activity, detect deviations,
    trends, cycles. Initial intention was to find out my sleeping drift.
    """
    return drift.show_drift(activity=activity, span_days=days)


commands = [once, cycle, pomodoro, punch_in, punch_out, log_activity,
            add_post_scriptum, find_facts, show_last_fact, update_fact,
            show_drift]


def main():
    dispatch_commands(commands)


if __name__=='__main__':
    main()
