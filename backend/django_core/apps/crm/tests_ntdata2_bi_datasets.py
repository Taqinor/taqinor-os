"""NTDATA2 — datasets BI CRM (`crm_leads` / `crm_clients`).

Couvre :
  * les deux datasets sont enregistrés (via `apps.py` ready()) ;
  * scoping société ;
  * le pivot stage × canal (critère d'acceptation) ;
  * les étapes viennent de STAGES.py, jamais écrites en dur dans le module ;
  * la ville d'un client vient du répertoire unifié `tiers`.
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm import stages as stage_mod
from apps.crm.bi_datasets import (
    CLIENTS_DATASET, LEADS_DATASET, stage_labels,
)
from apps.crm.models import Client, Lead
from authentication.models import Company
from core import data_explorer

User = get_user_model()


class CrmBiDatasetsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ntdata2-co', defaults={'nom': 'NTDATA2 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='ntdata2-autre', defaults={'nom': 'NTDATA2 Autre'})[0]
        self.user = User.objects.create_user(
            username='ntdata2_u', password='x', company=self.company)

    def test_datasets_enregistres(self):
        noms = {d['name'] for d in data_explorer.list_datasets()}
        self.assertIn(LEADS_DATASET, noms)
        self.assertIn(CLIENTS_DATASET, noms)

    def test_leads_scope_societe(self):
        Lead.objects.create(company=self.company, nom='L1')
        Lead.objects.create(company=self.autre, nom='LAutre')
        lignes = data_explorer.run_query(
            LEADS_DATASET, self.company, self.user, {'select': ['id']})
        self.assertEqual(len(lignes), 1)

    def test_pivot_stage_par_canal(self):
        premiere = stage_mod.STAGES[0]
        Lead.objects.create(company=self.company, nom='L2',
                            stage=premiere, canal='meta')
        Lead.objects.create(company=self.company, nom='L3',
                            stage=premiere, canal='meta')
        Lead.objects.create(company=self.company, nom='L4',
                            stage=premiere, canal='site')
        lignes = data_explorer.run_query(
            LEADS_DATASET, self.company, self.user, {
                'group_by': ['stage', 'canal'],
                'aggregates': [{'alias': 'n', 'fn': 'count', 'field': 'id'}],
            })
        par_canal = {r['canal']: r['n'] for r in lignes
                     if r['stage'] == premiere}
        self.assertEqual(par_canal['meta'], 2)
        self.assertEqual(par_canal['site'], 1)

    def test_perdu_et_motif_exposes(self):
        Lead.objects.create(company=self.company, nom='L5', perdu=True,
                            motif_perte='prix')
        lignes = data_explorer.run_query(
            LEADS_DATASET, self.company, self.user,
            {'select': ['perdu_bool', 'motif_perte'],
             'filters': {'perdu_bool': True}})
        self.assertEqual(lignes[0]['motif_perte'], 'prix')

    def test_stages_jamais_en_dur_dans_le_module(self):
        """Règle #2 — aucune clé d'étape n'est recopiée dans bi_datasets.py."""
        source = Path(
            __file__).resolve().parent.joinpath('bi_datasets.py').read_text(
                encoding='utf-8')
        for cle in stage_mod.STAGES:
            self.assertNotIn(cle, source)
        # …mais les libellés restent accessibles, LUS depuis STAGES.py.
        self.assertEqual(set(stage_labels()), set(stage_mod.STAGE_LABELS))

    def test_client_ville_vient_du_repertoire_tiers(self):
        from apps.tiers.models import Tiers

        tiers = Tiers.objects.create(company=self.company, nom='T1',
                                     ville='Casablanca')
        Client.objects.create(company=self.company, nom='C1', tiers=tiers)
        lignes = data_explorer.run_query(
            CLIENTS_DATASET, self.company, self.user,
            {'select': ['ville', 'type']})
        self.assertEqual(lignes[0]['ville'], 'Casablanca')
