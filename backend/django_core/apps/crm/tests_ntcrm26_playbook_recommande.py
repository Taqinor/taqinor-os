"""NTCRM26 — Recommandation de playbook par similarité.

Deux playbooks actifs sur le même stage avec des critères différents ne
s'appliquent chacun qu'au bon profil de lead (aucune IA/ML — core.rules pur).
"""
from django.test import TestCase

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadPlaybookProgress, Playbook, PlaybookEtape, PlaybookTache
from apps.crm.services import generer_playbook_progress, playbooks_recommandes


class PlaybookRecommandeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM26', slug='taqinor-ntcrm26')
        self.playbook_residentiel = Playbook.objects.create(
            company=self.company, nom='Playbook résidentiel', actif=True,
            condition={'field': 'type_installation', 'operator': 'eq', 'value': 'residentiel'})
        self.etape_residentiel = PlaybookEtape.objects.create(
            playbook=self.playbook_residentiel, stage=stages.QUOTE_SENT, ordre=1)
        PlaybookTache.objects.create(
            etape=self.etape_residentiel, libelle='Relancer par SMS', obligatoire=True, ordre=1)

        self.playbook_industriel = Playbook.objects.create(
            company=self.company, nom='Playbook industriel', actif=True,
            condition={'field': 'type_installation', 'operator': 'eq', 'value': 'industriel'})
        self.etape_industriel = PlaybookEtape.objects.create(
            playbook=self.playbook_industriel, stage=stages.QUOTE_SENT, ordre=1)
        PlaybookTache.objects.create(
            etape=self.etape_industriel, libelle='Planifier visite technique', obligatoire=True, ordre=1)

    def test_lead_residentiel_recoit_le_bon_playbook(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead résidentiel', type_installation='residentiel')
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].tache.libelle, 'Relancer par SMS')
        self.assertEqual(LeadPlaybookProgress.objects.filter(lead=lead).count(), 1)

    def test_lead_industriel_recoit_le_bon_playbook(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead industriel', type_installation='industriel')
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].tache.libelle, 'Planifier visite technique')

    def test_lead_hors_profil_ne_recoit_aucun_playbook_conditionne(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead agricole', type_installation='agricole')
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(created, [])

    def test_playbook_universel_reste_toujours_applique(self):
        universel = Playbook.objects.create(
            company=self.company, nom='Playbook universel', actif=True, condition=None)
        etape_universelle = PlaybookEtape.objects.create(
            playbook=universel, stage=stages.QUOTE_SENT, ordre=1)
        PlaybookTache.objects.create(
            etape=etape_universelle, libelle='Envoyer un merci', obligatoire=False, ordre=1)
        lead = Lead.objects.create(
            company=self.company, nom='Lead sans profil', type_installation='agricole')
        created = generer_playbook_progress(lead, stages.QUOTE_SENT)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].tache.libelle, 'Envoyer un merci')

    def test_playbooks_recommandes_selector_pur(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead pur', type_installation='residentiel')
        recommandes = playbooks_recommandes(lead, stages.QUOTE_SENT)
        self.assertEqual([p.pk for p in recommandes], [self.playbook_residentiel.pk])
