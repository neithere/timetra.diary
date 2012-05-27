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
Prediction
==========

:copyright: Andy Mikhaylenko, 2012
:license: LGPL3

.. note:: TODO

   READ THIS: http://otexts.com/fpp/

"""
from datetime import datetime, timedelta

from timetra import storage


def avg_delta(deltas):
    deltas_as_seconds = [delta.total_seconds() for delta in deltas]
    avg_seconds = sum(deltas_as_seconds) / float(len(deltas_as_seconds))
    return timedelta(seconds=avg_seconds)


def predict_next_occurence(activity, num_facts=4):
    """ Returns a tuple `(start_time, end_time)` of the next expected occurence
    of given activity.

    The algo is pretty dumb: take last N facts, take average gap between the
    facts to guess next occurrence relative to the last known fact, and use
    average duration as estimated duration.
    """
    all_facts = storage.get_facts_for_day(date=-1, search_terms=activity)
    recent_facts = all_facts[-num_facts:]
    if len(recent_facts) < 2:
        return None
    gaps = []
    prev = None
    for f in recent_facts:
        if prev:
            gaps.append(f.start_time - prev.end_time)
        prev = f
    est_gap = avg_delta(gaps)
    est_start = recent_facts[-1].end_time + est_gap
    est_duration = avg_delta(f.delta for f in recent_facts)
    est_end = est_start + est_duration

    now = datetime.now()
    if now < est_start:
        eta = est_start - now
        eta_is_negative = False
    else:
        eta = now - est_start
        eta_is_negative = True
    return {'start': est_start, 'end': est_end, 'duration': est_duration,
            'eta': eta, 'eta_is_negative': eta_is_negative}
