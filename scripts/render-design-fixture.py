"""Render the installed native templates using authored, non-fetched content."""
from types import SimpleNamespace
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('/usr/local/searxng/searx/templates'), autoescape=True)

def url_for(endpoint, **kw):
    if endpoint == 'static': return '/static/' + kw['filename']
    return '/' + endpoint

env.globals.update(_=lambda s:s, url_for=url_for, favicon_resolver='',
    get_setting=lambda key: {} if key=='brand.custom.links' else False,
    get_pretty_url=lambda u:[u.hostname, u.path], image_proxify=lambda url:url,
    get_result_template=lambda theme, name:'simple/result_templates/' + (name or 'default.html'))
rows=[]
for i, (title, content) in enumerate([
    ('How public-interest reporting crosses borders', 'An authored design fixture about collaborative reporting, shared evidence and the questions that connect communities. This is not a retrieved article.'),
    ('Independent journalism: methods, evidence and accountability', 'A longer English snippet tests line length and spacing. The reading experience should stay calm even when a result title wraps onto two lines.'),
    ('Διασυνοριακή δημοσιογραφία: έρευνα, τεκμηρίωση και δημόσιο συμφέρον', 'Συνθετικό κείμενο για τον έλεγχο της ελληνικής τυπογραφίας. Οι πηγές, τα στοιχεία και η μεθοδολογία χρειάζονται καθαρή και ευανάγνωστη παρουσίαση.'),
    ('What makes a source relevant to your question?', 'Relevance depends on the subject and the evidence, not merely on whether the website is a preferred source.'),
    ('An investigation without a supplied description', ''),
    ('A practical guide to collaborative research', 'A final authored entry checks the rhythm of a longer results page and the separation between the results and secondary diagnostics.')]):
    url=f'https://example.net/research/{i}'
    rows.append(dict(url=url, parsed_url=urlparse(url), title=title, content=content,
        score=1, template='default.html', category='general', engines=['brave','bing']))
html=env.get_template('simple/results.html').render(
    preferences=SimpleNamespace(get_value=lambda key: 'dark' if key=='simple_style' else False),
    request=SimpleNamespace(args={}), endpoint='results', locale_rfc5646='en-US',
    theme='simple', instance_name='AnonExplo · authored layout fixture',
    q='cross-border public-interest reporting', method='GET', selected_categories=['general'],
    categories=['general','news','science'], search_on_category_select=True,
    current_language='auto', search_language='en-US', sxng_locales=[('el','Ελληνικά','','Greek','')],
    time_range='', safesearch=0, results=rows, favicons={}, pageno=1, paging=False,
    max_response_time=1.4, timings=[('brave',.8),('bing',.5)], unresponsive_engines=[],
    suggestions=['collaborative reporting'], search_formats=['json','csv'],
    client_settings='', cache_url='', enable_metrics=False)
# Fixture never loads the core network-capable behavior; native markup/CSS are real.
html=html.replace('<script type="module"', '<script type="application/x-disabled"')
print(html)
