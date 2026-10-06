"""CIQ311 — bloc « Conditions » des PDF C&I : CGV gelées à l'envoi, note de
TVA et « Bon pour accord » éditable, lus par la même voie que le legacy.

Comportemental, SANS mock de la source : les clauses sont figées par
``figer_clauses_devis`` (envoi réel), les CGV de la société modifiées
ensuite, puis le document C&I est rendu par le VRAI chemin (``build_quote_data``
→ ``echapper_textes_client`` → ``_augment`` → ``build_html``).
"""
from django.test import TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Panneau mono 450W', '40', '1500'),
    ('Onduleur réseau 20 kW', '1', '30000'),
]

PUCES_ENVOI = ['Puce gelée à l\'envoi : réserve de propriété.',
               'Acompte à la commande : {acompte}&#37;']
PUCES_APRES = ['Puce MODIFIÉE après l\'envoi.']


def _module(mode):
    if mode == 'commercial':
        from apps.ventes.quote_engine.commercial import render, renderer
    else:
        from apps.ventes.quote_engine.industriel import render, renderer
    return render, renderer


class ConditionsCi(TestCase):
    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.modele = DocumentTemplates.get(company=self.company)

    def _devis(self, mode, ref):
        devis = make_devis(self.company, self.user, self.client_obj, LIGNES,
                           reference=ref)
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def _rendu(self, devis, mode):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client,
        )
        render, renderer = _module(mode)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        d = renderer._augment(echapper_textes_client(data))
        return d, render.build_html(d)

    def test_cgv_gelees_a_l_envoi_imprimees(self):
        from apps.ventes.domain.envoi import figer_clauses_devis
        self.modele.cgv_bullets = PUCES_ENVOI
        self.modele.save()
        for i, mode in enumerate(('commercial', 'industriel')):
            with self.subTest(mode=mode):
                devis = self._devis(mode, f'DEV-CIQ311-{i * 10 + 10:04d}')
                figer_clauses_devis(devis)
                devis.refresh_from_db()
                self.modele.cgv_bullets = PUCES_APRES
                self.modele.save()
                _d, html = self._rendu(devis, mode)
                self.assertIn('Puce gelée à l', html)
                self.assertIn('réserve de propriété', html)
                self.assertNotIn('Puce MODIFIÉE', html)
                self.assertNotIn('{acompte}', html)
                self.modele.cgv_bullets = PUCES_ENVOI
                self.modele.save()

    def test_variante_ci_prioritaire(self):
        from apps.ventes.domain.envoi import figer_clauses_devis
        self.modele.cgv_par_mode = {'industriel': {
            'titre': 'CG industriel',
            'bullets': ['Réception et réserves sous 8 jours.']}}
        self.modele.cgv_bullets = PUCES_ENVOI
        self.modele.save()
        devis = self._devis('industriel', 'DEV-CIQ311-0100')
        figer_clauses_devis(devis)
        devis.refresh_from_db()
        _d, html = self._rendu(devis, 'industriel')
        self.assertIn('Réception et réserves sous 8 jours.', html)
        self.assertNotIn('Puce gelée à l', html)

    def test_textes_bpa_edites_imprimes(self):
        self.modele.bpa_titre = 'Accord de la société'
        self.modele.bpa_mention = 'Cachet, signature et mention manuscrite'
        self.modele.save()
        for i, mode in enumerate(('commercial', 'industriel')):
            with self.subTest(mode=mode):
                devis = self._devis(mode, f'DEV-CIQ311-{i * 10 + 200:04d}')
                _d, html = self._rendu(devis, mode)
                self.assertIn('Accord de la société — Client', html)
                self.assertIn('Cachet, signature et mention manuscrite',
                              html)

    def test_rien_d_edite_libelles_par_defaut(self):
        from apps.ventes.quote_engine.generate_devis_premium import (
            DEFAULT_DOC_TEXTS,
        )
        for i, mode in enumerate(('commercial', 'industriel')):
            with self.subTest(mode=mode):
                devis = self._devis(mode, f'DEV-CIQ311-{i * 10 + 300:04d}')
                d, html = self._rendu(devis, mode)
                self.assertIn(f"{DEFAULT_DOC_TEXTS['bpa_titre']} — Client",
                              html)
                self.assertIn(DEFAULT_DOC_TEXTS['bpa_mention'], html)
                self.assertIn('Conditions générales du devis', html)
                # La note de TVA multi-taux du builder est imprimée.
                self.assertIn(d['tva_note'], html)

    @tag('weasyprint')
    def test_pages_tenues_et_rien_de_coupe(self):
        try:
            import fitz
            from weasyprint import HTML
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest('weasyprint / PyMuPDF indisponible')
        from apps.ventes.domain.envoi import figer_clauses_devis
        self.modele.cgv_bullets = [
            f'Clause n° {n} : texte de conditions générales assez long '
            'pour occuper une ligne entière du bloc.' for n in range(1, 9)]
        self.modele.save()
        for i, (mode, pages) in enumerate((('commercial', 3),
                                           ('industriel', 4))):
            with self.subTest(mode=mode):
                devis = self._devis(mode, f'DEV-CIQ311-{i * 10 + 400:04d}')
                figer_clauses_devis(devis)
                devis.refresh_from_db()
                _d, html = self._rendu(devis, mode)
                pdf = HTML(string=html).write_pdf()
                doc = fitz.open(stream=pdf, filetype='pdf')
                self.assertEqual(len(doc), pages)
                derniere = doc[len(doc) - 1]
                pied = derniere.rect.height * (1 - 13.0 / 297.0)
                blocs = [b for b in derniere.get_text('blocks')
                         if 'Clause n° 8' in b[4] or 'RC 691213' in b[4]]
                self.assertTrue(blocs)
                for b in blocs:
                    self.assertLess(b[3], pied, b[4][:60])
