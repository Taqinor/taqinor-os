"""CIQ618 — un chantier C&I ouvre seul son dossier 82-21 ; un régime inconnu
crée la prochaine action « Qualifier le régime ».
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.ventes.domain.dossier_8221 import PROCHAINE_ACTION_QUALIFIER
from apps.ventes.models import Devis, RegulatoryDossier
from apps.ventes.regulatory_docs import required_documents
from authentication.models import Company
from core.events import devis_accepted

User = get_user_model()


class OuvertureDossierTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ618', slug='ciq618-co')
        self.user = User.objects.create_user(
            username='ciq618', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hôtel', email='ciq618@example.com')
        self._n = 0

    def _devis(self, mode, etude):
        self._n += 10
        return Devis.objects.create(
            company=self.company, reference=f'DEV-CIQ618-{self._n}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params=etude)

    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def test_devis_commercial_ouvre_un_dossier_seme(self):
        devis = self._devis('commercial', {'puissance_kwc': 120})
        self._accepter(devis)
        chantier = Installation.objects.get(devis=devis)
        dossiers = RegulatoryDossier.objects.filter(company=self.company)
        self.assertEqual(dossiers.count(), 1)
        dossier = dossiers.get()
        self.assertEqual(dossier.devis_id, devis.id)
        self.assertEqual(dossier.chantier_id, chantier.id)
        self.assertEqual(dossier.statut, 'en_constitution')
        self.assertEqual(dossier.regime_8221, 'accord_raccordement')
        attendues = required_documents('accord_raccordement')
        items = list(dossier.checklist_items.order_by('ordre'))
        self.assertEqual([i.code for i in items],
                         [p['code'] for p in attendues])
        self.assertEqual({i.code: i.etape for i in items},
                         {p['code']: p['etape'] for p in attendues})
        # Miroir CIQ617 posé sur le chantier.
        chantier.refresh_from_db()
        self.assertEqual(chantier.dossier_statut, 'a_deposer')

    def test_reemission_du_signal_toujours_un_seul(self):
        devis = self._devis('industriel', {'puissance_kwc': 300})
        self._accepter(devis)
        self._accepter(devis)
        self.assertEqual(RegulatoryDossier.objects.filter(
            company=self.company).count(), 1)

    def test_regime_inconnu_prochaine_action(self):
        devis = self._devis('commercial', {})
        self._accepter(devis)
        dossier = RegulatoryDossier.objects.get(company=self.company)
        self.assertEqual(dossier.regime_8221, 'a_qualifier')
        self.assertEqual(dossier.prochaine_action, PROCHAINE_ACTION_QUALIFIER)
        self.assertEqual(dossier.checklist_items.count(), 0)
        self.assertIsNone(dossier.prochaine_action_date)

    def test_v2_acceptee_meme_dossier(self):
        v1 = self._devis('commercial', {'puissance_kwc': 120})
        self._accepter(v1)
        dossier = RegulatoryDossier.objects.get(company=self.company)
        v2 = self._devis('commercial', {'puissance_kwc': 130})
        Devis.objects.filter(pk=v1.pk).update(superseded_by=v2)
        self._accepter(v2)
        self.assertEqual(RegulatoryDossier.objects.filter(
            company=self.company).count(), 1)
        dossier.refresh_from_db()
        self.assertEqual(dossier.devis_id, v2.id)

    def test_residentiel_et_agricole_aucun_dossier(self):
        self._accepter(self._devis('residentiel', {'puissance_kwc': 6}))
        self._accepter(self._devis('agricole', {'puissance_kwc': 10}))
        self.assertFalse(RegulatoryDossier.objects.filter(
            company=self.company).exists())
