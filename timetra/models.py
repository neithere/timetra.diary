# coding: utf-8

# python
import datetime

# 3rd party
from monk import modeling
from monk.validation import optional


FACT = {
    'category': str,
    'activity': str,
    'since': datetime.datetime,
    'until': datetime.datetime,
    'tags': optional([str]),
    'hamster_fact_id': optional(int),
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
