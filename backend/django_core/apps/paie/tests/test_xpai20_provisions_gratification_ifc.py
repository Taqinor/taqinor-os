"""Tests XPAI20 — Provisions gratifications (13e mois) & IFC.

Couvre : la clôture mensuelle poste une provision auditable par employé et
par type (gratification + IFC), l'écriture comptable réversible est
équilibrée, la provision est idempotente (jamais recomptée deux fois pour la
même période), et le run 13e mois (validation d'un bulletin de nature
``gratification``) EXTOURNE les provisions gratification accumulées.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie, ProvisionPaieMensuelle
from apps.paie.services import (
    cloturer_periode_paie, ensure_defaults, generer_bulletin,
    generer_run_gratification, poster_provisions_mensuelles,
    provision_gratification_mensuelle, provision_ifc_mensuelle,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ProvisionCalculTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai20-calcul')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='P1', nom='Nom', prenom='P',
            date_embauche=date(2015, 1, 1),
            statut=DossierEmploye.Statut.ACTIF)
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'), affilie_cnss=True, affilie_amo=True)

    def test_provision_gratification_est_un_douzieme(self):
        montant = provision_gratification_mensuelle(self.profil, self.periode)
        attendu = (Decimal('12000') / Decimal('12')).quantize(Decimal('0.01'))
        self.assertEqual(montant, attendu)

    def test_provision_ifc_positive_avec_anciennete(self):
        montant = provision_ifc_mensuelle(self.profil, self.periode)
        self.assertGreater(montant, Decimal('0'))

    def test_provision_ifc_zero_sans_anciennete(self):
        dossier2 = DossierEmploye.objects.create(
            company=self.co, matricule='P2', nom='Nom', prenom='Q',
            statut=DossierEmploye.Statut.ACTIF)
        profil2 = ProfilPaie.objects.create(
            company=self.co, employe=dossier2,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))
        montant = provision_ifc_mensuelle(profil2, self.periode)
        self.assertEqual(montant, Decimal('0.00'))

    def test_provision_zero_profil_inactif(self):
        self.profil.actif = False
        self.profil.save()
        self.assertEqual(
            provision_gratification_mensuelle(self.profil, self.periode),
            Decimal('0.00'))
        self.assertEqual(
            provision_ifc_mensuelle(self.profil, self.periode), Decimal('0.00'))


class PosterProvisionsMensuellesTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai20-poster')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='P3', nom='Nom', prenom='R',
            date_embauche=date(2018, 1, 1),
            statut=DossierEmploye.Statut.ACTIF)
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)

    def test_poste_deux_lignes_par_profil(self):
        resultat = poster_provisions_mensuelles(self.periode)
        self.assertEqual(len(resultat['lignes']), 2)
        types = {lig.type_provision for lig in resultat['lignes']}
        self.assertEqual(
            types,
            {ProvisionPaieMensuelle.TYPE_GRATIFICATION,
             ProvisionPaieMensuelle.TYPE_IFC})

    def test_ecriture_equilibree(self):
        resultat = poster_provisions_mensuelles(self.periode)
        ecriture = resultat['ecriture']
        self.assertIsNotNone(ecriture)
        lignes = list(ecriture.lignes.all())
        debit_total = sum((lig.debit for lig in lignes), Decimal('0'))
        credit_total = sum((lig.credit for lig in lignes), Decimal('0'))
        self.assertEqual(debit_total, credit_total)
        self.assertGreater(debit_total, Decimal('0'))

    def test_idempotent_ne_recompte_pas(self):
        poster_provisions_mensuelles(self.periode)
        nb_avant = ProvisionPaieMensuelle.objects.filter(
            company=self.co, periode=self.periode).count()
        resultat2 = poster_provisions_mensuelles(self.periode)
        nb_apres = ProvisionPaieMensuelle.objects.filter(
            company=self.co, periode=self.periode).count()
        self.assertEqual(nb_avant, nb_apres)
        # Le second appel ne poste AUCUNE nouvelle écriture (rien de neuf).
        self.assertIsNone(resultat2['ecriture'])

    def test_cloture_mensuelle_poste_les_provisions(self):
        cloturer_periode_paie(self.periode)
        self.assertEqual(
            ProvisionPaieMensuelle.objects.filter(
                company=self.co, periode=self.periode).count(),
            2)

    def test_cloture_hors_cycle_ne_poste_rien(self):
        periode_hc = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)
        cloturer_periode_paie(periode_hc)
        self.assertEqual(
            ProvisionPaieMensuelle.objects.filter(
                company=self.co, periode=periode_hc).count(),
            0)


class ExtourneAuPaiementTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai20-extourne')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='P4', nom='Nom', prenom='S',
            date_embauche=date(2020, 1, 1),
            statut=DossierEmploye.Statut.ACTIF)
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'), affilie_cnss=True, affilie_amo=True)

    def test_run_13e_mois_extourne_provisions(self):
        # Accumule 3 mois de provisions gratification (mensuel).
        for mois in (1, 2, 3):
            periode = PeriodePaie.objects.create(
                company=self.co, annee=2026, mois=mois)
            bulletin = generer_bulletin(self.profil, periode)
            valider_bulletin(bulletin)
            poster_provisions_mensuelles(periode)

        provisions_avant = ProvisionPaieMensuelle.objects.filter(
            company=self.co, profil=self.profil,
            type_provision=ProvisionPaieMensuelle.TYPE_GRATIFICATION)
        self.assertEqual(provisions_avant.count(), 3)
        self.assertTrue(all(not p.extournee for p in provisions_avant))

        # Run 13e mois hors-cycle : validation extourne les 3 provisions.
        periode_run = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=12,
            type_run=PeriodePaie.TYPE_RUN_HORS_CYCLE)
        bulletins = generer_run_gratification(periode_run)
        self.assertEqual(len(bulletins), 1)
        valider_bulletin(bulletins[0])

        provisions_apres = ProvisionPaieMensuelle.objects.filter(
            company=self.co, profil=self.profil,
            type_provision=ProvisionPaieMensuelle.TYPE_GRATIFICATION)
        self.assertTrue(all(p.extournee for p in provisions_apres))
