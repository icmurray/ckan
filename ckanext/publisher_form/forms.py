import os, logging
from ckan.authz import Authorizer
import ckan.logic.action.create as create
import ckan.logic.action.update as update
import ckan.logic.action.get as get
from ckan.logic.converters import date_to_db, date_to_form, convert_to_extras, convert_from_extras
from ckan.logic import NotFound, NotAuthorized, ValidationError
from ckan.logic import tuplize_dict, clean_dict, parse_params
import ckan.logic.schema as default_schema
from ckan.logic.schema import group_form_schema
from ckan.logic.schema import package_form_schema
import ckan.logic.validators as val
from ckan.lib.base import BaseController, render, c, model, abort, request
from ckan.lib.base import redirect, _, config, h
from ckan.lib.package_saver import PackageSaver
from ckan.lib.field_types import DateType, DateConvertError
from ckan.lib.navl.dictization_functions import Invalid
from ckan.lib.navl.dictization_functions import validate, missing
from ckan.lib.navl.dictization_functions import DataError, flatten_dict, unflatten
from ckan.plugins import IDatasetForm, IGroupForm, IConfigurer
from ckan.plugins import implements, SingletonPlugin
from ckan.logic import check_access

from ckan.lib.navl.validators import (ignore_missing,
                                      not_empty,
                                      empty,
                                      ignore,
                                      keep_extras,
                                     )

log = logging.getLogger(__name__)

class PublisherForm(SingletonPlugin):
    """
    This plugin implements an IGroupForm for form associated with a
    publisher group. ``IConfigurer`` is used to add the local template
    path and the IGroupForm supplies the custom form.
    """
    implements(IGroupForm, inherit=True)
    implements(IConfigurer, inherit=True)

    def update_config(self, config):
        """
        This IConfigurer implementation causes CKAN to look in the
        ```templates``` directory when looking for the group_form()
        """
        here = os.path.dirname(__file__)
        rootdir = os.path.dirname(os.path.dirname(here))
        template_dir = os.path.join(rootdir, 'ckanext',
                                    'publisher_form', 'templates')
        config['extra_template_paths'] = ','.join([template_dir,
                config.get('extra_template_paths', '')])

    def group_form(self):
        """
        Returns a string representing the location of the template to be
        rendered.  e.g. "forms/group_form.html".
        """
        return 'publisher_form.html'

    def group_types(self):
        """
        Returns an iterable of group type strings.

        If a request involving a group of one of those types is made, then
        this plugin instance will be delegated to.

        There must only be one plugin registered to each group type.  Any
        attempts to register more than one plugin instance to a given group
        type will raise an exception at startup.
        """
        return ["publisher"]

    def is_fallback(self):
        """
        Returns true iff this provides the fallback behaviour, when no other
        plugin instance matches a group's type.

        As this is not the fallback controller we should return False.  If
        we were wanting to act as the fallback, we'd return True
        """
        return False

    def form_to_db_schema(self):
        """
        Returns the schema for mapping group data from a form to a format
        suitable for the database.
        """
        return group_form_schema()

    def db_to_form_schema(self):
        """
        Returns the schema for mapping group data from the database into a
        format suitable for the form (optional)
        """
        return {}

    def check_data_dict(self, data_dict):
        """
        Check if the return data is correct.

        raise a DataError if not.
        """

    def setup_template_variables(self, context, data_dict):
        """
        Add variables to c just prior to the template being rendered. We should
        use the available groups for the current user, but should be optional
        in case this is a top level group
        """
        c.body_class = "group edit"
        c.is_sysadmin = Authorizer().is_sysadmin(c.user)
        if 'group' in context:
            group = context['group']

            try:
                check_access('group_update', context)
                c.is_superuser_or_groupadmin = True
            except NotAuthorized:
                c.is_superuser_or_groupadmin = False

            c.possible_parents = model.Session.query(model.Group).\
                   filter(model.Group.state == 'active').\
                   filter(model.Group.type == 'publisher').\
                   filter(model.Group.name != group.id ).order_by(model.Group.title).all()

            c.parent = None
            grps = group.get_groups('publisher')
            if grps:
                c.parent = grps[0]

            c.users = group.members_of_type(model.User)



class PublisherDatasetForm(SingletonPlugin):
    """
        This plugin implements a new publisher form for cases where we
        want to enforce group (type=publisher) membership on a dataset.

    """
    implements(IDatasetForm, inherit=True)
    implements(IConfigurer, inherit=True)

    def update_config(self, config):
        """
        This IConfigurer implementation causes CKAN to look in the
        ```templates``` directory when looking for the package_form()
        """
        here = os.path.dirname(__file__)
        rootdir = os.path.dirname(os.path.dirname(here))
        template_dir = os.path.join(rootdir, 'ckanext',
                                    'publisher_form', 'templates')
        config['extra_template_paths'] = ','.join([template_dir,
                config.get('extra_template_paths', '')])

    def package_form(self):
        """
        Returns a string representing the location of the template to be
        rendered.  e.g. "package/new_package_form.html".
        """
        return 'dataset_form.html'

    def is_fallback(self):
        """
        Returns true iff this provides the fallback behaviour, when no other
        plugin instance matches a package's type.

        As this is not the fallback controller we should return False.  If
        we were wanting to act as the fallback, we'd return True
        """
        return True

    def package_types(self):
        """
        Returns an iterable of package type strings.

        If a request involving a package of one of those types is made, then
        this plugin instance will be delegated to.

        There must only be one plugin registered to each package type.  Any
        attempts to register more than one plugin instance to a given package
        type will raise an exception at startup.
        """
        return ["dataset"]

    def setup_template_variables(self, context, data_dict=None):
        """
        Adds variables to c just prior to the template being rendered that can
        then be used within the form
        """
        c.licences = [('', '')] + model.Package.get_license_options()
        c.publishers = [('Example publisher', 'Example publisher 2')]
        c.is_sysadmin = Authorizer().is_sysadmin(c.user)
        c.resource_columns = model.Resource.get_columns()
        c.groups_available = c.userobj.get_groups('publisher') if c.userobj else []


        ## This is messy as auths take domain object not data_dict
        pkg = context.get('package') or c.pkg
        if pkg:
            c.auth_for_change_state = Authorizer().am_authorized(
                c, model.Action.CHANGE_STATE, pkg)

    def form_to_db_schema(self):
        """
        Returns the schema for mapping package data from a form to a format
        suitable for the database.
        """
        return package_form_schema()

    def db_to_form_schema(data):
        """
        Returns the schema for mapping package data from the database into a
        format suitable for the form (optional)
        """
        return {}

    def check_data_dict(self, data_dict):
        """
        Check if the return data is correct and raises a DataError if not.
        """
        pass

