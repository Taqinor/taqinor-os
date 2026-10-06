"""CIQ617 — UN SEUL état du dossier 82-21 : le chantier lit le dossier
réglementaire (``ventes.RegulatoryDossier``) et n'en garde qu'un miroir.

Run :
    python manage.py test apps.installations.tests_ciq617_statut_unique -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.services import (
    MESSAGE_STATUT_GERE_PAR_DOSSIER, RAISON_DOSSIER_REFUSE,
    STATUT_DOSSIER_VERS_CHANTIER, _gate_check_dossier,
    compute_chantier_readiness, refleter_dossier_8221)
from apps.ventes.models import Devis, RegulatoryDossier
from authentication.models import Company

User = get_user_model()
DOSSIERS = '/api/django/ventes/dossiers-reglementaires/'
CHANTIERS = '/api/django/installations/chantiers/'
_CONTRAT = (Path(__file__).resolve().parent.parent / 'ventes'
            / 'contract_samples' / 'dossier_8221.json')


class StatutUniqueDossierTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ617', slug='ciq617-co')
        self.other = Company.objects.create(nom='Autre', slug='ciq617-autre')
        self.user = User.objects.create_user(
            username='ciq617', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.chantier = self._chantier(self.company, 'DEV-CIQ617-10')

    def _chantier(self, company, ref):
        client = Client.objects.create(
            company=company, nom='Usine', email=f'{ref.lower()}@example.com')
        devis = Devis.objects.create(
            company=company, reference=ref, client=client, statut='accepte',
            taux_tva=Decimal('20'), mode_installation='industriel')
        return Installation.objects.create(
            company=company, reference=f'CHT-{ref}', devis=devis,
            type_installation='industriel',
            regime_8221='accord_raccordement',
            dossier_statut=Installation.DossierStatut.A_DEPOSER)

    def _dossier(self, **extra):
        data = {'devis': self.chantier.devis_id,
                'chantier': self.chantier.id,
                'regime_8221': 'accord_raccordement'}
        data.update(extra)
        r = self.api.post(DOSSIERS, data, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def _patch_dossier(self, pk, **data):
        r = self.api.patch(f'{DOSSIERS}{pk}/', data, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.chantier.refresh_from_db()
        return r

    def test_dossier_approuve_debloque_le_gate(self):
        pk = self._dossier()
        self.assertIsNotNone(_gate_check_dossier(self.chantier))
        self._patch_dossier(pk, statut='approuve', date_decision='2026-11-20',
                            reference_dossier='REF-1')
        self.assertEqual(self.chantier.dossier_statut, 'approuve')
        self.assertEqual(self.chantier.dossier_reference, 'REF-1')
        self.assertEqual(str(self.chantier.dossier_date_approbation),
                         '2026-11-20')
        self.assertIsNone(_gate_check_dossier(self.chantier))
        self.assertTrue(compute_chantier_readiness(
            self.chantier)['dossier']['ok'])

    def test_dossier_refuse_bloque_avec_motif(self):
        pk = self._dossier()
        self._patch_dossier(pk, statut='refuse')
        self.assertNotEqual(self.chantier.dossier_statut, 'approuve')
        self.assertEqual(_gate_check_dossier(self.chantier),
                         RAISON_DOSSIER_REFUSE)
        # Même si quelqu'un écrit « approuvé » sur le chantier en base, le
        # dossier refusé reste la vérité.
        Installation.objects.filter(pk=self.chantier.pk).update(
            dossier_statut='approuve')
        self.chantier.refresh_from_db()
        self.assertEqual(_gate_check_dossier(self.chantier),
                         RAISON_DOSSIER_REFUSE)
        self.assertFalse(compute_chantier_readiness(
            self.chantier)['dossier']['ok'])

    def test_chacun_des_7_statuts_a_sa_correspondance(self):
        attendu = {
            'en_constitution': 'a_deposer', 'depose': 'depose',
            'en_instruction': 'depose', 'complement_demande': 'depose',
            'approuve': 'approuve', 'comptage_pose': 'compteur_pose',
            'refuse': 'a_deposer',
        }
        self.assertEqual(STATUT_DOSSIER_VERS_CHANTIER, attendu)
        self.assertEqual(set(attendu),
                         set(RegulatoryDossier.Statut.values))
        pk = self._dossier()
        for statut_dossier, statut_chantier in attendu.items():
            self._patch_dossier(pk, statut=statut_dossier)
            self.assertEqual(self.chantier.dossier_statut, statut_chantier,
                             statut_dossier)
        self.assertNotIn('approuve', {
            v for k, v in attendu.items() if k == 'refuse'})

    def test_patch_chantier_avec_dossier_refuse_400(self):
        self._dossier()
        r = self.api.patch(f'{CHANTIERS}{self.chantier.id}/',
                           {'dossier_statut': 'approuve'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(str(r.data['dossier_statut'][0]),
                         MESSAGE_STATUT_GERE_PAR_DOSSIER)
        self.chantier.refresh_from_db()
        self.assertEqual(self.chantier.dossier_statut, 'a_deposer')

    def test_sans_dossier_saisie_chantier_inchangee(self):
        r = self.api.patch(f'{CHANTIERS}{self.chantier.id}/',
                           {'dossier_statut': 'approuve'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['dossier_8221_resume']['source'],
                         'saisie_chantier')
        self.chantier.refresh_from_db()
        self.assertIsNone(_gate_check_dossier(self.chantier))

    def test_autre_societe_aucun_effet(self):
        autre = self._chantier(self.other, 'DEV-CIQ617-20')
        resume = {'source': 'dossier', 'statut': 'approuve',
                  'regime': 'accord_raccordement'}
        self.assertIsNone(refleter_dossier_8221(autre.id, resume,
                                                company=self.company))
        autre.refresh_from_db()
        self.assertEqual(autre.dossier_statut, 'a_deposer')

    def test_resume_conforme_au_contrat(self):
        pk = self._dossier()
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        r = self.api.get(f'{DOSSIERS}{pk}/')
        self.assertTrue(set(contrat['exemple']['resume']) <= set(
            r.data['resume']))
        self.assertEqual(r.data['resume']['source'], 'dossier')
        fiche = self.api.get(f'{CHANTIERS}{self.chantier.id}/')
        self.assertEqual(fiche.data['dossier_8221_resume']['source'],
                         'dossier')
        self.assertEqual(fiche.data['dossier_8221_resume']['statut'],
                         'en_constitution')
