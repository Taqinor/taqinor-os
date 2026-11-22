"""ACAL887 — douze kWh mensuels mesurés et leur écart au P50 servi.

Ce qui est prouvé ici :

* sans base : la réponse EST le contrat committé
  (``contract_samples/calepinage_production_mesuree.json``, ACAL886) — états
  ``exemple`` et ``exemple_vide`` recomposés par le vrai code à partir du P50
  mensuel de ``calepinage_resultat.json`` ; un mois sans mesure vaut ``null``
  (jamais 0) ; non simulé ou périmé ⇒ écart ``null`` avec le motif ; les refus
  (mois en double, hors 1-12, négatif, annee) nomment le champ ;
* en base (CI) : douze mesures collées rendent douze écarts, un mois en double
  ⇒ 400 qui nomme ``mesures[i].mois``, ``company`` du corps ignorée, 404 pour
  une autre société, 403 sans droit.

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_production_mesuree -v2
"""
import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage, ProductionMesuree
from apps.calepinage.services import production_mesuree as service

from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_production_mesuree.json')
    .read_text(encoding='utf-8'))
RESULTAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']

#: Le résultat SERVI frais : le P50 mensuel du contrat du résultat.
SERVI = {'simule': True, 'simulation_perimee': False, 'motif': '',
         'production': {'mensuel': RESULTAT['production']['mensuel']}}


def mesures_du_contrat():
    return [(ligne['mois'], ligne['kwh_mesure'], ligne['saisi_le'])
            for ligne in CONTRAT['exemple']['mesures']]


class ContratCommitteTest(SimpleTestCase):

    def test_exemple(self):
        etat = service._composer_etat(1, 2026, mesures_du_contrat(), SERVI)
        self.assertEqual(etat, CONTRAT['exemple'])

    def test_exemple_vide(self):
        self.assertEqual(service._composer_etat(1, None, [], SERVI),
                         CONTRAT['exemple_vide'])

    def test_douze_mesures_douze_ecarts(self):
        plein = mesures_du_contrat() + [(12, 800.0, '2026-11-21T10:00:00Z')]
        etat = service._composer_etat(1, 2026, plein, SERVI)
        self.assertEqual(len(etat['ecarts']), 12)
        self.assertTrue(all(ligne['ecart_pct'] is not None
                            for ligne in etat['ecarts']))
        self.assertEqual(etat['ecarts'][11]['ecart_pct'], -3.6)  # (800-830)/830
        self.assertEqual(etat['motif'], '')

    def test_un_mois_sans_mesure_vaut_null_jamais_zero(self):
        ligne = service._composer_etat(1, 2026, mesures_du_contrat(),
                                       SERVI)['ecarts'][11]
        self.assertIsNone(ligne['kwh_mesure'])
        self.assertIsNone(ligne['ecart_pct'])

    def test_non_simule_ou_perime_ecart_null_et_motif(self):
        for servi in ({'simule': False}, dict(SERVI, simulation_perimee=True,
                                              motif='document modifié')):
            etat = service._composer_etat(1, 2026, mesures_du_contrat(), servi)
            self.assertTrue(all(ligne['p50_kwh'] is None
                                and ligne['ecart_pct'] is None
                                for ligne in etat['ecarts']))
            self.assertIsNone(etat['ecart_annuel_pct'])
            self.assertTrue(etat['motif'])
            self.assertEqual(len(etat['mesures']), 11)

    def test_la_forme_du_get_est_celle_du_contrat(self):
        etat = service._composer_etat(1, 2026, mesures_du_contrat(), SERVI)
        self.assertEqual(sorted(etat), sorted(CONTRAT['exemple']))
        for cle in ('mesures', 'ecarts'):
            self.assertEqual(sorted(etat[cle][0]),
                             sorted(CONTRAT['exemple'][cle][0]))


class ValidationTest(SimpleTestCase):
    """Un refus nomme son champ ; rien n'est corrigé en silence."""

    @staticmethod
    def _corps(**options):
        corps = {'annee': 2026, 'mesures': [{'mois': 1, 'kwh_mesure': 850.0}]}
        corps.update(options)
        return corps

    def _champ(self, corps):
        with self.assertRaises(service.MesureRefusee) as refus:
            service._valider(corps)
        return refus.exception.champ

    def test_le_corps_du_contrat_est_accepte(self):
        annee, mesures = service._valider(CONTRAT['exemple_corps'])
        self.assertEqual((annee, len(mesures)), (2026, 11))

    def test_refus_nommes(self):
        double = [{'mois': 1, 'kwh_mesure': 1}, {'mois': 1, 'kwh_mesure': 2}]
        cas = [
            (self._corps(mesures=double), 'mesures[1].mois'),
            (self._corps(mesures=[{'mois': 13, 'kwh_mesure': 1}]),
             'mesures[0].mois'),
            (self._corps(mesures=[{'mois': 0, 'kwh_mesure': 1}]),
             'mesures[0].mois'),
            (self._corps(mesures=[{'mois': 2, 'kwh_mesure': -1}]),
             'mesures[0].kwh_mesure'),
            (self._corps(mesures=[{'mois': 2}]), 'mesures[0].kwh_mesure'),
            (self._corps(mesures=[{'mois': 2, 'kwh_mesure': True}]),
             'mesures[0].kwh_mesure'),
            (self._corps(mesures=[{'mois': m, 'kwh_mesure': 1}
                                  for m in range(1, 13)] * 2), 'mesures'),
            (self._corps(annee='2026'), 'annee'),
            ({'mesures': []}, 'annee'),
            ({'annee': 2026}, 'mesures'),
        ]
        for corps, champ in cas:
            self.assertEqual(self._champ(corps), champ, corps)

    def test_un_corps_qui_n_est_pas_un_objet_est_refuse(self):
        self.assertEqual(self._champ([]), '')


class ProductionMesureeEnBaseTest(BaseApiCalepinage):
    """GET/PUT en HTTP réel — exécutée par la CI (ORM)."""

    def setUp(self):
        super().setUp()
        self.cal = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        self.url = url_detail(self.cal.pk) + 'production-mesuree/'
        self.corps = CONTRAT['exemple_corps']

    def _servi(self):
        return mock.patch('apps.calepinage.selectors.resultat_servi',
                          return_value=SERVI)

    def test_douze_mesures_collees_rendent_douze_ecarts(self):
        corps = dict(self.corps, mesures=self.corps['mesures'] + [
            {'mois': 12, 'kwh_mesure': 800.0}])
        with self._servi():
            reponse = self.api.put(self.url, corps, format='json')
            lue = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(lue.status_code, 200, lue.data)
        self.assertEqual(len(lue.data['ecarts']), 12)
        self.assertEqual(lue.data['ecarts'][0]['ecart_pct'], -3.4)
        self.assertEqual(ProductionMesuree.objects.filter(
            calepinage=self.cal).count(), 12)

    def test_un_mois_manquant_est_null(self):
        with self._servi():
            self.api.put(self.url, self.corps, format='json')
            lue = self.api.get(self.url)
        self.assertIsNone(lue.data['ecarts'][11]['kwh_mesure'])
        self.assertIsNone(lue.data['ecarts'][11]['ecart_pct'])

    def test_un_doublon_est_refuse_en_nommant_le_mois_sans_rien_ecrire(self):
        corps = {'annee': 2026, 'mesures': [{'mois': 3, 'kwh_mesure': 1.0},
                                            {'mois': 3, 'kwh_mesure': 2.0}]}
        reponse = self.api.put(self.url, corps, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('mesures[1].mois', reponse.data)
        self.assertEqual(ProductionMesuree.objects.count(), 0)

    def test_non_simule_ecart_null_et_motif(self):
        self.api.put(self.url, self.corps, format='json')
        lue = self.api.get(self.url)
        self.assertEqual(lue.status_code, 200, lue.data)
        self.assertTrue(all(ligne['ecart_pct'] is None
                            for ligne in lue.data['ecarts']))
        self.assertTrue(lue.data['motif'])

    def test_company_du_corps_est_ignoree_et_l_auteur_vient_du_serveur(self):
        corps = dict(self.corps, company=self.autre.pk)
        self.api.put(self.url, corps, format='json')
        ligne = ProductionMesuree.objects.first()
        self.assertEqual(ligne.company_id, self.company.pk)
        self.assertEqual(ligne.saisi_par_id, self.user.pk)

    def test_un_nouveau_jeu_remplace_le_precedent(self):
        self.api.put(self.url, self.corps, format='json')
        self.api.put(self.url, {'annee': 2026, 'mesures': [
            {'mois': 1, 'kwh_mesure': 1.0}]}, format='json')
        self.assertEqual(ProductionMesuree.objects.count(), 1)

    def test_autre_societe_404(self):
        self.assertEqual(self.api_autre.get(self.url).status_code, 404)
        self.assertEqual(
            self.api_autre.put(self.url, self.corps, format='json')
            .status_code, 404)

    def test_sans_droit_403(self):
        self.assertEqual(self.api_sans.get(self.url).status_code, 403)
        self.assertEqual(
            self.api_sans.put(self.url, self.corps, format='json')
            .status_code, 403)

    def test_vide_sans_mesure(self):
        lue = self.api.get(self.url)
        self.assertEqual(lue.status_code, 200)
        self.assertEqual(lue.data['mesures'], [])
        self.assertEqual(lue.data['ecarts'], [])
