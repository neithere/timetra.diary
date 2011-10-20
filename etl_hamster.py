#!/usr/bin/env python2
"""
Extract-Transform-Load for Hamster
==================================

:author: Andrey Mikhaylenko
:dependencies:
    * ``hamster`` (see packages for your distro, e.g. ``hamster-applet``)
    * ``yaml``

Extracts facts from your local Hamster database, converts them to plain Python
``dict`` objects (omitting empty attributes) and does with them whatever you
need (by default dumps the whole list as YAML; be careful).
"""
import datetime
from hamster.client import Storage
import yaml


def get_facts():
    storage = Storage()
    end_date = datetime.date.today()
    start_date = datetime.datetime(2000,1,1) #end_date - datetime.timedelta(days=2)
    facts = storage.get_facts(date=start_date, end_date=end_date)
    return facts


def fact_to_dict(fact):
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
    return (fact_to_dict(fact) for fact in facts)


def dump_yaml(items):
    # the following is memory-consuming but I don't think there's a better way
    # to dump a generator to YAML
    items = list(items)
    print yaml.safe_dump(items)


def etl(extract, transform, load, extract_kw={}, transform_kw={}, load_kw={}):
    extracted = extract(**extract_kw)
    transformed = transform(extracted, **transform_kw)
    load(transformed, **load_kw)


if __name__ == '__main__':
    etl(get_facts, facts_to_dicts, dump_yaml)
