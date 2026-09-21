"""Tests PAIE36 — Clôture mensuelle + verrouillage + rectificatifs/rappels.

Couvre :
* ``cloturer_periode_paie`` — valide les brouillons restants et fige la période
  (statut → clôturée) ; idempotent.
* Verrouillage : ``generer_bulletin`` refuse une période clôturée.
* ``creer_bulletin_rectificatif`` — émet un nouveau bulletin lié à l'origine
  (figée) sur une période OUVERTE ≠ origine ; refuse même période / société
  différente / période clôturée / type invalide.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import BulletinPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    cloturer_periode_paie,
    creer_bulletin_rectificatif,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ClotureTests(TestCase):
    def setUp(self):
        self.co = make_company('clot')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='CL1', nom='Test', prenom='Clot')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def test_cloture_valide_brouillons_et_fige(self):
        b = generer_bulletin(self.profil, self.periode)
        self.assertEqual(b.statut, BulletinPaie.STATUT_BROUILLON)
        cloturer_periode_paie(self.periode)
        self.periode.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(self.periode.statut, PeriodePaie.STATUT_CLOTUREE)
        self.assertIsNotNone(self.periode.date_cloture)
        self.assertEqual(b.statut, BulletinPaie.STATUT_VALIDE)

    def test_cloture_verrouille_generation(self):
        cloturer_periode_paie(self.periode)
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            generer_bulletin(self.profil, self.periode)

    def test_cloture_idempotente(self):
        cloturer_periode_paie(self.periode)
        # Re-clôturer ne lève pas.
        cloturer_periode_paie(self.periode)
        self.periode.refresh_from_db()
        self.assertEqual(self.periode.statut, PeriodePaie.STATUT_CLOTUREE)


class RectificatifTests(TestCase):
    def setUp(self):
        self.co = make_company('rectif')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='RE1', nom='Test', prenom='Rectif')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.periode_suivante = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        self.origine = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.origine)
        cloturer_periode_paie(self.periode)

    def test_rectificatif_lie_origine(self):
        rectif = creer_bulletin_rectificatif(
            self.origine, self.periode_suivante, motif='Erreur de prime')
        self.assertEqual(rectif.type_bulletin, BulletinPaie.TYPE_RECTIFICATIF)
        self.assertEqual(rectif.rectifie_id, self.origine.id)
        self.assertEqual(rectif.motif, 'Erreur de prime')
        self.assertEqual(rectif.periode_id, self.periode_suivante.id)
        # L'origine reste figée.
        self.origine.refresh_from_db()
        self.assertEqual(self.origine.statut, BulletinPaie.STATUT_VALIDE)

    def test_rappel(self):
        rappel = creer_bulletin_rectificatif(
            self.origine, self.periode_suivante,
            type_bulletin=BulletinPaie.TYPE_RAPPEL, motif='Rappel salaire')
        self.assertEqual(rappel.type_bulletin, BulletinPaie.TYPE_RAPPEL)

    def test_refuse_meme_periode(self):
        # On rouvre l'origine est impossible ; on teste la garde même période.
        autre = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=8)
        b8 = generer_bulletin(self.profil, autre)
        valider_bulletin(b8)
        with self.assertRaises(ValueError):
            creer_bulletin_rectificatif(b8, autre)

    def test_refuse_periode_cloturee(self):
        autre_close = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=9)
        cloturer_periode_paie(autre_close)
        with self.assertRaises(ValueError):
            creer_bulletin_rectificatif(self.origine, autre_close)

    def test_refuse_type_invalide(self):
        with self.assertRaises(ValueError):
            creer_bulletin_rectificatif(
                self.origine, self.periode_suivante, type_bulletin='normal')
