# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import namedtuple

from timetra.utils import to_datetime


Part = namedtuple('Part', 'value name')


#finite_parts = dict(
#    months = 12,
#    days = 30,
#    hours = 24,
#    minutes = 60,
#)

naive_i18n = dict(
    years = u'лет',
    months = u'месяцев',
    days = u'дней',
    hours = u'часов',
    minutes = u'минут'
)


def format_delta_part(part):
    label = naive_i18n[part.name]
    return u'{value} {label}'.format(label=label, value=part.value)


def timedelta_to_relativedelta(td):
    minutes = hours = days = months = years = 0

    rem = int(td.total_seconds())

    seconds = rem % 60
    rem = rem // 60

    minutes = rem % 60
    rem = rem // 60

    hours = rem % 60
    rem = rem // 60

    days = rem % 24
    rem = rem // 24

    months = rem % 30
    rem = rem // 30

    years = rem % 12

    return relativedelta(years=years, months=months, days=days, hours=hours,
                         minutes=minutes, seconds=seconds)


def render_delta(dates_or_delta, stack_depth=2):
    """
    Renders pretty delta.  Usage::

        render_delta(delta)
        render_delta((d1, d2))

    """
    if isinstance(dates_or_delta, (tuple, list)):
        dt1, dt2 = dates_or_delta
        dt1 = to_datetime(dt1)
        dt2 = to_datetime(dt2)
        delta = relativedelta(dt2, dt1)
    else:
        delta = timedelta_to_relativedelta(dates_or_delta)

    stack = []

    if delta.years:
        stack.append(Part(delta.years, 'years'))

    if delta.months:
        stack.append(Part(delta.months, 'months'))

    if delta.days:
        stack.append(Part(delta.days, 'days'))

    if delta.hours:
        stack.append(Part(delta.hours, 'hours'))

    if delta.minutes:
        stack.append(Part(delta.minutes, 'minutes'))

    stack_cut = stack[:stack_depth]

#    def _filter_parts():
#        for part in reversed(stack_cut):
#            if part.name in finite_parts:
#                threshold = finite_parts[part.name] / 3
#                if threshold < part.value:
#                    yield part
#            else:
#                yield part
#    parts = list(reversed(list(_filter_parts())))

    parts = stack_cut
    if parts:
        return ' '.join(format_delta_part(p) for p in parts)
    else:
        return u'меньше минуты'
        #return u'только что'


if __name__ == '__main__':
    dt = datetime
    print(render_delta(dt(2012,6,20,19,0,0), dt(2012,6,20,19,1,0)))
    print(render_delta(dt(2012,6,20,14,0,0), dt(2012,6,20,19,1,0)))
    print(render_delta(dt(2012,6,19,18,0,0), dt(2012,6,20,19,1,0)))
    print(render_delta(dt(2012,5,19,18,0,0), dt(2012,6,20,19,1,0)))
    print(render_delta(dt(2012,3,19,18,0,0), dt(2012,6,20,19,1,0)))
    print(render_delta(dt(2012,1,19,18,0,0), dt(2012,6,20,19,1,0)))
    print(render_delta(dt(2011,3,19,18,0,0), dt(2012,6,20,19,1,0)))
