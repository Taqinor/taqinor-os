"""AMOT19 (C-AMOT-017, volet rendu) — les conditions de paiement IMPRIMÉES
(ligne « Paiement » du résidentiel, puces CGV, ligne Conditions du une-page,
conditions de la page publique) viennent des CASES de la branche imprimée
(``montants_tranches``) : somme = 100 %, aucun créneau absent ni à 0 %
imprimé ; le cas 3 tranches par défaut est inchangé.

Moteur réel (``build_quote_data``), rendus réels (résidentiel, legacy une-page),
page publique réelle (``_conditions_publiques``). Test-du-test : réintroduire
``pay.get("materiel", 60)`` + la ligne inconditionnelle dans ``trust.py`` ⇒
``test_deux_tranches_typees`` échoue (160 %).
"""
import html as _html

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.public.payload_conditions import _conditions_publiques
from apps.ventes.quote_engine import generate_devis_premium as legacy
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.generate_devis_premium import cgv_bullets_remplies
from apps.ventes.quote_engine.residential import render as res_render
from apps.ventes.quote_engine.residential import renderer as res_renderer
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

_LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
]


def _texte(h):
    return _html.unescape(h).replace('\xa0', ' ')


class EcheancierTexteCasesTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot19-co', nom='AMOT19')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, echeancier=None):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, _LIGNES,
                           reference=f'DEV-AMOT19-{self.n}')
        if echeancier is not None:
            Devis.objects.filter(pk=devis.pk).update(echeancier=echeancier)
            devis.refresh_from_db()
        return devis

    def _surfaces(self, devis):
        data = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
        res = _texte(res_render.build_html(res_renderer._augment(dict(data))))
        une_page = _texte(legacy.render_html_for(
            {**build_quote_data(devis, clean_pdf_options(
                {'pdf_mode': 'onepage'})), 'pdf_mode': 'onepage'}))
        cgv = [_texte(p) for p in cgv_bullets_remplies(data)]
        publiques = _conditions_publiques(data, devis) or []
        return data, res, une_page, cgv, publiques

    def _cases(self, data):
        return data['montants_tranches']['sans']

    def _verifier_deux_tranches(self, devis, acompte, solde):
        data, res, une_page, cgv, publiques = self._surfaces(devis)
        cases = self._cases(data)
        self.assertTrue(cases['deux_cases'])
        self.assertEqual(data['payment_terms'],
                         {'acompte': acompte, 'materiel': 0, 'solde': solde})
        self.assertEqual(acompte + solde, 100)
        self.assertIn(f'{acompte}% à la commande', res)
        self.assertIn(f'{solde}% à la mise en service', res)
        self.assertNotIn('à la réception du matériel', res)
        self.assertNotIn('réception du matériel', une_page)
        for puce in cgv + publiques:
            self.assertNotIn('réception du matériel', puce)
        self.assertTrue(any(f'{acompte}%' in p for p in cgv))
        self.assertEqual([p.strip() for p in cgv],
                         [p.replace(' ', ' ').strip() for p in publiques])

    def test_deux_tranches_typees(self):
        self._verifier_deux_tranches(self._devis([
            {'libelle': 'Commande', 'type': 'acompte', 'pct_or_montant': 45},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 55},
        ]), 45, 55)

    def test_cinquante_cinquante(self):
        self._verifier_deux_tranches(self._devis([
            {'libelle': 'Commande', 'type': 'acompte', 'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 50},
        ]), 50, 50)

    def test_non_typees_texte_egal_cases(self):
        data, res, une_page, cgv, publiques = self._surfaces(self._devis([
            {'libelle': 'Tranche 1', 'pct_or_montant': 45},
            {'libelle': 'Tranche 2', 'pct_or_montant': 55},
        ]))
        cases = self._cases(data)
        termes = data['payment_terms']
        self.assertEqual(termes['acompte'], cases['pct_a'])
        self.assertEqual(sum(float(v) for v in termes.values()), 100)
        self.assertIn(f"{cases['pct_a']}% à la commande", res)

    def test_trois_tranches_par_defaut_inchangees(self):
        data, res, une_page, cgv, publiques = self._surfaces(self._devis())
        self.assertEqual(data['payment_terms'],
                         {'acompte': 30, 'materiel': 60, 'solde': 10})
        self.assertIn('60% à la réception du matériel', res)
        self.assertIn('réception du matériel', une_page)
        self.assertTrue(any('réception du matériel' in p for p in cgv))
