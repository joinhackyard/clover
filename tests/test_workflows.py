"""Product memory regressions: fake model results, scratch storage, no Mac actions."""
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clover
from tests import scratch_dir


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(clover, 'SKILLS', str(scratch_dir(self) / 'skills.json'))
        p.start()
        self.addCleanup(p.stop)

    def test_automatically_saves_and_retrieves_verified_browser_procedure(self):
        p = unittest.mock.Mock()
        p.stdin = io.StringIO(); p.ask = ''; p.returncode = 0
        p.stdout = map(json.dumps, [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Bash',
             'input': {'command': clover.WEB + ' read'}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'Saved successfully.'}]}},
            {'type': 'result', 'result': 'Created your calendar event. [workflow create calendar event | Read the calendar form, fill today\'s requested values, save, then check the event appears.]'}])
        with patch.object(clover, 'say'):
            reply, _, _ = clover.run('make a calendar event', p)
        reply, saved = clover.remember_workflow('make a calendar event', reply, clover.run.ok, clover.run.cmds)
        self.assertTrue(saved)
        self.assertEqual(reply, 'Created your calendar event.')
        method = clover.workflows('Can you make a new calendar event tomorrow?')
        self.assertIn('Read the calendar form', method)
        self.assertNotIn('workflow', reply)
        self.assertEqual(clover.workflows('open calendar'), '')
        with patch.object(clover.subprocess, 'run') as action:
            self.assertIn('saved', clover.fast('And remember how to make a calendar event for the future'))
            action.assert_not_called()

    def test_never_saves_failed_incomplete_or_disabled_tasks(self):
        for reply, ok, cmds in [
                ('Done. [workflow start meeting | Use the menu; check meeting controls.]', False, ['open x']),
                ('Could not complete it. [workflow start meeting | Use the menu.]', True, ['open x']),
                ('Done. [workflow start meeting | Use the menu.]', True, []),
                ('[workflow start meeting | Use the menu.]', True, ['open x'])]:
            clean, saved = clover.remember_workflow('start meeting', reply, ok, cmds)
            self.assertFalse(saved)
            self.assertNotIn('[workflow', clean)
        with patch.object(clover, 'pref', return_value=False):
            _, saved = clover.remember_workflow('start meeting', 'Done. [workflow start meeting | Check meeting controls.]', True, ['open x'])
        self.assertFalse(saved)
        self.assertFalse((Path(clover.DIR) / 'workflows.json').exists())

    def test_unverified_history_cannot_be_claimed_as_remembered(self):
        with patch.object(clover.subprocess, 'run') as action:
            reply = clover.fast('remember how to create a meeting')
        self.assertIn('do not have a verified procedure', reply)
        action.assert_not_called()

    def test_learns_the_way_that_worked_without_the_ai_writing_a_tag(self):
        menu = clover.HANDS + ' click "Zoom Workplace > Start meeting"'
        tool = lambda i, c: {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': i, 'name': 'Bash', 'input': {'command': c}}]}}
        result = lambda i, err, content='': {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': i, 'is_error': err, 'content': content}]}}
        p = unittest.mock.Mock()
        p.stdin = io.StringIO(); p.ask = ''; p.returncode = 0
        p.stdout = map(json.dumps, [tool('a', clover.HANDS + ' see zoom.us'), result('a', False),
                                    tool('b', 'osascript -e "click New meeting"'), result('b', True),   # tried, failed, dropped
                                    tool('c', menu), result('c', False, 'Meeting controls are visible.'),
                                    {'type': 'result', 'result': 'Your Zoom meeting started.'}])
        with patch.object(clover, 'say'):
            reply, _, _ = clover.run('Um, make a new Zoom meeting', p)
        clover.learn('Um, make a new Zoom meeting', clover.run.cmds, reply)
        self.assertEqual(clover.skills()['make a new zoom meeting']['cmds'], [clover.HANDS+' menu zoom.us \'Zoom Workplace > Start meeting\''])
        with patch.object(clover, 'hands', return_value=('Clicked Start meeting', True)):
            self.assertEqual(clover.fast('start a zoom meeting'), 'Your Zoom meeting started.')
        clover.learn('click new meeting', [clover.HANDS + ' click 245,340'], 'Done.')   # a screen spot moves: never learned
        self.assertNotIn('click new meeting', clover.skills())

    def test_learns_only_the_successful_retry_when_a_tool_reports_failure(self):
        first, retry = (f'{clover.PLACE} Fixture fullscreen {screen}' for screen in ('monitor', 'laptop'))
        tool = lambda i, command: {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': i, 'name': 'Bash', 'input': {'command': command}}]}}
        receipt = lambda i, output, error=False: {'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': i, 'is_error': error, 'content': output}]}}
        p = unittest.mock.Mock(stdin=io.StringIO(), ask='', returncode=0)
        p.stdout = map(json.dumps, [tool('first', first), receipt('first', 'NOT DONE: wrong display.', True),
                                    tool('retry', retry), receipt('retry', 'Fixture window -> fullscreen.'),
                                    {'type': 'result', 'is_error': False, 'result': 'Done.'}])
        with patch.object(clover, 'say'):
            reply, _, _ = clover.run('Arrange workspace', p)
        self.assertTrue(clover.run.ok)
        self.assertEqual(clover.run.cmds, [retry])
        with patch.object(clover, 'cached_hands', return_value=None):
            self.assertTrue(clover.learn('Arrange workspace', clover.run.cmds, reply))
        self.assertEqual(clover.skills()['arrange workspace']['cmds'], [retry])

    def test_failure_words_in_ordinary_read_output_are_untrusted_text(self):
        p = unittest.mock.Mock(stdin=io.StringIO(), ask='', returncode=0)
        p.stdout = map(json.dumps, [
            {'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'id': 'read', 'name': 'Read', 'input': {'file_path': 'fixture.txt'}}]}},
            {'type': 'user', 'message': {'content': [
                {'type': 'tool_result', 'tool_use_id': 'read', 'is_error': False,
                 'content': 'The page says the previous attempt failed and cannot continue.'}]}},
            {'type': 'result', 'is_error': False, 'result': 'I read the page.'}])
        with patch.object(clover, 'say'):
            clover.run('Read the fixture', p)
        self.assertTrue(clover.run.ok)
        self.assertFalse(clover.run.observed[0]['error'])

    def test_failed_or_unsafe_receipts_are_not_learned(self):
        tool = lambda command: {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': 'action', 'name': 'Bash', 'input': {'command': command}}]}}
        receipt = lambda output, error: {'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'action', 'is_error': error, 'content': output}]}}
        for command, output, error, ok in [(f'{clover.PLACE} Fixture fullscreen laptop', 'NOT DONE: no window found.', True, False),
                                           ('rm -rf /tmp/example', 'Done.', False, True)]:
            with self.subTest(command=command):
                p = unittest.mock.Mock(stdin=io.StringIO(), ask='', returncode=0)
                p.stdout = map(json.dumps, [tool(command), receipt(output, error),
                                            {'type': 'result', 'is_error': False, 'result': 'Done.'}])
                with patch.object(clover, 'say'):
                    reply, _, _ = clover.run('Arrange workspace', p)
                self.assertEqual(clover.run.ok, ok)
                with patch.object(clover, 'cached_hands', return_value=None):
                    self.assertIsNone(clover.learn('Arrange workspace', clover.run.cmds, reply))
        self.assertEqual(clover.skills(), {})

    def test_replay_runs_instantly_for_any_wording_and_rejects_unsafe_commands(self):
        cmd = clover.HANDS + ' menu us.zoom.xos "Zoom Workplace > Start meeting"'
        reply, saved = clover.remember_workflow('Um, can you make a new Zoom meeting?',
            f'Your meeting started. [workflow start zoom meeting | Use the Zoom menu; check the meeting window.] [replay {cmd}]', True, [cmd])
        self.assertTrue(saved)
        self.assertEqual(reply, 'Your meeting started.')
        with patch.object(clover, 'hands', return_value=('Clicked Start meeting', True)) as action:
            self.assertEqual(clover.fast('Make a zoom meeting.'), 'Your meeting started.')
            self.assertIsNone(clover.fast('make a zoom call'))   # different words that matter: the AI decides
        self.assertEqual(action.call_args_list[0].args, ('menu', 'us.zoom.xos', 'Zoom Workplace > Start meeting'))
        for bad in [clover.HANDS + ' click 1,2', 'rm -rf ~/x', clover.HANDS + ' see x']:
            clover.remember_workflow('do thing', f'Done. [workflow do thing | a] [replay {bad}]', True, ['open x'])
            self.assertNotIn('do thing', clover.skills())

    def test_method_can_contain_shell_brackets_but_malformed_metadata_is_not_saved(self):
        reply, saved = clover.remember_workflow('check report ready',
            'Ready. [workflow check report ready | Run [ -f report.txt ] and inspect its contents.]', True, ['test -f report.txt'])
        self.assertTrue(saved)
        self.assertEqual(reply, 'Ready.')
        self.assertIn('[ -f report.txt ]', clover.workflows('check report ready'))
        for tag in ['[workflow invalid]', '[workflow | missing task]', '[workflow missing method | ]']:
            _, saved = clover.remember_workflow('bad task', 'Done. ' + tag, True, ['open x'])
            self.assertFalse(saved)

    def test_model_recipe_cannot_save_commands_that_were_not_run(self):
        actual=f'{clover.PLACE} Editor full monitor'
        invented=f'{clover.PLACE} Browser full laptop'
        _,saved=clover.remember_workflow('arrange desk',f'Done. [workflow arrange desk | Move and check the windows.] [replay {invented}]',True,[actual])
        self.assertTrue(saved)   # historical guidance may be kept, but it is not an executable shortcut
        self.assertNotIn('arrange desk',clover.skills())

    def test_ai_shortcut_helper_defers_saving_until_verification(self):
        command=f'{clover.SHOW} Editor'
        with patch.dict(os.environ,{'CLOVER_ASK':str(Path(clover.DIR)/'agent')}), \
             patch.object(sys,'argv',['clover.py','--shortcut','focus time',command]),patch('sys.stdout',new_callable=io.StringIO) as output:
            clover.main()
        self.assertEqual(clover.skills(),{})
        self.assertIn('successful tool results',output.getvalue())
        # A user's direct CLI definition remains available without running its actions.
        with patch.dict(os.environ,{k:v for k,v in os.environ.items() if k!='CLOVER_ASK'},clear=True), \
             patch.object(sys,'argv',['clover.py','--shortcut','focus time',command]),patch('sys.stdout',new_callable=io.StringIO):
            clover.main()
        self.assertEqual(clover.skills()['focus time']['cmds'],[command])

    def test_correction_removes_procedure_even_with_different_wording(self):
        clover.workflows('create calendar event', 'Use calendar form; verify event exists.')
        clover.unlearn('make a new calendar event')
        self.assertEqual(clover.workflows('create calendar event'), '')

    def test_settings_can_inspect_and_delete_saved_procedure(self):
        clover.workflows('create calendar event', 'Fill calendar form; verify event exists.')
        with patch('sys.argv', ['clover.py', '--state']), patch.object(clover, 'plan', return_value={}), \
             patch.object(clover, 'me', return_value={}), patch.object(clover, 'MEMORY', str(Path(clover.DIR) / 'memory.md')), \
             patch('sys.stdout', new_callable=io.StringIO) as out:
            clover.main()
        row = json.loads(out.getvalue())['skills'][0]
        self.assertEqual(row['say'], 'create calendar event')
        self.assertIn('verify event', row['reply'])
        with patch('sys.argv', ['clover.py', '--unlearn', row['say']]):
            clover.main()
        self.assertEqual(clover.workflows(), {})

    def test_full_request_saves_then_reuses_procedure_without_extra_model_call(self):
        brain = unittest.mock.Mock(return_value=(
            'Created it. [workflow create calendar event | Read calendar, fill current values, save; verify event exists.]', .001, []))
        brain.ok = True
        brain.cmds = brain.ran = [clover.WEB + ' read', clover.WEB + ' fill 2 title']
        brain.observed = []
        with patch.multiple(clover, licensed=lambda: True, ping=lambda: None, fast=lambda _: None,
                            front=lambda: ('Notes', ''), osa=lambda *a: '', screens=lambda: [],
                            describe=lambda *a: '', me_line=lambda: '', selection_context=lambda: '',
                            relevant_rules=lambda _: '', recent=lambda: [], screen_for=lambda *a: None,
                            wait_commit=lambda: True, run=brain, remember_turn=lambda *a: None,
                            log_turn=lambda *a, **k: None, restore_focus=lambda *a: None), \
             patch.object(clover.threading, 'Thread'), patch('sys.stdout', io.StringIO()):
            with patch('sys.argv', ['clover.py', 'make a calendar event']):
                clover.main()
            self.assertEqual(brain.call_count, 1)
            brain.return_value = ('Created it.', .001, [])
            with patch('sys.argv', ['clover.py', 'create a new calendar event tomorrow']):
                clover.main()
        self.assertEqual(brain.call_count, 2)
        self.assertIn('Saved workflow (historical guidance)', brain.call_args.args[0])
        self.assertIn('verify event exists', brain.call_args.args[0])

    def test_only_matching_procedure_enters_prompt_and_remember_waits_for_confirmation(self):
        clover.workflows('create calendar event', 'a' * 2000)
        clover.workflows('play jazz playlist', 'Read playlists; choose jazz; verify playing.')
        self.assertEqual(len(clover.workflows('create calendar event').split('Procedure: ')[1]), 800)
        self.assertNotIn('jazz', clover.workflows('create calendar event'))
        with patch.dict(os.environ, {'CLOVER_LIVE': '1'}):
            self.assertIsNone(clover.fast('remember how to create calendar event'))
        full = clover.SYSTEM + clover.ASK_ME + clover.POINTER + clover.LEARN_ME + clover.TEACH + clover.ASK_FIRST + clover.WORKFLOW
        self.assertLessEqual(len(full), 10000)
        installed = os.path.expanduser("~/Applications/Clover.app/Contents/Resources/clover.py")
        self.assertLessEqual(len(full.replace(clover.ME, installed)), 10000)

    def test_interrupted_shortcut_save_preserves_private_previous_file(self):
        saved={'original':{'mine':True,'cmds':['echo ok'],'reply':'Done.'}}
        Path(clover.SKILLS).write_text(json.dumps(saved))
        with patch.object(clover.json,'dump',side_effect=OSError('disk full')):
            with self.assertRaises(OSError): clover.save_skills({'new':{'mine':True}})
        self.assertEqual(clover.skills(),saved)
        self.assertEqual(list(Path(clover.DIR).iterdir()),[Path(clover.SKILLS)])
        clover.save_skills(saved)
        self.assertEqual(Path(clover.SKILLS).stat().st_mode & 0o777,0o600)


if __name__ == '__main__':
    unittest.main()
