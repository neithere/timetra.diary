#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Timer is a time tracking script.
#    Copyright © 2010-2011  Andrey Mikhaylenko
#
#    This file is part of Timer.
#
#    Timer is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Timer is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with Timer.  If not, see <http://gnu.org/licenses/>.
#
"""
Timer
=====

:author: Andrey Mikhaylenko
:dependencies:
    * argh
    * beep (optional)
    * hamster (optional)
    * pynotify (optional)
    * festival (optional)

"""
from argh import alias, arg, confirm, ArghParser, CommandError
import datetime
import os
import subprocess
import sys
import time
from warnings import warn

import drift


# Visible notifications
try:
    import pynotify
except ImportError:
    warn('Visible alerts are disabled')
    pynotify = None
else:
    pynotify.init('timer')

# Audible notifications
try:
#    sys.path.insert(0, '/home/andy/src')
#    import beeper   # custom script, see http://paste.pocoo.org/show/316/
#    import beeper_alsa
    subprocess.Popen(['beep', '-l', '0'])
except OSError:
    warn('Simple audible alerts are disabled')
    beep_enabled = False
else:
    beep_enabled = True

# Hamster integration
try:
    from hamster.client import Storage
    hamster_storage = Storage()
    try:
        from hamster.lib.stuff import Fact
    except ImportError:
        # legacy
        warn('using an old version of Hamster')
        from hamster.utils.stuff import Fact
except ImportError:
    warn('Hamster integration is disabled')
    hamster_storage = None
    Fact = None

# http://stackoverflow.com/questions/287871/print-in-terminal-with-colors-using-python
# TODO: use http://pypi.python.org/pypi/blessings/
COLOR_BLUE = '\033[94m'
COLOR_GREEN = '\033[92m'
COLOR_WARNING = '\033[93m'
COLOR_FAIL = '\033[91m'
COLOR_ENDC = '\033[0m'


HAMSTER_TAG = 'auto-timed'
HAMSTER_TAG_LOG = 'auto-logged'
# remind that "less than a minute left" each N seconds
LAST_MINUTE_ALARM_FREQUENCY = 30


def get_colored_now():
    """Returns colored and formatted current time"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return COLOR_GREEN + now + COLOR_ENDC


def beep(*pairs):
    """Emits beeps using the "beep" program."""
    if not beep_enabled:
        return
    beeps = []
    for frequency, duration in pairs:
        beeps.extend(['-f', str(frequency), '-l', str(duration), '-n'])
    beeps.pop()   # remove the last "-n" separator to prevent extra beep
    subprocess.Popen(['beep'] + beeps) #, '-f', str(frequency), '-l', str(duration)])
    #'beep -f 100 -n -f 150 -n -f 50 -n -f 300 -n -f 200 -n -f 400'.split())
#    try:
#        beeper.beep(frequency, duration)
#    except IOError:
#        beeper_alsa.beep(frequency, duration)


def say(text):
    """Uses Festival TTS to actually say the message."""
    # see http://ubuntuforums.org/showthread.php?t=751169
    sound_wrapper = 'padsp'  # or 'aoss' or 'esddsp' or none
    command = 'echo \'(SayText "{text}")\' | {sound_wrapper} festival &'
    text = text.replace('"','').replace("'",'')
    os.system(command.format(sound_wrapper=sound_wrapper, text=text))


class Period(object):
    ALARM_START = 1
    ALARM_END = 2
    ALARM_CANCEL = 3
    ALARM_REMIND = 4

    def __init__(self, minutes, name=None, category_name='workflow',
                 description='', hamsterable=False, tags=[], silent=False):
        self.minutes = int(minutes)
        self.name = name
        self.category_name = category_name
        self.description = description
        self.is_hamsterable = hamsterable
        self.hamster_tags = tags
        self.until = None
        self.silent = silent

    def __int__(self):
        return int(self.minutes)

    def __repr__(self):
        return str(unicode(self))

    def __unicode__(self):
        if self.name:
            return '{0.name} ({0.minutes} minutes)'.format(self)
        else:
            return '{0} minutes period'.format(int(self))

    def start(self):
        now = datetime.datetime.now()
        self.until = now + datetime.timedelta(minutes=self.minutes)

        if hamster_storage and self.is_hamsterable:
            tmpl = u'{self.name}@{self.category_name},{self.description}'
            fact = Fact(tmpl.format(**locals()), tags=self.hamster_tags)
            hamster_storage.add_fact(fact)
#                activity_name = unicode(self),
#                category_name = self.category_name,
#                tags = 'auto-timed',
#            )

#        message = 'Started {name} until {until}'.format(
        message = 'Started {name} for {minutes} minutes'.format(
            name = self.name or unicode(self),
#            until = self.until.strftime('%H:%M:%S'),
            minutes = self.minutes
        )
#        if until:
#            message += ' until {0}'.format(until.strftime('%H:%M:%S'))
        self.notify(message, self.ALARM_START)

    def stop(self):
        now = datetime.datetime.now()
        if self.until <= now:
            msg = '{self} is over!'.format(**locals())
            self.notify(msg, self.ALARM_END)
        else:
            delta = self.until - now
            msg = ('  Timer stopped with {0} minutes left (out of {1})'
                    ).format(delta.seconds / 60, self.minutes)
            self.notify(msg, self.ALARM_CANCEL)
        if self.is_hamsterable:
            hamster_storage.stop_tracking()
        self.until = None

    def notify(self, message, mode=None, log=True, osd=True):
        if log:
            color = COLOR_FAIL if mode == self.ALARM_CANCEL else COLOR_WARNING
            print '{time} {message}'.format(
                time = get_colored_now(),
                message = color + message + COLOR_ENDC,
            )

        if osd and pynotify:
            note = pynotify.Notification(summary=message)
            if mode == self.ALARM_START:
                note.set_urgency(pynotify.URGENCY_CRITICAL)
            note.show()

        if not self.silent:
            beeps = []
            if mode == self.ALARM_START:
                beeps.append((350, 250))

                # emit an extra beep for every 5 minutes of the period
                # (this helps understand which period has just ended)
                for i in range(0, self.minutes / 5):
                    # each beep is 50Hz higher than the previous one
                    freq = 50 * (i+1)
                    beeps.append((freq, 100))

                beeps.append((500,200))
            elif mode == self.ALARM_CANCEL:
                beeps += [(300, 50), (200, 50), (100, 200)]
            elif mode == self.ALARM_END:
                beeps += [(350, 250), (100, 200)]
            else:
                # probably the timer is about to end
                beeps += [(500, 20)]
            beep(*beeps)

            # FIXME this should be used *instead* of beeping if Festival
            # program is available
            if mode in [self.ALARM_START, self.ALARM_REMIND,
                        self.ALARM_CANCEL]:
                say(message)


def wait_for(period):
    until = datetime.datetime.now() + datetime.timedelta(minutes=int(period))
    period.start()
    while True:
        try:
            if until <= datetime.datetime.now():
                period.stop()
                return
            delta = until - datetime.datetime.now()
            if delta.seconds <= 60:
                period.notify('less than a minute left', period.ALARM_REMIND,
                              log=False)
            # wait a bit
            time.sleep(LAST_MINUTE_ALARM_FREQUENCY)
        except KeyboardInterrupt:
            period.stop()
            sys.exit()


def _once(*periods):
    for step in periods:
        wait_for(step)


def _cycle(*periods):
    print 'Cycling periods: {0}'.format(', '.join([str(x) for x in periods]))
    while True:
        _once(*periods)


def _get_hamster_activity(activity):
    """Given a mask, finds the (single) matching activity and returns its full
    name along with category name. Raises AssertionError if no matching
    activity could be found or more than item matched.
    """
    activities = hamster_storage.get_activities()
    # look for exact matches
    candidates = [d for d in activities if activity == d['name']]
    if not candidates:
        # look for partial matches
        candidates = [d for d in activities if activity in d['name']]
    assert candidates, 'unknown activity {0}'.format(activity)
    assert len(candidates) == 1, 'ambiguous name, matches:\n{0}'.format(
        '\n'.join((u'  - {category}: {name}'.format(**x)
                   for x in sorted(candidates))))
    return [unicode(candidates[0][x]) for x in ['name', 'category']]


def _parse_activity(activity_mask):
    activity, category = 'work', None
    if activity_mask:
        if '@' in activity_mask:
            return activity_mask.split('@')
        else:
            try:
                return _get_hamster_activity(activity_mask)
            except AssertionError as e:
                raise CommandError(e)
    return activity, category


def get_facts_for_day(date=None, end_date=None, search_terms=''):
    date = date or datetime.datetime.now().date()
    assert hamster_storage
    return hamster_storage.get_facts(date, end_date, search_terms)


def get_latest_fact(max_age_days=2):
    """ Returns the most recently logged fact.

    :param max_age_days:
        the maximum age of the fact in days. ``1`` means "only today",
        ``2`` means "today or yesterday". Default is ``2``.

        Especially useful with Hamster which sometimes cannot find an activity
        that occured just a couple of minutes ago.

    """
    assert max_age_days
    now = datetime.datetime.now()
    facts = get_facts_for_day(now)
    if not facts:
        start = now - datetime.timedelta(days=max_age_days-1)
        facts = get_facts_for_day(start, now)
    return facts[-1] if facts else None


def get_current_fact():
    fact = get_latest_fact()
    if fact and not fact.end_time:
        return fact


def _format_delta(delta):
    return unicode(delta).partition('.')[0]


def _update_fact(fact, extra_tags=None, extra_description=None, **kwargs):
    for key, value in kwargs.items():
        setattr(fact, key, value)
    if extra_description:
        delta = datetime.datetime.now() - fact.start_time
        new_desc = u'{0}\n\n(+{1}) {2}'.format(
            fact.description or '',
            _format_delta(delta),
            extra_description
        ).strip()
        fact.description = new_desc
    if extra_tags:
        fact.tags = list(set(fact.tags + extra_tags))
    hamster_storage.update_fact(fact.id, fact)


@arg('periods', nargs='+')
@arg('--silent', default=False)
def cycle(args):
    _cycle(*[Period(x, silent=args.silent) for x in args.periods])


@arg('periods', nargs='+')
@arg('--silent', default=False)
def once(args):
    _once(*[Period(x, silent=args.silent) for x in args.periods])


@arg('activity', default='work')
@arg('--silent', default=False)
@arg('-w', '--work-duration', default=30, help='period length in minutes')
@arg('-r', '--rest-duration', default=10, help='period length in minutes')
@arg('-d', '--description', default='', help='description for work periods')
def pomodoro(args):
    print 'Running Pomodoro timer'
    work_activity, work_category = _parse_activity(args.activity)
    tags = ['pomodoro', HAMSTER_TAG]

    work = Period(args.work_duration, name=work_activity,
                  category_name=work_category, hamsterable=True, tags=tags,
                  silent=args.silent, description=args.description)
    relax = Period(args.rest_duration, name='relax', hamsterable=True,
                   tags=tags, silent=args.silent)

    _cycle(work, relax)


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
    assert hamster_storage
    activity, category = _parse_activity(args.activity)
    h_act = u'{activity}@{category}'.format(**locals())
    start = None
    fact = None
    if args.continued:
        prev = get_latest_fact()
        if prev:
            if prev.activity == activity and prev.category == category:
                do_cont = True
                #comment = None
                if prev.end_time:
                    delta = datetime.datetime.now() - prev.end_time
                    question = (u'Merge with previous entry filling {0} of '
                                 'inactivity'.format(_format_delta(delta)))
                    if not confirm(question, default=True):
                        do_cont = False
                    #comment = question

                if do_cont:
                    fact = prev
                    _update_fact(fact, end_time=None)#, extra_description=comment)

            # if the last activity has not ended yet, it's ok: the `start`
            # variable will be `None`
            start = prev.end_time
            if start:
                yield u'Logging activity as started at {0}'.format(start)

    if not fact:
        fact = Fact(h_act, tags=[HAMSTER_TAG], start_time=start)
        hamster_storage.add_fact(fact)
        yield u'Started {0}'.format(h_act)

    if not args.interactive:
        return

    yield u'Type a comment and hit Enter. Empty comment ends activity.'
    try:
        while True:
            comment = raw_input(u'-> ').strip()
            if not comment:
                break
            fact = get_current_fact()
            assert fact, 'all logged activities are already closed'
            _update_fact(fact, extra_description=comment)
    except KeyboardInterrupt:
        pass
    fact = get_current_fact()
    hamster_storage.stop_tracking()
    yield u'Stopped (total {0.delta}).'.format(fact)


@alias('out')
@arg('-d', '--description', help='comment')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('--ppl', help='--ppl john,mary = -t with-john,with-mary')
def punch_out(args):
    "Stops an ongoing activity tracking in Hamster."
    assert hamster_storage

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
        fact = get_current_fact()
        assert fact
        _update_fact(fact, **kwargs)

    hamster_storage.stop_tracking()
    yield u'Stopped.'


def _split_time(string):
    """ Returns a pair of integers `(hours, minutes)` for given string::

        >>> _split_time('02:15')
        (2, 15)
        >>> _split_time('2:15')
        (2, 15)
        >>> _split_time(':15')
        (0, 15)
        >>> _split_time('15')
        (0, 15)

    """
    def _split(s):
        if ':' in s:
            return s.split(':')
        if len(s) <= 2:
            # "35" -> 00:35
            return 0, s
        return s[:-2], s[-2:]

    return tuple(int(x or 0) for x in _split(string))


def _parse_time(string):
    """
    Returns a datetime.time object and a boolean that tells whether given time
    should be substracted from the start time.

        >>> parse_time('20')
        (time(0, 20), False)
        >>> parse_time('-1:35')
        (time(1, 35), True)
        >>> parse_time('now')
        datetime.now().time()
        >>> parse_time('now-5')
        datetime.now().time() - timedelta(minutes=5)

    """
    substract = False

    if string == 'now':
        return datetime.datetime.now().time(), substract

    if string.startswith('now-'):
        # "now-150"
        now = datetime.datetime.now()
        _, substring = string.split('-')
        delta, _ = _parse_time(substring)
        start = now - datetime.timedelta(hours=delta.hour, minutes=delta.minute)
        return start.time(), substract

    if string.startswith('-'):
        # "-2:58"
        substract = True
        string = string[1:]

    hours, minutes = _split_time(string)

    return datetime.time(hours, minutes), substract


def _parse_time_to_datetime(string, relative_to=None, ensure_past_time=True):
    """ Parses string to a datetime, relative to given date (or current one):

    CURRENT FORMAT:
        12:05 = DATE, at 12:05
    TODO:
         1205 = DATE, at 12:05
          205 = DATE, at 02:05
           05 = DATE, at 00:05
            5 = DATE, at 00:05
           -5 = DATE - 5 minutes
    """
    if not string:
        return
    base_date = relative_to or datetime.datetime.now()
    parsed_time, _ = _parse_time(string)
    date_time = datetime.datetime.combine(base_date, parsed_time)
    if ensure_past_time and base_date < date_time:
        return date_time - datetime.timedelta(days=1)
    else:
        return date_time


def _parse_delta(string):
    """ Parses string to timedelta.
    """
    if not string:
        return
    hours, minutes = _split_time(string)
    return datetime.timedelta(hours=hours, minutes=minutes)


def _get_prev_end_time(require=False):
    prev = get_latest_fact()
    if not prev:
        raise CommandError('Cannot find previous activity.')
    if require and not prev.end_time:
        raise CommandError('Another activity is running.')
    return prev.end_time


def _get_start_end(since, until, delta):
    """
    :param since: `datetime.datetime`
    :param until: `datetime.datetime`
    :param delta: `datetime.timedelta`

    * since .. until
    * since .. since+delta
    * since .. now
    * until-delta .. until
    * prev .. until
    * prev .. prev+delta
    * prev .. now

    """
    prev = _get_prev_end_time(require=True)
    now = datetime.datetime.now()

    if since and until:
        return since, until
    elif since:
        if delta:
            return since, since+delta
        else:
            return since, now
    elif until:
        if delta:
            return until-delta, until
        else:
            return prev, until
    elif delta:
        return prev, prev+delta
    else:
        return prev, now


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
    assert hamster_storage
    since = args.since
    until = args.until
    duration = args.duration

    if args.between:
        assert not (since or until or duration), (
            '--since, --until and --duration must not be used with --between')
        since, until = args.between.split('-')

    since = _parse_time_to_datetime(since)
    until = _parse_time_to_datetime(until)
    delta = _parse_delta(duration)

    start, end = _get_start_end(since, until, delta)
    assert start < end < datetime.datetime.now()

    # check if we aren't going to overwrite any previous facts
    todays_facts = get_facts_for_day()
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
        msg = u'Given time overlaps earlier facts ({0}).'.format(overlap_str)
        yield COLOR_WARNING + msg + COLOR_ENDC
        yield u'Latest activity ended at {0.end_time}.'.format(overlap[-1])
        if 1 == len(overlap) and overlap[0].start_time and overlap[0].start_time < start:
            action = u'Fix previously logged activity'
        else:
            action = u'Add a parallel activity'
        if not confirm(action, default=False):
            yield u'Operation cancelled.'
            return

    activity, category = _parse_activity(args.activity)
    h_act = u'{activity}@{category}'.format(**locals())

    tags = [HAMSTER_TAG_LOG]
    if args.tags:
        tags = list(set(tags + args.tags.split(',')))
    if args.ppl:
        tags.extend(['with-{0}'.format(x) for x in args.ppl.split(',')])

    fact = Fact(h_act, tags=tags, description=args.description,
                start_time=start, end_time=end)
    hamster_storage.add_fact(fact)

    # report
    delta = fact.end_time - start  # почему-то сам факт "не знает" времени начала
    delta_minutes = delta.seconds / 60
    template = u'Logged {h_act} ({delta_minutes} min)'
    yield template.format(h_act=h_act, delta_minutes=delta_minutes)


@alias('ps')
@arg('text', nargs='+')
def add_post_scriptum(args):
    "Adds given text to the last logged (or current) fact."
    assert hamster_storage
    fact = get_latest_fact()
    assert fact
    text = ' '.join(args.text)
    _update_fact(fact, extra_description=text)


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
    facts = get_facts_for_day(since, end_date=until, search_terms=args.query)
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
    fact = get_latest_fact()
    if not fact:
        return
    padding = max(len(k) for k in fact.__dict__)
    field_template = u'{key:>{padding}}: {value}'
    for k in fact.__dict__:
        value = getattr(fact, k)
        if k == 'tags':
            value = ', '.join(unicode(tag) for tag in value)
        yield field_template.format(key=k, value=value, padding=padding)


@arg('-n', '--number', default=1,
     help='number of the fact: latest is 1, previous is 2, etc.')
@arg('--set-activity')
def update_fact(args):
    latest_facts = get_facts_for_day()
    fact = latest_facts[args.number - 1]
    kwargs = {}
    if args.set_activity:
        yield u'Updating fact {0}'.format(fact)
        kwargs['activity'] = args.set_activity
        _update_fact(fact, **kwargs)


@alias('drift')
@arg('activity')
@arg('-d', '--days', default=7)
def show_drift(args):
    """Displays hourly chart for given activity for a number of days.
    Primary use: evaluate regularity of certain activity, detect deviations,
    trends, cycles. Initial intention was to find out my sleeping drift.
    """
    return drift.show_drift(activity=args.activity, span_days=args.days)


commands = [once, cycle, pomodoro, punch_in, punch_out, log_activity,
            add_post_scriptum, find_facts, show_last, update_fact, show_drift]


if __name__=='__main__':
    parser = ArghParser()
    parser.add_commands(commands)
    parser.dispatch()
