"""Tests XQHS6 — SCAR : demande d'action corrective fournisseur.

Couvre :

* la création depuis une NCR d'origine fournisseur (exige ``fournisseur``) ;
* le cycle réponse → vérification → clôture ;
* le compte SCAR par fournisseur exposé par sélecteur ;
* le scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.qhse.models import DemandeActionFournisseur, NonConformite
from apps.qhse.selectors import scar_count_par_fournisseur
from apps.qhse.services import (
    creer_scar_depuis_ncr, repondre_scar, verifier_efficacite_scar,
)
from apps.stock.models import Fournisseur

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_fournisseur(company, nom='Fournisseur X'):
    return Fournisseur.objects.create(company=company, nom=nom)


def make_ncr_fournisseur(company, fournisseur, titre='NCR réception'):
    return NonConformite.objects.create(
        company=company, titre=titre, fournisseur=fournisseur,
        gravite=NonConformite.Gravite.MAJEURE)


class CreerScarDepuisNcrTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs6-creer', 'CoXqhs6Creer')
        self.fournisseur = make_fournisseur(self.company)

    def test_cree_scar_depuis_ncr_fournisseur(self):
        ncr = make_ncr_fournisseur(self.company, self.fournisseur)
        scar = creer_scar_depuis_ncr(ncr, echeance_reponse='2026-08-01')
        self.assertEqual(scar.fournisseur, self.fournisseur)
        self.assertEqual(scar.ncr_source, ncr)
        self.assertEqual(scar.statut, DemandeActionFournisseur.Statut.EMISE)

    def test_ncr_sans_fournisseur_leve_erreur(self):
        ncr = NonConformite.objects.create(company=self.company, titre='NCR sans fourn')
        with self.assertRaises(ValueError):
            creer_scar_depuis_ncr(ncr)


class CycleScarTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs6-cycle', 'CoXqhs6Cycle')
        self.fournisseur = make_fournisseur(self.company)
        self.ncr = make_ncr_fournisseur(self.company, self.fournisseur)
        self.scar = creer_scar_depuis_ncr(self.ncr)
        self.user = make_user(self.company, 'resp-xqhs6-cycle')

    def test_repondre_scar(self):
        repondre_scar(
            self.scar, cause_racine='Défaut process', action='Formation équipe',
            preuve_attachment_ids=[1, 2])
        self.scar.refresh_from_db()
        self.assertEqual(self.scar.statut, DemandeActionFournisseur.Statut.REPONDUE)
        self.assertIsNotNone(self.scar.date_reponse)
        self.assertEqual(self.scar.preuve_attachment_ids, [1, 2])

    def test_verifier_sans_reponse_leve_erreur(self):
        with self.assertRaises(ValueError):
            verifier_efficacite_scar(self.scar, True, verifiee_par=self.user)

    def test_verification_efficace_cloture(self):
        repondre_scar(self.scar, cause_racine='Cause', action='Action')
        verifier_efficacite_scar(self.scar, True, verifiee_par=self.user)
        self.scar.refresh_from_db()
        self.assertEqual(self.scar.statut, DemandeActionFournisseur.Statut.CLOSE)
        self.assertTrue(self.scar.efficace)

    def test_verification_inefficace_reste_verifiee(self):
        repondre_scar(self.scar, cause_racine='Cause', action='Action')
        verifier_efficacite_scar(self.scar, False, verifiee_par=self.user)
        self.scar.refresh_from_db()
        self.assertEqual(self.scar.statut, DemandeActionFournisseur.Statut.VERIFIEE)
        self.assertFalse(self.scar.efficace)


class ScarCountParFournisseurTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs6-count', 'CoXqhs6Count')
        self.fournisseur = make_fournisseur(self.company)

    def test_compte_ouvertes_et_total(self):
        ncr1 = make_ncr_fournisseur(self.company, self.fournisseur, 'NCR 1')
        ncr2 = make_ncr_fournisseur(self.company, self.fournisseur, 'NCR 2')
        scar1 = creer_scar_depuis_ncr(ncr1)
        creer_scar_depuis_ncr(ncr2)
        repondre_scar(scar1, cause_racine='C', action='A')
        verifier_efficacite_scar(scar1, True)

        result = scar_count_par_fournisseur(self.company, self.fournisseur.id)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['ouvertes'], 1)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs6-count-autre', 'CoXqhs6CountAutre')
        ncr = make_ncr_fournisseur(self.company, self.fournisseur)
        creer_scar_depuis_ncr(ncr)
        result = scar_count_par_fournisseur(autre, self.fournisseur.id)
        self.assertEqual(result['total'], 0)
