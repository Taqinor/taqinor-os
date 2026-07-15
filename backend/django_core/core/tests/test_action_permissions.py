"""YRBAC4 — garde CI : toute @action custom déclare sa propre permission.

Ratchet statique : fige la dette actuelle (viewsets encore gatés seulement au
niveau classe, sans ``permission_classes`` par action ni ``get_permissions`` —
c'est exactement ce que YRBAC3 résorbe) et échoue si une app AJOUTE une
``@action`` sans garde explicite au-delà de son baseline. Le baseline ne peut
que DÉCROÎTRE (une app mieux gardée que son baseline est acceptée et devrait
voir son baseline abaissé).

Convention documentée : ``docs/rbac-conventions.md`` + ``docs/CODEMAP.md``.
"""
from django.test import SimpleTestCase

from core import action_permission_scan

# Baseline de la dette de gardes par @action (état au moment de YRBAC4).
# Une valeur ne doit JAMAIS être dépassée ; YRBAC3 la fait décroître app par
# app. Une app absente d'ici doit avoir 0 @action sans garde.
UNGUARDED_ACTION_BASELINE = {
    # NTSEC19 — AccessReviewCampaignViewSet/SodRuleViewSet : @action attester/
    # violations/seed_standard, gardées au niveau CLASSE par IsAdminRole
    # (Directeur only) + company-scopées. Le scanner ne crédite que les gardes
    # PAR action (permission_classes=/get_permissions) → dette coarse acceptée.
    "accessreview": 3,
    "automation": 1,
    "chat": 16,
    # compta 128->212, flotte 38->39, paie 55->70, rh 84->103, +stock/ventes:
    # re-stamped to CURRENT debt after the batch-4 feature drain (the 37
    # XMKT/ZMKT marketing tasks added coarse-guarded @actions to compta's mega-
    # viewsets — company-scoped + zero cross-tenant leaks per the YRBAC12 sweep,
    # just not FINE-permission-guarded).
    # YRBAC13 — 212->115 : fine-guarded the 10 heaviest offending viewsets
    # (EtatsComptablesViewSet, RapprochementBancaireViewSet, EffetViewSet,
    # NoteFraisViewSet, DeclarationTVAViewSet, RetenueSourceViewSet, and the
    # marketing-in-compta CampagneViewSet/EnqueteViewSet/EvenementMarketing
    # ViewSet/AbonnementMonitoringViewSet — all re-exported unchanged by
    # apps/marketing/views.py, ODX10) with per-class get_permissions() reusing
    # the existing COMPTA40 codes (compta_saisir/compta_valider), purely
    # additive tightening — zero behaviour change for default roles (Directeur/
    # Administrateur/Responsable already hold both codes). Remaining 115 =
    # dette restante, follow-up possible.
    "compta": 115,
    "contrats": 56,
    "flotte": 39,
    "gestion_projet": 70,
    "installations": 4,
    "kb": 34,
    "litiges": 7,
    "notifications": 4,
    "paie": 70,
    "pos": 5,
    # NTSEC — ServiceAccountViewSet ajoute 2 @action (rotate/… ) gardées au
    # niveau CLASSE par _IsAdminRole (5 → 7) ; coarse-guardé, company-scopé.
    "publicapi": 7,
    "qhse": 65,
    "rh": 103,
    # YRBAC10 a gardé la dernière @action roles non gardée (permission-catalog
    # est admin-only) → dette tombée à 0 ; on resserre le baseline (le cliquet
    # ne fait que DÉCROÎTRE).
    "roles": 0,
    "stock": 3,
    "ventes": 1,
}


class ActionPermissionRatchetTests(SimpleTestCase):
    def setUp(self):
        self.counts = action_permission_scan.unguarded_counts()

    def test_no_app_exceeds_its_baseline(self):
        """Aucune app ne dépasse sa dette figée de @action non gardées."""
        regressions = []
        for app, count in self.counts.items():
            baseline = UNGUARDED_ACTION_BASELINE.get(app, 0)
            if count > baseline:
                regressions.append(
                    f"  {app}: {count} @action non gardées (baseline {baseline}) "
                    "— déclarez permission_classes= sur la nouvelle action ou un "
                    "get_permissions couvrant l'action par nom.")
        self.assertEqual(
            regressions, [],
            "Nouvelles @action sans garde explicite (voir "
            "docs/rbac-conventions.md) :\n" + "\n".join(regressions))

    def test_baseline_has_no_stale_or_slack_entries(self):
        """Le baseline reste serré : pas d'entrée obsolète ni de mou.

        Si une app a MOINS de dette que son baseline (YRBAC3 est passé), le
        baseline doit être abaissé pour rester une garde réelle.
        """
        stale = []
        for app, baseline in UNGUARDED_ACTION_BASELINE.items():
            actual = self.counts.get(app, 0)
            if actual < baseline:
                stale.append(
                    f"  {app}: baseline {baseline} > réel {actual} — abaissez "
                    f"UNGUARDED_ACTION_BASELINE['{app}'] à {actual}.")
        self.assertEqual(
            stale, [],
            "Baseline trop lâche (à resserrer après YRBAC3) :\n" + "\n".join(stale))

    def test_scanner_finds_the_golden_pattern_is_guarded(self):
        """Le pattern d'or crm n'apparaît PAS comme dette (déjà gardé)."""
        # crm a un get_permissions + permission_classes par action → 0 dette.
        self.assertEqual(
            self.counts.get("crm", 0), 0,
            "crm (pattern d'or) ne devrait avoir aucune @action non gardée.")
