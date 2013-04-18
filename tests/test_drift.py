# coding: utf-8

from datetime import datetime, timedelta

from timetra.reporting.drift import DriftData


class TestDurationSplitting:
    def test_basics(self):
        dt = datetime(2012,4,18, 20,00)
        d = DriftData(span_days=1, end_time=dt)
        assert d
        assert d[dt.date()]
        assert d[dt.date()][12]
        assert d[dt.date()][12].duration == timedelta()

    def test_exact_left_fits(self):
        "start time matches the hourbox left edge; fits the box"
        dt = datetime(2012,4,18, 20,00)
        d = DriftData(span_days=1, end_time=dt)
        # 11:00..11:03
        d.add_fact(dt.replace(hour=11, minute=0),
                   dt.replace(hour=11, minute=3))
        assert d[dt.date()][11].duration == timedelta(minutes=3)

    def test_exact_right_fits(self):
        "end time matches the hourbox right edge; fits the box"
        dt = datetime(2012,4,18, 20,00)
        d = DriftData(span_days=1, end_time=dt)
        # 11:45..12:00
        d.add_fact(dt.replace(hour=11, minute=45),
                   dt.replace(hour=12, minute=00))
        assert d[dt.date()][11].duration == timedelta(minutes=15)
        assert d[dt.date()][12].duration == timedelta(minutes=0)

    def test_inexact_fits(self):
        "fact start/end times are within a single hourbox but don't touch edges"
        dt = datetime(2012,4,18, 20,00)
        d = DriftData(span_days=1, end_time=dt)
        # 12:20..12:23
        d.add_fact(dt.replace(hour=12, minute=20),
                   dt.replace(hour=12, minute=23))
        assert d[dt.date()][12].duration == timedelta(minutes=3)

    def test_overlap_hours(self):
        dt = datetime(2012,4,18, 20,00)
        d = DriftData(span_days=1, end_time=dt)
        # 13:20..14:20
        d.add_fact(dt.replace(hour=13, minute=20),
                   dt.replace(hour=14, minute=20))
        assert d[dt.date()][13].duration == timedelta(minutes=40)
        assert d[dt.date()][14].duration == timedelta(minutes=20)

    def test_overlap_days(self):
        dt = datetime(2012,4,18, 20,00)
        d = DriftData(span_days=2, end_time=dt)
        # 22:50..1:15
        d.add_fact(dt.replace(day=17, hour=22, minute=50),
                   dt.replace(hour=1, minute=15))
        assert d[dt.date().replace(day=17)][22].duration == timedelta(minutes=10)
        assert d[dt.date().replace(day=17)][23].duration == timedelta(minutes=60)
        assert d[dt.date()][0].duration == timedelta(minutes=60)
        assert d[dt.date()][1].duration == timedelta(minutes=15)

