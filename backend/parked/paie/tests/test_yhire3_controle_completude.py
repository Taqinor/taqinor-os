"""Tests YHIRE3 — Contrôle de complétude pré-paie.

Rien ne signalait les trous avant génération. Couvre :
* actif sans profil de paie ;
* profil actif sans n° CNSS ;
* profil actif sans RIB ;
* profil actif dont le dossier RH n'est plus ACTIF (sorti) ;
* CDD dont ``contrat_date_fin`` est antérieure à la fin de la période ;
* cas sain (rien à signaler).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import controle_completude, ensure_defaults
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ControleCompletudeTests(TestCase):
    def setUp(self):
        self.co = make_company('yhire3')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _dossier(self, mat, statut=DossierEmploye.Statut.ACTIF, **kw):
        return DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P',
            statut=statut, **kw)

    def _profil(self, dossier, cnss='CNSS1', rib='RIB1', actif=True):
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True,
            affilie_amo=True, numero_cnss=cnss, rib=rib, actif=actif)

    def test_cas_sain_rien_a_signaler(self):
        dossier = self._dossier('S1')
        self._profil(dossier)
        r = controle_completude(self.periode)
        self.assertEqual(r['actifs_sans_profil'], [])
        self.assertEqual(r['profils_sans_cnss'], [])
        self.assertEqual(r['profils_sans_rib'], [])
        self.assertEqual(r['profils_actifs_dossiers_non_actifs'], [])
        self.assertEqual(r['contrats_expires'], [])

    def test_actif_sans_profil(self):
        dossier = self._dossier('A1')
        r = controle_completude(self.periode)
        ids = {x['dossier_id'] for x in r['actifs_sans_profil']}
        self.assertIn(dossier.id, ids)

    def test_profil_sans_cnss(self):
        dossier = self._dossier('C1')
        profil = self._profil(dossier, cnss='')
        r = controle_completude(self.periode)
        ids = {x['profil_id'] for x in r['profils_sans_cnss']}
        self.assertIn(profil.id, ids)

    def test_profil_sans_rib(self):
        dossier = self._dossier('R1')
        profil = self._profil(dossier, rib='')
        r = controle_completude(self.periode)
        ids = {x['profil_id'] for x in r['profils_sans_rib']}
        self.assertIn(profil.id, ids)

    def test_profil_actif_dossier_sorti(self):
        dossier = self._dossier('D1', statut=DossierEmploye.Statut.SORTI)
        profil = self._profil(dossier)
        r = controle_completude(self.periode)
        ids = {x['profil_id'] for x in r['profils_actifs_dossiers_non_actifs']}
        self.assertIn(profil.id, ids)

    def test_profil_actif_dossier_embauche(self):
        dossier = self._dossier('D2', statut=DossierEmploye.Statut.EMBAUCHE)
        profil = self._profil(dossier)
        r = controle_completude(self.periode)
        ids = {x['profil_id'] for x in r['profils_actifs_dossiers_non_actifs']}
        self.assertIn(profil.id, ids)

    def test_profil_inactif_ne_declenche_rien(self):
        # Un profil désactivé n'est pas un trou : exclu de tous les contrôles.
        dossier = self._dossier('I1', statut=DossierEmploye.Statut.SORTI)
        self._profil(dossier, cnss='', rib='', actif=False)
        r = controle_completude(self.periode)
        self.assertEqual(r['profils_sans_cnss'], [])
        self.assertEqual(r['profils_sans_rib'], [])
        self.assertEqual(r['profils_actifs_dossiers_non_actifs'], [])

    def test_cdd_expire_avant_fin_periode(self):
        dossier = self._dossier(
            'CDD1', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin='2026-06-15')
        profil = self._profil(dossier)
        r = controle_completude(self.periode)
        ids = {x['profil_id'] for x in r['contrats_expires']}
        self.assertIn(profil.id, ids)

    def test_cdd_encore_valide_non_signale(self):
        dossier = self._dossier(
            'CDD2', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin='2026-07-15')
        self._profil(dossier)
        r = controle_completude(self.periode)
        self.assertEqual(r['contrats_expires'], [])

    def test_cdi_sans_date_fin_non_signale(self):
        dossier = self._dossier(
            'CDI1', type_contrat=DossierEmploye.TypeContrat.CDI)
        self._profil(dossier)
        r = controle_completude(self.periode)
        self.assertEqual(r['contrats_expires'], [])

    def test_isolation_tenant(self):
        dossier = self._dossier('T1')
        self._profil(dossier, cnss='')
        autre = make_company('yhire3-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        r = controle_completude(periode_autre)
        self.assertEqual(r['profils_sans_cnss'], [])
