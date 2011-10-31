#!/usr/bin/env python2
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

# Visible notifications
try:
    import pynotify
except ImportError:
    warn('Visible alerts are disabled')
    pynotify = None

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
    os.system(command.format(**locals()))


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
                    beeps.append((200, 100))

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

def get_latest_fact():
    # XXX what if the latest fact was logged yesterday or even earlier?
    facts = get_facts_for_day()
    return facts[-1] if facts else None

def get_current_fact():
    fact = get_latest_fact()
    if fact and not fact.end_time:
        return fact

def _format_delta(delta):
    return unicode(delta).partition('.')[0]

def update_fact(fact, extra_tags=None, extra_description=None, **kwargs):
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
@arg('-w', '--work-duration', default=25, help='period length in minutes')
@arg('-r', '--rest-duration', default=5, help='period length in minutes')
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
                    update_fact(fact, end_time=None)#, extra_description=comment)

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
            update_fact(fact, extra_description=comment)
    except KeyboardInterrupt:
        pass
    fact = get_current_fact()
    hamster_storage.stop_tracking()
    yield u'Stopped (total {0.delta}).'.format(fact)

@alias('out')
@arg('-d', '--description', help='comment')
@arg('-t', '--tags', help='comma-separated list of tags')
def punch_out(args):
    "Stops an ongoing activity tracking in Hamster."
    assert hamster_storage

    kwargs = {}

    if args.description:
        kwargs.update(extra_description=args.description)

    if args.tags:
        kwargs.update(extra_tags=args.tags.split(','))

    if kwargs:
        fact = get_current_fact()
        update_fact(fact, **kwargs)

    hamster_storage.stop_tracking()
    yield u'Stopped.'

def _parse_time(string, relative_to=None):
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
    hour, minute = (int(x) for x in string.split(':'))
    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

@alias('log')
@arg('activity')
@arg('-d', '--description')
@arg('-t', '--tags', help='comma-separated list of tags')
@arg('--since', help='activity start time (HH:MM)')
@arg('--until', help='activity end time (HH:MM)')
#@arg('--duration', help='activity duration (HH:MM)')
@arg('-b', '--between', help='HH:MM-HH:MM')
def log_activity(args):
    "Logs a past activity (since last logged until now)"
    assert hamster_storage
    since = args.since
    until = args.until
    if args.between:
        assert not (since or until), (
            '--since and --until must not be used with --between')
        since, until = args.between.split('-')
    if since:
        start = _parse_time(since)
    else:
        prev = get_latest_fact()
        if not prev:
            raise CommandError('Cannot find previous activity.')
        start = prev.end_time
    if not start:
        raise CommandError('Cannot log fact: start time not provided '
                           'and another activity is running.')
    end_time = _parse_time(until) or datetime.datetime.now()
    assert start < end_time

    # check if we aren't going to overwrite any previous facts
    todays_facts = get_facts_for_day()
    def overlaps(fact, start_time):
        if not fact.end_time or start_time < fact.end_time:
            return True
    overlap = [f for f in todays_facts if overlaps(f, start)]
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

    fact = Fact(h_act, tags=tags, description=args.description,
                start_time=start, end_time=end_time)
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
    update_fact(fact, extra_description=text)

@alias('find')
@arg('query', help='"," = OR, " " = AND')
# NOTE: alas, Hamster does not support precise search by fields
#@arg('-c', '--category')
#@arg('-a', '--activity')
#@arg('-d', '--description')
#@arg('-t', '--tags')
@arg('--days', default=1, help='number of days to examine')
def find_facts(args):
    until = datetime.datetime.now()
    since = until - datetime.timedelta(days=args.days)
    print 'Facts with "{args.query}" in {since}..{until}'.format(**locals())
    facts = get_facts_for_day(since, end_date=until, search_terms=args.query)
    total_spent = datetime.timedelta()
    for fact in facts:
        tmpl = u'{time}  {fact.activity}@{fact.category} {tags} {fact.delta}'
        yield tmpl.format(
            fact = fact,
            tags = ' '.join(unicode(t) for t in fact.tags),
            time = fact.start_time.strftime('%Y-%m-%d %H:%M'),
        )
        if fact.description:
            yield fact.description
        yield '---'
        total_spent += fact.delta
    yield u'Total time spent: {0}'.format(total_spent)


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


commands = [once, cycle, pomodoro, punch_in, punch_out, log_activity,
            add_post_scriptum, find_facts, show_last]


if __name__=='__main__':
    parser = ArghParser()
    parser.add_commands(commands)
    parser.dispatch()
