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
#import datetime
import os
#from warnings import warn
import yaml


#from timetra import utils
from timetra import models
from timetra import caching


__all__ = ['Storage']


class YamlBackend:
    "Provides low-level access to the facts database"

    def __init__(self, data_dir, cache_dir):
        self.data_dir = data_dir
        self.cache = caching.Cache(cache_dir)

    def get_cached_day_file(self, path):
        return self.cache.get_cached_yaml_file(path, model=models.Fact)

    def _is_fact_matching(self, fact, filters):
        if not filters:
            return True
        for key, value in filters.items():
            if value not in (fact.get(key) or ''):
                return False
        return True

    def _collect_day_paths(self, since=None, until=None):

        for year in sorted(os.listdir(self.data_dir)):
            year_num = int(year)

            if since and year_num < since.year:
                continue
            if until and year_num > until.year:
                break

            year_path = os.path.join(self.data_dir, year)

            for month in sorted(os.listdir(year_path)):
                month_num = int(month)

                if since and year_num == since.year and month_num < since.month:
                    continue
                if until and year_num == until.year and month_num > until.month:
                    break

                month_path = os.path.join(year_path, month)

                for day in sorted(os.listdir(month_path)):
                    day_num = int(os.path.splitext(day)[0])

                    if since and year_num == since.year and month_num == since.month and day_num < since.day:
                        continue
                    if until and year_num == until.year and month_num == until.month and day_num > until.day:
                        break

                    yield os.path.join(month_path, day)

    def collect_facts(self, since=None, until=None, filters=None):
        for day_path in self._collect_day_paths(since=since, until=until):
            day_facts = self.get_cached_day_file(day_path)
            for fact in day_facts:
                if self._is_fact_matching(fact, filters):
                    yield fact

    def get_file_path_for_day(self, date):
        return os.path.join(
            self.data_dir,
            str(date.year),
            '{:0>2}'.format(date.month),
            '{:0>2}.yaml'.format(date.day),
        )

    def add(self, fact):
        # we expect the `fact` dictionary to be already validated
        file_path = self.get_file_path_for_day(fact['since'])
        if os.path.exists(file_path):
            with open(file_path) as f:
                facts = yaml.load(f)
        else:
            # make sure the year and month dirs are created
            month_dir = os.path.dirname(file_path)
            if not os.path.exists(month_dir):
                os.makedirs(month_dir)
            facts = []

        inserted = False
        for i, other in enumerate(facts):
            if fact['since'] < other['since']:
                facts.insert(i, fact)
                inserted = True
                break
        if not inserted:
            facts.append(fact)

        with open(file_path, 'w') as f:
            yaml.dump(facts, f)

        return file_path

    def find(self, since=None, until=None, activity=None, description=None, tag=None):
        filters = {}
        if activity:
            filters['activity'] = activity
        if description:
            filters['description'] = description
        if tag:
            filters['tags'] = tag
        return self.collect_facts(since=since, until=until, filters=filters)


class Storage:
    "Provides high-level access to the facts database"

    def __init__(self, backend):
        self.backend = backend

    def get(self, date_time):
        return self.backend.get(date_time)

    def get_latest(self):
        return self.backend.get_latest()

    def find(self, since=None, until=None, activity=None, description=None,
             tag=None):
        return self.backend.find(since=since, until=until, activity=activity,
                                 description=description, tag=tag)

    def add(self, fact):
        """Adds given fact to the database.  Returns whatever the backend
        returned (presumably the fact ID or something that can find/identify
        the newly created record).
        """
        # TODO [not only] Monk-powered validation
        fields = ('activity', 'since', 'until', 'description', 'tags')
        assert all(x in fact for x in fields)

        # TODO: identify and solve conflicts
        #fact.validate()
        #if fact.since in self.backend:
        #    # TODO: check overlap
        #    raise FactsInConflict('another fact starts with this date and time')
        #self.backend[fact.since] = fact
        return self.backend.add(fact)

    def update(self, fact, values):
        assert fact
        assert values
        return self.backend.update(fact, values)


    def delete(self, spec):
        assert spec.since, spec.activity
        fact = self.get(spec.since)
        assert fact
        assert fact.activity == spec.activity
        self.backend.delete(since=fact.since, activity=fact.activity)

    def resolve_activity(self, mask):
        """Given a mask, finds the (single) matching activity and returns its full
        name along with category name. Raises AssertionError if no matching
        activity could be found or more than item matched.

        :return: {'category': CATEGORY, 'activity': ACTIVITY}
        """
        seen = {}
        for fact in self.find():
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
            raise AmbiguousActivityName('ambiguous name, matches: {0}'.format(
                '; '.join(('{1}/{0}'.format(*x)
                        for x in sorted(candidates)))))
        activity, category = candidates[0]
        return {'activity': activity, 'category': category}

    def get_known_activities(self):
        return self.backend.get_known_activities()


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


'''
def get_hamster_activity_candidates(query):
    activities = hamster_storage.get_activities()
    if query:
        # look for exact matches
        candidates = [d for d in activities if query == d['name']]
        if not candidates:
            # look for partial matches
            candidates = [d for d in activities if query in d['name']]
    else:
        candidates = activities
    return [{'name':     unicode(c['name']),
             'category': unicode(c['category'])} for c in candidates]


def get_hamster_activity(activity):
    """Given a mask, finds the (single) matching activity and returns its full
    name along with category name. Raises AssertionError if no matching
    activity could be found or more than item matched.

    :return: {'category': CATEGORY, 'activity': ACTIVITY}
    """
    candidates = get_hamster_activity_candidates(activity)

    if not candidates:
        raise UnknownActivity('unknown activity {0}'.format(mask))
    if 1 < len(candidates):
        raise AmbiguousActivityName('ambiguous name, matches:\n{0}'.format(
            '\n'.join((u'  - {category}: {name}'.format(**x)
                       for x in sorted(candidates)))))
    first_candidate = candidates[0]
    return first_candidate['name'], first_candidate['category']


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
'''
