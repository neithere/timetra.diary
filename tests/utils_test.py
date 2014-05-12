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

    # regressions for "00:00" vs `None`:
    assert f(last, time(), time(5), now) == (
        datetime(2014, 2, 1, 0, 0),
        datetime(2014, 2, 1, 5, 0),
    )
    assert f(last, timedelta(minutes=-15), time(), now) == (
        datetime(2014, 1, 31, 23, 45),
        datetime(2014, 2,  1,  0,  0),
    )


@freeze_time('2014-01-31 19:51:37.123456')
def test_parse_bounds():

    f = utils.parse_date_time_bounds
    d = datetime

    now = d.now()
    last = d(2014,1,30, 22,15,45, 987654)
    last_rounded_fwd = d(2014,1,30, 22,16)

    # leading/trailing spaces are ignored
    assert f(' 18:55..19:30 ', last) == (d(2014,1,31, 18,55), d(2014,1,31, 19,30))

    assert f('18:55..19:30', last) == (d(2014,1,31, 18,55), d(2014,1,31, 19,30))
    assert f('00:55..01:30', last) == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    # same, semicolon omitted
    assert f( '0055..0130', last)  == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    # same, leading zeroes omitted
    assert f( '0:55..1:30', last)  == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    assert f(   '55..130', last)   == (d(2014,1,31,  0,55), d(2014,1,31,  1,30))
    assert f(     '..130', last)   == (last_rounded_fwd, d(2014,1,31,  1,30))
    # missing hour is considered 0 AM, not current one
    assert f(    '5..7', last)     == (d(2014,1,31,  0, 5), d(2014,1,31,  0, 7))
    # an ugly but probably valid case
    assert f(   ':5..:7', last)    == (d(2014,1,31,  0, 5), d(2014,1,31,  0, 7))

    ## defaults

    # since last until given
    assert f('..130', last) == (last_rounded_fwd, d(2014,1,31,  1,30))
    # since given until now
    assert f('130..', last) == (d(2014,1,31,  1,30), now)
    # since last until now
    assert f('..', last)    == (last_rounded_fwd, now)
    assert f('', last)      == (last_rounded_fwd, now)

    ## relative

    assert f('12:30..+5', last) == (d(2014,1,31, 12,30), d(2014,1,31, 12,35))
    assert f('12:30..-5', last) == (d(2014,1,31, 12,30), d(2014,1,31, 19,47))
    assert f('+5..12:30', last) == (d(2014,1,30, 22,21), d(2014,1,31, 12,30))
    assert f('-5..12:30', last) == (d(2014,1,31, 12,25), d(2014,1,31, 12,30))

    assert f('..-5', last) == (last_rounded_fwd, d(2014,1,31, 19,47))
    assert f('..+5', last) == (last_rounded_fwd, d(2014,1,30, 22,21))

    assert f('+5..', last) == (d(2014,1,30, 22,21), now)
    assert f('-5..', last) == (d(2014,1,31, 19,47), now)

    # both relative
    #
    # XXX the `-3..-2` case seems counterintuitive.
    # is "{until-x}..{now-y}" really better than "{now-x}..{now-y}"?
    #
    # (?) assert f('-3..-2', last) == (d(2014,1,31, 19,48), d(2014,1,31, 19,49))
    assert f('-3..-2', last) == (d(2014,1,31, 19,47), d(2014,1,31, 19,50))
    assert f('+5..+8', last) == (d(2014,1,30, 22,21), d(2014,1,30, 22,29))
    assert f('-9..+5', last) == (d(2014,1,31, 19,43), d(2014,1,31, 19,48))
    assert f('+2..-5', last) == (d(2014,1,30, 22,18), d(2014,1,31, 19,47))

    ## ultrashortcuts

    assert f('1230+5', last) == (d(2014,1,31, 12,30), d(2014,1,31, 12,35))
    with pytest.raises(ValueError):
        f('1230-5', last)
    # `delta` = `delta..`
    assert f('+5', last) == (d(2014,1,30, 22,21), now)
    assert f('-5', last) == (d(2014,1,31, 19,47), now)


@freeze_time('2014-01-31 19:30:00')
def test_parse_bounds_rounding():

    f = utils.parse_date_time_bounds
    d = datetime

    until = d(2014,1,31, 12,00)

    # When `since` is calculated from the previous fact, it is rounded forward
    # to half a minute.  This ensures that:
    #
    # a) the precision is lowered to a sane level and some overprecise tail
    #    of one fact's `until` field (seconds and microseconds) is not carried
    #    on and on by a series of consecutive facts.
    #
    # b) the facts don't overlap after correction.
    #
    assert f('..12:00', last=d(2014,1,30, 22,15, 0, 0)) == \
                            (d(2014,1,30, 22,15, 0, 0), until)

    assert f('..12:00', last=d(2014,1,30, 22,15, 1, 0)) == \
                            (d(2014,1,30, 22,15,30, 0), until)

    assert f('..12:00', last=d(2014,1,30, 22,15,15, 0)) == \
                            (d(2014,1,30, 22,15,30, 0), until)

    assert f('..12:00', last=d(2014,1,30, 22,15,30, 0)) == \
                            (d(2014,1,30, 22,15,30, 0), until)

    assert f('..12:00', last=d(2014,1,30, 22,15,31, 0)) == \
                            (d(2014,1,30, 22,16,00, 0), until)

    assert f('..12:00', last=d(2014,1,30, 22,15,30, 123456)) == \
                            (d(2014,1,30, 22,16, 0, 0), until)

    assert f('..12:00', last=d(2014,1,30, 22,15,59, 0)) == \
                            (d(2014,1,30, 22,16, 0, 0), until)

    # same applies to `since` calculated from `now`: we also round forwards

    last = d(2014,1,31)    # does not matter here
    with freeze_time('2014-01-31 19:30:00'):
        assert f('-5', last) == (d(2014,1,31, 19,25,  0, 0), d.now())
    with freeze_time('2014-01-31 19:30:01'):
        assert f('-5', last) == (d(2014,1,31, 19,25, 30, 0), d.now())
    with freeze_time('2014-01-31 19:30:00.123456'):
        assert f('-5', last) == (d(2014,1,31, 19,25, 30, 0), d.now())
    with freeze_time('2014-01-31 19:30:30.123456'):
        assert f('-5', last) == (d(2014,1,31, 19,26,  0, 0), d.now())
