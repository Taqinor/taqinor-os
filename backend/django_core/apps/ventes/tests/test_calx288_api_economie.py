"""CALX288 — ``GET /api/django/ventes/devis/<pk>/economie/`` en lecture seule.

La forme attendue n'est PAS retapée ici : elle est LUE dans le document
partagé ``apps/ventes/contract_samples/ventes_economie.json`` (CALX280), le
même que le test d'écran de l'onglet « Économie » (CALX289) importera.

Ce qui est prouvé (le « Done » de CALX288) :

* un devis d'une AUTRE société est INTROUVABLE (404, jamais 403) ;
* la réponse valide l'exemple committé (mêmes clés, mêmes formes d'entrées)
  — sans réglage société comme avec (``exemple_vide`` / ``exemple``) ;
* sur le cas de référence, ``economie_pour_devis`` REJOUE l'exemple committé
  (flux, VAN, TRI, LCOE, retours) ;
* aucune clé de la réponse ne contient ``prix``, ``cout`` ni ``marge``, et le
  détecteur de la garde ``apps/calepinage/tests/test_aucun_prix_achat.py``
  ne trouve rien ;
* sans réglage société, rien n'est inventé : flux vide, horizon et taux
  d'actualisation OMIS avec leur motif ;
* un moteur de devis en échec s'OMET (200 + motif ``devis``), jamais un 500 ;
* la route est en LECTURE SEULE (POST refusé) et exige une authentification.

Test ORM — non exécuté localement dans la lane (pas de base), la CI le valide.

Run :
    python manage.py test apps.ventes.tests.test_calx288_api_economie -v2
"""
import json
from pathlib import Path
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.calepinage.tests.test_aucun_prix_achat import cles_interdites
from apps.ventes.economie import economie_pour_devis
from testkit.factories import CompanyFactory, DevisFactory, UserFactory

#: Le document PARTAGÉ (PACT10) — jamais une charge utile retapée ici.
CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'ventes_economie.json')

#: Ce que le moteur de devis rend sur le CAS DE RÉFÉRENCE de l'exemple.
DONNEES_REFERENCE = {
    'scenario': 'Sans batterie',
    'totaux_sans': {'ttc': 100000.0},
    'totaux_avec': {'ttc': 130000.0},
    'eco_s_ann': 12000,
    'eco_a_ann': 15000,
    'prod_kwh': 10000,
    'savings_estimated': False,
}

#: Les réglages société du cas de référence (horizon 10 ans, taux nuls).
REGLAGES_REFERENCE = {
    cle: {'valeur': valeur,
          'source': 'réglage société — Paramètres › Tarification & ROI',
          'saisie_le': '2026-09-23'}
    for cle, valeur in (('horizon_ans', 10), ('taux_actualisation_pct', 0),
                        ('indexation_pct', 0), ('degradation_pct', 0))
}

CONSTRUCTEUR = 'apps.ventes.quote_engine.builder.build_quote_data'


def document():
    return json.loads(CONTRAT.read_text(encoding='utf-8'))


def toutes_les_cles(noeud):
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield str(cle)
            yield from toutes_les_cles(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from toutes_les_cles(valeur)


class _Base(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company,
                                role_legacy='responsable')
        self.devis = DevisFactory(company=self.company,
                                  reference='DEV-CALX288-0001',
                                  created_by=self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def url(self, devis=None):
        return f'/api/django/ventes/devis/{(devis or self.devis).pk}/economie/'

    def assert_forme_du_contrat(self, bloc, variante='exemple'):
        exemple = document()[variante]
        self.assertEqual(set(bloc), set(exemple))
        self.assertIsInstance(bloc['flux'], list)
        self.assertIsInstance(bloc['hypotheses'], list)
        self.assertIsInstance(bloc['omissions'], list)
        modele = document()['exemple']
        for ligne in bloc['flux']:
            self.assertEqual(set(ligne), set(modele['flux'][0]))
        for hypothese in bloc['hypotheses']:
            self.assertEqual(set(hypothese), set(modele['hypotheses'][0]))
            self.assertTrue(str(hypothese['source']).strip())
        for omission in bloc['omissions']:
            self.assertEqual(set(omission), set(modele['omissions'][0]))


class IsolationTest(_Base):
    def test_devis_d_une_autre_societe_introuvable_404(self):
        autre = DevisFactory(company=CompanyFactory(),
                             reference='DEV-CALX288-AUTRE')
        reponse = self.api.get(self.url(autre))
        self.assertEqual(reponse.status_code, 404)

    def test_le_service_ne_sert_que_la_societe_du_devis(self):
        autre_societe = CompanyFactory()
        with self.assertRaises(self.devis.__class__.DoesNotExist):
            economie_pour_devis(self.devis.pk, autre_societe, reglages={})

    def test_anonyme_refuse(self):
        reponse = APIClient().get(self.url())
        self.assertIn(reponse.status_code, (401, 403))

    def test_lecture_seule(self):
        # POST n'est pas routé sur l'action : DRF vérifie les permissions
        # AVANT de répondre 405 (``get_permissions`` sans action déclarée
        # retombe sur ``IsAdminRole``) — 403 pour un responsable, 405 pour un
        # administrateur ; jamais une écriture.
        reponse = self.api.post(self.url(), {}, format='json')
        self.assertIn(reponse.status_code, (403, 405))


class ContratTest(_Base):
    def test_la_reponse_valide_l_exemple_committe(self):
        with mock.patch(CONSTRUCTEUR, return_value=DONNEES_REFERENCE):
            reponse = self.api.get(self.url())
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assert_forme_du_contrat(reponse.data, 'exemple_vide')

    def test_sans_reglage_societe_rien_n_est_invente(self):
        with mock.patch(CONSTRUCTEUR, return_value=DONNEES_REFERENCE):
            bloc = self.api.get(self.url()).data
        self.assertIsNone(bloc['horizon_ans'])
        self.assertEqual(bloc['flux'], [])
        self.assertIsNone(bloc['van_mad'])
        omises = {o['cle'] for o in bloc['omissions']}
        self.assertIn('horizon_ans', omises)
        self.assertIn('taux_actualisation_pct', omises)
        retenues = {h['cle']: h for h in bloc['hypotheses']}
        self.assertEqual(retenues['investissement_mad']['valeur'], 100000.0)
        self.assertIn('DEV-CALX288-0001',
                      retenues['investissement_mad']['source'])
        self.assertEqual(retenues['option_devis']['valeur'], 'sans')

    def test_le_cas_de_reference_rejoue_l_exemple_committe(self):
        exemple = document()['exemple']
        with mock.patch(CONSTRUCTEUR, return_value=DONNEES_REFERENCE):
            bloc = economie_pour_devis(self.devis.pk, self.company,
                                       reglages=REGLAGES_REFERENCE)
        self.assert_forme_du_contrat(bloc)
        self.assertEqual(bloc['flux'], exemple['flux'])
        for cle in ('horizon_ans', 'van_mad', 'tri_pct', 'lcoe_mad_kwh',
                    'retour_ans', 'retour_actualise_ans'):
            self.assertEqual(bloc[cle], exemple[cle], cle)
        self.assertEqual([h['cle'] for h in bloc['hypotheses']],
                         [h['cle'] for h in exemple['hypotheses']])
        self.assertEqual([o['cle'] for o in bloc['omissions']],
                         [o['cle'] for o in exemple['omissions']])

    def test_l_option_avec_batterie_quand_le_devis_la_retient(self):
        donnees = dict(DONNEES_REFERENCE, scenario='Avec batterie')
        with mock.patch(CONSTRUCTEUR, return_value=donnees):
            bloc = economie_pour_devis(self.devis.pk, self.company,
                                       reglages=REGLAGES_REFERENCE)
        retenues = {h['cle']: h['valeur'] for h in bloc['hypotheses']}
        self.assertEqual(retenues['option_devis'], 'avec')
        self.assertEqual(retenues['investissement_mad'], 130000.0)
        self.assertEqual(retenues['economie_annee1_mad'], 15000.0)

    def test_moteur_en_echec_omission_jamais_500(self):
        with mock.patch(CONSTRUCTEUR, side_effect=RuntimeError('illisible')):
            reponse = self.api.get(self.url())
        self.assertEqual(reponse.status_code, 200)
        self.assert_forme_du_contrat(reponse.data, 'exemple_vide')
        self.assertIn('devis', {o['cle'] for o in reponse.data['omissions']})
        self.assertEqual(reponse.data['flux'], [])

    def test_reponse_reelle_sans_patch_a_la_forme_du_contrat(self):
        """Le vrai moteur de devis sur un devis vide : la forme tient."""
        reponse = self.api.get(self.url())
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assert_forme_du_contrat(reponse.data, 'exemple_vide')


class VocabulaireTest(_Base):
    def test_aucune_cle_prix_cout_marge(self):
        with mock.patch(CONSTRUCTEUR, return_value=DONNEES_REFERENCE):
            bloc = economie_pour_devis(self.devis.pk, self.company,
                                       reglages=REGLAGES_REFERENCE)
            reponse = self.api.get(self.url())
        for donnees in (bloc, reponse.data):
            for cle in toutes_les_cles(donnees):
                for mot in ('prix', 'cout', 'marge'):
                    self.assertNotIn(mot, cle.lower(), cle)
            # Le détecteur de la garde du calepinage reste muet.
            self.assertEqual(cles_interdites(donnees), [])
