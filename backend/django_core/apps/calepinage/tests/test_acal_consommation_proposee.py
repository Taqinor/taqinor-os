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
    MOIS_ETE, apercu_courbe_csv, _interpoler_factures,
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
        for montant in _interpoler_factures(650.0, 900.0):
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

    def test_csv_illisible_409_nomme(self):
        # ERR-ENF11-FUZZ-CALEPINAGE (w4) : le CONTENU du CSV est un fait que le
        # schéma publié ne peut pas dire -> 409 (la FORME du corps reste 400).
        reponse = self._proposer({'source': 'csv', 'csv': {
            'contenu': 'horodatage;kwh\n2026-01-01T00:00:00+01:00;0.12\n',
            'colonne': 'kwh_x'}})

        self.assertEqual(reponse.status_code, 409, reponse.content[:300])
        self.assertTrue(any(cle.startswith('csv.') for cle in reponse.data),
                        reponse.data)

    def test_forme_du_corps_400_avant_le_contenu(self):
        """La source, la classe, le TYPE des sous-documents et la présence de
        celui de la source choisie : un 400 qui nomme le champ."""
        for corps, champ in (
                ({}, 'source'), ({'source': 'xml'}, 'source'),
                ({'source': 'lead', 'classe': 'luxe'}, 'classe'),
                ({'source': 'factures'}, 'factures'),
                ({'source': 'factures', 'factures': 5}, 'factures'),
                ({'source': 'appareils'}, 'appareils'),
                ({'source': 'appareils', 'appareils': 0}, 'appareils'),
                ({'source': 'appareils', 'appareils': [1]}, 'appareils'),
                ({'source': 'appareils', 'appareils': [], 'charges': []},
                 'charges'),
                ({'source': 'csv'}, 'csv'),
                ({'source': 'lead', 'ramadan': 'oui'}, 'ramadan')):
            reponse = self._proposer(corps)
            self.assertEqual(reponse.status_code, 400, (corps, reponse.data))
            self.assertIn(champ, reponse.data)

    def test_contenu_refuse_409_nomme_et_jamais_500(self):
        for corps, champ in (
                ({'source': 'appareils', 'appareils': APPAREILS,
                  'charges': {'frigo': {}}}, 'charges.frigo'),
                ({'source': 'appareils', 'appareils': APPAREILS,
                  'charges': {'climatisation': 5}}, 'charges.climatisation'),
                ({'source': 'appareils', 'appareils': APPAREILS,
                  'charges': {'climatisation': {'zzz': 1}}},
                 'charges.climatisation.zzz'),
                ({'source': 'appareils', 'appareils': [{}]}, 'appareils'),
                ({'source': 'csv', 'csv': {}}, 'csv')):
            reponse = self._proposer(corps)
            self.assertEqual(reponse.status_code, 409, (corps, reponse.data))
            self.assertTrue(any(cle.startswith(champ) for cle in reponse.data),
                            (corps, reponse.data))

    def test_facture_non_finie_409_et_lead_absent_404(self):
        refus = self._proposer({'source': 'factures',
                                'factures': {'classe': 'residentiel'}})
        self.assertEqual(refus.status_code, 409)
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


class ProfilsTypesPutEnBaseTest(BaseApiCalepinage):
    """ERR-ENF11-FUZZ-CALEPINAGE (w4) — ``PUT parametres/profils-types/`` :
    FORME fautive 400 (chemin ``profils[<rang>].<champ>``), état 409 (clé en
    double, journée entièrement nulle), écriture 200 (la CI est la gate)."""

    JOURNEE = [1.0] * 12 + [2.0] * 12

    def _ligne(self, **surcharges):
        ligne = {'cle': 'maison-1', 'courbe': {'annuel': self.JOURNEE},
                 'provenance': 'Relevé de 12 factures, 2025.'}
        ligne.update(surcharges)
        return ligne

    def test_forme_fautive_400_nomme_la_ligne(self):
        reponse = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(), self._ligne(
                cle='autre', provenance='  ')]}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('profils[1].provenance', reponse.data)
        reponse = self.api.put(URL_PROFILS, {'profils': 'x'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('profils', reponse.data)

    def test_etat_409_cle_en_double_et_journee_nulle(self):
        doublon = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(),
                                      self._ligne(cle='MAISON-1')]},
            format='json')
        self.assertEqual(doublon.status_code, 409, doublon.data)
        self.assertIn('maison-1', doublon.data)
        nulle = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(
                courbe={'annuel': [0] * 24})]}, format='json')
        self.assertEqual(nulle.status_code, 409, nulle.data)
        self.assertIn('maison-1.courbe', nulle.data)

    def test_ecriture_200_remplace_les_profils_de_la_societe(self):
        reponse = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(famille='commercial')]},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        cles = [p['cle'] for p in reponse.data['profils']
                if p['source'] == 'societe']
        self.assertEqual(cles, ['maison-1'])


class CorpsProposerPublieTest(SimpleTestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE (w4) — le corps de ``consommation/proposer`` :
    UN prédicat, publié ET appliqué, sans base."""

    @staticmethod
    def _valider(corps):
        from apps.calepinage.serializers_conso import (
            ConsommationProposerCorpsSerializer,
        )

        champs = ConsommationProposerCorpsSerializer(data=corps)
        return champs.is_valid(), dict(champs.errors)

    def test_formes_valides(self):
        for corps in ({'source': 'lead'}, {'source': 'lead', 'classe':
                                           'domestique', 'ramadan': {}},
                      {'source': 'factures', 'factures': {},
                       'classe': 'agricole'},
                      {'source': 'appareils', 'appareils': []},
                      {'source': 'appareils', 'appareils': APPAREILS,
                       'charges': {'pac': {}}},
                      {'source': 'csv', 'csv': {'contenu': ''}}):
            self.assertTrue(self._valider(corps)[0], corps)

    def test_formes_fautives_nomment_le_champ(self):
        for corps, champ in (
                (None, 'non_field_errors'), ([], 'non_field_errors'),
                ({}, 'source'), ({'source': 5}, 'source'),
                ({'source': 'lead', 'classe': ''}, 'classe'),
                ({'source': 'lead', 'factures': []}, 'factures'),
                ({'source': 'lead', 'appareils': {}}, 'appareils'),
                ({'source': 'lead', 'appareils': ['x']}, 'appareils'),
                ({'source': 'lead', 'csv': None}, 'csv'),
                ({'source': 'factures'}, 'factures'),
                ({'source': 'appareils'}, 'appareils'),
                ({'source': 'csv'}, 'csv')):
            valide, erreurs = self._valider(corps)
            self.assertFalse(valide, corps)
            self.assertIn(champ, erreurs)

    def test_classes_saisissables_et_schema_oneof(self):
        from apps.calepinage.serializers_conso import classes_tarifaires
        from apps.parametres.tariff import CLASSES_INVERSION

        self.assertEqual(set(classes_tarifaires()),
                         {*CLASSES_INVERSION, 'domestique'})
        from apps.calepinage.services.consommation import SOURCES_PROPOSITION
        from apps.calepinage.serializers_conso import SOURCES_CONSOMMATION

        self.assertEqual(SOURCES_CONSOMMATION, SOURCES_PROPOSITION)


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
