"""Daily capture stays anonymous and retries failed sends, without network access."""
import json
import os
import platform
from pathlib import Path
import subprocess
import tempfile
import io
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import clover
from tests import run_swift


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        test_dir = os.environ.pop('CLOVER_DIR', None)
        self.addCleanup(lambda: os.environ.__setitem__('CLOVER_DIR', test_dir) if test_dir is not None else os.environ.pop('CLOVER_DIR', None))

    def test_success_is_daily_and_failure_can_retry(self):
        with tempfile.TemporaryDirectory(prefix='clover telemetry ') as root:
            root = Path(root)
            curl = root / 'curl'
            curl.write_text('#!/bin/sh\nexit "${FAKE_CURL_STATUS:-0}"\n')
            curl.chmod(0o700)
            spawn = subprocess.Popen

            def fake_send(args, **kwargs):
                payload = json.loads(args[4])
                self.assertEqual(payload['event'], 'used')
                self.assertEqual(payload['api_key'], 'fixture-token')
                self.assertEqual(payload['properties'], {'$process_person_profile': False, 'version': clover.APP_VERSION, 'commit': clover.APP_COMMIT,
                                                                  'macos': platform.mac_ver()[0], 'client': 'claude'})
                self.assertEqual(set(payload), {'api_key', 'event', 'distinct_id', 'properties'})
                worker = spawn(args, **kwargs)
                worker.wait(timeout=5)
                return worker

            with patch.object(clover, 'DIR', str(root)), patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), \
                 patch.object(clover, 'pref', return_value=True), patch.object(clover.subprocess, 'Popen', side_effect=fake_send) as send, \
                 patch.dict(os.environ, {'PATH': str(root), 'FAKE_CURL_STATUS': '22'}):
                clover.ping()
                self.assertFalse((root / 'pinged').exists())
                identity = (root / 'id').read_text()
                os.environ['FAKE_CURL_STATUS'] = '0'
                clover.ping()
                self.assertTrue((root / 'pinged').exists())
                clover.ping()
                self.assertEqual(send.call_count, 2)
                self.assertEqual((root / 'id').read_text(), identity)

    def test_failure_and_used_events_include_the_same_app_version_field(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), \
             patch.object(clover, 'pref', side_effect=lambda k, d: {'improve': True}.get(k, d)), \
             patch.object(clover.subprocess, 'Popen') as send:
            clover.report('Open the fixture', 'Could not open it', (), 1, 'error')
        payload = json.loads(send.call_args.args[0][4])
        self.assertEqual(payload['event'], 'task_failed')
        self.assertEqual(payload['properties']['version'], clover.APP_VERSION)
        self.assertEqual(set(payload['properties']), {'$process_person_profile', 'version', 'commit', 'task', 'reply', 'steps', 'why', 'secs', 'model', 'client', 'macos'})

    def test_failure_reports_drop_text_applescript_types_or_writes(self):
        steps = ['osascript -e \'tell application "System Events" to keystroke "hunter2"\'',
                 'osascript -e \'tell application "Notes" to make new note with properties {name:"Diary", body:"private words"}\'',
                 'osascript -e \'tell application "Notes" to set body of note 1 to "private words"\'']
        cleaned = ' '.join(map(clover.clean, steps))
        self.assertFalse(any(word in cleaned for word in ('hunter2', 'Diary', 'private')))
        self.assertIn('tell application "Notes"', cleaned)

    def test_ask_done_has_counts_and_command_classes_but_no_ask_text(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), patch.object(clover, 'pref', return_value=True), \
             patch.object(clover.subprocess, 'Popen') as send:
            clover.ask_done({'task': 'Private request', 'reply': 'Private answer', 'path': 'shortcut', 'model': 'instant',
                              'secs': 1.26, 'steps': ['one', 'two'], 'ran': [f'{clover.PLACE} Notes left', f'{clover.WEB} read secret'],
                              'status': 'completed', 'escalated': False})
        payload = json.loads(send.call_args.args[0][4])
        self.assertEqual(payload['event'], 'ask_done')
        self.assertEqual(payload['properties']['tools'], ['place', 'web'])
        self.assertEqual(payload['properties']['status'], 'ok')
        self.assertEqual(set(payload['properties']), {'$process_person_profile', 'version', 'commit', 'path', 'model', 'secs', 'steps',
                                                      'tools', 'status', 'escalated', 'macos', 'client'})
        self.assertNotIn('Private', json.dumps(payload))

    def test_ask_done_maps_terminal_states(self):
        with patch.object(clover, 'posthog') as send:
            for state in ('completed', 'failed', 'cancelled'):
                clover.ask_done({'status': state})
        self.assertEqual([call.args[1]['status'] for call in send.call_args_list], ['ok', 'failed', 'cancelled'])

    def test_error_shapes_never_include_exception_messages_or_shortcut_words(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), patch.object(clover, 'pref', return_value=True), \
             patch.object(clover.subprocess, 'Popen') as send:
            try:
                raise RuntimeError('private crash detail')
            except RuntimeError as error:
                clover.exception_error(type(error), error.__traceback__)
            clover.report_error('replay', shortcut='0123456789abcdef', failed_at=2)
        crash, replay = [json.loads(call.args[0][4]) for call in send.call_args_list]
        self.assertEqual(set(crash['properties']), {'$process_person_profile', 'version', 'commit', 'kind', 'macos', 'client',
                                                    'exception', 'file', 'line', 'function', 'at_line', 'at_function'})
        self.assertEqual(crash['properties']['exception'], 'RuntimeError')
        self.assertNotIn('private crash detail', json.dumps(crash))
        self.assertEqual(replay['properties']['kind'], 'replay')
        self.assertEqual(replay['properties']['shortcut'], '0123456789abcdef')
        self.assertEqual(replay['properties']['failed_at'], 2)

    def test_a_crash_inside_the_standard_library_names_the_clover_line_and_errno(self):
        code = {}
        exec(compile('import subprocess\ndef go():\n    subprocess.Popen(["/no/such/tool"])\n', clover.ME, 'exec'), code)   # a frame that counts as clover.py
        with patch.object(clover, 'report_error') as sent:
            try:
                code['go']()
            except OSError as error:
                clover.exception_error(type(error), error.__traceback__, error)
        props = sent.call_args.kwargs
        self.assertEqual((props['at_function'], props['at_line'], props['errno']), ('go', 3, 2))
        self.assertEqual(props['exception'], 'FileNotFoundError')
        self.assertNotEqual(props['file'], 'clover.py')

    def test_setup_problems_are_separate_from_real_worker_failures(self):
        cases = [('HTTP 404: model llama3 may not exist', True, 'server_rejected'),
                 ('400: model does not support tools', True, 'server_rejected'),
                 ('422: incompatible request', True, 'server_rejected'),
                 ('OAuth session expired', False, 'signed_out'),
                 ('HTTP 429', False, 'rate_limited'), ('Rate limit reached for requests', False, 'rate_limited'),
                 ('You’ve hit your weekly limit · resets 3pm', False, 'plan_limit'), ('Context window limit reached', False, 'too_long'),
                 ('network connection failed', False, 'offline')]
        with patch.object(clover, 'report_error') as sent:
            for detail, custom, why in cases:
                self.assertEqual(clover.failure_why(detail, custom), why)
                clover.report_worker_failure('claude', 'private-model-name', why)
            for why in ('setup_needed', 'provider_needed', 'model_missing'):
                clover.report_worker_failure('antigravity', 'haiku', why)
        self.assertTrue(all(call.args == ('setup',) for call in sent.call_args_list))
        self.assertNotIn('private', str(sent.call_args_list))
        with patch.object(clover, 'report_error') as sent:
            clover.report_worker_failure('claude', 'haiku', clover.failure_why('Unknown process failure'))
        sent.assert_called_once_with('worker_exit', worker='claude', model='haiku', why='stopped')

    def test_cancellation_has_no_error_event(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), patch.object(clover, 'TURN', {}), \
             patch.object(clover, 'posthog') as sent:
            clover.begin_turn('Private request')
            clover.end_turn()
            clover.report_worker_failure('claude', 'haiku', 'cancelled')
        self.assertEqual([call.args[0] for call in sent.call_args_list], ['ask_done'])
        self.assertEqual(sent.call_args.args[1]['status'], 'cancelled')

    def test_allow_decisions_share_denial_without_matching_reply_text(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.dict(os.environ, {'CLOVER_ASK': root}):
            marker = Path(root, 'declined')
            for question, answer, declined in [({'q': 'Send?', 'cmd': 'fixture'}, 'n', True),
                                                ({'q': 'Send?', 'cmd': 'fixture'}, 'y', False),
                                                ({'q': 'Send?', 'cmd': 'fixture'}, 'task', False),
                                                ({'pick': 'Which?', 'options': []}, '', False),
                                                ({'q': 'Retry?', 'retry': True}, 'n', False),
                                                ({'q': 'Permission?', 'need': 'screen'}, 'n', False)]:
                marker.unlink(missing_ok=True)
                def respond(path, data): Path(data['_a']).write_text(answer)
                with patch.object(clover, 'private_json', side_effect=respond):
                    self.assertEqual(clover.ask_user(question, 1), answer)
                self.assertEqual(marker.exists(), declined)
            clover.ask_user({'q': 'Send?', 'cmd': 'fixture'}, 0)
            self.assertTrue(marker.exists())
            with patch.object(Path, 'touch', side_effect=FileNotFoundError):
                self.assertIsNone(clover.ask_user({'q': 'Send?', 'cmd': 'fixture'}, 0))

    def test_question_after_ask_cleanup_is_cancelled_without_publishing_a_card(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.dict(os.environ, {'CLOVER_ASK': str(Path(root, 'removed-ask'))}), \
             patch.object(clover, 'private_json') as publish:
            directory = Path(root, 'removed-ask')
            directory.mkdir()
            open_lock = os.open
            def cancelled_before_lock(path, flags, mode):
                directory.rmdir()
                return open_lock(path, flags, mode)
            with patch.object(clover.os, 'open', side_effect=cancelled_before_lock):
                self.assertIsNone(clover.ask_user({'q': 'Send?', 'cmd': 'fixture'}, 60))
            self.assertIsNone(clover.ask_user({'q': 'Send?', 'cmd': 'fixture'}, 60))
            publish.assert_not_called()
            self.assertFalse(Path(root, 'removed-ask').exists())

    def test_main_crash_is_reported_once_with_the_handled_exit_status(self):
        with patch.object(clover, 'main', side_effect=RuntimeError('private detail')), \
             patch.object(clover, 'end_turn') as end, patch.object(clover, 'telemetry_enabled', return_value=True), \
             patch.object(clover, 'posthog') as sent, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit) as stopped: clover.run_main()
        self.assertEqual(stopped.exception.code, 70)
        end.assert_called_once_with('crashed')
        sent.assert_called_once()
        self.assertEqual((sent.call_args.args[0], sent.call_args.args[1]['kind'], sent.call_args.args[1]['worker']), ('error', 'worker_exit', 'python'))
        self.assertNotIn('private detail', str(sent.call_args))

    def test_normal_exits_and_a_closed_output_pipe_do_not_report_crashes(self):
        with patch.object(clover, 'report_error') as sent, patch.object(clover, 'end_turn') as end:
            with patch.object(clover, 'main', side_effect=SystemExit(0)):
                with self.assertRaises(SystemExit): clover.run_main()
            reader, writer = os.pipe(); os.close(reader)
            with os.fdopen(writer, 'w') as output, patch.object(clover, 'main', side_effect=BrokenPipeError), \
                 patch.object(clover, 'stop_workers') as stop, patch('sys.stdout', output):
                clover.run_main()
                sys.stdout.close()   # run_main replaced it with devnull
            stop.assert_called_once()
        sent.assert_not_called(); end.assert_not_called()

    def test_a_failed_crash_checkpoint_cannot_duplicate_or_hide_the_crash(self):
        with patch.object(clover, 'main', side_effect=ValueError('private detail')), \
             patch.object(clover, 'end_turn', side_effect=OSError('unwritable log')), \
             patch.object(clover, 'report_error') as sent, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit) as stopped: clover.run_main()
        self.assertEqual(stopped.exception.code, 70)
        sent.assert_called_once()
        self.assertEqual(sent.call_args.args, ('worker_exit',))
        self.assertEqual(sent.call_args.kwargs['exception'], 'ValueError')

    def test_thread_exit_is_normal_and_a_closed_relay_pipe_cancels_the_process(self):
        reader, writer = os.pipe(); os.close(reader)
        with os.fdopen(writer, 'w') as output, patch.object(sys, 'excepthook'), patch.object(threading, 'excepthook'), \
             patch.object(clover, 'report_error') as sent, patch.object(clover, 'stop_workers') as stop, patch('sys.stdout', output):
            clover.install_exception_hooks()
            for error in (SystemExit(0), BrokenPipeError()):
                threading.excepthook(SimpleNamespace(exc_type=type(error), exc_value=error, exc_traceback=None))
            sys.stdout.close()
        stop.assert_called_once(); sent.assert_not_called()

    def test_a_daemon_thread_failing_during_shutdown_is_not_a_crash(self):
        with patch.object(sys, 'excepthook'), patch.object(threading, 'excepthook') as previous, \
             patch.object(clover, 'report_error') as sent:
            clover.install_exception_hooks()
            with patch.object(threading, 'main_thread', return_value=SimpleNamespace(is_alive=lambda: False)):
                threading.excepthook(SimpleNamespace(exc_type=ValueError, exc_value=ValueError(), exc_traceback=None))
            error = RuntimeError('cannot schedule new futures after interpreter shutdown')
            threading.excepthook(SimpleNamespace(exc_type=type(error), exc_value=error, exc_traceback=None))
            sent.assert_not_called(); previous.assert_not_called()
            for detail in ('real worker failure', 'cannot schedule new futures after shutdown'):
                error = RuntimeError(detail)
                threading.excepthook(SimpleNamespace(exc_type=type(error), exc_value=error, exc_traceback=None))
        self.assertEqual(sent.call_count, 2); self.assertEqual(previous.call_count, 2)

    def test_a_backend_broken_pipe_with_live_output_is_a_real_failure(self):
        with patch.object(clover, 'main', side_effect=BrokenPipeError), patch.object(clover, 'end_turn'), \
             patch.object(clover, 'report_error') as sent, patch('sys.stdout', io.StringIO()), patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit) as stopped: clover.run_main()
        self.assertEqual(stopped.exception.code, 70)
        self.assertEqual(sent.call_args.args, ('worker_exit',))

    def test_swift_reports_only_unreported_process_deaths(self):
        source = Path(clover.ME).with_name('Clover.swift').read_text()
        rule = next(line.strip() for line in source.splitlines() if 'if p.terminationReason == .uncaughtSignal' in line)
        run_swift(self, '''import Foundation
struct Worker { var terminationReason: Process.TerminationReason; var terminationStatus: Int32 }
var sent = 0
func telemetry(_ args: [String]) { sent += 1 }
for (p, expected) in [(Worker(terminationReason: .exit, terminationStatus: 0), 0),
                      (Worker(terminationReason: .exit, terminationStatus: 70), 0),
                      (Worker(terminationReason: .exit, terminationStatus: 1), 1),
                      (Worker(terminationReason: .uncaughtSignal, terminationStatus: 15), 1),
                      (Worker(terminationReason: .uncaughtSignal, terminationStatus: 70), 1)] {
    sent = 0
    ''' + rule + '''
    precondition(sent == expected)
}
''')

    def test_dictation_has_only_mode_counts_timing_and_outcome(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), patch.object(clover, 'pref', return_value=True), \
             patch.object(clover.subprocess, 'Popen') as send:
            clover.dictation_event('cleanup', 1.23456, True, False, False, 'no box')
        payload = json.loads(send.call_args.args[0][4])
        self.assertEqual(payload['event'], 'dictation')
        self.assertEqual(payload['properties']['secs'], 1.235)
        self.assertEqual(set(payload['properties']), {'$process_person_profile', 'version', 'commit', 'macos', 'client', 'mode', 'secs',
                                                      'cleanup_used', 'fell_back', 'timed_out', 'insert'})

    def test_the_ask_log_and_its_folder_are_private_even_on_older_installs(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root):
            os.chmod(root, 0o755); log = Path(root, 'log.jsonl'); log.write_text(''); log.chmod(0o644)
            clover.append_log({'task': 'Summarize my inbox'})
            self.assertEqual((os.stat(root).st_mode & 0o777, log.stat().st_mode & 0o777), (0o700, 0o600))

    def test_disabled_does_not_send(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.object(clover.subprocess, 'Popen') as send:
            with patch.object(clover, 'POSTHOG_KEY', ''):
                clover.ping()
            with patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), \
                 patch.object(clover, 'pref', side_effect=lambda key, default: True if key == 'improve' else False):
                clover.ping()
                clover.ask_done({'status': 'completed'})
                clover.report_error('stopped')
                clover.dictation_event('verbatim', 1, False, False, False, 'ok')
                clover.report('Private request', 'Private reply', (), 1, 'error')
            send.assert_not_called()
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_new_users_are_counted_by_default(self):
        with tempfile.TemporaryDirectory() as root, patch.object(clover, 'DIR', root), \
             patch.object(clover, 'PREFS', str(Path(root) / 'settings.json')), \
             patch.object(clover, 'POSTHOG_KEY', 'fixture-token'), patch.object(clover.subprocess, 'Popen') as send:
            clover.ping()
        send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
