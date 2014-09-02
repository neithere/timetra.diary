#!/usr/bin/env python
# coding: utf-8
# PYTHON_ARGCOMPLETE_OK
#
#    Timetra is a time tracking application and library.
#    Copyright © 2010-2014  Andrey Mikhaylenko
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
~~~~~~~~~~~~~~~~~~~
Timetra Application
~~~~~~~~~~~~~~~~~~~

:author: Andrey Mikhaylenko

"""
import os

import argh
import yaml

from .storage import Storage, YamlBackend

from .diary import Diary
from .reporting import Reporting
from .timer import Timing
from .curses import TUI
#from .cli_old import LegacyCLI


CONF_FILE = os.getenv('TIMETRA_DIARY_CONFIG', 'conf.yaml')


def _init_storage():
    with open(CONF_FILE) as f:
        conf = yaml.load(f)
    backend = YamlBackend(**conf['backend'])
    storage = Storage(backend)
    return storage


def main():
    storage = _init_storage()

    p = argh.ArghParser()

    diary = Diary({'storage': storage})
    reporting = Reporting({'storage': storage})
    timing = Timing({'storage': storage})
    tui = TUI({'storage': storage})
    #old_cli = LegacyCLI({'storage': storage})

    command_tree = {
        None: diary.commands,
        'report': [
            reporting.drift
        ],
        'timing': [
            timing.pomodoro
        ],
        'tui': [
            tui.run
        ],
        #'old':    old_cli.commands,
    }
    for namespace, commands in command_tree.items():
        p.add_commands(commands, namespace=namespace)

    p.dispatch()


if __name__ == '__main__':
    main()
