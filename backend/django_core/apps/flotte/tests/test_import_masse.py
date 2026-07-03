"""Tests XFLT22 — Import CSV du parc + opérations en masse.

Couvre :
- Service ``creer_vehicule_import`` : crée un véhicule depuis une ligne,
  saute un doublon (immatriculation), rejette une ligne sans immatriculation.
- Service ``importer_vehicules_csv`` : rapport créés/doublons/erreurs,
  ``dry_run=True`` ne persiste rien.
- Service ``reaffecter_conducteurs_masse`` : clôt l'affectation courante et
  ouvre la nouvelle ; contrôle permis par ligne (échec listé sans bloquer
  le lot).
- Service ``rollout_plan_entretien`` : duplique le plan sur une sélection
  d'actifs, saute un actif déjà couvert (même type d'entretien).
- Endpoint ``POST /affectations/masse/`` : réaffectation en masse.
- Endpoint ``POST /plans-entretien/<id>/rollout/``.
- Endpoint ``/api/django/imports/commit/`` (target=vehicules) : import de
  10 lignes dont 2 doublons → 8 créés + rapport (via le framework
  ``apps.dataimport``, écriture déléguée à ``apps.flotte.services``).
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import (
    ActifFlotte,
    AffectationConducteur,
    Conducteur,
    PlanEntretien,
    Vehicule,
)
from apps.flotte.services import (
    creer_vehicule_import,
    importer_vehicules_csv,
    reaffecter_conducteurs_masse,
    rollout_plan_entretien,
)

User = get_user_model()

URL_AFFECTATIONS_MASSE = "/api/django/flotte/affectations/masse/"
URL_IMPORT_COMMIT = "/api/django/imports/commit/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


class CreerVehiculeImportServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-veh-svc", "Imp Veh Svc")

    def test_cree_depuis_ligne(self):
        statut, message = creer_vehicule_import(self.co, {
            "immatriculation": "IMP-1", "marque": "Renault",
            "modele": "Kangoo", "energie": "diesel", "kilometrage": "1000",
        })
        self.assertEqual(statut, "cree")
        self.assertIsNone(message)
        self.assertTrue(Vehicule.objects.filter(
            company=self.co, immatriculation="IMP-1").exists())

    def test_doublon_saute(self):
        Vehicule.objects.create(
            company=self.co, immatriculation="IMP-2", energie="diesel")
        statut, _ = creer_vehicule_import(
            self.co, {"immatriculation": "IMP-2"})
        self.assertEqual(statut, "doublon")
        self.assertEqual(Vehicule.objects.filter(
            company=self.co, immatriculation="IMP-2").count(), 1)

    def test_sans_immatriculation_erreur(self):
        statut, message = creer_vehicule_import(self.co, {"marque": "X"})
        self.assertEqual(statut, "erreur")
        self.assertIsNotNone(message)


class ImporterVehiculesCsvServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-veh-csv", "Imp Veh Csv")

    def test_rapport_crees_doublons(self):
        Vehicule.objects.create(
            company=self.co, immatriculation="IMP-D1", energie="diesel")
        lignes = [
            {"immatriculation": "IMP-D1"},  # doublon
            {"immatriculation": "IMP-N1"},
            {"immatriculation": "IMP-N2"},
        ]
        rapport = importer_vehicules_csv(self.co, lignes)
        self.assertEqual(rapport["crees"], 2)
        self.assertEqual(rapport["doublons"], 1)
        self.assertEqual(rapport["erreurs"], [])

    def test_dry_run_ne_persiste_rien(self):
        lignes = [{"immatriculation": "IMP-DRY1"}]
        rapport = importer_vehicules_csv(self.co, lignes, dry_run=True)
        self.assertEqual(rapport["crees"], 1)
        self.assertFalse(Vehicule.objects.filter(
            company=self.co, immatriculation="IMP-DRY1").exists())


class ReaffecterConducteursMasseServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-reaff", "Imp Reaff")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="RA-1", energie="diesel")
        self.cond_actuel = Conducteur.objects.create(company=self.co, nom="A")
        self.cond_nouveau = Conducteur.objects.create(company=self.co, nom="B")
        self.affectation = AffectationConducteur.objects.create(
            company=self.co, conducteur=self.cond_actuel, vehicule=self.veh,
            date_debut=datetime.date(2026, 1, 1), actif=True)

    def test_cloture_courante_et_ouvre_nouvelle(self):
        resultat = reaffecter_conducteurs_masse(
            self.co, [{
                'vehicule_id': self.veh.id,
                'conducteur_id': self.cond_nouveau.id,
            }], date_debut=datetime.date(2026, 6, 1))
        self.assertEqual(len(resultat['reussies']), 1)
        self.assertEqual(resultat['echecs'], [])

        self.affectation.refresh_from_db()
        self.assertFalse(self.affectation.actif)
        self.assertEqual(
            self.affectation.date_fin, datetime.date(2026, 5, 31))

        nouvelle = AffectationConducteur.objects.get(
            company=self.co, vehicule=self.veh, actif=True)
        self.assertEqual(nouvelle.conducteur_id, self.cond_nouveau.id)

    def test_echec_permis_liste_sans_bloquer_lot(self):
        self.veh.categorie_permis_requise = 'CE'
        self.veh.save()
        veh2 = Vehicule.objects.create(
            company=self.co, immatriculation="RA-2", energie="diesel")
        resultat = reaffecter_conducteurs_masse(
            self.co, [
                {'vehicule_id': self.veh.id,
                 'conducteur_id': self.cond_nouveau.id},
                {'vehicule_id': veh2.id, 'conducteur_id': self.cond_nouveau.id},
            ], date_debut=datetime.date(2026, 6, 1))
        self.assertEqual(len(resultat['echecs']), 1)
        self.assertEqual(len(resultat['reussies']), 1)


class RolloutPlanEntretienServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-rollout", "Imp Rollout")
        veh1 = Vehicule.objects.create(
            company=self.co, immatriculation="RO-1", energie="diesel")
        self.actif1 = ActifFlotte.objects.create(company=self.co, vehicule=veh1)
        veh2 = Vehicule.objects.create(
            company=self.co, immatriculation="RO-2", energie="diesel")
        self.actif2 = ActifFlotte.objects.create(company=self.co, vehicule=veh2)
        self.plan = PlanEntretien.objects.create(
            company=self.co, actif_flotte=self.actif1,
            type_entretien="Vidange", intervalle_km=10000)

    def test_duplique_sur_selection(self):
        resultat = rollout_plan_entretien(
            self.co, self.plan, [self.actif2.id])
        self.assertEqual(len(resultat['crees']), 1)
        self.assertEqual(resultat['crees'][0].type_entretien, "Vidange")

    def test_saute_actif_deja_couvert(self):
        PlanEntretien.objects.create(
            company=self.co, actif_flotte=self.actif2,
            type_entretien="Vidange", intervalle_km=8000)
        resultat = rollout_plan_entretien(
            self.co, self.plan, [self.actif2.id])
        self.assertEqual(resultat['crees'], [])
        self.assertIn(self.actif2.id, resultat['ignores'])


class AffectationMasseApiTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-masse-api", "Imp Masse Api")
        self.user = make_user(self.co, "imp-masse-user")
        self.veh = Vehicule.objects.create(
            company=self.co, immatriculation="MA-1", energie="diesel")
        self.cond = Conducteur.objects.create(company=self.co, nom="C")

    def test_masse_endpoint(self):
        resp = auth(self.user).post(URL_AFFECTATIONS_MASSE, {
            "reaffectations": [
                {"vehicule_id": self.veh.id, "conducteur_id": self.cond.id},
            ],
            "date_debut": "2026-06-01",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data["reussies"]), 1)

    def test_masse_endpoint_requiert_champs(self):
        resp = auth(self.user).post(URL_AFFECTATIONS_MASSE, {}, format="json")
        self.assertEqual(resp.status_code, 400)


class RolloutPlanApiTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-rollout-api", "Imp Rollout Api")
        self.user = make_user(self.co, "imp-rollout-user")
        veh1 = Vehicule.objects.create(
            company=self.co, immatriculation="RO-A1", energie="diesel")
        self.actif1 = ActifFlotte.objects.create(company=self.co, vehicule=veh1)
        veh2 = Vehicule.objects.create(
            company=self.co, immatriculation="RO-A2", energie="diesel")
        self.actif2 = ActifFlotte.objects.create(company=self.co, vehicule=veh2)
        self.plan = PlanEntretien.objects.create(
            company=self.co, actif_flotte=self.actif1,
            type_entretien="Révision", intervalle_km=15000)

    def test_rollout_endpoint(self):
        resp = auth(self.user).post(
            f"/api/django/flotte/plans-entretien/{self.plan.id}/rollout/",
            {"actif_flotte_ids": [self.actif2.id]}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data["crees"]), 1)


class ImportVehiculesFrameworkApiTests(TestCase):
    def setUp(self):
        self.co = make_company("imp-fw", "Imp Fw")
        self.user = make_user(self.co, "imp-fw-user", role="responsable")
        # target=vehicules n'est pas gardé par la permission produits (QG4) —
        # reste sur la règle historique responsable/admin.
        self.api = auth(self.user)

    def _csv(self, content):
        return SimpleUploadedFile(
            "vehicules.csv", content.encode("utf-8"), content_type="text/csv")

    def test_import_10_lignes_2_doublons_8_crees(self):
        Vehicule.objects.create(
            company=self.co, immatriculation="FW-1", energie="diesel")
        Vehicule.objects.create(
            company=self.co, immatriculation="FW-2", energie="diesel")

        lignes = ["Immatriculation,Marque,Modele,Energie,Km"]
        # 2 doublons déjà présents.
        lignes.append("FW-1,Renault,Kangoo,diesel,1000")
        lignes.append("FW-2,Renault,Kangoo,diesel,1000")
        # 8 nouvelles.
        for i in range(3, 11):
            lignes.append(f"FW-{i},Renault,Kangoo,diesel,1000")
        contenu = "\n".join(lignes) + "\n"

        resp = self.api.post(URL_IMPORT_COMMIT, {
            "file": self._csv(contenu), "target": "vehicules",
        }, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["created"], 8)
        self.assertEqual(len(resp.data["skipped"]), 2)
        self.assertEqual(
            Vehicule.objects.filter(company=self.co).count(), 10)
