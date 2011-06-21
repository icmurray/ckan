"""\
New auth system based around logic layer authorization

Used like this:

::

    from ckan.new_authz import is_authorized

    def logic_layer_function(...):
        if not is_authorized('package_create', data_dict, context):
            # Handle here
            return
        # Continue as normal
"""
from logging import getLogger
from ckan.plugins import implements, SingletonPlugin
from ckan.plugins import IAuthFunctions

log = getLogger(__name__)


def return_false(data_dict, context):
    return False

# XXX Bug in the plugin system, the plugin is loaded just becasue it is 
#     imported, without it being explicitly loaded in setup.py
#class DefaultAuthFunctions(SingletonPlugin):
class OverrideAuthFunctions():
    """
    Emit a log line when objects are inserted into the database
    """

    implements(IAuthFunctions, inherit=True)

    def get_auth_functions(self):
        raise Exception('not being runi at all')
        return {
            'package_create': return_false
        }

from ckan.plugins import PluginImplementations

# This is a private cache used by get_auth_function() and should never
# be accessed directly
_fetched_auth_functions = None

def is_authorized(logic_function_name, data_dict, context):
    auth_function = _get_auth_function(logic_function_name)
    return auth_function(data_dict, context)

def _get_auth_function(logic_function_name):
    if _fetched_auth_functions is not None:
        return _fetched_auth_functions[logic_function_name]
    # Otherwise look in all the plugins to resolve all possible
    global _fetched_auth_functions
    # First get the default ones in the ckan/logic/auth directory
    default_auth_functions = {}
    # Rather than writing them out in full will use __import__
    # to load anything from ckan.auth that looks like it might
    # be an authorisation function
    for auth_module_name in ['get', 'create', 'update']:
        module_path = 'ckan.logic.auth.'+auth_module_name
        module = __import__(module_path)
        for part in module_path.split('.')[1:]:
            module = getattr(module, part)
        for k, v in module.__dict__.items():
            if not k.startswith('_'):
                default_auth_functions[k] = v
    # Then overwrite them with any specific ones in the plugins:
    resolved_auth_function_plugins = {}
    _fetched_auth_functions = {}
    for plugin in PluginImplementations(IAuthFunctions):
        for name, auth_function in plugin.get_auth_functions().items():
            if name in resolved_auth_function_plugins:
                raise Exception(
                    'The auth function %r is already implemented in %r' % (
                        name,
                        resolved_auth_function_plugins[name]
                    )
                )
            else:
                log.debug('Auth function %r was inserted', plugin.name)
                resolved_auth_function_plugins[name] = plugin.name
                _fetched_auth_functions[name] = auth_function
    # Use the updated ones in preference to the originals.
    _fetched_auth_functions.update(default_auth_functions)
    return _fetched_auth_functions[logic_function_name]

