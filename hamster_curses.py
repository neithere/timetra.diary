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
import hamster.client
import shlex
import urwid

import timer


# TODO: move to config
#
# TODO: procrastination is not a property of an activity on its own;
#       it's rather a property of an activity in the context of current
#       priorities and the possibilities to tackle higher-priority tasks.
#       That is, the user is procrastinating if current activity has lower
#       priority than a number of planned actions doable right now.
#
#       In short:
#
#       * a "good" activity is bound to a high-priority task (HPT);
#       * a "bad" activity is anything that prevents doing a HPT that is
#         relevant in given context;
#       * if there's no relevant HPT at the moment, any activity is OK.
#
CATEGORY_COLOURS = {
    # "desirable" categories
    'productive': ('education', 'errands', 'self-care', 'work', 'maintenance'),
    # "undesirable" categories
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


class TabNavigatedFrame(urwid.Frame):
    """ A :class:`urwid.Frame` that supports changing focus between its parts
    on :key:`tab`.
    """
    def keypress(self, size, key):
        switch_order = {
            'tab': {
                'header': 'body',
                'body': 'footer',
                'footer': 'header',
            },
            'shift tab': {
                'header': 'footer',
                'body': 'header',
                'footer': 'body',
            }
        }
        if key not in switch_order:
            return self.__super.keypress(size, key)
        next_part = switch_order[key][self.focus_part]
        self.set_focus(next_part)


class History(list):
    """ A list that remembers current position::

        >>> h = History()
        >>> h
        <History [] at 0>
        >>> h.up()
        >>> h.down()
        >>> h.append('a')
        >>> h
        <History ['a'] at 0>
        >>> h.up()
        'a'
        >>> h.down()
        'a'
        >>> h.append('b')
        >>> h
        <History ['a', 'b'] at 1>
        >>> h.up()   # first up
        'a'
        >>> h.up()   # second up
        'a'
        >>> h.down() # first down
        'b'
        >>> h.down() # second down
        'b'

    """
    def __init__(self, *args):
        super(History, self).__init__(*args)
        self.position = len(self) - 1 if self else 0

    def __repr__(self):
        return '<History {content} at {position}>'.format(
            content = super(History, self).__repr__(),
            position = self.position
        )

    def append(self, item):
        if not item:
            return
        if self and self[-1] == item:
            return
        super(History, self).append(item)
        # reset index to the last added value
        self.position = len(self) - 1

    def up(self):
        if not self:
            return
        if 0 < self.position:
            self.position -= 1
        return self[self.position]

    def down(self):
        if not self:
            return
        if self.position < len(self) - 1:
            self.position += 1
        return self[self.position]

    def get_current(self):
        if not self:
            return
        return self[self.position]


class Prompt(urwid.Edit):
    """ A :class:`urwid.Edit` that can be submitted with :key:`enter` to a
    special handler function. The field is cleared on submit.

    Usage (with Python3 syntax for shorter example)::

        def handle_command(raw_command):
            command, *args = ' '.split(raw_command)
            if command == 'help':
                show_help(args)
            elif cmd == 'save':
                save_as(args[0])

        prompt = Prompt(u'>>> ', controller=handle_command)

    """
    def __init__(self, *args, **kwargs):
        self.handle_value = kwargs.pop('controller')
        # TODO: ideally, the history should be stored in a file to recover last
        #       command in case of a crash.
        self.history = History()
        self.__super.__init__(*args, **kwargs)

    def keypress(self, size, key):
        if key == 'enter':
            self.history.append(self.edit_text)
            handled = self.handle_value(self.edit_text)
            if handled:
                self.edit_text = u''
            return
        elif key == 'up':
            if not self.edit_text:
                self.edit_text = self.history.get_current()
            else:
                self.edit_text = self.history.up()
        elif key == 'down':
            if not self.edit_text:
                self.edit_text = self.history.get_current()
            else:
                self.edit_text = self.history.down()

        return self.__super.keypress(size, key)


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
        ('cmd_output',      'light blue',  'default'),
        ('prompt',          'light gray',  'default'),
    ]

    def __init__(self):
        self.storage = hamster.client.Storage()
        self.factlog = urwid.ListBox(urwid.SimpleListWalker([]))
        self.stats = urwid.ListBox(urwid.SimpleListWalker([]))

        prompt = Prompt(u':', controller=self.handle_prompt)
        self.prompt = urwid.AttrWrap(prompt, 'prompt')

        header = urwid.Text(u'(not refreshed)')
        body = urwid.Columns([
            self.factlog,
            self.stats,
        ])

        cmd_output = urwid.Text(u'')    # command output
        cmd_output = urwid.AttrWrap(cmd_output, 'cmd_output')

        footer = urwid.Pile([
            cmd_output,
            self.prompt
        ])
        self.frame = TabNavigatedFrame(header=header, body=body, footer=footer)
        self.refresh_data()

    def run(self):
        loop = urwid.MainLoop(self.render(), self.palette,
                              unhandled_input=self.unhandled_input)
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

    def quit(self):
        raise urwid.ExitMainLoop()

    def unhandled_input(self, key):
        if key == 'q':
            self.quit()
        elif key == ':':
            self.frame.set_focus('footer')

    def handle_timer_api(self, argv):
        parser = timer.ArghParser()
        parser.add_commands(timer.commands)

        response = u''
        try:
            response = parser.dispatch(argv, output_file=None)
        except SystemExit:
            pass
        self.show_command_output(response)  # + unicode(args))

    def show_command_output(self, value):
        self.frame.footer.widget_list[0].set_text(unicode(value))

    def handle_prompt(self, value):
        # shlex.split respects quotes.
        # It does not however support Unicode prior to Python 2.7.3.
        argv = shlex.split(value.encode('utf-8'))
        argv = [unicode(arg) for arg in argv]
        if not argv:
            self.show_command_output(u'')
            return
        command = argv[0]

        mapping = {
            'resume': self.resume_activity,
            'stop': self.stop_activity,
            'quit': self.quit,
            'timer': lambda: self.handle_timer_api(argv[1:]),
        }
        shortcuts = {
            'resume': ['r'],
            'stop': ['x'],
            'quit': ['q', 'exit'],
            'timer': ['t'],
        }
        for cmd, aliases in shortcuts.items():
            for alias in aliases:
                mapping[alias] = mapping[cmd]
        if command not in mapping:
            self.show_command_output(u'Unknown command "{0}"'.format(command))
            return
        func = mapping[command]
        func()
        return True


if __name__ == '__main__':
    view = HamsterDayView()
    view.run()
