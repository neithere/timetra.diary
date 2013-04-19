# coding: utf-8

# python
import datetime

# 3rd party
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
