# coding: utf-8
#
# source: https://gist.github.com/weaver/317164
#
# Copyright (c) 2009 Raymond Hettinger
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

from collections import OrderedDict

import yaml


### Construct OrderedDict

def construct_odict(load, node):
    """This is the same as SafeConstructor.construct_yaml_omap(),
    except the data type is changed to OrderedDict() and setitem is
    used instead of append in the loop.

    >>> yaml.load('''
    ... !!omap
    ... - foo: bar
    ... - mumble: quux
    ... - baz: gorp
    ... ''')
    OrderedDict([('foo', 'bar'), ('mumble', 'quux'), ('baz', 'gorp')])

    >>> yaml.load('''!!omap [ foo: bar, mumble: quux, baz : gorp ]''')
    OrderedDict([('foo', 'bar'), ('mumble', 'quux'), ('baz', 'gorp')])
    """

    omap = OrderedDict()
    yield omap
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(
            "while constructing an ordered map",
            node.start_mark,
            "expected a sequence, but found %s" % node.id, node.start_mark
        )
    for subnode in node.value:
        if not isinstance(subnode, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(
                "while constructing an ordered map", node.start_mark,
                "expected a mapping of length 1, but found %s" % subnode.id,
                subnode.start_mark
            )
        if len(subnode.value) != 1:
            raise yaml.constructor.ConstructorError(
                "while constructing an ordered map", node.start_mark,
                "expected a single mapping item, but found %d items" % len(subnode.value),
                subnode.start_mark
            )
        key_node, value_node = subnode.value[0]
        key = load.construct_object(key_node)
        value = load.construct_object(value_node)
        omap[key] = value


### Represent OrderedDict

def repr_odict(dumper, data):
    """
    >>> data = OrderedDict([('foo', 'bar'), ('mumble', 'quux'), ('baz', 'gorp')])
    >>> yaml.dump(data, default_flow_style=False)
    '!!omap\\n- foo: bar\\n- mumble: quux\\n- baz: gorp\\n'
    >>> yaml.dump(data, default_flow_style=True)
    '!!omap [foo: bar, mumble: quux, baz: gorp]\\n'
    """
    return repr_pairs(dumper, u'tag:yaml.org,2002:omap', data.iteritems())


def repr_pairs(dump, tag, sequence, flow_style=None):
    """This is the same code as BaseRepresenter.represent_sequence(),
    but the value passed to dump.represent_data() in the loop is a
    dictionary instead of a tuple."""

    value = []
    node = yaml.SequenceNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    for (key, val) in sequence:
        item = dump.represent_data({key: val})
        if not (isinstance(item, yaml.ScalarNode) and not item.style):
            best_style = False
        value.append(item)
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


def setup():
    yaml.add_constructor(u'tag:yaml.org,2002:omap', construct_odict)
    yaml.add_representer(OrderedDict, repr_odict)


if __name__ == '__main__':
    import doctest
    setup()
    doctest.testmod()
