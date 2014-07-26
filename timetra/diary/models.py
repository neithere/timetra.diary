# coding: utf-8

# python
from collections import OrderedDict
import datetime

# 3rd party
from monk import modeling
from monk.schema import optional


fact_schema = OrderedDict([
    (optional('category'), str),
    ('activity', str),
    ('since', datetime.datetime.now),
    ('until', datetime.datetime),
    (optional('tags'), [
        optional(str),
    ]),
    (optional('hamster_fact_id'), int),    # legacy
    ('description', optional(str)),
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
