"""Tests XQHS8 — Registre des exigences légales toutes thématiques + pack Maroc.

Couvre :

* le registre couvre les 5 thématiques (environnement/sécurité/travail/
  technique/autre) sur le même modèle ``ConformiteEnvironnementale`` ;
* l'enregistrement d'une évaluation périodique de conformité ;
* le seed marocain idempotent, additif, flagué "applicabilité à confirmer" ;
* le scoping société.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import ConformiteEnvironnementale
from apps.qhse.services import enregistrer_evaluation_conformite


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ThematiqueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs8-them', 'CoXqhs8Them')

    def test_cree_exigence_securite(self):
        conf = ConformiteEnvironnementale.objects.create(
            company=self.company, intitule='Vérif électrique annuelle',
            type_conformite=ConformiteEnvironnementale.TypeConformite.
            VERIFICATION_ELECTRIQUE,
            thematique=ConformiteEnvironnementale.Thematique.SECURITE)
        self.assertEqual(
            conf.thematique, ConformiteEnvironnementale.Thematique.SECURITE)

    def test_defaut_environnement_inchange(self):
        conf = ConformiteEnvironnementale.objects.create(
            company=self.company, intitule='Autorisation env')
        self.assertEqual(
            conf.thematique, ConformiteEnvironnementale.Thematique.ENVIRONNEMENT)

    def test_toutes_thematiques_disponibles(self):
        valeurs = {c.value for c in ConformiteEnvironnementale.Thematique}
        self.assertEqual(
            valeurs,
            {'environnement', 'securite', 'travail', 'technique', 'autre'})


class EnregistrerEvaluationConformiteTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs8-eval', 'CoXqhs8Eval')

    def test_enregistre_evaluation(self):
        conf = ConformiteEnvironnementale.objects.create(
            company=self.company, intitule='CSH trimestriel',
            thematique=ConformiteEnvironnementale.Thematique.TRAVAIL)
        enregistrer_evaluation_conformite(
            conf, 'Conforme', date='2026-06-01')
        conf.refresh_from_db()
        self.assertEqual(conf.resultat_derniere_evaluation, 'Conforme')
        self.assertEqual(str(conf.date_derniere_evaluation), '2026-06-01')

    def test_evaluation_ne_change_pas_statut_declare(self):
        conf = ConformiteEnvironnementale.objects.create(
            company=self.company, intitule='Test',
            statut=ConformiteEnvironnementale.Statut.CONFORME)
        enregistrer_evaluation_conformite(conf, 'Non conforme')
        conf.refresh_from_db()
        self.assertEqual(conf.statut, ConformiteEnvironnementale.Statut.CONFORME)


class SeedExigencesMarocTests(TestCase):
    def test_seed_cree_des_exigences(self):
        company = make_company('co-xqhs8-seed', 'CoXqhs8Seed')
        out = StringIO()
        call_command('seed_exigences_maroc', '--company', company.slug, stdout=out)
        qs = ConformiteEnvironnementale.objects.filter(company=company)
        self.assertGreater(qs.count(), 0)

    def test_seed_flague_applicabilite_a_confirmer(self):
        company = make_company('co-xqhs8-seed-flag', 'CoXqhs8SeedFlag')
        call_command(
            'seed_exigences_maroc', '--company', company.slug, stdout=StringIO())
        for conf in ConformiteEnvironnementale.objects.filter(company=company):
            self.assertIn('à confirmer', conf.notes)

    def test_seed_couvre_plusieurs_thematiques(self):
        company = make_company('co-xqhs8-seed-them', 'CoXqhs8SeedThem')
        call_command(
            'seed_exigences_maroc', '--company', company.slug, stdout=StringIO())
        thematiques = set(
            ConformiteEnvironnementale.objects.filter(company=company)
            .values_list('thematique', flat=True))
        self.assertIn('environnement', thematiques)
        self.assertIn('securite', thematiques)
        self.assertIn('travail', thematiques)

    def test_seed_idempotent(self):
        company = make_company('co-xqhs8-seed2', 'CoXqhs8Seed2')
        call_command(
            'seed_exigences_maroc', '--company', company.slug, stdout=StringIO())
        nb_avant = ConformiteEnvironnementale.objects.filter(
            company=company).count()
        call_command(
            'seed_exigences_maroc', '--company', company.slug, stdout=StringIO())
        self.assertEqual(
            ConformiteEnvironnementale.objects.filter(company=company).count(),
            nb_avant)

    def test_seed_isolation_societe(self):
        c1 = make_company('co-xqhs8-seed-a', 'CoXqhs8SeedA')
        c2 = make_company('co-xqhs8-seed-b', 'CoXqhs8SeedB')
        call_command('seed_exigences_maroc', '--company', c1.slug, stdout=StringIO())
        self.assertEqual(
            ConformiteEnvironnementale.objects.filter(company=c2).count(), 0)
