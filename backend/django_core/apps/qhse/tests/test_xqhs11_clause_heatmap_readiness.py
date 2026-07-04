"""Tests XQHS11 — Mapping clauses ISO multi-référentiel + heatmap + readiness.

Couvre :

* un critère mappe une clause + référentiel (nullable, additif) ;
* le seed idempotent de clauses (HLS partagée) ;
* la heatmap des non-conformités d'audit par clause ;
* le readiness multi-référentiel (% de clauses couvertes) ;
* le scoping société.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import (
    Audit, ClauseNorme, CritereAudit, GrilleAudit, ReponseCritere,
)
from apps.qhse.selectors import (
    constats_par_clause, readiness_multi_referentiel,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_grille(company):
    return GrilleAudit.objects.create(company=company, nom='Grille ISO')


def make_critere(company, grille, clause, referentiel='9001', intitule='C1'):
    return CritereAudit.objects.create(
        company=company, grille=grille, intitule=intitule,
        clause=clause, referentiel=referentiel)


def make_audit(company, grille):
    return Audit.objects.create(company=company, grille=grille)


class SeedClausesNormeTests(TestCase):
    def test_seed_cree_clauses(self):
        company = make_company('co-xqhs11-seed', 'CoXqhs11Seed')
        call_command('seed_clauses_norme', '--company', company.slug, stdout=StringIO())
        self.assertGreater(
            ClauseNorme.objects.filter(company=company).count(), 0)

    def test_seed_couvre_3_referentiels(self):
        company = make_company('co-xqhs11-seed3', 'CoXqhs11Seed3')
        call_command('seed_clauses_norme', '--company', company.slug, stdout=StringIO())
        refs = set(
            ClauseNorme.objects.filter(company=company)
            .values_list('referentiel', flat=True))
        self.assertEqual(refs, {'9001', '14001', '45001'})

    def test_seed_idempotent(self):
        company = make_company('co-xqhs11-seed-idem', 'CoXqhs11SeedIdem')
        call_command('seed_clauses_norme', '--company', company.slug, stdout=StringIO())
        nb = ClauseNorme.objects.filter(company=company).count()
        call_command('seed_clauses_norme', '--company', company.slug, stdout=StringIO())
        self.assertEqual(ClauseNorme.objects.filter(company=company).count(), nb)


class ConstatsParClauseTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs11-heat', 'CoXqhs11Heat')
        self.grille = make_grille(self.company)

    def test_agrege_non_conformes_par_clause(self):
        c1 = make_critere(self.company, self.grille, '8.5.1')
        c2 = make_critere(self.company, self.grille, '8.5.1')
        audit = make_audit(self.company, self.grille)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=c1,
            resultat=ReponseCritere.Resultat.NON_CONFORME)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=c2,
            resultat=ReponseCritere.Resultat.NON_CONFORME)
        result = constats_par_clause(self.company)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['nb_non_conformes'], 2)

    def test_exclut_criteres_sans_clause(self):
        critere = CritereAudit.objects.create(
            company=self.company, grille=self.grille, intitule='Sans clause')
        audit = make_audit(self.company, self.grille)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=critere,
            resultat=ReponseCritere.Resultat.NON_CONFORME)
        result = constats_par_clause(self.company)
        self.assertEqual(result, [])

    def test_exclut_conformes(self):
        critere = make_critere(self.company, self.grille, '9.1')
        audit = make_audit(self.company, self.grille)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=critere,
            resultat=ReponseCritere.Resultat.CONFORME)
        result = constats_par_clause(self.company)
        self.assertEqual(result, [])

    def test_filtre_referentiel(self):
        c1 = make_critere(self.company, self.grille, '6.1.2', referentiel='9001')
        c2 = make_critere(self.company, self.grille, '6.1.2', referentiel='14001')
        audit = make_audit(self.company, self.grille)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=c1,
            resultat=ReponseCritere.Resultat.NON_CONFORME)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=c2,
            resultat=ReponseCritere.Resultat.NON_CONFORME)
        result = constats_par_clause(self.company, referentiel='9001')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['referentiel'], '9001')


class ReadinessMultiReferentielTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs11-ready', 'CoXqhs11Ready')
        self.grille = make_grille(self.company)

    def test_calcule_pct_couverture(self):
        ClauseNorme.objects.create(
            company=self.company, referentiel='9001', numero='8.5.1',
            intitule='Maîtrise production')
        ClauseNorme.objects.create(
            company=self.company, referentiel='9001', numero='9.1.2',
            intitule='Satisfaction client')
        critere = make_critere(self.company, self.grille, '8.5.1')
        audit = make_audit(self.company, self.grille)
        ReponseCritere.objects.create(
            company=self.company, audit=audit, critere=critere,
            resultat=ReponseCritere.Resultat.CONFORME)

        result = readiness_multi_referentiel(self.company)
        self.assertEqual(result['9001']['total_clauses'], 2)
        self.assertEqual(result['9001']['couvertes'], 1)
        self.assertEqual(result['9001']['pct'], 50.0)

    def test_sans_clauses_pct_none(self):
        result = readiness_multi_referentiel(self.company)
        self.assertEqual(result, {})

    def test_isolation_societe(self):
        autre = make_company('co-xqhs11-ready-autre', 'CoXqhs11ReadyAutre')
        ClauseNorme.objects.create(
            company=self.company, referentiel='9001', numero='8.5.1',
            intitule='X')
        result = readiness_multi_referentiel(autre)
        self.assertEqual(result, {})
