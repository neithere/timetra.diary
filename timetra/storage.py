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
"""
import datetime
import os
from warnings import warn


from timetra import utils
from timetra import models
from timetra import caching


__all__ = ['collect_facts']


def _collect_day_paths(root, since=None, until=None):

    for year in sorted(os.listdir(root)):
        year_num = int(year)

        if since and year_num < since.year:
            continue
        if until and year_num > until.year:
            break

        year_path = os.path.join(root, year)

        for month in sorted(os.listdir(year_path)):
            month_num = int(month)

            if since and year_num == since.year and month_num < since.month:
                continue
            if until and year_num == until.year and month_num > until.month:
                print('break')
                break

            month_path = os.path.join(year_path, month)

            for day in sorted(os.listdir(month_path)):
                day_num = int(os.path.splitext(day)[0])

                if since and year_num == since.year and month_num == since.month and day_num < since.day:
                    continue
                if until and year_num == until.year and month_num == until.month and day_num > until.day:
                    break

                yield os.path.join(month_path, day)

#paths = []
#path = '../timetra/data/facts_by_year_month_day/2013/01/17.yaml'


def _is_fact_matching(fact, filters):
    if not filters:
        return True
    for key, value in filters.items():
        if fact.get(key) != value:
            return False
    return True


def collect_facts(root_dir, since=None, until=None, filters=None):
    for day_path in _collect_day_paths(root_dir, since=since, until=until):
        day_facts = caching.get_cached_yaml_file(day_path, models.Fact)
        for fact in day_facts:
            if _is_fact_matching(fact, filters):
                yield fact


#--------------
# Auxiliary API
#

class StorageError(Exception):
    """ Base class for all storage-related exceptions.
    """


class ActivityMatchingError(StorageError):
    """ Raised if no known activity unambiguously matches given pattern.
    """


class UnknownActivity(ActivityMatchingError):
    """ Raised if no activity in the storage corresponds to given pattern.
    """


class AmbiguousActivityName(ActivityMatchingError):
    """ Raised if more than a single known activity matches given pattern.
    """


class CannotCreateFact(StorageError):
    pass


class FactNotFound(StorageError):
    pass


class FactsInConflict(StorageError):
    pass


def get_hamster_activity(mask):
    return resolve_activity(mask)


def resolve_activity(mask):
    """Given a mask, finds the (single) matching activity and returns its full
    name along with category name. Raises AssertionError if no matching
    activity could be found or more than item matched.

    :return: {'category': CATEGORY, 'activity': ACTIVITY}
    """
    seen = {}
    for fact in collect_facts():
        pair = fact.activity, fact.category
        seen[pair] = seen.get(pair, 0) + 1

    # look for exact matches
    sorted_seen = [x for x in sorted(seen, key=seen.get, reverse=True)]
    candidates = [d for d in sorted_seen if mask == d[0]]
    if not candidates:
        # look for partial matches
        candidates = [d for d in sorted_seen if mask in d[0]]
    if not candidates:
        raise UnknownActivity('unknown activity {0}'.format(mask))
    if 1 < len(candidates):
        raise AmbiguousActivityName('ambiguous name, matches:\n{0}'.format(
            '\n'.join((u'  - {category}: {name}'.format(**x)
                       for x in sorted(candidates)))))
    return candidates[0]


def parse_activity(activity_mask):
    activity, category = 'work', None
    if activity_mask:
        if '@' in activity_mask:
            # hamster-like notation
            activity, category = activity_mask.split('@')
        else:
            return resolve_activity(activity_mask)
    return {'activity': activity, 'category': category}


def _to_date(date_or_datetime):
    if isinstance(date_or_datetime, datetime.datetime):
        return date_or_datetime.date()
    else:
        return date_or_datetime


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

    date = _to_date(date)
    end_date = _to_date(end_date)

    results = hamster_storage.get_facts(date, end_date, search_terms)
    return [dict_to_fact(f) for f in results]


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
    facts = get_facts_for_day(now.date())
    if not facts:
        start = now - datetime.timedelta(days=max_age_days-1)
        facts = get_facts_for_day(start, now)
    return dict_to_fact(facts[-1]) if facts else None


def get_current_fact():
    fact = get_latest_fact()
    if fact and not fact.end_time:
        return fact


def get_prev_end_time(require=False):
    prev = get_latest_fact()
    if not prev:
        raise FactNotFound('Cannot find previous activity.')
    if require and not prev.end_time:
        raise FactsInConflict('Another activity is running.')
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
             end_time=None, dry_run=False):
    activity, category = parse_activity(loose_name)
    h_act = u'{activity}@{category}'.format(activity=activity,
                                            category=category)
    fact = Fact(h_act, tags=tags, description=description,
                start_time=start_time, end_time=end_time)

    # sanity checks

    if fact.end_time < fact.start_time:
        raise ValueError('start time must be earlier than end time; '
                         'got {0} and {1}'.format(fact.start_time,
                                                  fact.end_time))

    if datetime.datetime.now() < fact.end_time:
        raise ValueError('end time must not be in the future')

    if not dry_run:
        fact.id = hamster_storage.add_fact(fact.serialized_name(), start_time, end_time)
        if not fact.id:
            raise CannotCreateFact(u'Another activity may be running')
    return fact


def update_fact(fact, dry_run=False, extra_tags=None, extra_description=None,
                **kwargs):
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
    if not dry_run:
        hamster_storage.update_fact(fact.id, fact.serialized_name(),
                                    fact.start_time, fact.end_time)
