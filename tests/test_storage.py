# coding: utf-8

# python
from datetime import datetime  #, timedelta
import sys

# 3rd-party
import pytest

sys.path.insert(0, '.')

# this app
from timetra.models import Fact
from timetra.storage import Storage, UnknownActivity, AmbiguousActivityName


FIXTURE_ROOT = 'tests/fixtures'
CACHE_ROOT = 'tests/.testcache'


class MockBackend:
    def __init__(self, initial_data):
        self.data = initial_data

    def add(self, fact):
        self.data.append(fact)

    def find(self, since=None, until=None, activity=None, description=None,
             tag=None):
        for fact in self.data:
            # NOTE: overlapping facts (that partially fit) are not considered matching
            if since and fact.since < since:
                continue
            if until and fact.until > until:
                continue
            if activity and fact.activity != activity:
                continue
            if description and description not in fact.description:
                continue
            if tag and tag not in fact.tags:
                continue
            yield fact

    def get_latest(self):
        return list(sorted(self.data, key=lambda x: x.since))[-1]

    def get_known_activities(self):
        seen = {}
        for fact in self.data:
            pair = (fact.category, fact.activity)
            if pair not in seen:
                seen[pair] = 1
        return [{'activity': a, 'category': c} for c,a in sorted(seen)]


class TestStorage:

    def setup_method(self, method):
        mock_backend = MockBackend([
            Fact(
                activity='timetra',
                category='foss',
                since=datetime(2012,5,24, 15,59),
                until=datetime(2012,5,24, 18,38),
                description='Renamed and refactored Timetra: the script becomes a project',
                tags=['in-ekb'],
            ),
            Fact(activity='walk',
                 category='errands',
                 since=datetime(2013,4,13, 4,28,54),
                 until=datetime(2013,4,13, 4,34,23),
                 description='walked the dog',
                 tags=['with-dog', 'in-ekb'],
                 hamster_fact_id=44047,
            )
        ])
        self.storage = Storage(backend=mock_backend)

    def test_find_facts(self):
        xs = list(self.storage.find())
        assert len(xs) == 2
        assert xs[0].activity == 'timetra'
        assert xs[0].description == 'Renamed and refactored Timetra: the script becomes a project'
        assert xs[0].since == datetime(2012,5,24, 15,59)

        assert xs[1].activity == 'walk'
        assert xs[1].since == datetime(2013,4,13, 4,28,54)

    def test_find_facts_since(self):
        xs = list(self.storage.find(since=datetime(2012,1,1)))
        assert len(xs) == 2

        xs = list(self.storage.find(since=datetime(2013,1,1)))
        assert len(xs) == 1

        xs = list(self.storage.find(since=datetime(2014,1,1)))
        assert len(xs) == 0

    def test_find_facts_until(self):
        xs = list(self.storage.find(until=datetime(2012,1,1)))
        assert len(xs) == 0

        xs = list(self.storage.find(until=datetime(2013,1,1)))
        assert len(xs) == 1

        xs = list(self.storage.find(until=datetime(2014,1,1)))
        assert len(xs) == 2

    def test_find_facts_activity(self):
        xs = list(self.storage.find(activity='whatchamacallit'))
        assert len(xs) == 0

        xs = list(self.storage.find(activity='walk'))
        assert len(xs) == 1
        assert 'with-dog' in xs[0].tags

    def test_find_facts_description(self):
        xs = list(self.storage.find(description='whatchamacallit'))
        assert len(xs) == 0

        xs = list(self.storage.find(description='dog'))
        assert len(xs) == 1

        xs = list(self.storage.find(description='the'))
        assert len(xs) == 2

    def test_find_facts_tags(self):
        xs = list(self.storage.find(tag='whatchamacallit'))
        assert len(xs) == 0

        xs = list(self.storage.find(tag='with-dog'))
        assert len(xs) == 1

        xs = list(self.storage.find(tag='in-ekb'))
        assert len(xs) == 2

    def test_get_fact_latest(self):
        fact = self.storage.get_latest()
        assert fact.activity == 'walk'

    @pytest.mark.xfail
    def test_get_fact_by_date_and_time(self):
        raise NotImplementedError

    def test_add_fact(self):
        xs = list(self.storage.find())
        assert len(xs) == 2

        self.storage.add(Fact(
            category='leisure',
            activity='party',
            since=datetime(2012,12,31, 23,55),
            until=datetime(2013,1,1, 1,30),
            description='Happy New Year!',
            tags=['with-friends']
        ))

        xs = list(self.storage.find())
        assert len(xs) == 3
        assert xs[-1].activity == 'party'

    @pytest.mark.xfail
    def test_update_fact(self):
        raise NotImplementedError

    @pytest.mark.xfail
    def test_delete_fact(self):
        raise NotImplementedError

    def test_resolve_activity(self):
        "Find a single activity matching given mask"

        with pytest.raises(UnknownActivity) as excinfo:
            self.storage.resolve_activity('x')

        with pytest.raises(AmbiguousActivityName) as excinfo:
            self.storage.resolve_activity('a')
        assert 'timetra' in str(excinfo)
        assert 'walk' in str(excinfo)

        assert self.storage.resolve_activity('wa') == {'category': 'errands', 'activity': 'walk'}

    def test_find_activities(self):
        "Collect distinct activity/category pairs from the data"
        activities = self.storage.get_known_activities()
        assert activities == [
            {'category': 'errands', 'activity': 'walk'},
            {'category': 'foss', 'activity': 'timetra'},
        ]

        self.storage.add(Fact(activity='music', category='create'))
        activities = self.storage.get_known_activities()
        assert activities == [
            {'category': 'create', 'activity': 'music'},
            {'category': 'errands', 'activity': 'walk'},
            {'category': 'foss', 'activity': 'timetra'},
        ]

        # activities with same names can co-exist in different categories
        self.storage.add(Fact(activity='music', category='consume'))
        activities = self.storage.get_known_activities()
        assert activities == [
            {'category': 'consume', 'activity': 'music'},
            {'category': 'create', 'activity': 'music'},
            {'category': 'errands', 'activity': 'walk'},
            {'category': 'foss', 'activity': 'timetra'},
        ]

