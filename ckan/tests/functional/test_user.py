from ckan.tests import *
import ckan.model as model

class TestUserController(TestController):
    @classmethod
    def setup_class(self):
        model.repo.rebuild_db()
        CreateTestData.create()

        # make 3 changes, authored by annafan
        for i in range(3):
            pkg = model.Package.by_name(u'annakarenina')
            pkg.notes = u'Changed notes %i' % i
            rev = model.repo.new_revision()
            rev.author = u'annafan'
            model.repo.commit_and_remove()

    @classmethod
    def teardown_class(self):
        model.repo.rebuild_db()

    def test_user_index(self):
        offset = url_for(controller='user')
        # TODO

    def test_user_read(self):
        user = model.User.by_name(u'annafan')
        offset = url_for(controller='user', action='read', id=user.id)
        res = self.app.get(offset, status=200)
        assert 'User Account - annafan' in res, res
        assert 'Number of edits:</strong> 3' in res, res
        assert 'Number of packages administered:</strong> 1' in res, res
        assert 'Recent changes' in res, res

    def test_user_read_logged_in(self):
        user = model.User.by_name(u'annafan')
        offset = url_for(controller='user', action='read', id=user.id)
        res = self.app.get(offset, extra_environ={'REMOTE_USER': str(user.name)})
        assert 'User Account - annafan' in res, res
        assert 'Logged in as <strong>%s</strong>' % user.name in res, res
        assert 'View your API key' in res

    def test_user_login(self):
        offset = url_for(controller='user', action='login')
        res = self.app.get(offset, status=200)
        assert 'Login' in res, res
        assert 'use your OpenID' in res
        assert 'haven\'t already got an OpenID' in res

    def test_logout(self):
        offset = url_for(controller='user', action='logout')
        res = self.app.get(offset)
        assert 'You have logged out successfully.' in res

    def test_user_created_on_login(self):
        username = u'okfntest'
        user = model.User.by_name(username)
        if user:
            user.purge()
            model.Session.commit()
            model.Session.remove()

        offset = url_for(controller='user', action='login')
        res = self.app.get(offset, extra_environ=dict(REMOTE_USER='okfntest'))
        user = model.User.by_name(u'okfntest')
        assert user
        assert len(user.apikey) == 36


    def test_apikey(self):
        # not_logged_in
        user = model.User.by_name(u'okfntest')
        if user:
            user.purge()
            model.Session.commit()
            model.Session.remove()

        offset = url_for(controller='user', action='login')
        res = self.app.get(offset, extra_environ=dict(REMOTE_USER='okfntest'))
        res = self.app.get(offset, status=[302]) 

    # -----------
    # tests for top links present in every page
     # TODO: test sign in results in:
     # a) a username at top of page
     # b) logout link

    def test_home_login(self):
        offset = url_for('home')
        res = self.app.get(offset)
        # cannot use click because it does not allow a 401 response ...
        # could get round this by checking that url is correct and then doing a
        # get but then we are back to test_user_login
        res.click('Login via OpenID')
        # assert 'Please Sign In' in res

    def test_apikey(self):
        username= u'okfntest'
        user = model.User.by_name(u'okfntest')
        if not user:
            user = model.User(name=u'okfntest')
            model.Session.commit()
            model.Session.remove()

        # not logged in
        offset = url_for(controller='user', action='apikey')
        res = self.app.get(offset, status=[302]) 

        res = self.app.get(offset, extra_environ=dict(REMOTE_USER='okfntest'))
        print user.apikey
        assert 'Your API key is: %s' % user.apikey in res, res



    ############
    # Disabled
    ############

    # TODO: 2009-06-27 delete/update these methods (now moving to repoze)
    def _login_form(self, res):
        # cannot use for time being due to 'bug' in AuthKit
        # paste.fixture does not set REMOTE_ADDR which AuthKit requires to do
        # its stuff (though note comment in code suggesting amendment)
        # create cookie see authkit/authenticate/cookie.py l. 364 
            # if self.include_ip:
            # # Fixes ticket #30
            # # @@@ should this use environ.get('REMOTE_ADDR','0.0.0.0')?
            #  remote_addr = environ.get('HTTP_X_FORWARDED_FOR', environ['REMOTE_ADDR'])
            #  
            # KeyError: 'REMOTE_ADDR' 
        # could get round this by adding stuff to environ using paste fixture's
        # extra_environ, see:
        # http://pythonpaste.org/webtest/#modifying-the-environment-simulating-authentication
        assert 'Please Sign In' in res
        username = u'okfntest'
        password = u'okfntest'
        fv = res.forms[0]
        fv['username'] = username
        fv['password'] = password
        res = fv.submit()
        return res

    def _login_openid(self, res):
        # this requires a valid account on some openid provider
        # (or for us to stub an open_id provider ...)
        assert 'Please Sign In' in res
        username = u'http://okfntest.myopenid.com'
        fv = res.forms[0]
        fv['passurl'] =  username
        web.submit()
        web.code(200)
        assert 'You must sign in to authenticate to' in res
        assert username in res
        fv['password'] =  u'okfntest'
        res = fv.submit()
        print str(res)
        assert 'Please carefully verify whether you wish to trust' in res
        fv = res.forms[0]
        res = fv.submit('allow_once')
        # at this point we should return
        # but for some reason this does not work ...
        return res

