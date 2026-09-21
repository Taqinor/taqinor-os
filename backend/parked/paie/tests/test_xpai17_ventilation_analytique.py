"""Tests XPAI17 — Ventilation analytique de la masse salariale + coût global.

Couvre : ventilation au prorata des heures ``rh.FeuilleTemps`` (résolution
d'un ``compta.CentreCout`` par chantier), repli sur une clé % fixe
(``VentilationAnalytiquePaie``) quand aucune heure n'existe, aucune clé →
non ventilé, coût global par profil, et l'écriture ``journal_de_paie_ventile``
équilibrée avec lignes de rémunération éclatées par centre.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    BulletinPaie, PeriodePaie, ProfilPaie, VentilationAnalytiquePaie,
)
from apps.paie.services import (
    cout_employeur_bulletin, cout_global_par_profil, ensure_defaults,
    generer_bulletin, journal_de_paie_ventile, valider_bulletin,
    ventilation_analytique_bulletin,
)
from apps.rh.models import DossierEmploye, FeuilleTemps
from apps.compta.models import CentreCout


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class VentilationAnalytiqueTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai17-ventil')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V1', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)

    def _valider(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(bulletin)
        return BulletinPaie.objects.get(pk=bulletin.pk)

    def test_sans_heures_sans_cle_non_ventile(self):
        bulletin = self._valider()
        lignes = ventilation_analytique_bulletin(bulletin)
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0]['centre_cout_id'])
        self.assertEqual(lignes[0]['montant'], cout_employeur_bulletin(bulletin))

    def test_ventile_au_prorata_des_heures(self):
        FeuilleTemps.objects.create(
            company=self.co, employe=self.dossier, installation_id=101,
            date='2026-06-05', heures=Decimal('60'))
        FeuilleTemps.objects.create(
            company=self.co, employe=self.dossier, installation_id=202,
            date='2026-06-10', heures=Decimal('40'))
        bulletin = self._valider()
        lignes = ventilation_analytique_bulletin(bulletin)
        self.assertEqual(len(lignes), 2)
        total = cout_employeur_bulletin(bulletin)
        somme = sum((lig['montant'] for lig in lignes), Decimal('0'))
        self.assertEqual(somme, total)
        # 60/100 des heures → 60 % du coût sur le premier centre.
        attendu_60 = (total * Decimal('60') / Decimal('100')).quantize(
            Decimal('0.01'))
        montants = sorted(lig['montant'] for lig in lignes)
        self.assertIn(attendu_60, montants + [
            (total - m) for m in montants])
        # Deux centres de coût distincts créés.
        centres = CentreCout.objects.filter(company=self.co)
        self.assertEqual(centres.count(), 2)
        codes = set(centres.values_list('code', flat=True))
        self.assertEqual(codes, {'CHANTIER-101', 'CHANTIER-202'})

    def test_heures_hors_periode_ignorees(self):
        FeuilleTemps.objects.create(
            company=self.co, employe=self.dossier, installation_id=101,
            date='2026-05-05', heures=Decimal('60'))
        bulletin = self._valider()
        lignes = ventilation_analytique_bulletin(bulletin)
        self.assertEqual(len(lignes), 1)
        self.assertIsNone(lignes[0]['centre_cout_id'])

    def test_repli_cle_fixe_quand_pas_dheures(self):
        centre = CentreCout.objects.create(
            company=self.co, code='AGENCE-X', libelle='Agence X',
            axe=CentreCout.Axe.AGENCE)
        VentilationAnalytiquePaie.objects.create(
            company=self.co, profil=self.profil,
            centre_cout_id=centre.id, pourcentage=Decimal('70'))
        bulletin = self._valider()
        lignes = ventilation_analytique_bulletin(bulletin)
        self.assertEqual(len(lignes), 2)  # 70 % centre + 30 % reliquat
        centre_ligne = next(
            lig for lig in lignes if lig['centre_cout_id'] == centre.id)
        reliquat_ligne = next(
            lig for lig in lignes if lig['centre_cout_id'] is None)
        total = cout_employeur_bulletin(bulletin)
        self.assertEqual(
            centre_ligne['montant'],
            (total * Decimal('70') / Decimal('100')).quantize(Decimal('0.01')))
        self.assertEqual(
            centre_ligne['montant'] + reliquat_ligne['montant'], total)

    def test_cle_fixe_100_pct_sans_reliquat(self):
        centre = CentreCout.objects.create(
            company=self.co, code='AGENCE-Y', libelle='Agence Y')
        VentilationAnalytiquePaie.objects.create(
            company=self.co, profil=self.profil,
            centre_cout_id=centre.id, pourcentage=Decimal('100'))
        bulletin = self._valider()
        lignes = ventilation_analytique_bulletin(bulletin)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['centre_cout_id'], centre.id)

    def test_cout_global_par_profil(self):
        self._valider()
        resultat = cout_global_par_profil(self.periode)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['profil_id'], self.profil.id)
        self.assertEqual(resultat[0]['matricule'], 'V1')
        self.assertGreater(resultat[0]['cout_global'], Decimal('0'))

    def test_journal_ventile_equilibre(self):
        FeuilleTemps.objects.create(
            company=self.co, employe=self.dossier, installation_id=303,
            date='2026-06-05', heures=Decimal('50'))
        self._valider()
        ecriture = journal_de_paie_ventile(self.periode)
        self.assertIsNotNone(ecriture)
        lignes = list(ecriture.lignes.all())
        debit_total = sum((lig.debit for lig in lignes), Decimal('0'))
        credit_total = sum((lig.credit for lig in lignes), Decimal('0'))
        self.assertEqual(debit_total, credit_total)
        # Au moins une ligne débit porte le centre de coût du chantier.
        centre = CentreCout.objects.get(company=self.co, code='CHANTIER-303')
        self.assertTrue(
            any(lig.centre_cout_id == centre.id for lig in lignes))

    def test_journal_ventile_sans_bulletin_valide_renvoie_none(self):
        autre_periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        self.assertIsNone(journal_de_paie_ventile(autre_periode))
