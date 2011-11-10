import json
from pprint import pprint
from nose.tools import assert_equal, assert_raises

from ckan.lib.create_test_data import CreateTestData
from ckan.lib.dictization.model_dictize import resource_dictize
import ckan.model as model
from ckan.tests import WsgiAppCase
from ckan.tests.functional.api import assert_dicts_equal_ignoring_ordering 
from ckan.logic import get_action, NotAuthorized

class TestAction(WsgiAppCase):

    STATUS_200_OK = 200
    STATUS_201_CREATED = 201
    STATUS_400_BAD_REQUEST = 400
    STATUS_403_ACCESS_DENIED = 403
    STATUS_404_NOT_FOUND = 404
    STATUS_409_CONFLICT = 409

    sysadmin_user = None
    
    normal_user = None

    @classmethod
    def setup_class(self):
        CreateTestData.create()
        self.sysadmin_user = model.User.get('testsysadmin')
        self.normal_user = model.User.get('annafan')

    @classmethod
    def teardown_class(self):
        model.repo.rebuild_db()

    def _add_basic_package(self, package_name=u'test_package', **kwargs):
        package = {
            'name': package_name,
            'title': u'A Novel By Tolstoy',
            'resources': [{
                'description': u'Full text.',
                'format': u'plain text',
                'url': u'http://www.annakarenina.com/download/'
            }]
        }
        package.update(kwargs)

        postparams = '%s=1' % json.dumps(package)
        res = self.app.post('/api/action/package_create', params=postparams,
                            extra_environ={'Authorization': 'tester'})
        return json.loads(res.body)['result']

    def test_01_package_list(self):
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/package_list', params=postparams)
        assert_dicts_equal_ignoring_ordering(
            json.loads(res.body),
            {"help": "Lists packages by name or id",
             "success": True,
             "result": ["annakarenina", "warandpeace"]})
        
    def test_02_package_autocomplete(self):
        postparams = '%s=1' % json.dumps({'q':'war'})
        res = self.app.post('/api/action/package_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success'] == True
        pprint(res_obj['result'][0]['name'])
        assert res_obj['result'][0]['name'] == 'warandpeace'

    def test_03_create_update_package(self):

        package = {
            'author': None,
            'author_email': None,
            'extras': [{'key': u'original media','value': u'"book"'}],
            'license_id': u'other-open',
            'maintainer': None,
            'maintainer_email': None,
            'name': u'annakareninanew',
            'notes': u'Some test now',
            'resources': [{'alt_url': u'alt123',
                           'description': u'Full text.',
                           'extras': {u'alt_url': u'alt123', u'size': u'123'},
                           'format': u'plain text',
                           'hash': u'abc123',
                           'position': 0,
                           'url': u'http://www.annakarenina.com/download/'},
                          {'alt_url': u'alt345',
                           'description': u'Index of the novel',
                           'extras': {u'alt_url': u'alt345', u'size': u'345'},
                           'format': u'json',
                           'hash': u'def456',
                           'position': 1,
                           'url': u'http://www.annakarenina.com/index.json'}],
            'tags': [{'name': u'russian'}, {'name': u'tolstoy'}],
            'title': u'A Novel By Tolstoy',
            'url': u'http://www.annakarenina.com',
            'version': u'0.7a'
        }

        wee = json.dumps(package)
        postparams = '%s=1' % json.dumps(package)
        res = self.app.post('/api/action/package_create', params=postparams,
                            extra_environ={'Authorization': 'tester'})
        package_created = json.loads(res.body)['result']
        print package_created
        package_created['name'] = 'moo'
        postparams = '%s=1' % json.dumps(package_created)
        res = self.app.post('/api/action/package_update', params=postparams,
                            extra_environ={'Authorization': 'tester'})

        package_updated = json.loads(res.body)['result']
        package_updated.pop('revision_id')
        package_updated.pop('revision_timestamp')
        package_created.pop('revision_id')
        package_created.pop('revision_timestamp')
        assert package_updated == package_created#, (pformat(json.loads(res.body)), pformat(package_created['result']))

    def test_18_create_package_not_authorized(self):

        package = {
            'extras': [{'key': u'original media','value': u'"book"'}],
            'license_id': u'other-open',
            'maintainer': None,
            'maintainer_email': None,
            'name': u'annakareninanew_not_authorized',
            'notes': u'Some test now',
            'tags': [{'name': u'russian'}, {'name': u'tolstoy'}],
            'title': u'A Novel By Tolstoy',
            'url': u'http://www.annakarenina.com',
        }

        wee = json.dumps(package)
        postparams = '%s=1' % json.dumps(package)
        res = self.app.post('/api/action/package_create', params=postparams,
                                     status=self.STATUS_403_ACCESS_DENIED)

    def test_04_user_list(self):
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/user_list', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Lists the current users'
        assert res_obj['success'] == True
        assert len(res_obj['result']) == 7
        assert res_obj['result'][0]['name'] == 'annafan'
        assert res_obj['result'][0]['about'] == 'I love reading Annakarenina. My site: <a href="http://anna.com">anna.com</a>'
        assert not 'apikey' in res_obj['result'][0]

    def test_05_user_show(self):
        # Anonymous request
        postparams = '%s=1' % json.dumps({'id':'annafan'})
        res = self.app.post('/api/action/user_show', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Shows user details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['name'] == 'annafan'
        assert result['about'] == 'I love reading Annakarenina. My site: <a href="http://anna.com">anna.com</a>'
        assert 'activity' in result
        assert 'created' in result
        assert 'display_name' in result
        assert 'number_administered_packages' in result
        assert 'number_of_edits' in result
        assert not 'apikey' in result
        assert not 'reset_key' in result

        # Same user can see his api key
        res = self.app.post('/api/action/user_show', params=postparams,
                            extra_environ={'Authorization': str(self.normal_user.apikey)})

        res_obj = json.loads(res.body)
        result = res_obj['result']
        assert result['name'] == 'annafan'
        assert 'apikey' in result
        assert 'reset_key' in result

        # Sysadmin user can see everyone's api key
        res = self.app.post('/api/action/user_show', params=postparams,
                            extra_environ={'Authorization': str(self.sysadmin_user.apikey)})

        res_obj = json.loads(res.body)
        result = res_obj['result']
        assert result['name'] == 'annafan'
        assert 'apikey' in result
        assert 'reset_key' in result

    def test_05_user_show_edits(self):
        postparams = '%s=1' % json.dumps({'id':'tester'})
        res = self.app.post('/api/action/user_show', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Shows user details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['name'] == 'tester'
        assert_equal(result['about'], None)
        assert result['number_of_edits'] >= 1
        edit = result['activity'][-1] # first edit chronologically
        assert_equal(edit['author'], 'tester')
        assert 'timestamp' in edit
        assert_equal(edit['state'], 'active')
        assert_equal(edit['approved_timestamp'], None)
        assert_equal(set(edit['groups']), set(('roger', 'david')))
        assert_equal(edit['state'], 'active')
        assert edit['message'].startswith('Creating test data.')
        assert_equal(set(edit['packages']), set(('warandpeace', 'annakarenina')))
        assert 'id' in edit

    def test_06_tag_list(self):
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/tag_list', params=postparams)
        assert_dicts_equal_ignoring_ordering(
            json.loads(res.body),
            {'help': 'Returns a list of tags',
             'success': True,
             'result': ['russian', 'tolstoy', u'Flexible \u0489!']})
        #Get all fields
        postparams = '%s=1' % json.dumps({'all_fields':True})
        res = self.app.post('/api/action/tag_list', params=postparams)
        res_obj = json.loads(res.body)
        pprint(res_obj)
        assert res_obj['success'] == True

        names = [ res_obj['result'][i]['name'] for i in xrange(len(res_obj['result'])) ]
        russian_index = names.index('russian')
        tolstoy_index = names.index('tolstoy')
        flexible_index = names.index(u'Flexible \u0489!')

        assert res_obj['result'][russian_index]['name'] == 'russian'
        assert res_obj['result'][tolstoy_index]['name'] == 'tolstoy'

        number_of_russian_packages = len(res_obj['result'][russian_index]['packages'])
        number_of_tolstoy_packages = len(res_obj['result'][tolstoy_index]['packages'])
        number_of_flexible_packages = len(res_obj['result'][flexible_index]['packages'])
        
        # TODO : This "moo" package appears to have leaked in from other tests.
        #        Is that meant to be the case? IM
        assert number_of_russian_packages == 3, \
               'Expected 2 packages tagged with "russian"' # warandpeace , annakarenina , moo
        assert number_of_tolstoy_packages == 2, \
               'Expected 2 packages tagged with "tolstoy"' # moo , annakarenina
        assert number_of_flexible_packages == 2, \
               u'Expected 2 packages tagged with "Flexible \u0489!"' # warandpeace , annakarenina

        assert 'id' in res_obj['result'][0]
        assert 'id' in res_obj['result'][1]
        assert 'id' in res_obj['result'][2]

    def test_07_tag_show(self):
        postparams = '%s=1' % json.dumps({'id':'russian'})
        res = self.app.post('/api/action/tag_show', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Shows tag details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['name'] == 'russian'
        assert 'id' in result
        assert 'packages' in result and len(result['packages']) == 3
        assert [package['name'] for package in result['packages']].sort() == ['annakarenina', 'warandpeace', 'moo'].sort()

    def test_07_flexible_tag_show(self):
        """
        Asserts that the api can be used to retrieve the details of the flexible tag.

        The flexible tag is the tag with spaces, punctuation and foreign
        characters in its name, that's created in `ckan/lib/create_test_data.py`.
        """
        postparams = '%s=1' % json.dumps({'id':u'Flexible \u0489!'})
        res = self.app.post('/api/action/tag_show', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Shows tag details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['name'] == u'Flexible \u0489!'
        assert 'id' in result
        assert 'packages' in result and len(result['packages']) == 2
        assert [package['name'] for package in result['packages']].sort() == ['annakarenina', 'warandpeace'].sort()

    def test_07_tag_show_unknown_license(self):
        # create a tagged package which has an invalid license
        CreateTestData.create_arbitrary([{
            'name': u'tag_test',
            'tags': u'tolstoy',
            'license': 'never_heard_of_it',
            }])
        postparams = '%s=1' % json.dumps({'id':'tolstoy'})
        res = self.app.post('/api/action/tag_show', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success'] == True
        result = res_obj['result']
        for pkg in result['packages']:
            if pkg['name'] == 'tag_test':
                break
        else:
            assert 0, 'tag_test not among packages'
        assert_equal(pkg['license_id'], 'never_heard_of_it')
        assert_equal(pkg['isopen'], False)

    def test_08_user_create_not_authorized(self):
        postparams = '%s=1' % json.dumps({'name':'test_create_from_action_api', 'password':'testpass'})
        res = self.app.post('/api/action/user_create', params=postparams,
                            status=self.STATUS_403_ACCESS_DENIED)
        res_obj = json.loads(res.body)
        assert res_obj == {'help': 'Creates a new user',
                           'success': False,
                           'error': {'message': 'Access denied', '__type': 'Authorization Error'}}

    def test_09_user_create(self):
        user_dict = {'name':'test_create_from_action_api',
                      'about': 'Just a test user',
                      'email': 'me@test.org',
                      'password':'testpass'}

        postparams = '%s=1' % json.dumps(user_dict)
        res = self.app.post('/api/action/user_create', params=postparams,
                            extra_environ={'Authorization': str(self.sysadmin_user.apikey)})
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Creates a new user'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['name'] == user_dict['name']
        assert result['about'] == user_dict['about']
        assert 'apikey' in result
        assert 'created' in result
        assert 'display_name' in result
        assert 'number_administered_packages' in result
        assert 'number_of_edits' in result
        assert not 'password' in result

    def test_10_user_create_parameters_missing(self):
        user_dict = {}

        postparams = '%s=1' % json.dumps(user_dict)
        res = self.app.post('/api/action/user_create', params=postparams,
                            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
                            status=self.STATUS_409_CONFLICT)
        res_obj = json.loads(res.body)
        assert res_obj == {
            'error': {
                '__type': 'Validation Error',
                'name': ['Missing value'],
                'email': ['Missing value'],
                'password': ['Missing value']
            },
            'help': 'Creates a new user',
            'success': False
        }

    def test_11_user_create_wrong_password(self):
        user_dict = {'name':'test_create_from_action_api_2',
                'email':'me@test.org',
                      'password':'tes'} #Too short

        postparams = '%s=1' % json.dumps(user_dict)
        res = self.app.post('/api/action/user_create', params=postparams,
                            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
                            status=self.STATUS_409_CONFLICT)

        res_obj = json.loads(res.body)
        assert res_obj == {
            'error': {
                '__type': 'Validation Error',
                'password': ['Your password must be 4 characters or longer']
            },
            'help': 'Creates a new user',
            'success': False
        }

    def test_12_user_update(self):
        normal_user_dict = {'id': self.normal_user.id,
                            'fullname': 'Updated normal user full name',
                            'email': 'me@test.org',
                            'about':'Updated normal user about'}

        sysadmin_user_dict = {'id': self.sysadmin_user.id,
                            'fullname': 'Updated sysadmin user full name',
                            'email': 'me@test.org',
                            'about':'Updated sysadmin user about'} 

        #Normal users can update themselves
        postparams = '%s=1' % json.dumps(normal_user_dict)
        res = self.app.post('/api/action/user_update', params=postparams,
                            extra_environ={'Authorization': str(self.normal_user.apikey)})

        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Updates the user\'s details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['id'] == self.normal_user.id
        assert result['name'] == self.normal_user.name
        assert result['fullname'] == normal_user_dict['fullname']
        assert result['about'] == normal_user_dict['about']
        assert 'apikey' in result
        assert 'created' in result
        assert 'display_name' in result
        assert 'number_administered_packages' in result
        assert 'number_of_edits' in result
        assert not 'password' in result

        #Sysadmin users can update themselves
        postparams = '%s=1' % json.dumps(sysadmin_user_dict)
        res = self.app.post('/api/action/user_update', params=postparams,
                            extra_environ={'Authorization': str(self.sysadmin_user.apikey)})

        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Updates the user\'s details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['id'] == self.sysadmin_user.id
        assert result['name'] == self.sysadmin_user.name
        assert result['fullname'] == sysadmin_user_dict['fullname']
        assert result['about'] == sysadmin_user_dict['about']

        #Sysadmin users can update all users
        postparams = '%s=1' % json.dumps(normal_user_dict)
        res = self.app.post('/api/action/user_update', params=postparams,
                            extra_environ={'Authorization': str(self.sysadmin_user.apikey)})

        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Updates the user\'s details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['id'] == self.normal_user.id
        assert result['name'] == self.normal_user.name
        assert result['fullname'] == normal_user_dict['fullname']
        assert result['about'] == normal_user_dict['about']

        #Normal users can not update other users
        postparams = '%s=1' % json.dumps(sysadmin_user_dict)
        res = self.app.post('/api/action/user_update', params=postparams,
                            extra_environ={'Authorization': str(self.normal_user.apikey)},
                            status=self.STATUS_403_ACCESS_DENIED)

        res_obj = json.loads(res.body)
        assert res_obj == {
            'error': {
                '__type': 'Authorization Error',
                'message': 'Access denied'
            },
            'help': 'Updates the user\'s details',
            'success': False
        }

    def test_13_group_list(self):
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/group_list', params=postparams)
        res_obj = json.loads(res.body)
        assert_dicts_equal_ignoring_ordering(
            res_obj,
            {
                'result': [
                    'david',
                    'roger'
                    ],
                'help': 'Returns a list of groups',
                'success': True
            })
        
        #Get all fields
        postparams = '%s=1' % json.dumps({'all_fields':True})
        res = self.app.post('/api/action/group_list', params=postparams)
        res_obj = json.loads(res.body)

        assert res_obj['success'] == True
        assert res_obj['result'][0]['name'] == 'david'
        assert res_obj['result'][0]['display_name'] == 'Dave\'s books'
        assert res_obj['result'][0]['packages'] == 2
        assert res_obj['result'][1]['name'] == 'roger'
        assert res_obj['result'][1]['packages'] == 1
        assert 'id' in res_obj['result'][0]
        assert 'revision_id' in res_obj['result'][0]
        assert 'state' in res_obj['result'][0]

    def test_14_group_show(self):
        postparams = '%s=1' % json.dumps({'id':'david'})
        res = self.app.post('/api/action/group_show', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['help'] == 'Shows group details'
        assert res_obj['success'] == True
        result = res_obj['result']
        assert result['name'] == 'david'
        assert result['title'] == result['display_name'] == 'Dave\'s books'
        assert result['state'] == 'active'
        assert 'id' in result
        assert 'revision_id' in result
        assert len(result['packages']) == 2

        #Group not found
        postparams = '%s=1' % json.dumps({'id':'not_present_in_the_db'})
        res = self.app.post('/api/action/group_show', params=postparams,
                            status=self.STATUS_404_NOT_FOUND)

        res_obj = json.loads(res.body)
        pprint(res_obj)
        assert res_obj == {
            'error': {
                '__type': 'Not Found Error',
                'message': 'Not found'
            },
            'help': 'Shows group details',
            'success': False
        }

    def test_15_tag_autocomplete(self):
        #Empty query
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj == {
            'help': 'Returns tags containing the provided string', 
            'result': [], 
            'success': True
        }

        #Normal query
        postparams = '%s=1' % json.dumps({'q':'r'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj == {
            'help': 'Returns tags containing the provided string', 
            'result': ['russian'], 
            'success': True
        }

    def test_15_tag_autocomplete_tag_with_spaces(self):
        """Asserts autocomplete finds tags that contain spaces"""

        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-space-1',
            'tags': [u'with space'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':'w'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert 'with space' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_tag_with_foreign_characters(self):
        """Asserts autocomplete finds tags that contain foreign characters"""
        
        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-foreign-character-1',
            'tags': [u'greek beta \u03b2'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':'greek'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert u'greek beta \u03b2' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_tag_with_punctuation(self):
        """Asserts autocomplete finds tags that contain punctuation"""
        
        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-fullstop-1',
            'tags': [u'fullstop.'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':'fullstop'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert u'fullstop.' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_tag_with_capital_letters(self):
        """
        Asserts autocomplete finds tags that contain capital letters
        
        Note : the only reason this test passes for now is that the
               search is for a lower cases substring.  If we had searched
               for "CAPITAL" then it would fail.  This is because currently
               the search API lower cases all search terms.  There's a
               sister test (`test_15_tag_autocomplete_search_with_capital_letters`)
               that tests that functionality.
        """
        
        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-capital-letter-1',
            'tags': [u'CAPITAL idea old chap'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':'idea'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert u'CAPITAL idea old chap' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_search_with_space(self):
        """
        Asserts that a search term containing a space works correctly
        """

        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-space-2',
            'tags': [u'with space'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':'th sp'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert 'with space' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_search_with_foreign_character(self):
        """
        Asserts that a search term containing a foreign character works correctly
        """

        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-foreign-character-2',
            'tags': [u'greek beta \u03b2'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':u'\u03b2'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert u'greek beta \u03b2' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_search_with_punctuation(self):
        """
        Asserts that a search term containing punctuation works correctly
        """

        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-fullstop-2',
            'tags': [u'fullstop.'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':u'stop.'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert 'fullstop.' in res_obj['result'], res_obj['result']

    def test_15_tag_autocomplete_search_with_capital_letters(self):
        """
        Asserts that a search term containing capital letters works correctly

        NOTE - this test FAILS.  This is because I haven't implemented the
               search side of flexible tags yet.

        NOTE - when this test is fixed, remove the NOTE in
               `test_15_tag_autocomplete_tag_with_capital_letters` that
               references this one.
        """

        CreateTestData.create_arbitrary([{
            'name': u'package-with-tag-that-has-a-capital-letter-2',
            'tags': [u'CAPITAL idea old chap'],
            'license': 'never_heard_of_it',
            }])

        postparams = '%s=1' % json.dumps({'q':u'CAPITAL'})
        res = self.app.post('/api/action/tag_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['success']
        assert 'CAPITAL idea old chap' in res_obj['result'], res_obj['result']

    def test_16_user_autocomplete(self):
        #Empty query
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/user_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj == {
            'help': 'Returns users containing the provided string', 
            'result': [], 
            'success': True
        }

        #Normal query
        postparams = '%s=1' % json.dumps({'q':'joe'})
        res = self.app.post('/api/action/user_autocomplete', params=postparams)
        res_obj = json.loads(res.body)
        assert res_obj['result'][0]['name'] == 'joeadmin'
        assert 'id','fullname' in res_obj['result'][0]

    def test_17_bad_action(self):
        #Empty query
        postparams = '%s=1' % json.dumps({})
        res = self.app.post('/api/action/bad_action_name', params=postparams,
                            status=400)
        res_obj = json.loads(res.body)
        assert_equal(res_obj, u'Bad request - Action name not known: bad_action_name')

    def test_19_update_resource(self):
        package = {
            'name': u'annakareninanew',
            'resources': [{
                'alt_url': u'alt123',
                'description': u'Full text.',
                'extras': {u'alt_url': u'alt123', u'size': u'123'},
                'format': u'plain text',
                'hash': u'abc123',
                'position': 0,
                'url': u'http://www.annakarenina.com/download/'
            }],
            'title': u'A Novel By Tolstoy',
            'url': u'http://www.annakarenina.com',
        }

        postparams = '%s=1' % json.dumps(package)
        res = self.app.post('/api/action/package_create', params=postparams,
                            extra_environ={'Authorization': 'tester'})
        package_created = json.loads(res.body)['result']

        resource_created = package_created['resources'][0]
        new_resource_url = u'http://www.annakareinanew.com/download/' 
        resource_created['url'] = new_resource_url
        postparams = '%s=1' % json.dumps(resource_created)
        res = self.app.post('/api/action/resource_update', params=postparams,
                            extra_environ={'Authorization': 'tester'})
        
        resource_updated = json.loads(res.body)['result']
        assert resource_updated['url'] == new_resource_url, resource_updated

        resource_updated.pop('url')
        resource_updated.pop('revision_id')
        resource_created.pop('url')
        resource_created.pop('revision_id')
        resource_created.pop('revision_timestamp')
        assert resource_updated == resource_created

    def test_20_task_status_update(self):
        package_created = self._add_basic_package(u'test_task_status_update')

        task_status = {
            'entity_id': package_created['id'],
            'entity_type': u'package',
            'task_type': u'test_task',
            'key': u'test_key',
            'value': u'test_value',
            'state': u'test_state'
        }
        postparams = '%s=1' % json.dumps(task_status)
        res = self.app.post(
            '/api/action/task_status_update', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_status_updated = json.loads(res.body)['result']
        task_status_id = task_status_updated.pop('id')
        task_status_updated.pop('last_updated')
        assert task_status_updated == task_status, (task_status_updated, task_status)

        task_status_updated['id'] = task_status_id
        task_status_updated['value'] = u'test_value_2'
        postparams = '%s=1' % json.dumps(task_status_updated)
        res = self.app.post(
            '/api/action/task_status_update', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_status_updated_2 = json.loads(res.body)['result']
        task_status_updated_2.pop('last_updated')
        assert task_status_updated_2 == task_status_updated, task_status_updated_2

    def test_21_task_status_update_many(self):
        package_created = self._add_basic_package(u'test_task_status_update_many')
        task_statuses = {
            'data': [
                {
                    'entity_id': package_created['id'],
                    'entity_type': u'package',
                    'task_type': u'test_task',
                    'key': u'test_task_1',
                    'value': u'test_value_1',
                    'state': u'test_state'
                },
                {
                    'entity_id': package_created['id'],
                    'entity_type': u'package',
                    'task_type': u'test_task',
                    'key': u'test_task_2',
                    'value': u'test_value_2',
                    'state': u'test_state'
                }
            ]
        }
        postparams = '%s=1' % json.dumps(task_statuses)
        res = self.app.post(
            '/api/action/task_status_update_many', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_statuses_updated = json.loads(res.body)['result']['results']
        for i in range(len(task_statuses['data'])):
            task_status = task_statuses['data'][i]
            task_status_updated = task_statuses_updated[i]
            task_status_updated.pop('id') 
            task_status_updated.pop('last_updated') 
            assert task_status == task_status_updated, (task_status_updated, task_status, i)

    def test_22_task_status_normal_user_not_authorized(self):
        task_status = {} 
        postparams = '%s=1' % json.dumps(task_status)
        res = self.app.post(
            '/api/action/task_status_update', params=postparams,
            extra_environ={'Authorization': str(self.normal_user.apikey)},
            status=self.STATUS_403_ACCESS_DENIED
        )
        res_obj = json.loads(res.body)
        expected_res_obj = {
            'help': None,
            'success': False,
            'error': {'message': 'Access denied', '__type': 'Authorization Error'}
        }
        assert res_obj == expected_res_obj, res_obj

    def test_23_task_status_validation(self):
        task_status = {} 
        postparams = '%s=1' % json.dumps(task_status)
        res = self.app.post(
            '/api/action/task_status_update', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
            status=self.STATUS_409_CONFLICT
        )

    def test_24_task_status_show(self):
        package_created = self._add_basic_package(u'test_task_status_show')

        task_status = {
            'entity_id': package_created['id'],
            'entity_type': u'package',
            'task_type': u'test_task',
            'key': u'test_task_status_show',
            'value': u'test_value',
            'state': u'test_state'
        }
        postparams = '%s=1' % json.dumps(task_status)
        res = self.app.post(
            '/api/action/task_status_update', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_status_updated = json.loads(res.body)['result']

        postparams = '%s=1' % json.dumps({'id': task_status_updated['id']})
        res = self.app.post(
            '/api/action/task_status_show', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_status_show = json.loads(res.body)['result']

        task_status_show.pop('last_updated')
        task_status_updated.pop('last_updated')
        assert task_status_show == task_status_updated, (task_status_show, task_status_updated)

    def test_25_task_status_delete(self):
        package_created = self._add_basic_package(u'test_task_status_delete')

        task_status = {
            'entity_id': package_created['id'],
            'entity_type': u'package',
            'task_type': u'test_task',
            'key': u'test_task_status_delete',
            'value': u'test_value',
            'state': u'test_state'
        }
        postparams = '%s=1' % json.dumps(task_status)
        res = self.app.post(
            '/api/action/task_status_update', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_status_updated = json.loads(res.body)['result']

        postparams = '%s=1' % json.dumps({'id': task_status_updated['id']})
        res = self.app.post(
            '/api/action/task_status_delete', params=postparams,
            extra_environ={'Authorization': str(self.sysadmin_user.apikey)},
        )
        task_status_delete = json.loads(res.body)
        assert task_status_delete['success'] == True

    def test_26_resource_show(self):
        pkg = model.Package.get('annakarenina')
        resource = pkg.resources[0]
        postparams = '%s=1' % json.dumps({'id': resource.id})
        res = self.app.post('/api/action/resource_show', params=postparams)
        result = json.loads(res.body)['result']
        resource_dict = resource_dictize(resource, {'model': model})
        result.pop('revision_timestamp')
        assert result == resource_dict, (result, resource_dict)

    
    def test_27_get_site_user_not_authorized(self):
        assert_raises(NotAuthorized,
                     get_action('get_site_user'),
                     {'model': model}, {})
        user = model.User.get('test.ckan.net')
        assert not user

        user=get_action('get_site_user')({'model': model, 'ignore_auth': True}, {})
        assert user['name'] == 'test.ckan.net'

        user = model.User.get('test.ckan.net')
        assert user

        user=get_action('get_site_user')({'model': model, 'ignore_auth': True}, {})
        assert user['name'] == 'test.ckan.net'
        
        user = model.Session.query(model.User).filter_by(name='test.ckan.net').one()
        assert user








