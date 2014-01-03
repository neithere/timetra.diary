#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Prints summary on given activity + tags.
Uses our Hamster ETL API instead of Hamster's built-in query API for better
accuracy (in fact, the native tools yield utter crap).
"""
import datetime

from argh import command, dispatch_command

from etl_hamster import etl, facts_to_dicts, get_facts, _curry


def collect_and_print_summary(items, activity=None, tags=[]):
    total_found = 0
    total_spent = datetime.timedelta()
    longest_duration = None
    seen_workdays = {}
    first_date = last_date = None

    for fact in items:
        match_activity = fact['activity'] == activity
        match_tags = bool(set(fact.get('tags', [])) & set(tags))
        if not (match_activity or match_tags):
            continue

        if not first_date:
            first_date = fact['since'].date()
        last_date = fact['until'].date()

        delta = fact['until'] - fact['since']
        total_found += 1
        total_spent += delta
        seen_workdays[fact['since'].date()] = 1

        if not longest_duration or longest_duration < delta:
            longest_duration = delta

    total_delta = last_date - first_date
    total_days = total_delta.days
    total_workdays = len(seen_workdays)
    total_minutes = total_spent.total_seconds() / 60
    total_hours = total_minutes / 60

    print u'--- FOUND FACTS: ---'
    print u'  {0} -- {1}  ({2} days)'.format(first_date, last_date, total_days)
    print
    print u'   total facts: {0}'.format(total_found)
    print u'    time spent: {0}'.format(total_spent)
    print u'  avg duration: {0:.1f}h'.format(
        total_hours / (total_found or 1))
    print u'       per day: {0:.1f}h'.format(
        total_hours / total_days)
    # "workdays" here are dates when given activity was started at least once.
    print u'   per workday: {0:.1f}h  (i.e. not counting empty days)'.format(
        total_hours / (total_workdays or 1))
    print u'       longest: {0:.1f}h'.format(
        longest_duration.total_seconds() / 60 / 60 if longest_duration else 0)
    print u'     frequency: facts occur every {0:.1f} day(s)'.format(
        float(total_days) / total_workdays)
    print u'---'


@command
def show_summary(activity=None, tags=None):
    """ show_summary('mary', 'with-mary')
    """
    assert activity or tags
    tags = ','.split(tags) if tags else []

    extract = get_facts
    transform = facts_to_dicts
    load = _curry(collect_and_print_summary, activity=activity, tags=tags)
    etl(extract, transform, load)


if __name__ == '__main__':
    dispatch_command(show_summary)
