"""Tests AUD148 — hygiène des surfaces d'accès portail.

(a) PORT-14 — ``ComptePortailClient.derniere_connexion`` n'était écrite par
    AUCUN code : grep sur ``backend/django_core`` ne rendait que le modèle et
    le serializer en lecture seule, pendant que l'écran ERP affiche la colonne.
    Le patron existe pourtant dans le dépôt (``education/public_views.py`` met
    bien à jour SON équivalent). La colonne d'audit d'accès était donc vide le
    jour où l'on cherche qui a consulté quoi.

(b) PORT-15 — ``DocumentClientPortail.fichier`` (``FileField``
    ``upload_to='compta/portail_docs/'``) était sérialisé tel quel et rendu en
    lien DIRECT par l'écran, alors que ``settings/base.py`` ne définit ni
    ``MEDIA_URL`` ni ``MEDIA_ROOT``, qu'aucune route ne sert ``/media/`` et que
    ``frontend/nginx.conf`` n'a aucune ``location /media/`` : le lien était
    mort par construction.

(c) PORT-17 — ``compta.services.provisionner_compte_portail`` réactive un
    compte désactivé, à l'exact opposé de la politique portail. NON TRAITÉ ICI :
    le correctif vit dans ``apps/compta/services.py``, hors du périmètre de
    cette lane (voir le rapport de lane). Aucun test rouge n'est déposé pour un
    défaut que cette lane ne peut pas fermer.

Ces tests étaient ROUGES avant le correctif : ``derniere_connexion`` restait
NULL après une consultation portail (tokenisée comme JWT), et le payload
documents portait l'URL brute du ``FileField``.

Run :
    python manage.py test apps.portail.tests.test_aud148_hygiene_acces -v2
"""
import itertools
from datetime import timedelta
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.portail.models import ComptePortailClient, DocumentClientPortail
from apps.portail.services import enregistrer_connexion_portail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD148-{n}',
        email=f'aud148-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, client_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = client_id
    user.save()
    return user


# ── (a) PORT-14 — la dernière connexion est enfin horodatée ────────────────

class DerniereConnexionPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('aud148-co', 'AUD148 Société')
        self.client_crm = make_client_crm(self.co, 'Alpha')
        self.compte = ComptePortailClient.objects.create(
            company=self.co, client=self.client_crm,
            token_acces='aud148-token-alpha')
        self.user = make_portal_user(
            self.co, 'aud148-portail-a', self.client_crm.id)

    def test_une_connexion_jwt_renseigne_la_derniere_connexion(self):
        """ROUGE avant AUD148 : la colonne restait NULL."""
        self.assertIsNone(self.compte.derniere_connexion)

        api = APIClient()
        api.force_authenticate(user=self.user)
        self.assertEqual(
            api.get('/api/django/portail/mes-devis/').status_code, 200)

        self.compte.refresh_from_db()
        self.assertIsNotNone(self.compte.derniere_connexion)

    def test_une_connexion_tokenisee_renseigne_la_derniere_connexion(self):
        """ROUGE avant AUD148 : la colonne restait NULL."""
        public = APIClient()
        res = public.get(
            f'/api/django/compta/portail/{self.compte.token_acces}'
            '/mon-releve/')
        self.assertEqual(res.status_code, 200, res.content)

        self.compte.refresh_from_db()
        self.assertIsNotNone(self.compte.derniere_connexion)

    def test_lhorodatage_nest_pas_reecrit_a_chaque_requete(self):
        """Une écriture par GET transformerait chaque lecture en UPDATE."""
        recent = timezone.now() - timedelta(minutes=5)
        pose = enregistrer_connexion_portail(self.compte.id, recent)
        self.assertIsNone(pose)

    def test_lhorodatage_est_rafraichi_au_dela_de_la_periode(self):
        vieux = timezone.now() - timedelta(days=3)
        pose = enregistrer_connexion_portail(self.compte.id, vieux)
        self.assertIsNotNone(pose)
        self.compte.refresh_from_db()
        self.assertGreater(self.compte.derniere_connexion, vieux)

    def test_un_compte_absent_ne_casse_rien(self):
        self.assertIsNone(enregistrer_connexion_portail(None, None))


# ── (b) PORT-15 — plus aucune URL /media/ publiée ──────────────────────────

class LienDocumentPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('aud148-co-doc', 'AUD148 Documents')
        self.client_crm = make_client_crm(self.co, 'Beta')
        self.responsable = CustomUser.objects.create_user(
            username='aud148-resp', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=(
                f'Bearer {AccessToken.for_user(self.responsable)}'))

    def _document_avec_fichier(self, libelle, nom_fichier):
        """Le dépôt GED (WIR94) est simulé — même patron que
        ``test_wir94_ged_routing`` : ces tests portent sur le PAYLOAD, pas sur
        le stockage objet."""
        with mock.patch('apps.ged.services.deposit_document',
                        side_effect=RuntimeError('GED hors périmètre')):
            return DocumentClientPortail.objects.create(
                company=self.co, client_id=self.client_crm.id,
                libelle=libelle,
                fichier=SimpleUploadedFile(nom_fichier, b'contenu'))

    def test_le_payload_ne_publie_plus_lurl_brute_du_filefield(self):
        """ROUGE avant AUD148 : `fichier` sortait en `/media/…`, lien mort."""
        self._document_avec_fichier('Facture ONEE', 'facture.txt')

        res = self.api.get('/api/django/portail/documents-client-portail/')

        self.assertEqual(res.status_code, 200, res.content)
        corps = res.content.decode('utf-8', 'replace')
        self.assertNotIn('/media/', corps)
        self.assertNotIn('portail_docs', corps)

    def test_le_payload_dit_quun_binaire_existe_sans_donner_son_url(self):
        self._document_avec_fichier('Avec binaire', 'plan.txt')

        res = self.api.get('/api/django/portail/documents-client-portail/')
        ligne = (res.data.get('results') or res.data)[0]
        self.assertTrue(ligne['fichier_present'])
        self.assertNotIn('fichier', ligne)

    def test_sans_document_ged_aucun_lien_nest_propose(self):
        DocumentClientPortail.objects.create(
            company=self.co, client_id=self.client_crm.id, libelle='Sans GED')

        res = self.api.get('/api/django/portail/documents-client-portail/')
        ligne = (res.data.get('results') or res.data)[0]
        self.assertIsNone(ligne['lien_ged'])
        self.assertFalse(ligne['fichier_present'])
