"""AUD315 (volet export) — plus d'export superutilisateur tous tenants mêlés.

`_co_qs` renvoyait un queryset NON filtré pour tout appelant `is_superuser`
sans société, et `export_list` n'acceptait aucun paramètre de société : un
export lancé par ce profil produisait un seul fichier mélangeant TOUTES les
sociétés. Le sélecteur est désormais obligatoire (400 sinon), et l'export
n'emporte que la société désignée.

Run :
    docker compose exec django_core python manage.py test \
        apps.dataimport.test_aud315_export_selecteur_societe -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.dataimport.exports_view import _co_qs, _devis_rows
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
URL = '/api/django/imports/export/devis/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ExportSelecteurSocieteTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.get_or_create(
            slug='aud315x-a', defaults={'nom': 'A'})[0]
        self.co_b = Company.objects.get_or_create(
            slug='aud315x-b', defaults={'nom': 'B'})[0]
        for co, ref in ((self.co_a, 'DEV-A315'), (self.co_b, 'DEV-B315')):
            client = Client.objects.create(company=co, nom=f'C{ref}')
            Devis.objects.create(
                company=co, reference=ref, client=client,
                taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        self.root = User.objects.create_superuser(
            username='aud315x-root', password='x', email='r315@example.com')
        self.staff_a = User.objects.create_user(
            username='aud315x-a', password='x', company=self.co_a,
            role_legacy='admin')

    def test_superuser_sans_selecteur_ne_ramene_rien(self):
        """Le cœur du défaut : plus jamais un queryset toutes sociétés."""
        qs = _co_qs(Devis, self.root)

        self.assertEqual(qs.count(), 0)

    def test_superuser_avec_selecteur_ne_ramene_que_cette_societe(self):
        qs = _co_qs(Devis, self.root, self.co_b.id)

        self.assertEqual(
            list(qs.values_list('reference', flat=True)), ['DEV-B315'])

    def test_endpoint_refuse_400_sans_selecteur(self):
        resp = _auth(self.root).post(URL, {}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('company', resp.data)

    def test_endpoint_accepte_avec_selecteur(self):
        resp = _auth(self.root).post(
            URL, {'company': self.co_a.id}, format='json')

        self.assertEqual(resp.status_code, 200)

    def test_utilisateur_scope_ignore_le_selecteur_dune_autre_societe(self):
        """Un compte à société ne peut pas exporter une AUTRE société."""
        _, _, rows, _ = _devis_rows(self.staff_a, [], self.co_b.id)

        self.assertEqual([r[0] for r in rows], ['DEV-A315'])

    def test_utilisateur_scope_exporte_toujours_sa_societe(self):
        resp = _auth(self.staff_a).post(URL, {}, format='json')

        self.assertEqual(resp.status_code, 200)
