# coding: utf-8

# python
import datetime

# 3rd party
from monk import modeling
from monk.schema import optional


FACT = {
    'category': str,
    'activity': str,
    'since': datetime.datetime.now,
    'until': datetime.datetime,
    'tags': optional([str]),
    optional('hamster_fact_id'): int,
    'description': optional(str),
}


class Model(modeling.TypedDictReprMixin,
            modeling.DotExpandedDictMixin,
            modeling.StructuredDictMixin,
            dict):

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
        self._insert_defaults()
        self._make_dot_expanded()


class Fact(Model):
    structure = FACT

    @property
    def duration(self):
        return (self.until or datetime.datetime.now()) - self.since
