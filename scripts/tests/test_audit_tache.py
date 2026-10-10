"""Tests de scripts/audit_tache.py — le generateur de clauses CALCULEES (AMET80-82).

Stdlib pur (unittest) : aucune base, aucun Django, aucun reseau, aucun docker.
Lancer :
    python -m unittest scripts.tests.test_audit_tache -v

PAR DEFAUT, TOUT tourne sur des DEPOTS JETABLES (git init dans un dossier
temporaire) dont les fichiers synthetiques reproduisent chaque forme du depot
reel (urls + router.register + @action -> ViewSet -> wrapper
`frontend/src/api/*.js` -> ecran, thunk Redux, route plus specifique, liste de
champs + setattr, tests a codes HTTP, plans SPL…). Aucune assertion ne depend
du code applicatif VIVANT : ce module tourne dans le job BLOQUANT stage-names
de chaque PR, et une PR qui reecrit DevisRow.jsx ou scinde crm/views.py ne
doit jamais rougir ici pour une raison etrangere.

GOLDENS REELS (opt-in) — `scripts/tests/golden/audit_tache/<CAS>.json` :
sorties GENEREES par l'outil sur l'arbre reel (ACRM26, ACHT22, AFAC47), cles
par SYMBOLE, jamais par numero de ligne, comparaison « rien ne disparait ».
`vérifie AMET` les rejoue :
    AUDIT_TACHE_REEL=1 python -m unittest scripts.tests.test_audit_tache
Une derive y est une INFORMATION (le code a bouge), pas un echec de l'outil.
Regenerer apres un changement voulu :
    AUDIT_TACHE_REEL=1 AUDIT_TACHE_GOLDEN=ecrire python -m unittest scripts.tests.test_audit_tache
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_tache as at  # noqa: E402

GOLDEN = ROOT / "scripts" / "tests" / "golden" / "audit_tache"
REEL = os.environ.get("AUDIT_TACHE_REEL") == "1"
ECRIRE = os.environ.get("AUDIT_TACHE_GOLDEN") == "ecrire"
RAISON_REEL = ("goldens sur le code applicatif VIVANT : AUDIT_TACHE_REEL=1 pour les rejouer "
               "(vérifie AMET)")

DJ = "backend/django_core/apps"
FACTURE = f"{DJ}/ventes/views/facture.py::FactureViewSet.perform_update"
# Commandes rejouees par cas sur l'arbre REEL (opt-in). La sortie projetee EST le golden.
CAS = {
    "ACRM26": [
        ("appelants", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("lecteurs-front", "tranches_facturees"),
        ("ecrivains", "Lead.whatsapp"),
        ("ecrivains", "Lead.telephone_whatsapp"),
        ("assertions-existantes", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("listes-figees", f"{DJ}/crm/services.py"),
        ("jumeaux", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions"),
        ("jumeaux", f"{DJ}/crm/views.py::SiteProfileViewSet.get_permissions"),
        ("emplacement", f"{DJ}/crm/services.py::merge_leads"),
    ],
    "ACHT22": [
        ("appelants", f"{DJ}/installations/views/livraison.py::LivraisonViewSet.bon_livraison"),
        ("appelants", f"{DJ}/installations/livraison_pdf.py::bon_livraison_pdf"),
        ("assertions-existantes", f"{DJ}/installations/views/livraison.py::LivraisonViewSet.bon_livraison"),
        ("lecteurs-sample", "roof_layout_v2.schema.json"),
        ("test-canonique", f"{DJ}/installations/services.py::recreer_nomenclature_ordre_assemblage"),
    ],
    "AFAC47": [
        ("appelants", FACTURE),
        ("appelants", f"{DJ}/ventes/utils/echeancier.py::tranches_normalisees"),
        ("assertions-existantes", f"{DJ}/ventes/recouvrement.py::ParametrageRelanceClientViewSet.perform_update"),
        ("assertions-existantes", f"{FACTURE} --anciens Montant figé"),
        ("listes-figees", f"{DJ}/ventes/recouvrement.py"),
    ],
}


def executer(commande: str, argument: str) -> dict:
    """`argument` peut porter `--anciens <litteral>` (comme la CLI)."""
    cible, _, ancien = argument.partition(" --anciens ")
    options = {"anciens": [ancien]} if ancien else {}
    return at.COMMANDES[commande](cible, **options)


def comparer(test, attendu: dict, obtenu: dict, contexte: str):
    """Rien du golden ne disparait : listes incluses, compteurs >=."""
    for cle, valeur in attendu.items():
        recu = obtenu.get(cle)
        if isinstance(valeur, list):
            manquants = sorted(set(valeur) - set(recu or []))
            test.assertFalse(manquants, f"{contexte} [{cle}] : disparus {manquants}")
        elif isinstance(valeur, int) and not isinstance(valeur, bool):
            test.assertGreaterEqual(recu, valeur, f"{contexte} [{cle}]")
        else:
            test.assertEqual(recu, valeur, f"{contexte} [{cle}]")


@unittest.skipUnless(REEL, RAISON_REEL)
class GoldenTests(unittest.TestCase):
    def test_chaque_golden_est_retrouve(self):
        for cas, commandes in CAS.items():
            sorties = {f"{c} {a}": at.projection(c, executer(c, a)) for c, a in commandes}
            chemin = GOLDEN / f"{cas}.json"
            if ECRIRE:
                chemin.write_text(json.dumps({"cas": cas, "commandes": sorties}, ensure_ascii=False,
                                             indent=1, sort_keys=True) + "\n", encoding="utf-8")
            golden = json.loads(chemin.read_text(encoding="utf-8"))
            for libelle, attendu in golden["commandes"].items():
                with self.subTest(cas=cas, commande=libelle):
                    comparer(self, attendu, sorties[libelle], f"{cas} {libelle}")

    def test_goldens_sans_numero_de_ligne(self):
        for cas in CAS:
            texte = (GOLDEN / f"{cas}.json").read_text(encoding="utf-8")
            self.assertNotRegex(texte, r"\.(?:py|jsx?|mjs):\d", cas)


# ---------------------------------------------------------------------------
# Depots jetables
# ---------------------------------------------------------------------------

def _git(racine, *args):
    subprocess.run(["git", *args], cwd=racine, check=True, capture_output=True)


class DepotJetable:
    """git init + des fichiers synthetiques ; un dossier de cache isole."""

    def __init__(self, fichiers: dict):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        for rel, contenu in fichiers.items():
            chemin = self.racine / rel
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(contenu, encoding="utf-8")
        _git(self.racine, "init", "-q")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        self.cache = tempfile.TemporaryDirectory()

    def fermer(self):
        self.tmp.cleanup()
        self.cache.cleanup()


class DepotActif:
    """Fait du depot jetable LA racine des modules (ROOT lus a l'appel), puis restaure."""

    CIBLES = ((at, "ROOT"), (at, "CACHE_DIR"), (at.cac, "ROOT"), (at.cac, "FRONT_SRC"),
              (at.ctc, "ROOT"), (at.ctc, "FRONT_SRC"), (at.ctc, "_INDEX_NOMS"))

    def __init__(self, depot: DepotJetable):
        self.depot = depot
        self.sauvegarde = [(m, n, getattr(m, n)) for m, n in self.CIBLES]
        valeurs = {"ROOT": depot.racine, "CACHE_DIR": Path(depot.cache.name),
                   "FRONT_SRC": depot.racine / "frontend" / "src", "_INDEX_NOMS": None}
        for module, nom in self.CIBLES:
            setattr(module, nom, valeurs[nom])
        at._ETATS.clear()

    def restaurer(self):
        for module, nom, valeur in self.sauvegarde:
            setattr(module, nom, valeur)
        at._ETATS.clear()


def _viewset(nom: str, corps: str, docstring: str = "") -> str:
    doc = f'    """{docstring}"""\n\n' if docstring else ""
    return f"\n\nclass {nom}(viewsets.ModelViewSet):\n{doc}    def get_permissions(self):\n{corps}"


CORPS_ORIGINE = ("        if self.action in READ_ACTIONS:\n            return [IsAnyRole()]\n"
                 "        return [IsResponsableOrAdmin()]\n")
CORPS_ADMIN = ("        if self.action in READ_ACTIONS:\n            return [IsAnyRole()]\n"
               "        return [IsAdminRole()]\n")
ENTETE_VUES = ("from rest_framework import viewsets\nfrom rest_framework.decorators import action, api_view\n"
               "from core.permissions import READ_ACTIONS, IsAdminRole, IsAnyRole, IsResponsableOrAdmin\n")


def _fichiers_erp() -> dict:
    """Le depot synthetique : chaque forme du depot reel, en petit."""
    # 105 corps get_permissions identiques (R3_V3), repartis sur 3 fichiers, docstrings variees.
    vues_crm = ENTETE_VUES + _viewset("EquipeCommercialeViewSet", CORPS_ORIGINE) + "".join(
        _viewset(f"Referentiel{i:03d}ViewSet", CORPS_ORIGINE, "doc" if i % 2 else "") for i in range(1, 40))
    vues_crm += _viewset("CanalViewSet", CORPS_ADMIN)  # meme nom, autre corps
    vues_crm += "\n\n@api_view(['GET'])\ndef equipes_statistiques(request):\n    return None\n"
    vues_sav = ENTETE_VUES + "".join(_viewset(f"Sav{i:03d}ViewSet", CORPS_ORIGINE) for i in range(40, 80))
    vues_stock = ENTETE_VUES + "".join(_viewset(f"Stock{i:03d}ViewSet", CORPS_ORIGINE) for i in range(80, 105))
    remplissage = "".join(f"\n\ndef aide_{i:04d}(x):\n    return x + {i}\n" for i in range(520))
    return {
        # --- backend : montage d'URL statique (lu par check_api_contract.BackendRoutes) ---
        "backend/django_core/erp_agentique/urls.py": (
            "from django.urls import include, path\n\nurlpatterns = [\n"
            "    path('api/django/crm/', include('apps.crm.urls')),\n"
            "    path('api/django/ventes/', include('apps.ventes.urls')),\n"
            "    path('api/django/installations/', include('apps.installations.urls')),\n]\n"),
        f"{DJ}/crm/urls.py": (
            "from django.urls import include, path\nfrom rest_framework.routers import DefaultRouter\n"
            "from .views import EquipeCommercialeViewSet, equipes_statistiques\n\n"
            "router = DefaultRouter()\nrouter.register(r'equipes', EquipeCommercialeViewSet)\n\n"
            "urlpatterns = [\n    path('equipes/statistiques/', equipes_statistiques),\n"
            "    path('', include(router.urls)),\n]\n"),
        f"{DJ}/crm/views.py": vues_crm,
        f"{DJ}/sav/views.py": vues_sav,
        f"{DJ}/stock/views.py": vues_stock,
        f"{DJ}/ventes/urls.py": (
            "from django.urls import include, path\nfrom rest_framework.routers import DefaultRouter\n"
            "from .views import FactureViewSet\n\nrouter = DefaultRouter()\n"
            "router.register(r'factures', FactureViewSet)\n\nurlpatterns = [path('', include(router.urls))]\n"),
        f"{DJ}/ventes/views/__init__.py": "from .facture import FactureViewSet  # noqa\n",
        f"{DJ}/ventes/views/facture.py": (
            "from rest_framework import viewsets\nfrom rest_framework.decorators import action\n\n\n"
            "class FactureViewSet(viewsets.ModelViewSet):\n    def perform_update(self, serializer):\n"
            "        raise ValueError('Montant figé après émission')\n\n"
            "    @action(detail=True, methods=['post'])\n    def emettre(self, request, pk=None):\n"
            "        return None\n"),
        f"{DJ}/ventes/utils/echeancier.py": (
            "def tranches_normalisees(devis):\n    return []\n\n\n"
            "def schedule_for_devis(devis):\n    return tranches_normalisees(devis)\n"),
        f"{DJ}/ventes/quote_engine/builder.py": (
            "from apps.ventes.utils import echeancier\n\n\n"
            "def tranches_echeancier_en_montant(devis):\n    return echeancier.tranches_normalisees(devis)\n"),
        f"{DJ}/ventes/reexport.py": "from apps.ventes.utils.echeancier import tranches_normalisees  # noqa\n",
        "backend/django_core/erp_agentique/settings.py": (
            "CELERY_BEAT_SCHEDULE = {'t': {'task': 'apps.ventes.utils.echeancier.tranches_normalisees'}}\n"),
        f"{DJ}/ventes/tests/test_echeancier.py": (
            "from apps.ventes.utils.echeancier import tranches_normalisees\n\n\n"
            "class EcheancierTests:\n    def test_vide(self):\n        assert tranches_normalisees(None) == []\n"),
        # --- ecrivains d'un champ ---
        f"{DJ}/crm/models.py": (
            "from django.db import models\n\n\nclass Lead(models.Model):\n"
            "    telephone = models.CharField(max_length=50)\n    whatsapp = models.CharField(max_length=50)\n"),
        f"{DJ}/crm/services.py": (
            "from .models import Lead\n\nQUESTIONS = {}\nQUESTIONS['whatsapp'] = 'Votre WhatsApp ?'\n"
            "_MERGE_FILL_FIELDS = ['email', 'whatsapp']\n\n\n"
            "def _apply_meta_form_extras(lead):\n    lead.whatsapp = lead.telephone\n\n\n"
            "def merge_leads(survivant, doublon):\n    for field in _MERGE_FILL_FIELDS:\n"
            "        setattr(survivant, field, getattr(doublon, field))\n    return survivant\n\n\n"
            "def creer_lead_proprietaire(w):\n    return Lead(whatsapp=w)\n\n\n"
            "def lire(x):\n    return Lead.objects.filter(whatsapp=x)\n" + remplissage),
        # --- emplacement / test canonique ---
        f"{DJ}/installations/urls.py": "urlpatterns = []\n",
        f"{DJ}/installations/services.py": (
            "def recreer_nomenclature_ordre_assemblage(ordre, user=None):\n"
            '    """ACHT17 — re-fige la nomenclature."""\n    return ordre\n'),
        f"{DJ}/installations/views/kitting.py": (
            '"""Vues FG328 — pre-assemblage / kitting magasin."""\n'
            "from ..services import recreer_nomenclature_ordre_assemblage\n\n\n"
            "def modifier_ordre(ordre):\n    return recreer_nomenclature_ordre_assemblage(ordre)\n"),
        f"{DJ}/installations/tests_fg328_kitting.py": "class KittingTests:\n    def test_kit(self):\n        pass\n",
        f"{DJ}/installations/test_astk46_kitting_decimal.py": "class D:\n    def test_d(self):\n        pass\n",
        f"{DJ}/installations/tests_asec33_kitting_ids.py": "class I:\n    def test_i(self):\n        pass\n",
        # --- tests qui figent l'ancien comportement ---
        f"{DJ}/crm/tests_zsal3_equipe_crud.py": (
            "URL = '/api/django/crm/equipes/'\n\n\nclass TestEquipeCommercialeCRUD:\n"
            "    def setUp(self):\n        self.resp = make_user(role_legacy='admin')\n\n"
            "    def test_responsable_cree_une_equipe(self):\n"
            "        resp = self.api.post('/api/django/crm/equipes/', {'nom': 'Sud'})\n"
            "        self.assertEqual(resp.status_code, 201)\n\n"
            "    def test_commercial_peut_lire(self):\n        resp = self.api.get(URL)\n"
            "        self.assertEqual(resp.status_code, 200)\n\n"
            "    def test_cross_company_404(self):\n        resp = self.api.patch(f'{URL}{9}/', {})\n"
            "        self.assertEqual(resp.status_code, 404)\n\n"
            "    def test_statistiques_route_soeur(self):\n"
            "        r = self.api.get('/api/django/crm/equipes/statistiques/')\n"
            "        self.assertEqual(r.status_code, 200)\n"),
        f"{DJ}/facturation/tests/test_atot_montants_figes.py": (
            "class MontantsFigesTests:\n    def setUp(self):\n        self.u = make_user(role_legacy='responsable')\n\n"
            "    def test_patch_montant_emise_refuse(self):\n"
            "        r = self.api.patch(f'/api/django/ventes/factures/{self.f.id}/', {'montant_ht': 1})\n"
            "        self.assertEqual(r.status_code, 400)\n"
            "        self.assertIn('Montant figé', str(r.data))\n\n"
            "    def test_sans_rapport(self):\n        self.assertEqual(1, 1)\n"),
        f"{DJ}/ventes/tests/test_xfac_asec28_bc_mandat_fk.py": (
            "class Asec28Tests:\n    def test_relance_etranger_400(self):\n"
            "        r = self.api.patch(f'/api/django/ventes/factures/{self.f.id}/', {'client': 9})\n"
            "        self.assertEqual(r.status_code, 400)\n\n"
            "    def test_creation_post(self):\n        r = self.api.post('/api/django/ventes/factures/', {})\n"
            "        self.assertEqual(r.status_code, 201)\n"),
        # --- contract sample ---
        f"{DJ}/calepinage/contract_samples/roof_layout_v2.schema.json": "{}\n",
        f"{DJ}/calepinage/tests/test_roof_contrat.py": (
            '"""Contrat roof_layout_v2.schema.json (mention en docstring : pas un lecteur)."""\n'
            "SAMPLE = 'contract_samples/roof_layout_v2.schema.json'\n"),
        f"{DJ}/calepinage/notes.py": "# roof_layout_v2.schema.json cite en commentaire seulement\nX = 1\n",
        "frontend/src/features/calepinage/roof.test.js": (
            "import schema from '../../../../backend/django_core/apps/calepinage/contract_samples/"
            "roof_layout_v2.schema.json'\ntest('forme', () => expect(schema).toBeTruthy())\n"),
        "docs/contrats.md": "roof_layout_v2.schema.json est decrit ici.\n",
        # --- frontend : wrappers, thunk, ecrans ---
        "frontend/src/api/crmApi.js": (
            "import api from './axios'\n\nconst crmApi = {\n"
            "  getEquipesStatistiques: () => api.get('/crm/equipes/statistiques/'),\n"
            "  getEquipes: (params) => api.get('/crm/equipes/', { params }),\n"
            "  saveEquipe: (id, data) =>\n"
            "    id ? api.patch(`/crm/equipes/${id}/`, data) : api.post('/crm/equipes/', data),\n"
            "}\n\nexport default crmApi\n"),
        "frontend/src/api/ventesApi.js": (
            "import api from './axios'\n\nconst ventesApi = {\n"
            "  getFacture: (id) => api.get(`/ventes/factures/${id}/`),\n"
            "  updateFacture: (id, data) => api.put(`/ventes/factures/${id}/`, data),\n"
            "}\n\nexport default ventesApi\n"),
        "frontend/src/features/ventes/store/ventesSlice.js": (
            "import { createAsyncThunk } from '@reduxjs/toolkit'\nimport ventesApi from '../../../api/ventesApi'\n\n"
            "export const updateFacture = createAsyncThunk('ventes/updateFacture', async ({ id, data }) => {\n"
            "  const res = await ventesApi.updateFacture(id, data)\n  return res.data\n})\n"),
        "frontend/src/pages/ventes/FactureForm.jsx": (
            "import { useDispatch } from 'react-redux'\n"
            "import { updateFacture } from '../../features/ventes/store/ventesSlice'\n\n"
            "export default function FactureForm({ id, data }) {\n  const dispatch = useDispatch()\n"
            "  const enregistrer = () => dispatch(updateFacture({ id, data }))\n"
            "  return <button onClick={enregistrer}>OK</button>\n}\n"),
        "frontend/src/pages/parametres/EquipesCommercialesSection.jsx": (
            "import crmApi from '../../api/crmApi'\n\nexport default function EquipesCommercialesSection() {\n"
            "  crmApi.getEquipes()\n  return null\n}\n"),
        "frontend/src/pages/dashboard/MesEquipesCard.jsx": (
            "import crmApi from '../../api/crmApi'\n\nexport default function MesEquipesCard() {\n"
            "  crmApi.getEquipesStatistiques()\n  return null\n}\n"),
        "frontend/src/pages/ventes/devisList/DevisRow.jsx": (
            "// tranches_facturees : commentaire, pas une lecture\nexport default function DevisRow({ d }) {\n"
            "  const tout = d.solde && d.solde.tranches_facturees >= d.solde.tranches_total\n"
            "  return tout ? null : (d.solde?.tranches_facturees > 0 ? 'Générer facture' : 'Facturer')\n}\n"),
        "frontend/src/features/crm/workspace/DevisTab.jsx": (
            "export default function DevisTab({ solde }) {\n  return solde?.tranches_facturees ?? 0\n}\n"),
        "frontend/src/pages/ventes/devisList/DevisRow.test.jsx": "const d = { solde: { tranches_facturees: 1 } }\n",
        # --- plans : SPL qui deplace merge_leads (ouvert), une autre qui ne fait que le citer, une fermee ---
        "docs/plans/PLAN_AUDIT_TRANSVERSE.md": (
            "- [ ] SPL22 — **Déplacer la fusion de leads de `crm/services.py` vers `crm/leads_fusion.py` "
            "(move only)** : `crm/leads_fusion.py` ← 2 symboles : FUSION_NOTE, merge_leads ; "
            "Files: `backend/django_core/apps/crm/services.py` (ROUTINE)\n"
            "- [ ] SPL3 — **Déplacer les actions en masse de `crm/services.py` vers `crm/fiche_bulk.py` "
            "(move only)** : appelle merge_leads ; `crm/fiche_bulk.py` ← 1 symboles : bulk_x ; "
            "Files: `backend/django_core/apps/crm/services.py` (ROUTINE)\n"
            "- [x] SPL1 — **Déplacer merge_leads de `crm/services.py`** : fait.\n"),
        # --- listes figees : une garde qui declare son type, une qui ne le declare pas ---
        "scripts/check_get_or_create.py": (
            '"""Garde."""\nTYPE_DE_CLE = "par_symbole"\nREGISTRE = "docs/get-or-create-audit.md"\n'
            "# python scripts/check_get_or_create.py --write\n"),
        "docs/get-or-create-audit.md": "| `backend/django_core/apps/crm/services.py::merge_leads::Lead` |\n",
        "scripts/check_lignes.py": '"""Garde."""\nBASE = "lignes_allow.txt"\n# --write-baseline\n',
        "scripts/lignes_allow.txt": "backend/django_core/apps/crm/services.py:12\n",
    }


class _SurDepotErp(unittest.TestCase):
    """Un seul depot synthetique partage par les classes de forme (construit une fois)."""

    @classmethod
    def setUpClass(cls):
        cls.depot = DepotJetable(_fichiers_erp())
        cls.actif = DepotActif(cls.depot)
        cls.memo = {}

    @classmethod
    def tearDownClass(cls):
        cls.actif.restaurer()
        cls.depot.fermer()

    def sortie(self, commande: str, argument: str) -> dict:
        if (commande, argument) not in self.memo:
            self.memo[(commande, argument)] = executer(commande, argument)
        return self.memo[(commande, argument)]


class AppelantsTests(_SurDepotErp):
    def test_lecteurs_front_trouve_devisrow_et_devistab(self):
        # ATOT2 : « 0 écran » alors que DevisRow.jsx ET DevisTab.jsx lisent la cle.
        sortie = self.sortie("lecteurs-front", "tranches_facturees")
        fichiers = {e["fichier"]: e for e in sortie["lecteurs"]}
        devisrow = "frontend/src/pages/ventes/devisList/DevisRow.jsx"
        self.assertEqual(fichiers[devisrow]["lignes"], [3, 4])          # le commentaire (l. 1) n'est pas lu
        self.assertIn("frontend/src/features/crm/workspace/DevisTab.jsx", fichiers)
        self.assertTrue(fichiers["frontend/src/pages/ventes/devisList/DevisRow.test.jsx"]["test"])
        self.assertIn("lecteurs FRONT de `tranches_facturees` 2", sortie["texte"])
        self.assertIn("`DevisRow.jsx:3,4`", sortie["texte"])

    def test_thunk_redux_amene_facture_form(self):
        # ATOT9 : le PUT de FactureForm passe par le thunk `updateFacture`.
        sortie = self.sortie("appelants", FACTURE)
        self.assertEqual([r["route"] for r in sortie["routes"]], ["/api/django/ventes/factures/<id>/"])
        self.assertEqual([(w["nom"], w["verbe"]) for w in sortie["wrappers"]], [("updateFacture", "PUT")])
        form = "frontend/src/pages/ventes/FactureForm.jsx"
        self.assertEqual(sortie["ecrans"], [form])
        self.assertEqual(sortie["chemins"][form], "ventesSlice.js::updateFacture ← ventesApi.js::updateFacture")

    def test_route_plus_specifique_gagne_mes_equipes_card(self):
        # `/crm/equipes/statistiques/` est servi par la vue `path()`, pas par le detail `<pk>` du ViewSet.
        sortie = self.sortie("appelants", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions")
        self.assertTrue(sortie["vue_drf"])
        self.assertEqual(sorted({w["nom"] for w in sortie["wrappers"]}), ["getEquipes", "saveEquipe"])
        self.assertEqual(sortie["ecrans"], ["frontend/src/pages/parametres/EquipesCommercialesSection.jsx"])
        self.assertNotIn("MesEquipesCard", sortie["texte"])

    def test_route_sans_wrapper_dit_zero_ecran(self):
        sortie = self.sortie("appelants", f"{DJ}/ventes/views/facture.py::FactureViewSet.emettre")
        self.assertEqual([r["route"] for r in sortie["routes"]], ["/api/django/ventes/factures/<id>/emettre/"])
        self.assertEqual(sortie["ecrans"], [])
        self.assertIn("→ 0 écran", sortie["texte"])

    def test_appelants_python_au_format_fichier_symbole(self):
        sortie = self.sortie("appelants", f"{DJ}/ventes/utils/echeancier.py::tranches_normalisees")
        prod = sorted(e["symbole"] for e in sortie["python"] if not e["test"])
        self.assertEqual(prod, [f"{DJ}/ventes/quote_engine/builder.py::tranches_echeancier_en_montant",
                                f"{DJ}/ventes/utils/echeancier.py::schedule_for_devis"])  # pas reexport.py
        self.assertEqual([e["symbole"] for e in sortie["python"] if e["test"]],
                         [f"{DJ}/ventes/tests/test_echeancier.py::EcheancierTests.test_vide"])
        self.assertEqual([c["symbole"] for c in sortie["chaines"]],
                         ["backend/django_core/erp_agentique/settings.py::<module>"])
        self.assertIn("front : 0 écran", sortie["texte"])

    def test_ecrivains_suivent_setattr_dynamique(self):
        sortie = self.sortie("ecrivains", "Lead.whatsapp")
        vias = {(e["symbole"].split("::")[1], e["via"]) for e in sortie["ecrivains"]}
        self.assertEqual(vias, {("_apply_meta_form_extras", "affectation"),
                                ("merge_leads", "setattr dynamique via _MERGE_FILL_FIELDS"),
                                ("creer_lead_proprietaire", "Lead(…)")})   # ni filter(), ni la table QUESTIONS
        self.assertTrue(sortie["champ_existe"])
        absent = self.sortie("ecrivains", "Lead.telephone_whatsapp")
        self.assertFalse(absent["champ_existe"])
        self.assertIn("⚠ champ `telephone_whatsapp` introuvable sur le modèle `Lead`", absent["texte"])


class AssertionsTests(_SurDepotErp):
    def test_ancien_litteral_trouve_le_test_qui_le_fige(self):
        # Given de la tache : `--anciens "Montant figé"` sur FactureViewSet.perform_update.
        sortie = self.sortie("assertions-existantes", f"{FACTURE} --anciens Montant figé")
        tests = {a["test"]: a for a in sortie["assertions"]}
        fige = tests[f"{DJ}/facturation/tests/test_atot_montants_figes.py::MontantsFigesTests::"
                     "test_patch_montant_emise_refuse"]
        self.assertIn("littéral « Montant figé »", fige["via"])
        self.assertEqual((fige["verbes"], fige["codes"], fige["roles"], fige["verdict"]),
                         (["PATCH"], [400], ["responsable"], ""))
        self.assertIn("reste vert", sortie["texte"])
        # Golden ACRM26 (R3_V3) : les tests 201/200/404 de tests_zsal3_equipe_crud.py, constante URL suivie,
        # route soeur `statistiques` exclue.
        acrm = self.sortie("assertions-existantes", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions")
        zsal3 = {a["test"].rsplit("::", 1)[1]: a for a in acrm["assertions"] if "tests_zsal3_equipe_crud" in a["test"]}
        self.assertEqual(sorted(zsal3), ["test_commercial_peut_lire", "test_cross_company_404",
                                         "test_responsable_cree_une_equipe"])
        self.assertEqual({c for a in zsal3.values() for c in a["codes"]}, {201, 200, 404})
        self.assertEqual({r for a in zsal3.values() for r in a["roles"]}, {"admin"})

    def test_asec28_patch_seulement(self):
        sortie = self.sortie("assertions-existantes", FACTURE)
        asec28 = {a["test"].rsplit("::", 1)[1]: a for a in sortie["assertions"] if "asec28" in a["test"]}
        self.assertEqual(list(asec28), ["test_relance_etranger_400"])   # le POST de creation n'exerce pas l'update
        self.assertEqual(asec28["test_relance_etranger_400"]["verbes"], ["PATCH"])

    def test_lecteurs_sample_trouve_tests_et_front(self):
        sortie = self.sortie("lecteurs-sample", "roof_layout_v2.schema.json")
        self.assertEqual({x["fichier"]: x["categorie"] for x in sortie["lecteurs"]},
                         {f"{DJ}/calepinage/tests/test_roof_contrat.py": "test-py",
                          "frontend/src/features/calepinage/roof.test.js": "test-front"})

    def test_listes_figees_nomment_garde_type_et_regeneration(self):
        sortie = self.sortie("listes-figees", f"{DJ}/crm/services.py")
        gardes = {g["garde"]: g for g in sortie["gardes"]}
        g = gardes["scripts/check_get_or_create.py"]
        self.assertEqual((g["liste"], g["type_de_cle"], g["declare"], g["regeneration"]),
                         ("docs/get-or-create-audit.md", "par_symbole", True,
                          "python scripts/check_get_or_create.py --write"))
        g = gardes["scripts/check_lignes.py"]
        self.assertEqual((g["liste"], g["type_de_cle"], g["declare"]), ("scripts/lignes_allow.txt", "par_ligne", False))
        self.assertIn("TYPE_DE_CLE absent (déduit : par_ligne)", sortie["texte"])
        self.assertIn("python scripts/check_lignes.py --write-baseline", sortie["texte"])

    def test_type_de_cle_declare_par_les_quatre_gardes(self):
        # Lit les gardes de CE depot (scripts/, possedes par la lane) : pas du code applicatif.
        for garde in ("check_get_or_create", "check_naive_datetime", "check_duplicats_litteraux",
                      "check_taches_cablage"):
            texte = (ROOT / "scripts" / f"{garde}.py").read_text(encoding="utf-8")
            self.assertRegex(texte, r'(?m)^TYPE_DE_CLE = "par_(?:ligne|symbole)"(?:  #.*)?$', garde)


class JumeauxTests(_SurDepotErp):
    def test_get_permissions_rend_105_corps_identiques_sans_troncature(self):
        # R3_V3 : « 12 jumeaux » affirmes alors qu'il y en avait 105 (cible comprise).
        sortie = self.sortie("jumeaux", f"{DJ}/crm/views.py::EquipeCommercialeViewSet.get_permissions")
        identiques = sortie["corps_identiques"]
        self.assertEqual(len(identiques), 105)                  # docstrings ignorees
        self.assertEqual(sortie["nb_corps_identiques"], 105)
        self.assertEqual(sum(j["cible"] for j in identiques), 1)
        self.assertIn("corps identiques 105", sortie["texte"])
        for j in identiques:                                    # aucune troncature dans le texte
            self.assertIn(j["symbole"].split("::", 1)[1], sortie["texte"])
        for fichier in ("crm/views.py", "sav/views.py", "stock/views.py"):
            self.assertIn(f"`{DJ}/{fichier}` :", sortie["texte"])   # liste par fichier
        self.assertEqual(sortie["meme_nom"], [f"{DJ}/crm/views.py::CanalViewSet.get_permissions"])
        self.assertRegex(sortie["texte"],
                         r"\(gen [0-9a-f]{9} .+::EquipeCommercialeViewSet\.get_permissions#[0-9a-f]{8}\)")

    def test_emplacement_mur_et_spl_qui_deplace(self):
        sortie = self.sortie("emplacement", f"{DJ}/crm/services.py::merge_leads")
        self.assertTrue(sortie["mur"])
        self.assertGreaterEqual(sortie["lignes"], 2000)
        self.assertEqual(sortie["spl"], ["SPL22"])               # SPL3 le cite sans le deplacer ; SPL1 fermee
        self.assertIn("@after: SPL22", sortie["texte"])

    def test_test_canonique_classe_le_module_kitting_en_premier(self):
        sortie = self.sortie(
            "test-canonique", f"{DJ}/installations/services.py::recreer_nomenclature_ordre_assemblage")
        modules = [m["module"] for m in sortie["modules"]]
        self.assertEqual(modules[0], f"{DJ}/installations/tests_fg328_kitting.py")   # affinite FG328 de l'appelant
        self.assertEqual(len(modules), 3)
        self.assertTrue(sortie["modules"][0]["id_de_tache"])

    def test_inspecter_est_l_api_exportee(self):
        rapport = at.inspecter(f"{DJ}/installations/services.py::recreer_nomenclature_ordre_assemblage")
        self.assertEqual(sorted(rapport), ["emplacement", "jumeaux", "test_canonique", "texte"])
        self.assertTrue(callable(at.index))

    def test_clause_texte_pret_a_coller(self):
        tampon = io.StringIO()
        with redirect_stdout(tampon), redirect_stderr(io.StringIO()):
            code = at.main(["--clause", "Emplacement", f"{DJ}/crm/services.py::merge_leads"])
        self.assertEqual(code, 0)
        self.assertTrue(tampon.getvalue().startswith(f"Emplacement : `{DJ}/crm/services.py::merge_leads` ("))

    def test_verifier_tampon_perime_exit_1(self):
        depot = DepotJetable({"backend/app/a.py": "def f():\n    return 1\n"})
        self.addCleanup(depot.fermer)
        _, _, d = at.resoudre("backend/app/a.py::f", depot.racine)
        frais = f"(gen abcdef123 backend/app/a.py::f#{d.empreinte[:8]})"
        (depot.racine / "docs").mkdir()
        (depot.racine / "docs" / "PLAN.md").write_text(
            f"- [ ] ZZT1 — **x** : {frais} Files: `backend/app/a.py`\n"
            "- [ ] ZZT2 — **y** : (gen abcdef123 backend/app/a.py::f#00000000) Files: `backend/app/a.py`\n",
            encoding="utf-8")
        sauvegarde = at.ctc.ROOT
        at.ctc.ROOT = depot.racine
        self.addCleanup(setattr, at.ctc, "ROOT", sauvegarde)
        self.assertFalse(at.verifier("ZZT1", racine=depot.racine)["perimee"])
        self.assertTrue(at.verifier("ZZT2", racine=depot.racine)["perimee"])
        (depot.racine / "backend" / "app" / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        self.assertTrue(at.verifier("ZZT1", racine=depot.racine)["perimee"])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(at.main(["--verifier", "ZZT2", "--racine", str(depot.racine)]), 1)


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.depot = DepotJetable({
            "backend/app/a.py": "def f():\n    return 1\n\n\nclass K:\n    def m(self):\n        return f()\n",
            "backend/app/b.py": "from app.a import f\n\n\ndef g():\n    return f()\n",
            "backend/app/migrations/0001_x.py": "def f():\n    return 1\n",
            "scripts/c.py": "def h():\n    return 2\n",
        })
        self.addCleanup(self.depot.fermer)

    def test_narrow_restreint_par_git_grep(self):
        idx = at.index(narrow=r"\bg\b", racine=self.depot.racine, cache_dir=self.depot.cache.name)
        self.assertEqual(sorted(idx), ["backend/app/b.py"])

    def test_index_complet_ignore_les_migrations_et_qualifie(self):
        idx = at.index(racine=self.depot.racine, cache_dir=self.depot.cache.name)
        self.assertEqual(sorted(idx), ["backend/app/a.py", "backend/app/b.py", "scripts/c.py"])
        noms = [d.qualname for d in idx["backend/app/a.py"]["defs"]]
        self.assertEqual(noms, ["f", "K", "K.m"])

    def test_cache_disque_par_sha_puis_invalide(self):
        cache = self.depot.cache.name
        at.index(racine=self.depot.racine, cache_dir=cache)
        self.assertEqual(len(list(Path(cache).glob("*.pickle"))), 1)
        at.index(racine=self.depot.racine, cache_dir=cache)
        self.assertEqual(len(list(Path(cache).glob("*.pickle"))), 1, "chaud = meme cle")
        (self.depot.racine / "scripts" / "c.py").write_text("def h2():\n    return 3\n", encoding="utf-8")
        at._ETATS.clear()  # l'etat git est memoise par process (une commande = un process)
        idx = at.index(racine=self.depot.racine, cache_dir=cache)
        self.assertEqual([d.qualname for d in idx["scripts/c.py"]["defs"]], ["h2"])

    def test_corps_identiques_meme_empreinte(self):
        idx = at.index(racine=self.depot.racine, cache_dir=self.depot.cache.name)
        empreintes = {d.qualname: d.empreinte for f in idx.values() for d in f["defs"]}
        self.assertNotEqual(empreintes["f"], empreintes["h"])


if __name__ == "__main__":
    unittest.main()
