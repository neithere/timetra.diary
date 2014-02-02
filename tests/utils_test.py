# coding: utf-8

# python
from datetime import datetime, time, timedelta

# 3rd-party
from freezegun import freeze_time
import pytest

# this app
from timetra.diary import utils


def test_extract_components():
    f = utils.extract_date_time_bounds

    ## simple since, until

    assert f('18:55..19:30') == {'since': '18:55', 'until': '19:30'}
    assert f('00:55..01:30') == {'since': '00:55', 'until': '01:30'}
    # same, semicolon omitted
    assert f('0055..0130')   == {'since': '0055',  'until': '0130'}
    # same, leading zeroes omitted
    assert f('0:55..1:30')   == {'since': '0:55',  'until': '1:30'}
    assert f('55..130')      == {'since':   '55',  'until':  '130'}
    # missing hour is considered 0 AM, not current one
    assert f('5..7')         == {'since':    '5',  'until':    '7'}
    # an ugly but probably valid case
    assert f(':5..:7')       == {'since':   ':5',  'until':   ':7'}

    ## defaults

    # since last until given
    assert f('..130') == {'until':  '130'}
    # since given until now
    assert f('55..')  == {'since':   '55'}
    # since last until now
    assert f('..') == {}
    assert f('')   == {}

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
    f = utils.string_to_time_or_delta
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

    assert f(None) == None


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
    assert f(last, timedelta(minutes=-10), timedelta(minutes=+3), now) == (
        datetime(2014, 2, 1, 21, 20),
        datetime(2014, 2, 1, 21, 23),
    )


@freeze_time('2014-01-31 19:51')
def test_parse_bounds_simple():

    f = utils.parse_date_time_bounds
    d = datetime

    last = datetime(2014, 1, 30, 22, 15)

    assert f('18:55..19:30', last) == (d(2014,1,31, 18,55), d(2014,1,31, 19,30))
    assert f('00:55..01:30', last) == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    # same, semicolon omitted
    assert f( '0055..0130', last)  == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    # same, leading zeroes omitted
    assert f( '0:55..1:30', last)  == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    assert f(   '55..130', last)   == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    assert f(     '..130', last)   == (d(2014,1,30, 22,15), d(2014,1,31,  1,30))
    # missing hour is considered 0 AM, not current one
    assert f(    '5..7', last)     == (d(2014,1,31,  0, 5), d(2014,1,31,  0, 7))
    # an ugly but probably valid case
    assert f(   ':5..:7', last)    == (d(2014,1,31,  0, 5), d(2014,1,31,  0, 7))

    ## defaults

    # since last until given
    assert f('..130', last) == (d(2014,1,30, 22,15), d(2014,1,31,  1,30))
    # since given until now
    assert f('130..', last) == (d(2014,1,31,  1,30), d(2014,1,31, 19,51))
    # since last until now
    assert f('..', last)    == (d(2014,1,30, 22,15), d(2014,1,31, 19,51))
    assert f('', last)      == (d(2014,1,30, 22,15), d(2014,1,31, 19,51))

    ## relative

    assert f('12:30..+5', last) == (d(2014,1,31, 12,30), d(2014,1,31, 12,35))
    assert f('12:30..-5', last) == (d(2014,1,31, 12,30), d(2014,1,31, 19,46))
    assert f('+5..12:30', last) == (d(2014,1,30, 22,20), d(2014,1,31, 12,30))
    assert f('-5..12:30', last) == (d(2014,1,31, 12,25), d(2014,1,31, 12,30))

    # both relative
    #
    # XXX the `-3..-2` case seems counterintuitive.
    # is "{until-x}..{now-y}" really better than "{now-x}..{now-y}"?
    #
    # (?) assert f('-3..-2', last) == (d(2014,1,31, 19,48), d(2014,1,31, 19,49))
    assert f('-3..-2', last) == (d(2014,1,31, 19,46), d(2014,1,31, 19,49))
    assert f('+5..+8', last) == (d(2014,1,30, 22,20), d(2014,1,30, 22,28))
    assert f('-9..+5', last) == (d(2014,1,31, 19,42), d(2014,1,31, 19,47))
    assert f('+2..-5', last) == (d(2014,1,30, 22,17), d(2014,1,31, 19,46))

    ## ultrashortcuts

    assert f('1230+5', last) == (d(2014,1,31, 12,30), d(2014,1,31, 12,35))
    with pytest.raises(ValueError):
        f('1230-5', last)
    assert f('+5', last) == (d(2014,1,30, 22,20), d(2014,1,31, 19,51))
    assert f('-5', last) == (d(2014,1,31, 19,46), d(2014,1,31, 19,51))
