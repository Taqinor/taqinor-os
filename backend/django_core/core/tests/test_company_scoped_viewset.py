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
