"""Tests XQHS15 — Diffusion & accusé de lecture des procédures qualité.

Couvre :

* une diffusion cible N employés (accusés créés) ;
* l'accusé de lecture est idempotent (ne duplique pas, ne change pas
  ``lu_le`` une fois posé) ;
* « mes lectures en attente » ;
* la relance des retardataires ;
* le % de conformité par procédure ;
* une nouvelle version re-déclenche la diffusion sur la même population ;
* le scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import AccuseLecture, ProcedureQualite
from apps.qhse.selectors import conformite_lecture_procedure
from apps.qhse.services import (
    accuser_lecture, diffuser_procedure, lectures_en_attente,
    rediffuser_nouvelle_version, relancer_retardataires_lecture,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='technicien'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_procedure(
        company, reference='PRO-QUAL-001', version=1,
        statut=ProcedureQualite.Statut.EN_VIGUEUR):
    return ProcedureQualite.objects.create(
        company=company, reference=reference, titre='Procédure test',
        version=version, statut=statut)


class DiffuserProcedureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs15-diff', 'CoXqhs15Diff')
        self.procedure = make_procedure(self.company)

    def test_diffuse_a_n_employes(self):
        u1 = make_user(self.company, 'u1-xqhs15')
        u2 = make_user(self.company, 'u2-xqhs15')
        diffusion = diffuser_procedure(self.procedure, [u1, u2])
        self.assertEqual(diffusion.accuses_lecture.count(), 2)

    def test_population_cible_enregistree(self):
        u1 = make_user(self.company, 'u3-xqhs15')
        diffusion = diffuser_procedure(self.procedure, [u1])
        self.assertEqual(diffusion.population_cible['user_ids'], [u1.id])


class AccuserLectureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs15-accuse', 'CoXqhs15Accuse')
        self.procedure = make_procedure(self.company)
        self.user = make_user(self.company, 'lecteur-xqhs15')
        self.diffusion = diffuser_procedure(self.procedure, [self.user])

    def test_accuse_lecture(self):
        accuse = accuser_lecture(self.diffusion, self.user)
        self.assertIsNotNone(accuse.lu_le)

    def test_idempotent_ne_duplique_pas(self):
        accuser_lecture(self.diffusion, self.user)
        accuser_lecture(self.diffusion, self.user)
        self.assertEqual(
            AccuseLecture.objects.filter(
                diffusion=self.diffusion, user=self.user).count(), 1)

    def test_ne_change_pas_lu_le_deuxieme_appel(self):
        accuse1 = accuser_lecture(self.diffusion, self.user)
        premiere_lecture = accuse1.lu_le
        accuse2 = accuser_lecture(self.diffusion, self.user)
        self.assertEqual(accuse2.lu_le, premiere_lecture)


class LecturesEnAttenteTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs15-attente', 'CoXqhs15Attente')
        self.procedure = make_procedure(self.company)
        self.user = make_user(self.company, 'lecteur2-xqhs15')

    def test_liste_les_diffusions_non_lues(self):
        diffuser_procedure(self.procedure, [self.user])
        en_attente = lectures_en_attente(self.user)
        self.assertEqual(en_attente.count(), 1)

    def test_exclut_les_lus(self):
        diffusion = diffuser_procedure(self.procedure, [self.user])
        accuser_lecture(diffusion, self.user)
        en_attente = lectures_en_attente(self.user)
        self.assertEqual(en_attente.count(), 0)


class RelancerRetardatairesLectureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs15-relance', 'CoXqhs15Relance')
        self.procedure = make_procedure(self.company)

    def test_relance_non_lus(self):
        user = make_user(self.company, 'retard-xqhs15')
        diffuser_procedure(self.procedure, [user])
        relances = relancer_retardataires_lecture(company=self.company)
        self.assertEqual(len(relances), 1)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs15-relance-autre', 'CoXqhs15RelanceAutre')
        user = make_user(self.company, 'retard2-xqhs15')
        diffuser_procedure(self.procedure, [user])
        relances = relancer_retardataires_lecture(company=autre)
        self.assertEqual(len(relances), 0)


class ConformiteLectureProcedureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs15-conf', 'CoXqhs15Conf')
        self.procedure = make_procedure(self.company)

    def test_calcule_pct(self):
        u1 = make_user(self.company, 'conf1-xqhs15')
        u2 = make_user(self.company, 'conf2-xqhs15')
        diffusion = diffuser_procedure(self.procedure, [u1, u2])
        accuser_lecture(diffusion, u1)

        result = conformite_lecture_procedure(self.company, 'PRO-QUAL-001')
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['lus'], 1)
        self.assertEqual(result['pct'], 50.0)

    def test_sans_diffusion_pct_none(self):
        result = conformite_lecture_procedure(self.company, 'PRO-INEXISTANTE')
        self.assertIsNone(result['pct'])


class RediffuserNouvelleVersionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs15-redif', 'CoXqhs15Redif')

    def test_rediffuse_meme_population(self):
        v1 = make_procedure(self.company, version=1)
        user = make_user(self.company, 'v1-xqhs15')
        diffuser_procedure(v1, [user])

        v2 = make_procedure(self.company, version=2)
        diffusion2 = rediffuser_nouvelle_version(v1, v2)
        self.assertIsNotNone(diffusion2)
        self.assertEqual(diffusion2.procedure, v2)
        self.assertEqual(diffusion2.accuses_lecture.count(), 1)

    def test_sans_diffusion_anterieure_ne_fait_rien(self):
        v1 = make_procedure(self.company, version=1)
        v2 = make_procedure(self.company, version=2)
        result = rediffuser_nouvelle_version(v1, v2)
        self.assertIsNone(result)

    def test_nouvelle_diffusion_repart_a_zero_lecture(self):
        v1 = make_procedure(self.company, version=1)
        user = make_user(self.company, 'v2-xqhs15')
        diffusion1 = diffuser_procedure(v1, [user])
        accuser_lecture(diffusion1, user)

        v2 = make_procedure(self.company, version=2)
        diffusion2 = rediffuser_nouvelle_version(v1, v2)
        accuse2 = diffusion2.accuses_lecture.get(user=user)
        self.assertIsNone(accuse2.lu_le)
