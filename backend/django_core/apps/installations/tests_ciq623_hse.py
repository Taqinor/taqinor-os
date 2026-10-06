"""CIQ623 — sécurité chantier minimale dans ``installations`` : documents HSE
et garde ``exige_hse`` avant le montage ; docstrings QHSE corrigées.
"""
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import (
    DocumentProjet, Installation, RevisionDocument, StageModele)
from apps.installations.services import (
    _gate_check_hse, seed_stages, stage_gate_status,
    verifier_avancement_etape)
from apps.ventes.models import Devis, RegulatoryDossier
from authentication.models import Company

User = get_user_model()
CHANTIERS = '/api/django/installations/chantiers/'
HSE = ('plan_prevention', 'analyse_risques', 'permis_travail_hauteur')


class HseMinimalTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ623', slug='ciq623-co')
        self.user = User.objects.create_user(
            username='ciq623', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self._n = 0

    def _chantier(self, type_installation='industriel',
                  regime='accord_raccordement'):
        self._n += 10
        client = Client.objects.create(
            company=self.company, nom='Site', email=f'h{self._n}@example.com')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-CIQ623-{self._n}',
            client=client, statut='accepte', taux_tva=Decimal('20'))
        return Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ623-{self._n}',
            devis=devis, type_installation=type_installation,
            regime_8221=regime, statut=Installation.Statut.PLANIFIE)

    def _documents(self, chantier, types=HSE, revision=True):
        for type_doc in types:
            doc = DocumentProjet.objects.create(
                company=self.company, installation=chantier,
                type_doc=type_doc, titre=type_doc)
            if revision:
                RevisionDocument.objects.create(
                    company=self.company, document=doc,
                    date_revision=date(2027, 1, 1))

    def test_societe_amorcee_etape_exige_hse(self):
        seed_stages(self.company)
        montage = StageModele.objects.get(company=self.company,
                                          cle='montage_mecanique')
        self.assertTrue(montage.exige_hse)
        # Le Directeur rend l'étape bloquante : le gate HSE la ferme.
        montage.bloquant = True
        montage.save(update_fields=['bloquant'])
        chantier = self._chantier('residentiel', 'non_concerne')
        chantier.statut = Installation.Statut.SIGNE
        chantier.save(update_fields=['statut'])
        status = stage_gate_status(chantier, montage)
        self.assertFalse(status['satisfait'])
        self.assertIn('Plan de prévention', status['raisons'][0])
        self.assertEqual(verifier_avancement_etape(chantier, montage),
                         ['Étape « Montage mécanique (structure & panneaux) » : '
                          + status['raisons'][0]])
        self._documents(chantier)
        self.assertTrue(stage_gate_status(chantier, montage)['satisfait'])
        self.assertEqual(verifier_avancement_etape(chantier, montage), [])

    def test_document_sans_revision_ne_compte_pas(self):
        chantier = self._chantier()
        self._documents(chantier, revision=False)
        self.assertIsNotNone(_gate_check_hse(chantier))

    def test_ci_non_amorce_sans_documents_refuse(self):
        chantier = self._chantier()
        RegulatoryDossier.objects.create(
            company=self.company, devis=chantier.devis, chantier=chantier,
            regime_8221='accord_raccordement', statut='approuve',
            convention_signee_le=date(2027, 3, 1))
        r = self.api.patch(f'{CHANTIERS}{chantier.id}/',
                           {'statut': 'en_cours'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any('Documents de sécurité' in m
                            for m in r.data['statut']))
        self._documents(chantier)
        r = self.api.patch(f'{CHANTIERS}{chantier.id}/',
                           {'statut': 'en_cours'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_residentiel_non_amorce_identique(self):
        chantier = self._chantier('residentiel', 'declaration_bt')
        r = self.api.patch(f'{CHANTIERS}{chantier.id}/',
                           {'statut': 'en_cours'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_plus_de_promesse_qhse22(self):
        racine = Path(__file__).resolve().parent
        for chemin in racine.rglob('*.py'):
            if 'tests' in chemin.name or 'migrations' in chemin.parts:
                continue
            texte = chemin.read_text(encoding='utf-8')
            self.assertNotIn('QHSE22', texte, chemin)
            self.assertIsNone(
                re.search(r"points? d'arrêt QHSE \(toujours", texte), chemin)
