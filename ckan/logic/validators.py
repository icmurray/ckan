import re
import datetime
from pylons.i18n import _, ungettext, N_, gettext
from ckan.lib.navl.dictization_functions import Invalid, Missing, missing, unflatten
from ckan.authz import Authorizer
from ckan.logic import check_access, NotAuthorized
from ckan.lib.helpers import date_str_to_datetime
from ckan.model import MAX_TAG_LENGTH

def package_id_not_changed(value, context):

    package = context.get('package')
    if package and value != package.id:
        raise Invalid(_('Cannot change value of key from %s to %s. '
                        'This key is read-only') % (package.id, value))
    return value

def int_validator(value, context):
    if isinstance(value, int):
        return value
    try:
        if value.strip() == '':
            return None
        return int(value)
    except (AttributeError, ValueError), e:
        raise Invalid(_('Invalid integer'))

def isodate(value, context):
    if isinstance(value, datetime.datetime):
        return value
    if value == '':
        return None
    try:
        date = date_str_to_datetime(value)
    except (TypeError, ValueError), e:
        raise Invalid(_('Date format incorrect'))
    return date

def no_http(value, context):

    model = context['model']
    session = context['session']

    if 'http:' in value:
        raise Invalid(_('No links are allowed in the log_message.'))
    return value

def package_id_exists(value, context):

    model = context['model']
    session = context['session']

    result = session.query(model.Package).get(value)
    if not result:
        raise Invalid(_('Dataset was not found.'))
    return value

def package_name_exists(value, context):

    model = context['model']
    session = context['session']

    result = session.query(model.Package).filter_by(name=value).first()

    if not result:
        raise Invalid(_('Dataset with name %r does not exist.') % str(value))
    return value

def package_id_or_name_exists(value, context):

    model = context['model']
    session = context['session']

    result = session.query(model.Package).get(value)
    if result:
        return value

    result = session.query(model.Package).filter_by(name=value).first()

    if not result:
        raise Invalid(_('Dataset was not found.'))

    return result.id

def extras_unicode_convert(extras, context):
    for extra in extras:
        extras[extra] = unicode(extras[extra])
    return extras

name_match = re.compile('[a-z0-9_\-]*$')
def name_validator(val, context):
    # check basic textual rules
    if len(val) < 2:
        raise Invalid(_('Name must be at least %s characters long') % 2)
    if not name_match.match(val):
        raise Invalid(_('Url must be purely lowercase alphanumeric '
                        '(ascii) characters and these symbols: -_'))
    return val

def package_name_validator(key, data, errors, context):
    model = context["model"]
    session = context["session"]
    package = context.get("package")

    query = session.query(model.Package.name).filter_by(name=data[key])
    if package:
        package_id = package.id
    else:
        package_id = data.get(key[:-1] + ("id",))
    if package_id and package_id is not missing:
        query = query.filter(model.Package.id <> package_id) 
    result = query.first()
    if result:
        errors[key].append(_('That URL is already in use.'))

def duplicate_extras_key(key, data, errors, context):

    unflattened = unflatten(data)
    extras = unflattened.get('extras', [])
    extras_keys = []
    for extra in extras:
        if not extra.get('deleted'):
            extras_keys.append(extra['key'])
    
    for extra_key in set(extras_keys):
        extras_keys.remove(extra_key)
    if extras_keys:
        errors[key].append(_('Duplicate key "%s"') % extras_keys[0])
    
def group_name_validator(key, data, errors, context):
    model = context['model']
    session = context['session']
    group = context.get('group')

    query = session.query(model.Group.name).filter_by(name=data[key])
    if group:
        group_id = group.id
    else:
        group_id = data.get(key[:-1] + ('id',))
    if group_id and group_id is not missing:
        query = query.filter(model.Group.id <> group_id) 
    result = query.first()
    if result:
        errors[key].append(_('Group name already exists in database'))

def tag_length_validator(value, context):

    if len(value) < 2:
        raise Invalid(
            _('Tag "%s" length is less than minimum %s') % (value, 2)
        )
    if len(value) > MAX_TAG_LENGTH:
        raise Invalid(
            _('Tag "%s" length is more than maximum %i') % (value, MAX_TAG_LENGTH)
        )
    return value

def tag_name_validator(value, context):

    tagname_match = re.compile('[\w\-_.]*$', re.UNICODE)
    if not tagname_match.match(value):
        raise Invalid(_('Tag "%s" must be alphanumeric '
                        'characters or symbols: -_.') % (value))
    return value

def tag_not_uppercase(value, context):

    tagname_uppercase = re.compile('[A-Z]')
    if tagname_uppercase.search(value):
        raise Invalid(_('Tag "%s" must not be uppercase' % (value)))
    return value

def tag_string_convert(key, data, errors, context):

    value = data[key]

    tags = value.split()
    for num, tag in enumerate(tags):
        data[('tags', num, 'name')] = tag.lower()

    for tag in tags:
        tag_length_validator(tag, context)
        tag_name_validator(tag, context)

def ignore_not_admin(key, data, errors, context):

    model = context['model']
    user = context.get('user')

    if user and Authorizer.is_sysadmin(user):
        return

    authorized = False
    pkg = context.get('package')
    if pkg:
        try:
            check_access('package_change_state',context)
            authorized = True
        except NotAuthorized:
            authorized = False
    
    if (user and pkg and authorized):
        return

    data.pop(key)

def user_name_validator(value,context):
    model = context['model']

    if not model.User.check_name_valid(value):
        raise Invalid(
            _('That login name is not valid. It must be at least 3 characters, restricted to alphanumerics and these symbols: %s') % '_\-'
        )

    if not model.User.check_name_available(value):
        raise Invalid(
            _("That login name is not available.")
        )

    return value

def user_both_passwords_entered(key, data, errors, context):
    
    password1 = data.get(('password1',),None)
    password2 = data.get(('password2',),None)

    if password1 is None or password1 == '' or \
       password2 is None or password2 == '':
        errors[('password',)].append(_('Please enter both passwords'))

def user_password_validator(key, data, errors, context):
    value = data[key]

    if not value == '' and not isinstance(value, Missing) and not len(value) >= 4:
        errors[('password',)].append(_('Your password must be 4 characters or longer'))

def user_passwords_match(key, data, errors, context):
    
    password1 = data.get(('password1',),None)
    password2 = data.get(('password2',),None)

    if not password1 == password2:
        errors[key].append(_('The passwords you entered do not match'))
    else:
        #Set correct password
        data[('password',)] = password1

def user_password_not_empty(key, data, errors, context):
    '''Only check if password is present if the user is created via action API.
       If not, user_both_passwords_entered will handle the validation'''
     
    if not ('password1',) in data and not ('password2',) in data:
        password = data.get(('password',),None)
        if not password:
            errors[key].append(_('Missing value'))

def user_about_validator(value,context):
    if 'http://' in value or 'https://' in value:
        raise Invalid(_('Edit not allowed as it looks like spam. Please avoid links in your description.'))

    return value
