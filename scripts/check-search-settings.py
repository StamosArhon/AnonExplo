"""Run inside the pinned SearXNG venv; no upstream requests or secret output."""
from searx import settings
from searx.preferences import Preferences
from searx.favicons import proxy

assert settings['search']['autocomplete'] == ''
assert settings['search']['favicon_resolver'] == ''
assert settings['server']['image_proxy'] is True
assert settings['ui']['query_in_title'] is False
assert settings['preferences'].lock == {'autocomplete', 'favicon_resolver', 'image_proxy', 'query_in_title'}
assert settings['search']['suspended_times']['SearxEngineTooManyRequests'] > 0
assert settings['search']['suspended_times']['SearxEngineCaptcha'] > 0
engine_config = {e['name']: e for e in settings['engines']}
assert engine_config['bing']['disabled'] is False
assert engine_config['bing']['weight'] == 0.35, 'Preserve evaluated Bing ranking weight'
assert settings['search']['default_lang'] == 'auto', 'Do not impose a global language'

# Initialize only the local resolver catalogue, not the web app or engines.
proxy.init(proxy.FaviconProxyConfig())
prefs = Preferences(['simple'], ['general'], {}, [])
prefs.parse_dict({'autocomplete': 'google', 'favicon_resolver': 'google',
                  'image_proxy': '0', 'query_in_title': '1', 'language': 'el'})
assert prefs.get_value('autocomplete') == ''
assert prefs.get_value('favicon_resolver') == ''
assert prefs.get_value('image_proxy') is True
assert prefs.get_value('query_in_title') is False
assert prefs.get_value('language') == 'el', 'Language must remain user-selectable'
print('PASS: SearXNG privacy defaults, stale-preference locks, language choice, and provider cooldowns.')
