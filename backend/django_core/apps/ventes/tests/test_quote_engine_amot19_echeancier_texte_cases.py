"""AMOT19 (C-AMOT-017, volet rendu) — les conditions de paiement IMPRIMÉES
(ligne « Paiement » du résidentiel, puces CGV, ligne Conditions du une-page,
conditions de la page publique) viennent des CASES de la branche imprimée
(``montants_tranches``) : somme = 100 %, aucun créneau absent ni à 0 %
imprimé ; le cas 3 tranches par défaut est inchangé.

Moteur réel (``build_quote_data``), rendus réels (résidentiel, legacy une-page),
page publique réelle (``_conditions_publiques``). APDF13 — le résidentiel et
le une-page impriment les puces CGV (``cgv_imprimees``) : la ligne
« Paiement » composée en dur a disparu. Test-du-test : retirer l'omission du
créneau nul de ``remplir_cgv_bullets`` ⇒ ``test_deux_tranches_typees`` échoue.

AMET25 (C-AMET-003, D-ECH-FIGE) — ``EcheancierFigePdfTests`` : le PDF d'un
devis ACCEPTÉ imprime l'échéancier FIGÉ à l'acceptation (``figer_echeancier``,
AMET1), jamais les réglages société changés depuis ; un brouillon les suit.
"""
import html as _html
import re
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.public.payload_conditions import _conditions_publiques
from apps.ventes.quote_engine import generate_devis_premium as legacy
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.clauses_cgv import cgv_bullets_remplies
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
        self.assertIn(f'Acompte à la commande : {acompte}%', res)
        self.assertIn(f'{solde}% après la mise en marche', res)
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
        self.assertIn(f"Acompte à la commande : {cases['pct_a']}%", res)

    def test_mixte_quatre_jalons_pct_derives_des_montants(self):
        """AGNR52 (C-AGNR-VER-006) — échéancier mixte hors règle (6 000 MAD
        + 40/20/10 % sur 17 000 TTC) : au niveau d'AGNR54, la puce CGV, le
        marqueur ``{echeancier}`` et la page publique impriment les % du bloc
        C&I (dernier au reliquat) à côté des montants servis (Σ = TTC) ; les
        4 jalons reçoivent leurs branches en MAD ; niveau 7 : le texte d'hier.
        Mutant : relire le % déclaré dans ``puce_echeancier_ci`` ⇒ échec."""
        from apps.ventes.quote_engine import builder
        from apps.ventes.quote_engine.ci.synthese import _echeancier as bloc_ci
        from apps.ventes.quote_engine.clauses_cgv import _pct_txt, cgv_imprimees
        from apps.ventes.domain.regles_calcul import (
            REGLES_CONSO_PUBLIQUE_0111 as REGLES_ECHEANCIER_DERIVE)
        from apps.ventes.quote_engine.montants import fmt_centimes
        corps = [
            {'libelle': 'Commande', 'type': 'acompte', 'unite': 'montant', 'pct_or_montant': 6000},
            {'libelle': 'Livraison', 'jalon': 'livraison_materiel', 'unite': 'pct', 'pct_or_montant': 40},
            {'libelle': 'MES', 'jalon': 'mise_en_service', 'unite': 'pct', 'pct_or_montant': 20},
            {'libelle': 'Réception', 'jalon': 'reception_definitive', 'unite': 'pct', 'pct_or_montant': 10}]
        textes = {}
        for niveau in (REGLES_ECHEANCIER_DERIVE, REGLES_ECHEANCIER_DERIVE - 1):
            self.n += 1
            devis = make_devis(self.company, self.user, self.client_obj, [
                ('Panneau mono 550W', '10', '1000', '10'),
                ('Onduleur réseau Huawei 5kW', '1', '5000', '20')],
                reference=f'DEV-AGNR52-{self.n}')
            Devis.objects.filter(pk=devis.pk).update(
                echeancier=corps, mode_installation='industriel', regles_calcul=niveau)
            devis.refresh_from_db()
            data = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
            textes[niveau] = (
                data, ' '.join(_texte(p) for p in cgv_imprimees(data)['puces']),
                builder._marqueurs_cgv_ci(devis, '')['echeancier'],
                _texte(' '.join(_conditions_publiques(data, devis) or [])))
        data, puce, marqueur, publique = textes[REGLES_ECHEANCIER_DERIVE]
        bloc = bloc_ci(data, 'sans')
        self.assertEqual([j['pct'] for j in bloc], [35.29, 40, 20, 4.71])
        self.assertAlmostEqual(sum(j['montant_ttc'] for j in bloc), 17000, places=2)
        for j in bloc:
            morceau = f"{_pct_txt(j['pct'])} % · {fmt_centimes(j['montant_ttc'])} MAD TTC"
            for surface in (puce, marqueur, publique):
                self.assertIn(morceau, surface)
        self.assertNotIn(' 10 % ·', puce + marqueur)
        cases = data['montants_tranches']['sans']
        self.assertEqual(cases['acompte'], 6000.0)
        self.assertAlmostEqual(cases['acompte'] + cases['solde2'], 17000, places=2)
        data7, puce7, marqueur7, _publique7 = textes[REGLES_ECHEANCIER_DERIVE - 1]
        self.assertTrue(data7.get('regles_echeancier_historique'))
        self.assertNotIn('regles_echeancier_historique', data)
        self.assertNotIn('% ·', puce7 + marqueur7)
        self.assertIn('6000 MAD TTC', marqueur7)
        self.assertNotEqual(data7['montants_tranches']['sans']['acompte'], 6000.0)

    def test_agricole_cases_pct_derives_des_montants(self):
        """AGNR52 — cases agricoles d'un [5 000 MAD ; 60 % ; 10 %] sur 20 000
        TTC : 25 / 60 / 15 % à côté de 5 000 / 12 000 / 3 000 MAD (dernier au
        reliquat) ; ``regles_echeancier_historique`` : les % servis d'hier."""
        from apps.ventes.quote_engine.agricole import pages as agr
        from apps.ventes.quote_engine.conditions_commerciales import (
            repartition_paiement)
        termes = {'acompte': 25, 'materiel': 60, 'solde': 10}
        tranches = [{'unite': 'montant', 'valeur': 5000},
                    {'unite': 'pct', 'valeur': 60}, {'unite': 'pct', 'valeur': 10}]
        d = {'payment_terms': termes, 'totaux_all': {'ttc': 20000},
             'montants_tranches': {'sans': repartition_paiement(20000, termes, tranches)}}
        from apps.ventes.quote_engine.montants import fmt_centimes
        cases = _texte(agr._echeancier(d, 'fr'))
        for pct, montant in ((25, 5000), (60, 12000), (15, 3000)):
            self.assertIn(f'{pct} % · {fmt_centimes(montant)} MAD', cases)
        hier = _texte(agr._echeancier(dict(d, regles_echeancier_historique=True), 'fr'))
        self.assertIn(f'10 % · {fmt_centimes(3000)} MAD', hier)

    def test_recommandee_sans_texte_cases_acompte_alignes(self):
        """AMOT122 (C-AMOT-VER4-007, D-AMOT-VER4-1) — deux options résidentiel,
        recommandée « Sans », acompte 10 000 MAD : texte (``payment_terms``),
        cases du Devis final (résidentiel ET legacy) et page publique lisent
        LA branche d'``option_effective`` ; niveau 11 : rien servi (rendu
        d'hier). Mutant : cases par recommandation ⇒ % ≠ texte."""
        from apps.ventes.domain.regles_calcul import REGLES_CENTAINE_0311
        from apps.ventes.public.payload_conditions import _acompte_publique
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
            ('Onduleur hybride Deye 5kW', '1', '15000'),
            ('Batterie Dyness 5kWh', '1', '20000'),
        ], reference=f'DEV-AMOT122-{self.n}', etude_params={
            'scenario': 'Les deux (Sans + Avec)', 'recommended_option': 'Sans batterie'})
        Devis.objects.filter(pk=devis.pk).update(mode_installation='residentiel', echeancier=[
            {'libelle': 'Acompte', 'type': 'montant', 'pct_or_montant': 10000},
            {'libelle': 'Solde', 'pct_or_montant': 50}])
        devis.refresh_from_db()
        opts = clean_pdf_options({'pdf_mode': 'full', 'devis_final': True})
        data = build_quote_data(devis, opts)
        self.assertEqual(data['branche_echeancier'], 'avec')
        cases = data['montants_tranches']['avec']
        pct = cases['pct_a']
        self.assertNotEqual(pct, data['montants_tranches']['sans']['pct_a'])
        self.assertEqual(data['payment_terms']['acompte'], pct)
        res_html = res_render.build_html(res_renderer._augment(dict(data)))
        self.assertEqual(re.findall(r'class="p3-pay-p">([^<]+)<', res_html)[:1], [f'{pct}%'])
        self.assertIn(f'line-height:1.0;">{pct}%</div>', legacy.render_html_for(dict(data)))
        publique = _acompte_publique(devis)
        self.assertEqual(publique['option'], 'avec_batterie')
        self.assertEqual(Decimal(publique['ttc']), Decimal(str(cases['acompte'])))
        Devis.objects.filter(pk=devis.pk).update(regles_calcul=REGLES_CENTAINE_0311)
        devis.refresh_from_db()
        self.assertNotIn('branche_echeancier', build_quote_data(devis, opts))

    def test_trois_tranches_par_defaut_inchangees(self):
        data, res, une_page, cgv, publiques = self._surfaces(self._devis())
        self.assertEqual(data['payment_terms'],
                         {'acompte': 30, 'materiel': 60, 'solde': 10})
        self.assertIn('60% à la réception du matériel', res)
        self.assertIn('réception du matériel', une_page)
        self.assertTrue(any('réception du matériel' in p for p in cgv))


class EcheancierFigePdfTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amet25-co', nom='AMET25')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _reglages(self, acompte, materiel, solde):
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company=self.company)
        profil.payment_terms = {'residentiel': {
            'acompte': acompte, 'materiel': materiel, 'solde': solde}}
        profil.save(update_fields=['payment_terms'])

    def _termes(self, devis):
        return build_quote_data(devis, clean_pdf_options(
            {'pdf_mode': 'full'}))['payment_terms']

    def test_pdf_imprime_l_echeancier_fige_apres_changement_de_reglage(self):
        from apps.ventes.utils.echeancier import (
            figer_echeancier, tranches_normalisees)
        signe = make_devis(self.company, self.user, self.client_obj, _LIGNES,
                           reference='DEV-AMET25-1')
        Devis.objects.filter(pk=signe.pk).update(statut='accepte')
        signe.refresh_from_db()
        self.assertFalse(figer_echeancier(signe)['deja_fige'])
        self._reglages(30, 40, 30)
        signe.refresh_from_db()
        fige = {'acompte': 30, 'materiel': 60, 'solde': 10}
        self.assertEqual(self._termes(signe), fige)
        # PDF = écran : la source unique des tranches dit la même chose.
        self.assertEqual([t['valeur'] for t in tranches_normalisees(signe)],
                         list(fige.values()))
        # Un brouillon (aucun échéancier propre) suit les réglages du jour.
        brouillon = make_devis(self.company, self.user, self.client_obj,
                               _LIGNES, reference='DEV-AMET25-2')
        self.assertEqual(self._termes(brouillon),
                         {'acompte': 30, 'materiel': 40, 'solde': 30})
