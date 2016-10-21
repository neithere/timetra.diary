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
Reporting
=========
"""
from confu import Configurable
from terminaltables import SingleTable

from ..storage import Storage
from .. import formatdelta
from .drift import show_drift, show_weekly_averages
from .prediction import predict_next_occurence


class Reporting(Configurable):
    needs = {
        'storage': Storage,
    }

    def drift(self, activity='sleep', days=7, shift=False,
              colorize_weekends=False):
        return show_drift(self['storage'], activity, days, shift,
                          colorize_weekends)

    def weekly(self, activity='sleep', weeks=4):
        return show_weekly_averages(self['storage'], activity, weeks)

    def predict(self, activity):
        """ Predicts next occurence of given activity.
        """
        guess = predict_next_occurence(self['storage'], activity)
        data = [
            ['start', 'end', 'duration', 'ETA'],
        ]
        data.append([
            guess['start'].strftime('%Y-%m-%d %H:%M'),
            guess['end'].strftime('%Y-%m-%d %H:%M'),
            formatdelta.render_delta(guess['duration']),
            '{0}{1}'.format('-' if guess['eta_is_negative'] else '+',
                            formatdelta.render_delta(guess['eta'])),
        ])
        return SingleTable(data).table
