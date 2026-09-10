"""Native rendering/source-guard tests; no application startup or search."""
from pathlib import Path
import unittest
from jinja2 import Environment, FileSystemLoader
from searx.result_types import LegacyResult, MainResult
from apply_preview import patch


class PreviewRendering(unittest.TestCase):
    def test_scores_and_escape_in_native_macro(self):
        env = Environment(loader=FileSystemLoader('/usr/local/searxng/searx/templates'), autoescape=True)
        env.globals.update(get_pretty_url=lambda _: [], favicon_resolver='', _=lambda s:s)
        macro = env.get_template('simple/macros.html').module.result_header
        for kind in (LegacyResult, MainResult):
            result = kind(url='https://example.org/', title='Public fixture', score=1.05)
            rendered = str(macro(result, {}, lambda url:url))
            self.assertIn('data-ae-score="1.05"', rendered)
            self.assertIn('result-default', rendered)
            self.assertIn('<h3>', rendered)
        rendered = str(macro({'url':'https://example.org/', 'score':'" onmouseover="x', 'title':'fixture'}, {}, lambda url:url))
        self.assertNotIn('data-ae-score="" onmouseover=', rendered)

    def test_script_is_same_origin_and_deferred(self):
        source = Path('/usr/local/searxng/searx/templates/simple/results.html').read_text()
        self.assertEqual(source.count('<script src="/anonexplo-preview.js" defer></script>'),1)

    def test_guards_refuse_unknown_and_double_patch(self):
        for name in ('macros.html','results.html'):
            for source in ('unknown',Path('/usr/local/searxng/searx/templates/simple',name).read_text()):
                with self.assertRaises(ValueError):
                    patch(name,source)


if __name__ == '__main__':
    unittest.main()
