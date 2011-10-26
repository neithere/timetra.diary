#!/usr/bin/env python2
"""
Extract-Transform-Load for Hamster
==================================

:author: Andrey Mikhaylenko
:dependencies:
    * Hamster_ (see packages for your distro, e.g. ``hamster-applet``)
    * argh_
    * PyYAML_ (for :func:`dump_yaml`)
    * pymongo_ (for :func:`dump_mongo`)

.. _Hamster: http://projecthamster.wordpress.com
.. _PyYAML: http://pyyaml.org/wiki/PyYAMLDocumentation
.. _pymongo: http://pypi.python.org/pypi/pymongo/
.. _argh: http://pypi.python.org/pypi/argh/

Extracts facts from your local Hamster database, converts them to plain Python
``dict`` objects (omitting empty attributes) and does with them whatever you
need (by default dumps the whole list as YAML; be careful).
"""
import datetime
from functools import partial
from hamster.client import Storage
import pymongo
import yaml


#--- Extractors

def get_facts():
    storage = Storage()
    end_date = datetime.date.today()
    start_date = datetime.datetime(2000,1,1) #end_date - datetime.timedelta(days=2)
    facts = storage.get_facts(date=start_date, end_date=end_date)
    return facts


#--- Transformers

def _fact_to_dict(fact):
    # Fact attributes:
    # activity  activity_id  category  date  delta  description  id
    # original_activity  serialized_name  start_time  tags
    data = {
        'activity': fact.activity,
        'category': fact.category,
        'start_time': fact.start_time,
        'end_time': fact.end_time,
        'hamster_fact_id': int(fact.id),
    }
    if fact.tags:
        data['tags'] = [unicode(tag) for tag in fact.tags]
    if fact.description:
        data['description'] = fact.description
    if fact.activity != fact.original_activity:
        data['original_activity'] = fact.original_activity
    return data


def facts_to_dicts(facts):
    return (_fact_to_dict(fact) for fact in facts)


#--- Loaders

def dump_yaml(items, path=None):
    assert path
    # the following is memory-consuming but I don't think there's a better way
    # to dump a generator to YAML
    items = list(items)
    with open(path, 'w') as f:
        print yaml.safe_dump(items, f)
    return len(items)


def dump_mongo(items, db='test', collection='hamster'):
    # TODO: use a tzrules file to properly convert local time to UTC
    conn = pymongo.Connection()
    c = conn[db][collection]
    print('  dropping collection {db}.{collection}'.format(**locals()))
    c.drop()
    print('  importing items to MongoDB...')
    cnt = 0
    for item in items:
        c.insert(item)
        cnt += 1
    return cnt


#--- Auxiliary functions

def _curry(func, *args, **kwargs):
    """ Same as :func:`functools.partial` but preserves ``__name__``.
    """
    f = partial(func, *args, **kwargs)
    f.__name__ = func.__name__
    return f


#--- Main ETL function

def etl(extract, transform, load, extract_kw={}, transform_kw={}, load_kw={}):
    print('Extracting with {0.__name__}...'.format(extract))
    extracted = extract(**extract_kw)
    print('Transforming with {0.__name__}...'.format(transform))
    transformed = transform(extracted, **transform_kw)
    print('Loading with {0.__name__}...'.format(load))
    loaded_cnt = load(transformed, **load_kw)
    print('Loaded {0} items.'.format(loaded_cnt))


if __name__ == '__main__':
    extract = get_facts
    transform = facts_to_dicts
    #load = curry(dump_yaml, path='hamster.yaml')
    load = _curry(dump_mongo, db='test', collection='hamster')

    etl(extract, transform, load)
