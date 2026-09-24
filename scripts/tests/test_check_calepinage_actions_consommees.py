"""Tests de scripts/check_calepinage_actions_consommees.py (CALX381).

Stdlib pur (unittest), aucune base de donnees :
    python -m unittest scripts.tests.test_check_calepinage_actions_consommees -v

Deux garanties verrouillees, comme pour check_services_appeles.py /
check_ecrans_atteignables.py : la DETECTION (une @action que rien n'appelle
doit rougir, en nommant fichier:ligne et url_path) et le SILENCE (une action
appelee par le client, une servie par window.open, et une couverte par le
passif ne doivent JAMAIS rougir). Un cas verifie en plus le piege DRF : le
url_path PAR DEFAUT garde le souligne du nom de methode.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_calepinage_actions_consommees as cac  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxDepot:
    """Depot Django + frontend jetable, branche sur les constantes du module
    (jamais le vrai depot). `BackendRoutes` (reutilisee telle quelle, CALX381
    : « jamais un second resolveur ») recoit `DJANGO_ROOT` directement par son
    constructeur — aucun besoin de monkeypatcher `check_api_contract`."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.django = self.racine / "backend" / "django_core"
        self.front = self.racine / "frontend" / "src"
        self.views = self.django / "apps" / "calepinage" / "views"
        self.baseline = self.racine / "scripts" / "calepinage_actions_allow.txt"

        write(self.django / "erp_agentique" / "urls.py", """
from django.urls import include, path
urlpatterns = [
    path('api/django/', include([path('calepinage/', include('apps.calepinage.urls'))])),
]
""")
        write(self.django / "apps" / "calepinage" / "urls.py", """
from rest_framework.routers import DefaultRouter
from .views import CalepinageViewSet

router = DefaultRouter()
router.register(r'calepinages', CalepinageViewSet, basename='calepinage')
urlpatterns = router.urls
""")
        # `CalepinageViewSet` vit dans un fichier FRERE de `views/__init__.py`
        # — exactement comme le vrai depot (`views/calepinages.py:158`) : la
        # resolution de paquet greffeur (`actions_of` -> `module.rsplit('.',
        # 1)[0]`) attend le dotted module d'un FICHIER a l'interieur du
        # paquet, jamais celui du paquet lui-meme (sinon `rsplit` retranche
        # un niveau de trop et aucune greffe ne se resout plus).
        write(self.views / "__init__.py", "")
        write(self.views / "calepinages.py", """
from rest_framework import viewsets

class CalepinageViewSet(viewsets.ModelViewSet):
    pass
""")

        self._sauvegarde = (
            cac.ROOT, cac.DJANGO_ROOT, cac.FRONTEND_SRC, cac.BASELINE_PATH,
        )
        cac.ROOT = self.racine
        cac.DJANGO_ROOT = self.django
        cac.FRONTEND_SRC = self.front
        cac.BASELINE_PATH = self.baseline

    def vue(self, nom_fichier: str, contenu: str) -> Path:
        return write(self.views / nom_fichier, contenu)

    def frontend(self, relatif: str, contenu: str) -> Path:
        return write(self.front / relatif, contenu)

    def close(self):
        (cac.ROOT, cac.DJANGO_ROOT, cac.FRONTEND_SRC,
         cac.BASELINE_PATH) = self._sauvegarde
        self.tmp.cleanup()


class BaseDepot(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)

    def constats(self):
        constats, _ = cac.analyse()
        return constats

    def par_fonction(self, nom):
        return [c for c in self.constats() if c["fonction"] == nom]


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BaseDepot):
    def test_action_greffee_sans_aucun_appelant(self):
        self.depot.vue("sorties.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='rapport-orphelin')
def rapport_orphelin(self, request):
    pass

CalepinageViewSet.rapport_orphelin = rapport_orphelin
""")
        constats = self.par_fonction("rapport_orphelin")
        self.assertEqual(len(constats), 1)
        self.assertEqual(constats[0]["url_path"], "rapport-orphelin")
        self.assertTrue(constats[0]["fichier"].endswith("sorties.py"))
        self.assertGreater(constats[0]["ligne"], 0)

    def test_main_rend_1_et_nomme_fichier_ligne_et_url_path(self):
        chemin = self.depot.vue("sorties.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='rapport-orphelin')
def rapport_orphelin(self, request):
    pass

CalepinageViewSet.rapport_orphelin = rapport_orphelin
""")
        import io
        import contextlib
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cac.main([])
        self.assertEqual(code, 1)
        texte = sortie.getvalue()
        self.assertIn(f"{chemin.relative_to(self.depot.racine).as_posix()}", texte)
        self.assertIn("rapport-orphelin", texte)


# ===========================================================================
# Silence
# ===========================================================================

class SilenceTests(BaseDepot):
    def test_action_appelee_par_le_client_ne_rougit_pas(self):
        self.depot.vue("consommation.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='rapport-consommation')
def rapport_consommation(self, request):
    pass

CalepinageViewSet.rapport_consommation = rapport_consommation
""")
        self.depot.frontend("api/calepinageApi.js", """
export const calepinages = {
  rapportConsommation: () => api.get('/calepinage/calepinages/rapport-consommation/'),
}
""")
        self.assertEqual(self.par_fonction("rapport_consommation"), [])

    def test_action_ouverte_par_window_open_ne_rougit_pas(self):
        self.depot.vue("export_pdf.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='export-pdf')
def export_pdf(self, request):
    pass

CalepinageViewSet.export_pdf = export_pdf
""")
        self.depot.frontend("features/calepinage/Bouton.jsx", """
export function ouvrir() {
  window.open('/api/django/calepinage/calepinages/export-pdf/')
}
""")
        self.assertEqual(self.par_fonction("export_pdf"), [])

    def test_action_ouverte_par_href_ne_rougit_pas(self):
        self.depot.vue("export_dxf.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='export-dxf')
def export_dxf(self, request):
    pass

CalepinageViewSet.export_dxf = export_dxf
""")
        self.depot.frontend("features/calepinage/Lien.jsx", """
export const Lien = () => <a href="/api/django/calepinage/calepinages/export-dxf/">DXF</a>
""")
        self.assertEqual(self.par_fonction("export_dxf"), [])

    def test_action_couverte_par_le_passif_ne_fait_pas_echouer_main(self):
        chemin = self.depot.vue("sorties.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='rapport-orphelin')
def rapport_orphelin(self, request):
    pass

CalepinageViewSet.rapport_orphelin = rapport_orphelin
""")
        # La ligne EXACTE vient du constat reel, jamais d'un decompte a la
        # main du texte ci-dessus (fragile au moindre octet ajoute).
        ligne = self.par_fonction("rapport_orphelin")[0]["ligne"]
        cle = f"{chemin.relative_to(self.depot.racine).as_posix()}:{ligne}"
        write(self.depot.baseline,
              cac.ENTETE_BASE + f"{cle}  rapport-orphelin  # dette historique de test\n")
        code = cac.main([])
        self.assertEqual(code, 0)

    def test_url_path_par_defaut_garde_le_souligne(self):
        # Piege DRF (meme regle que check_api_contract) : sans url_path
        # explicite, le chemin par defaut est le NOM DE LA METHODE TEL QUEL.
        self.depot.vue("interne.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False)
def rapport_interne(self, request):
    pass

CalepinageViewSet.rapport_interne = rapport_interne
""")
        self.depot.frontend("api/calepinageApi.js", """
export const calepinages = {
  rapportInterne: () => api.get('/calepinage/calepinages/rapport_interne/'),
}
""")
        constats = self.par_fonction("rapport_interne")
        self.assertEqual(constats, [])

    def test_url_path_par_defaut_souligne_reste_detecte_si_non_appele(self):
        self.depot.vue("interne.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False)
def rapport_interne(self, request):
    pass

CalepinageViewSet.rapport_interne = rapport_interne
""")
        constats = self.par_fonction("rapport_interne")
        self.assertEqual(len(constats), 1)
        self.assertEqual(constats[0]["url_path"], "rapport_interne")


# ===========================================================================
# Base de reference
# ===========================================================================

class BaselineTests(BaseDepot):
    def test_write_baseline_refuse_de_grandir_sans_lautorisation(self):
        self.depot.vue("sorties.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='rapport-orphelin')
def rapport_orphelin(self, request):
    pass

CalepinageViewSet.rapport_orphelin = rapport_orphelin
""")
        write(self.depot.baseline, cac.ENTETE_BASE)
        code = cac.main(["--write-baseline"])
        self.assertEqual(code, 1)

    def test_write_baseline_retire_une_dette_corrigee(self):
        chemin = self.depot.vue("sorties.py", """
from rest_framework.decorators import action
from . import CalepinageViewSet

@action(detail=False, url_path='rapport-consommation')
def rapport_consommation(self, request):
    pass

CalepinageViewSet.rapport_consommation = rapport_consommation
""")
        cle = f"{chemin.relative_to(self.depot.racine).as_posix()}:6"
        write(self.depot.baseline,
              cac.ENTETE_BASE + f"{cle}  rapport-consommation  # ancienne dette\n")
        self.depot.frontend("api/calepinageApi.js", """
export const calepinages = {
  rapportConsommation: () => api.get('/calepinage/calepinages/rapport-consommation/'),
}
""")
        code = cac.main(["--write-baseline"])
        self.assertEqual(code, 0)
        base = cac.charger_base(self.depot.baseline)
        self.assertNotIn(cle, base)


if __name__ == "__main__":
    unittest.main()
