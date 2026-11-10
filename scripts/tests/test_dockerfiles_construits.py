"""ADEP6 - aucun Dockerfile ni requirements ORPHELIN.

Un `Dockerfile*` ou `requirements*.txt` jamais construit ni surveille est un
squelette mort (`backend/celery_worker/` : requirements non epingles, 4 taches
PLACEHOLDER, jamais importees). Chaque fichier doit etre reference par :

  * un `build`/`context`/`dockerfile` d'un `docker-compose*.yml` ;
  * un `docker build -f`, un `file:` ou un `context:` d'un workflow, ou son
    chemin cite dans un workflow / un script de deploiement ;
  * un `directory` de `.github/dependabot.yml` (surveillance des dependances).

Stdlib pure : `python -m unittest scripts.tests.test_dockerfiles_construits`.
"""
import re
import sys
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

IGNORES = {".git", "node_modules", ".claude", "dist", "build", "parked", "__pycache__"}
# Fichiers deja orphelins au 09/10/2026 (cliquet : ne peut que retrecir, une
# entree morte fait echouer le test). Chaque ligne dit pourquoi.
ORPHELINS_CONNUS = {
    # Simulateur FastAPI rehoste en systemd sur le serveur (jamais construit
    # par docker/CI) et non surveille par dependabot : a decider par le
    # fondateur (surveiller /services/simulator ou retirer le dossier).
    "services/simulator/requirements.txt": "ADEP6 - hors compose, hors dependabot",
}


def fichiers_a_garder(racine):
    for chemin in sorted(racine.rglob("*")):
        if not chemin.is_file():
            continue
        if any(p in IGNORES for p in chemin.relative_to(racine).parts):
            continue
        nom = chemin.name
        if nom.startswith("Dockerfile") or (nom.startswith("requirements") and nom.endswith(".txt")):
            yield chemin.relative_to(racine).as_posix()


def _textes_de_reference(racine):
    textes = []
    motifs = ("docker-compose*.yml", "docker-compose*.yaml", ".github/workflows/*.yml",
              ".github/workflows/*.yaml", ".github/dependabot.yml", "scripts/*.sh",
              "scripts/*.ps1", ".github/actions/**/*.yml")
    for motif in motifs:
        for chemin in racine.glob(motif):
            try:
                textes.append(chemin.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(textes)


def _dossiers_dependabot(racine):
    chemin = racine / ".github" / "dependabot.yml"
    if not chemin.is_file():
        return set()
    return {d.strip().strip("/") for d in re.findall(
        r"directory:\s*[\"']?([^\"'\n]+)", chemin.read_text(encoding="utf-8"))}


def _contextes_compose(racine):
    """Dossiers de contexte de build des fichiers compose (`build: ./x` ou
    `context: ./x`), relatifs a la racine."""
    contextes = set()
    for chemin in racine.glob("docker-compose*.y*ml"):
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:^|\s)(?:build|context):\s*[\"']?([./\w-]+)", texte):
            contextes.add(m.group(1).strip().lstrip("./").strip("/") or ".")
    return contextes


def orphelins(racine):
    textes = _textes_de_reference(racine)
    dependabot = _dossiers_dependabot(racine)
    contextes = _contextes_compose(racine)
    sortie = []
    for rel in fichiers_a_garder(racine):
        dossier = str(Path(rel).parent.as_posix()).strip(".") or "."
        nom = Path(rel).name
        reference = (
            rel in textes
            or (nom.startswith("Dockerfile") and dossier in contextes)
            or (nom.startswith("requirements") and dossier in dependabot)
            or (nom.startswith("Dockerfile") and dossier in dependabot)
            or (nom.startswith("Dockerfile") and f"{dossier}/{nom}" in textes))
        if not reference:
            sortie.append(rel)
    return sortie


def _ecrire(racine, rel, contenu=""):
    chemin = racine / rel
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")


class DockerfilesConstruitsTests(unittest.TestCase):
    def test_dockerfile_orphelin_rouge(self):
        import tempfile
        racine = Path(tempfile.mkdtemp())
        _ecrire(racine, "docker-compose.yml",
                "services:\n  web:\n    build: ./backend/web\n")
        _ecrire(racine, "backend/web/Dockerfile")           # construit
        _ecrire(racine, "backend/celery_worker/Dockerfile")  # orphelin
        _ecrire(racine, "backend/celery_worker/requirements.txt")  # orphelin
        _ecrire(racine, ".github/dependabot.yml",
                "updates:\n  - package-ecosystem: pip\n    directory: \"/backend/api\"\n")
        _ecrire(racine, "backend/api/requirements.txt")      # surveille
        self.assertEqual(orphelins(racine), [
            "backend/celery_worker/Dockerfile",
            "backend/celery_worker/requirements.txt"])

    def test_chemin_cite_dans_un_workflow_compte(self):
        import tempfile
        racine = Path(tempfile.mkdtemp())
        _ecrire(racine, ".github/workflows/ci.yml",
                "run: docker build -f .github/ci-image/Dockerfile.e2e .\n")
        _ecrire(racine, ".github/ci-image/Dockerfile.e2e")
        self.assertEqual(orphelins(racine), [])

    def test_depot_reel_vert(self):
        reels = set(orphelins(ROOT))
        self.assertEqual(reels - set(ORPHELINS_CONNUS), set(),
                         "Dockerfile/requirements jamais construit ni surveille")
        self.assertEqual(set(ORPHELINS_CONNUS) - reels, set(),
                         "entree morte de ORPHELINS_CONNUS : retirez-la")

    def test_dependabot_groupes_sans_majeure(self):
        # ADCG66 — une majeure incompatible ne rougit plus toute la PR de groupe.
        import yaml
        config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
        groupes = 0
        for entree in config["updates"]:
            for nom, groupe in (entree.get("groups") or {}).items():
                groupes += 1
                self.assertEqual(groupe.get("update-types"), ["minor", "patch"], nom)
        self.assertEqual(groupes, 6)
        django_core = next(e for e in config["updates"] if e["directory"] == "/backend/django_core")
        self.assertIn({"dependency-name": "django", "versions": [">=6.0"]}, django_core.get("ignore") or [])

    def test_squelette_celery_worker_supprime(self):
        self.assertFalse((ROOT / "backend" / "celery_worker").exists())
        self.assertFalse((ROOT / "frontend" / "Dockerfile.dev").exists())


# --- Tests fusionnes depuis test_docker_compose.py ---
# ADCG14 — santé des services vitaux dans docker-compose.yml (+ docker-compose.prod.yml).
#
# Nouveau fichier car : aucun module de test pour les fichiers compose (texte de la tâche).
# Lecture PyYAML (installé avant le runner) ; la balise compose `!reset` est acceptée.
# Run:
#     python -m unittest scripts.tests.test_docker_compose -v
class _Chargeur(yaml.SafeLoader):
    pass


_Chargeur.add_constructor("!reset", lambda loader, node: None)


def _services():
    """Services de docker-compose.yml, clés de docker-compose.prod.yml superposées."""
    base = yaml.load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"), Loader=_Chargeur)
    prod = yaml.load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"), Loader=_Chargeur)
    services = base["services"]
    for nom, cles in (prod.get("services") or {}).items():
        services.setdefault(nom, {}).update(cles or {})
    return services


class DockerComposeTests(unittest.TestCase):
    def setUp(self):
        self.services = _services()

    def test_services_vitaux_ont_un_healthcheck(self):
        attendus = {
            "db": "pg_isready -h localhost -U $$POSTGRES_USER",
            "redis": "redis-cli",
            "django_core": "http://localhost:8000/api/django/core/health/live/",
        }
        for nom, sonde in attendus.items():
            with self.subTest(service=nom):
                hc = self.services[nom].get("healthcheck")
                self.assertIsNotNone(hc, f"{nom} sans healthcheck")
                self.assertIn(sonde, " ".join(hc["test"]))
                for cle in ("interval", "timeout", "start_period"):
                    self.assertIn(cle, hc)
        self.assertIn("urllib.request", " ".join(self.services["django_core"]["healthcheck"]["test"]))
        self.assertNotIn("health/ready", " ".join(self.services["django_core"]["healthcheck"]["test"]))

    def test_django_attend_base_et_redis_sains(self):
        dep = self.services["django_core"]["depends_on"]
        self.assertEqual(dep["db"]["condition"], "service_healthy")
        self.assertEqual(dep["redis"]["condition"], "service_healthy")

    def test_nginx_sans_condition_de_sante_sur_django(self):
        dep = self.services["nginx"].get("depends_on") or []
        if isinstance(dep, dict):
            self.assertNotEqual((dep.get("django_core") or {}).get("condition"), "service_healthy")


class AutomergeDependabotTests(unittest.TestCase):
    """ADCG67 / D-ADCG-2 : fusion auto des seules PR de securite mono-paquet patch/minor."""

    def test_automerge_dependabot_securite_seulement(self):
        texte = (ROOT / ".github/workflows/dependabot-automerge.yml").read_text(encoding="utf-8")
        wf = yaml.safe_load(texte)
        declencheurs = wf.get("on") or wf.get(True)
        self.assertEqual(set(declencheurs), {"pull_request_target"})
        job = wf["jobs"]["automerge"]
        self.assertEqual(
            job["if"], "github.event.pull_request.user.login == 'dependabot[bot]'")
        self.assertEqual(wf["permissions"], {})
        self.assertEqual(job["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertNotIn("actions/checkout", texte)
        self.assertNotIn("pull_request.head", texte)
        etapes = job["steps"]
        meta = next(e for e in etapes if "fetch-metadata" in e.get("uses", ""))
        self.assertRegex(meta["uses"], r"dependabot/fetch-metadata@v\d+\.\d+\.\d+$")
        fusion = next(e for e in etapes if "gh pr merge" in e.get("run", ""))
        self.assertIn("gh pr merge --auto \"$PR_URL\"", fusion["run"])
        self.assertNotIn("--merge", fusion["run"])
        cond = fusion["if"]
        for garde in ("dependency-group == ''",
                      "contains(steps.meta.outputs.dependency-names, ',')",
                      "semver-patch", "semver-minor"):
            self.assertIn(garde, cond)
        self.assertNotIn("semver-major", cond)
        self.assertNotIn("--admin", texte)
        self.assertNotIn("ghsa-id", cond)
        # Invariant : tout ecosysteme groupe toutes les minor+patch, sinon une PR
        # non groupee patch/minor ne prouverait plus la securite.
        dep = yaml.safe_load(
            (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
        for upd in dep["updates"]:
            groupes = (upd.get("groups") or {}).values()
            self.assertTrue(
                any(g.get("patterns") == ["*"]
                    and {"minor", "patch"} <= set(g.get("update-types") or [])
                    for g in groupes),
                "ecosysteme sans groupe '*' minor+patch : %s" % upd.get("directory"))


if __name__ == "__main__":
    unittest.main()
