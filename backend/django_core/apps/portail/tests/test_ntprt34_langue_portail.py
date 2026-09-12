"""Tests NTPRT34 — langue du portail (FR/AR), préférence PAR COMPTE.

Critère d'acceptation : « le choix de langue persiste par compte portail
(préférence utilisateur, pas cookie volatile) ». On vérifie donc que la valeur
survit à une nouvelle requête (donc à un nouvel appareil), qu'elle est
STRICTEMENT privée au compte qui l'a posée, et qu'elle n'est jamais lue du
corps de requête.

Run :
    python manage.py test apps.portail.tests.test_ntprt34_langue_portail -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.portail.models import PreferencePortail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    PORTAIL_PARTENAIRE_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    ROLE_PORTAIL_PARTENAIRE,
    Role,
)
from authentication.models import Company, CustomUser

URL = '/api/django/portail/ma-preference/'

_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_PARTENAIRE: (
        ROLE_PORTAIL_PARTENAIRE, 'portail_partenaire_id',
        PORTAIL_PARTENAIRE_PERMISSIONS),
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id=1):
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


class PreferenceLangueTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt34-co', 'NTPRT34 Société')
        self.client_user = make_portal_user(
            self.company, 'ntprt34-c', CustomUser.PORTEE_PORTAIL_CLIENT)
        self.api = api_pour(self.client_user)

    def test_sans_choix_la_langue_est_le_francais(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['langue'], 'fr')
        self.assertEqual(
            [lg['code'] for lg in res.data['langues_disponibles']],
            ['fr', 'ar'])
        # Aucune ligne créée par une simple LECTURE.
        self.assertEqual(PreferencePortail.objects.count(), 0)

    def test_le_choix_persiste_entre_deux_requetes(self):
        """Critère d'acceptation : préférence de COMPTE, pas cookie."""
        self.assertEqual(
            self.api.put(URL, {'langue': 'ar'}, format='json').status_code,
            200)

        # Nouveau client HTTP = nouvel « appareil » : aucun cookie partagé.
        autre_appareil = api_pour(self.client_user)
        self.assertEqual(autre_appareil.get(URL).data['langue'], 'ar')

    def test_la_societe_et_le_compte_viennent_du_jeton(self):
        autre = make_company('ntprt34-co-b', 'NTPRT34 Société B')
        intrus = make_portal_user(
            autre, 'ntprt34-intrus', CustomUser.PORTEE_PORTAIL_CLIENT)
        self.api.put(
            URL,
            {'langue': 'ar', 'utilisateur': intrus.id, 'company': autre.id},
            format='json')

        preference = PreferencePortail.objects.get()
        self.assertEqual(preference.utilisateur_id, self.client_user.id)
        self.assertEqual(preference.company_id, self.company.id)
        # Le compte visé par le corps n'a RIEN changé chez lui.
        self.assertEqual(api_pour(intrus).get(URL).data['langue'], 'fr')

    def test_changer_deux_fois_ne_cree_pas_deux_lignes(self):
        self.api.put(URL, {'langue': 'ar'}, format='json')
        self.api.put(URL, {'langue': 'fr'}, format='json')
        self.assertEqual(PreferencePortail.objects.filter(
            utilisateur=self.client_user).count(), 1)
        self.assertEqual(self.api.get(URL).data['langue'], 'fr')

    def test_langue_inconnue_nomme_le_champ_fautif(self):
        res = self.api.put(URL, {'langue': 'es'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('langue', res.data)
        self.assertEqual(PreferencePortail.objects.count(), 0)

    def test_les_trois_portees_portail_y_ont_droit(self):
        """La préférence d'affichage est la SEULE surface commune."""
        for portee, nom in (
                (CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 'ntprt34-f'),
                (CustomUser.PORTEE_PORTAIL_PARTENAIRE, 'ntprt34-p')):
            user = make_portal_user(self.company, nom, portee)
            api = api_pour(user)
            self.assertEqual(api.get(URL).status_code, 200)
            self.assertEqual(
                api.put(URL, {'langue': 'ar'}, format='json').status_code, 200)

    def test_un_interne_est_refuse(self):
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='role-interne-ntprt34',
            defaults={'permissions': ['crm_voir']})
        interne = CustomUser.objects.create_user(
            username='ntprt34-interne', password='motdepasse-test-1234',
            company=self.company, role=role)
        api = api_pour(interne)
        self.assertEqual(api.get(URL).status_code, 403)
        self.assertEqual(
            api.put(URL, {'langue': 'ar'}, format='json').status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))
