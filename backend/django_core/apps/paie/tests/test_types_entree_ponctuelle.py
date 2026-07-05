"""Tests ZPAI9 — Catalogue de types d'entrées ponctuelles (Other Input Types).

Couvre :
* ``ensure_types_entree_ponctuelle_standard`` — seed idempotent (0 doublon au
  re-run), n'écrase jamais un type édité.
* ``calculer_bulletin`` — une entrée ponctuelle typée « frais non imposable »
  sort des bases CNSS/IR (brut/brut_imposable inchangés) et rejoint
  directement le net ; une entrée « déduction ponctuelle » (sens=retenue) le
  diminue. Les entrées existantes (sans ``type_entree``) restent intactes.
* Isolation tenant sur le seed.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    ElementVariable, PeriodePaie, ProfilPaie, TypeEntreePonctuelle,
)
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    ensure_types_entree_ponctuelle_standard,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class SeedTests(TestCase):
    def setUp(self):
        self.co = make_company('type-entree-seed')

    def test_seed_cree_types_standard(self):
        result = ensure_types_entree_ponctuelle_standard(self.co)
        self.assertEqual(result['types'], 3)
        self.assertEqual(
            TypeEntreePonctuelle.objects.filter(company=self.co).count(), 3)

    def test_seed_idempotent(self):
        ensure_types_entree_ponctuelle_standard(self.co)
        result2 = ensure_types_entree_ponctuelle_standard(self.co)
        self.assertEqual(result2['types'], 0)
        self.assertEqual(
            TypeEntreePonctuelle.objects.filter(company=self.co).count(), 3)

    def test_seed_ne_touche_pas_type_edite(self):
        ensure_types_entree_ponctuelle_standard(self.co)
        pourboire = TypeEntreePonctuelle.objects.get(
            company=self.co, code='POURBOIRE')
        pourboire.libelle = 'Pourboire (édité)'
        pourboire.save(update_fields=['libelle'])
        ensure_types_entree_ponctuelle_standard(self.co)
        pourboire.refresh_from_db()
        self.assertEqual(pourboire.libelle, 'Pourboire (édité)')

    def test_isolation_tenant(self):
        autre_co = make_company('type-entree-seed-autre')
        ensure_types_entree_ponctuelle_standard(self.co)
        ensure_types_entree_ponctuelle_standard(autre_co)
        self.assertEqual(
            TypeEntreePonctuelle.objects.filter(company=self.co).count(), 3)
        self.assertEqual(
            TypeEntreePonctuelle.objects.filter(company=autre_co).count(), 3)


class BulletinTypeEntreeTests(TestCase):
    def setUp(self):
        self.co = make_company('type-entree-bulletin')
        ensure_defaults(self.co)
        ensure_types_entree_ponctuelle_standard(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='TE1', nom='Test', prenom='Entree')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.type_frais_ni = TypeEntreePonctuelle.objects.get(
            company=self.co, code='REMB_FRAIS_NI')
        self.type_deduction = TypeEntreePonctuelle.objects.get(
            company=self.co, code='DEDUCTION_PONCT')

    def test_frais_non_imposable_hors_bases(self):
        base = calculer_bulletin(self.profil, self.periode)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Frais de mission',
            montant=Decimal('500'), type_entree=self.type_frais_ni)
        avec_frais = calculer_bulletin(self.profil, self.periode)
        # brut/brut_imposable inchangés (hors bases CNSS/IR).
        self.assertEqual(avec_frais['brut'], base['brut'])
        self.assertEqual(avec_frais['net_imposable'], base['net_imposable'])
        self.assertEqual(avec_frais['ir'], base['ir'])
        # Le net à payer augmente de 500.
        self.assertEqual(
            avec_frais['net_a_payer'], base['net_a_payer'] + Decimal('500.00'))
        self.assertTrue(any(
            ligne['code'] == 'REMB_FRAIS_NI' for ligne in avec_frais['lignes']))

    def test_deduction_ponctuelle_diminue_net(self):
        base = calculer_bulletin(self.profil, self.periode)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Trop-perçu',
            montant=Decimal('150'), type_entree=self.type_deduction)
        avec_deduction = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(avec_deduction['brut'], base['brut'])
        self.assertEqual(
            avec_deduction['net_a_payer'],
            base['net_a_payer'] - Decimal('150.00'))

    def test_element_sans_type_entree_inchange(self):
        # Une prime SANS type catalogue reste imposable/cotisable (historique).
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, libelle='Prime perf',
            montant=Decimal('500'))
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut_imposable'], res['brut'])
