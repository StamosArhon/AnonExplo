"""Deterministic native merge/render regression tests; no engines or HTTP calls."""
from datetime import date, datetime, timedelta, timezone
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jinja2 import Environment, FileSystemLoader
from searx.engines import engines
from searx.result_types import LegacyResult, MainResult
from searx.results import ResultContainer, merge_two_main_results
from apply_date_merge import REPAIR, patched_source, patched_template

TYPES = (LegacyResult, MainResult)
DATE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def result(kind, engine, published=None, **extra):
    return kind(url='https://example.invalid/item', title='Synthetic', content='',
                engine=engine, engines={engine}, publishedDate=published, **extra)


class DateMergeTests(unittest.TestCase):
    def test_missing_date_all_type_pairs(self):
        for left in TYPES:
            for right in TYPES:
                with self.subTest(left=left.__name__, right=right.__name__):
                    origin, other = result(left, 'a'), result(right, 'b', DATE)
                    merge_two_main_results(origin, other)
                    self.assertIs(origin.publishedDate, DATE)
                    self.assertEqual(origin.as_dict()['pubdate'], '2026-01-02 03:04:05+0000')
                    self.assertEqual(origin.engines, {'a', 'b'})

    def test_existing_date_and_display_preserved(self):
        for left in TYPES:
            for right in TYPES:
                for incoming in (None, DATE, DATE + timedelta(days=1)):
                    with self.subTest(left=left.__name__, right=right.__name__, incoming=incoming):
                        origin = result(left, 'a', DATE, pubdate='existing display')
                        merge_two_main_results(origin, result(right, 'b', incoming))
                        self.assertIs(origin.publishedDate, DATE)
                        self.assertEqual(origin.as_dict()['pubdate'], 'existing display')

    def test_never_invents_or_parses_incoming_dates(self):
        # Native adapters must normalize valid datetimes before deduplication.
        # This repair is not a parser or an override of malformed origin data.
        for left in TYPES:
            for right in TYPES:
                for invalid in (None, '', '2026-01-02', 0, 123, date(2026, 1, 2)):
                    with self.subTest(left=left.__name__, right=right.__name__, invalid=invalid):
                        origin = result(left, 'a')
                        merge_two_main_results(origin, result(right, 'b', invalid))
                        self.assertIsNone(origin.publishedDate)

    def test_naive_and_offset_dates_preserved_without_timezone_inference(self):
        for stamp in (DATE.replace(tzinfo=None), DATE.astimezone(timezone(timedelta(hours=3)))):
            origin = result(LegacyResult, 'a')
            merge_two_main_results(origin, result(MainResult, 'b', stamp, pubdate='stale'))
            self.assertIs(origin.publishedDate, stamp)
            self.assertEqual(origin.as_dict()['pubdate'], stamp.strftime('%Y-%m-%d %H:%M:%S%z'))

    def test_incoming_result_not_modified(self):
        other = result(MainResult, 'b', DATE, pubdate='incoming')
        before = other.as_dict().copy()
        merge_two_main_results(result(LegacyResult, 'a'), other)
        self.assertEqual(other.as_dict(), before)

    def test_repeated_merge_retains_first_available_date(self):
        origin = result(LegacyResult, 'a')
        merge_two_main_results(origin, result(MainResult, 'b', DATE))
        merge_two_main_results(origin, result(LegacyResult, 'c', DATE + timedelta(days=5)))
        self.assertIs(origin.publishedDate, DATE)
        self.assertEqual(origin.engines, {'a', 'b', 'c'})

    def test_native_pipeline_and_ranking_unchanged_except_dates(self):
        # Compare against the exact original merge function in memory. No
        # production mutation and no heuristic reconstruction of ranking.
        source = inspect.getsource(merge_two_main_results)
        self.assertEqual(source.count(REPAIR), 1)
        namespace = dict(merge_two_main_results.__globals__)
        exec(source.replace(REPAIR, '', 1), namespace)
        baseline = namespace['merge_two_main_results']

        def run(left, right, reverse, merge):
            container = ResultContainer()
            rows = [('probe-a', result(left, 'probe-a')),
                    ('probe-b', result(right, 'probe-b', DATE))]
            if reverse:
                rows.reverse()
            with patch.dict(engines, {name: SimpleNamespace(name=name, weight=1, categories=['news'], paging=False)
                                     for name in ('probe-a', 'probe-b')}), \
                 patch('searx.results.histogram_observe'), patch('searx.results.counter_add'), \
                 patch('searx.results.merge_two_main_results', merge):
                for name, row in rows:
                    container.extend(name, [row, MainResult(url=f'https://example.invalid/{name}', title='Other')])
                return [row.as_dict().copy() for row in container.get_ordered_results()]

        for left in TYPES:
            for right in TYPES:
                for reverse in (False, True):
                    with self.subTest(left=left.__name__, right=right.__name__, reverse=reverse):
                        original = run(left, right, reverse, baseline)
                        repaired = run(left, right, reverse, merge_two_main_results)
                        self.assertEqual(len(repaired), 3)
                        merged = next(r for r in repaired if r['url'].endswith('/item'))
                        self.assertEqual(merged['publishedDate'], DATE)
                        self.assertEqual(merged['engines'], {'probe-a', 'probe-b'})
                        self.assertEqual(merged['positions'], [1, 1])
                        strip_dates = lambda rows: [{k: v for k, v in r.items() if k not in ('publishedDate', 'pubdate')}
                                                   for r in rows]
                        self.assertEqual(strip_dates(repaired), strip_dates(original))

    def test_native_template_date_markup(self):
        # Render the real date macro, without app/engine initialization.
        env = Environment(loader=FileSystemLoader('/usr/local/searxng/searx/templates'), autoescape=True)
        macro = env.get_template('simple/macros.html').module.result_sub_header
        for kind in TYPES:
            origin = result(kind, 'a')
            self.assertNotIn('<time', str(macro(origin)))
            merge_two_main_results(origin, result(MainResult, 'b', DATE))
            markup = str(macro(origin))
            self.assertIn('datetime="2026-01-02 03:04:05+0000"', markup)
            self.assertIn('class="published_date"', markup)
            self.assertIs(origin.as_dict()['publishedDate'], DATE)

    def test_native_template_existing_legacy_date_markup(self):
        env = Environment(loader=FileSystemLoader('/usr/local/searxng/searx/templates'), autoescape=True)
        origin = result(LegacyResult, 'a', DATE)
        origin.normalize_result_fields()
        markup = str(env.get_template('simple/macros.html').module.result_sub_header(origin))
        self.assertIn('datetime="2026-01-02 03:04:05+0000"', markup)

    def test_native_json_retains_date_and_engine_attribution(self):
        from searx.webutils import get_json_response
        for kind in TYPES:
            origin = result(kind, 'a')
            merge_two_main_results(origin, result(MainResult, 'b', DATE))
            container = ResultContainer()
            container._closed = True
            container._main_results_sorted = [origin]
            payload = json.loads(get_json_response(SimpleNamespace(query='synthetic'), container))
            row = payload['results'][0]
            self.assertEqual(row['publishedDate'], DATE.isoformat())
            self.assertEqual(row['pubdate'], '2026-01-02 03:04:05+0000')
            self.assertEqual(set(row['engines']), {'a', 'b'})

    def test_template_guard_rejects_unknown_and_double_patch(self):
        from pathlib import Path
        for source in (b'unknown', Path('/usr/local/searxng/searx/templates/simple/macros.html').read_bytes()):
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                patched_template(source)

    def test_source_guard_rejects_unknown_source(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            patched_source(b'not the pinned source')

    def test_source_guard_rejects_double_patch(self):
        import searx.results
        from pathlib import Path
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            patched_source(Path(searx.results.__file__).read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
