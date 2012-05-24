#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web application
===============
"""
import flask

from timetra import storage


blueprint = flask.Blueprint('timetra', __name__)


@blueprint.route('/')
def dashboard():
    return flask.render_template('dashboard.html', storage=storage)


@blueprint.route('activities/<activity>/')
def activity(activity):
    facts = storage.get_facts_for_day(date=-1, search_terms=activity)
    return flask.render_template('activity.html', storage=storage,
                                 activity=activity, facts=facts)


def create_app(config, debug=False):
    app = flask.Flask(__name__)
    app.debug = debug
    if config:
        app.config.from_object(config)
    app.register_blueprint(blueprint, url_prefix='/')
    return app
