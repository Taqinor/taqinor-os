"""Tests NTPRT35 — widget « Satisfaction » post-interaction (portail client).

Critère d'acceptation : « le prompt n'apparaît qu'une fois par événement
(jamais répété à chaque connexion) ». On le vérifie SANS aucun état de
session : une fois répondue, l'enquête sort du sélecteur — la « reconnexion »
est simulée par un nouveau client HTTP.

L'autre enjeu est l'isolation : l'enquête d'un autre client (ou d'une autre
société) est INTROUVABLE, en lecture comme en écriture.

Run :
    python manage.py test apps.portail.tests.test_ntprt35_satisfaction -v2
"""
import itertools

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.marketing.models import EnqueteNPS
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from authentication.models import Company, CustomUser

URL = '/api/django/portail/satisfaction/'
URL_REPONDRE = f'{URL}repondre/'

_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}

#: Ids de clients FICTIFS : `EnqueteNPS.client_id` est une référence opaque
#: (PositiveIntegerField, cross-app) — aucun `crm.Client` n'est requis ici.
CLIENT_A = 4001
CLIENT_B = 4002


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def api_pour(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def make_enquete(company, client_id):
    return EnqueteNPS.objects.create(
        company=company, client_id=client_id, chantier_id=next(_seq) + 9000,
        statut=EnqueteNPS.Statut.ENVOYEE)


class SatisfactionPromptTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt35-co', 'NTPRT35 Société')
        self.user = make_portal_user(
            self.company, 'ntprt35-c', CustomUser.PORTEE_PORTAIL_CLIENT,
            CLIENT_A)
        self.api = api_pour(self.user)

    def test_sans_enquete_le_prompt_ne_s_affiche_pas(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNone(res.data['enquete'])

    def test_une_enquete_en_attente_est_proposee(self):
        enquete = make_enquete(self.company, CLIENT_A)
        res = self.api.get(URL)
        self.assertEqual(res.data['enquete']['id'], enquete.id)
        self.assertEqual(res.data['enquete']['chantier_id'],
                         enquete.chantier_id)

    def test_le_prompt_ne_revient_jamais_apres_reponse(self):
        """Critère d'acceptation : une fois par ÉVÉNEMENT."""
        enquete = make_enquete(self.company, CLIENT_A)
        res = self.api.post(URL_REPONDRE, {
            'enquete_id': enquete.id, 'score': 9,
            'commentaire': 'Chantier impeccable.'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

        enquete.refresh_from_db()
        self.assertEqual(enquete.statut, EnqueteNPS.Statut.REPONDUE)
        self.assertEqual(enquete.score, 9)
        self.assertEqual(enquete.commentaire, 'Chantier impeccable.')

        # « Reconnexion » = nouveau client HTTP, aucun état local partagé.
        self.assertIsNone(api_pour(self.user).get(URL).data['enquete'])

    def test_l_enquete_d_un_autre_client_est_invisible(self):
        make_enquete(self.company, CLIENT_B)
        self.assertIsNone(self.api.get(URL).data['enquete'])

    def test_repondre_a_l_enquete_d_un_autre_client_est_404(self):
        autre = make_enquete(self.company, CLIENT_B)
        res = self.api.post(URL_REPONDRE,
                            {'enquete_id': autre.id, 'score': 10},
                            format='json')
        self.assertEqual(res.status_code, 404)
        autre.refresh_from_db()
        self.assertEqual(autre.statut, EnqueteNPS.Statut.ENVOYEE)
        self.assertIsNone(autre.score)

    def test_repondre_a_l_enquete_d_une_autre_societe_est_404(self):
        autre_co = make_company('ntprt35-co-b', 'NTPRT35 Société B')
        etrangere = make_enquete(autre_co, CLIENT_A)
        res = self.api.post(URL_REPONDRE,
                            {'enquete_id': etrangere.id, 'score': 10},
                            format='json')
        self.assertEqual(res.status_code, 404)
        etrangere.refresh_from_db()
        self.assertEqual(etrangere.statut, EnqueteNPS.Statut.ENVOYEE)

    def test_note_hors_bornes_nomme_le_champ_fautif(self):
        enquete = make_enquete(self.company, CLIENT_A)
        for mauvaise in (11, -1, 'neuf'):
            res = self.api.post(URL_REPONDRE,
                                {'enquete_id': enquete.id,
                                 'score': mauvaise}, format='json')
            self.assertEqual(res.status_code, 400, res.data)
            self.assertIn('score', res.data)
        enquete.refresh_from_db()
        self.assertEqual(enquete.statut, EnqueteNPS.Statut.ENVOYEE)

    def test_un_compte_fournisseur_est_refuse(self):
        f = make_portal_user(
            self.company, 'ntprt35-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        api = api_pour(f)
        self.assertEqual(api.get(URL).status_code, 403)
        self.assertEqual(
            api.post(URL_REPONDRE, {'enquete_id': 1, 'score': 5},
                     format='json').status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))


class LienAvisGoogleTests(TestCase):
    """FG239 reste un ROUTAGE gaté par une simple URL société — jamais une API
    payante. Sans URL configurée : aucun lien, aucune erreur."""

    def setUp(self):
        self.company = make_company('ntprt35g-co', 'NTPRT35g Société')
        self.user = make_portal_user(
            self.company, 'ntprt35g-c', CustomUser.PORTEE_PORTAIL_CLIENT,
            CLIENT_A)
        self.api = api_pour(self.user)

    def _repondre(self, score):
        enquete = make_enquete(self.company, CLIENT_A)
        return self.api.post(URL_REPONDRE,
                             {'enquete_id': enquete.id, 'score': score},
                             format='json')

    def test_sans_url_configuree_aucun_lien(self):
        with override_settings(GOOGLE_REVIEW_URL=''):
            res = self._repondre(10)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['lien_avis_google'], '')

    def test_un_promoteur_recoit_le_lien(self):
        with override_settings(
                GOOGLE_REVIEW_URL='https://exemple.test/avis'):
            res = self._repondre(10)
        self.assertEqual(res.data['lien_avis_google'],
                         'https://exemple.test/avis')

    def test_un_detracteur_ne_recoit_pas_le_lien(self):
        """On ne route JAMAIS un client mécontent vers un avis public."""
        with override_settings(
                GOOGLE_REVIEW_URL='https://exemple.test/avis'):
            res = self._repondre(3)
        self.assertEqual(res.data['lien_avis_google'], '')
