# coding: utf-8

# python
from datetime import datetime

# 3rd-party
from freezegun import freeze_time
import pytest

# this app
from timetra.diary.utils import (
    extract_date_time_bounds,
    parse_date_time_bounds
)


#
# Этапы:
# 1. строка → компоненты (since, delta, until)
# 2. индивидуальная нормализация компонентов: строка → time/timedelta
# 3. взаимная нормализация компонентов: time → datetime, timedelta → datetime
#


def test_extract_bounds():
    f = extract_date_time_bounds

    ## simple since, until

    assert f('18:55..19:30') == {'since': '18:55', 'until': '19:30'}
    assert f('00:55..01:30') == {'since': '00:55', 'until': '01:30'}
    # same, semicolon omitted
    assert f('0055..0130')   == {'since': '0055',  'until': '0130'}
    # same, leading zeroes omitted
    assert f('0:55..1:30')   == {'since': '0:55',  'until': '1:30'}
    assert f('55..130')      == {'since':   '55',  'until':  '130'}
    assert f('5..7')         == {'since':    '5',  'until':    '7'}
    # an ugly but probably valid case
    assert f(':5..:7')       == {'since':   ':5',  'until':   ':7'}

    ## relative

    assert f('12:30..+5') == {'since': '12:30', 'until': '+5'}
    assert f('12:30..-5') == {'since': '12:30', 'until': '-5'}
    assert f('+5..12:30') == {'since': '+5', 'until': '12:30'}
    assert f('-5..12:30') == {'since': '-5', 'until': '12:30'}

    # both relative
    assert f('-3..-2') == {'since': '-3', 'until': '-2'}
    assert f('+5..+8') == {'since': '+5', 'until': '+8'}
    assert f('-9..+5') == {'since': '-9', 'until': '+5'}
    assert f('+2..-5') == {'since': '+2', 'until': '-5'}

    ## ultrashortcuts

    assert f('1230+5') == {'since': '1230', 'until': '+5'}
    with pytest.raises(ValueError):
        f('1230-5')
    assert f('+5') == {'since': '+5'}
    assert f('-5') == {'since': '-5'}


def test_bounds_normalize_components():
    raise NotImplementedError


def test_bounds_normalize_group():
    raise NotImplementedError


#@freeze_time('2014-01-31 19:51')
def test_parse_bounds_simple():
    f = parse_date_time_bounds
    assert f('18:55..19:30') == (datetime(2014,1,31, 18,55),
                                 datetime(2014,1,31, 19,30))
    assert f('00:55..01:30') == (datetime(2014,1,31, 0,55),
                                 datetime(2014,1,31, 1,30))
    assert f('0055..0130')   == (datetime(2014,1,31, 0,55),
                                 datetime(2014,1,31, 1,30))
    assert f('55..130')      == (datetime(2014,1,31, 0,55),
                                 datetime(2014,1,31, 1,30))
