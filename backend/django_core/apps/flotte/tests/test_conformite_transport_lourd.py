"""Tests XFLT27 — Conformité transport lourd (chronotachygraphe & conducteur
professionnel).

Couvre :
- ``EcheanceReglementaire.TypeEcheance.CHRONOTACHYGRAPHE`` : une échéance de
  calibration chronotachygraphe DUE dans les 30 jours remonte dans le moteur
  d'alertes FLOTTE24 (comme tout autre type d'échéance réglementaire).
- Champs additifs ``Conducteur`` (carte pro + formation NARSA) :
  - carte de conducteur professionnel EXPIRÉE remonte dans les alertes
    (source ``carte_conducteur_pro``) ;
  - formation continue NARSA expirée/imminente remonte (source
    ``formation_narsa``) ;
  - conducteur sans ces documents (véhicule léger) -> aucune alerte
    supplémentaire (pas de régression sur le parc léger).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    Conducteur,
    EcheanceReglementaire,
    Vehicule,
)
from apps.flotte.selectors import (
    alertes_echeances_reglementaires,
    echeances_reglementaires_expirantes,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_actif(company, immat="TL-1"):
    veh = Vehicule.objects.create(
        company=company, immatriculation=immat, energie="diesel")
    return ActifFlotte.objects.create(company=company, vehicule=veh)


class ChronotachygrapheAlerteTests(TestCase):
    def setUp(self):
        self.co = make_company("tl-chrono", "TL Chrono")
        self.actif = make_actif(self.co, "CHR-1")
        self.today = datetime.date(2026, 6, 15)

    def test_echeance_j30_alertee(self):
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance=EcheanceReglementaire.TypeEcheance.CHRONOTACHYGRAPHE,
            date_echeance=self.today + datetime.timedelta(days=20))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        sources_types = [
            (a["source"], a["type"]) for a in result["alertes"]]
        self.assertIn(
            ("echeance_reglementaire", "chronotachygraphe"), sources_types)

    def test_echeance_hors_fenetre_absente(self):
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance=EcheanceReglementaire.TypeEcheance.CHRONOTACHYGRAPHE,
            date_echeance=self.today + datetime.timedelta(days=90))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 0)

    def test_selector_expirantes_inclut_chronotachygraphe(self):
        EcheanceReglementaire.objects.create(
            company=self.co, actif_flotte=self.actif,
            type_echeance=EcheanceReglementaire.TypeEcheance.CHRONOTACHYGRAPHE,
            date_echeance=self.today + datetime.timedelta(days=10))
        expirantes = echeances_reglementaires_expirantes(
            self.co, within=30, today=self.today)
        self.assertEqual(expirantes.count(), 1)


class ConducteurProNarsaAlerteTests(TestCase):
    def setUp(self):
        self.co = make_company("tl-cond", "TL Cond")
        self.today = datetime.date(2026, 6, 15)

    def test_carte_pro_expiree_alertee(self):
        Conducteur.objects.create(
            company=self.co, nom="Chauffeur Poids Lourd",
            carte_conducteur_pro_numero="CPC-1",
            carte_conducteur_pro_expiration=(
                self.today - datetime.timedelta(days=5)))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        sources = [a["source"] for a in result["alertes"]]
        self.assertIn("carte_conducteur_pro", sources)
        self.assertEqual(result["nb_echu"], 1)

    def test_formation_narsa_expirante_alertee(self):
        Conducteur.objects.create(
            company=self.co, nom="Chauffeur Narsa",
            formation_continue_narsa_date=self.today - datetime.timedelta(
                days=365),
            formation_continue_narsa_validite=(
                self.today + datetime.timedelta(days=7)))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        sources = [a["source"] for a in result["alertes"]]
        self.assertIn("formation_narsa", sources)

    def test_conducteur_sans_documents_transport_lourd_rien(self):
        # Chauffeur de véhicule léger : aucun de ces champs renseigné, aucune
        # alerte supplémentaire générée (pas de régression).
        Conducteur.objects.create(company=self.co, nom="Chauffeur Léger")
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 0)

    def test_conducteur_inactif_ignore(self):
        Conducteur.objects.create(
            company=self.co, nom="Chauffeur Inactif", actif=False,
            carte_conducteur_pro_expiration=(
                self.today - datetime.timedelta(days=5)))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 0)

    def test_scope_societe(self):
        autre = make_company("tl-cond-b", "TL Cond B")
        Conducteur.objects.create(
            company=autre, nom="Autre Chauffeur",
            carte_conducteur_pro_expiration=(
                self.today - datetime.timedelta(days=1)))
        result = alertes_echeances_reglementaires(self.co, today=self.today)
        self.assertEqual(result["nb_total"], 0)
