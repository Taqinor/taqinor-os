"""Tests XFLT29 — Avantage en nature véhicule -> paie.

Couvre :
- Champs additifs ``AffectationConducteur.usage_prive`` /
  ``valeur_avantage_mensuelle`` (défauts : False / 0, aucune régression).
- Selector ``avantages_en_nature(company, mois)`` :
  - affectation usage privé recouvrant le mois -> remonte, avec la valeur
    saisie ;
  - affectation SANS usage privé -> absente ;
  - affectation hors période (mois non recouvert) -> absente ;
  - conducteur sans compte ERP lié (``user`` nul) -> absente (ne peut pas
    être intégrée à la paie) ;
  - affectation ``date_fin`` nulle (en cours) -> remonte pour tout mois
    depuis son début ;
  - scope société.
- La flotte n'écrit JAMAIS dans le module paie : ce sélecteur est LECTURE
  SEULE (aucun import de ``apps.rh``/``apps.paie`` ici).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.flotte.models import AffectationConducteur, Conducteur, Vehicule
from apps.flotte.selectors import avantages_en_nature

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy="normal")


def make_vehicule(company, immat):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")


class AvantageEnNatureModelTests(TestCase):
    def test_defauts(self):
        co = make_company("avn-model", "AVN Model")
        cond = Conducteur.objects.create(company=co, nom="Chauffeur")
        veh = make_vehicule(co, "AVN-1")
        aff = AffectationConducteur.objects.create(
            company=co, conducteur=cond, vehicule=veh,
            date_debut=datetime.date(2026, 1, 1))
        self.assertFalse(aff.usage_prive)
        self.assertEqual(aff.valeur_avantage_mensuelle, 0)


class AvantagesEnNatureSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("avn-svc", "AVN Svc")
        self.user = make_user(self.co, "avn-user")
        self.cond = Conducteur.objects.create(
            company=self.co, nom="Chauffeur Perso", user=self.user)
        self.veh = make_vehicule(self.co, "AVN-2")

    def test_usage_prive_recouvre_mois_remonte(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 12, 31),
            usage_prive=True, valeur_avantage_mensuelle="800.00")
        result = avantages_en_nature(self.co, "2026-06")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["conducteur_id"], self.cond.id)
        self.assertEqual(str(result[0]["valeur_avantage_mensuelle"]), "800.00")

    def test_sans_usage_prive_absente(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            usage_prive=False)
        result = avantages_en_nature(self.co, "2026-06")
        self.assertEqual(result, [])

    def test_hors_periode_absente(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            date_fin=datetime.date(2026, 3, 31),
            usage_prive=True, valeur_avantage_mensuelle="500")
        result = avantages_en_nature(self.co, "2026-06")
        self.assertEqual(result, [])

    def test_date_fin_nulle_toujours_en_cours(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            usage_prive=True, valeur_avantage_mensuelle="650")
        result = avantages_en_nature(self.co, "2026-11")
        self.assertEqual(len(result), 1)

    def test_conducteur_sans_user_absente(self):
        cond_externe = Conducteur.objects.create(
            company=self.co, nom="Chauffeur Externe")
        AffectationConducteur.objects.create(
            company=self.co, conducteur=cond_externe, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1),
            usage_prive=True, valeur_avantage_mensuelle="400")
        result = avantages_en_nature(self.co, "2026-06")
        self.assertEqual(result, [])

    def test_scope_societe(self):
        autre = make_company("avn-svc-b", "AVN Svc B")
        user_b = make_user(autre, "avn-user-b")
        cond_b = Conducteur.objects.create(
            company=autre, nom="Chauffeur B", user=user_b)
        veh_b = make_vehicule(autre, "AVN-B1")
        AffectationConducteur.objects.create(
            company=autre, conducteur=cond_b, vehicule=veh_b,
            date_debut=datetime.date(2026, 1, 1),
            usage_prive=True, valeur_avantage_mensuelle="900")
        result = avantages_en_nature(self.co, "2026-06")
        self.assertEqual(result, [])
