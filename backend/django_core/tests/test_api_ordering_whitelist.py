"""YAPIC2 — garde : tout viewset dont le tri (`OrderingFilter`) est actif
déclare une whitelist `ordering_fields` explicite (jamais `None`/`'__all__'`).

DB-free (AST uniquement, mirrors ``core/action_permission_scan.py``'s
static-scan style) : ce module ne fait tourner AUCUNE requête et n'a besoin
d'AUCUN `django.setup()` — il lit le SOURCE des `urls.py` (pour "les
viewsets enregistrés via les routers" — chaque `<router>.register(prefix,
ViewSetClass)`) puis le source des fichiers de vues pour résoudre
`filter_backends`/`ordering_fields` de chaque viewset trouvé.

Un viewset est jugé "tri actif" si :
  * il déclare SA PROPRE `filter_backends` et `OrderingFilter` y figure, OU
  * il ne déclare PAS `filter_backends` DU TOUT — il hérite alors du défaut
    global `REST_FRAMEWORK['DEFAULT_FILTER_BACKENDS']` (YAPIC2, posé dans
    `erp_agentique/settings/base.py`), qui INCLUT `OrderingFilter`.

C'est un RATCHET (même pattern que ``core/tests/test_action_permissions.py``
UNGUARDED_ACTION_BASELINE) : ``ORDERING_WHITELIST_EXEMPT`` fige la dette
actuelle (générée à l'écriture de ce test) — un NOUVEAU viewset non-conforme
absent de cette liste fait échouer le test ; un viewset RETIRÉ de la liste
(parce qu'il a reçu un `ordering_fields` explicite) ne doit JAMAIS y être
laissé (test de fraîcheur du baseline ci-dessous).
"""
from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = DJANGO_CORE_ROOT / "apps"

# Non-app URLconf modules that also register DRF routers (foundation apps,
# not under apps/).
EXTRA_URLS_MODULES = {
    "authentication": DJANGO_CORE_ROOT / "authentication" / "urls.py",
    "core": DJANGO_CORE_ROOT / "core" / "urls.py",
}

# Baseline of currently-noncompliant registered viewsets, as
# "app.ViewSetClassName" — REGENERATED 2026-09-28 (ERR-QAH-TESTS-RACINE) by
# re-running `scan_noncompliant_viewsets()` against the real repo: this
# module had never run in CI (`backend/django_core/tests/` was not a
# discovery root — see `scripts/ci_shard.py` TOP_LEVEL_MODULES), so the
# 2026-07-12 baseline had drifted badly out of sync with the many viewsets
# added since (adsengine, crm.Playbook*, stock.PortailTiersTokenViewSet…)
# and carried dozens of stale entries for apps parked by SOLMVP53. This set
# is now EXACTLY `scan_noncompliant_viewsets()`'s output — verified
# identical to `test_api_surface_parity.py`'s own scan (YAPIC11, shares this
# baseline). The 4 previously-flagged stock views (categorie/fournisseur/
# kit/fiche_technique) are FIXED (ordering_fields now set) and therefore
# deliberately ABSENT here. Tightening this baseline further (adding
# ordering_fields to an entry, dropping it here) stays future work — this is
# a debt-tracking ratchet, not a security control: it whitelists which
# viewsets DON'T yet have an explicit `ordering_fields`, it does not disable
# any permission or scoping check.
ORDERING_WHITELIST_EXEMPT: set[str] = {
    "accessreview.AccessReviewCampaignViewSet",
    "accessreview.SodRuleViewSet",
    "adsengine.AdCampaignMirrorViewSet",
    "adsengine.AnnotationViewSet",
    "adsengine.AnomalyEventViewSet",
    "adsengine.ArmDailyStatViewSet",
    "adsengine.AssumptionNodeViewSet",
    "adsengine.BrandKitViewSet",
    "adsengine.CommentKeywordRuleViewSet",
    "adsengine.CompetitorAdObservationViewSet",
    "adsengine.CompetitorPageViewSet",
    "adsengine.ConsentRecordViewSet",
    "adsengine.CreativeAssetViewSet",
    "adsengine.CreativeBacklogItemViewSet",
    "adsengine.CreativeGenerationBatchViewSet",
    "adsengine.CreativePolicyViewSet",
    "adsengine.DecisionLogViewSet",
    "adsengine.EngineActionViewSet",
    "adsengine.EngineAlertViewSet",
    "adsengine.ExperimentArmViewSet",
    "adsengine.ExperimentViewSet",
    "adsengine.FactEntryViewSet",
    "adsengine.FactTableViewSet",
    "adsengine.FlightPhaseViewSet",
    "adsengine.FlightPlanViewSet",
    "adsengine.GuardrailConfigViewSet",
    "adsengine.MetaConnectionViewSet",
    "adsengine.ProposalTemplateViewSet",
    "adsengine.ReconciliationSnapshotViewSet",
    "adsengine.RulePolicyViewSet",
    "authentication.CompanyViewSet",
    "authentication.UserViewSet",
    "automation.AutomationRuleVersionViewSet",
    "crm.AppareilEquipeViewSet",
    "crm.ApporteurViewSet",
    "crm.CanalViewSet",
    "crm.DealEnregistreViewSet",
    "crm.DefiViewSet",
    "crm.EquipeCommercialeViewSet",
    "crm.ForecastEntryViewSet",
    "crm.LeadTagViewSet",
    "crm.MotifPerteViewSet",
    "crm.ObjectifCommercialViewSet",
    "crm.ParrainageViewSet",
    "crm.PlanActiviteViewSet",
    "crm.PlanCompteViewSet",
    "crm.PlaybookEtapeViewSet",
    "crm.PlaybookTacheViewSet",
    "crm.PlaybookViewSet",
    "crm.RelanceEtapeViewSet",
    "crm.RevueCompteViewSet",
    "crm.SalleVenteViewSet",
    "crm.SavedViewViewSet",
    "crm.SiteProfileViewSet",
    "crm.WebsiteLeadPayloadViewSet",
    "customfields.CustomFieldDefViewSet",
    "customfields.CustomObjectDefViewSet",
    "customfields.FieldRolePermissionViewSet",
    "ged.DocumentLienViewSet",
    "ged.DocumentTagAssignmentViewSet",
    "ged.QuotaStockageViewSet",
    "identity.IdentityProviderViewSet",
    "identity.IpAllowRuleViewSet",
    "identity.NetworkPolicyViewSet",
    "identity.TrustedDeviceViewSet",
    "installations.AppelCommandeViewSet",
    "installations.ApprobationBCFViewSet",
    "installations.BinAffectationViewSet",
    "installations.BinLocationViewSet",
    "installations.BudgetEngagementViewSet",
    "installations.BudgetProjetViewSet",
    "installations.CategorieStockageViewSet",
    "installations.ChecklistEtapeModeleViewSet",
    "installations.ChecklistTemplateViewSet",
    "installations.ColisLigneViewSet",
    "installations.ColisViewSet",
    "installations.CommandeCadreLigneViewSet",
    "installations.CommandeCadreViewSet",
    "installations.CommissioningRecordViewSet",
    "installations.ComptageLigneViewSet",
    "installations.ContratPrixFournisseurViewSet",
    "installations.ContratPrixLigneViewSet",
    "installations.ControleQualiteModeleViewSet",
    "installations.DemandeAchatLigneViewSet",
    "installations.DemandeAchatViewSet",
    "installations.DemandeTransfertViewSet",
    "installations.DossierImportViewSet",
    "installations.EquipeViewSet",
    "installations.EtapeAssemblageViewSet",
    "installations.FicheInterventionChampViewSet",
    "installations.FicheInterventionTemplateViewSet",
    "installations.FraisImportViewSet",
    "installations.GeofenceAlertViewSet",
    "installations.GpsConsentRecordViewSet",
    "installations.KitComposantViewSet",
    "installations.KitViewSet",
    "installations.LandedCostLigneViewSet",
    "installations.LivraisonLigneViewSet",
    "installations.LivraisonViewSet",
    "installations.LotPrelevementViewSet",
    "installations.MaterielConsigneViewSet",
    "installations.OrdreAssemblageLigneViewSet",
    "installations.OrdreAssemblageViewSet",
    "installations.OrdreDemontageLigneViewSet",
    "installations.OrdreDemontageViewSet",
    "installations.PickListLigneViewSet",
    "installations.PickListViewSet",
    "installations.PositionTechnicienViewSet",
    "installations.PreuveLivraisonViewSet",
    "installations.ProjetChantierViewSet",
    "installations.ProjetDevisViewSet",
    "installations.ProjetTacheViewSet",
    "installations.ProjetTicketViewSet",
    "installations.ProjetViewSet",
    "installations.PutAwayViewSet",
    "installations.ReceptionNonFactureeViewSet",
    "installations.RegleApprobationAchatViewSet",
    "installations.RegleRangementViewSet",
    "installations.RegleReapproViewSet",
    "installations.RetourLivraisonLigneViewSet",
    "installations.RetourLivraisonViewSet",
    "installations.RetourMaterielLigneViewSet",
    "installations.RetourMaterielViewSet",
    "installations.SafetyChecklistSlotViewSet",
    "installations.SerieEntrepotViewSet",
    "installations.SessionComptageViewSet",
    "installations.SeuilApprobationBCFViewSet",
    "installations.ShotListSlotViewSet",
    "installations.SousTraitantViewSet",
    "installations.StageModeleViewSet",
    "installations.TransporteurViewSet",
    "installations.TypeInterventionViewSet",
    "monitoring.CleaningEventViewSet",
    "monitoring.MonitoringConfigViewSet",
    "monitoring.MonitoringSettingsViewSet",
    "monitoring.ProductionReadingViewSet",
    "monitoring.ProductionWarrantyViewSet",
    "notifications.AnnonceViewSet",
    "notifications.HolidayViewSet",
    "notifications.MessageAccueilViewSet",
    "notifications.NotificationPreferenceViewSet",
    "notifications.NotificationRoutingRuleViewSet",
    "notifications.NotificationViewSet",
    "notifications.WhatsAppTemplateViewSet",
    "notifications.WorkingHoursConfigViewSet",
    "offlinesync.OfflineOperationViewSet",
    "onboarding.OnboardingItemsMasquesViewSet",
    "onboarding.OnboardingProgressViewSet",
    "onboarding.ProductTourViewSet",
    "outillage.KitOutillageItemViewSet",
    "outillage.KitOutillageViewSet",
    "publicapi.ApiKeyViewSet",
    "publicapi.WebhookViewSet",
    "records.ActivityTypeViewSet",
    "records.ActivityViewSet",
    "records.AttachmentViewSet",
    "records.CommentViewSet",
    "records.FollowerViewSet",
    "records.TagViewSet",
    "records.TaggedItemViewSet",
    "roles.RoleViewSet",
    "sav.CategorieEquipementViewSet",
    "sav.CategorieTicketViewSet",
    "sav.CauseDefaillanceViewSet",
    "sav.CompatibilitePieceViewSet",
    "sav.EquipeMaintenanceViewSet",
    "sav.MaintenanceChecklistTemplateViewSet",
    "sav.RemedeDefaillanceViewSet",
    "sav.ReponseTypeViewSet",
    "sav.SavSlaSettingsViewSet",
    "sav.WorksheetMaintenanceModeleViewSet",
    "stock.AccordRFAFournisseurViewSet",
    "stock.AchatsParametresViewSet",
    "stock.AlerteRappelViewSet",
    "stock.BlocageQualiteViewSet",
    "stock.BudgetDepartementViewSet",
    "stock.CatalogueAchatViewSet",
    "stock.CompatibiliteHazmatCasierViewSet",
    "stock.ConditionnementProduitViewSet",
    "stock.DepotConsignationViewSet",
    "stock.DocumentFournisseurViewSet",
    "stock.DossierOnboardingFournisseurViewSet",
    "stock.EmplacementStockViewSet",
    "stock.EngagementBudgetViewSet",
    "stock.ExpeditionTransporteurViewSet",
    "stock.IncidentQualiteFournisseurViewSet",
    "stock.InventaireAnnuelViewSet",
    "stock.MarqueViewSet",
    "stock.ModeleBonCommandeFournisseurViewSet",
    "stock.MouvementRebutViewSet",
    "stock.NomenclatureCodeBarresViewSet",
    "stock.PlanChargementViewSet",
    "stock.PlanComptageTournantViewSet",
    "stock.PlanEchantillonnageViewSet",
    "stock.PortailTiersTokenViewSet",
    "stock.ProfilSaisonnierViewSet",
    "stock.QuaiViewSet",
    "stock.RegleCodeBarresViewSet",
    "stock.RendezVousTransporteurViewSet",
    "stock.RetourClientViewSet",
    "stock.RevalorisationStockViewSet",
    "stock.SeuilReapproCasierViewSet",
    "stock.TacheReapproInterneViewSet",
    "stock.ToleranceRapprochementCategorieViewSet",
    "stock.UniteLogistiqueViewSet",
    "stock.VaguePickingViewSet",
    "trash.CorbeilleViewSet",
    "uxviews.FavoriUtilisateurViewSet",
    "uxviews.SavedViewViewSet",
    "ventes.AsBuiltPackViewSet",
    "ventes.AttestationConformiteViewSet",
    "ventes.AttestationREViewSet",
    "ventes.CommissioningTestViewSet",
    "ventes.DevisPresetViewSet",
    "ventes.DevisViewSet",
    "ventes.DossierChecklistItemViewSet",
    "ventes.DossierExchangeViewSet",
    "ventes.IVCurveCaptureViewSet",
    "ventes.LigneDevisViewSet",
    "ventes.LigneFactureViewSet",
    "ventes.ListePrixViewSet",
    "ventes.MandatPaiementViewSet",
    "ventes.PlanCommissionViewSet",
    "ventes.Regularisation8221ViewSet",
    "ventes.RegulatoryDossierViewSet",
    "ventes.RemiseEncaissementViewSet",
    "ventes.RoofLayoutViewSet",
    "ventes.SubventionDossierViewSet",
    "ventes.TestPerformanceReceptionViewSet",
    "visites.VisiteTerrainViewSet",
}


def _iter_urls_modules():
    for path in sorted(APPS_ROOT.glob("*/urls.py")):
        yield path.parent.name, path
    for app, path in EXTRA_URLS_MODULES.items():
        if path.exists():
            yield app, path


def _iter_view_files(app: str):
    app_dir = APPS_ROOT / app
    if not app_dir.is_dir():
        app_dir = DJANGO_CORE_ROOT / app
    if not app_dir.is_dir():
        return
    for path in sorted(app_dir.rglob("*.py")):
        if "migrations" in path.parts:
            continue
        name = path.name
        if name == "views.py" or path.parent.name == "views" \
                or name.endswith("_views.py"):
            yield path


def _registered_viewsets():
    """{(app, ViewSetClassName), ...} from every `<router>.register(prefix,
    ViewSetClass, ...)` call found in every urls.py."""
    found = set()
    for app, path in _iter_urls_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) \
                    or node.func.attr != "register":
                continue
            if len(node.args) < 2:
                continue
            viewset_arg = node.args[1]
            if isinstance(viewset_arg, ast.Name):
                found.add((app, viewset_arg.id))
    return found


def _resolve_attr_names(value_node):
    """Best-effort list of trailing names in a `[filters.SearchFilter, ...]`
    list literal, e.g. ['SearchFilter', 'OrderingFilter']."""
    names = []
    if not isinstance(value_node, (ast.List, ast.Tuple)):
        return names
    for elt in value_node.elts:
        if isinstance(elt, ast.Attribute):
            names.append(elt.attr)
        elif isinstance(elt, ast.Name):
            names.append(elt.id)
    return names


def _find_class_ordering_config(app: str, class_name: str):
    """Returns (has_own_filter_backends, ordering_active, ordering_fields)
    for the FIRST ClassDef named `class_name` found among the app's view
    files. Returns None if not found (e.g. viewset defined via a factory or
    imported from a foundation app — advisory scan, not exhaustive)."""
    for path in _iter_view_files(app):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != class_name:
                continue
            has_filter_backends = False
            ordering_active = False
            ordering_fields = None
            for stmt in node.body:
                if not isinstance(stmt, ast.Assign):
                    continue
                targets = [t.id for t in stmt.targets
                           if isinstance(t, ast.Name)]
                if "filter_backends" in targets:
                    has_filter_backends = True
                    backend_names = _resolve_attr_names(stmt.value)
                    ordering_active = "OrderingFilter" in backend_names
                if "ordering_fields" in targets:
                    if isinstance(stmt.value, ast.Constant):
                        ordering_fields = stmt.value.value
                    elif isinstance(stmt.value, (ast.List, ast.Tuple)):
                        ordering_fields = [
                            e.value for e in stmt.value.elts
                            if isinstance(e, ast.Constant)
                        ]
            if not has_filter_backends:
                # No own filter_backends -> inherits DEFAULT_FILTER_BACKENDS
                # (YAPIC2), which includes OrderingFilter.
                ordering_active = True
            return has_filter_backends, ordering_active, ordering_fields
    return None


def scan_noncompliant_viewsets():
    """Returns a sorted list of 'app.ViewSetClassName' for every registered
    viewset with tri actif but no explicit (non-'__all__') ordering_fields."""
    violations = []
    for app, class_name in _registered_viewsets():
        result = _find_class_ordering_config(app, class_name)
        if result is None:
            continue
        _has_own, ordering_active, ordering_fields = result
        if not ordering_active:
            continue
        if ordering_fields is None or ordering_fields == "__all__":
            violations.append(f"{app}.{class_name}")
    return sorted(violations)


class OrderingWhitelistRatchetTests(SimpleTestCase):

    def setUp(self):
        self.violations = set(scan_noncompliant_viewsets())

    def test_no_new_viewset_exceeds_the_exempt_baseline(self):
        new_violations = self.violations - ORDERING_WHITELIST_EXEMPT
        self.assertEqual(
            new_violations, set(),
            "NOUVEAU(X) viewset(s) avec OrderingFilter actif sans "
            "ordering_fields explicite (voir YAPIC2) :\n  "
            + "\n  ".join(sorted(new_violations)))

    def test_the_4_stock_views_fixed_by_yapic2_are_not_stale_exemptions(self):
        """Les 4 vues stock corrigées par CETTE tâche ne doivent jamais
        réapparaître dans le baseline d'exemption (sinon le ratchet mentirait
        sur l'état réel)."""
        fixed = {
            "stock.CategorieViewSet", "stock.FournisseurViewSet",
            "stock.KitProduitViewSet", "stock.FicheTechniqueViewSet",
        }
        self.assertFalse(
            fixed & ORDERING_WHITELIST_EXEMPT,
            "Une vue stock corrigée par YAPIC2 est encore dans "
            "ORDERING_WHITELIST_EXEMPT — retirez-la, le baseline ne fait "
            "que DÉCROÎTRE.")
        self.assertFalse(
            fixed & self.violations,
            "Une vue stock censée être corrigée par YAPIC2 réapparaît "
            "comme non-conforme — vérifiez ordering_fields.")
