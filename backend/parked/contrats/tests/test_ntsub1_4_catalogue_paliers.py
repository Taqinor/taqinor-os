"""Tests NTSUB1-4 — Revenus récurrents : catalogue d'offres, add-ons, paliers
d'usage, compteurs génériques.

Couvre :
- NTSUB1 : CRUD company-scopé de ``PlanAbonnement`` (API), ``company`` posée
  côté serveur ; création d'un ``Contrat`` depuis un plan pré-remplit
  montant/plan_recurrent (snapshot) ; un contrat sans plan reste inchangé ;
  modifier le plan après coup ne change aucun contrat existant.
- NTSUB2 : ``AddOnAbonnement``/``AbonnementAddOnLigne`` — un add-on actif à la
  date du cycle ajoute son montant à la facture générée ; un add-on désactivé
  (``actif_jusqua`` dépassée) n'est plus facturé ; aucun impact sans add-on.
- NTSUB3 : ``PalierUsage`` (modèle + validation exactement addon XOR plan).
- NTSUB4 : ``CompteurUsage`` — ingestion idempotente, agrégation par période,
  absence de compteur = 0.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    AbonnementAddOnLigne,
    AddOnAbonnement,
    CompteurUsage,
    Contrat,
    EcheancierContrat,
    PlanAbonnement,
    PlanRecurrent,
)

User = get_user_model()

PLANS_ABONNEMENT = "/api/django/contrats/plans-abonnement/"
CONTRATS = "/api/django/contrats/contrats/"
COMPTEURS = "/api/django/contrats/compteurs-usage/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_plan_recurrent(company, nom="Mensuel"):
    return PlanRecurrent.objects.create(
        company=company, nom=nom, unite=PlanRecurrent.Unite.MENSUEL,
        intervalle=1)


def make_plan_abonnement(company, code="OFFRE1", prix_base="500"):
    return PlanAbonnement.objects.create(
        company=company, code=code, nom="Offre " + code,
        plan_recurrent=make_plan_recurrent(company, nom=f"Plan-{code}"),
        prix_base=Decimal(prix_base))


def make_contrat(company, montant="1000", client_id=None):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut=Contrat.Statut.ACTIF, client_id=client_id)


# ---------------------------------------------------------------------------
# NTSUB1 — PlanAbonnement (catalogue d'offres)
# ---------------------------------------------------------------------------


class PlanAbonnementApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub1-api", "Ntsub1Api")
        self.admin = make_user(self.co, "ntsub1-api-admin", role="admin")

    def test_creer_company_posee_serveur(self):
        plan_recurrent = make_plan_recurrent(self.co)
        api = auth(self.admin)
        res = api.post(
            PLANS_ABONNEMENT,
            {"code": "P1", "nom": "Plan un", "plan_recurrent": plan_recurrent.id,
             "prix_base": "300", "company": 999}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        plan = PlanAbonnement.objects.get(id=res.data["id"])
        self.assertEqual(plan.company_id, self.co.id)  # pas 999

    def test_code_unique_par_societe(self):
        plan_recurrent = make_plan_recurrent(self.co)
        PlanAbonnement.objects.create(
            company=self.co, code="DUP", nom="A", plan_recurrent=plan_recurrent)
        api = auth(self.admin)
        res = api.post(
            PLANS_ABONNEMENT,
            {"code": "DUP", "nom": "B", "plan_recurrent": plan_recurrent.id},
            format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_meme_code_autre_societe_autorise(self):
        autre_co = make_company("ntsub1-api-2", "Ntsub1Api2")
        PlanAbonnement.objects.create(
            company=autre_co, code="SAME", nom="Autre",
            plan_recurrent=make_plan_recurrent(autre_co))
        plan_recurrent = make_plan_recurrent(self.co)
        api = auth(self.admin)
        res = api.post(
            PLANS_ABONNEMENT,
            {"code": "SAME", "nom": "Moi", "plan_recurrent": plan_recurrent.id},
            format="json")
        self.assertEqual(res.status_code, 201, res.content)

    def test_scope_societe(self):
        autre_co = make_company("ntsub1-api-3", "Ntsub1Api3")
        make_plan_abonnement(self.co, code="MOI")
        make_plan_abonnement(autre_co, code="AUTRE")
        api = auth(self.admin)
        res = api.get(PLANS_ABONNEMENT)
        codes = {row["code"] for row in res.data["results"]} if isinstance(
            res.data, dict) and "results" in res.data else {
            row["code"] for row in res.data}
        self.assertIn("MOI", codes)
        self.assertNotIn("AUTRE", codes)

    def test_filtre_actif(self):
        make_plan_abonnement(self.co, code="ACTIF1")
        inactif = make_plan_abonnement(self.co, code="INACTIF1")
        inactif.actif = False
        inactif.save(update_fields=['actif'])
        api = auth(self.admin)
        res = api.get(f"{PLANS_ABONNEMENT}?actif=1")
        codes = {row["code"] for row in res.data["results"]} if isinstance(
            res.data, dict) and "results" in res.data else {
            row["code"] for row in res.data}
        self.assertIn("ACTIF1", codes)
        self.assertNotIn("INACTIF1", codes)


class AppliquerPlanAbonnementServiceTests(TestCase):
    """Snapshot : appliquer_plan_abonnement copie une fois, ne suit jamais."""

    def setUp(self):
        self.co = make_company("ntsub1-svc", "Ntsub1Svc")

    def test_applique_montant_et_plan_recurrent(self):
        plan = make_plan_abonnement(self.co, code="SVC1", prix_base="750")
        contrat = make_contrat(self.co, montant="0")
        services.appliquer_plan_abonnement(contrat, plan)
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('750'))
        self.assertEqual(contrat.plan_recurrent_id, plan.plan_recurrent_id)

    def test_modifier_le_plan_apres_coup_ne_change_pas_le_contrat(self):
        plan = make_plan_abonnement(self.co, code="SVC2", prix_base="750")
        contrat = make_contrat(self.co, montant="0")
        services.appliquer_plan_abonnement(contrat, plan)
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('750'))

        plan.prix_base = Decimal('9999')
        plan.save(update_fields=['prix_base'])

        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal('750'))  # inchangé (snapshot)


class ContratCreationDepuisPlanApiTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub1-create", "Ntsub1Create")
        self.admin = make_user(self.co, "ntsub1-create-admin", role="admin")

    def test_creation_avec_plan_sans_montant_pre_remplit(self):
        plan = make_plan_abonnement(self.co, code="CR1", prix_base="620")
        api = auth(self.admin)
        res = api.post(
            CONTRATS,
            {"objet": "Contrat depuis plan", "type_contrat": "om",
             "plan_abonnement": plan.id}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        contrat = Contrat.objects.get(id=res.data["id"])
        self.assertEqual(contrat.montant, Decimal('620'))
        self.assertEqual(contrat.plan_recurrent_id, plan.plan_recurrent_id)

    def test_creation_avec_plan_et_montant_explicite_ne_ecrase_pas(self):
        plan = make_plan_abonnement(self.co, code="CR2", prix_base="620")
        api = auth(self.admin)
        res = api.post(
            CONTRATS,
            {"objet": "Contrat montant explicite", "type_contrat": "om",
             "plan_abonnement": plan.id, "montant": "111"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        contrat = Contrat.objects.get(id=res.data["id"])
        self.assertEqual(contrat.montant, Decimal('111'))  # pas écrasé

    def test_creation_sans_plan_reste_inchangee(self):
        api = auth(self.admin)
        res = api.post(
            CONTRATS,
            {"objet": "Contrat classique", "type_contrat": "om",
             "montant": "200"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        contrat = Contrat.objects.get(id=res.data["id"])
        self.assertEqual(contrat.montant, Decimal('200'))
        self.assertIsNone(contrat.plan_abonnement_id)

    def test_plan_abonnement_autre_societe_refuse(self):
        autre_co = make_company("ntsub1-create-2", "Ntsub1Create2")
        plan_autre = make_plan_abonnement(autre_co, code="AUTRE")
        api = auth(self.admin)
        res = api.post(
            CONTRATS,
            {"objet": "Contrat interdit", "type_contrat": "om",
             "plan_abonnement": plan_autre.id}, format="json")
        self.assertEqual(res.status_code, 400, res.content)


# ---------------------------------------------------------------------------
# NTSUB2 — Add-ons
# ---------------------------------------------------------------------------


class AddOnFacturationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub2-fact", "Ntsub2Fact")

    def _addon(self, prix="150"):
        return AddOnAbonnement.objects.create(
            company=self.co, code="OPT1", nom="Supervision avancée",
            prix_unitaire=Decimal(prix))

    def test_addon_actif_est_compte(self):
        import datetime

        addon = self._addon(prix="150")
        contrat = make_contrat(self.co)
        AbonnementAddOnLigne.objects.create(
            company=self.co, type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id, addon=addon, quantite=2,
            actif_depuis=datetime.date(2026, 1, 1))
        montant = services.montant_addons_periode(
            self.co, type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id, periode_fin=datetime.date(2026, 3, 1))
        self.assertEqual(montant, Decimal('300'))  # 2 x 150

    def test_addon_desactive_avant_periode_non_compte(self):
        import datetime

        addon = self._addon(prix="150")
        contrat = make_contrat(self.co)
        AbonnementAddOnLigne.objects.create(
            company=self.co, type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id, addon=addon, quantite=1,
            actif_depuis=datetime.date(2026, 1, 1),
            actif_jusqua=datetime.date(2026, 1, 31))
        montant = services.montant_addons_periode(
            self.co, type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id, periode_fin=datetime.date(2026, 3, 1))
        self.assertEqual(montant, Decimal('0'))

    def test_sans_addon_aucun_impact(self):
        import datetime

        contrat = make_contrat(self.co)
        montant = services.montant_addons_periode(
            self.co, type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id, periode_fin=datetime.date(2026, 3, 1))
        self.assertEqual(montant, Decimal('0'))


class FacturerLigneEcheanceAvecAddonsTests(TestCase):
    """La facturation récurrente XCTR5 (facturer_ligne_echeance) inclut
    désormais les add-ons actifs de la période — NTSUB2."""

    def setUp(self):
        self.co = make_company("ntsub2-cycle", "Ntsub2Cycle")

    def _preparer_echeancier(self, montant='1000'):
        import datetime

        from apps.crm.models import Client

        client = Client.objects.create(company=self.co, nom='Client Test')
        contrat = make_contrat(self.co, montant=montant, client_id=client.id)
        echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True)
        ligne = services.ajouter_ligne_echeance(
            echeancier, date_echeance=datetime.date(2026, 3, 1),
            montant=Decimal(montant))
        return contrat, ligne

    def test_sans_addon_montant_inchange(self):
        contrat, ligne = self._preparer_echeancier(montant='1000')
        facture = services.facturer_ligne_echeance(ligne)
        self.assertEqual(facture.montant_ttc, Decimal('1000.00'))

    def test_avec_addon_actif_montant_augmente(self):
        addon = AddOnAbonnement.objects.create(
            company=self.co, code='OPTF', nom='Option facturée',
            prix_unitaire=Decimal('100'))
        contrat, ligne = self._preparer_echeancier(montant='1000')
        AbonnementAddOnLigne.objects.create(
            company=self.co, type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id, addon=addon, quantite=1,
            actif_depuis='2026-01-01')
        facture = services.facturer_ligne_echeance(ligne)
        self.assertEqual(facture.montant_ttc, Decimal('1100.00'))  # 1000 + 100


# ---------------------------------------------------------------------------
# NTSUB3 — PalierUsage
# ---------------------------------------------------------------------------


class PalierUsageModelTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub3-model", "Ntsub3Model")

    def test_palier_addon_xor_plan_valide_via_api(self):
        addon = AddOnAbonnement.objects.create(
            company=self.co, code='USG', nom='Usage', prix_unitaire=Decimal('0'))
        admin = make_user(self.co, "ntsub3-admin", role="admin")
        api = auth(admin)
        res = api.post(
            "/api/django/contrats/paliers-usage/",
            {"addon": addon.id, "seuil_min": "0", "seuil_max": "100",
             "prix_unitaire": "2", "mode": "volume"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)

    def test_palier_sans_addon_ni_plan_refuse(self):
        admin = make_user(self.co, "ntsub3-admin2", role="admin")
        api = auth(admin)
        res = api.post(
            "/api/django/contrats/paliers-usage/",
            {"seuil_min": "0", "seuil_max": "100", "prix_unitaire": "2"},
            format="json")
        self.assertEqual(res.status_code, 400, res.content)

    def test_palier_addon_et_plan_ensemble_refuse(self):
        addon = AddOnAbonnement.objects.create(
            company=self.co, code='USG2', nom='Usage2', prix_unitaire=Decimal('0'))
        plan = make_plan_abonnement(self.co, code='USGPLAN')
        admin = make_user(self.co, "ntsub3-admin3", role="admin")
        api = auth(admin)
        res = api.post(
            "/api/django/contrats/paliers-usage/",
            {"addon": addon.id, "plan_abonnement": plan.id, "seuil_min": "0",
             "prix_unitaire": "2"}, format="json")
        self.assertEqual(res.status_code, 400, res.content)


# ---------------------------------------------------------------------------
# NTSUB4 — CompteurUsage
# ---------------------------------------------------------------------------


class CompteurUsageIngestionTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub4-ingest", "Ntsub4Ingest")
        self.admin = make_user(self.co, "ntsub4-admin", role="admin")

    def test_ingestion_simple(self):
        api = auth(self.admin)
        res = api.post(
            COMPTEURS,
            {"type_cible": "contrat", "cible_id": 1,
             "code_compteur": "interventions", "periode_debut": "2026-01-01",
             "periode_fin": "2026-01-31", "quantite": "5"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(
            CompteurUsage.objects.filter(company=self.co).count(), 1)

    def test_ingestion_deux_fois_meme_periode_ne_duplique_pas(self):
        api = auth(self.admin)
        payload = {
            "type_cible": "contrat", "cible_id": 1,
            "code_compteur": "interventions", "periode_debut": "2026-01-01",
            "periode_fin": "2026-01-31", "quantite": "5",
        }
        res1 = api.post(COMPTEURS, payload, format="json")
        self.assertEqual(res1.status_code, 201, res1.content)
        payload["quantite"] = "8"  # relevé corrigé
        res2 = api.post(COMPTEURS, payload, format="json")
        self.assertEqual(res2.status_code, 201, res2.content)

        self.assertEqual(
            CompteurUsage.objects.filter(company=self.co).count(), 1)
        compteur = CompteurUsage.objects.get(company=self.co)
        self.assertEqual(compteur.quantite, Decimal('8'))  # mis à jour

    def test_scope_societe(self):
        autre_co = make_company("ntsub4-ingest-2", "Ntsub4Ingest2")
        services.ingerer_compteur_usage(
            self.co, type_cible='contrat', cible_id=1,
            code_compteur='c1', periode_debut='2026-01-01',
            periode_fin='2026-01-31', quantite=Decimal('3'))
        services.ingerer_compteur_usage(
            autre_co, type_cible='contrat', cible_id=1,
            code_compteur='c1', periode_debut='2026-01-01',
            periode_fin='2026-01-31', quantite=Decimal('99'))
        api = auth(self.admin)
        res = api.get(COMPTEURS)
        quantites = [row["quantite"] for row in res.data["results"]] if isinstance(
            res.data, dict) and "results" in res.data else [
            row["quantite"] for row in res.data]
        self.assertEqual(len(quantites), 1)
        self.assertEqual(Decimal(quantites[0]), Decimal('3'))


class TotalUsagePeriodeSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company("ntsub4-total", "Ntsub4Total")

    def test_somme_correspond_aux_compteurs(self):
        services.ingerer_compteur_usage(
            self.co, type_cible='contrat', cible_id=7,
            code_compteur='api_calls', periode_debut='2026-01-01',
            periode_fin='2026-01-31', quantite=Decimal('10'))
        services.ingerer_compteur_usage(
            self.co, type_cible='contrat', cible_id=7,
            code_compteur='api_calls', periode_debut='2026-02-01',
            periode_fin='2026-02-28', quantite=Decimal('15'))
        total = services.total_usage_periode(
            self.co, type_cible='contrat', cible_id=7,
            code_compteur='api_calls', periode_debut='2026-01-01',
            periode_fin='2026-02-28')
        self.assertEqual(total, Decimal('25'))

    def test_absence_de_compteur_renvoie_zero(self):
        total = services.total_usage_periode(
            self.co, type_cible='contrat', cible_id=999,
            code_compteur='inexistant', periode_debut='2026-01-01',
            periode_fin='2026-01-31')
        self.assertEqual(total, Decimal('0'))
