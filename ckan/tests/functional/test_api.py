from lib_api import *

class ApiTestCase(ApiControllerTestCase): 

    def test_get_api(self):
        # Check interface resource (without a slash).
        offset = self.offset('')
        res = self.app.get(offset, status=[200])
        self.assert_version_data(res)
        # Check interface resource (with a slash).
        # Todo: Stop this raising an error.
        #offset = self.offset('/')
        #res = self.app.get(offset, status=[200])
        #self.assert_version_data(res)

    def assert_version_data(self, res):
        data = self.data_from_res(res)
        assert 'version' in data, data
        expected_version = self.get_expected_api_version()
        self.assert_equal(data['version'], expected_version) 


# Tests for Version 1 of the API.
class TestApi1(Api1TestCase, ApiTestCase): pass
# Tests for Version 2 of the API.
class TestApi2(Api2TestCase, ApiTestCase): pass
# Tests for unversioned API.
class TestApiUnversioned(ApiUnversionedTestCase, ApiTestCase): pass


