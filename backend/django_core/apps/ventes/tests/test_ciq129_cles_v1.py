"""CIQ129 (D-CIQ-21) — les clés ÉCRAN C&I v1 et les réponses de catégorie à
plat QUITTENT le schéma d'``etude_params``.

CE QUE CES TESTS TIENNENT :

1. aucune des clés retirées n'est encore déclarée au schéma ; chacune reçue
   ⇒ un reproche FR qui la NOMME (``valider``), donc un 400 à l'endpoint de
   fusion, sans écriture ;
2. le contrat v2 garde les réponses : ``rythme.reponses_categorie`` passe ;
3. le rendu ne lit plus aucune clé retirée : l'étude rendue les écarte, le
   bloc de catégorie lit les réponses v2, la mention 82-21 lit la revente du
   moteur C&I, le ``mode_kpis`` C&I est la projection de ``synthese_ci`` ;
4. une copie/V2 ne reprend pas ces clés d'un ancien devis.

Aucune reprise de données, aucun essai à blanc (D-CIQ-21).
"""
import json
from pathlib import Path

from django.test import SimpleTestCase
from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain import etude_schema as S
from apps.ventes.domain.etudes import etude_params_pour_copie
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

#: Les sept clés v1 de l'étude ÉCRAN (QJR510/QJR528/QJR578).
CLES_V1 = ('taux_autoconso', 'taux_couverture', 'payback', 'injection_kwh_an',
           'injection_dh_an', 'etude_kwc_base', 'part_diurne_pct')
#: Les réponses de catégorie à plat (QX44, ``COMMERCIAL_CATEGORY_QUESTIONS``).
REPONSES_A_PLAT = (
    'chambres', 'occupation_pct', 'piscine', 'chambres_froides', 'horaires',
    'cuisson', 'surface_vente_m2', 'effectif', 'clim', 'lits', 'garde_nuit',
    'internat', 'fermeture_estivale', 'surface_m2', 'chauffe', 'four',
    'cuisson_nocturne', 'temperature_consigne', 'volume_m3',
    'saisonnalite_recolte')
CONTRAT_CI = (Path(__file__).resolve().parents[1] / 'contract_samples'
              / 'etude_ci_preview.json')


class SchemaSansClesV1Tests(SimpleTestCase):

    def test_aucune_cle_retiree_n_est_declaree(self):
        for cle in CLES_V1 + REPONSES_A_PLAT:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, S.SCHEMA)
                self.assertIn(cle, S.CLES_RETIREES_CI_V1)

    def test_la_liste_des_retirees_couvre_exactement_ces_cles(self):
        self.assertEqual(set(S.CLES_RETIREES_CI_V1),
                         set(CLES_V1 + REPONSES_A_PLAT))

    def test_le_contrat_v2_les_liste_a_retirer(self):
        contrat = json.loads(CONTRAT_CI.read_text(encoding='utf-8'))
        a_retirer = contrat['cles_etude_params_ci_v2']['a_retirer_v1']
        for cle in CLES_V1:
            with self.subTest(cle=cle):
                self.assertIn(cle, a_retirer)

    def test_chaque_cle_recue_est_nommee_en_francais(self):
        for cle in CLES_V1 + REPONSES_A_PLAT:
            with self.subTest(cle=cle):
                reproches = S.valider({cle: 1})
                self.assertEqual(len(reproches), 1, reproches)
                self.assertIn('« %s »' % cle, reproches[0])
                self.assertIn('Clé retirée', reproches[0])

    def test_la_fusion_refuse_et_ne_touche_rien(self):
        depart = {'scenario': 'Sans batterie'}
        with self.assertRaises(ValueError) as ctx:
            S.fusionner(depart, proprietaire=S.ECRAN, payback=3.4)
        self.assertIn('payback', str(ctx.exception))
        self.assertEqual(depart, {'scenario': 'Sans batterie'})

    def test_les_reponses_v2_passent(self):
        self.assertEqual(S.valider({
            'categorie_commerciale': 'boulangerie',
            'rythme': {'categorie_commerciale': 'boulangerie',
                       'reponses_categorie': {
                           'four': 'electrique', 'cuisson_nocturne': True,
                           'heures_cuisson': [[2, 6]]}},
        }), [])

    def test_une_copie_ne_reprend_pas_les_cles_retirees(self):
        bloc = etude_params_pour_copie({
            'scenario': 'Sans batterie', 'payback': 3.1, 'chambres': 40,
            'part_diurne_pct': 70})
        self.assertEqual(bloc, {'scenario': 'Sans batterie'})


class RenduSansClesV1Tests(SimpleTestCase):
    """Le rendu lit la source v2 — jamais la clé retirée."""

    def test_l_etude_rendue_ecarte_les_cles_retirees(self):
        from apps.ventes.quote_engine.builder import _etude_rendue
        stocke = {'conso_annuelle': 120000, 'payback': 3.0,
                  'taux_autoconso': 62, 'chambres': 40}
        self.assertEqual(_etude_rendue(stocke), {'conso_annuelle': 120000})
        self.assertIn('payback', stocke)  # le bloc stocké n'est jamais muté

    def test_le_bloc_de_categorie_lit_les_reponses_v2(self):
        from apps.ventes.quote_engine.ci.categories import (
            categorie_ci, texte_ligne)
        data = {'mode_installation': 'commercial', 'etude': {
            'categorie_commerciale': 'hotel',
            'rythme': {'reponses_categorie': {'chambres': 48}}}}
        textes = [texte_ligne(li) for li in
                  categorie_ci(data)['bloc']['lignes']]
        self.assertTrue(any('48' in t for t in textes), textes)

    def test_une_reponse_a_plat_n_est_plus_lue(self):
        from apps.ventes.quote_engine.ci.categories import (
            categorie_ci, texte_ligne)
        data = {'mode_installation': 'commercial', 'etude': {
            'categorie_commerciale': 'hotel', 'chambres': 48}}
        textes = [texte_ligne(li) for li in
                  categorie_ci(data)['bloc']['lignes']]
        self.assertFalse(any('48' in t for t in textes), textes)

    def test_la_mention_82_21_lit_la_revente_du_moteur(self):
        from apps.ventes.quote_engine.ci.mentions import mentions_ci
        base = {'mode_installation': 'industriel',
                'etude': {'tension_raccordement': 'MT',
                          'injection_dh_an': 9800}}
        cles = [m['cle'] for m in mentions_ci(base)]
        self.assertNotIn('revente', cles)
        base['economie_ci'] = {'revente': {'statut': 'omise',
                                           'valeur_mad_an': 9800}}
        cles = [m['cle'] for m in mentions_ci(base)]
        self.assertIn('revente', cles)

    def test_mode_kpis_ci_est_la_projection_de_la_synthese(self):
        from apps.ventes.public.payload_economie import _mode_kpis
        k = _mode_kpis({'mode_installation': 'industriel', 'etude': {
            'taux_autoconso': 74, 'taux_couverture': 52, 'payback': 3.6,
            'injection_kwh_an': 1200, 'injection_dh_an': 900}})
        self.assertEqual(set(k.values()), {None})


class EndpointEtudeParamsCiq129Tests(APITestCase):
    """Le refus tel que le navigateur le reçoit : 400 FR nommant la clé,
    aucune écriture."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company),
            [('Panneau Jinko 580W', '20', '1000')],
            reference='DEV-CIQ129-0010')
        self.devis.mode_installation = 'commercial'
        self.devis.save(update_fields=['mode_installation'])
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.url = ('/api/django/ventes/devis/%s/etude-params/'
                    % self.devis.id)

    def test_payback_part_diurne_cuisson_nocturne_refusees(self):
        for corps in ({'payback': 3.4}, {'part_diurne_pct': 70},
                      {'cuisson_nocturne': True}):
            cle = next(iter(corps))
            with self.subTest(cle=cle):
                resp = self.api.patch(self.url, corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertIn(cle, str(resp.data['detail']))
                self.devis.refresh_from_db()
                self.assertNotIn(cle, self.devis.etude_params or {})

    def test_les_reponses_v2_sont_acceptees(self):
        resp = self.api.patch(self.url, {'rythme': {
            'categorie_commerciale': 'boulangerie',
            'reponses_categorie': {'cuisson_nocturne': True}}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.devis.refresh_from_db()
        self.assertTrue(self.devis.etude_params['rythme']
                        ['reponses_categorie']['cuisson_nocturne'])
