"""ADOC172 — le passage du chantier à ``materiel_commande`` puis ``installe``
publie les jalons « Matériel » / « Installation » du suivi client (phases
portail ``appro`` / ``pose``) via ``synchroniser_jalon_portail``."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation, JalonProjet
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
)
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class JalonsStatutTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ADOC172 Co')
        self.user = User.objects.create_user(
            username='adoc172', password='x', company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ADOC172',
            telephone='+212600000172')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-ADOC17201',
            client=client, statut=Devis.Statut.ACCEPTE,
            date_acceptation=datetime.date(2026, 8, 26),
            taux_tva=Decimal('20'))
        self.link = ShareLink.for_devis(self.devis)
        self.chantier, _ = create_installation_from_devis(
            self.devis, self.user, self.company)
        self.api = APIClient()

    def _passer(self, statut):
        inst = Installation.objects.get(pk=self.chantier.pk)
        changer_statut_chantier(inst, statut, self.user, verifier_gates=False)

    def _suivi(self):
        resp = self.api.get(f'/api/django/ventes/suivi/{self.link.token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data, {m['key']: m for m in resp.data['milestones']}

    def test_materiel_commande_coche_materiel(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        _, ms = self._suivi()
        self.assertTrue(ms['materiel']['done'])
        self.assertTrue(ms['materiel']['date'])
        self.assertFalse(ms['installation']['done'])

    def test_installe_coche_installation(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        data, ms = self._suivi()
        self.assertTrue(ms['installation']['done'])
        self.assertTrue(ms['installation']['date'])
        self.assertEqual(data['mis_a_jour_le'], ms['installation']['date'])

    def test_annulation_decoche(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        Installation.objects.filter(pk=self.chantier.pk).update(annule=True)
        _, ms = self._suivi()
        self.assertFalse(ms['materiel']['done'])
        self.assertFalse(ms['installation']['done'])

    def test_idempotent(self):
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        self._passer(Installation.Statut.MATERIEL_COMMANDE)
        self._passer(Installation.Statut.INSTALLE)
        for phase in (JalonProjet.Phase.APPRO, JalonProjet.Phase.POSE):
            self.assertEqual(JalonProjet.objects.filter(
                installation=self.chantier, phase=phase).count(), 1)

    def test_retour_arriere_ne_coche_rien(self):
        self._passer(Installation.Statut.INSTALLE)
        self._passer(Installation.Statut.SIGNE)
        self.assertFalse(JalonProjet.objects.filter(
            installation=self.chantier, phase=JalonProjet.Phase.APPRO,
            atteint=True).exists())
