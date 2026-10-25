#!/usr/bin/env python3
"""GC22: real reconciliation shape + legacy shape, fail-closed checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import yaml

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/graphic_design_lab/greeting_cards/gc22_template_reference_v0_3.py'
SCHEME = 'coordination/graphic_design_lab/directions/greeting_cards/goal_driven_v0_1/02_PRODUCT/greeting_card_skeleton_v0_1.yaml'

spec = importlib.util.spec_from_file_location('gc22_schema_fix', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GC22TemplateTests(unittest.TestCase):
    def candidate(self, geometry, top=None):
        row = {'id':'P04.GREETING_BODY','geometry':geometry}
        if top is not None:
            row['target_bbox_pdf_mm']=top
        return {'elements':[row]}

    def test_real_top_level_with_descriptive_geometry(self):
        c = self.candidate('GC16_CANDIDATE_AND_GC18_A2_VISUAL_TARGET', [32.,32.,182.,212.])
        self.assertEqual(mod.p04_candidate_greeting_bbox(c),[32.,32.,182.,212.])

    def test_legacy_nested_geometry(self):
        c=self.candidate({'target_bbox_pdf_mm':[32.,32.,182.,212.]})
        self.assertEqual(mod.p04_candidate_greeting_bbox(c),[32.,32.,182.,212.])

    def test_both_identical_accepted(self):
        c=self.candidate({'target_bbox_pdf_mm':[32,32,182,212]},[32.,32.,182.,212.])
        self.assertEqual(mod.p04_candidate_greeting_bbox(c),[32.,32.,182.,212.])

    def test_both_conflicting_blocked(self):
        c=self.candidate({'target_bbox_pdf_mm':[27,32,187,212]},[32,32,182,212])
        with self.assertRaisesRegex(mod.Blocked,'P04_CANDIDATE_DUPLICATE_BBOX_CONFLICT'):
            mod.p04_candidate_greeting_bbox(c)

    def test_missing_bbox_blocked(self):
        with self.assertRaisesRegex(mod.Blocked,'P04_CANDIDATE_BBOX_INVALID'):
            mod.p04_candidate_greeting_bbox(self.candidate('NOT_SET'))

    def test_duplicate_greeting_elements_blocked(self):
        c=self.candidate('TEXT', [32,32,182,212]); c['elements'].append(dict(c['elements'][0]))
        with self.assertRaisesRegex(mod.Blocked,'P04_GREETING_BODY_NOT_UNIQUE'):
            mod.p04_candidate_greeting_bbox(c)

    def test_bad_types_rejected(self):
        for bbox in ([32,32,182,'212'], [True,32,182,212], [32,32,182], [32,32,32,212]):
            with self.subTest(bbox=bbox):
                with self.assertRaises(mod.Blocked):
                    mod.p04_candidate_greeting_bbox(self.candidate('REAL_SCHEMA',bbox))

    def test_current_source_integration_with_real_schema(self):
        """Run actual load_inputs against SOURCE_FIXTURE_ROOT, if supplied."""
        import os
        root = os.environ.get('GC22_FIXTURE_ROOT')
        gc19 = os.environ.get('GC22_FIXTURE_GC19')
        if not (root and gc19):
            self.skipTest('set GC22_FIXTURE_ROOT and GC22_FIXTURE_GC19 for integration')
        with tempfile.TemporaryDirectory(prefix='gc22-schema-') as d:
            dst=Path(d)
            for rel in mod.FILES.values():
                p=dst/rel; p.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(Path(root)/rel,p)
            candidate_path=dst/SCHEME
            candidate=yaml.safe_load(candidate_path.read_text(encoding='utf8'))
            matches=[r for r in candidate['elements'] if r.get('id')=='P04.GREETING_BODY']
            self.assertEqual(len(matches),1)
            matches[0]['geometry']='GC16_CANDIDATE_AND_GC18_A2_VISUAL_TARGET'
            matches[0]['target_bbox_pdf_mm']=[32.,32.,182.,212.]
            candidate_path.write_text(yaml.safe_dump(candidate,allow_unicode=True),encoding='utf8')
            data=mod.load_inputs(dst,Path(gc19))
            self.assertEqual(data['boxes']['p04_greeting'],[32.,32.,182.,212.])


    def _real_local_fixture(self):
        """Bundled fixed synthetic fixture is discovered through env only."""
        import os
        root=os.environ.get('GC22_FIXTURE_ROOT')
        gc19=os.environ.get('GC22_FIXTURE_GC19')
        if not (root and gc19):
            self.skipTest('set GC22_FIXTURE_ROOT / GC22_FIXTURE_GC19')
        return Path(root),Path(gc19)

    def test_verify_fresh_stage_and_no_write(self):
        from types import SimpleNamespace
        prepress,gc19=self._real_local_fixture()
        with tempfile.TemporaryDirectory(prefix='gc22-stage-v03-') as temp:
            root=Path(temp)
            (root/'tmp').mkdir()
            output=root/'tmp'/'review_r001'
            current=mod.load_inputs(prepress,gc19)
            mod.stage(SimpleNamespace(output_dir=output, gdl_root=root),current)
            manifest=output/'reference_manifest.json'
            before={p.name:mod.sha(p) for p in output.iterdir()}
            r=mod.verify_staged_reference(prepress,gc19,root,output)
            after={p.name:mod.sha(p) for p in output.iterdir()}
            self.assertEqual(r['page_count'],4)
            self.assertEqual(r['png_count'],4)
            self.assertEqual(r['p04_greeting_bbox_pdf_mm'],[32.,32.,182.,212.])
            self.assertEqual(before,after)
            self.assertEqual(manifest.exists(),True)

    def test_verify_rejects_modified_pdf(self):
        from types import SimpleNamespace
        prepress,gc19=self._real_local_fixture()
        with tempfile.TemporaryDirectory(prefix='gc22-stage-v03-') as temp:
            root=Path(temp); (root/'tmp').mkdir()
            output=root/'tmp'/'review_r001'
            mod.stage(SimpleNamespace(output_dir=output,gdl_root=root),
                      mod.load_inputs(prepress,gc19))
            p=output/'greeting_card_layout_guide.pdf'
            with p.open('ab') as fp: fp.write(b'CHANGED')
            with self.assertRaisesRegex(mod.Blocked,'VERIFY_OUTPUT_SHA_MISMATCH'):
                mod.verify_staged_reference(prepress,gc19,root,output)

    def test_verify_rejects_unexpected_file(self):
        from types import SimpleNamespace
        prepress,gc19=self._real_local_fixture()
        with tempfile.TemporaryDirectory(prefix='gc22-stage-v03-') as temp:
            root=Path(temp); (root/'tmp').mkdir()
            output=root/'tmp'/'review_r001'
            mod.stage(SimpleNamespace(output_dir=output,gdl_root=root),
                      mod.load_inputs(prepress,gc19))
            (output/'surprise.txt').write_text('bad')
            with self.assertRaisesRegex(mod.Blocked,'VERIFY_UNEXPECTED_OR_MISSING_FILES'):
                mod.verify_staged_reference(prepress,gc19,root,output)

if __name__ == '__main__':
    unittest.main()
