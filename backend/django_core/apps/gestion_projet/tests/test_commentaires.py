"""Tests des commentaires & @mentions (PROJ34).

``company`` et ``auteur`` sont posés côté serveur ; les @mentions sont
restreintes à la MÊME société. La cible précise est une référence LÂCHE typée.

Couvre : création (auteur/company serveur) ; @mentions même-société (refus
cross-tenant 400) ; filtre par cible (cible_type+cible_id) et par mention ;
scoping multi-société ; accès Administrateur/Responsable (403 pour ``normal``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import CommentaireProjet, Projet

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CommentaireApiTests(TestCase):
    BASE = '/api/django/gestion-projet/commentaires/'

    def setUp(self):
        self.co_a = make_company('gp-cmt-a', 'A')
        self.co_b = make_company('gp-cmt-b', 'B')
        self.user_a = make_user(self.co_a, 'cmt-a')
        self.collegue = make_user(self.co_a, 'cmt-collegue')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_creation_auteur_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id,
            'texte': 'Bien noté @collegue',
            'mentions': [self.collegue.id],
            'auteur': 99999,  # posté faux — ignoré.
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cmt = CommentaireProjet.objects.get(id=resp.data['id'])
        self.assertEqual(cmt.company_id, self.co_a.id)
        self.assertEqual(cmt.auteur_id, self.user_a.id)
        self.assertEqual(list(cmt.mentions.values_list('id', flat=True)),
                         [self.collegue.id])

    def test_mention_autre_societe_refusee(self):
        etranger = make_user(self.co_b, 'cmt-etranger')
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'projet': self.projet.id, 'texte': 'x',
            'mentions': [etranger.id],
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_cible(self):
        CommentaireProjet.objects.create(
            company=self.co_a, projet=self.projet, texte='sur tâche 5',
            cible_type=CommentaireProjet.CibleType.TACHE, cible_id=5)
        CommentaireProjet.objects.create(
            company=self.co_a, projet=self.projet, texte='sur projet')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}?cible_type=tache&cible_id=5')
        self.assertEqual(resp.status_code, 200)
        textes = [c['texte'] for c in rows(resp)]
        self.assertEqual(textes, ['sur tâche 5'])

    def test_filtre_mention(self):
        cmt = CommentaireProjet.objects.create(
            company=self.co_a, projet=self.projet, texte='hello')
        cmt.mentions.add(self.collegue)
        CommentaireProjet.objects.create(
            company=self.co_a, projet=self.projet, texte='other')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}?mention={self.collegue.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_scoping_isolation(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        CommentaireProjet.objects.create(
            company=self.co_b, projet=autre, texte='B')
        CommentaireProjet.objects.create(
            company=self.co_a, projet=self.projet, texte='A')
        api = auth(self.user_a)
        resp = api.get(self.BASE)
        self.assertEqual(len(rows(resp)), 1)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'cmt-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)
