"""Tests YHIRE6 — Une seule source du salaire : Remuneration (rh, datée) ↔
ProfilPaie.salaire_base (paie, copie statique).

``rh.Remuneration`` (historisée par ``date_effet``) et
``paie.ProfilPaie.salaire_base`` ne se parlaient jamais. Couvre :
* ``rh.selectors.remuneration_en_vigueur`` — la ligne dont ``date_effet`` la
  plus récente ≤ jour, normalisée en équivalent mensuel ;
* ``controle_completude`` remonte l'écart salaire profil ≠ rémunération en
  vigueur (YHIRE3 étendu) ;
* ``synchroniser_salaire`` aligne le profil (jamais silencieuse).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    controle_completude, ensure_defaults, synchroniser_salaire,
)
from apps.rh import selectors as rh_selectors
from apps.rh.models import DossierEmploye, Remuneration


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class RemunerationEnVigueurTests(TestCase):
    def setUp(self):
        self.co = make_company('yhire6-sel')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='R1', nom='N', prenom='P')

    def test_ligne_la_plus_recente_lte_jour(self):
        Remuneration.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal('9000'),
            periodicite=Remuneration.Periodicite.MENSUEL,
            date_effet=date(2026, 1, 1))
        Remuneration.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal('11000'),
            periodicite=Remuneration.Periodicite.MENSUEL,
            date_effet=date(2026, 6, 1))
        ref = rh_selectors.remuneration_en_vigueur(
            self.co, self.dossier.id, date(2026, 6, 30))
        self.assertEqual(ref['montant_mensuel'], Decimal('11000.00'))
        # Une date antérieure à la 2e ligne ne voit que la 1ère.
        ref_avant = rh_selectors.remuneration_en_vigueur(
            self.co, self.dossier.id, date(2026, 3, 1))
        self.assertEqual(ref_avant['montant_mensuel'], Decimal('9000.00'))

    def test_aucune_ligne_renvoie_none(self):
        self.assertIsNone(
            rh_selectors.remuneration_en_vigueur(
                self.co, self.dossier.id, date(2026, 6, 30)))

    def test_normalisation_journalier(self):
        Remuneration.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal('400'),
            periodicite=Remuneration.Periodicite.JOURNALIER,
            date_effet=date(2026, 1, 1))
        ref = rh_selectors.remuneration_en_vigueur(
            self.co, self.dossier.id, date(2026, 6, 30))
        self.assertEqual(ref['montant_mensuel'], Decimal('10400.00'))


class ControleCompletudeEcartsTests(TestCase):
    def setUp(self):
        self.co = make_company('yhire6-ctrl')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P')

    def test_ecart_detecte(self):
        Remuneration.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal('12000'),
            periodicite=Remuneration.Periodicite.MENSUEL,
            date_effet=date(2026, 1, 1))
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='C1', rib='R1')
        r = controle_completude(self.periode)
        ids = {x['profil_id'] for x in r['ecarts_remuneration']}
        self.assertIn(profil.id, ids)
        item = next(
            x for x in r['ecarts_remuneration'] if x['profil_id'] == profil.id)
        self.assertEqual(item['remuneration_en_vigueur'], Decimal('12000.00'))

    def test_aucun_ecart_si_salaire_aligne(self):
        Remuneration.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal('10000'),
            periodicite=Remuneration.Periodicite.MENSUEL,
            date_effet=date(2026, 1, 1))
        ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='C1', rib='R1')
        r = controle_completude(self.periode)
        self.assertEqual(r['ecarts_remuneration'], [])

    def test_sans_remuneration_rh_pas_signale(self):
        ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), numero_cnss='C1', rib='R1')
        r = controle_completude(self.periode)
        self.assertEqual(r['ecarts_remuneration'], [])


class SynchroniserSalaireTests(TestCase):
    def setUp(self):
        self.co = make_company('yhire6-sync')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='N', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))

    def test_synchronise_le_profil(self):
        Remuneration.objects.create(
            company=self.co, employe=self.dossier, montant=Decimal('13000'),
            periodicite=Remuneration.Periodicite.MENSUEL,
            date_effet=date(2026, 1, 1))
        synchroniser_salaire(self.profil, date(2026, 6, 30))
        self.profil.refresh_from_db()
        self.assertEqual(self.profil.salaire_base, Decimal('13000.00'))

    def test_sans_remuneration_inchange(self):
        synchroniser_salaire(self.profil, date(2026, 6, 30))
        self.profil.refresh_from_db()
        self.assertEqual(self.profil.salaire_base, Decimal('10000'))
