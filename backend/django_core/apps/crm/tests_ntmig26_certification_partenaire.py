"""NTMIG26 — couche certification sur ``crm.Partenaire``.

Critère d'acceptation : un partenaire peut porter un niveau ``certifie`` avec
2 spécialités et une date d'expiration, SANS casser les fiches existantes.

Couvre aussi : la couche certification est DISTINCTE de l'agrément FG237
(mêmes fiches, champs différents), les spécialités sont prises dans une liste
fermée, le compteur de déploiements n'est pas modifiable par requête, et une
expiration antérieure à la certification est refusée.

Run :
    python manage.py test apps.crm.tests_ntmig26_certification_partenaire -v2
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Partenaire

User = get_user_model()

PARTENAIRES = '/api/django/crm/partenaires/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntmig26CertificationTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig26', 'NTMIG26')
        self.user = User.objects.create_user(
            username='ntmig26-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = auth(self.user)
        self.partenaire = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig26-token')

    def test_fiche_existante_par_defaut_sans_certification(self):
        """Rétro-compatibilité : aucune fiche n'est modifiée par NTMIG26."""
        resp = self.api.get(f'{PARTENAIRES}{self.partenaire.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['niveau_certification'], 'aucun')
        self.assertEqual(resp.data['specialites'], [])
        self.assertEqual(resp.data['nb_deploiements_reussis'], 0)
        self.assertIsNone(resp.data['date_certification'])
        self.assertFalse(resp.data['certification_expiree'])
        # L'agrément de base FG237 est intact et INDÉPENDANT.
        self.assertEqual(resp.data['statut_onboarding'], 'prospect')

    def test_certifie_avec_deux_specialites_et_expiration(self):
        resp = self.api.patch(f'{PARTENAIRES}{self.partenaire.pk}/', {
            'niveau_certification': 'certifie',
            'specialites': ['compta', 'ventes'],
            'date_certification': '2026-01-15',
            'date_expiration_certification': '2027-01-15',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['niveau_certification'], 'certifie')
        self.assertEqual(resp.data['specialites'], ['compta', 'ventes'])
        self.assertEqual(resp.data['date_expiration_certification'],
                         '2027-01-15')
        self.assertFalse(resp.data['certification_expiree'])

        partenaire = Partenaire.objects.get(pk=self.partenaire.pk)
        self.assertEqual(partenaire.rang_certification, 2)
        # L'agrément de base n'a PAS bougé : deux couches distinctes.
        self.assertEqual(partenaire.statut_onboarding, 'prospect')

    def test_certification_expiree(self):
        self.partenaire.niveau_certification = 'or'
        self.partenaire.date_expiration_certification = (
            datetime.date(2020, 1, 1))
        self.partenaire.save()
        resp = self.api.get(f'{PARTENAIRES}{self.partenaire.pk}/')
        self.assertTrue(resp.data['certification_expiree'])

    def test_specialite_inconnue_refusee(self):
        resp = self.api.patch(f'{PARTENAIRES}{self.partenaire.pk}/', {
            'specialites': ['compta', 'astrologie'],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('specialites', resp.data)

    def test_specialites_dedoublonnees(self):
        resp = self.api.patch(f'{PARTENAIRES}{self.partenaire.pk}/', {
            'specialites': ['compta', 'compta', 'rh'],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['specialites'], ['compta', 'rh'])

    def test_specialites_non_liste_refusee(self):
        resp = self.api.patch(f'{PARTENAIRES}{self.partenaire.pk}/', {
            'specialites': 'compta',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_expiration_avant_certification_refusee(self):
        resp = self.api.patch(f'{PARTENAIRES}{self.partenaire.pk}/', {
            'date_certification': '2026-06-01',
            'date_expiration_certification': '2026-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('date_expiration_certification', resp.data)

    def test_compteur_de_deploiements_non_modifiable_par_requete(self):
        """Gonfler son propre historique ne doit pas être un simple PATCH."""
        resp = self.api.patch(f'{PARTENAIRES}{self.partenaire.pk}/', {
            'nb_deploiements_reussis': 99,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            Partenaire.objects.get(pk=self.partenaire.pk)
            .nb_deploiements_reussis, 0)

    def test_rang_certification_suit_l_echelle(self):
        attendus = {
            'aucun': 0, 'enregistre': 1, 'certifie': 2, 'or': 3, 'platine': 4}
        for niveau, rang in attendus.items():
            self.partenaire.niveau_certification = niveau
            self.assertEqual(self.partenaire.rang_certification, rang)

    def test_ancienne_route_compta_expose_les_memes_champs(self):
        resp = self.api.get(
            f'/api/django/compta/partenaires/{self.partenaire.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('niveau_certification', resp.data)
        self.assertIn('specialites', resp.data)
