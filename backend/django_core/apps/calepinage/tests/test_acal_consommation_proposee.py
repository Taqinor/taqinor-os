"""ACAL310 — la consommation PROPOSÉE par le serveur (D-ACAL-20).

Constats C-ACAL-145 / C-ACAL-125 / C-ACAL-004 : le seul écrivain de
``roof_layout.consumption`` était l'atelier TS, sur un barème REGIE figé ; les
fonctions serveur (profil depuis le lead, kWh par le barème SOCIÉTÉ,
appareils + charges, Ramadan, aperçu CSV) n'avaient aucune porte ; la
simulation ignorait ``consumption.saisons`` ; ``profil_depuis_import`` ne
nourrissait aucun profil type.

``POST calepinages/<pk>/consommation/proposer/`` les branche (lecture PURE),
``courbe_charge`` lit les saisons, ``PUT parametres/profils-types/`` accepte
``depuis_import``.

Base de test réelle, barème société RÉEL (``TariffSettings``), lead réel,
client HTTP réel ; la simulation réelle (client rejoué) pour les saisons.
Aucun mock de la source.

Run :
    python manage.py test apps.calepinage.tests.test_acal_consommation_proposee -v2
"""
from __future__ import annotations

import copy
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.consommation import (
    MOIS_ETE, apercu_courbe_csv, interpoler_factures,
)
from apps.calepinage.services.courbe_charge import construire_courbe_charge
from apps.parametres.models_tariff import TariffSettings
from apps.parametres.tariff import kwh_depuis_facture

from .test_api_liste import BaseApiCalepinage
from .test_calx5_simulation import LAYOUT

BASE = '/api/django/calepinage/calepinages/'
URL_PROFILS = '/api/django/calepinage/parametres/profils-types/'

APPAREILS = [
    {'kind': 'frigo', 'label': 'Réfrigérateur', 'dailyKwh': 1.2,
     'startHour': 0, 'endHour': 24, 'billing': 'foyer',
     'provenance': 'saisi'},
    {'kind': 'four', 'label': 'Four', 'dailyKwh': 2.0, 'startHour': 18,
     'endHour': 21, 'billing': 'foyer', 'provenance': 'saisi'},
]


class _Base(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.lead.facture_hiver = Decimal('650')
        self.lead.facture_ete = Decimal('900')
        self.lead.ete_differente = True
        self.lead.type_installation = 'residentiel'
        self.lead.save()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Conso 310', roof_layout=copy.deepcopy(LAYOUT))
        self.url = f'{BASE}{self.calepinage.pk}/consommation/proposer/'

    def _proposer(self, corps):
        return self.api.post(self.url, corps, format='json')


class ProposerTest(_Base):

    def test_lead_factures_bareme_societe(self):
        # Le barème de la SOCIÉTÉ, modifié : un prix unique de 2,00 MAD/kWh
        # (jamais le barème REGIE figé de l'atelier).
        reglages = TariffSettings.get(company=self.company)
        reglages.residential_tiers = [{'max_kwh': None,
                                       'prix_kwh_ttc': '2.00'}]
        # Un barème RÉGLÉ déclare aussi ses charges fixes d'abonnement :
        # sans elles, ``kwh_depuis_facture`` refuse de convertir (kwh None,
        # motif nommé — CALX257) plutôt que de compter le compteur en kWh.
        reglages.redevance_compteur_mad_mois = Decimal('39.94')
        reglages.save()

        reponse = self._proposer({'source': 'lead'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        reglages = TariffSettings.get(company=self.company)
        attendu = 0.0
        for montant in interpoler_factures(650.0, 900.0):
            kwh = kwh_depuis_facture(reglages, montant,
                                     classe='residentiel')['kwh']
            attendu += float(kwh)
        self.assertAlmostEqual(reponse.data['kwh_annuel'], attendu,
                               delta=0.2)
        consumption = reponse.data['consumption']
        self.assertEqual(consumption['source']['bareme'], 'societe')
        self.assertEqual(consumption['source']['origine'], 'lead')
        self.assertEqual(len(reponse.data['courbe24']), 24)
        self.assertIn('ete', reponse.data['saisons'])
        self.assertGreater(reponse.data['saisons']['ete'],
                           reponse.data['saisons']['hiver'])
        # Lecture PURE : rien n'est écrit.
        self.calepinage.refresh_from_db()
        self.assertNotIn('consumption', self.calepinage.roof_layout)

    def test_appareils_et_climatisation(self):
        reponse = self._proposer({
            'source': 'appareils', 'appareils': APPAREILS,
            'charges': {'climatisation': {
                'btu': 12000, 'eer': 3.2,
                'heures_fonctionnement': [13, 14, 15, 16]}}})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        courbe = reponse.data['courbe24']
        # 3,2 kWh/j d'appareils + 12000/3.2/1000 × 4 h = 15 kWh de clim.
        self.assertAlmostEqual(sum(courbe), 3.2 + 15.0, delta=0.05)
        self.assertGreater(courbe[14], courbe[3])
        self.assertEqual(reponse.data['consumption']['methode'], 'appareils')

    def test_ramadan_decale_la_courbe(self):
        sans = self._proposer({'source': 'appareils', 'appareils': APPAREILS})
        avec = self._proposer({'source': 'appareils', 'appareils': APPAREILS,
                               'ramadan': {'actif': True,
                                           'jour': '2026-03-01'}})

        self.assertEqual(avec.status_code, 200, avec.content[:300])
        self.assertNotEqual(avec.data['courbe24'], sans.data['courbe24'])
        self.assertAlmostEqual(sum(avec.data['courbe24']),
                               sum(sans.data['courbe24']), delta=0.01)
        self.assertEqual(avec.data['consumption']['methode'], 'courbe')

    def test_csv_illisible_400_nomme(self):
        reponse = self._proposer({'source': 'csv', 'csv': {
            'contenu': 'horodatage;kwh\n2026-01-01T00:00:00+01:00;0.12\n',
            'colonne': 'kwh_x'}})

        self.assertEqual(reponse.status_code, 400, reponse.content[:300])
        self.assertTrue(any(cle.startswith('csv.') for cle in reponse.data),
                        reponse.data)

    def test_facture_non_finie_400_et_lead_absent_404(self):
        refus = self._proposer({'source': 'factures',
                                'factures': {'classe': 'residentiel'}})
        self.assertEqual(refus.status_code, 400)
        self.assertIn('factures.hiver_mad', refus.data)

        sans_lead = Calepinage.objects.create(
            company=self.company, client_id=self.client_a.pk,
            titre='Sans lead')
        reponse = self.api.post(
            f'{BASE}{sans_lead.pk}/consommation/proposer/',
            {'source': 'lead'}, format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_profil_depuis_import_cree_un_profil_societe(self):
        lignes = ['horodatage;kwh'] + [
            f'2025-01-01T00:00:00+00:00;{0.5 + (heure % 24) / 48:.3f}'
            for heure in range(8760)]
        apercu = apercu_courbe_csv('\n'.join(lignes), colonne='kwh')

        reponse = self.api.put(URL_PROFILS, {'depuis_import': {
            'apercu': apercu, 'cle': 'releve_maison', 'libelle': 'Relevé',
            'famille': 'residentiel', 'origine': 'Relevé SRM 2025'}},
            format='json')

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        lecture = self.api.get(URL_PROFILS)
        cles = [profil.get('cle') for profil in lecture.data['profils']]
        self.assertIn('releve_maison', cles)


class SaisonsLuesParLaSimulationTest(SimpleTestCase):
    """``consumption.saisons`` module la courbe de charge de la simulation."""

    def _serie(self):
        points = [{'annee': 2021, 'mois': mois, 'jour': 15, 'heure': heure,
                   'p_ac_kw': 1.0}
                  for mois in (1, 7) for heure in range(24)]
        return {'points': points, 'pas_minutes': 60,
                'colonne_energie': 'p_ac_kw'}

    def _charge(self, saisons=None):
        consumption = {'courbe24': [0.5] * 24, 'methode': 'courbe',
                       'source': {'origine': 'essai'}}
        if saisons:
            consumption['saisons'] = saisons
        return construire_courbe_charge(
            self._serie(), consommation={'layout': {
                'consumption': consumption}})

    def test_saisons_lues_par_la_simulation(self):
        sans = self._charge()
        avec = self._charge({'ete': 1.5, 'hiver': 0.8})

        self.assertEqual(sans['courbe'][:24], sans['courbe'][24:])
        janvier, juillet = avec['courbe'][:24], avec['courbe'][24:]
        self.assertIn(7, MOIS_ETE)
        self.assertAlmostEqual(janvier[0], 0.5 * 0.8)
        self.assertAlmostEqual(juillet[0], 0.5 * 1.5)
        self.assertTrue(any('saisonnalité SAISIE' in texte
                            for texte in avec['avertissements']))
