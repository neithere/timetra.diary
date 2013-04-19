#!/usr/bin/env python
# coding: utf-8

# python
import datetime
import os

# 3rd party
from monk.validation import optional

# app
import caching


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

model = {
    'category': str,
    'activity': str,
    'since': datetime.datetime,
    'until': datetime.datetime,
    'tags': optional([str]),
    'hamster_fact_id': optional(int),
    'description': optional(str),
}


def _is_fact_matching(fact, filters):
    if not filters:
        return True
    for key, value in filters.items():
        if fact.get(key) != value:
            return False
    return True


def collect_facts(root_dir, since=None, until=None, filters=None):
    for day_path in _collect_day_paths(root_dir, since=since, until=until):
        day_facts = caching.get_cached_yaml_file(day_path, model)
        for fact in day_facts:
            if _is_fact_matching(fact, filters):
                yield fact


if __name__ == '__main__':
    ROOT = '../timetra/data/facts_by_year_month_day/'

    #since = None
    #since = datetime.date(2012, 1, 1)
    since = datetime.date.today() - datetime.timedelta(days=7)

    until = None
    #until = datetime.date(2012, 1, 2)

    filters = {
        'activity': 'timetra',
    }
    items = collect_facts(ROOT, since=since, until=until, filters=filters)
    items = list(items)
    for item in items:
        print(item.since.strftime('%Y-%m-%d %H:%M'),
              item.category, item.activity,
              '#' + ', #'.join([x for x in item.get('tags', []) if x != 'timetra-log']))
        if 'description' in item:
            print('   ', item.description)
            print()
    print('Found', len(items), 'items')

#total_cnt = 0
#match_cnt = 0
#for path in _collect_day_paths(ROOT): #, since=datetime.date(2012,1,1)):
#    #print(path)
#    xs = caching.get_cached_yaml_file(path, model)
#    total_cnt += len(xs)
#    for x in xs:
#        if x['activity'] == 'argh':
#            match_cnt += 1
#print('Total records in the database:', total_cnt)
#print('Matching records:', match_cnt)
