"""Tests AUD834 — scripts/check_viewset_model_scope.py.

Stdlib pur (unittest), aucune base de donnees, aucun Django. Lancer :
    python -m unittest scripts.tests.test_check_viewset_model_scope -v

La garde apparie la BASE d'un viewset au MODELE qu'il sert. Les tests qui
comptent le plus sont ceux qui l'empechent de crier au loup : un scoping ecrit
dans un MIXIN local (patron `_PlaybookEnfantViewSetMixin` de crm), un modele
introuvable, une base de modele venue d'ailleurs — trois silences deliberes.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_tenant_isolation as cti  # noqa: E402
import check_viewset_model_scope as cvms  # noqa: E402


def ecrire(base: Path, chemin: str, texte: str) -> Path:
    cible = base / chemin
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(texte, encoding="utf-8")
    return cible


# Le modele enfant du patron territoires : une FK obligatoire vers son parent,
# AUCUN champ `company`. C'est cette forme meme qui fait sauter le balayage
# YRBAC12 (`build_minimal_instance` leve `SkipModel` sur une FK obligatoire).
MODELE_ENFANT = (
    "class Territoire(models.Model):\n"
    "    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)\n"
    "\n\n"
    "class TerritoireRegle(models.Model):\n"
    "    territoire = models.ForeignKey(Territoire, on_delete=models.CASCADE)\n"
    "    priorite = models.IntegerField(default=0)\n"
)


class PatronCasseTests(unittest.TestCase):
    def _analyser(self, modeles: str, vues: str):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ecrire(base, "apps/territoires/models.py", modeles)
            ecrire(base, "apps/territoires/views.py", vues)
            return cvms.analyser(base)

    def test_sans_get_queryset_le_patron_territoires_est_detecte(self):
        constats, _ = self._analyser(MODELE_ENFANT, (
            "class TerritoireRegleViewSet(CompanyScopedModelViewSet):\n"
            "    queryset = TerritoireRegle.objects.select_related('territoire')\n"
            "    serializer_class = TerritoireRegleSerializer\n"))
        self.assertEqual(len(constats), 1, constats)
        cle, modele, raison = constats[0]
        self.assertTrue(cle.endswith("::TerritoireRegleViewSet"), cle)
        self.assertEqual(modele, "TerritoireRegle")
        self.assertIn("ne definit pas get_queryset", raison)

    def test_un_get_queryset_qui_appelle_super_est_detecte(self):
        constats, _ = self._analyser(MODELE_ENFANT, (
            "class TerritoireRegleViewSet(TenantMixin, viewsets.ModelViewSet):\n"
            "    queryset = TerritoireRegle.objects.all()\n"
            "    def get_queryset(self):\n"
            "        return super().get_queryset().filter(priorite__gt=0)\n"))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("appelle super()", constats[0][2])

    def test_le_modele_sert_via_l_attribut_model(self):
        constats, _ = self._analyser(MODELE_ENFANT, (
            "class TerritoireRegleViewSet(CompanyScopedModelViewSet):\n"
            "    model = TerritoireRegle\n"))
        self.assertEqual(len(constats), 1, constats)


class SilencesDeliberesTests(unittest.TestCase):
    """La garde ne vaut RIEN si elle crie au loup : cinq silences assumes."""

    def _constats(self, modeles: str, vues: str):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ecrire(base, "apps/x/models.py", modeles)
            ecrire(base, "apps/x/views.py", vues)
            return cvms.analyser(base)[0]

    def test_le_patron_de_sortie_aud814_est_vert(self):
        # get_queryset qui NE PASSE PAS par super() et scope via le parent.
        self.assertEqual(self._constats(MODELE_ENFANT, (
            "class TerritoireRegleViewSet(CompanyScopedModelViewSet):\n"
            "    queryset = TerritoireRegle.objects.all()\n"
            "    def get_queryset(self):\n"
            "        qs = viewsets.ModelViewSet.get_queryset(self)\n"
            "        return qs.filter(territoire__company=self.request.user.company)\n")),
            [])

    def test_un_mixin_local_qui_scope_est_vert(self):
        # Patron reel `_PlaybookEnfantViewSetMixin` (crm) : le scoping vit dans
        # le mixin, la classe finale ne redefinit rien.
        self.assertEqual(self._constats(MODELE_ENFANT, (
            "class _EnfantMixin:\n"
            "    company_path = 'territoire__company_id'\n"
            "    def get_queryset(self):\n"
            "        qs = self.base_queryset()\n"
            "        return qs.filter(**{self.company_path: self.request.user.company_id})\n"
            "\n\n"
            "class TerritoireRegleViewSet(_EnfantMixin, CompanyScopedModelViewSet):\n"
            "    queryset = TerritoireRegle.objects.all()\n")),
            [])

    def test_un_modele_porteur_de_company_est_vert(self):
        self.assertEqual(self._constats(
            "class Territoire(models.Model):\n"
            "    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)\n",
            "class TerritoireViewSet(CompanyScopedModelViewSet):\n"
            "    queryset = Territoire.objects.all()\n"), [])

    def test_company_heritee_d_une_base_abstraite_est_verte(self):
        self.assertEqual(self._constats(
            "class SocieteMixin(models.Model):\n"
            "    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)\n"
            "\n\n"
            "class Truc(SocieteMixin):\n"
            "    libelle = models.CharField(max_length=10)\n",
            "class TrucViewSet(CompanyScopedModelViewSet):\n"
            "    queryset = Truc.objects.all()\n"), [])

    def test_un_modele_introuvable_ne_rougit_jamais(self):
        self.assertEqual(self._constats(
            "class Autre(models.Model):\n    pass\n",
            "class InconnuViewSet(CompanyScopedModelViewSet):\n"
            "    queryset = ModeleDUneAutreApp.objects.all()\n"), [])

    def test_une_base_de_modele_non_resolue_ne_rougit_jamais(self):
        # `company` peut venir de la base absente : le doute ne rougit pas.
        self.assertEqual(self._constats(
            "class Truc(BaseVenueDAilleurs):\n"
            "    libelle = models.CharField(max_length=10)\n",
            "class TrucViewSet(CompanyScopedModelViewSet):\n"
            "    queryset = Truc.objects.all()\n"), [])

    def test_une_vue_sans_base_tenant_est_hors_perimetre(self):
        self.assertEqual(self._constats(MODELE_ENFANT, (
            "class TerritoireRegleViewSet(viewsets.ModelViewSet):\n"
            "    queryset = TerritoireRegle.objects.all()\n")), [])


class AucuneGardeExistanteNeVoitCePatronTests(unittest.TestCase):
    """AUD834 — le constat lui-meme : rien ne couvrait cet appariement."""

    def test_check_tenant_isolation_declare_la_vue_conforme(self):
        # La garde d'isolation se satisfait de la base tenant : elle prouve
        # l'INTENTION de scoper, jamais sa faisabilite sur ce modele-la.
        with tempfile.TemporaryDirectory() as tmp:
            vues = ecrire(Path(tmp), "apps/territoires/views.py", (
                "class TerritoireRegleViewSet(CompanyScopedModelViewSet):\n"
                "    queryset = TerritoireRegle.objects.all()\n"
                "    serializer_class = TerritoireRegleSerializer\n"))
            _, constats = cti.check_view_file(vues)
        self.assertEqual(constats, [], "check_tenant_isolation voit le defaut ?")


class AllowlistTests(unittest.TestCase):
    def test_un_bypass_documente_neutralise_le_constat(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            allow = base / "allow.txt"
            allow.write_text("# raison : bypass explicite, scoping ailleurs\n"
                             "apps/x/views.py::TrucViewSet\n", encoding="utf-8")
            self.assertEqual(cvms.charger_allowlist(allow),
                             {"apps/x/views.py::TrucViewSet"})

    def test_une_allowlist_absente_vaut_ensemble_vide(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cvms.charger_allowlist(Path(tmp) / "absent.txt"),
                             set())


class DepotReelTests(unittest.TestCase):
    def test_l_arbre_courant_est_vert(self):
        constats, inventaire = cvms.analyser()
        allow = cvms.charger_allowlist()
        nouveaux = [c for c in constats if c[0] not in allow]
        self.assertEqual(nouveaux, [], nouveaux)
        # Une garde qui n'analyse plus rien serait verte pour rien (AUD832).
        self.assertGreater(len(inventaire), 100, len(inventaire))

    def test_l_entete_explique_pourquoi_le_sweep_yrbac12_saute_ces_modeles(self):
        entete = Path(cvms.__file__).read_text(encoding="utf-8")[:4000]
        self.assertIn("SkipModel", entete)
        self.assertIn("AUD814", entete)


if __name__ == "__main__":
    unittest.main()
