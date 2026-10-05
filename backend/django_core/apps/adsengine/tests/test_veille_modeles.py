"""VEIL14 — Modèles de découverte de la veille (une migration additive).

Prouve : unicité ``(company, page_id)`` de l'annonceur (autre société → OK) ;
une même pub vue deux fois par la même requête = une ligne ; l'historique de
verdicts ne se réécrit jamais ; la migration 0057 se défait puis se refait
(aller/retour dans la transaction du test — DDL transactionnel Postgres, la
base de test n'est jamais laissée à moitié migrée).
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase

from authentication.models import Company

from apps.adsengine.models import (
    CompetitorPage, VeilleAnnonceur, VeilleDecouverte, VeillePubVue,
    VeilleRequete, VeilleVerdict,
)

TABLES = (
    'adsengine_veilledecouverte', 'adsengine_veillerequete',
    'adsengine_veilleannonceur', 'adsengine_veillepubvue',
    'adsengine_veilleverdict',
)


def creer_decouverte(company, **kw):
    valeurs = {'plafond_appels': 10, 'plafond_pages_par_requete': 3,
               'mots_cles': [{'texte': 'robe', 'pays': ['FR']}]}
    valeurs.update(kw)
    return VeilleDecouverte.objects.create(company=company, **valeurs)


class UniciteTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='A', slug='veille-mod-a')
        self.b = Company.objects.create(nom='B', slug='veille-mod-b')

    def test_annonceur_unique_par_societe_et_page(self):
        VeilleAnnonceur.objects.create(company=self.a, page_id='123')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VeilleAnnonceur.objects.create(company=self.a, page_id='123')
        # autre société : OK
        VeilleAnnonceur.objects.create(company=self.b, page_id='123')
        self.assertEqual(
            VeilleAnnonceur.objects.filter(page_id='123').count(), 2)

    def test_pub_vue_unique_par_requete(self):
        dec = creer_decouverte(self.a)
        req = VeilleRequete.objects.create(
            company=self.a, decouverte=dec, mot_cle='robe', pays='FR')
        ann = VeilleAnnonceur.objects.create(company=self.a, page_id='9')
        for _ in range(2):
            VeillePubVue.objects.get_or_create(
                company=self.a, requete=req, ad_archive_id='777',
                defaults={'annonceur': ann})
        self.assertEqual(VeillePubVue.objects.filter(requete=req).count(), 1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VeillePubVue.objects.create(
                    company=self.a, requete=req, annonceur=ann,
                    ad_archive_id='777')

    def test_requete_unique_par_decouverte_mot_cle_pays_mode(self):
        dec = creer_decouverte(self.a)
        VeilleRequete.objects.create(
            company=self.a, decouverte=dec, mot_cle='robe', pays='FR')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VeilleRequete.objects.create(
                    company=self.a, decouverte=dec, mot_cle='robe', pays='FR')
        VeilleRequete.objects.create(
            company=self.a, decouverte=dec, mot_cle='robe', pays='FR',
            search_type='KEYWORD_EXACT_PHRASE')

    def test_verdict_historique_jamais_modifie(self):
        ann = VeilleAnnonceur.objects.create(company=self.a, page_id='5')
        verdict = VeilleVerdict.objects.create(
            company=self.a, annonceur=ann, classe='vendeur',
            decide_par='regle', motif_fr='règle')
        verdict.classe = 'doublon'
        with self.assertRaises(ValidationError):
            verdict.save()
        verdict.refresh_from_db()
        self.assertEqual(verdict.classe, 'vendeur')

    def test_annonceurs_distincts_par_decouverte(self):
        dec = creer_decouverte(self.a)
        req = VeilleRequete.objects.create(
            company=self.a, decouverte=dec, mot_cle='robe', pays='FR')
        req2 = VeilleRequete.objects.create(
            company=self.a, decouverte=dec, mot_cle='robe', pays='BE')
        ann = VeilleAnnonceur.objects.create(company=self.a, page_id='1')
        ann2 = VeilleAnnonceur.objects.create(company=self.a, page_id='2')
        VeillePubVue.objects.create(company=self.a, requete=req,
                                    annonceur=ann, ad_archive_id='a1')
        VeillePubVue.objects.create(company=self.a, requete=req2,
                                    annonceur=ann, ad_archive_id='a1')
        VeillePubVue.objects.create(company=self.a, requete=req2,
                                    annonceur=ann2, ad_archive_id='a2')
        self.assertEqual(dec.annonceurs_distincts, 2)

    def test_competitor_page_intacte(self):
        # La Page suivie saisie à la main garde son unicité (company, name).
        CompetitorPage.objects.create(company=self.a, name='X')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompetitorPage.objects.create(company=self.a, name='X')


class MigrationAllerRetourTests(TestCase):
    def test_0057_se_defait_puis_se_refait(self):
        executor = MigrationExecutor(connection)
        loader = executor.loader
        cle = ('adsengine', '0057_veille_decouverte')
        migration = loader.get_migration(*cle)
        etat_apres = loader.project_state(cle)
        # L'état « avant » doit contenir TOUTES les dépendances de 0057 (dont
        # core.BackgroundJob), pas seulement l'ascendance de 0056.
        etat_avant = loader.project_state([
            ('adsengine', '0056_pub128_field_test_result'),
            ('core', '0033_ntplt29_backgroundjob'),
            ('authentication', '0001_initial'),
        ])

        with connection.schema_editor() as editor:
            migration.unapply(etat_apres.clone(), editor)
        tables = set(connection.introspection.table_names())
        for table in TABLES:
            self.assertNotIn(table, tables)

        with connection.schema_editor() as editor:
            migration.apply(etat_avant.clone(), editor)
        tables = set(connection.introspection.table_names())
        for table in TABLES:
            self.assertIn(table, tables)
