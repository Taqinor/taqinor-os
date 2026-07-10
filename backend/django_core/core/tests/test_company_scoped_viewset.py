"""ARC2 — ``CompanyScopedModelViewSet`` : base transverse unique.

Prouve (a) que la base porte bien ``TenantMixin`` dans son MRO (donc que tout
viewset qui l'adopte est SCOPÉ société) et (b) que le sweep d'isolation
générique (YRBAC12, ``core.tenant_isolation_scan.discover_tenant_viewsets``)
DÉTECTE AUTOMATIQUEMENT chaque pilote converti — c'est le branchement du test
générique demandé par ARC2 : aucun pilote n'a besoin d'un enregistrement
manuel, la découverte le prend en charge dès qu'il hérite de la base.
"""
from django.test import SimpleTestCase

from core.mixins import TenantMixin
from core.permissions import ScopedPermission
from core.tenant_isolation_scan import discover_tenant_viewsets
from core.viewsets import CompanyScopedModelViewSet


class CompanyScopedModelViewSetBaseTests(SimpleTestCase):
    def test_base_carries_tenant_mixin_in_mro(self):
        """La base compose TenantMixin — condition de la détection YRBAC12
        (``base.__name__ == "TenantMixin"``) et de l'isolation société."""
        self.assertTrue(
            any(b.__name__ == "TenantMixin"
                for b in CompanyScopedModelViewSet.__mro__),
            "CompanyScopedModelViewSet doit hériter de TenantMixin.")
        self.assertTrue(issubclass(CompanyScopedModelViewSet, TenantMixin))

    def test_named_extension_points_are_neutral(self):
        """YAPIC1/YAPIC2 : la base ne pose NI pagination NI filter_backends
        propres — défauts DRF/projet inchangés (comportement byte-identique)."""
        # Aucune surcharge de classe ⇒ hérite du défaut ModelViewSet (None /
        # réglage projet). On vérifie qu'aucune valeur n'a été figée sur la base
        # elle-même (sinon elle changerait le comportement de tous les pilotes).
        self.assertNotIn("pagination_class",
                         CompanyScopedModelViewSet.__dict__)
        self.assertNotIn("filter_backends",
                         CompanyScopedModelViewSet.__dict__)


class PilotsAutoDiscoveredBySweepTests(SimpleTestCase):
    """Les 3 pilotes ARC2 sont découverts par le sweep générique YRBAC12 sans
    branchement manuel — donc couverts par
    ``core.tests.test_tenant_isolation_sweep`` automatiquement."""

    PILOTS = {
        "ClientViewSet",           # apps/crm
        "TransporteurViewSet",     # apps/installations
        "CauseDefaillanceViewSet",  # apps/sav
    }

    def test_three_pilots_discovered(self):
        discovered = {e.view_class.__name__ for e in discover_tenant_viewsets()}
        missing = self.PILOTS - discovered
        self.assertFalse(
            missing,
            f"Pilotes ARC2 non détectés par le sweep YRBAC12 : {missing}. "
            "Ils doivent hériter de CompanyScopedModelViewSet (TenantMixin).")

    def test_pilots_subclass_the_base(self):
        by_name = {
            e.view_class.__name__: e.view_class
            for e in discover_tenant_viewsets()
        }
        for name in self.PILOTS:
            self.assertIn(name, by_name)
            self.assertTrue(
                issubclass(by_name[name], CompanyScopedModelViewSet),
                f"{name} doit hériter de CompanyScopedModelViewSet.")


class DefaultScopedPermissionARC55Tests(SimpleTestCase):
    """ARC55 — la base pose ``ScopedPermission`` en défaut ET les 3 pilotes
    conservent leur ``get_permissions`` propre, donc leur matrice 401/403 est
    INCHANGÉE (le défaut est shadowé). Les tests d'isolation par pilote
    prouvent en plus les codes 401/403/404 réels côté HTTP."""

    def test_base_default_permission_is_scoped(self):
        self.assertEqual(
            CompanyScopedModelViewSet.permission_classes, [ScopedPermission],
            "La base doit poser ScopedPermission comme permission par défaut.")

    def test_default_scoped_permission_has_no_specific_codes(self):
        """Sans read_permission/write_permission, ScopedPermission = « authentifié
        suffit » des deux côtés → équivalent strict du défaut IsAuthenticated."""
        self.assertIsNone(
            getattr(CompanyScopedModelViewSet, "read_permission", None))
        self.assertIsNone(
            getattr(CompanyScopedModelViewSet, "write_permission", None))

    def test_pilots_keep_own_get_permissions(self):
        """Chaque pilote surcharge get_permissions : DRF ne consulte donc jamais
        le permission_classes de la base → 401/403 byte-identiques."""
        from apps.crm.views import ClientViewSet
        from apps.installations.views.transporteur import TransporteurViewSet
        from apps.sav.views import CauseDefaillanceViewSet
        for vs in (ClientViewSet, TransporteurViewSet, CauseDefaillanceViewSet):
            self.assertIn(
                "get_permissions", vs.__dict__,
                f"{vs.__name__} doit conserver son get_permissions propre "
                "(matrice 401/403 inchangée).")
