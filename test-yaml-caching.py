#!/usr/bin/env python
# coding: utf-8

# python
import datetime

# app
from timetra.storage import collect_facts


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
