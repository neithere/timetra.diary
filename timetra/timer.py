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
import sys
import time
import datetime

from timetra import notification
from timetra.storage import Fact, hamster_storage
from timetra.term import success, warning, failure


# remind that "less than a minute left" each N seconds
LAST_MINUTE_ALARM_FREQUENCY = 30


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

        # TODO replace with signals
        if self.is_hamsterable:
            hamster_storage.stop_tracking()

        self.until = None

    def notify(self, message, mode=None, log=True, osd=True):
        if log:
            colored = failure if mode == self.ALARM_CANCEL else warning
            print '{time} {message}'.format(
                time = get_colored_now(),
                message = colored(message),
            )

        if osd:
            notification.show(message, critical=bool(mode == self.ALARM_START))

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
            notification.beep(*beeps)

            # FIXME this should be used *instead* of beeping if Festival
            # program is available
            if mode in [self.ALARM_START, self.ALARM_REMIND,
                        self.ALARM_CANCEL]:
                notification.say(message)


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


def get_colored_now():
    """Returns colored and formatted current time"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return success(now)
