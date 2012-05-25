#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web application
===============
"""
import datetime
from flask import Blueprint, Flask, redirect, render_template, request, url_for
import wtforms as wtf

from timetra import storage
from timetra.curses import CATEGORY_COLOURS


blueprint = Blueprint('timetra', __name__)


class TagListField(wtf.Field):
    widget = wtf.widgets.TextInput()

    def _value(self):
        return u' '.join(self.data) if self.data else u''

    def process_formdata(self, valuelist):
        self.data = []
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(',')]


class FactForm(wtf.Form):
    category = wtf.SelectField()
    activity = wtf.TextField()
    description = wtf.TextAreaField()
    tags = TagListField()
    start_time = wtf.DateTimeField()
    end_time = wtf.DateTimeField(u'End Time', [wtf.validators.Optional()])


def get_stats(facts):
    if not facts:
        return []

    categories = {}
    stats = []

    # map category types to CSS classes to tweak progress bar colour
    default_appraisal = 'info'
    appraisal_mapping = {
        'productive': 'success',
        'procrastination': 'warning',
    }
    def _get_appraisal(category):
        for type_, matching_names in CATEGORY_COLOURS.items():
            if category in matching_names:
                return appraisal_mapping.get(type_)
        return default_appraisal

    for fact in facts:
        categories.setdefault(fact.category, datetime.timedelta(0))
        categories[fact.category] += fact.delta
    #max_seconds = max(categories[k].total_seconds() for k in categories)
    max_seconds = 24 * 60 * 60
    for category in sorted(categories, key=lambda k: categories[k]):
        total_seconds = categories[category].total_seconds()  # <- float
        percentage = total_seconds / max_seconds * 100
        appraisal = _get_appraisal(category)
        stats.append({'category': category, 'percentage': percentage,
                      'appraisal': appraisal, 'duration': categories[category]})

    return stats


@blueprint.route('/')
def dashboard():
    facts = storage.get_facts_for_day()
    stats = get_stats(facts)
    return render_template('dashboard.html', facts=facts, stats=stats)


@blueprint.route('search/')
def search():
    query = request.values.get('q')
    facts = storage.get_facts_for_day(date=-1, search_terms=query)
    return render_template('search.html', storage=storage, facts=facts)


@blueprint.route('activities/<activity>/')
def activity(activity):
    facts = storage.get_facts_for_day(date=-1, search_terms=activity)
    return render_template('activity.html', storage=storage,
                           activity=activity, facts=facts)


@blueprint.route('facts/<int:fact_id>/edit', methods=['GET', 'POST'])
def edit_fact(fact_id):
    fact = storage.hamster_storage.get_fact(fact_id)
    form = FactForm(request.form, fact)
    categories = storage.hamster_storage.get_categories()
    form.category.choices = [(x['name'], x['name']) for x in categories]
    if request.method == 'POST' and form.validate():
        form.populate_obj(fact)
        #-- Hamster peculiarities -----------------------------------------------------------
        # Update is performed via remove/insert, so the
        # fact_id after update should not be used anymore. Instead use the ID
        # from the fact dict that is returned by this function
        #
        new_id = storage.hamster_storage.update_fact(fact_id, fact)
        #
        #----------------------------------------------------------------------
        return redirect(url_for('timetra.edit_fact', fact_id=new_id))

    return render_template('edit.html', storage=storage, fact=fact, form=form)


def create_app(config, debug=False):
    app = Flask(__name__)
    app.debug = debug
    if config:
        app.config.from_object(config)
    app.register_blueprint(blueprint, url_prefix='/')
    return app
