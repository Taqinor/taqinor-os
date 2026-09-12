"""NTSRV19 — Créer un article KB depuis un ticket résolu.

Critère d'acceptation testé : le brouillon généré contient déjà la cause et
le remède saisis sur le ticket, zéro resaisie manuelle des faits de base.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.kb.models import KbArticle, KbArticleLien

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


class TestCreerDepuisTicket(TestCase):
    URL = '/api/django/kb/articles/creer-depuis-ticket/'

    def setUp(self):
        self.company = make_company('ntsrv19-co', 'NTSRV19 Co')
        self.user = make_user(self.company, 'ntsrv19_agent')
        self.api = auth(self.user)

    def test_brouillon_contient_cause_et_remede_sans_resaisie(self):
        r = self.api.post(self.URL, {
            'ticket_id': 42, 'type_panne': 'Onduleur en panne',
            'equipement': 'Huawei SUN2000-5KTL',
            'description': "L'onduleur ne démarre plus après un orage.",
            'cause': 'Surtension réseau ayant grillé la carte AC.',
            'remede': 'Remplacement de la carte AC + mise à la terre vérifiée.',
            'derniere_note': 'Client confirme le redémarrage normal.',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        article = KbArticle.objects.get(pk=r.data['id'])
        self.assertEqual(article.statut, KbArticle.Statut.BROUILLON)
        self.assertEqual(article.titre, 'Onduleur en panne — Huawei SUN2000-5KTL')
        self.assertIn('Surtension réseau ayant grillé la carte AC.', article.corps)
        self.assertIn(
            'Remplacement de la carte AC + mise à la terre vérifiée.',
            article.corps)
        self.assertIn('Client confirme le redémarrage normal.', article.corps)
        self.assertEqual(article.company_id, self.company.id)
        self.assertEqual(article.auteur_id, self.user.id)

    def test_lien_retour_trace_la_provenance(self):
        r = self.api.post(self.URL, {
            'ticket_id': 99, 'type_panne': 'Fuite', 'equipement': 'Pompe',
            'description': 'Fuite au raccord.',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        lien = KbArticleLien.objects.get(
            article_id=r.data['id'], type_cible=KbArticleLien.TypeCible.TICKET)
        self.assertEqual(lien.cible_id, 99)
        self.assertEqual(lien.company_id, self.company.id)

    def test_ticket_id_manquant_refuse(self):
        r = self.api.post(self.URL, {'type_panne': 'X'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_titre_replie_sur_ticket_id_sans_type_panne_ni_equipement(self):
        r = self.api.post(self.URL, {
            'ticket_id': 7, 'description': 'Description seule.',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        article = KbArticle.objects.get(pk=r.data['id'])
        self.assertEqual(article.titre, 'Ticket #7')

    def test_isolation_societe(self):
        autre_co = make_company('ntsrv19-autre-co', 'NTSRV19 Autre Co')
        autre_user = make_user(autre_co, 'ntsrv19_agent_autre')
        r = auth(autre_user).post(self.URL, {
            'ticket_id': 1, 'type_panne': 'X',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        article = KbArticle.objects.get(pk=r.data['id'])
        self.assertEqual(article.company_id, autre_co.id)
        self.assertFalse(
            KbArticle.objects.filter(
                company=self.company, pk=article.id).exists())
