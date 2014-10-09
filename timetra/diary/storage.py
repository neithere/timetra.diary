
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
#    along with Timer.  If not, see <http://gnu.org/licenses/>.
#
"""
Storage
=======
"""
from collections import OrderedDict
import datetime
import os
#from warnings import warn

import monk
import yaml


from . import caching, models


__all__ = ['Storage']


#--- YAML STUFF
#
#


# http://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
class Literal(str):
    pass

def _represent_literal(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


def _represent_dictorder(self, data):
    return self.represent_mapping('tag:yaml.org,2002:map', data.items())


def configure_yaml():
    yaml.add_representer(Literal, _represent_literal)
    yaml.add_representer(OrderedDict, _represent_dictorder)


configure_yaml()


#
#
#--- / YAML STUFF


def _prepare_value_for_yaml(value):
    """
    Returns a YAML-friendly representation of given value.  Normally it just
    returns the value as is; a string containing `\n` is wrapped in
    :class:`Literal`.

    Preconditions:

    * a representer for :class:`Literal` is registered in the `yaml` library.
      This is normally done by calling :func:`configure_yaml`.

    """
    if value and isinstance(value, str) and '\n' in value:
        # dump multi-line fields as literal blocks (the "|+" stuff)
        return Literal(value)
    return value


def _prepare_fact_for_yaml(fact_dict):
    """
    Returns a YAML-friendly representation of given fact by doing the following:

    1) builds an `OrderedDict` for given data;
    2) calls :func:`_prepare_value_for_yaml` for each value.

    Preconditions:

    * the `structure` attribute of class :class:`~timetra.diary.models.Fact`
      is an `OrderedDict`;
    * a representer for :class:`OrderedDict` is registered in the `yaml`
      library.  This is normally done by calling :func:`configure_yaml`.

    :param fact_dict:
        A `dict`-like object representing the fact.

    """

    fact_od = OrderedDict()

    # add known keys
    for k in models.Fact.structure:
        if k not in fact_dict:
            continue
        value = fact_dict[k]
        fact_od[k] = _prepare_value_for_yaml(value)

    # add unknown keys (to be validated elsewhere)
    for k in fact_dict:
        if k not in models.Fact.structure:
            fact_od[k] = fact_dict[k]

    return fact_od


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
        for key, pattern in filters.items():
            pattern = pattern.lower()

            # support multiple values per key
            value = fact.get(key)
            if isinstance(value, list):
                values = value
            else:
                values = [value]

            if not any(pattern in str(v or '').lower() for v in values):
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
                try:
                    month_num = int(month)
                except ValueError as e:
                    print('Bogus month dir/file name: {} — {}'.format(
                        os.path.join(year_path, month), e))
                    continue

                if since and year_num == since.year and month_num < since.month:
                    continue
                if until and year_num == until.year and month_num > until.month:
                    break

                month_path = os.path.join(year_path, month)

                for day_file in sorted(os.listdir(month_path)):
                    _day, _ext = os.path.splitext(day_file)
                    if _ext != '.yaml':
                        continue
                    try:
                        day_num = int(_day)
                    except ValueError as e:
                        # example: VIM puts a '.31.yaml' file backup while editing
                        print('Bogus day filename: {} — {}'.format(
                            os.path.join(month_path, day_file), e))
                        continue

                    if since and year_num == since.year and month_num == since.month and day_num < since.day:
                        continue
                    if until and year_num == until.year and month_num == until.month and day_num > until.day:
                        break

                    yield os.path.join(month_path, day_file)

    def collect_facts(self, since=None, until=None, filters=None,
                      hint_reverse=False):
        day_paths = self._collect_day_paths(since=since, until=until)
        if hint_reverse:
            # optimization hint
            day_paths = reversed(list(day_paths))
        for day_path in day_paths:
            day_facts = self.get_cached_day_file(day_path)
            if hint_reverse:
                day_facts = reversed(day_facts)
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

    def _load_from_file(self, file_path):
        if os.path.exists(file_path):
            with open(file_path) as f:
                return yaml.load(f)
        return []

    def _dump_to_file(self, file_path, facts, create=False):
        if not os.path.exists(file_path):
            # make sure the year and month dirs are created
            month_dir = os.path.dirname(file_path)
            if not os.path.exists(month_dir):
                os.makedirs(month_dir)

        fact_ods = []
        for fact in facts:
            # insert defaults
            monk.merge_defaults(models.Fact.structure, fact)

            # validate structure and types
            monk.validate(models.Fact.structure, fact)

            # ensure field order and stuff
            fact_od = _prepare_fact_for_yaml(fact)

            fact_ods.append(fact_od)

        with open(file_path, 'w') as f:
            yaml.dump(fact_ods, f, allow_unicode=True, default_flow_style=False)

    def add(self, fact):
        # we expect the `fact` dictionary to be already validated
        file_path = self.get_file_path_for_day(fact['since'])
        facts = list(self._load_from_file(file_path) or [])

        for i, other in enumerate(facts):
            if fact['since'] < other['since']:
                facts.insert(i, fact)
                break
        else:
            facts.append(fact)

        self._dump_to_file(file_path, facts, create=True)

        return file_path

    def get(self, date_time):
        facts = self.collect_facts(since=date_time.date(),
                                   until=date_time.date())
        for fact in facts:
            if fact['since'] == date_time:
                return fact

        raise FactNotFound(date_time)

    def delete(self, since, activity):
        file_path = self.get_file_path_for_day(since)
        facts = self._load_from_file(file_path)

        for i, fact in enumerate(facts):
            if fact['since'] == since and fact['activity'] == activity:
                facts.pop(i)
                break
        else:
            raise FactNotFound('{} {}'.format(since, activity))

        self._dump_to_file(file_path, facts, create=False)

    def update(self, old_fact, kwargs):
        # make sure it exists
        existing_fact = self.get(old_fact['since'])
        assert existing_fact['activity'] == old_fact['activity']

        new_fact = models.Fact(old_fact, **kwargs)
        new_fact.validate()

        # If date_time changes, we may need to delete from one file and
        # write to another one (i.e. 2 files are updated).
        #
        # To support this case without extra logic we simply delete old record
        # and then add a new one.
        #
        # The problem is that there's no transactions here; we cannot even
        # add before deleting because if the fact stays at the same place,
        # we'd have two similar facts one after another and it would be hard
        # to tell which one should be deleted.

        self.delete(old_fact['since'], old_fact['activity'])
        self.add(new_fact)

    def get_latest(self):
        return self.collect_facts(hint_reverse=True).__next__()

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

    def find_overlapping_facts(self, since, until, days_before=1):
        """
        Returns a generator that yields facts overlapping given boundaries.
        This *may* behave as `find()` but it is intended to be more precise
        (down to seconds instead of days).

        :param since: date and time when the gap starts
        :param until: date and time when the gap ends
        :param days_before: the number of days prior to `since` to look at

        By default the check only spans the `since..until` period and the day
        before `since`.  Thus, facts spanning more than one day (and beginning
        before `since - 1 day`) may not be detected.  Tune `days_before` to
        change this behaviour.
        """
        _since = since - datetime.timedelta(days=days_before)
        facts = self.find(since=_since, until=until)
        for fact in facts:
            if fact.since < since and fact.until <= until:
                continue
            if fact.since >= since and fact.until > until:
                continue
            yield fact

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
            # okay, too many; let's exclude empty categories
            candidates_with_categories = [c for c in candidates if c[1]]
            if candidates_with_categories:
                candidates = candidates_with_categories

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
'''
