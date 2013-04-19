# coding: utf-8
import atexit
import os
import shelve

import xdg.BaseDirectory


__all__ = ['get_cached_yaml_file']


APP_NAME = 'timetra'    # settings.APP_NAME


cache_dir = xdg.BaseDirectory.save_cache_path(APP_NAME)
cache_path = cache_dir + '/yaml_files.db'
try:
    cache = shelve.open(cache_path)
except:
    os.remove(cache_path)
    cache = shelve.open(cache_path)

# http://stackoverflow.com/questions/2180946/really-weird-issue-with-shelve-python
# (got this issue even on Python 2.7.4)
atexit.register(lambda: cache.close())


def get_cached_yaml_file(path, model):
    #results = tmpl_cache.get(key=search_param, createfunc=load_card)
    time_key = u'changed:{0}'.format(path)
    data_key = u'content:{0}'.format(path)
    mtime_cache = cache.get(time_key)
    mtime_file = os.stat(path).st_mtime
    if mtime_cache == mtime_file:
        data = cache[data_key]
        print('[x]', path)
    else:
        print('[ ]', path)
        data = list(_load_object_list(path, model))
        cache[data_key] = data
        cache[time_key] = mtime_file
    #cache.close()
    return data


import yaml
from monk.modeling import DotExpandedDict
from monk.validation import ValidationError, validate_structure

def _load_object_list(path, model):
    with open(path) as f:
        items = yaml.load(f)

    if not items:
        return

    for data in items:
        obj = DotExpandedDict(data)

        try:
            validate_structure(model, obj)
        except (ValidationError, TypeError) as e:
            raise type(e)('{path}: {e}'.format(path=path, e=e))

        yield obj


def reset():
    try:
        cache.close()
    except:
        pass
    os.remove(cache_path)


commands = [ reset ]
