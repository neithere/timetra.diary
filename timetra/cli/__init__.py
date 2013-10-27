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
import datetime
import re
import textwrap

from argh import (aliases, arg, ArghParser, confirm, CommandError, expects_obj,
                  named, wrap_errors)
from argh.io import safe_input
import prettytable
import yaml

from timetra.reporting import drift, prediction
from timetra.term import success, warning, failure, t
from timetra import storage, timer, utils, formatdelta


HAMSTER_TAG = 'timetra'
HAMSTER_TAG_LOG = 'timetra-log'
HAMSTER_TAG_LOAD = 'timetra-load'


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
                        category_name=work_category, trackable=True,
                        tags=tags, silent=silent,
                        description=description)
    relax = timer.Period(rest_duration, name='relax', trackable=True,
                         tags=tags, silent=silent)

    timer._cycle(work, relax)


@named('in')
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
        storage.add_fact(fact)
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
    storage.stop_tracking()
    for line in show_last_fact():
        yield line


@named('out')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('-w', '--with_person', help='-w john,mary = -t with-john,with-mary')
def punch_out(description=None, tags=None, with_person=None):
    "Stops an ongoing activity tracking in Hamster."
    kwargs = {}

    if description:
        kwargs.update(extra_description=description)

    # tags
    extra_tags = []
    if tags:
        extra_tags.extend(tags.split(','))
    if with_person:
        extra_tags.extend(['with-{0}'.format(x) for x in with_person.split(',')])
    if extra_tags:
        kwargs.update(extra_tags=extra_tags)

    fact = storage.get_current_fact()

    if not fact:
        raise CommandError(failure(u'No activity is running.'))

    if kwargs:
        storage.update_fact(fact, **kwargs)

    storage.stop_tracking()

    for line in show_last_fact():
        yield line


def complete_activity(prefix, **kwargs):
    candidates = storage.get_hamster_activity_candidates(prefix)
    return [u'{name}@{category}'.format(**c) for c in candidates]


@named('log')
@arg('activity', nargs='?', help='must be specified unless --amend is set',
     completer=complete_activity)
@arg('-a', '--amend', default=False,
     help='update last fact instead of creating a new one')
@arg('-d', '--description')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('--date', help='date to which --since and --until are appended')
@arg('-s', '--since', help='activity start time (HH:MM)')
@arg('-u', '--until', help='activity end time (HH:MM)')
@arg('--duration', help='activity duration (HH:MM)')
@arg('-b', '--between', help='HH:MM-HH:MM')
@arg('-w', '--with-person', help='-w john,mary = -t with-john,with-mary')
@arg('--dry-run', default=False, help='do not alter the database')
@arg('-p', '--pick', default=None, help='last activity name to pick if --amend flag '
     'is set (if not given, last activity is picked, regardless of its name)')
@arg('--no-input', default=False, help='no additional interactive input')
@wrap_errors([storage.StorageError, NotFoundError], processor=failure)
@expects_obj
def log_activity(args):
    "Logs a past activity (since last logged until now)"

    # TODO: split all changes into steps and apply each using a separate,
    # well-tested function

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

    if args.date:
        rel_date = datetime.datetime.strptime(args.date, '%Y-%m-%d')
        since = utils.parse_time_to_datetime(since, relative_to=rel_date,
                                             ensure_past_time=False)
        until = utils.parse_time_to_datetime(until, relative_to=rel_date,
                                             ensure_past_time=False)
    else:
        since = utils.parse_time_to_datetime(since)
        until = utils.parse_time_to_datetime(until)

    delta = utils.parse_delta(duration)

    tags = [HAMSTER_TAG_LOG]
    if args.tags:
        tags = list(set(tags + args.tags.split(',')))
    if args.with_person:
        tags.extend(['with-{0}'.format(x) for x in args.with_person.split(',')])

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
    try:
        for line in check_overlap(start, end,
                                  activity=(args.pick or args.activity),
                                  amend_fact=prev if args.amend else None):
            yield line
    except OverlapError as e:
        raise CommandError(failure(e))

    if args.activity:
        activity, category = parse_activity(args.activity)
    else:
        activity = category = None

    description = None
    if args.description:
        description = args.description
    elif args.no_input:
        pass
    elif args.amend and prev.description:
        # updating a fact that already has a description
        pass
    else:
        # collect multi-line description from interactive user input
        lines = []
        num = 0
        try:
            while True:
                line = safe_input('        > ' if num else warning('Describe> '))
                if line:
                    lines.append(line)
                else:
                    yield ''
                    break
                num += 1
        except (KeyboardInterrupt, EOFError):
            raise CommandError(failure('Operation cancelled.'))
        else:
            description = '\n'.join(lines) if lines else None

    if args.amend:
        #template = u'Updated {fact.activity}@{fact.category} ({delta_minutes} min)'
        assert prev
        fact = prev

        kwargs = dict(
            start_time=start,
            end_time=end,
            dry_run=args.dry_run,
        )
        if activity:
            kwargs.update(activity=activity, category=category)
        if description is not None:
            kwargs.update(description=description)
        if args.tags is not None or args.with_person is not None:
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
                args.activity,    # NOTE: not using parsed activity + category because hamster wants the foo@bar thing
                start_time=start,
                end_time=end,
                description=description,
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


class OverlapError(RuntimeError):
    pass


class TooManyOverlappingFacts(OverlapError):
    pass


class FactOverlapsReplacement(OverlapError):
    pass


def check_overlap(start, end, activity='NEW ACTIVITY', amend_fact=None):
    """ Interactive check for overlapping facts.  To be used from other
    commands as generator.
    """
    def overlaps(fact, start_time, end_time):
        if not fact.end_time:
            # previous activity is still open
            return True
        if start_time >= fact.end_time or end_time <= fact.start_time:
            return False
        return True

    # check if we aren't going to overwrite any previous facts
    # FIXME not today but start.date() .. end.date()
    todays_facts = storage.get_facts_for_day(
        date =   (start - datetime.timedelta(days=1)).date(),
        end_date = (end + datetime.timedelta(days=1)).date())

    overlap = [f for f in todays_facts if overlaps(f, start, end)]

    if amend_fact:
        # do not count last fact as overlapping if we are about to change it.
        # using unicode(fact) because Hamster's Fact objects cannot be compared
        # directly for some reason.
        overlap = [f for f in overlap if not unicode(f) == unicode(amend_fact)]

    if not overlap:
        return

    if 1 < len(overlap):
        raise TooManyOverlappingFacts('FAIL: too many overlapping facts')

    prev_fact = overlap[-1]

    if start <= prev_fact.start_time and prev_fact.end_time <= end:
        # new fact devours an older one; this cannot be handled "properly"
        # FIXME: should count deltas <1min as equality
        raise FactOverlapsReplacement('FAIL: new fact would replace an older one')

    # FIXME: probably time should be rounded to seconds or even minutes
    #        for safer comparisons (i.e. 15:30:15 == 15:30:20)

    #--- begin vision   (pure visualization; backend will make decisions
    #                    on its own, hopefully in the same vein)

    outcome = []
    old = prev_fact.activity
    new = activity

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
        raise CommandError('Operation cancelled.')


@aliases('ps')
def add_post_scriptum(*text):
    "Adds given text to the last logged (or current) fact."
    assert text
    fact = storage.get_latest_fact()
    assert fact
    text = ' '.join(text)
    storage.update_fact(fact, extra_description=text)

    for output in show_last_fact():
        yield output


@named('find')
@arg('query', help='"," = OR, " " = AND')
# NOTE: alas, Hamster does not support precise search by fields
#@arg('-c', '--category')
#@arg('-a', '--activity')
#@arg('-d', '--description')
#@arg('-t', '--tags')
@arg('-d', '--days', help='number of days to examine')
@arg('--summary', help='display only summary')
@arg('--show-date-if-crosses-days', help='display full end date if event '
                                         'spans multiple days')
def find_facts(query, days=1, summary=False, show_date_if_crosses_days=False, compact=False):
    "Queries the fact database."
    until = datetime.datetime.now()
    since = until - datetime.timedelta(days=days)
    yield '# query "{0}"'.format(query)
    yield '# since {0}'.format(since)
    yield '# until {0}'.format(until)
    yield ''
    facts = storage.get_facts_for_day(since, end_date=until,
                                      search_terms=query)
    first_notion = None
    total_spent = datetime.timedelta()
    total_found = 0
    min_duration = None
    min_duration_event = None
    max_duration = None
    max_duration_event = None
    seen_workdays = {}
    last_date = None

    def make_table():
        tbl = prettytable.PrettyTable()
        if compact:
            tbl.field_names = ['time', 'activity', 'summary']
        else:
            tbl.field_names = ['time', 'activity', 'delta', 'summary', 'tags']
        tbl.align = 'l'
        return tbl

    table = None

    for fact in facts:
        if not summary:
            start = fact.start_time
            since_repr = start.strftime('%H:%M')
            if not last_date or last_date != start.date():
                if table:
                    yield table
                yield ''
                yield t.blue(start.strftime('%d %b %Y'))
                yield ''
                table = make_table()
            last_date = start.date()

            until_repr = fact.end_time.strftime('%H:%M')
            if (fact.start_time.date() != fact.end_time.date()
                and show_date_if_crosses_days):
                until_repr = fact.end_time.strftime('%Y-%m-%d %H:%M')

            tags = (unicode(x) for x in fact.tags)
            tags = [x for x in tags if not x in (HAMSTER_TAG, HAMSTER_TAG_LOG)]
            if compact:
                activity_repr = u'{0.activity}'.format(fact)
                description_width = 40
            else:
                activity_repr = u'{0.category}/{0.activity}'.format(fact)
                description_width = 70
            time_repr = '{}—{}'.format(since_repr, until_repr)
            tags_repr = u'#{0}'.format(' #'.join(tags)) if tags else '—'
            summary_repr = textwrap.fill(fact.description or '—',
                                         width=description_width)
            delta_repr = '+{0}'.format(utils.format_delta(fact.delta))

            if compact:
                summary_repr += u' {}'.format(tags_repr)
                time_repr += u' {}'.format(delta_repr)
                row = [time_repr, activity_repr, summary_repr]
            else:
                row = [time_repr, activity_repr, delta_repr, summary_repr, tags_repr]

            table.add_row(row)

        if not first_notion:
            first_notion = fact.start_time
        total_spent += fact.delta
        total_found += 1
        if min_duration is None or (datetime.timedelta(minutes=1) < fact.delta and fact.delta < min_duration):
            min_duration = fact.delta
            min_duration_event = fact
        if max_duration is None or max_duration < fact.delta:
            max_duration = fact.delta
            max_duration_event = fact
        seen_workdays[fact.start_time.date()] = 1

    if not summary:
        yield table

    if not total_found:
        yield failure(u'No facts found.')
        return

    total_workdays = len(seen_workdays)
    yield ''
    yield u'# Summary'
    yield u''
    yield u'* {0} facts'.format(warning(total_found))
    yield u'* {0} was the first notion ({1} ago)'.format(
        warning(first_notion), datetime.datetime.now() - first_notion)
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


@named('last')
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
        name=success(fact.activity),
        start=fact.start_time.strftime('%H:%M'),
        duration=utils.format_delta(fact.delta),
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


@named('update')
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


@aliases('load')
def load_from_file(path, dry_run=False):
    """
    Assumes the following format::

        2013-01-27:
            - "0100-0130 activity description #with #tags"

    """
    with open(path) as f:
        dates = yaml.load(f)

    def _parse_record(raw, date):
        date = datetime.datetime.combine(date, datetime.time(23,59))
        pattern = re.compile(r'(?P<since>\d{4})\-(?P<until>\d{4})\s'
                             r'(?P<activity>[0-9a-z\-_@]+)'
                             r'(?P<description>\s+.+)?')
        match = pattern.search(raw)
        if not match:
            raise ValueError(u'could not parse "{0}"'.format(raw))
        gd = match.groupdict()
        since = utils.parse_time_to_datetime(gd['since'], relative_to=date,
                                             ensure_past_time=False)
        until = utils.parse_time_to_datetime(gd['until'], relative_to=date,
                                             ensure_past_time=False)
        if until < since:
            # started on one day, ended on another
            until += datetime.timedelta(days=1)
        activity, category = parse_activity(gd['activity'])
        description = gd['description'] or ''

        # partially mimic Hamster's tag-in-description serialization convention
        if ' #' in description:
            description, tags = description.split(' #', 1)
            tags = [t.strip() for t in tags.split('#') if t.strip()]
        else:
            tags = []
        tags.append(HAMSTER_TAG_LOAD)

        return {
            'since': since,
            'until': until,
            'activity': '@'.join([activity, category]),
            'description': description.strip(),
            'tags': tags
        }

    for date in sorted(dates):
        yield date
        for record in dates[date]:
            yield 'IN: {0}'.format(record)
            fact_data = _parse_record(record, date)
            try:
                for line in check_overlap(fact_data['since'],
                                          fact_data['until'],
                                          activity=fact_data['activity']):
                    yield line
            except FactOverlapsReplacement:
                yield '...already imported, skipping'
            else:
                fact = storage.add_fact(
                    fact_data['activity'],
                    start_time=fact_data['since'],
                    end_time=fact_data['until'],
                    description=fact_data['description'],
                    tags=fact_data['tags'],
                    dry_run=dry_run)
                yield 'SAVED: {0}'.format(fact)
        yield '---'


@named('predict')
def predict_next(activity):
    """ Predicts next occurence of given activity.
    """
    guess = prediction.predict_next_occurence(activity)
    table = prettytable.PrettyTable()
    table.field_names = 'start', 'end', 'duration', 'ETA'
    table.add_row([
        guess['start'].strftime('%Y-%m-%d %H:%M'),
        guess['end'].strftime('%Y-%m-%d %H:%M'),
        formatdelta.render_delta(guess['duration']),
        '{0}{1}'.format('-' if guess['eta_is_negative'] else '+',
                        formatdelta.render_delta(guess['eta'])),
    ])
    return table


commands = {
    None: [log_activity, add_post_scriptum, find_facts,
            show_last_fact, update_fact, load_from_file],
    'punch': [punch_in, punch_out],
    'timer': [once, cycle, pomodoro],
    'report': [named('drift')(drift.show_drift),
               predict_next],
}


def main():
    parser = ArghParser()
    for namespace in commands:
        parser.add_commands(commands[namespace], namespace=namespace)
    parser.dispatch()


if __name__=='__main__':
    main()
