from routes import url_for
from nose.tools import assert_equal

from ckan.tests import search_related, CreateTestData
from ckan.tests.html_check import HtmlCheckMethods
from ckan.tests.pylons_controller import PylonsTestCase
from ckan.tests.mock_mail_server import SmtpServerHarness
import ckan.model as model
from base import FunctionalTestCase
from ckan.lib.mailer import get_reset_link, create_reset_key

class TestUserController(FunctionalTestCase, HtmlCheckMethods, PylonsTestCase, SmtpServerHarness):
    @classmethod
    def setup_class(self):
        PylonsTestCase.setup_class()
        SmtpServerHarness.setup_class()
        CreateTestData.create()

        # make 3 changes, authored by annafan
        for i in range(3):
            rev = model.repo.new_revision()
            pkg = model.Package.by_name(u'annakarenina')
            pkg.notes = u'Changed notes %i' % i
            rev.author = u'annafan'
            model.repo.commit_and_remove()

        CreateTestData.create_user('unfinisher', about='<a href="http://unfinished.tag')
        CreateTestData.create_user('uncloser', about='<a href="http://unclosed.tag">')
        CreateTestData.create_user('spammer', about=u'<a href="http://mysite">mysite</a> <a href=\u201dhttp://test2\u201d>test2</a>')
        CreateTestData.create_user('spammer2', about=u'<a href="http://spamsite1.com\u201d>spamsite1</a>\r\n<a href="http://www.spamsite2.com\u201d>spamsite2</a>\r\n')
        
    @classmethod
    def teardown_class(self):
        SmtpServerHarness.teardown_class()
        model.repo.rebuild_db()

    def teardown(self):
        # just ensure we're not logged in
        self.app.get('/user/logout')

    def test_user_read(self):
        user = model.User.by_name(u'annafan')
        offset = '/user/%s' % user.id
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'annafan' in res, res
        assert 'Logged in' not in main_res, main_res
        assert 'My Account' not in main_res, main_res
        assert 'about' in main_res, main_res
        assert 'I love reading Annakarenina' in res, main_res
        self.check_named_element(res, 'a',
                                 'http://anna.com',
                                 'target="_blank"',
                                 'rel="nofollow"')
        assert 'Edit' not in main_res, main_res
        assert 'Number of edits:</strong> 3' in res, res
        assert 'Number of packages administered:</strong> 1' in res, res
        assert 'Revision History' in res, res

    def test_user_read_without_id(self):
        offset = '/user/'
        res = self.app.get(offset, status=302)

    def test_user_read_without_id_but_logged_in(self):
        user = model.User.by_name(u'annafan')
        offset = '/user/'
        res = self.app.get(offset, status=200, extra_environ={'REMOTE_USER': str(user.name)})
        main_res = self.main_div(res)
        assert 'annafan' in main_res, main_res
        assert 'My Account' in main_res, main_res

    def test_user_read_logged_in(self):
        user = model.User.by_name(u'annafan')
        offset = '/user/%s' % user.id
        res = self.app.get(offset, extra_environ={'REMOTE_USER': str(user.name)})
        main_res = self.main_div(res)
        assert 'annafan' in res, res
        assert 'My Account' in main_res, main_res
        assert 'Edit' in main_res, main_res

    def test_user_read_about_unfinished(self):
        user = model.User.by_name(u'unfinisher')
        offset = '/user/%s' % user.id
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'unfinisher' in res, res
        assert '&lt;a href="http://unfinished.tag' in main_res, main_res

    def test_user_read_about_unclosed(self):
        user = model.User.by_name(u'uncloser')
        offset = '/user/%s' % user.id
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'unclosed' in res, res
        # tag gets closed by genshi
        assert '<a href="http://unclosed.tag" target="_blank" rel="nofollow">\n</a>' in main_res, main_res

    def test_user_read_about_spam(self):
        user = model.User.by_name(u'spammer')
        offset = '/user/%s' % user.id
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'spammer' in res, res
        self.check_named_element(res, 'a',
                                 'href="http://mysite"',
                                 'target="_blank"',
                                 'rel="nofollow"')

        self.check_named_element(res, 'a',
                                 'href="TAG MALFORMED"',
                                 'target="_blank"',
                                 'rel="nofollow"')

    def test_user_read_about_spam2(self):
        user = model.User.by_name(u'spammer2')
        offset = '/user/%s' % user.id
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'spammer2' in res, res
        assert 'spamsite2' not in res, res
        assert 'Error: Could not parse About text' in res, res
        
    def test_user_login(self):
        offset = url_for(controller='user', action='login', id=None)
        res = self.app.get(offset, status=200)
        assert 'Login' in res, res
        assert 'Please click your account provider' in res, res
        assert 'Don\'t have an OpenID' in res, res

    def test_logout(self):
        res = self.app.get('/user/logout')
        res2 = res.follow()
        assert 'You have logged out successfully.' in res2, res2

    #def test_user_created_on_login(self):
    #    username = u'okfntest'
    #    user = model.User.by_name(username)
    #    if user:
    #        user.purge()
    #        model.Session.commit()
    #        model.Session.remove()

    #    offset = url_for(controller='user', action='login')
    #    res = self.app.get(offset, extra_environ=dict(REMOTE_USER='okfntest'))
    #    user = model.User.by_name(u'okfntest')
    #    assert user
    #    assert len(user.apikey) == 36

    # -----------
    # tests for top links present in every page
     # TODO: test sign in results in:
     # a) a username at top of page
     # b) logout link

    @search_related
    def test_home_login(self):
        offset = url_for('home')
        res = self.app.get(offset)
        # cannot use click because it does not allow a 401 response ...
        # could get round this by checking that url is correct and then doing a
        # get but then we are back to test_user_login
        res.click('Login')
        # assert 'Please Sign In' in res

    def test_apikey(self):
        username= u'okfntest'
        user = model.User.by_name(u'okfntest')
        if not user:
            user = model.User(name=u'okfntest')
            model.Session.add(user)
            model.Session.commit()
            model.Session.remove()

        # not logged in
        offset = url_for(controller='user', action='read', id=username)
        res = self.app.get(offset) 
        assert not 'API key' in res

        offset = url_for(controller='user', action='read', id='okfntest')
        res = self.app.get(offset, extra_environ={'REMOTE_USER': 'okfntest'})
        assert 'Your API key is: %s' % user.apikey in res, res

    def test_user_create(self):
        # create/register user
        username = 'testcreate'
        fullname = u'Test Create'
        password = u'testpassword'
        assert not model.User.by_name(unicode(username))

        offset = url_for(controller='user', action='register')
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'Register' in main_res, main_res
        fv = res.forms['register_form']
        fv['login'] = username
        fv['fullname'] = fullname
        fv['password1'] = password
        fv['password2'] = password
        res = fv.submit('signup')
        
        # view user
        assert res.status == 302, self.main_div(res).encode('utf8')
        res = res.follow()
        if res.status == 302:
            res = res.follow()
        if res.status == 302:
            res = res.follow()
        if res.status == 302:
            res = res.follow()
        assert res.status == 200, res
        main_res = self.main_div(res)
        assert username in main_res, main_res
        assert fullname in main_res, main_res

        user = model.User.by_name(unicode(username))
        assert user
        assert_equal(user.name, username)
        assert_equal(user.fullname, fullname)
        assert user.password

    def test_user_create_unicode(self):
        # create/register user
        username = u'testcreate4'
        fullname = u'Test Create\xc2\xa0'
        password = u'testpassword\xc2\xa0'
        assert not model.User.by_name(username)

        offset = url_for(controller='user', action='register')
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'Register' in main_res, main_res
        fv = res.forms['register_form']
        fv['login'] = username
        fv['fullname'] = fullname.encode('utf8')
        fv['password1'] = password.encode('utf8')
        fv['password2'] = password.encode('utf8')
        res = fv.submit('signup')
        
        # view user
        assert res.status == 302, self.main_div(res).encode('utf8')
        res = res.follow()
        if res.status == 302:
            res = res.follow()
        if res.status == 302:
            res = res.follow()
        if res.status == 302:
            res = res.follow()
        assert res.status == 200, res
        main_res = self.main_div(res)
        assert username in main_res, main_res
        assert fullname in main_res, main_res

        user = model.User.by_name(unicode(username))
        assert user
        assert_equal(user.name, username)
        assert_equal(user.fullname, fullname)
        assert user.password

    def test_user_create_no_name(self):
        # create/register user
        password = u'testpassword'

        offset = url_for(controller='user', action='register')
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'Register' in main_res, main_res
        fv = res.forms['register_form']
        fv['password1'] = password
        fv['password2'] = password
        res = fv.submit('signup')
        assert res.status == 200, res
        main_res = self.main_div(res)
        assert 'Please enter a login name' in main_res, main_res

    def test_user_create_bad_name(self):
        # create/register user
        username = u'%%%%%%' # characters not allowed
        password = 'testpass'

        offset = url_for(controller='user', action='register')
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'Register' in main_res, main_res
        fv = res.forms['register_form']
        fv['login'] = username
        fv['password1'] = password
        fv['password2'] = password
        res = fv.submit('signup')
        assert res.status == 200, res
        main_res = self.main_div(res)
        assert 'login name is not valid' in main_res, main_res
        self.check_named_element(main_res, 'input', 'name="login"', 'value="%s"' % username)

    def test_user_create_bad_password(self):
        # create/register user
        username = 'testcreate2'
        password = u'a' # too short

        offset = url_for(controller='user', action='register')
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'Register' in main_res, main_res
        fv = res.forms['register_form']
        fv['login'] = username
        fv['password1'] = password
        fv['password2'] = password
        res = fv.submit('signup')
        assert res.status == 200, res
        main_res = self.main_div(res)
        assert 'password must be 4 characters or longer' in main_res, main_res
        self.check_named_element(main_res, 'input', 'name="login"', 'value="%s"' % username)

    def test_user_create_without_password(self):
        # create/register user
        username = 'testcreate3'
        user = model.User.by_name(unicode(username))

        offset = url_for(controller='user', action='register')
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert 'Register' in main_res, main_res
        fv = res.forms['register_form']
        fv['login'] = username
        # no password
        res = fv.submit('signup')
        assert res.status == 200, res
        main_res = self.main_div(res)
        assert 'Please enter a password' in main_res, main_res
        self.check_named_element(main_res, 'input', 'name="login"', 'value="%s"' % username)

    def test_user_edit(self):
        # create user
        username = 'testedit'
        about = u'Test About'
        user = model.User.by_name(unicode(username))
        if not user:
            model.Session.add(model.User(name=unicode(username), about=about,
                                         password='letmein'))
            model.repo.commit_and_remove()
            user = model.User.by_name(unicode(username))

        # edit
        new_about = u'Changed about'
        new_password = u'testpass'
        offset = url_for(controller='user', action='edit', id=user.id)
        res = self.app.get(offset, status=200, extra_environ={'REMOTE_USER':username})
        main_res = self.main_div(res)
        assert 'Edit User: ' in main_res, main_res
        assert about in main_res, main_res
        fv = res.forms['user-edit']
        fv['about'] = new_about
        fv['password1'] = new_password
        fv['password2'] = new_password
        res = fv.submit('preview', extra_environ={'REMOTE_USER':username})
        
        # preview
        main_res = self.main_div(res)
        assert 'Edit User: testedit' in main_res, main_res
        before_preview = main_res[:main_res.find('Preview')]
        assert new_about in before_preview, before_preview
        in_preview = main_res[main_res.find('Preview'):]
        assert new_about in in_preview, in_preview

        # commit
        res = fv.submit('save', extra_environ={'REMOTE_USER':username})      
        assert res.status == 302, self.main_div(res).encode('utf8')
        res = res.follow()
        main_res = self.main_div(res)
        assert 'testedit' in main_res, main_res
        assert new_about in main_res, main_res

        # read, not logged in
        offset = url_for(controller='user', action='read', id=user.id)
        res = self.app.get(offset, status=200)
        main_res = self.main_div(res)
        assert new_about in main_res, main_res

    def test_edit_spammer(self):
        # create user
        username = 'testeditspam'
        about = u'Test About <a href="http://spamsite.net">spamsite</a>'
        user = model.User.by_name(unicode(username))
        if not user:
            model.Session.add(model.User(name=unicode(username), about=about,
                                         password='letmein'))
            model.repo.commit_and_remove()
            user = model.User.by_name(unicode(username))

        # edit
        offset = url_for(controller='user', action='edit', id=user.id)
        res = self.app.get(offset, status=200, extra_environ={'REMOTE_USER':username})
        main_res = self.main_div(res)
        assert 'Edit User: ' in main_res, main_res
        assert 'Test About &lt;a href="http://spamsite.net"&gt;spamsite&lt;/a&gt;' in main_res, main_res
        fv = res.forms['user-edit']
        res = fv.submit('preview', extra_environ={'REMOTE_USER':username})
        # commit
        res = fv.submit('save', extra_environ={'REMOTE_USER':username})      
        assert res.status == 200, res.status
        main_res = self.main_div(res)
        assert 'looks like spam' in main_res, main_res
        assert 'Edit User: ' in main_res, main_res


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
        fv = res.forms['user-login']
        fv['username'] = username
        fv['password'] = password
        res = fv.submit()
        return res

    def _login_openid(self, res):
        # this requires a valid account on some openid provider
        # (or for us to stub an open_id provider ...)
        assert 'Please Sign In' in res
        username = u'http://okfntest.myopenid.com'
        fv = res.forms['user-login']
        fv['passurl'] =  username
        web.submit()
        web.code(200)
        assert 'You must sign in to authenticate to' in res
        assert username in res
        fv['password'] =  u'okfntest'
        res = fv.submit()
        assert 'Please carefully verify whether you wish to trust' in res
        fv = res.forms[0]
        res = fv.submit('allow_once')
        # at this point we should return
        # but for some reason this does not work ...
        return res

    def test_request_reset_user_password_link_user_incorrect(self):
        offset = url_for(controller='user',
                         action='request_reset')
        res = self.app.get(offset)
        fv = res.forms['user-password-reset']
        fv['user'] = 'unknown'
        res = fv.submit()
        main_res = self.main_div(res)
        assert 'No such user: unknown' in main_res, main_res # error

    def test_request_reset_user_password_using_search(self):
        CreateTestData.create_user(name='larry1', email='kittens@john.com')
        offset = url_for(controller='user',
                         action='request_reset')
        res = self.app.get(offset)
        fv = res.forms['user-password-reset']
        fv['user'] = 'kittens'
        res = fv.submit()
        assert_equal(res.status, 302)
        assert_equal(res.header_dict['Location'], 'http://localhost/')

        CreateTestData.create_user(name='larry2', fullname='kittens')
        res = self.app.get(offset)
        fv = res.forms['user-password-reset']
        fv['user'] = 'kittens'
        res = fv.submit()
        main_res = self.main_div(res)
        assert '"kittens" matched several users' in main_res, main_res
        assert 'larry1' not in main_res, main_res
        assert 'larry2' not in main_res, main_res

        res = self.app.get(offset)
        fv = res.forms['user-password-reset']
        fv['user'] = ''
        res = fv.submit()
        main_res = self.main_div(res)
        assert 'No such user:' in main_res, main_res

        res = self.app.get(offset)
        fv = res.forms['user-password-reset']
        fv['user'] = 'l'
        res = fv.submit()
        main_res = self.main_div(res)
        assert 'No such user:' in main_res, main_res

    def test_reset_user_password_link(self):
        # Set password
        CreateTestData.create_user(name='bob', email='bob@bob.net', password='test1')
        
        # Set password to something new
        model.User.by_name(u'bob').password = 'test2'
        model.repo.commit_and_remove()
        test2_encoded = model.User.by_name(u'bob').password
        assert test2_encoded != 'test2'
        assert model.User.by_name(u'bob').password == test2_encoded

        # Click link from reset password email
        create_reset_key(model.User.by_name(u'bob'))
        reset_password_link = get_reset_link(model.User.by_name(u'bob'))
        offset = reset_password_link.replace('http://test.ckan.net', '')
        print offset
        res = self.app.get(offset)

        # Reset password form
        fv = res.forms['user-reset']
        fv['password1'] = 'test1'
        fv['password2'] = 'test1'
        res = fv.submit('save', status=302)

        # Check a new password is stored
        assert model.User.by_name(u'bob').password != test2_encoded

    def test_perform_reset_user_password_link_key_incorrect(self):
        CreateTestData.create_user(name='jack', password='test1')
        # Make up a key - i.e. trying to hack this
        user = model.User.by_name(u'jack')
        offset = url_for(controller='user',
                         action='perform_reset',
                         id=user.id,
                         key='randomness') # i.e. incorrect
        res = self.app.get(offset, status=403) # error

    def test_perform_reset_user_password_link_user_incorrect(self):
        # Make up a key - i.e. trying to hack this
        user = model.User.by_name(u'jack')
        offset = url_for(controller='user',
                         action='perform_reset',
                         id='randomness',  # i.e. incorrect
                         key='randomness')
        res = self.app.get(offset, status=404)
