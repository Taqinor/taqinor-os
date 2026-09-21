"""Tests XFLT4 — Fiche véhicule enrichie + cycle de vie complet.

Couvre :
- Modèle ``Vehicule`` :
  - nouveaux champs additifs (vin, annee, date_acquisition, type_fiscal,
    tags, checklist_mise_en_service) ;
  - nouveaux statuts (commande, a_vendre, vendu) aux côtés des 3 historiques ;
  - ``checklist_mise_en_service_ok()``.
- Service ``changer_statut_vehicule`` :
  - transition journalisée (JournalStatutVehicule, user + horodatage
    serveur-side) ;
  - passage commande→actif refusé si checklist incomplète (message FR) ;
  - passage commande→actif accepté si checklist complète ;
  - statut invalide refusé ; même statut = no-op sans journal.
- Endpoints API :
  - ``POST /vehicules/<id>/changer-statut/`` (écriture responsable/admin) ;
  - ``GET /vehicules/<id>/historique/`` (lecture tout rôle).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import JournalStatutVehicule, Vehicule
from apps.flotte.services import changer_statut_vehicule

User = get_user_model()


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


CHECKLIST_COMPLETE = {
    'immatriculation_faite': True, 'plaques': True,
    'assurance_active': True, 'carte_grise_recue': True,
}


class VehiculeModelXflt4Tests(TestCase):
    def setUp(self):
        self.co = make_company("veh-xflt4", "Veh Xflt4")

    def test_nouveaux_champs_additifs(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="V1", energie="diesel",
            vin="VF1XXXX1234567890", annee=2022,
            type_fiscal=Vehicule.TypeFiscal.UTILITAIRE, tags=["chantier"])
        self.assertEqual(veh.vin, "VF1XXXX1234567890")
        self.assertEqual(veh.annee, 2022)
        self.assertEqual(veh.tags, ["chantier"])

    def test_nouveaux_statuts(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="V2", energie="diesel",
            statut=Vehicule.Statut.COMMANDE)
        self.assertEqual(veh.statut, "commande")
        veh.statut = Vehicule.Statut.A_VENDRE
        veh.save()
        veh.statut = Vehicule.Statut.VENDU
        veh.save()
        self.assertEqual(veh.statut, "vendu")

    def test_statuts_historiques_intacts(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="V3", energie="diesel")
        self.assertEqual(veh.statut, Vehicule.Statut.ACTIF)

    def test_checklist_incomplete(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="V4", energie="diesel",
            checklist_mise_en_service={'immatriculation_faite': True})
        self.assertFalse(veh.checklist_mise_en_service_ok())

    def test_checklist_complete(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="V5", energie="diesel",
            checklist_mise_en_service=CHECKLIST_COMPLETE)
        self.assertTrue(veh.checklist_mise_en_service_ok())


class ChangerStatutVehiculeServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("cst-svc", "Cst Svc")
        self.user = make_user(self.co, "cst-user")

    def test_transition_journalisee(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CS1", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        changer_statut_vehicule(
            veh, Vehicule.Statut.MAINTENANCE, user=self.user)
        veh.refresh_from_db()
        self.assertEqual(veh.statut, "maintenance")
        entree = JournalStatutVehicule.objects.get(vehicule=veh)
        self.assertEqual(entree.ancien_statut, "actif")
        self.assertEqual(entree.nouveau_statut, "maintenance")
        self.assertEqual(entree.user_id, self.user.id)

    def test_commande_vers_actif_refuse_checklist_incomplete(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CS2", energie="diesel",
            statut=Vehicule.Statut.COMMANDE,
            checklist_mise_en_service={'immatriculation_faite': True})
        with self.assertRaises(ValueError) as ctx:
            changer_statut_vehicule(veh, Vehicule.Statut.ACTIF, user=self.user)
        self.assertIn("checklist", str(ctx.exception).lower())
        veh.refresh_from_db()
        self.assertEqual(veh.statut, "commande")
        self.assertEqual(JournalStatutVehicule.objects.count(), 0)

    def test_commande_vers_actif_accepte_checklist_complete(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CS3", energie="diesel",
            statut=Vehicule.Statut.COMMANDE,
            checklist_mise_en_service=CHECKLIST_COMPLETE)
        changer_statut_vehicule(veh, Vehicule.Statut.ACTIF, user=self.user)
        veh.refresh_from_db()
        self.assertEqual(veh.statut, "actif")
        self.assertEqual(JournalStatutVehicule.objects.count(), 1)

    def test_statut_invalide_refuse(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CS4", energie="diesel")
        with self.assertRaises(ValueError):
            changer_statut_vehicule(veh, "statut_inconnu", user=self.user)

    def test_meme_statut_noop_sans_journal(self):
        veh = Vehicule.objects.create(
            company=self.co, immatriculation="CS5", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        changer_statut_vehicule(veh, Vehicule.Statut.ACTIF, user=self.user)
        self.assertEqual(JournalStatutVehicule.objects.count(), 0)


class VehiculeCycleDeVieApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company("cv-cycle-a", "Cv Cycle A")
        self.co_b = make_company("cv-cycle-b", "Cv Cycle B")
        self.admin_a = make_user(self.co_a, "cyc-admin-a", "admin")
        self.user_a = make_user(self.co_a, "cyc-user-a", "normal")

    def test_changer_statut_forbidden_for_normal_role(self):
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation="API1", energie="diesel")
        resp = auth(self.user_a).post(
            f"/api/django/flotte/vehicules/{veh.id}/changer-statut/",
            {"statut": "maintenance"}, format="json")
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_changer_statut_ok(self):
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation="API2", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        resp = auth(self.admin_a).post(
            f"/api/django/flotte/vehicules/{veh.id}/changer-statut/",
            {"statut": "maintenance"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'maintenance')

    def test_changer_statut_commande_actif_bloque_message_fr(self):
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation="API3", energie="diesel",
            statut=Vehicule.Statut.COMMANDE)
        resp = auth(self.admin_a).post(
            f"/api/django/flotte/vehicules/{veh.id}/changer-statut/",
            {"statut": "actif"}, format="json")
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn("checklist", resp.data['detail'].lower())

    def test_historique_read_any_role_scoped(self):
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation="API4", energie="diesel",
            statut=Vehicule.Statut.ACTIF)
        auth(self.admin_a).post(
            f"/api/django/flotte/vehicules/{veh.id}/changer-statut/",
            {"statut": "maintenance"}, format="json")
        resp = auth(self.user_a).get(
            f"/api/django/flotte/vehicules/{veh.id}/historique/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['nouveau_statut'], 'maintenance')
