'''For unit testing that does not use paste fixture web requests, but needs
pylons set up for access to c, g or the template engine.

Based on answer at:
http://groups.google.com/group/pylons-discuss/browse_thread/thread/5f8d8f59fd459a77
'''

from unittest import TestCase 
from paste.registry import Registry 
import pylons 
from pylons.util import AttribSafeContextObj
import ckan.lib.app_globals as app_globals
from pylons.controllers.util import Request, Response 
from routes.util import URLGenerator

from ckan.config.routing import make_map
from ckan.tests import *
from ckan.lib.cli import MockTranslator

class TestSession(dict):
    def save(self):
        pass

class PylonsTestCase(object):
    """A basic test case which allows access to pylons.c and pylons.request. 
    """
    @classmethod
    def setup_class(cls):
        cls.registry=Registry() 
        cls.registry.prepare() 

        cls.context_obj=AttribSafeContextObj()
        cls.registry.register(pylons.c, cls.context_obj)

        cls.app_globals_obj = app_globals.Globals()
        cls.registry.register(pylons.g, cls.app_globals_obj)

        cls.request_obj=Request(dict(HTTP_HOST="nohost")) 
        cls.registry.register(pylons.request, cls.request_obj) 

        cls.translator_obj=MockTranslator() 
        cls.registry.register(pylons.translator, cls.translator_obj) 

        cls.buffet = pylons.templating.Buffet('genshi', template_root='ckan.templates')
        cls.registry.register(pylons.buffet, cls.buffet)

        cls.registry.register(pylons.response, Response())
        mapper = make_map()
        cls.registry.register(pylons.url, URLGenerator(mapper, {}))
        cls.registry.register(pylons.session, TestSession())
