"""Offline data agent orchestration tests: no database, API or LLM calls."""
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from qa_agents.data import command


class DataTests(unittest.TestCase):
    def test_agent_uses_fixed_transport_and_explicit_run_id(self):
        with patch('qa_agents.data.subprocess.run') as child:
            child.return_value = SimpleNamespace(returncode=0, stdout='{"connected":true}')
            self.assertTrue(command('prepare', 'run-1')['connected'])
            argv = child.call_args.args[0]
            self.assertEqual(argv[-3:], ['prepare', '--run-id', 'run-1'])

    def test_provider_failure_never_exposes_subprocess_secrets(self):
        with patch('qa_agents.data.subprocess.run') as child:
            child.return_value = SimpleNamespace(returncode=1, stdout='password=SECRET', stderr='SECRET')
            with self.assertRaisesRegex(RuntimeError, 'dedicated PostgreSQL') as error:
                command('status')
            self.assertNotIn('SECRET', str(error.exception))

    def test_preparation_failure_prevents_test_runner(self):
        from qa_agents.pipeline import build_graph
        from qa_agents.tests.test_pipeline import execution
        calls = []
        with patch.dict(os.environ, {'TEST_DATA_PROVIDER': 'postgres'}), patch(
                'qa_agents.pipeline.data_command', side_effect=RuntimeError('unavailable')):
            state = build_graph(runner=lambda *args: calls.append(args), reader=lambda *_: execution()).invoke({
                'run_id': 'offline-data', 'results_dir': 'unused', 'mode': 'full', 'local_only': True})
        self.assertEqual(calls, [])
        self.assertEqual(state['summary']['data']['status'], 'ERROR')
        self.assertEqual(state['summary']['exit_code'], 1)
