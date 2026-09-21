"""Tests YHIRE5 — Réconcilier rh.AvanceSalaire (guichet) ↔ paie.AvanceSalarie
(moteur de retenue).

Deux moteurs parallèles jamais connectés : une avance approuvée côté RH
n'était JAMAIS retenue sur le bulletin. Couvre :
* ``creer_avance_depuis_rh`` matérialise une ``paie.AvanceSalarie`` liée par
  id, idempotente (rejouer ne recrée jamais une 2ᵉ avance) ;
* sans profil de paie -> ``ValueError`` explicite (jamais un crash silencieux) ;
* ``apps.paie.selectors.solde_avance`` lit le solde réel côté RH sans jamais
  importer ``paie.models``.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie import selectors as paie_selectors
from apps.paie.models import AvanceSalarie, ProfilPaie
from apps.paie.services import creer_avance_depuis_rh
from apps.rh.models import AvanceSalaire, DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class CreerAvanceDepuisRhTests(TestCase):
    def setUp(self):
        self.co = make_company('yhire5')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='AV1', nom='N', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))

    def _rh_avance(self, montant='1500', annee=2026, mois=7, **kw):
        return AvanceSalaire.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal(montant),
            date_demande=date(2026, 6, 20), motif='Test',
            annee_deduction=annee, mois_deduction=mois,
            statut=AvanceSalaire.Statut.APPROUVEE, **kw)

    def test_materialise_avance_paie(self):
        rh_avance = self._rh_avance()
        avance = creer_avance_depuis_rh(rh_avance)
        self.assertIsNotNone(avance)
        self.assertEqual(avance.montant_total, Decimal('1500'))
        self.assertEqual(avance.montant_echeance, Decimal('1500'))
        self.assertEqual(avance.nombre_echeances, 1)
        self.assertEqual(avance.profil_id, self.profil.id)
        self.assertEqual(avance.date_debut, date(2026, 7, 1))
        rh_avance.refresh_from_db()
        self.assertEqual(rh_avance.paie_avance_id, avance.id)

    def test_idempotent_ne_cree_pas_deux_avances(self):
        rh_avance = self._rh_avance()
        avance1 = creer_avance_depuis_rh(rh_avance)
        rh_avance.refresh_from_db()
        avance2 = creer_avance_depuis_rh(rh_avance)
        self.assertEqual(avance1.id, avance2.id)
        self.assertEqual(
            AvanceSalarie.objects.filter(profil=self.profil).count(), 1)

    def test_sans_profil_leve_valueerror(self):
        dossier_sans_profil = DossierEmploye.objects.create(
            company=self.co, matricule='AV2', nom='N', prenom='P')
        rh_avance = AvanceSalaire.objects.create(
            company=self.co, employe=dossier_sans_profil,
            montant=Decimal('500'), annee_deduction=2026, mois_deduction=7,
            statut=AvanceSalaire.Statut.APPROUVEE)
        with self.assertRaises(ValueError):
            creer_avance_depuis_rh(rh_avance)

    def test_selecteur_solde_avance_cross_app(self):
        rh_avance = self._rh_avance(montant='1000')
        avance = creer_avance_depuis_rh(rh_avance)
        solde = paie_selectors.solde_avance(avance.id)
        self.assertEqual(solde, Decimal('1000.00'))

    def test_selecteur_id_inconnu_renvoie_none(self):
        self.assertIsNone(paie_selectors.solde_avance(999999))

    def test_defaut_mois_annee_si_absents(self):
        rh_avance = self._rh_avance(annee=None, mois=None)
        avance = creer_avance_depuis_rh(rh_avance)
        self.assertIsNotNone(avance)
