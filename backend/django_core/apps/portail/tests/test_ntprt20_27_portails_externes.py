"""Tests NTPRT20/NTPRT27 — tableaux de bord FOURNISSEUR et PARTENAIRE.

L'enjeu est la SYMÉTRIE des gardes : chaque tableau de bord n'est joignable que
par la portée EXACTE correspondante. Le piège à éviter est « c'est un compte
portail, donc ça passe » — un compte CLIENT ne doit jamais lire les chiffres
d'un fournisseur, et un fournisseur jamais ceux d'un autre fournisseur.

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt20_27_portails_externes -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import CommissionPartenaire, Partenaire
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    PORTAIL_PARTENAIRE_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    ROLE_PORTAIL_PARTENAIRE,
    Role,
)
from apps.stock.models import Fournisseur
from authentication.models import Company, CustomUser

URL_FOURNISSEUR = '/api/django/portail/fournisseur/tableau-de-bord/'
URL_PARTENAIRE = '/api/django/portail/partenaire/tableau-de-bord/'

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
    """Société de test — slug EXPLICITE et DISTINCT par appelant."""
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


def make_fournisseur(company, nom='Fournisseur'):
    n = next(_seq)
    return Fournisseur.objects.create(company=company, nom=f'{nom}-{n}')


def make_partenaire(company, nom='Partenaire'):
    n = next(_seq)
    # `Partenaire.token_acces` est UNIQUE et sans défaut : la production le pose
    # côté serveur (`PartenaireViewSet.perform_create` →
    # `secrets.token_urlsafe(32)`), donc une fixture qui l'omet insère deux fois
    # la chaîne vide et viole la contrainte. Convention déjà suivie par toutes
    # les autres fixtures `Partenaire` du repo : un jeton explicite et distinct.
    return Partenaire.objects.create(
        company=company, nom=f'{nom}-{n}', token_acces=f'tok-ntprt20-{n}')


class TableauDeBordFournisseurTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt20-co', 'NTPRT20 Société')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.user_a = make_portal_user(
            self.company, 'ntprt20-f-a',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        self.api = APIClient()

    def test_le_fournisseur_voit_son_resume(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL_FOURNISSEUR)

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['fournisseur_nom'], self.f_a.nom)
        self.assertIn('bcf_a_confirmer', res.data)

    def test_un_compte_client_est_refuse(self):
        """« C'est un compte portail » NE SUFFIT PAS : la portée doit matcher."""
        client_user = make_portal_user(
            self.company, 'ntprt20-c', CustomUser.PORTEE_PORTAIL_CLIENT, 1)
        self.api.force_authenticate(user=client_user)
        self.assertEqual(self.api.get(URL_FOURNISSEUR).status_code, 403)

    def test_un_compte_partenaire_est_refuse(self):
        p = make_portal_user(
            self.company, 'ntprt20-p', CustomUser.PORTEE_PORTAIL_PARTENAIRE, 1)
        self.api.force_authenticate(user=p)
        self.assertEqual(self.api.get(URL_FOURNISSEUR).status_code, 403)

    def test_un_interne_est_refuse(self):
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='role-interne-ntprt20',
            defaults={'permissions': ['stock_voir', 'stock_creer']})
        interne = CustomUser.objects.create_user(
            username='ntprt20-interne', password='motdepasse-test-1234',
            company=self.company, role=role)
        self.api.force_authenticate(user=interne)
        self.assertEqual(self.api.get(URL_FOURNISSEUR).status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get(URL_FOURNISSEUR)
        self.assertIn(res.status_code, (401, 403))

    def test_compte_sans_rattachement_refuse(self):
        orphelin = make_portal_user(
            self.company, 'ntprt20-orphelin',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, None)
        self.api.force_authenticate(user=orphelin)
        # Refusé — surtout PAS les chiffres de la société entière.
        self.assertEqual(self.api.get(URL_FOURNISSEUR).status_code, 403)

    def test_un_fournisseur_d_une_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt20-co-b', 'NTPRT20 Société B')
        etranger = make_portal_user(
            autre, 'ntprt20-f-etranger',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        self.api.force_authenticate(user=etranger)
        res = self.api.get(URL_FOURNISSEUR)
        # Le fournisseur n'existe pas dans SA société → résumé vide, jamais
        # les chiffres du fournisseur homonyme d'un autre tenant.
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['fournisseur_nom'], '')


class TableauDeBordPartenaireTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt27-co', 'NTPRT27 Société')
        self.p_a = make_partenaire(self.company, 'Alpha')
        self.p_b = make_partenaire(self.company, 'Beta')
        CommissionPartenaire.objects.create(
            company=self.company, partenaire=self.p_a,
            base_ht=Decimal('1000'), taux=Decimal('10'),
            montant=Decimal('100'),
            statut=CommissionPartenaire.Statut.DUE)
        CommissionPartenaire.objects.create(
            company=self.company, partenaire=self.p_b,
            base_ht=Decimal('5000'), taux=Decimal('10'),
            montant=Decimal('500'),
            statut=CommissionPartenaire.Statut.DUE)
        self.user_a = make_portal_user(
            self.company, 'ntprt27-p-a',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.p_a.id)
        self.api = APIClient()

    def test_le_partenaire_ne_voit_que_SES_commissions(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL_PARTENAIRE)

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['partenaire_nom'], self.p_a.nom)
        # 100 (le sien) et surtout PAS 600 (la somme des deux partenaires).
        self.assertEqual(Decimal(res.data['commissions_dues']),
                         Decimal('100'))

    def test_un_compte_fournisseur_est_refuse(self):
        f = make_portal_user(
            self.company, 'ntprt27-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        self.api.force_authenticate(user=f)
        self.assertEqual(self.api.get(URL_PARTENAIRE).status_code, 403)

    def test_un_compte_client_est_refuse(self):
        c = make_portal_user(
            self.company, 'ntprt27-c', CustomUser.PORTEE_PORTAIL_CLIENT, 1)
        self.api.force_authenticate(user=c)
        self.assertEqual(self.api.get(URL_PARTENAIRE).status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get(URL_PARTENAIRE)
        self.assertIn(res.status_code, (401, 403))

    def test_compte_sans_rattachement_refuse(self):
        orphelin = make_portal_user(
            self.company, 'ntprt27-orphelin',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, None)
        self.api.force_authenticate(user=orphelin)
        self.assertEqual(self.api.get(URL_PARTENAIRE).status_code, 403)

    def test_partenaire_d_une_autre_societe_voit_un_resume_vide(self):
        autre = make_company('ntprt27-co-b', 'NTPRT27 Société B')
        etranger = make_portal_user(
            autre, 'ntprt27-p-etranger',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.p_a.id)
        self.api.force_authenticate(user=etranger)
        res = self.api.get(URL_PARTENAIRE)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['partenaire_nom'], '')
        self.assertEqual(Decimal(res.data['commissions_dues']), Decimal('0'))
