#!/usr/bin/env python3
"""Offline canonical source regression; no server, client, Windows or Git mutations."""
import importlib.util, json, hashlib, pathlib, re, subprocess, shutil, unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/'scripts/graphic_design_lab/greeting_cards'
STUDIO=SCRIPTS/'illustrator_studio_cli_v1.py'
SPEC=importlib.util.spec_from_file_location('studio_under_test',STUDIO)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class Tests(unittest.TestCase):
    def test_01_single_renderer(self):
        t=M.render_template()
        self.assertEqual(t.count('function greeting(font)'),1)
        self.assertEqual(t.count('function sender(font)'),1)
        self.assertEqual(t.count('/*__GC29_SCENE__*/'),1)
    def test_02_configuration(self):
        d=M.config();self.assertEqual(len(d['allowed_profiles']),4)
        self.assertEqual(d['policy']['automatic_queue'],False)
    def test_03_pasport(self):
        d=M.safe_json(M.PASSPORT)
        self.assertEqual(d['source_of_truth']['renderer'],str(M.JSX.relative_to(M.ROOT)))
        self.assertGreaterEqual(len(d['issues']),13)
    def test_04_no_private_data(self):
        data=STUDIO.read_text('utf8')+M.render_template()+M.CFG.read_text('utf8')
        self.assertNotIn('EXAMPLE_CLIENT_PRIVATE',data)
        self.assertNotIn('EXAMPLE_PHONE_PRIVATE',data)
    def test_05_p04_fresh_frames(self):
        s=M.render_template().split('  function greeting(font){',1)[1].split('  function sender(font){',1)[0]
        self.assertIn('t.remove()',s)
        self.assertIn('visible===exact',s)
        self.assertNotIn('app.redraw()',s)
        self.assertNotIn('ch.size=',s)
        self.assertNotIn('ch.leading=',s)
    def test_06_sender_one_config(self):
        t=M.render_template()
        self.assertIn('scene.studio_settings.sender.baselines_mm',t)
        self.assertIn('scene.studio_settings.sender.font_sizes_pt[i]',t)
    def test_07_p03_one_config(self):
        self.assertIn('scene.studio_settings.p03.photo_clip_mm',M.render_template())
    def test_08_no_runtime_tmp_reference(self):
        code=STUDIO.read_text('utf8');self.assertNotIn("ROOT/'tmp'",code)
        self.assertNotIn("root/'tmp'",code)
    def test_09_no_native_by_default(self):
        self.assertEqual(M.main(['--mode','check']),0)
    def test_10_wrong_confirmation(self):
        with self.assertRaises(M.Blocked):M.execute('pilot','fake',M.JOBS[1],None,24,False,None)
    def test_11_unknown_job(self):
        with self.assertRaises(M.Blocked):M.execute('pilot','fake','unknown',None,24,True,'x')
    def test_12_missing_status_attempt(self):
        with self.assertRaises(M.Blocked):M.execute('status','fake',M.JOBS[1],None,24,False,None)
    def test_13_pinned_transport(self):
        self.assertEqual(len(M.BM_SHA),64);self.assertEqual(len(M.BC_SHA),64)
    def test_14_no_legacy_renderer_dependencies(self):
        code=STUDIO.read_text('utf8')
        for x in ('gc47bx_fresh_frame_native_fit_r001.py','gc47bw_shared_p04_bounded_tier_r001.py','gc47bu_apa_fixed_tier_recovery_r001.py'):
            self.assertNotIn(x,code)
    def test_15_manifest_receipt_auth(self):
        code=STUDIO.read_text('utf8')
        self.assertIn("'automatic_retry':False",code)
        self.assertIn("'native_dispatch_count_max':1",code)
        self.assertIn("'canonical_renderer_sha256'",code)
    def test_16_four_jobs_synthetic_compilation(self):
        setting=M.config();source=M.render_template();template_sha=M.sha(source.encode())
        for job in M.JOBS:
            scene={'job_id':job,'pages':4,'production_ready':False,'visual_approved':False,
                   'greeting_text':'Lorem ipsum '+job,'front_lines':['Line 1','Line 2'],
                   'sender_lines':['Sender','Row 2','Row 3'], 'layers':[]}
            legacy=b'#target illustrator\n'+job.encode()
            assets={f'asset_{i}.png':b'A'*512+str(i).encode() for i in range(12)}
            manifest={'jsx_sha256':M.sha(legacy),'asset_sha256':{k:M.sha(v) for k,v in assets.items()},
                      'job_id':job,'pages':4,'production_ready':False,'visual_approved':False}
            compiled={job:(scene,legacy,json.dumps(manifest).encode(),assets,'OLD_COMPAT_SOURCE')}
            obj=M.candidate(job,compiled,setting,source)
            self.assertEqual(obj['renderer_sha'],template_sha)
            self.assertIn(b'ILLUSTRATOR_STUDIO_ONE_CANONICAL_JSX_V1',obj['jsx'])
            self.assertNotIn(b'/*__GC29_SCENE__*/',obj['jsx'])
            self.assertEqual(json.loads(obj['manifest'])['jsx_sha256'],obj['jsx_sha'])
    def test_17_js_syntax_offline(self):
        cmd=shutil.which('node')
        if cmd is None:self.skipTest('node missing on target; locally checked during package build')
        s=M.render_template().replace('/*__GC29_SCENE__*/','{}')
        if s.startswith('#target illustrator'):s=s.split('\n',1)[1]
        process=subprocess.run([cmd,'--check','-'],input=s,text=True,capture_output=True)
        self.assertEqual(process.returncode,0,process.stderr)
    def test_18_client_token_unicode(self):
        name='Тестова назва з пробілами'
        self.assertEqual(M.decode_client(M.encode_client(name)),name)
    def test_19_client_token_invalid(self):
        with self.assertRaises(M.Blocked):M.decode_client('..')
    def test_20_passport_visual_bugs(self):
        rows=M.safe_json(M.PASSPORT)['issues'];ids={x['id'] for x in rows}
        self.assertIn('STUDIO-P04-002',ids);self.assertIn('STUDIO-P03-001',ids)
    def test_21_no_auto_loop_native(self):
        code=STUDIO.read_text('utf8')
        self.assertEqual(code.count("controller_command(attempt,'launch')"),1)
    def test_22_one_shared_p04_tier_config(self):
        conf=M.config()['p04']
        self.assertIn(14,conf['long_tiers_pt']);self.assertIn(15,conf['long_tiers_pt'])
        self.assertIn(18.5,conf['short_tiers_pt'])
    def test_23_readonly_status_design_edit_independent(self):
        code=STUDIO.read_text('utf8')
        self.assertIn('def bound(',code);self.assertIn('ATTEMPT.fullmatch',code)
    def test_24_zap_supported_by_entry(self):
        self.assertEqual(M.JOBS[0],'gdl_gc_zap_20261011')
        self.assertIn('if job!=ZAP',STUDIO.read_text('utf8'))
    def test_25_production_flag_never_generated(self):
        self.assertIn('"production_ready":false',M.render_template())
    def test_27_passport_export_code(self):
        self.assertIn('def export_passport():',STUDIO.read_text('utf8'))
    def test_26_no_force_kill(self):
        self.assertNotIn('taskkill',STUDIO.read_text('utf8').lower())

if __name__=='__main__':unittest.main(verbosity=2)
