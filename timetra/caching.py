# coding: utf-8
import logging
import os
import shelve

import yaml
from monk.errors import ValidationError
from monk.validation import validate


__all__ = ['Cache']


log = logging.getLogger(__name__)


class Cache:
    APP_NAME = 'timetra'
    FILE_NAME = 'yaml_files.db'

    def __init__(self, root_dir=None):
        cache_dir = root_dir or self._make_xdg_dir()
        path = cache_dir + '/' + self.FILE_NAME

        try:
            db = shelve.open(path)
        except:
            os.remove(path)
            db = shelve.open(path)

        self.path = path
        self.db = db

    def _make_xdg_dir(self):
        import xdg.BaseDirectory
        return xdg.BaseDirectory.save_cache_path(self.APP_NAME)

    def get_cached_yaml_file(self, path, model):
        #results = tmpl_cache.get(key=search_param, createfunc=load_card)
        time_key = 'changed:' + path
        data_key = 'content:' + path
        mtime_cache = self.db.get(time_key)
        mtime_file = os.stat(path).st_mtime
        if mtime_cache == mtime_file:
            data = self.db[data_key]
            log.debug('[x]', path)
        else:
            log.debug('[ ]', path)
            data = list(self._load_object_list(path, model))
            self.db[data_key] = data
            self.db[time_key] = mtime_file
        #cache.close()
        return data


    def _load_object_list(self, path, model):
        with open(path) as f:
            items = yaml.load(f)

        if not items:
            return

        for data in items:
            obj = model(data)

            try:
                validate(model, obj)
            except (ValidationError, TypeError) as e:
                raise type(e)('{path}: {e}'.format(path=path, e=e))

            yield obj

    def reset(self):
        try:
            self.db.close()
        except:
            pass
        os.remove(self.path)


#cache = Cache()
#
#commands = [ cache.reset ]
