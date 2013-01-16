#!/usr/bin/env python
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
#    along with Timetra.  If not, see <http://gnu.org/licenses/>.
#

import io
import os

from setuptools import setup, find_packages

with io.open(os.path.join(os.path.dirname(__file__), 'README'), encoding='ascii') as f:
    readme = f.read()


from timetra import __version__


setup(
    # overview
    name             = 'timetra',
    description      = 'a time tracking application and library',
    long_description = readme,

    # technical info
    version  = __version__,
    packages = find_packages(),
    provides = ['timetra'],
    install_requires = [
        'python>=2.6', 'argh>=0.22', 'hamster_sqlite>=0.2',
        # curses
        'urwid>=1.0',
        # web
        'flask>=0.9', 'wtforms>=1.0',
    ],
    include_package_data = True,
    zip_safe = False,

    # copyright
    author   = 'Andrey Mikhaylenko',
    author_email = 'neithere@gmail.com',
    license  = 'GNU Lesser General Public License (LGPL), Version 3',

    # more info
    url          = 'http://bitbucket.org/timetra/timetra/',
    download_url = 'http://bitbucket.org/timetra/timetra/src/',

    # categorization
    keywords     = ('cli command line time tracking timer diary'),
    classifiers  = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Programming Language :: Python',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
