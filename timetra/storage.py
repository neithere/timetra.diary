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
Storage
=======

A thin wrapper around Hamster API.

Likely to be replaced by a standalone API with pluggable engines.

"""
import datetime
from warnings import warn


try:
    from hamster.client import Storage
    hamster_storage = Storage()
    try:
        from hamster.lib.stuff import Fact
    except ImportError:
        # legacy
        warn('using an old version of Hamster')
        from hamster.utils.stuff import Fact
except ImportError:
    warn('Hamster integration is disabled')
    hamster_storage = None
    Fact = None


from timetra import utils


__all__ = ['Fact', 'hamster_storage']


#--------------
# Auxiliary API
#

class ActivityMatchingError(Exception):
    """ Raised if no known activity unambiguously matches given pattern.
    """


class UnknownActivity(ActivityMatchingError):
    """ Raised if no activity in the storage corresponds to given pattern.
    """


class AmbiguousActivityName(ActivityMatchingError):
    """ Raised if more than a single known activity matches given pattern.
    """


class CannotCreateFact(Exception):
    pass


def get_hamster_activity(activity):
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
    if not candidates:
        raise UnknownActivity('unknown activity {0}'.format(activity))
    if 1 < len(candidates):
        raise AmbiguousActivityName('ambiguous name, matches:\n{0}'.format(
            '\n'.join((u'  - {category}: {name}'.format(**x)
                       for x in sorted(candidates)))))
    return [unicode(candidates[0][x]) for x in ['name', 'category']]


def parse_activity(activity_mask):
    activity, category = 'work', None
    if activity_mask:
        if '@' in activity_mask:
            return activity_mask.split('@')
        else:
            return get_hamster_activity(activity_mask)
    return activity, category


def get_facts_for_day(date=None, end_date=None, search_terms=''):
    """
    :param date:
        The earliest date to which facts may belong.

        * If `None`, current date is taken.
        * If ``-1``, a date 5 years ago is taken. Because why not, that's why.
          And also an `end_date` is set to current date if it was `None`.

    """
    if date == -1:
        # HACK: this selects the last 5 years (an arbitrarily "very early"
        # point in time which actually means "no left bound" but Hamster
        # requires that we specify one)
        date = (datetime.datetime.now() - datetime.timedelta(days=365*5)).date()
        end_date = end_date or datetime.datetime.now().date()
    elif date is None:
        date = datetime.datetime.now().date()
    assert hamster_storage
    return hamster_storage.get_facts(date, end_date, search_terms)


def get_latest_fact(max_age_days=2):
    """ Returns the most recently logged fact.

    :param max_age_days:
        the maximum age of the fact in days. ``1`` means "only today",
        ``2`` means "today or yesterday". Default is ``2``.

        Especially useful with Hamster which sometimes cannot find an activity
        that occured just a couple of minutes ago.

    """
    assert max_age_days
    now = datetime.datetime.now()
    facts = get_facts_for_day(now)
    if not facts:
        start = now - datetime.timedelta(days=max_age_days-1)
        facts = get_facts_for_day(start, now)
    return facts[-1] if facts else None


def get_current_fact():
    fact = get_latest_fact()
    if fact and not fact.end_time:
        return fact


def get_prev_end_time(require=False):
    prev = get_latest_fact()
    if not prev:
        raise CommandError('Cannot find previous activity.')
    if require and not prev.end_time:
        raise CommandError('Another activity is running.')
    return prev.end_time


def get_start_end(since, until, delta):
    """
    :param since: `datetime.datetime`
    :param until: `datetime.datetime`
    :param delta: `datetime.timedelta`

    * since .. until
    * since .. since+delta
    * since .. now
    * until-delta .. until
    * prev .. until
    * prev .. prev+delta
    * prev .. now

    """
    prev = get_prev_end_time(require=True)
    now = datetime.datetime.now()

    if since and until:
        return since, until
    elif since:
        if delta:
            return since, since+delta
        else:
            return since, now
    elif until:
        if delta:
            return until-delta, until
        else:
            return prev, until
    elif delta:
        return prev, prev+delta
    else:
        return prev, now


def add_fact(loose_name, tags=None, description='', start_time=None,
             end_time=None):
    activity, category = parse_activity(loose_name)
    h_act = u'{activity}@{category}'.format(activity=activity,
                                            category=category)
    fact = Fact(h_act, tags=tags, description=description,
                start_time=start_time, end_time=end_time)
    fact.id = hamster_storage.add_fact(fact)
    if not fact.id:
        raise CannotCreateFact(u'Another activity may be running')
    return fact


def update_fact(fact, extra_tags=None, extra_description=None, **kwargs):
    for key, value in kwargs.items():
        setattr(fact, key, value)
    if extra_description:
        delta = datetime.datetime.now() - fact.start_time
        new_desc = u'{0}\n\n(+{1}) {2}'.format(
            fact.description or '',
            utils.format_delta(delta),
            extra_description
        ).strip()
        fact.description = new_desc
    if extra_tags:
        fact.tags = list(set(fact.tags + extra_tags))
    hamster_storage.update_fact(fact.id, fact)
