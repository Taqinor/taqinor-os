"""CIQ621 — site pro : pas de pose avant l'accord et la convention (loi 82-21
art. 4-6 ; décret 2.25.100 art. 8, 13-14), même sans gates amorcés.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.services import (
    AVERTISSEMENT_COMPTEUR_DISTRIBUTEUR, RAISON_CI_SANS_CONVENTION,
    _gate_avertissements, stages_configures)
from apps.ventes.models import Devis, RegulatoryDossier
from authentication.models import Company

User = get_user_model()
CHANTIERS = '/api/django/installations/chantiers/'


class _Stage:
    cle = 'mise_en_service'
    exige_dossier = False


class TravauxApresConventionTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ621', slug='ciq621-co')
        self.directeur = User.objects.create_superuser(
            username='ciq621_dir', password='x', email='d@example.com',
            company=self.company)
        self.responsable = User.objects.create_user(
            username='ciq621_resp', password='x', role_legacy='responsable',
            company=self.company)
        self._n = 0

    def _api(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def _chantier(self, type_installation='industriel',
                  regime='accord_raccordement'):
        self._n += 10
        client = Client.objects.create(
            company=self.company, nom='Site', email=f's{self._n}@example.com')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-CIQ621-{self._n}',
            client=client, statut='accepte', taux_tva=Decimal('20'))
        return Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ621-{self._n}',
            devis=devis, type_installation=type_installation,
            regime_8221=regime, statut=Installation.Statut.PLANIFIE)

    def _patch(self, user, chantier, **data):
        return self._api(user).patch(f'{CHANTIERS}{chantier.id}/', data,
                                     format='json')

    def test_societe_non_amorcee_sans_convention_refusee(self):
        self.assertFalse(stages_configures(self.company))
        chantier = self._chantier()
        RegulatoryDossier.objects.create(
            company=self.company, devis=chantier.devis, chantier=chantier,
            regime_8221='accord_raccordement', statut='approuve')
        r = self._patch(self.responsable, chantier, statut='en_cours')
        self.assertEqual(r.status_code, 400)
        self.assertIn(RAISON_CI_SANS_CONVENTION, r.data['statut'])
        chantier.refresh_from_db()
        self.assertEqual(chantier.statut, 'planifie')

    def test_convention_saisie_autorise(self):
        chantier = self._chantier()
        RegulatoryDossier.objects.create(
            company=self.company, devis=chantier.devis, chantier=chantier,
            regime_8221='accord_raccordement', statut='approuve',
            convention_signee_le=date(2027, 3, 1))
        r = self._patch(self.responsable, chantier, statut='en_cours')
        self.assertEqual(r.status_code, 200, r.data)

    def test_derogation_directeur_autorisee_et_journalisee(self):
        chantier = self._chantier()
        r = self._patch(self.directeur, chantier, statut='en_cours',
                        motif_derogation_8221='Toiture du client, urgence')
        self.assertEqual(r.status_code, 200, r.data)
        notes = [a.body for a in chantier.activites.all() if a.body]
        self.assertTrue(any('dérogation Directeur' in n
                            and 'urgence' in n for n in notes), notes)

    def test_responsable_avec_motif_refuse(self):
        chantier = self._chantier()
        r = self._patch(self.responsable, chantier, statut='en_cours',
                        motif_derogation_8221='Pressé')
        self.assertEqual(r.status_code, 400)

    def test_residentiel_et_agricole_inchanges(self):
        for type_installation, regime in (
                ('residentiel', 'declaration_bt'),
                ('agricole', 'declaration_hors_reseau')):
            chantier = self._chantier(type_installation, regime)
            r = self._patch(self.responsable, chantier, statut='en_cours')
            self.assertEqual(r.status_code, 200, (type_installation, r.data))

    def test_avertissement_compteur_a_la_mise_en_service(self):
        chantier = self._chantier()
        self.assertIn(AVERTISSEMENT_COMPTEUR_DISTRIBUTEUR,
                      _gate_avertissements(chantier, _Stage()))
        RegulatoryDossier.objects.create(
            company=self.company, devis=chantier.devis, chantier=chantier,
            regime_8221='accord_raccordement', statut='comptage_pose')
        self.assertNotIn(AVERTISSEMENT_COMPTEUR_DISTRIBUTEUR,
                         _gate_avertissements(chantier, _Stage()))
        residentiel = self._chantier('residentiel', 'declaration_bt')
        self.assertEqual(_gate_avertissements(residentiel, _Stage()), [])
