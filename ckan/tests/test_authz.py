import ckan.model as model
import ckan.model.authz as mauthz
import ckan.authz

from copy import copy
from ckan.model import Role, Action

class TestBlacklister(object):

    def test_1(self):
        blacklister = ckan.authz.Blacklister()
        bad_username = u'83.222.23.234' # in test.ini
        good_username = u'124.168.141.31'
        good_username2 = u'testadmin'
        assert blacklister.is_blacklisted(bad_username)
        assert not blacklister.is_blacklisted(good_username)
        assert not blacklister.is_blacklisted(good_username2)


class TestAuthorizer(object):

    @classmethod
    def setup_class(self):
        model.Session.add(model.Package(name=u'testpkg'))
        model.Session.add(model.Package(name=u'testpkg2'))
        model.Session.add(model.User(name=u'testadmin'))
        model.Session.add(model.User(name=u'testsysadmin'))
        model.Session.add(model.User(name=u'notadmin'))
        model.Session.add(model.Group(name=u'testgroup'))
        model.Session.add(model.Group(name=u'testgroup2'))
        model.repo.new_revision()
        model.repo.commit_and_remove()

        pkg = model.Package.by_name(u'testpkg')
        grp = model.Group.by_name(u'testgroup')
        admin = model.User.by_name(u'testadmin')
        sysadmin = model.User.by_name(u'testsysadmin')
        model.add_user_to_role(admin, model.Role.ADMIN, pkg)
        model.add_user_to_role(admin, model.Role.ADMIN, grp)
        model.add_user_to_role(sysadmin, model.Role.ADMIN, model.System())
        model.repo.commit_and_remove()

        self.authorizer = ckan.authz.Authorizer()
        self.pkg = model.Package.by_name(u'testpkg')
        self.pkg2 = model.Package.by_name(u'testpkg2')
        self.grp = model.Group.by_name(u'testgroup')
        self.grp2 = model.Group.by_name(u'testgroup2')
        self.admin = model.User.by_name(u'testadmin')
        self.sysadmin = model.User.by_name(u'testsysadmin')
        self.notadmin = model.User.by_name(u'notadmin')

    @classmethod
    def teardown_class(self):
        model.Session.remove()
        model.repo.rebuild_db()
        model.Session.remove()

    authorizer = ckan.authz.Authorizer()

    def test_pkg_admin(self):
        action = model.Action.PURGE
        assert self.authorizer.is_authorized(self.admin.name, action, self.pkg)
        assert not self.authorizer.is_authorized(self.admin.name, action, self.pkg2)
        assert not self.authorizer.is_authorized(u'blah', action, self.pkg)

    def test_grp_admin(self):
        action = model.Action.PURGE
        assert self.authorizer.is_authorized(self.admin.name, action, self.grp)
        assert not self.authorizer.is_authorized(self.admin.name, action, self.grp2)
        assert not self.authorizer.is_authorized(u'blah', action, self.grp)

    def test_pkg_sys_admin(self):
        action = model.Action.PURGE
        assert self.authorizer.is_authorized(self.sysadmin.name, action, self.pkg)
        assert self.authorizer.is_authorized(self.sysadmin.name, action, self.pkg2)
        assert not self.authorizer.is_authorized(u'blah', action, self.pkg)

    def test_grp_sys_admin(self):
        action = model.Action.PURGE
        assert self.authorizer.is_authorized(self.sysadmin.name, action, self.grp)
        assert self.authorizer.is_authorized(self.sysadmin.name, action, self.grp2)
        assert not self.authorizer.is_authorized(u'blah', action, self.grp)

    def test_blacklist_edit_pkg(self):
        action = model.Action.EDIT
        username = u'testadmin'
        bad_username = u'83.222.23.234'
        assert self.authorizer.is_authorized(self.admin.name, action, self.pkg)
        assert not self.authorizer.is_authorized(bad_username, action, self.pkg)

    def test_blacklist_edit_grp(self):
        action = model.Action.EDIT
        username = u'testadmin'
        bad_username = u'83.222.23.234'
        assert self.authorizer.is_authorized(self.admin.name, action, self.grp)
        assert not self.authorizer.is_authorized(bad_username, action, self.grp)

    def test_revision_purge(self):
        action = model.Action.PURGE
        isa = self.authorizer.is_authorized(self.sysadmin.name, action,
                model.Revision)
        assert isa, isa
        isnot = self.authorizer.is_authorized(self.notadmin.name, action,
                model.Revision)
        assert not isnot, isnot


class TestLockedDownAuthorizer(object):

    @classmethod
    def setup_class(self):
        q = model.Session.query(model.UserObjectRole).filter(model.UserObjectRole.role==Role.EDITOR)
        q = q.filter(model.UserObjectRole.user==model.User.by_name(u"visitor"))
        model.Session.delete(q.one())
        model.repo.commit_and_remove()
        
        model.Session.add(model.Package(name=u'testpkg'))
        model.Session.add(model.Package(name=u'testpkg2'))
        model.Session.add(model.User(name=u'testadmin'))
        model.Session.add(model.User(name=u'testsysadmin'))
        model.Session.add(model.User(name=u'notadmin'))
        model.Session.add(model.Group(name=u'testgroup'))
        model.Session.add(model.Group(name=u'testgroup2'))
        model.repo.new_revision()
        model.repo.commit_and_remove()

        pkg = model.Package.by_name(u'testpkg')
        grp = model.Group.by_name(u'testgroup')
        admin = model.User.by_name(u'testadmin')
        sysadmin = model.User.by_name(u'testsysadmin')
        model.add_user_to_role(admin, model.Role.ADMIN, pkg)
        model.add_user_to_role(admin, model.Role.ADMIN, grp)
        model.add_user_to_role(sysadmin, model.Role.ADMIN, model.System())
        model.repo.commit_and_remove()

        self.authorizer = ckan.authz.Authorizer()
        self.pkg = model.Package.by_name(u'testpkg')
        self.pkg2 = model.Package.by_name(u'testpkg2')
        self.grp = model.Group.by_name(u'testgroup')
        self.grp2 = model.Group.by_name(u'testgroup2')
        self.admin = model.User.by_name(u'testadmin')
        self.sysadmin = model.User.by_name(u'testsysadmin')
        self.notadmin = model.User.by_name(u'notadmin')

    @classmethod
    def teardown_class(self):
        model.Session.remove()
        model.repo.rebuild_db()
        model.Session.remove()

    authorizer = ckan.authz.Authorizer()

    def test_pkg_create(self):
        action = model.Action.PACKAGE_CREATE
        assert self.authorizer.is_authorized(self.admin.name, action, model.System())
        assert self.authorizer.is_authorized(self.notadmin.name, action, model.System())
        assert not self.authorizer.is_authorized(u'blah', action, model.System())
        assert not self.authorizer.is_authorized(u'visitor', action, model.System())
    
    def test_pkg_edit(self):
        #reproduce a bug 
        from pprint import pprint 
        pprint(model.Session.query(model.RoleAction).all())
        pprint(model.Session.query(model.UserObjectRole).all())
        action = model.Action.EDIT
        assert self.authorizer.is_authorized(self.notadmin.name, action, model.System())
    
    def test_pkg_admin(self):
        action = model.Action.PURGE
        assert self.authorizer.is_authorized(self.admin.name, action, self.pkg)
        assert not self.authorizer.is_authorized(self.admin.name, action, self.pkg2)
        assert not self.authorizer.is_authorized(u'blah', action, self.pkg)

    def test_grp_sys_admin(self):
        action = model.Action.PURGE
        assert self.authorizer.is_authorized(self.sysadmin.name, action, self.grp)
        assert self.authorizer.is_authorized(self.sysadmin.name, action, self.grp2)
        assert not self.authorizer.is_authorized(u'blah', action, self.grp)


class TestAuthorizerForAuthorizationGroups(object):

    @classmethod
    def setup_class(self):
        model.Session.add(model.Package(name=u'testpkg'))
        model.Session.add(model.Group(name=u'testgroup'))
        model.Session.add(model.User(name=u'ag_member'))
        model.Session.add(model.User(name=u'ag_notmember'))
        model.Session.add(model.AuthorizationGroup(name=u'authz_group'))
        model.repo.new_revision()
        model.repo.commit_and_remove()

        pkg = model.Package.by_name(u'testpkg')
        grp = model.Group.by_name(u'testgroup')
        authzgrp = model.AuthorizationGroup.by_name(u'authz_group')
        member = model.User.by_name(u'ag_member')
        #sysadmin = model.User.by_name(u'testsysadmin')
        model.add_authorization_group_to_role(authzgrp, model.Role.ADMIN, pkg)
        model.add_authorization_group_to_role(authzgrp, model.Role.ADMIN, grp)
        model.add_user_to_authorization_group(member, authzgrp, model.Role.ADMIN)
        model.repo.commit_and_remove()

        self.authorizer = ckan.authz.Authorizer()
        self.pkg = model.Package.by_name(u'testpkg')
        self.grp = model.Group.by_name(u'testgroup')
        self.member = model.User.by_name(u'ag_member')
        self.notmember = model.User.by_name(u'ag_notmember')
        self.authzgrp = model.AuthorizationGroup.by_name(u'authz_group')

    @classmethod
    def teardown_class(self):
        model.Session.remove()
        model.repo.rebuild_db()
        model.Session.remove()

    authorizer = ckan.authz.Authorizer()

    def test_edit_via_grp(self):
        action = model.Action.EDIT
        assert not self.authorizer.is_authorized(self.notmember.name, action, self.pkg)
        assert not self.authorizer.is_authorized(self.notmember.name, action, self.grp)
        assert self.authorizer.is_authorized(self.member.name, action, self.pkg)
        assert self.authorizer.is_authorized(self.member.name, action, self.grp)
        
    def test_add_to_authzgrp(self):
        model.Session.add(model.User(name=u'ag_joiner'))
        model.repo.new_revision()
        model.repo.commit_and_remove()
        user = model.User.by_name(u'ag_joiner')
        assert not model.user_in_authorization_group(user, self.authzgrp)
        model.add_user_to_authorization_group(member, authzgrp, model.Role.ADMIN)
        model.repo.new_revision()
        model.repo.commit_and_remove()
        assert model.user_in_authorization_group(user, self.authzgrp)

    def test_remove_from_authzgrp(self):
        model.Session.add(model.User(name=u'ag_leaver'))
        model.repo.new_revision()
        model.repo.commit_and_remove()
        user = model.User.by_name(u'ag_leaver')
        model.add_user_to_authorization_group(member, authzgrp, model.Role.ADMIN)
        model.repo.new_revision()
        model.repo.commit_and_remove()
        assert model.user_in_authorization_group(user, self.authzgrp)
        model.remove_user_from_authorization_group(member, authzgrp, model.Role.ADMIN)
        model.repo.new_revision()
        model.repo.commit_and_remove()
        assert not model.user_in_authorization_group(user, self.authzgrp)

    def test_authzgrp_edit_rights(self):
        assert self.authorizer.is_authorized(self.member.name, model.Action.READ, self.authzgrp)
        assert self.authorizer.is_authorized(self.notmember.name, model.Action.READ, self.authzgrp)
        assert self.authorizer.is_authorized(self.member.name, model.Action.EDIT, self.authzgrp)
        assert not self.authorizer.is_authorized(self.notmember.name, model.Action.EDIT, self.authzgrp)
