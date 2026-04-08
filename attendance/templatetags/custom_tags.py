from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_status(record):
    if record:
        return record.status
    return ""

@register.filter
def get_reason(record):
    if record:
        return record.reason_text
    return ""