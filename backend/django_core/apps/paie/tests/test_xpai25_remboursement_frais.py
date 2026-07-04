"""Tests XPAI25 — Notes de frais remboursées sur le bulletin.

Couvre : une indemnité chantier VALIDÉE non payée de la période apparaît en
ligne « Remboursement frais » hors bases CNSS/IR, la validation du bulletin
marque l'indemnité remboursée côté compta (double comptage impossible), une
indemnité brouillon/soumise n'est jamais reprise, et l'isolation par
utilisateur (un profil sans compte lié n'obtient rien).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import BaremeIndemnite, IndemniteChantier
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults, generer_bulletin, remboursements_frais_periode,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class RemboursementFraisTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai25-frais')
        ensure_defaults(self.co)
        compta_services.seed_plan_comptable(self.co)
        self.user = User.objects.create_user(
            username='xpai25-emp', password='x', company=self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='F1', nom='Nom', prenom='P',
            user=self.user)
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bareme = BaremeIndemnite.objects.create(
            company=self.co, libelle='Barème', taux_km=Decimal('3'),
            per_diem=Decimal('100'), defaut=True)

    def _indemnite_validee(self, montant_jours=2, jour=15):
        indem = compta_services.creer_indemnite_chantier(
            self.co, employe=self.user, date_deplacement=date(2026, 6, jour),
            nombre_jours=montant_jours, libelle_chantier='Chantier X',
            user=self.user)
        compta_services.soumettre_indemnite_chantier(indem)
        compta_services.valider_indemnite_chantier(indem)
        return indem

    def test_indemnite_validee_apparait_dans_remboursements(self):
        indem = self._indemnite_validee()
        total, lignes = remboursements_frais_periode(self.profil, self.periode)
        self.assertEqual(total, indem.montant_total)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0][0].id, indem.id)

    def test_bulletin_porte_ligne_remboursement_hors_ir_cnss(self):
        indem = self._indemnite_validee()
        bulletin = generer_bulletin(self.profil, self.periode)
        codes = [lig.code for lig in bulletin.lignes.all()]
        self.assertIn('REMB_FRAIS', codes)
        ligne_remb = bulletin.lignes.get(code='REMB_FRAIS')
        self.assertEqual(ligne_remb.montant, indem.montant_total)
        # Le remboursement ne doit pas gonfler la base imposable/CNSS : le
        # brut/brut_imposable ne bougent pas avec/sans indemnité (vérifié en
        # comparant à un profil identique sans indemnité).
        dossier2 = DossierEmploye.objects.create(
            company=self.co, matricule='F2', nom='Nom', prenom='Q')
        profil2 = ProfilPaie.objects.create(
            company=self.co, employe=dossier2,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)
        bulletin2 = generer_bulletin(profil2, self.periode)
        self.assertEqual(bulletin.brut_imposable, bulletin2.brut_imposable)
        self.assertEqual(bulletin.ir, bulletin2.ir)
        self.assertGreater(bulletin.net_a_payer, bulletin2.net_a_payer)

    def test_validation_marque_indemnite_remboursee(self):
        indem = self._indemnite_validee()
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        indem.refresh_from_db()
        self.assertEqual(indem.statut, IndemniteChantier.Statut.REMBOURSEE)

    def test_double_validation_ne_double_compte_pas(self):
        indem = self._indemnite_validee()
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        indem.refresh_from_db()
        montant_apres_1 = indem.montant_total
        # Revalider (no-op côté bulletin) ne doit jamais re-rembourser/lever.
        valider_bulletin(bulletin)
        indem.refresh_from_db()
        self.assertEqual(indem.montant_total, montant_apres_1)
        self.assertEqual(indem.statut, IndemniteChantier.Statut.REMBOURSEE)

    def test_indemnite_brouillon_non_reprise(self):
        compta_services.creer_indemnite_chantier(
            self.co, employe=self.user, date_deplacement=date(2026, 6, 10),
            nombre_jours=1, user=self.user)  # reste en brouillon
        total, lignes = remboursements_frais_periode(self.profil, self.periode)
        self.assertEqual(total, Decimal('0.00'))
        self.assertEqual(lignes, [])

    def test_profil_sans_utilisateur_lie_aucun_remboursement(self):
        dossier_sans_user = DossierEmploye.objects.create(
            company=self.co, matricule='F3', nom='Nom', prenom='R')
        profil_sans_user = ProfilPaie.objects.create(
            company=self.co, employe=dossier_sans_user,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'))
        self._indemnite_validee()
        total, lignes = remboursements_frais_periode(
            profil_sans_user, self.periode)
        self.assertEqual(total, Decimal('0.00'))
        self.assertEqual(lignes, [])

    def test_indemnite_hors_periode_non_reprise(self):
        self._indemnite_validee(jour=15)
        autre_periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        total, lignes = remboursements_frais_periode(
            self.profil, autre_periode)
        self.assertEqual(total, Decimal('0.00'))
        self.assertEqual(lignes, [])
