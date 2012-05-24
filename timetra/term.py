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
"""
===============
Terminal colors
===============
"""
from functools import partial


# http://stackoverflow.com/questions/287871/print-in-terminal-with-colors-using-python
# TODO: use http://pypi.python.org/pypi/blessings/
COLOR_BLUE = '\033[94m'
COLOR_GREEN = '\033[92m'
COLOR_WARNING = '\033[93m'
COLOR_FAIL = '\033[91m'
COLOR_ENDC = '\033[0m'


def colored(text, color):
    return u'{0}{1}{2}'.format(color, text, COLOR_ENDC)


success = partial(colored, color=COLOR_GREEN)
warning = partial(colored, color=COLOR_WARNING)
failure = partial(colored, color=COLOR_FAIL)
