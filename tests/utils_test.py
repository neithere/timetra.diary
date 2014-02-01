# coding: utf-8

# python
from datetime import datetime, time, timedelta

# 3rd-party
from freezegun import freeze_time
import pytest

# this app
from timetra.diary import utils

#
# Этапы:
# 1. строка → компоненты (since, delta, until)
# 2. индивидуальная нормализация компонентов: строка → time/timedelta
# 3. взаимная нормализация компонентов: time → datetime, timedelta → datetime
#


def test_extract_bounds():
    f = utils.extract_date_time_bounds

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


def test_bounds_normalize_component():
    f = utils.normalize_component
    assert f('15:37') == time(15, 37)
    assert f('05:37') == time(5, 37)
    assert f('5:37')  == time(5, 37)
    assert f('1537')  == time(15, 37)
    assert f('537')   == time(5, 37)
    assert f('37')    == time(0, 37)
    assert f('7')     == time(0, 7)

    assert f('+5')    == timedelta(hours=0, minutes=5)
    assert f('+50')   == timedelta(hours=0, minutes=50)
    assert f('+250')  == timedelta(hours=2, minutes=50)
    assert f('+1250') == timedelta(hours=12, minutes=50)
    with pytest.raises(AssertionError):
        assert f('+70')

    assert f('-5')    == timedelta(hours=0, minutes=-5)
    assert f('-50')   == timedelta(hours=0, minutes=-50)
    assert f('-250')  == timedelta(hours=-2, minutes=-50)
    assert f('-1250') == timedelta(hours=-12, minutes=-50)
    with pytest.raises(AssertionError):
        assert f('-70')


def test_bounds_normalize_group():
    f = utils.normalize_group

    last = datetime(2014, 1, 31,  22, 55)
    now  = datetime(2014, 2,  1,  21, 30)

    # f(last, since, until, now)

    assert f(last, None, None, now) == (
        datetime(2014, 1, 31, 22, 55),
        datetime(2014, 2,  1, 21, 30),
    )
    assert f(last, None, time(20,0), now) == (
        datetime(2014, 1, 31, 22, 55),
        datetime(2014, 2,  1, 20,  0),
    )
    assert f(last, time(12,0), None, now) == (
        datetime(2014, 2, 1, 12,  0),
        datetime(2014, 2, 1, 21, 30),
    )
    assert f(last, time(23,0), time(20,0), now) == (
        datetime(2014, 1, 31, 23, 0),
        datetime(2014, 2,  1, 20, 0),
    )
    assert f(last, timedelta(minutes=5), time(20,0), now) == (
        datetime(2014, 1, 31, 23, 0),
        datetime(2014, 2,  1, 20, 0),
    )
    assert f(last, time(23,0), timedelta(minutes=5), now) == (
        datetime(2014, 1, 31, 23, 0),
        datetime(2014, 1, 31, 23, 5),
    )
    assert f(last, timedelta(minutes=-5), time(20,0), now) == (
        datetime(2014, 2, 1, 19, 55),
        datetime(2014, 2, 1, 20,  0),
    )
    assert f(last, time(23,0), timedelta(minutes=-5), now) == (
        datetime(2014, 1, 31, 23,  0),
        datetime(2014, 2,  1, 21, 25),
    )

    # TODO: edge cases, expected errors (ambiguity)

    raise NotImplementedError


#@freeze_time('2014-01-31 19:51')
def test_parse_bounds_simple():

    raise NotImplementedError

    f = utils.parse_date_time_bounds
    assert f('18:55..19:30') == (datetime(2014,1,31, 18,55),
                                 datetime(2014,1,31, 19,30))
    assert f('00:55..01:30') == (datetime(2014,1,31, 0,55),
                                 datetime(2014,1,31, 1,30))
    assert f('0055..0130')   == (datetime(2014,1,31, 0,55),
                                 datetime(2014,1,31, 1,30))
    assert f('55..130')      == (datetime(2014,1,31, 0,55),
                                 datetime(2014,1,31, 1,30))
