"""Tests NTPRT10 — « Mes devis » du portail client authentifié.

Le cœur de ces tests est l'ISOLATION : un compte portail ne doit voir et
n'accepter QUE les devis de SON client, et le PDF canonique ``/proposal``
(règle #4) doit s'ouvrir à ce client-là et à personne d'autre.

Couvre :

* la liste est bornée au client rattaché (jamais un devis d'un autre client de
  la MÊME société — le piège le plus facile à laisser passer) ;
* les BROUILLONS internes ne sortent jamais vers le portail ;
* un compte portail FOURNISSEUR/PARTENAIRE est refusé (403) : « portail » ne
  suffit pas, la portée doit être EXACTEMENT ``portail_client`` ;
* un compte portail SANS rattachement (``portail_client_id`` nul) est refusé ;
* un utilisateur INTERNE est refusé sur les routes portail ;
* ``/proposal`` : le client propriétaire passe, un autre client reçoit 404
  (aucun oracle d'existence), l'interne reste inchangé ;
* l'acceptation exige nom + consentement EXPLICITE, bascule le devis par le
  chemin unique de ``ventes`` et est idempotente.

Run :
    python manage.py test apps.portail.tests.test_ntprt10_mes_devis -v2
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    PORTAIL_PARTENAIRE_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    ROLE_PORTAIL_PARTENAIRE,
    Role,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    """Société de test — slug EXPLICITE et DISTINCT par appelant.

    Un slug généré identique entre deux « sociétés » ferait passer un test
    d'isolation croisée qui ne teste en réalité qu'une seule société.
    """
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'NTPRT10-{n}',
        email=f'ntprt10-{company.id}-{n}@example.invalid')


def make_devis(company, client, statut=Devis.Statut.ENVOYE):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-NTPRT10-{n}', client=client,
        statut=statut, taux_tva=Decimal('20'))


# Portée portail → (nom du rôle système NTPRT1, champ d'id, code permission).
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


def make_interne(company, username, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=f'role-{username}',
        defaults={'permissions': list(permissions)})
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)


class MesDevisIsolationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt10-co-a', 'NTPRT10 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.devis_a = make_devis(self.company, self.client_a)
        self.devis_b = make_devis(self.company, self.client_b)
        self.brouillon_a = make_devis(
            self.company, self.client_a, statut=Devis.Statut.BROUILLON)
        self.user_a = make_portal_user(
            self.company, 'ntprt10-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()

    def test_liste_bornee_au_client_rattache(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-devis/')

        self.assertEqual(res.status_code, 200)
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertIn(self.devis_a.id, ids)
        # Devis d'un AUTRE client de la MÊME société : jamais visible.
        self.assertNotIn(self.devis_b.id, ids)

    def test_les_brouillons_internes_ne_sortent_jamais(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-devis/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.brouillon_a.id, ids)

    def test_aucun_champ_de_cout_dans_le_payload(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-devis/')
        corps = str(res.data)
        for interdit in ('prix_achat', 'marge', 'prix_revendeur'):
            self.assertNotIn(interdit, corps)

    def test_detail_d_un_devis_d_autrui_est_introuvable(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(
            f'/api/django/portail/mes-devis/{self.devis_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_compte_portail_fournisseur_refuse(self):
        fournisseur = make_portal_user(
            self.company, 'ntprt10-portail-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        self.api.force_authenticate(user=fournisseur)
        res = self.api.get('/api/django/portail/mes-devis/')
        self.assertEqual(res.status_code, 403)

    def test_compte_portail_partenaire_refuse(self):
        partenaire = make_portal_user(
            self.company, 'ntprt10-portail-p',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, 1)
        self.api.force_authenticate(user=partenaire)
        res = self.api.get('/api/django/portail/mes-devis/')
        self.assertEqual(res.status_code, 403)

    def test_compte_portail_sans_rattachement_refuse(self):
        orphelin = make_portal_user(
            self.company, 'ntprt10-orphelin',
            CustomUser.PORTEE_PORTAIL_CLIENT, None)
        self.api.force_authenticate(user=orphelin)
        res = self.api.get('/api/django/portail/mes-devis/')
        # Refusé — surtout PAS « tout voir » faute de filtre.
        self.assertEqual(res.status_code, 403)

    def test_utilisateur_interne_refuse(self):
        interne = make_interne(self.company, 'ntprt10-interne',
                               ['ventes_voir', 'roles_gerer'])
        self.api.force_authenticate(user=interne)
        res = self.api.get('/api/django/portail/mes-devis/')
        self.assertEqual(res.status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get('/api/django/portail/mes-devis/')
        self.assertIn(res.status_code, (401, 403))

    def test_client_d_une_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt10-co-b', 'NTPRT10 Société B')
        client_autre = make_client(autre, 'Gamma')
        make_devis(autre, client_autre)
        etranger = make_portal_user(
            autre, 'ntprt10-portail-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            client_autre.id)

        self.api.force_authenticate(user=etranger)
        res = self.api.get('/api/django/portail/mes-devis/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.devis_a.id, ids)
        self.assertNotIn(self.devis_b.id, ids)


class ProposalPdfPortailTests(TestCase):
    """Règle #4 — ``/proposal`` reste l'unique rendu, ouvert au PROPRIÉTAIRE."""

    def setUp(self):
        self.company = make_company('ntprt10-pdf-co', 'NTPRT10 PDF')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.devis_a = make_devis(self.company, self.client_a)
        self.user_a = make_portal_user(
            self.company, 'ntprt10-pdf-a', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_a.id)
        self.user_b = make_portal_user(
            self.company, 'ntprt10-pdf-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_b.id)
        self.url = f'/api/django/ventes/devis/{self.devis_a.id}/proposal/'
        self.api = APIClient()

    def _stub_pdf(self):
        """Neutralise le moteur PDF : ce test porte sur la GARDE, pas le rendu."""
        return patch(
            'apps.ventes.quote_engine.generate_premium_devis_pdf',
            return_value='cle-bidon')

    def test_le_client_proprietaire_atteint_son_pdf(self):
        self.api.force_authenticate(user=self.user_a)
        with self._stub_pdf(), patch(
                'apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF-'):
            res = self.api.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def test_un_autre_client_recoit_404_pas_403(self):
        """Aucun oracle d'existence : le devis d'autrui est INTROUVABLE."""
        self.api.force_authenticate(user=self.user_b)
        res = self.api.get(self.url)
        self.assertEqual(res.status_code, 404)

    def test_le_client_ne_peut_pas_ecrire_par_ce_chemin(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.post(self.url, {}, format='json')
        self.assertIn(res.status_code, (403, 405))

    def test_le_client_ne_voit_pas_la_liste_interne_des_devis(self):
        """La garde interne (`IsAnyRole`) exclut les comptes portail (NTPRT5)."""
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/ventes/devis/')
        self.assertEqual(res.status_code, 403)

    def test_interne_responsable_inchange(self):
        interne = make_interne(self.company, 'ntprt10-pdf-resp',
                               ['ventes_voir', 'ventes_creer'])
        self.api.force_authenticate(user=interne)
        with self._stub_pdf(), patch(
                'apps.ventes.utils.pdf.download_pdf', return_value=b'%PDF-'):
            res = self.api.get(self.url)
        self.assertEqual(res.status_code, 200)


class AccepterDevisPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt10-acc-co', 'NTPRT10 Acceptation')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.devis = make_devis(self.company, self.client_a)
        self.user_a = make_portal_user(
            self.company, 'ntprt10-acc-a', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_a.id)
        self.user_b = make_portal_user(
            self.company, 'ntprt10-acc-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_b.id)
        self.url = f'/api/django/portail/mes-devis/{self.devis.id}/accepter/'
        self.api = APIClient()

    def test_acceptation_bascule_le_devis_par_le_chemin_unique(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.post(
            self.url, {'nom': 'Sami Client', 'consent_esign': True},
            format='json')

        self.assertEqual(res.status_code, 200, res.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.devis.accepte_par_nom, 'Sami Client')

    def test_trace_portail_posee(self):
        from apps.portail.models import AcceptationDevisPortail
        self.api.force_authenticate(user=self.user_a)
        self.api.post(self.url, {'nom': 'Sami', 'consent_esign': True},
                      format='json')
        acc = AcceptationDevisPortail.objects.get(
            company=self.company, devis=self.devis)
        self.assertTrue(acc.accepte)
        self.assertEqual(acc.nom_signataire, 'Sami')

    def test_consentement_explicite_obligatoire(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.post(self.url, {'nom': 'Sami'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_nom_obligatoire(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.post(self.url, {'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 400)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_un_autre_client_ne_peut_pas_accepter(self):
        self.api.force_authenticate(user=self.user_b)
        res = self.api.post(
            self.url, {'nom': 'Intrus', 'consent_esign': True}, format='json')
        self.assertEqual(res.status_code, 404)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)

    def test_idempotent(self):
        self.api.force_authenticate(user=self.user_a)
        payload = {'nom': 'Sami', 'consent_esign': True}
        premier = self.api.post(self.url, payload, format='json')
        second = self.api.post(self.url, payload, format='json')
        self.assertEqual(premier.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
