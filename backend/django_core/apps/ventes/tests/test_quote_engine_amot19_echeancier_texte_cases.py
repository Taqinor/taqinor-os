"""AMOT19 (C-AMOT-017) — le TEXTE des conditions de paiement (ligne
« Paiement », puces CGV, ligne Conditions du une-page, page publique) vient de
``montants_tranches`` de la branche imprimée — la même source que les cases :
somme = 100 %, aucun créneau absent ni à 0 % imprimé.

Rejoue VA p3 (cases 50/0/50, texte « 60% à la réception du matériel ») et
VC s3 (« 45% à la commande · 60% à la réception du matériel · 55% à la mise
en service »). Les 3 tranches par défaut (30/60/10) sont inchangées.

Test-du-test : réintroduire ``pay.get("materiel", 60)`` dans ``trust.py`` ⇒
``test_trust_deux_tranches`` rouge (160 %).
"""
import re

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.builder import (
    repartition_paiement, termes_paiement_imprimes)
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data


def _data(termes, scenario='Sans batterie', total=50000.0):
    rep = repartition_paiement(total, termes)
    return {'scenario': scenario, 'recommended': scenario,
            'payment_terms': dict(termes),
            'montants_tranches': {'sans': rep, 'avec': rep}}


def _pcts(texte):
    return [int(x) for x in re.findall(r'(\d+)\s*(?:%|&#37;)', texte)]


CAS = {
    'deux_typees_45_55': ({'acompte': 45, 'solde': 55}, [45, 55]),
    'deux_typees_50_50': ({'acompte': 50, 'solde': 50}, [50, 50]),
    'positionnel_45_45_10': ({'acompte': 45, 'materiel': 45, 'solde': 10},
                             [45, 45, 10]),
    'defaut_30_60_10': ({'acompte': 30, 'materiel': 60, 'solde': 10},
                        [30, 60, 10]),
}


class EcheancierTexteCasesTests(SimpleTestCase):
    def test_termes_imprimes_egaux_aux_cases(self):
        for nom, (termes, attendu) in CAS.items():
            with self.subTest(nom):
                imp = termes_paiement_imprimes(_data(termes))
                self.assertEqual(sum(v for v in imp.values()), 100)
                self.assertEqual(list(imp.values()), attendu)
                if len(attendu) == 2:
                    self.assertNotIn('materiel', imp)

    def test_cgv_puces_sans_creneau_absent(self):
        for nom, (termes, attendu) in CAS.items():
            with self.subTest(nom):
                data = _data(termes)
                data['termes_paiement_imprimes'] = termes_paiement_imprimes(data)
                puces = G.cgv_bullets_remplies(data)
                pcts = [p for b in puces for p in _pcts(b)
                        if 'TVA' not in b and 'Tarifs' not in b]
                self.assertEqual(pcts, attendu)
                if len(attendu) == 2:
                    self.assertFalse(any('mat&#233;riel' in b or 'matériel' in b
                                         for b in puces))

    def test_trust_deux_tranches(self):
        data = _residential_sample_data()
        data.update(_data({'acompte': 45, 'solde': 55},
                          scenario=data.get('scenario') or 'Avec batterie'))
        data['termes_paiement_imprimes'] = termes_paiement_imprimes(data)
        html = render.build_html(renderer._augment(data))
        self.assertIn('45% à la commande', html)
        self.assertIn('55% à la mise en service', html)
        self.assertNotIn('à la réception du matériel', html)

    def test_trust_sans_cle_repli_d_hier(self):
        data = _residential_sample_data()
        html = render.build_html(renderer._augment(data))
        self.assertIn('30% à la commande', html)
        self.assertIn('60% à la réception du matériel', html)


class EcheancierTexteCasesBuilderTests(TestCase):
    """Le builder pose la clé (règles corrigées) ; un devis aux règles
    d'origine n'en porte pas."""

    def test_cle_posee_et_absente_aux_regles_d_origine(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        company = make_company()
        devis = make_devis(company, make_user(company), make_client(company), [
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000')],
            reference='DEV-AMOT19-0001')
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(sum(data['termes_paiement_imprimes'].values()), 100)
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertNotIn('termes_paiement_imprimes', data)
