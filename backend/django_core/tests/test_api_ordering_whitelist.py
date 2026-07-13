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
# "app.ViewSetClassName" — generated 2026-07-12 by running this exact scan.
# The 4 previously-flagged stock views (categorie/fournisseur/kit/
# fiche_technique) are FIXED (ordering_fields now set) and therefore
# deliberately ABSENT here. Every OTHER entry relies on the new
# DEFAULT_FILTER_BACKENDS (YAPIC2) and had zero tri/recherche before this
# task — fixing all of them is out of this task's declared scope
# (apps/stock/views/*.py only); tightening this baseline (adding
# ordering_fields, dropping the entry here) is future work.
ORDERING_WHITELIST_EXEMPT: set[str] = {
    "authentication.CompanyViewSet",
    "authentication.UserViewSet",
    "chat.CannedResponseViewSet",
    "chat.ConversationViewSet",
    "chat.MessageViewSet",
    "chat.RetentionPolicyViewSet",
    "chat.ScheduledMessageViewSet",
    "chat.UserChatStatusViewSet",
    "compta.AbonnementListeViewSet",
    "compta.BalanceOuvertureViewSet",
    "compta.BilletEvenementViewSet",
    "compta.CommunicationEvenementViewSet",
    "compta.ComparateurCashFinancementViewSet",
    "compta.ComparateurDevisViewSet",
    "compta.CompensationViewSet",
    "compta.DomaineEnvoiViewSet",
    "compta.EntiteConsolidationViewSet",
    "compta.EtapeSequenceViewSet",
    "compta.EtatsComptablesViewSet",
    "compta.LettrageViewSet",
    "compta.PilotageViewSet",
    "compta.PlanComptableViewSet",
    "compta.ProvisionsPeriodeViewSet",
    "compta.QuestionEvenementViewSet",
    "compta.SequenceRelanceViewSet",
    "compta.SessionGuidedSellingViewSet",
    "compta.TypeEvenementViewSet",
    "contrats.ParametresLocationViewSet",
    "crm.CanalViewSet",
    "crm.EquipeCommercialeViewSet",
    "crm.LeadTagViewSet",
    "crm.MotifPerteViewSet",
    "crm.ObjectifCommercialViewSet",
    "crm.ParrainageViewSet",
    "crm.PlanActiviteViewSet",
    "crm.SiteProfileViewSet",
    "crm.WebsiteLeadPayloadViewSet",
    "customfields.CustomFieldDefViewSet",
    "customfields.CustomObjectDefViewSet",
    "ged.DocumentLienViewSet",
    "ged.DocumentTagAssignmentViewSet",
    "ged.QuotaStockageViewSet",
    "gestion_projet.ChronoActifViewSet",
    "gestion_projet.ReglageTempsViewSet",
    "identity.IpAllowRuleViewSet",
    "identity.NetworkPolicyViewSet",
    "installations.AppelCommandeViewSet",
    "installations.ApprobationBCFViewSet",
    "installations.AstreinteViewSet",
    "installations.AttestationSousTraitantViewSet",
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
    "installations.DocumentProjetViewSet",
    "installations.DossierImportViewSet",
    "installations.EquipeViewSet",
    "installations.EtapeAssemblageViewSet",
    "installations.EvaluationSousTraitantViewSet",
    "installations.FactureSousTraitantViewSet",
    "installations.FicheInterventionChampViewSet",
    "installations.FicheInterventionTemplateViewSet",
    "installations.FraisImportViewSet",
    "installations.GeofenceAlertViewSet",
    "installations.GpsConsentRecordViewSet",
    "installations.IndisponibiliteRessourceViewSet",
    "installations.JalonProjetViewSet",
    "installations.KitComposantViewSet",
    "installations.KitViewSet",
    "installations.LandedCostLigneViewSet",
    "installations.LivraisonLigneViewSet",
    "installations.LivraisonViewSet",
    "installations.LotPrelevementViewSet",
    "installations.MaterielConsigneViewSet",
    "installations.ModeleProjetViewSet",
    "installations.OrdreAssemblageLigneViewSet",
    "installations.OrdreAssemblageViewSet",
    "installations.OrdreDemontageLigneViewSet",
    "installations.OrdreDemontageViewSet",
    "installations.OrdreSousTraitanceViewSet",
    "installations.PaiementSousTraitantViewSet",
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
    "installations.RFQConsultationViewSet",
    "installations.RFQOffreViewSet",
    "installations.RFQViewSet",
    "installations.ReceptionNonFactureeViewSet",
    "installations.RecurrenceInterventionViewSet",
    "installations.RegleRangementViewSet",
    "installations.RegleReapproViewSet",
    "installations.RetenueGarantieSousTraitantViewSet",
    "installations.RetourLivraisonLigneViewSet",
    "installations.RetourLivraisonViewSet",
    "installations.RetourMaterielLigneViewSet",
    "installations.RetourMaterielViewSet",
    "installations.ReunionChantierViewSet",
    "installations.RevisionDocumentViewSet",
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
    "notifications.NotificationPreferenceViewSet",
    "notifications.NotificationRoutingRuleViewSet",
    "notifications.NotificationViewSet",
    "notifications.WhatsAppTemplateViewSet",
    "notifications.WorkingHoursConfigViewSet",
    "outillage.KitOutillageItemViewSet",
    "outillage.KitOutillageViewSet",
    "paie.LigneVirementViewSet",
    "pos.CommandeRetraitViewSet",
    "pos.ConfigMaterielPOSViewSet",
    "pos.SessionCaisseViewSet",
    "pos.VenteComptoirViewSet",
    "publicapi.ApiKeyViewSet",
    "publicapi.WebhookViewSet",
    "qhse.CalendrierQhseViewSet",
    "qhse.CoutNonQualiteViewSet",
    "qhse.Iso9001ReadinessViewSet",
    "qhse.LienSignalementPublicViewSet",
    "qhse.ParetoDefautsViewSet",
    "qhse.QhseChatterEntryViewSet",
    "qhse.SignalementPublicViewSet",
    "records.ActivityTypeViewSet",
    "records.ActivityViewSet",
    "records.AttachmentViewSet",
    "records.CommentViewSet",
    "records.FollowerViewSet",
    "records.TagViewSet",
    "records.TaggedItemViewSet",
    "rh.CockpitRhViewSet",
    "rh.EcheancesRhViewSet",
    "rh.KiosquePointageViewSet",
    "rh.PortailSelfServiceViewSet",
    "rh.RecrutementStatistiquesViewSet",
    "rh.ReglageRHViewSet",
    "rh.TableauBordHseViewSet",
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
    "stock.AchatsParametresViewSet",
    "stock.ConditionnementProduitViewSet",
    "stock.EmplacementStockViewSet",
    "stock.InventaireAnnuelViewSet",
    "stock.MarqueViewSet",
    "stock.ModeleBonCommandeFournisseurViewSet",
    "stock.NomenclatureCodeBarresViewSet",
    "stock.RegleCodeBarresViewSet",
    "stock.RevalorisationStockViewSet",
    "ventes.AsBuiltPackViewSet",
    "ventes.AttestationConformiteViewSet",
    "ventes.AttestationREViewSet",
    "ventes.CommissioningTestViewSet",
    "ventes.DevisPresetViewSet",
    "ventes.DevisViewSet",
    "ventes.DossierChecklistItemViewSet",
    "ventes.DossierExchangeViewSet",
    "ventes.FicheTechniqueViewSet",
    "ventes.IVCurveCaptureViewSet",
    "ventes.LigneDevisViewSet",
    "ventes.LigneFactureViewSet",
    "ventes.ListePrixViewSet",
    "ventes.MandatPaiementViewSet",
    "ventes.Regularisation8221ViewSet",
    "ventes.RegulatoryDossierViewSet",
    "ventes.RemiseEncaissementViewSet",
    "ventes.RoofLayoutViewSet",
    "ventes.SubventionDossierViewSet",
    "ventes.TestPerformanceReceptionViewSet",
    "voip.AppelViewSet",
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
