"""Tests AUD145 — UNE seule preuve d'acceptation portail par devis.

Défaut d'origine : ``AcceptationDevisPortail.objects.get_or_create(
company=…, devis=…)`` (``portail/views_client.py``) s'exécutait HORS
transaction et APRÈS ``accept_devis``, alors que ``Meta`` ne déclarait aucune
contrainte (seulement ``db_table`` et ``ordering`` — à comparer avec
``ComptePortailClient.Meta``, qui porte bien un
``UniqueConstraint(['company','client'])``). Le verrou anti-course
d'``accept_devis`` (``select_for_update`` sur le groupe de variantes) protège
le DEVIS, pas cette ligne : le second POST devenait un no-op idempotent sur le
statut mais retombait quand même sur ce ``get_or_create``. Un double-clic du
client sur « J'accepte » produisait deux preuves d'acceptation du même devis,
avec deux horodatages — une pièce juridique ambiguë.

Honnêteté sur le « rouge » : c'est
``test_la_contrainte_db_refuse_une_seconde_preuve_en_ecriture_directe`` qui
était ROUGE (aucune contrainte n'existait, la seconde insertion passait) — le
test de double-clic SÉQUENTIEL, lui, passait déjà (``get_or_create`` fait un
``get`` avant le ``create``) : c'est la COURSE, non reproductible depuis le
client de test Django synchrone, que la contrainte ferme réellement. Il est
conservé comme garde de non-régression du chemin nominal.

Run :
    python manage.py test apps.portail.tests.test_aud145_unicite_acceptation -v2
"""
import itertools
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.portail.models import AcceptationDevisPortail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    Role,
)
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD145-{n}',
        email=f'aud145-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, client_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = client_id
    user.save()
    return user


class UniciteAcceptationPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('aud145-co', 'AUD145 Société')
        self.client_crm = make_client_crm(self.company, 'Alpha')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AUD145-1',
            client=self.client_crm, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.user = make_portal_user(
            self.company, 'aud145-portail-a', self.client_crm.id)
        self.url = f'/api/django/portail/mes-devis/{self.devis.id}/accepter/'
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_double_clic_ne_produit_quune_seule_preuve(self):
        """Chemin nominal (séquentiel) : déjà vert avant AUD145, conservé comme
        garde de non-régression du rattrapage ``IntegrityError``."""
        charge = {'nom': 'Client Alpha', 'consent_esign': True}
        premier = self.api.post(self.url, charge, format='json')
        second = self.api.post(self.url, charge, format='json')

        self.assertEqual(premier.status_code, 200, premier.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(
            AcceptationDevisPortail.objects.filter(
                company=self.company, devis=self.devis).count(),
            1)

    def test_la_contrainte_db_refuse_une_seconde_preuve_en_ecriture_directe(self):
        """ROUGE avant AUD145 : la seconde insertion passait."""
        AcceptationDevisPortail.objects.create(
            company=self.company, devis=self.devis,
            nom_signataire='Client Alpha')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AcceptationDevisPortail.objects.create(
                    company=self.company, devis=self.devis,
                    nom_signataire='Doublon')

        self.assertEqual(
            AcceptationDevisPortail.objects.filter(
                company=self.company, devis=self.devis).count(),
            1)

    def test_lhorodatage_de_la_premiere_signature_est_conserve(self):
        charge = {'nom': 'Client Alpha', 'consent_esign': True}
        self.api.post(self.url, charge, format='json')
        preuve = AcceptationDevisPortail.objects.get(
            company=self.company, devis=self.devis)
        premier_horodatage = preuve.signe_le

        self.api.post(self.url, {'nom': 'Autre Nom', 'consent_esign': True},
                      format='json')

        preuve.refresh_from_db()
        self.assertEqual(preuve.signe_le, premier_horodatage)
        self.assertEqual(preuve.nom_signataire, 'Client Alpha')

    def test_deux_societes_peuvent_avoir_chacune_leur_preuve(self):
        """La contrainte est bien (société, devis), jamais (devis) seul."""
        autre = make_company('aud145-co-b', 'AUD145 Société B')
        AcceptationDevisPortail.objects.create(
            company=self.company, devis=self.devis, nom_signataire='A')
        AcceptationDevisPortail.objects.create(
            company=autre, devis=self.devis, nom_signataire='B')
        self.assertEqual(
            AcceptationDevisPortail.objects.filter(devis=self.devis).count(),
            2)

    def test_les_preuves_sans_devis_ne_se_bloquent_pas_entre_elles(self):
        """``devis`` est nullable : en PostgreSQL les NULL restent distincts."""
        AcceptationDevisPortail.objects.create(
            company=self.company, devis=None, nom_signataire='Sans devis 1')
        AcceptationDevisPortail.objects.create(
            company=self.company, devis=None, nom_signataire='Sans devis 2')
        self.assertEqual(
            AcceptationDevisPortail.objects.filter(
                company=self.company, devis__isnull=True).count(),
            2)
