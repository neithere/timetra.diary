#!/usr/bin/env python2
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
import urwid


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
