"""YRBAC1 — test-inventaire des permissions d'endpoint.

Parcourt l'URLconf racine, résout les ``permission_classes`` de chaque vue DRF,
et :

* ÉCHOUE si un endpoint résout à ``AllowAny`` seul hors allowlist publique
  documentée (tout NOUVEL ``AllowAny`` non listé casse le build) ;
* régénère l'artefact ``docs/rbac-endpoint-inventory.md`` (chemin → permissions)
  et vérifie qu'il n'a pas dérivé (le fichier committé doit refléter le code) ;
* vérifie que l'inventaire couvre une large part de la surface (non trivial).

Le fichier peut être régénéré en posant ``REGEN_RBAC_INVENTORY=1`` avant de
lancer la suite (utile après ajout/retrait d'endpoints).
"""
import os
from pathlib import Path

from django.test import SimpleTestCase

from core import rbac_inventory

INVENTORY_FILE = (
    Path(__file__).resolve().parents[3] / "docs" / "rbac-endpoint-inventory.md"
)


class EndpointPermissionInventoryTests(SimpleTestCase):
    def setUp(self):
        self.inventory = rbac_inventory.build_inventory()

    def test_inventory_is_non_trivial(self):
        """L'inventaire recense une large surface d'endpoints DRF."""
        self.assertGreaterEqual(
            len(self.inventory), 50,
            "L'inventaire des endpoints est anormalement petit "
            f"({len(self.inventory)}) — le parcours d'URLconf a-t-il régressé ?",
        )

    def test_no_unallowlisted_allow_any(self):
        """Aucun endpoint AllowAny hors allowlist publique documentée."""
        offenders = rbac_inventory.offending_allow_any(self.inventory)
        detail = "\n".join(f"  {e.pattern} ({e.view_name})" for e in offenders)
        self.assertEqual(
            offenders, [],
            "Endpoints résolus à AllowAny seul HORS allowlist "
            "(ajoutez la garde métier attendue, ou le préfixe à "
            "core.rbac_inventory.PUBLIC_ALLOWLIST_PREFIXES avec justification) :\n"
            f"{detail}",
        )

    def test_inventory_artifact_is_in_sync(self):
        """docs/rbac-endpoint-inventory.md reflète l'état courant du code."""
        rendered = rbac_inventory.render_inventory_markdown(self.inventory)
        if os.environ.get("REGEN_RBAC_INVENTORY") == "1" or not INVENTORY_FILE.exists():
            INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            INVENTORY_FILE.write_text(rendered, encoding="utf-8")
        committed = INVENTORY_FILE.read_text(encoding="utf-8")
        self.assertEqual(
            committed.strip(), rendered.strip(),
            "L'inventaire committé a dérivé du code. Régénérez-le avec "
            "REGEN_RBAC_INVENTORY=1 python manage.py test "
            "core.tests.test_endpoint_permission_inventory.",
        )

    def test_new_allow_any_would_fail(self):
        """Un endpoint AllowAny non-allowlisté serait détecté comme fautif."""
        rogue = rbac_inventory.EndpointPermissions(
            pattern="api/django/rogue/secret/",
            view_name="RogueView",
            permission_classes=("AllowAny",),
        )
        offenders = rbac_inventory.offending_allow_any([rogue])
        self.assertIn(rogue, offenders)

    def test_allowlisted_public_prefix_is_permitted(self):
        """Un AllowAny sous un préfixe public allowlisté ne fait pas échouer."""
        legit = rbac_inventory.EndpointPermissions(
            pattern="api/django/public/devis/abc/proposal/",
            view_name="ProposalView",
            permission_classes=("AllowAny",),
        )
        offenders = rbac_inventory.offending_allow_any([legit])
        self.assertEqual(offenders, [])
