#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#    HamsterCurses is a curses client for Hamster time tracker.
#    Copyright © 2011  Andrey Mikhaylenko
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
Curses UI for Hamster
=====================

:author: Andrey Mikhaylenko
:dependencies:
    * Hamster_
    * urwid_

.. _Hamster: http://projecthamster.wordpress.com
.. _urwid: http://excess.org/urwid/
"""
import datetime
import urwid
import hamster.client


# TODO: move to config
# TODO: procrastination is not a property of an activity on its own;
#       it's rather a property of an activity in the context of current
#       priorities and the possibilities to tackle higher-priority tasks.
#       That is, the user is procrastinating if current activity has lower
#       priority than a number of planned actions doable right now.
CATEGORY_COLOURS = {
    'productive': ('education', 'errands', 'self-care', 'work', 'maintenance'),
    'procrastination': ('needless'),
}

def format_time(date_time):
    if not date_time:
        return u'.....'
    return date_time.strftime('%H:%M')


def get_delta_graph(delta_seconds, minutes_in_block=10):
    blocks_cnt = int(delta_seconds / 60 / minutes_in_block) or 1
    return '■' * blocks_cnt


def get_colour(category):
    for colour in CATEGORY_COLOURS:
        if category in CATEGORY_COLOURS[colour]:
            return colour


class HamsterDayView(object):
    palette = [
        ('body',            'black',       'light gray', 'standout'),
        ('input normal',    'white',       'black'),
        ('input select',    'black',       'yellow'),
        ('button',          'light gray',  'dark green', 'standout'),
        ('button select',   'white',       'dark green'),
        ('header',          'white',       'dark blue'),
        ('bg background',   'light gray',  'black'),
        ('bg 1',            'black',       'dark blue', 'standout'),
        ('bg 2',            'black',       'dark cyan', 'standout'),
        ('productive',      'light green', 'default'),
        ('procrastination', 'light red',   'default'),
    ]

    def __init__(self):
        self.storage = hamster.client.Storage()
        self.factlog = urwid.ListBox(urwid.SimpleListWalker([]))
        self.stats = urwid.ListBox(urwid.SimpleListWalker([]))

        header = urwid.Text(u'(not refreshed)')
        body = urwid.Columns([
            self.factlog,
            self.stats,
        ])
        footer = urwid.Columns([
            #urwid.Text(unicode(datetime.datetime.now())),
            urwid.Text(
                u'q/Esc: quit    '
                u'x: stop activity    '
                u'r: resume last activity'
            )
        ])
        self.frame = urwid.Frame(header=header, body=body, footer=footer)
        self.refresh_data()

    def run(self):
        loop = urwid.MainLoop(self.render(), self.palette,
                              unhandled_input=self.handle_input)
        self.set_refresh_timeout(loop)
        loop.run()

    def set_refresh_timeout(self, main_loop, user_data=None):
        self.refresh_data()
        main_loop.set_alarm_in(2, self.set_refresh_timeout)

    def refresh_factlist(self, facts):
        # Activity log

        # replace list items without dropping the list object
        # (so self.factlog.body doesn't get orphaned)
        self.factlog.body[:] = []

        for fact in facts:
            delta_graph = unicode(get_delta_graph(fact.delta.total_seconds()))
            text = urwid.Text([
                format_time(fact.start_time),
                u'  {0: >2.0f}  '.format(fact.delta.total_seconds() / 60),
                (get_colour(fact.category), delta_graph),
                u'  ',
                fact.activity,
            ])
            self.factlog.body.append(text)

    def refresh_stats(self, facts):
        # Summary by categories
        self.stats.body[:] = []
        categories = {}
        if not facts:
            return
        for fact in facts:
            categories.setdefault(fact.category, datetime.timedelta(0))
            categories[fact.category] += fact.delta
        padding = max(len(x) for x in categories) + 1
        for category in sorted(categories, key=lambda k: categories[k]):
            total_seconds = categories[category].total_seconds()
            #tmpl = r'{category} {delta_graph}'.format()
            text = urwid.Text('{category: >{padding}} {delta_graph}'.format(
                    category = category,
                    delta_graph = get_delta_graph(total_seconds),
                    padding = padding,
            ))
            colour = get_colour(category)
            text = urwid.AttrWrap(text, colour)
            self.stats.body.append(text)

    def refresh_current_activity(self, facts):
        # Current activity
        now_text, now_delta = 'no activity', ''
        if facts:
            fact = facts[0]
            if fact.end_time:
                # display untracked time after last logged fact
                end_delta = datetime.datetime.now() - fact.end_time
                now_delta = u'({end_delta} minutes not tracked) '.format(
                    end_delta = end_delta.seconds / 60,
                )
            else:
                # display current activity
                now_text = u' {f.category}: {f.activity}'.format(f=fact)
                now_delta = u'{delta_graph} {f.delta} '.format(
                    f = fact,
                    delta_graph = get_delta_graph(fact.delta.total_seconds()),
                )

        head = urwid.Columns([
            urwid.Text(now_text),
            urwid.Text(now_delta, align='right')
        ])
        head = urwid.AttrWrap(head, 'header')
        self.frame.header = head

    def refresh_data(self):

        facts = list(reversed(self.storage.get_todays_facts()))

        self.refresh_factlist(facts)
        self.refresh_stats(facts)
        self.refresh_current_activity(facts)


    def render(self):
        return self.frame

    def resume_activity(self):
        facts = self.storage.get_todays_facts()   # XXX what if not today?
        if not facts:
            return
        fact = facts[-1]
        fact.end_time = None
        self.storage.update_fact(fact.id, fact)#, extra_description=comment)
        self.refresh_data()

    def stop_activity(self):
        self.storage.stop_tracking()
        self.refresh_data()

    def handle_input(self, key):
        if key in ('enter', 'tab'):
            # shift focus to the next widget
            widget, pos = self.factlog.body.get_focus()
            self.factlog.body.set_focus(pos + 1)
        elif key in ('f8', 'esc', 'q'):
            raise urwid.ExitMainLoop()
        #elif key in ('f5'):
        #    self.refresh_data()
        elif key == 'r':
            self.resume_activity()
        elif key == 'x':
            self.stop_activity()


view = HamsterDayView()
view.run()
