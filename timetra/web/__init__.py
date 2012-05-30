#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Web application
===============
"""
import datetime
from flask import (Blueprint, Flask, flash, redirect, render_template, request,
                   url_for)
import wtforms as wtf

from timetra import storage
from timetra.curses import CATEGORY_COLOURS
from timetra.reporting import drift, methodology, prediction
from timetra.utils import format_delta


blueprint = Blueprint('timetra', __name__)


class TagListField(wtf.Field):
    widget = wtf.widgets.TextInput()

    def _value(self):
        return u' '.join(self.data) if self.data else u''

    def process_formdata(self, valuelist):
        self.data = []
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(' ')]


class AddFactForm(wtf.Form):
    loose_name = wtf.TextField(u'Activity', [wtf.validators.Required()])
    description = wtf.TextAreaField()
    tags = TagListField()
    start_time = wtf.DateTimeField(default=datetime.datetime.now)
    end_time = wtf.DateTimeField(u'End Time', [wtf.validators.Optional()])


class FactForm(wtf.Form):
    category = wtf.SelectField()
    activity = wtf.TextField(u'Activity', [wtf.validators.Required()])
    description = wtf.TextAreaField()
    tags = TagListField()
    start_time = wtf.DateTimeField()
    end_time = wtf.DateTimeField(u'End Time', [wtf.validators.Optional()])


def appraise_category(category):
    # map category types to CSS classes to tweak progress bar colour
    default_appraisal = 'info'
    appraisal_mapping = {
        'productive': 'success',
        'procrastination': 'warning',
    }
    for type_, matching_names in CATEGORY_COLOURS.items():
        if category in matching_names:
            return appraisal_mapping.get(type_)
    return default_appraisal


def approx_time(dt):
    hour = dt.hour
    minute = int(round((dt.minute / 100.),1)*100)
    if minute == 60:
        hour += 1
        minute = 0
    return u'{hour}:{minute:0>2}'.format(hour=hour, minute=minute)

def get_stats(facts):
    if not facts:
        return []

    categories = {}
    stats = []

    for fact in facts:
        categories.setdefault(fact.category, datetime.timedelta(0))
        categories[fact.category] += fact.delta
    #max_seconds = max(categories[k].total_seconds() for k in categories)
    max_seconds = 24 * 60 * 60
    for category in sorted(categories, key=lambda k: categories[k]):
        total_seconds = categories[category].total_seconds()  # <- float
        percentage = total_seconds / max_seconds * 100
        stats.append({'category': category, 'percentage': percentage,
                      'duration': categories[category]})

    return stats


@blueprint.route('/')
def dashboard():
    # можно storage.get_facts_for_today(), но тогда в 00:00 обрезается в ноль
    facts = storage.hamster_storage.get_todays_facts()
    stats = get_stats(facts)
    sleep_drift = drift.collect_drift_data(activity='sleeping', span_days=7)
    next_sleep = prediction.predict_next_occurence('sleeping')
    day = datetime.date.today() - datetime.timedelta(days=1)
    return render_template('dashboard.html', facts=facts, stats=stats,
                           appraise_category=appraise_category,
                           sleep_drift=sleep_drift, next_sleep=next_sleep,
                           format_delta=format_delta, approx_time=approx_time,
                           methodology=methodology, day=day)


@blueprint.route('<int:year>/<int:month>/<int:day>/')
def day_view(year, month, day):
    day = datetime.date(year, month, day)
    facts = storage.get_facts_for_day(day)
    stats = get_stats(facts)
    prev = day - datetime.timedelta(days=1)
    next = day + datetime.timedelta(days=1)
    return render_template('day.html', day=day, facts=facts, stats=stats,
                           prev=prev, next=next)


@blueprint.route('reports/drift/')
def report_drift():
    sleep_drift = drift.collect_drift_data(activity='sleeping', span_days=30)
    return render_template('drift.html', sleep_drift=sleep_drift)


@blueprint.route('reports/predictions/')
def report_predictions():
    predictions = {}
    activities = storage.hamster_storage.get_activities()
    for activity in activities:
        item = prediction.predict_next_occurence(activity['name']) or {}
        item.update(activity=activity['name'])
        predictions.setdefault(activity['category'], []).append(item)
    return render_template('predictions.html', predictions=predictions)


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


@blueprint.route('facts/add/', methods=['GET', 'POST'])
def add_fact():
    data = request.form.copy()
    form = AddFactForm(data)
    if request.method == 'POST' and form.validate():
        try:
            fact = storage.add_fact(**form.data)
        except (storage.ActivityMatchingError, storage.CannotCreateFact) as e:
            flash(u'Error: {0}'.format(e), 'error')
        else:
            url = url_for('timetra.edit_fact', fact_id=fact.id)
            message = u'Added <a href="{url}">{f.activity}@{f.category}</a>'
            flash(message.format(url=url, f=fact), 'success')
            return redirect(url_for('timetra.dashboard'))

    return render_template('add.html', storage=storage, form=form)


@blueprint.route('facts/<int:fact_id>/', methods=['GET', 'POST'])
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
        flash(u'Fact has been successfully updated', 'success')
        return redirect(url_for('timetra.edit_fact', fact_id=new_id))

    return render_template('edit.html', storage=storage, fact=fact, form=form)


def create_app(config, debug=False):
    app = Flask(__name__)
    app.debug = debug
    if config:
        app.config.from_object(config)
    app.register_blueprint(blueprint, url_prefix='/')
    return app
