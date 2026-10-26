import unittest
from unittest.mock import patch
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from qa_agents import observability as obs


class ObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exporter = InMemorySpanExporter()
        cls.provider = TracerProvider()
        cls.provider.add_span_processor(SimpleSpanProcessor(cls.exporter))

    @classmethod
    def tearDownClass(cls):
        cls.provider.shutdown()

    def setUp(self):
        self.exporter.clear()
        # OpenTelemetry's global provider is write-once and may already belong
        # to Langfuse. Use an isolated tracer without changing global state.
        tracer = patch.object(trace, 'get_tracer', return_value=self.provider.get_tracer('qa-framework'))
        tracer.start()
        self.addCleanup(tracer.stop)
        self.enabled = patch.object(obs, 'client', return_value=object())
        self.enabled.start()
        self.addCleanup(self.enabled.stop)

    def test_metadata_and_errors_never_capture_payloads(self):
        with self.assertRaisesRegex(ValueError, 'SECRET'):
            with obs.observation('python.failure', {'input': 'SECRET', 'qa.operation': 'test'}):
                raise ValueError('SECRET')
        span = self.exporter.get_finished_spans()[-1]
        self.assertEqual(span.status.description, 'OPERATION_FAILED')
        self.assertNotIn('SECRET', str(span.attributes))
        self.assertFalse(span.events)

    def test_child_context_matches_parent(self):
        with obs.observation('python.parent') as span:
            carrier = obs.child_environment()
            self.assertIn(f'{span.get_span_context().trace_id:032x}', carrier['QA_TRACEPARENT'])

    def test_langchain_callback_keeps_structure_without_inputs_or_outputs(self):
        from uuid import uuid4
        handler = obs.callbacks()[0]
        run_id = uuid4()
        handler.on_chain_start({}, {'secret': 'SECRET'}, run_id=run_id, name='test-chain')
        handler.on_chain_end({'secret': 'SECRET'}, run_id=run_id)
        span = self.exporter.get_finished_spans()[-1]
        self.assertEqual(span.name, 'langchain.test-chain')
        self.assertNotIn('SECRET', str(span.attributes))
        self.assertNotIn(run_id, handler.spans)

    def test_disabled_observation_does_not_change_result(self):
        with patch.object(obs, 'client', return_value=None):
            @obs.traced('disabled')
            def operation():
                return 42
            self.assertEqual(operation(), 42)

    def test_failed_business_result_is_not_marked_successful(self):
        with obs.observation('python.failed-process') as span:
            span.set_attributes({'qa.success': False, 'qa.exit_code': 1})
        recorded = self.exporter.get_finished_spans()[-1]
        self.assertEqual(recorded.status.description, 'TASK_UNSUCCESSFUL')
