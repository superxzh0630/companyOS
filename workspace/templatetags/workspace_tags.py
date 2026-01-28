from django import template

register = template.Library()


@register.filter
def get_field(form, field_name):
    """
    Get a form field by its name dynamically.
    Usage: {{ form|get_field:field_key }}
    """
    try:
        return form[field_name]
    except KeyError:
        return ""


@register.filter
def get_field_errors(form, field_name):
    """
    Get errors for a specific field by name.
    Usage: {{ form|get_field_errors:field_key }}
    """
    try:
        field = form[field_name]
        return field.errors
    except KeyError:
        return []


@register.filter
def add_class(field, css_class):
    """
    Add a CSS class to a form field widget.
    Usage: {{ form.field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={"class": css_class})
