"""NTPRT31 — Ressources marketing partenaire (partage GLOBAL par rôle GED).

Couvre :

* ``ged.selectors.ressources_partenaire_portail`` ne renvoie QUE les
  documents portant une ``AclGed`` EXPLICITE sur le rôle système « Portail
  partenaire » — un document « interne uniquement » (SANS cette ACL)
  n'apparaît JAMAIS (critère d'acceptation NTPRT31), même via une ACL posée
  sur un simple utilisateur ou un dossier ;
* la ressource est visible par TOUT partenaire de la société (partage
  GLOBAL, pas par partenaire) — jamais par un partenaire d'une autre société ;
* le téléchargement sert le contenu de la version courante, et 404 sur une
  ressource non partagée.

Run :
    python manage.py test apps.portail.tests.test_ntprt31_ressources_partenaire -v2
"""
import itertools
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.ged.models import AclGed, Cabinet, Document, DocumentVersion, Folder
from apps.roles.models import (
    PORTAIL_PARTENAIRE_PERMISSIONS, ROLE_PORTAIL_PARTENAIRE, Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_partenaire_user(company, username):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_PARTENAIRE,
        defaults={'permissions': list(PORTAIL_PARTENAIRE_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_PARTENAIRE
    user.portail_partenaire_id = next(_seq)
    user.save()
    return user, role


def make_document(company, nom='Fiche produit panneau.pdf'):
    n = next(_seq)
    cabinet = Cabinet.objects.create(company=company, nom=f'Cabinet-{n}')
    folder = Folder.objects.create(
        company=company, cabinet=cabinet, nom=f'Dossier-{n}')
    document = Document.objects.create(company=company, folder=folder, nom=nom)
    DocumentVersion.objects.create(
        company=company, document=document, version=1,
        file_key=f'ged/{company.id}/{n}.pdf', filename=nom,
        size=99, mime='application/pdf')
    return document


class RessourcesPartenairePortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt31-co-a', 'NTPRT31 Société A')
        self.partenaire, self.role = make_partenaire_user(
            self.company, 'ntprt31-partenaire-a')
        self.api = APIClient()
        self.api.force_authenticate(user=self.partenaire)

    def test_document_sans_acl_najamais_visible(self):
        make_document(self.company, "Argumentaire interne (pas d'ACL)")
        res = self.api.get('/api/django/portail/ressources/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['results'], [])

    def test_document_partage_avec_le_role_partenaire_visible(self):
        document = make_document(self.company, 'Logo TAQINOR.png')
        AclGed.objects.create(
            company=self.company, document=document, role=self.role)
        res = self.api.get('/api/django/portail/ressources/')
        self.assertEqual(res.status_code, 200, res.data)
        ids = [d['id'] for d in res.data['results']]
        self.assertEqual(ids, [document.id])
        self.assertEqual(res.data['results'][0]['taille'], 99)

    def test_partage_est_global_visible_par_un_autre_partenaire(self):
        document = make_document(self.company)
        AclGed.objects.create(
            company=self.company, document=document, role=self.role)
        autre_partenaire, _ = make_partenaire_user(
            self.company, 'ntprt31-partenaire-b')
        api = APIClient()
        api.force_authenticate(user=autre_partenaire)
        res = api.get('/api/django/portail/ressources/')
        ids = [d['id'] for d in res.data['results']]
        self.assertEqual(ids, [document.id])

    def test_acl_sur_un_utilisateur_ne_suffit_pas(self):
        """Un partage nominatif (utilisateur) n'ouvre PAS les ressources
        partenaire — seul le rôle système compte ici."""
        document = make_document(self.company)
        AclGed.objects.create(
            company=self.company, document=document,
            utilisateur=self.partenaire)
        res = self.api.get('/api/django/portail/ressources/')
        self.assertEqual(res.data['results'], [])

    def test_acl_sur_le_dossier_seul_ne_suffit_pas(self):
        document = make_document(self.company)
        AclGed.objects.create(
            company=self.company, folder=document.folder, role=self.role)
        res = self.api.get('/api/django/portail/ressources/')
        self.assertEqual(res.data['results'], [])

    def test_document_dune_autre_societe_invisible(self):
        autre = make_company('ntprt31-co-b', 'NTPRT31 Société B')
        _, autre_role = make_partenaire_user(autre, 'ntprt31-partenaire-c')
        document = make_document(autre)
        AclGed.objects.create(
            company=autre, document=document, role=autre_role)
        res = self.api.get('/api/django/portail/ressources/')
        self.assertEqual(res.data['results'], [])

    def test_client_ne_peut_pas_atteindre_les_ressources_partenaire(self):
        from apps.roles.models import PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT
        role_client, _ = Role.objects.get_or_create(
            company=self.company, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        client_user = CustomUser.objects.create_user(
            username='ntprt31-client', password='motdepasse-test-1234',
            company=self.company, role=role_client)
        client_user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        client_user.portail_client_id = 1
        client_user.save()
        api = APIClient()
        api.force_authenticate(user=client_user)
        res = api.get('/api/django/portail/ressources/')
        self.assertEqual(res.status_code, 403)


class TelechargerRessourcePartenaireTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt31-dl-a', 'NTPRT31 Téléchargement A')
        self.partenaire, self.role = make_partenaire_user(
            self.company, 'ntprt31-dl-partenaire')
        self.document = make_document(self.company, 'Notice technique.pdf')
        AclGed.objects.create(
            company=self.company, document=self.document, role=self.role)
        self.api = APIClient()
        self.api.force_authenticate(user=self.partenaire)

    def test_telechargement_ressource_partagee(self):
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(b'%PDF-1.4', None)):
            res = self.api.get(
                f'/api/django/portail/ressources/{self.document.id}/'
                'telecharger/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def test_telechargement_ressource_non_partagee_404(self):
        autre_document = make_document(self.company, 'Sans ACL.pdf')
        res = self.api.get(
            f'/api/django/portail/ressources/{autre_document.id}/'
            'telecharger/')
        self.assertEqual(res.status_code, 404)
