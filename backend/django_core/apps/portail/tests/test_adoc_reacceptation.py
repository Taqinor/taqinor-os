"""ADOC127 — aucune preuve d'e-signature portail pour un devis accepté ailleurs.

Constat (C-ADOC-048, sonde #89) : ``accept_devis`` rend un devis DÉJÀ
accepté inchangé, sans erreur ; la vue portail enchaînait alors la création
+ signature d'une ``AcceptationDevisPortail`` (nom « Client ») et un audit
« Devis accepté via le portail client » — une preuve d'e-signature fabriquée
pour un devis que le commercial avait accepté en interne.

Correctif : statut lu AVANT ``accept_devis`` → 409 « Ce devis est déjà
accepté. » sans aucune écriture ; un devis accepté AU PORTAIL puis re-posté
reste idempotent (200, preuve d'origine inchangée).

Run :
    python manage.py test apps.portail.tests.test_adoc_reacceptation -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.crm.models import Client
from apps.portail.models import AcceptationDevisPortail
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
)
from apps.ventes.models import Devis
from apps.ventes.services import accept_devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

DETAIL_AUDIT = 'Devis accepté via le portail client'


class ReacceptationPortailTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc127-{n}', defaults={'nom': f'ADOC127 {n}'})
        self.client_a = Client.objects.create(
            company=self.co, nom='Alpha', prenom=f'ADOC127-{n}',
            email=f'adoc127-{n}@example.invalid')
        self.devis = Devis.objects.create(
            company=self.co, reference=f'DEV-ADOC127-{n}',
            client=self.client_a, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        role, _ = Role.objects.get_or_create(
            company=self.co, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        self.portail = CustomUser.objects.create_user(
            username=f'adoc127-portail-{n}', password='motdepasse-test-1234',
            company=self.co, role=role)
        self.portail.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        self.portail.portail_client_id = self.client_a.id
        self.portail.save()
        self.commercial = CustomUser.objects.create_user(
            username=f'adoc127-commercial-{n}',
            password='motdepasse-test-1234', company=self.co,
            role_legacy='responsable')
        self.url = f'/api/django/portail/mes-devis/{self.devis.id}/accepter/'
        self.api = APIClient()
        self.api.force_authenticate(user=self.portail)

    def _audits_portail(self):
        return AuditLog.objects.filter(
            object_id=str(self.devis.id), detail=DETAIL_AUDIT)

    def test_devis_accepte_hors_portail_409_sans_preuve(self):
        accept_devis(devis=self.devis, user=self.commercial,
                     nom='Commercial', consentement=True)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)

        res = self.api.post(
            self.url, {'nom': 'Client', 'consent_esign': True},
            format='json')

        self.assertEqual(res.status_code, 409, res.content)
        self.assertEqual(res.json(), {'detail': 'Ce devis est déjà accepté.'})
        self.assertFalse(AcceptationDevisPortail.objects.filter(
            devis_id=self.devis.id).exists())
        self.assertFalse(self._audits_portail().exists())
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.accepte_par_nom, 'Commercial')

    def test_double_envoi_portail_idempotent(self):
        payload = {'nom': 'Sami', 'consent_esign': True}
        premier = self.api.post(self.url, payload, format='json')
        self.assertEqual(premier.status_code, 200, premier.content)
        preuve = AcceptationDevisPortail.objects.get(devis_id=self.devis.id)
        signe_le = preuve.signe_le
        nb_audits = self._audits_portail().count()

        second = self.api.post(
            self.url, {'nom': 'Autre nom', 'consent_esign': True},
            format='json')
        self.assertEqual(second.status_code, 200, second.content)
        preuve.refresh_from_db()
        self.assertEqual(preuve.nom_signataire, 'Sami')
        self.assertEqual(preuve.signe_le, signe_le)
        self.assertEqual(AcceptationDevisPortail.objects.filter(
            devis_id=self.devis.id).count(), 1)
        self.assertEqual(self._audits_portail().count(), nb_audits)
