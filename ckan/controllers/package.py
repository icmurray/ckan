import logging
import urlparse
from urllib import urlencode
import json

from sqlalchemy.orm import eagerload_all
from sqlalchemy import or_
import genshi
from pylons import config, cache
from pylons.i18n import get_lang, _
from autoneg.accept import negotiate

import ckan.logic.action.create as create
import ckan.logic.action.update as update
import ckan.logic.action.get as get
from ckan.logic.schema import package_form_schema
from ckan.lib.base import request, c, BaseController, model, abort, h, g, render
from ckan.lib.base import etag_cache, response, redirect, gettext
from ckan.authz import Authorizer
from ckan.lib.search import query_for, SearchError
from ckan.lib.cache import proxy_cache
from ckan.lib.package_saver import PackageSaver, ValidationException
from ckan.lib.navl.dictization_functions import DataError, unflatten, validate
from ckan.logic import NotFound, NotAuthorized, ValidationError
from ckan.logic import tuplize_dict, clean_dict, parse_params, flatten_to_string_key
from ckan.plugins import PluginImplementations, IPackageController
from ckan.lib.dictization import table_dictize
import ckan.forms
import ckan.authz
import ckan.rating
import ckan.misc

log = logging.getLogger('ckan.controllers')

def search_url(params):
    url = h.url_for(controller='package', action='search')
    params = [(k, v.encode('utf-8') if isinstance(v, basestring) else str(v)) \
                    for k, v in params]
    return url + u'?' + urlencode(params)

autoneg_cfg = [
    ("application", "xhtml+xml", ["html"]),
    ("text", "html", ["html"]),
    ("application", "rdf+xml", ["rdf"]),
    ("application", "turtle", ["ttl"]),
    ("text", "plain", ["nt"]),
    ("text", "x-graphviz", ["dot"]),
    ]

class PackageController(BaseController):

    ## hooks for subclasses 
    package_form = 'package/new_package_form.html'

    def _form_to_db_schema(self):
        return package_form_schema()

    def _db_to_form_schema(self):
        '''This is an interface to manipulate data from the database
        into a format suitable for the form (optional)'''

    def _check_data_dict(self, data_dict):
        '''Check if the return data is correct, mostly for checking out if
        spammers are submitting only part of the form'''

        surplus_keys_schema = ['__extras', '__junk', 'state', 'groups',
                               'extras_validation', 'save', 'preview',
                               'return_to']

        schema_keys = package_form_schema().keys()
        keys_in_schema = set(schema_keys) - set(surplus_keys_schema)

        if keys_in_schema - set(data_dict.keys()):
            log.info('incorrect form fields posted')
            raise DataError(data_dict)

    def _setup_template_variables(self, context):
        c.groups = get.group_list_availible(context)
        c.groups_authz = get.group_list_authz(context)
        c.licences = [('', '')] + model.Package.get_license_options()
        c.is_sysadmin = Authorizer().is_sysadmin(c.user)
        c.resource_columns = model.Resource.get_columns()

        ## This is messy as auths take domain object not data_dict
        pkg = context.get('package') or c.pkg
        if pkg:
            c.auth_for_change_state = Authorizer().am_authorized(
                c, model.Action.CHANGE_STATE, pkg)

    ## end hooks

    authorizer = ckan.authz.Authorizer()
    extensions = PluginImplementations(IPackageController)

    def search(self):        
        if not self.authorizer.am_authorized(c, model.Action.SITE_READ, model.System):
            abort(401, _('Not authorized to see this page'))
        q = c.q = request.params.get('q') # unicode format (decoded from utf8)
        c.open_only = request.params.get('open_only')
        c.downloadable_only = request.params.get('downloadable_only')
        c.query_error = False
        try:
            page = int(request.params.get('page', 1))
        except ValueError, e:
            abort(400, ('"page" parameter must be an integer'))
        limit = 20
        query = query_for(model.Package)

        # most search operations should reset the page counter:
        params_nopage = [(k, v) for k,v in request.params.items() if k != 'page']
        
        def drill_down_url(**by):
            params = list(params_nopage)
            params.extend(by.items())
            return search_url(set(params))
        
        c.drill_down_url = drill_down_url 
        
        def remove_field(key, value):
            params = list(params_nopage)
            params.remove((key, value))
            return search_url(params)

        c.remove_field = remove_field
        
        def pager_url(q=None, page=None):
            params = list(params_nopage)
            params.append(('page', page))
            return search_url(params)

        try:
            c.fields = []
            for (param, value) in request.params.items():
                if not param in ['q', 'open_only', 'downloadable_only', 'page'] \
                        and len(value) and not param.startswith('_'):
                    c.fields.append((param, value))

            query.run(query=q,
                      fields=c.fields,
                      facet_by=g.facets,
                      limit=limit,
                      offset=(page-1)*limit,
                      return_objects=True,
                      filter_by_openness=c.open_only,
                      filter_by_downloadable=c.downloadable_only,
                      username=c.user)
                       
            c.page = h.Page(
                collection=query.results,
                page=page,
                url=pager_url,
                item_count=query.count,
                items_per_page=limit
            )
            c.facets = query.facets
            c.page.items = query.results
        except SearchError, se:
            c.query_error = True
            c.facets = {}
            c.page = h.Page(collection=[])
        
        return render('package/search.html')

    @staticmethod
    def _pkg_cache_key(pkg):
        # note: we need pkg.id in addition to pkg.revision.id because a
        # revision may have more than one package in it.
        return str(hash((pkg.id, pkg.latest_related_revision.id, c.user, pkg.get_average_rating())))

    def _clear_pkg_cache(self, pkg):
        read_cache = cache.get_cache('package/read.html', type='dbm')
        read_cache.remove_value(self._pkg_cache_key(pkg))

    @proxy_cache()
    def read(self, id):
        
        #check if package exists
        c.pkg = model.Package.get(id)
        if c.pkg is None:
            abort(404, _('Package not found'))
        
        cache_key = self._pkg_cache_key(c.pkg)        
        etag_cache(cache_key)
        
        #set a cookie so we know whether to display the welcome message
        c.hide_welcome_message = bool(request.cookies.get('hide_welcome_message', False))
        response.set_cookie('hide_welcome_message', '1', max_age=3600) #(make cross-site?)

        # used by disqus plugin
        c.current_package_id = c.pkg.id
        
        if config.get('rdf_packages') is not None:
            accept_header = request.headers.get('Accept', '*/*')
            for content_type, exts in negotiate(autoneg_cfg, accept_header):
                if "html" not in exts: 
                    rdf_url = '%s%s.%s' % (config['rdf_packages'], c.pkg.id, exts[0])
                    redirect(rdf_url, code=303)
                break
            
        #is the user allowed to see this package?
        auth_for_read = self.authorizer.am_authorized(c, model.Action.READ, c.pkg)
        if not auth_for_read:
            abort(401, _('Unauthorized to read package %s') % id)
        
        for item in self.extensions:
            item.read(c.pkg)

        #render the package
        PackageSaver().render_package(c.pkg)
        return render('package/read.html')

    def comments(self, id):

        #check if package exists
        c.pkg = model.Package.get(id)
        if c.pkg is None:
            abort(404, _('Package not found'))

        # used by disqus plugin
        c.current_package_id = c.pkg.id

        #is the user allowed to see this package?
        auth_for_read = self.authorizer.am_authorized(c, model.Action.READ, c.pkg)
        if not auth_for_read:
            abort(401, _('Unauthorized to read package %s') % id)

        for item in self.extensions:
            item.read(c.pkg)

        #render the package
        PackageSaver().render_package(c.pkg)
        return render('package/comments.html')


    def history(self, id):
        if 'diff' in request.params or 'selected1' in request.params:
            try:
                params = {'id':request.params.getone('pkg_name'),
                          'diff':request.params.getone('selected1'),
                          'oldid':request.params.getone('selected2'),
                          }
            except KeyError, e:
                if dict(request.params).has_key('pkg_name'):
                    id = request.params.getone('pkg_name')
                c.error = _('Select two revisions before doing the comparison.')
            else:
                params['diff_entity'] = 'package'
                h.redirect_to(controller='revision', action='diff', **params)

        c.pkg = model.Package.get(id)
        if not c.pkg:
            abort(404, _('Package not found'))
        format = request.params.get('format', '')
        if format == 'atom':
            # Generate and return Atom 1.0 document.
            from webhelpers.feedgenerator import Atom1Feed
            feed = Atom1Feed(
                title=_(u'CKAN Package Revision History'),
                link=h.url_for(controller='revision', action='read', id=c.pkg.name),
                description=_(u'Recent changes to CKAN Package: ') + (c.pkg.title or ''),
                language=unicode(get_lang()),
            )
            for revision, obj_rev in c.pkg.all_related_revisions:
                try:
                    dayHorizon = int(request.params.get('days'))
                except:
                    dayHorizon = 30
                try:
                    dayAge = (datetime.now() - revision.timestamp).days
                except:
                    dayAge = 0
                if dayAge >= dayHorizon:
                    break
                if revision.message:
                    item_title = u'%s' % revision.message.split('\n')[0]
                else:
                    item_title = u'%s' % revision.id
                item_link = h.url_for(controller='revision', action='read', id=revision.id)
                item_description = _('Log message: ')
                item_description += '%s' % (revision.message or '')
                item_author_name = revision.author
                item_pubdate = revision.timestamp
                feed.add_item(
                    title=item_title,
                    link=item_link,
                    description=item_description,
                    author_name=item_author_name,
                    pubdate=item_pubdate,
                )
            feed.content_type = 'application/atom+xml'
            return feed.writeString('utf-8')
        c.pkg_revisions = c.pkg.all_related_revisions
        return render('package/history.html')

    def new(self, data=None, errors=None, error_summary=None):
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'extras_as_string': True,
                   'preview': 'preview' in request.params,
                   'save': 'save' in request.params,
                   'schema': self._form_to_db_schema()}

        auth_for_create = Authorizer().am_authorized(c, model.Action.PACKAGE_CREATE, model.System())
        if not auth_for_create:
            abort(401, _('Unauthorized to create a package'))

        if (context['save'] or context['preview']) and not data:
            return self._save_new(context)

        data = data or {}
        errors = errors or {}
        error_summary = error_summary or {}
        vars = {'data': data, 'errors': errors, 'error_summary': error_summary}

        self._setup_template_variables(context)
        c.form = render(self.package_form, extra_vars=vars)
        return render('package/new.html')


    def edit(self, id, data=None, errors=None, error_summary=None):
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'extras_as_string': True,
                   'preview': 'preview' in request.params,
                   'save': 'save' in request.params,
                   'id': id,
                   'schema': self._form_to_db_schema()}

        if (context['save'] or context['preview']) and not data:
            return self._save_edit(id, context)

        try:
            old_data = get.package_show(context)
            schema = self._db_to_form_schema()
            if schema:
                old_data, errors = validate(old_data, schema)
            data = data or old_data
        except NotAuthorized:
            abort(401, _('Unauthorized to read package %s') % '')

        c.pkg = context.get("package")

        am_authz = self.authorizer.am_authorized(c, model.Action.EDIT, c.pkg)
        if not am_authz:
            abort(401, _('User %r not authorized to edit %s') % (c.user, id))

        errors = errors or {}
        vars = {'data': data, 'errors': errors, 'error_summary': error_summary}

        self._setup_template_variables(context)
        c.form = render(self.package_form, extra_vars=vars)
        return render('package/edit.html')

    def read_ajax(self, id, revision=None):
        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author,
                   'id': id, 'extras_as_string': True,
                   'schema': self._form_to_db_schema()}

        try:
            data = get.package_show(context)
            schema = self._db_to_form_schema()
            if schema:
                data, errors = validate(data, schema)
        except NotAuthorized:
            abort(401, _('Unauthorized to read package %s') % '')

        ## hack as db_to_form schema should have this
        data['tag_string'] = ' '.join([tag['name'] for tag in data.get('tags', [])])
        data.pop('tags')
        data = flatten_to_string_key(data)
        
        if revision:
            revision = model.Session.query(model.PackageRevision).filter_by(
                revision_id=revision, id=data['id']).one()
            data.update(table_dictize(revision, context))

        response.headers['Content-Type'] = 'application/json;charset=utf-8'
        return json.dumps(data)

    def history_ajax(self, id):

        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author,
                   'id': id, 'extras_as_string': True}
        pkg = model.Package.get(id)
        data = []
        for num, (revision, revision_obj) in enumerate(pkg.all_related_revisions):
            data.append({'revision_id': revision.id,
                         'message': revision.message,
                         'timestamp': revision.timestamp.isoformat(),
                         'current_approved': True if num == 0 else False})

        response.headers['Content-Type'] = 'application/json;charset=utf-8'
        return json.dumps(data)

    def _save_new(self, context):
        try:
            data_dict = clean_dict(unflatten(
                tuplize_dict(parse_params(request.params))))
            self._check_data_dict(data_dict)
            context['message'] = data_dict.get('log_message', '')
            pkg = create.package_create(data_dict, context)

            if context['preview']:
                PackageSaver().render_package(context['package'])
                c.is_preview = True
                c.preview = render('package/read_core.html')
                return self.new(data_dict)

            self._form_save_redirect(pkg['name'], 'new')
        except NotAuthorized:
            abort(401, _('Unauthorized to read package %s') % '')
        except NotFound, e:
            abort(404, _('Package not found'))
        except DataError:
            abort(400, _(u'Integrity Error'))
        except ValidationError, e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.new(data_dict, errors, error_summary)

    def _save_edit(self, id, context):
        try:
            data_dict = clean_dict(unflatten(
                tuplize_dict(parse_params(request.params))))
            self._check_data_dict(data_dict)
            context['message'] = data_dict.get('log_message', '')
            pkg = update.package_update(data_dict, context)
            c.pkg = context['package']

            if context['preview']:
                c.is_preview = True
                PackageSaver().render_package(context['package'])
                c.preview = render('package/read_core.html')
                return self.edit(id, data_dict)

            self._form_save_redirect(pkg['name'], 'edit')
        except NotAuthorized:
            abort(401, _('Unauthorized to read package %s') % id)
        except NotFound, e:
            abort(404, _('Package not found'))
        except DataError:
            abort(400, _(u'Integrity Error'))
        except ValidationError, e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.edit(id, data_dict, errors, error_summary)

    def _form_save_redirect(self, pkgname, action):
        '''This redirects the user to the CKAN package/read page,
        unless there is request parameter giving an alternate location,
        perhaps an external website.
        @param pkgname - Name of the package just edited
        @param action - What the action of the edit was
        '''
        assert action in ('new', 'edit')
        url = request.params.get('return_to') or \
              config.get('package_%s_return_url' % action)
        if url:
            url = url.replace('<NAME>', pkgname)
        else:
            url = h.url_for(controller='package', action='read', id=pkgname)
        redirect(url)        
        
    def _adjust_license_id_options(self, pkg, fs):
        options = fs.license_id.render_opts['options']
        is_included = False
        for option in options:
            license_id = option[1]
            if license_id == pkg.license_id:
                is_included = True
        if not is_included:
            options.insert(1, (pkg.license_id, pkg.license_id))

    def authz(self, id):
        pkg = model.Package.get(id)
        if pkg is None:
            abort(404, gettext('Package not found'))
        c.pkgname = pkg.name
        c.pkgtitle = pkg.title

        c.authz_editable = self.authorizer.am_authorized(c, model.Action.EDIT_PERMISSIONS, pkg)
        if not c.authz_editable:
            abort(401, gettext('User %r not authorized to edit %s authorizations') % (c.user, id))

        if 'save' in request.params: # form posted
            # A dict needed for the params because request.params is a nested
            # multidict, which is read only.
            params = dict(request.params)
            c.fs = ckan.forms.get_authz_fieldset('package_authz_fs').bind(pkg.roles, data=params or None)
            try:
                self._update_authz(c.fs)
            except ValidationException, error:
                # TODO: sort this out 
                # fs = error.args
                # return render('package/authz.html')
                raise
            # now do new roles
            newrole_user_id = request.params.get('PackageRole--user_id')
            newrole_authzgroup_id = request.params.get('PackageRole--authorized_group_id')
            if newrole_user_id != '__null_value__' and newrole_authzgroup_id != '__null_value__':
                c.message = _(u'Please select either a user or an authorization group, not both.')
            elif newrole_user_id != '__null_value__':
                user = model.Session.query(model.User).get(newrole_user_id)
                # TODO: chech user is not None (should go in validation ...)
                role = request.params.get('PackageRole--role')
                newpkgrole = model.PackageRole(user=user, package=pkg,
                        role=role)
                # With FA no way to get new PackageRole back to set package attribute
                # new_roles = ckan.forms.new_roles_fs.bind(model.PackageRole, data=params or None)
                # new_roles.sync()
                for item in self.extensions:
                    item.authz_add_role(newpkgrole)
                model.repo.commit_and_remove()
                c.message = _(u'Added role \'%s\' for user \'%s\'') % (
                    newpkgrole.role,
                    newpkgrole.user.display_name)
            elif newrole_authzgroup_id != '__null_value__':
                authzgroup = model.Session.query(model.AuthorizationGroup).get(newrole_authzgroup_id)
                # TODO: chech user is not None (should go in validation ...)
                role = request.params.get('PackageRole--role')
                newpkgrole = model.PackageRole(authorized_group=authzgroup, 
                        package=pkg, role=role)
                # With FA no way to get new GroupRole back to set group attribute
                # new_roles = ckan.forms.new_roles_fs.bind(model.GroupRole, data=params or None)
                # new_roles.sync()
                for item in self.extensions:
                    item.authz_add_role(newpkgrole)
                model.Session.commit()
                model.Session.remove()
                c.message = _(u'Added role \'%s\' for authorization group \'%s\'') % (
                    newpkgrole.role,
                    newpkgrole.authorized_group.name)
        elif 'role_to_delete' in request.params:
            pkgrole_id = request.params['role_to_delete']
            pkgrole = model.Session.query(model.PackageRole).get(pkgrole_id)
            if pkgrole is None:
                c.error = _(u'Error: No role found with that id')
            else:
                for item in self.extensions:
                    item.authz_remove_role(pkgrole)
                if pkgrole.user:
                    c.message = _(u'Deleted role \'%s\' for user \'%s\'') % \
                                (pkgrole.role, pkgrole.user.display_name)
                elif pkgrole.authorized_group:
                    c.message = _(u'Deleted role \'%s\' for authorization group \'%s\'') % \
                                (pkgrole.role, pkgrole.authorized_group.name)
                pkgrole.purge()
                model.repo.commit_and_remove()

        # retrieve pkg again ...
        c.pkg = model.Package.get(id)
        fs = ckan.forms.get_authz_fieldset('package_authz_fs').bind(c.pkg.roles)
        c.form = fs.render()
        c.new_roles_form = \
            ckan.forms.get_authz_fieldset('new_package_roles_fs').render()
        return render('package/authz.html')

    def rate(self, id):
        package_name = id
        package = model.Package.get(package_name)
        if package is None:
            abort(404, gettext('404 Package Not Found'))
        self._clear_pkg_cache(package)
        rating = request.params.get('rating', '')
        if rating:
            try:
                ckan.rating.set_my_rating(c, package, rating)
            except ckan.rating.RatingValueException, e:
                abort(400, gettext('Rating value invalid'))
        h.redirect_to(controller='package', action='read', id=package_name, rating=str(rating))

    def autocomplete(self):
        q = unicode(request.params.get('q', ''))
        if not len(q): 
            return ''
        pkg_list = []
        like_q = u"%s%%" % q
        pkg_query = ckan.authz.Authorizer().authorized_query(c.user, model.Package)
        pkg_query = pkg_query.filter(or_(model.Package.name.ilike(like_q),
                                         model.Package.title.ilike(like_q)))
        pkg_query = pkg_query.limit(10)
        for pkg in pkg_query:
            if pkg.name.lower().startswith(q.lower()):
                pkg_list.append('%s|%s' % (pkg.name, pkg.name))
            else:
                pkg_list.append('%s (%s)|%s' % (pkg.title.replace('|', ' '), pkg.name, pkg.name))
        return '\n'.join(pkg_list)

    def _render_edit_form(self, fs, params={}, clear_session=False):
        # errors arrive in c.error and fs.errors
        c.log_message = params.get('log_message', '')
        # rgrp: expunge everything from session before dealing with
        # validation errors) so we don't have any problematic saves
        # when the fs.render causes a flush.
        # seb: If the session is *expunged*, then the form can't be
        # rendered; I've settled with a rollback for now, which isn't
        # necessarily what's wanted here.
        # dread: I think this only happened with tags because until
        # this changeset, Tag objects were created in the Renderer
        # every time you hit preview. So I don't believe we need to
        # clear the session any more. Just in case I'm leaving it in
        # with the log comments to find out.
        if clear_session:
            # log to see if clearing the session is ever required
            if model.Session.new or model.Session.dirty or model.Session.deleted:
                log.warn('Expunging session changes which were not expected: '
                         '%r %r %r', (model.Session.new, model.Session.dirty,
                                      model.Session.deleted))
            try:
                model.Session.rollback()
            except AttributeError: # older SQLAlchemy versions
                model.Session.clear()
        edit_form_html = fs.render()
        c.form = h.literal(edit_form_html)
        return h.literal(render('package/edit_form.html'))

    def _update_authz(self, fs):
        validation = fs.validate()
        if not validation:
            c.form = self._render_edit_form(fs, request.params)
            raise ValidationException(fs)
        try:
            fs.sync()
        except Exception, inst:
            model.Session.rollback()
            raise
        else:
            model.Session.commit()

    def _person_email_link(self, name, email, reference):
        if email:
            if not name:
                name = email
            return h.mail_to(email_address=email, name=name, encode='javascript')
        else:
            if name:
                return name
            else:
                return reference + " unknown"
