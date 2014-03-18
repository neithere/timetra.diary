# coding: utf-8
# http://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data

import yaml


class literal(str):
    pass


def literal_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


def ordered_dict_representer(dumper, data):
    return dumper.represent_mapping('tag:yaml.org,2002:omap', data)


def setup():
    yaml.add_representer(literal, literal_representer)
