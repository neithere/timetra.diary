#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# (c) Andy Mikhaylenko, 2010    (2010-09-05, 2010-09-29, 2010-12-02)
#
# Dependencies:
#  - argh
#  - beep
#  - hamster (optional)
#  - pynotify (optional)
#  - festival (optional)

from argh import arg, command, ArghParser
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
#try:
#    sys.path.insert(0, '/home/andy/src')
#    import beeper   # custom script, see http://paste.pocoo.org/show/316/
#    import beeper_alsa
#except ImportError:
#    warn('Audible alerts are disabled')
#    beeper = None

# Hamster integration
try:
    from hamster.client import Storage
    hamster_storage = Storage()
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


# remind that "less than a minute left" each N seconds
LAST_MINUTE_ALARM_FREQUENCY = 30


def get_colored_now():
    """Returns colored and formatted current time"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return COLOR_GREEN + now + COLOR_ENDC

def beep(*pairs):
    """Emits beeps using the "beep" program."""
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

    def __init__(self, minutes, name=None, category_name='Pomodoro',
                 hamsterable=False, silent=False):
        self.minutes = int(minutes)
        self.name = name
        self.category_name = category_name
        self.is_hamsterable = hamsterable
        self.until = None
        self.silent = silent

    def __int__(self):
        return int(self.minutes)

    def __repr__(self):
        return str(unicode(self))

    def __unicode__(self):
        return self.name or '{0}-minute{1} period'.format(
            int(self), 's' if 1 < int(self) else '')

    def start(self):
        now = datetime.datetime.now()
        self.until = now + datetime.timedelta(minutes=self.minutes)

        if hamster_storage and self.is_hamsterable:
            tag = 'auto-timed'
            tmpl = u'{self}@{self.category_name}'
            fact = Fact(tmpl.format(**locals()), tags=[tag])
            hamster_storage.add_fact(fact)
#                activity_name = unicode(self),
#                category_name = self.category_name,
#                tags = 'auto-timed',
#            )

        message = 'Started {name} until {until}'.format(
            name = unicode(self),
            until = self.until.strftime('%H:%M:%S'),
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
    print 'Cycling periods: {0}'.format(
        ', '.join([str(x) for x in periods]))
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
    assert len(candidates) == 1, 'ambiguous name, matches {0}'.format(
        [u'{name}@{category}'.format(**x) for x in candidates])
    return [unicode(candidates[0][x]) for x in ['name', 'category']]

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
@arg('-r', '--rest-duration', default=25, help='period length in minutes')
def pomodoro(args):
    print 'Running Pomodoro timer'
    work_activity, work_category = 'work', None
    if args.activity:
        if '@' in args.activity:
            work_activity, work_category = args.activity.split('@')
        else:
            work_activity, work_category = _get_hamster_activity(args.activity)

    work = Period(args.work_duration, name=work_activity,
                  category_name=work_category, hamsterable=True,
                  silent=args.silent)
    relax = Period(args.rest_duration, name='relax', hamsterable=True,
                   silent=args.silent) 

    _cycle(work, relax)

if __name__=='__main__':
    parser = ArghParser()
    parser.add_commands([once, cycle, pomodoro])
    parser.dispatch()
