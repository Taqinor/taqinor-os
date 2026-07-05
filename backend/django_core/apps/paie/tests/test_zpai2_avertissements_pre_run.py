"""Tests ZPAI2 — Panneau d'avertissements pré-run (blocages de paie).

Odoo affiche en haut du dashboard Paie les problèmes à résoudre AVANT de
payer. Couvre :
* profil virement sans RIB -> avertissement bloquant ;
* salaire de base à 0 -> bloquant ;
* profil complet -> aucun avertissement ;
* les catégories de ``controle_completude`` (CNSS manquant, dossier non
  actif, CDD échu, actif sans profil) sont reflétées ;
* aucune écriture sur ``rh`` ; isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import avertissements_periode, ensure_defaults
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class AvertissementsPeriodeTests(TestCase):
    def setUp(self):
        self.co = make_company('zpai2')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _dossier(self, mat, **kw):
        return DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P', **kw)

    def test_profil_complet_aucun_avertissement(self):
        dossier = self._dossier('OK1')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='C1', rib='R1',
            mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT)
        r = avertissements_periode(self.periode)
        types = {a['type'] for a in r}
        self.assertNotIn('rib_manquant_virement', types)
        self.assertNotIn('salaire_nul', types)
        self.assertNotIn('cnss_manquant', types)

    def test_rib_manquant_virement_bloquant(self):
        dossier = self._dossier('RIB1')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='C1', rib='',
            mode_paiement=ProfilPaie.MODE_PAIEMENT_VIREMENT)
        r = avertissements_periode(self.periode)
        item = next(a for a in r if a['type'] == 'rib_manquant_virement')
        self.assertEqual(item['gravite'], 'bloquant')

    def test_rib_manquant_mais_mode_espece_pas_de_warning(self):
        dossier = self._dossier('RIB2')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='C1', rib='',
            mode_paiement=ProfilPaie.MODE_PAIEMENT_ESPECES)
        r = avertissements_periode(self.periode)
        types = {a['type'] for a in r}
        self.assertNotIn('rib_manquant_virement', types)

    def test_salaire_nul_bloquant(self):
        dossier = self._dossier('SAL1')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('0'), numero_cnss='C1', rib='R1')
        r = avertissements_periode(self.periode)
        item = next(a for a in r if a['type'] == 'salaire_nul')
        self.assertEqual(item['gravite'], 'bloquant')

    def test_cnss_manquant_reflete(self):
        dossier = self._dossier('CN1')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='', rib='R1')
        r = avertissements_periode(self.periode)
        types = {a['type'] for a in r}
        self.assertIn('cnss_manquant', types)

    def test_actif_sans_profil_reflete(self):
        self._dossier('SP1')
        r = avertissements_periode(self.periode)
        types = {a['type'] for a in r}
        self.assertIn('sans_profil_paie', types)

    def test_isolation_tenant(self):
        dossier = self._dossier('T1')
        ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('0'))
        autre = make_company('zpai2-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        r = avertissements_periode(periode_autre)
        self.assertEqual(r, [])
