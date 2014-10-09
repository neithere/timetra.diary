# coding: utf-8

# python
from collections import OrderedDict
import datetime

# 3rd party
from monk import modeling, nullable, optional, IsA, Equals, Exists


fact_schema = OrderedDict([
    (Equals('category') | ~Exists(), str),
    ('activity', str),
    ('since', datetime.datetime.now),
    ('until', datetime.datetime),
    (Equals('tags') | ~Exists(), [
        IsA(str) | Equals(None) | ~Exists(),
    ]),
    (Equals('hamster_fact_id') | ~Exists(), int),    # legacy
    ('description', nullable(str)),
])


class Model(modeling.TypedDictReprMixin,
            modeling.DotExpandedDictMixin,
            modeling.StructuredDictMixin,
            dict):

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        self._insert_defaults()
        self._make_dot_expanded()


class Fact(Model):
    structure = fact_schema

    @property
    def duration(self):
        return (self.until or datetime.datetime.now()) - self.since
