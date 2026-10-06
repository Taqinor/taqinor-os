"""ADOC19 — chaque changement old→new d'un document GED est journalisé.

Constat C-ADOC-021 de l'audit documents (2026-10-05) : aucun renommage,
déplacement, assignation, tag, corbeille ou opération en lot n'apparaissait
dans la timeline du document.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged.models import (
    Cabinet, Document, DocumentActivity, DocumentTag, Folder,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/documents/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ChatterOldNewTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc19', defaults={'nom': 'ADOC19'})[0]
        self.resp = User.objects.create_user(
            username='adoc19-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.u = User.objects.create_user(
            username='adoc19-u', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.f1 = Folder.objects.create(company=self.co, cabinet=cab, nom='F1')
        self.f2 = Folder.objects.create(company=self.co, cabinet=cab, nom='F2')
        self.doc = Document.objects.create(
            company=self.co, folder=self.f1, nom='Contrat A')
        self.tag = DocumentTag.objects.create(company=self.co, nom='Urgent')

    def test_sept_gestes_journalises(self):
        api = auth(self.resp)
        url = f'{BASE}{self.doc.pk}/'
        etapes = [
            api.patch(url, {'nom': 'Contrat B'}, format='json'),
            api.post(f'{url}deplacer/', {'folder': self.f2.pk}, format='json'),
            api.post(f'{url}assigner/', {'proprietaire': self.u.pk},
                     format='json'),
            api.post(f'{url}tagger/', {'tag': self.tag.pk}, format='json'),
            api.post(f'{url}mettre-en-corbeille/', {}, format='json'),
            api.post(f'{url}restaurer-corbeille/', {}, format='json'),
            api.post(f'{BASE}operations-lot/', {
                'documents': [self.doc.pk], 'operation': 'deplacer',
                'params': {'folder': self.f1.pk}}, format='json'),
        ]
        for resp in etapes:
            self.assertIn(resp.status_code, (200, 201), resp.content)
        lignes = list(DocumentActivity.objects.filter(
            document=self.doc, type_evenement='modification'
        ).order_by('created_at', 'id'))
        messages = [ligne.message for ligne in lignes]
        self.assertEqual(len(lignes), 7, messages)
        self.assertEqual(messages[0], 'nom : Contrat A → Contrat B')
        self.assertEqual(messages[1], 'dossier : F1 → F2')
        self.assertEqual(messages[2], 'propriétaire : — → adoc19-u')
        self.assertEqual(messages[3], 'tag Urgent : absent → posé')
        self.assertEqual(messages[4], 'corbeille : non → oui')
        self.assertEqual(messages[5], 'corbeille : oui → non')
        self.assertEqual(messages[6], 'dossier : F2 → F1')
        self.assertTrue(all(ligne.utilisateur_id == self.resp.pk
                            for ligne in lignes))
        timeline = api.get(f'{url}timeline/')
        self.assertEqual(timeline.status_code, 200)
        self.assertIn('nom : Contrat A → Contrat B', str(timeline.data))
