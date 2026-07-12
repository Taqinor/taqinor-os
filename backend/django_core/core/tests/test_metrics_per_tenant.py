"""NTPLT44 — métriques HTTP par tenant + compteurs Celery par queue."""
from django.test import SimpleTestCase

from core import metrics


class PerTenantMetricsTests(SimpleTestCase):
    def setUp(self):
        # État process-local isolé par test.
        metrics._http_by_tenant.clear()
        metrics._http_real_companies.clear()
        metrics._task_by_queue.clear()

    def test_http_counter_and_histogram_rendered(self):
        metrics.record_http_request(company_id=7, status=200, duration_ms=120)
        metrics.record_http_request(company_id=7, status=500, duration_ms=3000)
        text = metrics.render_prometheus_text()
        self.assertIn('taqinor_http_requests_total{company="7",status="2xx"} 1',
                      text)
        self.assertIn('taqinor_http_requests_total{company="7",status="5xx"} 1',
                      text)
        self.assertIn('taqinor_http_request_duration_seconds_count'
                      '{company="7"} 2', text)

    def test_cardinality_guard_caps_at_top_n(self):
        # Au-delà du plafond, les sociétés supplémentaires tombent sous `other`.
        for cid in range(metrics._CARDINALITY_CAP + 5):
            metrics.record_http_request(cid, 200, 10)
        labels = set(metrics.http_tenant_metrics().keys())
        real = {label for label in labels if label.isdigit()}
        self.assertLessEqual(len(real), metrics._CARDINALITY_CAP)
        self.assertIn('other', labels)

    def test_none_company_is_system_label(self):
        metrics.record_http_request(None, 200, 5)
        self.assertIn('system', metrics.http_tenant_metrics())

    def test_celery_per_queue_counters(self):
        metrics.record_task_queue('interactive', ok=True)
        metrics.record_task_queue('interactive', ok=False)
        metrics.record_task_queue('bulk', ok=True)
        text = metrics.render_prometheus_text()
        self.assertIn('taqinor_celery_queue_tasks_total'
                      '{queue="interactive",status="success"} 1', text)
        self.assertIn('taqinor_celery_queue_tasks_total'
                      '{queue="interactive",status="failure"} 1', text)
        self.assertIn('taqinor_celery_queue_tasks_total'
                      '{queue="bulk",status="success"} 1', text)
