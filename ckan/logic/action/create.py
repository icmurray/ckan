import logging

import ckan.rating as ratings
from ckan.plugins import (PluginImplementations,
                          IGroupController,
                          IPackageController)
from ckan.logic import NotFound, ValidationError
from ckan.logic import check_access
from ckan.lib.base import _
from ckan.lib.dictization.model_dictize import (package_to_api1,
                                                package_to_api2,
                                                group_to_api1,
                                                group_to_api2)

from ckan.lib.dictization.model_save import (group_api_to_dict,
                                             group_dict_save,
                                             package_api_to_dict,
                                             package_dict_save,
                                             user_dict_save)

from ckan.lib.dictization.model_dictize import (group_dictize,
                                                package_dictize,
                                                user_dictize)


from ckan.logic.schema import default_create_package_schema, default_resource_schema

from ckan.logic.schema import default_group_schema, default_user_schema
from ckan.lib.navl.dictization_functions import validate 
from ckan.logic.action.update import (_update_package_relationship,
                                      package_error_summary,
                                      group_error_summary)
log = logging.getLogger(__name__)

def package_create(context, data_dict):

    model = context['model']
    user = context['user']
    schema = context.get('schema') or default_create_package_schema()
    model.Session.remove()
    model.Session()._context = context

    check_access('package_create',context,data_dict)

    data, errors = validate(data_dict, schema, context)

    if errors:
        model.Session.rollback()
        raise ValidationError(errors, package_error_summary(errors))

    rev = model.repo.new_revision()
    rev.author = user
    if 'message' in context:
        rev.message = context['message']
    else:
        rev.message = _(u'REST API: Create object %s') % data.get("name")

    pkg = package_dict_save(data, context)
    admins = []
    if user:
        admins = [model.User.by_name(user.decode('utf8'))]

    model.setup_default_user_roles(pkg, admins)
    # Needed to let extensions know the package id
    model.Session.flush()
    for item in PluginImplementations(IPackageController):
        item.create(pkg)
    model.repo.commit()        

    ## need to let rest api create
    context["package"] = pkg
    ## this is added so that the rest controller can make a new location 
    context["id"] = pkg.id
    log.debug('Created object %s' % str(pkg.name))
    return package_dictize(pkg, context) 

def package_create_validate(context, data_dict):
    model = context['model']
    user = context['user']
    schema = context.get('schema') or default_create_package_schema()
    model.Session.remove()
    model.Session()._context = context
    
    check_access('package_create',context,data_dict)

    data, errors = validate(data_dict, schema, context)

    if errors:
        model.Session.rollback()
        raise ValidationError(errors, package_error_summary(errors))
    else:
        return data

def resource_create(context, data_dict):
    #TODO This doesn't actually do anything

    model = context['model']
    user = context['user']

    data, errors = validate(data_dict,
                            default_resource_schema(),
                            context)

def package_relationship_create(context, data_dict):

    model = context['model']
    user = context['user']
    id = data_dict["id"]
    id2 = data_dict["id2"]
    rel_type = data_dict["rel"]
    api = context.get('api_version') or '1'
    ref_package_by = 'id' if api == '2' else 'name'

    # Create a Package Relationship.
    pkg1 = model.Package.get(id)
    pkg2 = model.Package.get(id2)
    if not pkg1:
        raise NotFound('First package named in address was not found.')
    if not pkg2:
        return NotFound('Second package named in address was not found.')

    check_access('package_relationship_create', context, data_dict)

    ##FIXME should have schema
    comment = data_dict.get('comment', u'')

    existing_rels = pkg1.get_relationships_with(pkg2, rel_type)
    if existing_rels:
        return _update_package_relationship(existing_rels[0],
                                            comment, context)
    rev = model.repo.new_revision()
    rev.author = user
    rev.message = _(u'REST API: Create package relationship: %s %s %s') % (pkg1, rel_type, pkg2)
    rel = pkg1.add_relationship(rel_type, pkg2, comment=comment)
    model.repo.commit_and_remove()
    relationship_dicts = rel.as_dict(ref_package_by=ref_package_by)
    return relationship_dicts

def group_create(context, data_dict):
    model = context['model']
    user = context['user']
    schema = context.get('schema') or default_group_schema()

    check_access('group_create',context,data_dict)

    data, errors = validate(data_dict, schema, context)

    if errors:
        model.Session.rollback()
        raise ValidationError(errors, group_error_summary(errors))

    rev = model.repo.new_revision()
    rev.author = user

    if 'message' in context:
        rev.message = context['message']
    else:
        rev.message = _(u'REST API: Create object %s') % data.get("name")

    group = group_dict_save(data, context)

    if user:
        admins = [model.User.by_name(user.decode('utf8'))]
    else:
        admins = []
    model.setup_default_user_roles(group, admins)
    # Needed to let extensions know the group id
    model.Session.flush()
    for item in PluginImplementations(IGroupController):
        item.create(group)
    model.repo.commit()        
    context["group"] = group
    context["id"] = group.id
    log.debug('Created object %s' % str(group.name))
    return group_dictize(group, context)

def rating_create(context, data_dict):

    model = context['model']
    user = context.get("user") 

    package_ref = data_dict.get('package')
    rating = data_dict.get('rating')
    opts_err = None
    if not package_ref:
        opts_err = _('You must supply a package id or name (parameter "package").')
    elif not rating:
        opts_err = _('You must supply a rating (parameter "rating").')
    else:
        try:
            rating_int = int(rating)
        except ValueError:
            opts_err = _('Rating must be an integer value.')
        else:
            package = model.Package.get(package_ref)
            if rating < ratings.MIN_RATING or rating > ratings.MAX_RATING:
                opts_err = _('Rating must be between %i and %i.') % (ratings.MIN_RATING, ratings.MAX_RATING)
            elif not package:
                opts_err = _('Package with name %r does not exist.') % package_ref
    if opts_err:
        raise ValidationError(opts_err)

    user = model.User.by_name(user)
    ratings.set_rating(user, package, rating_int)

    package = model.Package.get(package_ref)
    ret_dict = {'rating average':package.get_average_rating(),
                'rating count': len(package.ratings)}
    return ret_dict

def user_create(context, data_dict):
    '''Creates a new user'''

    model = context['model']
    user = context['user']
    schema = context.get('schema') or default_user_schema()

    check_access('user_create', context, data_dict)

    data, errors = validate(data_dict, schema, context)

    if errors:
        model.Session.rollback()
        raise ValidationError(errors, group_error_summary(errors))

    user = user_dict_save(data, context)

    model.repo.commit()        
    context['user'] = user
    context['id'] = user.id
    log.debug('Created user %s' % str(user.name))
    return user_dictize(user, context)

## Modifications for rest api

def package_create_rest(context, data_dict):
    
    api = context.get('api_version') or '1'

    check_access('package_create_rest', context, data_dict)

    dictized_package = package_api_to_dict(data_dict, context)
    dictized_after = package_create(context, dictized_package) 

    pkg = context['package']

    if api == '1':
        package_dict = package_to_api1(pkg, context)
    else:
        package_dict = package_to_api2(pkg, context)

    data_dict['id'] = pkg.id

    return package_dict

def group_create_rest(context, data_dict):

    api = context.get('api_version') or '1'

    check_access('group_create_rest', context, data_dict)

    dictized_group = group_api_to_dict(data_dict, context)
    dictized_after = group_create(context, dictized_group) 

    group = context['group']

    if api == '1':
        group_dict = group_to_api1(group, context)
    else:
        group_dict = group_to_api2(group, context)

    data_dict['id'] = group.id

    return group_dict

