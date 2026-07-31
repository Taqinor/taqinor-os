"""Tests NTPRT11 — « Mes commandes & factures » + paiement en ligne GATÉ.

Deux exigences distinctes :

1. ISOLATION — comme NTPRT10 : un compte portail ne voit et ne paie QUE les
   factures de SON client (jamais celles d'un autre client de la même société,
   jamais d'une autre société), et la portée doit être EXACTEMENT
   ``portail_client``.
2. GATING COÛT — sans clé CMI, « Payer » ne doit JAMAIS partir en réseau : il
   crée une intention LOCALE ``initie`` et renvoie le RIB en repli, jamais une
   erreur (critère d'acceptation NTPRT11).

Run :
    python manage.py test apps.portail.tests.test_ntprt11_mes_factures -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.facturation.models import Facture
from apps.portail.models import PaiementFacturePortail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par appelant."""
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'NTPRT11-{n}',
        email=f'ntprt11-{company.id}-{n}@example.invalid')


def make_facture(company, client, statut=Facture.Statut.EMISE):
    n = next(_seq)
    return Facture.objects.create(
        company=company, reference=f'FAC-NTPRT11-{n}', client=client,
        statut=statut, montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
        montant_ttc=Decimal('1200'), taux_tva=Decimal('20'))


_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


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


class MesFacturesIsolationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt11-co-a', 'NTPRT11 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.facture_a = make_facture(self.company, self.client_a)
        self.facture_b = make_facture(self.company, self.client_b)
        self.brouillon_a = make_facture(
            self.company, self.client_a, statut=Facture.Statut.BROUILLON)
        self.user_a = make_portal_user(
            self.company, 'ntprt11-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()

    def test_liste_bornee_au_client_rattache(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-factures/')

        self.assertEqual(res.status_code, 200)
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertIn(self.facture_a.id, ids)
        self.assertNotIn(self.facture_b.id, ids)

    def test_les_brouillons_internes_ne_sortent_jamais(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-factures/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.brouillon_a.id, ids)

    def test_detail_d_une_facture_d_autrui_est_introuvable(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(
            f'/api/django/portail/mes-factures/{self.facture_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_compte_portail_fournisseur_refuse(self):
        fournisseur = make_portal_user(
            self.company, 'ntprt11-portail-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        self.api.force_authenticate(user=fournisseur)
        res = self.api.get('/api/django/portail/mes-factures/')
        self.assertEqual(res.status_code, 403)

    def test_compte_portail_sans_rattachement_refuse(self):
        orphelin = make_portal_user(
            self.company, 'ntprt11-orphelin',
            CustomUser.PORTEE_PORTAIL_CLIENT, None)
        self.api.force_authenticate(user=orphelin)
        res = self.api.get('/api/django/portail/mes-factures/')
        self.assertEqual(res.status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get('/api/django/portail/mes-factures/')
        self.assertIn(res.status_code, (401, 403))

    def test_client_d_une_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt11-co-b', 'NTPRT11 Société B')
        client_autre = make_client(autre, 'Gamma')
        etranger = make_portal_user(
            autre, 'ntprt11-portail-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            client_autre.id)
        self.api.force_authenticate(user=etranger)
        res = self.api.get('/api/django/portail/mes-factures/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.facture_a.id, ids)
        self.assertNotIn(self.facture_b.id, ids)


class PayerFacturePortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt11-pay-co', 'NTPRT11 Paiement')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.facture = make_facture(self.company, self.client_a)
        self.user_a = make_portal_user(
            self.company, 'ntprt11-pay-a', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_a.id)
        self.user_b = make_portal_user(
            self.company, 'ntprt11-pay-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_b.id)
        self.url = (
            f'/api/django/portail/mes-factures/{self.facture.id}/payer/')
        self.api = APIClient()

    @override_settings(CMI_ENABLED=False, CMI_MERCHANT_KEY='')
    def test_sans_cle_cmi_intention_locale_et_rib_jamais_d_erreur(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.post(self.url, {}, format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['paiement_en_ligne_actif'])
        self.assertEqual(res.data['statut'],
                         PaiementFacturePortail.Statut.INITIE)
        self.assertTrue(res.data['reference'])
        # Repli virement présent (RIB vide si la société ne l'a pas renseigné,
        # mais la clé existe toujours — jamais une erreur).
        self.assertIn('virement', res.data)
        self.assertIn('rib', res.data['virement'])

        paiement = PaiementFacturePortail.objects.get(
            id=res.data['paiement_id'])
        self.assertEqual(paiement.company_id, self.company.id)
        self.assertEqual(paiement.facture_id, self.facture.id)
        self.assertEqual(paiement.methode,
                         PaiementFacturePortail.Methode.VIREMENT)

    @override_settings(CMI_ENABLED=False, CMI_MERCHANT_KEY='')
    def test_le_repli_ne_deverse_pas_l_identite_legale_de_la_societe(self):
        """Un écran EXTERNE ne reçoit que bénéficiaire/banque/RIB."""
        self.api.force_authenticate(user=self.user_a)
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(set(res.data['virement'].keys()),
                         {'beneficiaire', 'banque', 'rib'})
        corps = str(res.data)
        for interdit in ('ice', 'patente', 'cnss', 'identifiant_fiscal'):
            self.assertNotIn(interdit, corps)

    def test_un_autre_client_ne_peut_pas_payer(self):
        self.api.force_authenticate(user=self.user_b)
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 404)
        self.assertFalse(
            PaiementFacturePortail.objects.filter(
                facture=self.facture).exists())

    def test_compte_portail_fournisseur_ne_peut_pas_payer(self):
        fournisseur = make_portal_user(
            self.company, 'ntprt11-pay-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        self.api.force_authenticate(user=fournisseur)
        res = self.api.post(self.url, {}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_anonyme_ne_peut_pas_payer(self):
        res = APIClient().post(self.url, {}, format='json')
        self.assertIn(res.status_code, (401, 403))
        self.assertFalse(PaiementFacturePortail.objects.exists())
