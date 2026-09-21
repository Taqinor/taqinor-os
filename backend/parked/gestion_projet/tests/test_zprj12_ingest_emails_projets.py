"""Tests de la création de tâches par e-mail entrant (alias projet) (ZPRJ12).

Réutilise le MÊME mécanisme d'ingestion que ``apps.ventes.inbound_email``
(no-op propre sans clé/hôte configuré). Couvre : un e-mail vers l'alias d'un
projet crée exactement une tâche du bon projet/société, alias inconnu ignoré
proprement, ingestion non configurée = no-op, champ posé/filtrable, unique par
société quand renseigné.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import Projet, Tache


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class IngestionNonConfigureeTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z12-noconf', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z12-0', nom='P',
            alias_email='projet0@taqinor.ma')

    def test_noop_sans_configuration(self):
        self.assertFalse(services.is_email_ingestion_configured())
        tache = services.ingest_email_projet(
            self.co, to_alias='projet0@taqinor.ma', subject='Sujet',
            body='Corps')
        self.assertIsNone(tache)
        self.assertEqual(Tache.objects.filter(projet=self.projet).count(), 0)


@override_settings(BREVO_INBOUND_SECRET='test-secret')
class IngestEmailProjetServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z12-svc', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z12', nom='P',
            alias_email='projet1@taqinor.ma')

    def test_email_vers_alias_cree_tache_bon_projet(self):
        tache = services.ingest_email_projet(
            self.co, to_alias='PROJET1@taqinor.ma', subject='Fuite toit',
            body='Il y a une fuite', from_email='client@example.com')
        self.assertIsNotNone(tache)
        self.assertEqual(tache.projet_id, self.projet.id)
        self.assertEqual(tache.company_id, self.co.id)
        self.assertEqual(tache.libelle, 'Fuite toit')
        self.assertEqual(tache.statut, Tache.Statut.A_FAIRE)
        self.assertIn('client@example.com', tache.description)

    def test_alias_inconnu_ignore_proprement(self):
        tache = services.ingest_email_projet(
            self.co, to_alias='inconnu@taqinor.ma', subject='X', body='Y')
        self.assertIsNone(tache)
        self.assertEqual(Tache.objects.count(), 0)

    def test_alias_dune_autre_societe_ignore(self):
        autre_co = make_company('gp-z12-autre', 'Autre')
        tache = services.ingest_email_projet(
            autre_co, to_alias='projet1@taqinor.ma', subject='X', body='Y')
        self.assertIsNone(tache)


@override_settings(BREVO_INBOUND_SECRET='test-secret')
class IngestEmailsProjetsCommandTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z12-cmd', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z12-C', nom='P',
            alias_email='cmd@taqinor.ma')

    def test_commande_cree_tache(self):
        out = StringIO()
        call_command(
            'ingest_emails_projets', company='gp-z12-cmd',
            to='cmd@taqinor.ma', subject='Objet', body='Corps',
            **{'from': 'x@example.com'}, stdout=out)
        self.assertEqual(Tache.objects.filter(projet=self.projet).count(), 1)
        self.assertIn('créée', out.getvalue())


class AliasEmailUniciteTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z12-uniq', 'S')

    def test_deux_projets_sans_alias_ok(self):
        Projet.objects.create(company=self.co, code='P-U1', nom='A')
        Projet.objects.create(company=self.co, code='P-U2', nom='B')
        self.assertEqual(Projet.objects.filter(company=self.co).count(), 2)

    def test_meme_alias_deux_projets_leve(self):
        Projet.objects.create(
            company=self.co, code='P-U3', nom='A', alias_email='dup@t.ma')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Projet.objects.create(
                company=self.co, code='P-U4', nom='B', alias_email='dup@t.ma')
