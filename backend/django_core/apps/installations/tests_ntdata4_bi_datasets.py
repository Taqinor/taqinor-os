"""NTDATA4 — datasets BI `chantiers` (installations) et `sav_contrats`.

Couvre :
  * les deux datasets sont enregistrés (via les `apps.py` respectifs) ;
  * scoping société du dataset chantiers ;
  * le pivot ville × statut (critère d'acceptation) ;
  * `valeur_annuelle` d'un contrat = prix de la période × 12 / mois de la
    périodicité (et reste VIDE sans prix, jamais zéro).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.installations.bi_datasets import CHANTIERS_DATASET
from apps.installations.models_installation import Installation
from apps.sav.bi_datasets import CONTRATS_DATASET_NAME
from apps.sav.models import ContratMaintenance
from authentication.models import Company
from core import data_explorer

User = get_user_model()


class ChantiersBiDatasetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntdata4-co', defaults={'nom': 'NTDATA4 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='ntdata4-autre', defaults={'nom': 'NTDATA4 Autre'})[0]
        self.user = User.objects.create_user(
            username='ntdata4_u', password='x', company=self.company)
        self.poseur = User.objects.create_user(
            username='ntdata4_poseur', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientNTDATA4')

    def _chantier(self, reference, **kw):
        defaults = dict(company=self.company, reference=reference,
                        client=self.client_obj)
        defaults.update(kw)
        return Installation.objects.create(**defaults)

    def test_dataset_enregistre(self):
        noms = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn(CHANTIERS_DATASET, noms)
        self.assertIn(CONTRATS_DATASET_NAME, noms)

    def test_scope_societe(self):
        self._chantier('CH-NTDATA4-1')
        autre_client = Client.objects.create(
            company=self.autre, nom='AutreClientNTDATA4')
        Installation.objects.create(
            company=self.autre, reference='CH-NTDATA4-X',
            client=autre_client)
        lignes = data_explorer.run_query(
            CHANTIERS_DATASET, self.company, self.user, {'select': ['id']})
        self.assertEqual(len(lignes), 1)

    def test_pivot_ville_par_statut(self):
        premier = self._chantier('CH-NTDATA4-2', site_ville='Casablanca')
        self._chantier('CH-NTDATA4-3', site_ville='Casablanca',
                       statut=premier.statut)
        self._chantier('CH-NTDATA4-4', site_ville='Rabat',
                       statut=premier.statut)
        lignes = data_explorer.run_query(
            CHANTIERS_DATASET, self.company, self.user, {
                'group_by': ['ville', 'statut'],
                'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
            })
        par_ville = {r['ville']: r['n'] for r in lignes}
        self.assertEqual(par_ville['Casablanca'], 2)
        self.assertEqual(par_ville['Rabat'], 1)

    def test_kwc_signature_reception_installateur(self):
        self._chantier(
            'CH-NTDATA4-5', site_ville='Agadir',
            puissance_installee_kwc=Decimal('9.50'),
            date_signature=date(2026, 2, 10),
            date_reception=date(2026, 4, 3),
            technicien_responsable=self.poseur)
        lignes = data_explorer.run_query(
            CHANTIERS_DATASET, self.company, self.user,
            {'select': ['kwc', 'mois_signature', 'mois_reception',
                        'installateur']})
        ligne = lignes[0]
        self.assertEqual(ligne['kwc'], Decimal('9.50'))
        self.assertEqual(ligne['mois_signature'], date(2026, 2, 1))
        self.assertEqual(ligne['mois_reception'], date(2026, 4, 1))
        self.assertEqual(ligne['installateur'], 'ntdata4_poseur')


class SavContratsBiDatasetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntdata4b-co', defaults={'nom': 'NTDATA4b Co'})[0]
        self.user = User.objects.create_user(
            username='ntdata4b_u', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientNTDATA4b')

    def test_valeur_annuelle_par_periodicite(self):
        trimestriel = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite=ContratMaintenance.Periodicite.TRIMESTRIEL,
            date_debut=date(2026, 1, 1), prix=Decimal('1000.00'))
        annuel = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite=ContratMaintenance.Periodicite.ANNUEL,
            date_debut=date(2026, 1, 1), prix=Decimal('1000.00'))
        lignes = {
            r['id']: r for r in data_explorer.run_query(
                CONTRATS_DATASET_NAME, self.company, self.user,
                {'select': ['id', 'valeur_annuelle', 'frequence', 'statut']})
        }
        self.assertEqual(lignes[trimestriel.id]['valeur_annuelle'],
                         Decimal('4000.00'))
        self.assertEqual(lignes[annuel.id]['valeur_annuelle'],
                         Decimal('1000.00'))
        self.assertEqual(lignes[annuel.id]['frequence'],
                         ContratMaintenance.Periodicite.ANNUEL)
        self.assertEqual(lignes[annuel.id]['statut'], 'actif')

    def test_valeur_annuelle_vide_sans_prix(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite=ContratMaintenance.Periodicite.MENSUEL,
            date_debut=date(2026, 1, 1), prix=None, actif=False)
        lignes = data_explorer.run_query(
            CONTRATS_DATASET_NAME, self.company, self.user,
            {'select': ['id', 'valeur_annuelle', 'statut'],
             'filters': {'id': contrat.id}})
        self.assertIsNone(lignes[0]['valeur_annuelle'])
        self.assertEqual(lignes[0]['statut'], 'inactif')
