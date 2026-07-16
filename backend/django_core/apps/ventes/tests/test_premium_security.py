"""Security/robustness tests for the premium quote engine fixes.

ERR17 — concurrent renders must not interleave (module-global state is now
        serialized behind a process-level lock).
ERR37 — user-controlled text (client fields, line designations/marque/...) is
        HTML-escaped before it reaches the PDF HTML.
ERR76 — a user-supplied custom acompte can never produce a negative "Matériel"
        amount or an acompte over 100 %.
"""
import re
import tempfile
import threading

from django.test import TransactionTestCase

from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)


# WOW15 — TransactionTestCase (et non TestCase) : test_err17 lance un vrai
# threading.Thread ; sous TestCase, le thread reçoit sa PROPRE connexion DB
# (thread-local) HORS de la transaction atomique du test → il ne voit pas les
# données non commitées et peut interbloquer/échouer. TransactionTestCase
# commite les données, donc le thread les voit. Prérequis pour `--parallel`.
class TestPremiumEngineSecurity(TransactionTestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _data(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
            ('Batterie 5 kWh', '1', '14000'),
        ])
        return build_quote_data(devis)

    def _capture_html(self, data):
        """Render and capture the generated HTML without touching WeasyPrint."""
        from apps.ventes.quote_engine import generate_devis_premium as G
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_premium_sec_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    # ── ERR37 ───────────────────────────────────────────────────────────────
    def test_err37_client_fields_html_escaped(self):
        data = self._data()
        data['client_name'] = '<script>alert(1)</script>'
        data['client_addr'] = 'A & B "Co" <x>'
        html = self._capture_html(data)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('A & B "Co" <x>', html)
        self.assertIn('&lt;x&gt;', html)

    def test_err37_line_designation_escaped(self):
        data = self._data()
        for it in (data.get('sans_items', []) + data.get('avec_items', [])):
            it['designation'] = '<img src=x onerror=alert(1)>'
        html = self._capture_html(data)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)

    # ── ERR76 ───────────────────────────────────────────────────────────────
    def test_err76_custom_acompte_clamped(self):
        data = self._data()
        data['devis_final'] = True
        data['payment_mode'] = 'custom'
        data['custom_acompte'] = 10 ** 9  # absurdly large
        html = self._capture_html(data)
        idx = html.find('Modalit')  # "Modalités de paiement"
        self.assertGreater(idx, -1, 'payment section must be present')
        block = html[idx:idx + 1600]
        pcts = [int(m) for m in re.findall(r'>(\d+)%<', block)]
        self.assertTrue(pcts, 'expected percentage boxes in the payment section')
        for p in pcts:
            self.assertGreaterEqual(p, 0)
            self.assertLessEqual(p, 100)

    # ── ERR17 ───────────────────────────────────────────────────────────────
    def test_err17_render_lock_blocks_concurrent_render(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        self.assertTrue(hasattr(G, '_RENDER_LOCK'))

        started = threading.Event()
        release = threading.Event()
        other_acquired = []

        orig = G._render_premium_pdf

        def slow(data, out):
            started.set()
            release.wait(3)
            return str(out)  # skip the real render — only hold the lock

        G._render_premium_pdf = slow
        out_path = tempfile.NamedTemporaryFile(
            suffix='.pdf', delete=False).name  # WOW15 — chemin unique (pas de /tmp fixe partagé entre workers --parallel)
        try:
            data = self._data()
            t = threading.Thread(
                target=lambda: G.generate_premium_pdf(data, out_path))
            t.start()
            self.assertTrue(started.wait(3), 'render thread did not start')
            # The render thread holds _RENDER_LOCK; this (different) thread must
            # not be able to acquire it while a render is in progress.
            got = G._RENDER_LOCK.acquire(blocking=False)
            other_acquired.append(got)
            if got:
                G._RENDER_LOCK.release()
            release.set()
            t.join(5)
        finally:
            G._render_premium_pdf = orig
            release.set()
        self.assertFalse(
            other_acquired[0],
            'a second thread must not acquire _RENDER_LOCK during a render',
        )
