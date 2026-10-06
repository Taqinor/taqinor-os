"""ADOC125 — la carte « Devis en attente » = la liste « Mes devis ».

Constat (C-ADOC-046, sonde #87) : ``resume_portail_client`` comptait TOUS
les devis envoyés, y compris une version REMPLACÉE par une révision
(``is_active=False``) que « Mes devis » ne liste plus (QJR520) : le compteur
dépassait la liste, et la V1 remplacée restait acceptable au portail.

Run :
    python manage.py test apps.portail.tests.test_adoc_tableau_de_bord_revision -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
)
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

TABLEAU = '/api/django/portail/client/tableau-de-bord/'
LISTE = '/api/django/portail/mes-devis/'


class TableauDeBordRevisionTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc125-{n}', defaults={'nom': f'ADOC125 {n}'})
        self.client_a = Client.objects.create(
            company=self.co, nom='Alpha', prenom=f'ADOC125-{n}',
            email=f'adoc125-{n}@example.invalid')
        self.d1 = Devis.objects.create(
            company=self.co, reference=f'DEV-ADOC125-{n}',
            client=self.client_a, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        role, _ = Role.objects.get_or_create(
            company=self.co, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        user = CustomUser.objects.create_user(
            username=f'adoc125-portail-{n}', password='motdepasse-test-1234',
            company=self.co, role=role)
        user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        user.portail_client_id = self.client_a.id
        user.save()
        self.commercial = CustomUser.objects.create_user(
            username=f'adoc125-com-{n}', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def _compteur_et_liste(self):
        tableau = self.api.get(TABLEAU)
        self.assertEqual(tableau.status_code, 200, tableau.content)
        liste = self.api.get(LISTE)
        self.assertEqual(liste.status_code, 200, liste.content)
        envoyes = [d for d in liste.json()['results']
                   if d['statut'] == 'envoye']
        return tableau.json()['devis_en_attente'], len(envoyes)

    def test_compteur_egal_liste_a_chaque_etape(self):
        self.assertEqual(self._compteur_et_liste(), (1, 1))

        v2 = reviser_devis(self.d1, user=self.commercial)
        self.d1.refresh_from_db()
        self.assertFalse(self.d1.is_active)
        self.assertEqual(self.d1.statut, Devis.Statut.ENVOYE)
        # Pendant la révision : V1 remplacée, V2 brouillon ⇒ rien en attente.
        self.assertEqual(self._compteur_et_liste(), (0, 0))

        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        self.assertEqual(self._compteur_et_liste(), (1, 1))
        # Rechargement : mêmes compteurs.
        self.assertEqual(self._compteur_et_liste(), (1, 1))

    def test_v1_remplacee_non_acceptable(self):
        reviser_devis(self.d1, user=self.commercial)
        res = self.api.post(
            f'{LISTE}{self.d1.id}/accepter/',
            {'nom': 'Client', 'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 404, res.content)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.ENVOYE)
