"""ADCG1+ — la séquence de deploy (`scripts/auto-deploy.sh`) et son déclencheur
manuel (`scripts/deploy-prod.ps1`) rejoués au BANC : faux `git` / `docker` /
`flock` / `systemctl` / `curl` qui journalisent chaque appel dans `calls.log`,
arborescence /opt remplacée par un dossier temporaire. Aucun serveur, aucun
docker réel. Patron : `docs/audits/sondes/ADCG/C-ADCG-002.py`.

Run : python -m unittest scripts.tests.test_auto_deploy -v
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTO = ROOT / "scripts" / "auto-deploy.sh"
PS1 = ROOT / "scripts" / "deploy-prod.ps1"
A, B, C = "a" * 40, "b" * 40, "c" * 40

# Faux exécutable commun : journalise « <nom> <args> », simule quelques sorties,
# et sort en 1 quand l'appel correspond au motif FAIL (regex étendue).
SHIM = r'''#!/usr/bin/env bash
n=$(basename "$0"); a="$n $*"; echo "$a" >> "$BANC/calls.log"
case "$a" in *" up -d"*) echo "env DEPLOYED_SHA=${DEPLOYED_SHA-}" >> "$BANC/calls.log";; esac
case "$a" in
 "git rev-parse origin/main") cat "$BANC/origin";;
 "git rev-parse HEAD") cat "$BANC/HEAD";;
 "git rev-parse --short "*) echo "${3:0:9}";;
 "git diff --name-only"*) cat "$BANC/changes";;
 "git reset --hard "*) t=$3; [ "$t" = origin/main ] && t=$(cat "$BANC/origin"); echo "$t" > "$BANC/HEAD";;
 "git show origin/main:scripts/auto-deploy.sh") cat "$BANC/auto_origin.sh";;
 *"python -c"*health*) echo "${HEALTH-ok}";;
 *showmigrations*) printf '%b' "${SHOWMIG-}";;
 "curl "*) printf '%s' "${HTTP_CODE-200}";;
 *pending_restart*) echo "${PENDING_RESTART-0}";;
esac
if [ -n "${FAIL:-}" ] && echo "$a" | grep -qE "$FAIL"; then exit 1; fi
exit 0
'''
SHIMS = ("git", "docker", "flock", "systemctl", "curl")


def _px(chemin):
    """Chemin vu par bash (Git Bash sous Windows : /c/...)."""
    p = str(chemin).replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if re.match(r"^[A-Za-z]:", p) else p


def _bash():
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    return git_bash if os.path.exists(git_bash) else shutil.which("bash")


def _remote():
    """Le script distant de deploy-prod.ps1 (here-string `$remote`)."""
    texte = PS1.read_text(encoding="utf-8")
    corps = re.search(r"\$remote = @'\r?\n(.*?)\r?\n'@", texte, re.S).group(1)
    return "ZERO_DOWNTIME=0\n" + corps


class Banc:
    """Racine système factice : bin/ (faux exécutables), repo/, state/."""

    def __init__(self, dossier, changes="", last=A, origin=B):
        self.d = Path(dossier)
        for sous in ("bin", "repo/backend/db", "state"):
            (self.d / sous).mkdir(parents=True, exist_ok=True)
        for nom in SHIMS:
            shim = self.d / "bin" / nom
            shim.write_bytes(SHIM.encode())
            shim.chmod(0o755)
        (self.d / "repo/backend/db/provision_sql_agent_ro.sh").write_bytes(
            b'echo PROVISION >> "$BANC/calls.log"\n')
        (self.d / "HEAD").write_text(last or A)
        (self.d / "origin").write_text(origin)
        (self.d / "changes").write_text(changes)
        (self.d / "auto_origin.sh").write_bytes(AUTO.read_bytes())
        if last:
            self.ecrire("last_deployed_commit", last)

    def ecrire(self, nom, valeur):
        (self.d / "state" / nom).write_text(valeur)

    def lire(self, nom):
        f = self.d / "state" / nom
        return f.read_text(encoding="utf-8").strip() if f.exists() else None

    def jouer(self, texte=None, **env):
        texte = AUTO.read_text(encoding="utf-8") if texte is None else texte
        texte = (texte.replace("/opt/taqinor-os", _px(self.d / "repo"))
                 .replace("/opt/autodeploy", _px(self.d / "state")))
        script = self.d / "s.sh"
        script.write_bytes(texte.replace("\r\n", "\n").encode())
        r = subprocess.run(
            [_bash(), "-c", 'export PATH="$1:$PATH"; bash "$2"', "_",
             _px(self.d / "bin"), _px(script)],
            env={**os.environ, "BANC": _px(self.d), "PAUSE_SANTE": "0", **env}, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=180)
        return r.returncode, r.stdout + r.stderr

    @property
    def appels(self):
        f = self.d / "calls.log"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    @property
    def journal(self):
        return self.lire("deploy.log") or ""

    def index(self, motif):
        return next((i for i, a in enumerate(self.appels) if re.search(motif, a)), None)

    def compte(self, motif):
        return sum(1 for a in self.appels if re.search(motif, a))


LOT_ECRAN_API = "frontend/src/pages/ventes/Liste.jsx\nbackend/django_core/apps/ventes/views.py\n"


@unittest.skipUnless(_bash(), "bash introuvable")
class AutoDeployTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def banc(self, sous="", **kw):
        return Banc(Path(self._tmp.name) / sous, **kw)

    def test_manuel_declenche_la_sequence_unique(self):
        banc = self.banc(changes=LOT_ECRAN_API)
        rc, sortie = banc.jouer(_remote())
        self.assertEqual(rc, 0, sortie)
        commandes = {a.split(" ")[0] + " " + a.split(" ")[1] for a in banc.appels}
        self.assertEqual(commandes, {"git fetch", "git show", "systemctl start"}, banc.appels)
        self.assertIn("systemctl start taqinor-autodeploy.service", banc.appels)
        self.assertNotIn("docker compose", _remote())
        self.assertNotIn("manage.py", _remote())
        self.assertEqual((banc.d / "state" / "auto-deploy.sh").read_bytes(), AUTO.read_bytes())
        # Le code de sortie de la séquence est rendu tel quel.
        (banc.d / "calls.log").unlink()
        rc, _ = banc.jouer(_remote(), FAIL="^systemctl start")
        self.assertNotEqual(rc, 0)
        # La séquence unique : écran + API -> build frontend, restart backend, six étapes.
        (banc.d / "calls.log").unlink()
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie + banc.journal)
        self.assertIsNotNone(banc.index(r"prod\.yml build frontend$"))
        self.assertIsNotNone(banc.index(r" restart django_core "))
        for motif in ("PROVISION", "seed_catalogue", "pg_isready", "showmigrations",
                      r"ps -a --format", "builder prune"):
            self.assertIsNotNone(banc.index(motif), motif)
        self.assertEqual(banc.lire("last_deployed_commit"), B)
        self.assertIn("— OK", banc.journal)

    def test_migrate_avant_tout_redemarrage(self):
        """ADCG2 — migrate (image neuve) précède `up -d` et `restart django_core`."""
        lot = ("backend/django_core/apps/crm/models.py\n"
               "backend/django_core/apps/crm/migrations/0999_x.py\n")
        banc = self.banc(changes=lot)
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie)
        i_migrate = banc.index(r"run --rm --no-deps django_core python manage\.py migrate --noinput")
        self.assertIsNotNone(i_migrate, banc.appels)
        self.assertLess(i_migrate, banc.index(r"prod\.yml up -d"))
        self.assertLess(i_migrate, banc.index(r" restart django_core "))
        self.assertGreater(banc.index("init_roles"), banc.index(r"prod\.yml up -d"))
        # Cycle 2 : migrate en échec -> rien n'est redémarré ni recréé.
        (banc.d / "calls.log").unlink()
        banc.ecrire("last_deployed_commit", A)
        rc, _ = banc.jouer(FAIL="manage.py migrate")
        self.assertNotEqual(rc, 0)
        self.assertEqual(banc.compte(r"prod\.yml up -d"), 0, banc.appels)
        self.assertEqual(banc.compte(r" restart "), 0, banc.appels)
        self.assertIn("ECHEC", banc.journal)

    def test_echec_meme_commit_pas_rejoue(self):
        """ADCG3 — deux cycles sur un commit en échec = un seul migrate."""
        banc = self.banc(changes="backend/django_core/apps/crm/views.py\n")
        for _ in range(2):
            rc, _ = banc.jouer(FAIL="manage.py migrate")
        self.assertEqual(banc.compte("manage.py migrate --noinput"), 1, banc.appels)
        self.assertEqual(banc.lire("commit_en_echec"), B)
        self.assertEqual(banc.journal.count("ECHEC"), 1, banc.journal)
        # Le chemin manuel efface l'état : B est retenté.
        banc.jouer(_remote())
        self.assertIsNone(banc.lire("commit_en_echec"))
        banc.jouer(FAIL="manage.py migrate")
        self.assertEqual(banc.compte("manage.py migrate --noinput"), 2)
        # Un nouveau commit C est tenté ; un succès efface l'état.
        (banc.d / "origin").write_text(C)
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie)
        self.assertEqual(banc.compte("manage.py migrate --noinput"), 3)
        self.assertIsNone(banc.lire("commit_en_echec"))
        self.assertEqual(banc.lire("last_deployed_commit"), C)

    def test_sante_vide_ou_http_non_200_est_un_echec(self):
        """ADCG4 — sonde vide, showmigrations en échec, health/ready ≠ 200 : ECHEC."""
        lot = "backend/django_core/apps/crm/views.py\n"
        cas = {"sonde vide": {"HEALTH": ""}, "showmigrations": {"FAIL": "showmigrations"},
               "http 502": {"HTTP_CODE": "502"}}
        for nom, env in cas.items():
            with self.subTest(nom):
                banc = self.banc(nom.replace(" ", "_"), changes=lot)
                rc, _ = banc.jouer(**env)
                self.assertNotEqual(rc, 0, banc.journal)
                self.assertIn("ECHEC", banc.journal)
                self.assertEqual(banc.lire("last_deployed_commit"), A)
        self.assertEqual(banc.compte(r"^curl .*--resolve api\.taqinor\.ma:443:127\.0\.0\.1 "
                                     r"https://api\.taqinor\.ma/api/django/core/health/ready/"), 5)
        banc = self.banc("vert", changes=lot)
        rc, sortie = banc.jouer(HEALTH="degraded")
        self.assertEqual(rc, 0, sortie + banc.journal)
        self.assertEqual(banc.lire("last_deployed_commit"), B)

    def test_echec_revient_au_dernier_commit_sain(self):
        """ADCG5 — migrate ou santé en échec : retour effectif à last_deployed_commit."""
        lot = "backend/django_core/apps/crm/views.py\nbackend/django_core/requirements.txt\n"
        for nom, env in {"migrate": {"FAIL": "manage.py migrate"}, "sante": {"HEALTH": ""}}.items():
            with self.subTest(nom):
                banc = self.banc(nom, changes=lot)
                rc, _ = banc.jouer(**env)
                self.assertNotEqual(rc, 0)
                i_neuf = banc.index(f"^git reset --hard {B}$")
                i_sain = banc.index(f"^git reset --hard {A}$")
                self.assertIsNotNone(i_sain, banc.appels)
                self.assertLess(i_neuf, i_sain)
                apres = banc.appels[i_sain:]
                self.assertTrue(any(re.search(r"prod\.yml build django_core$", a) for a in apres))
                self.assertTrue(any(re.search(r"prod\.yml up -d", a) for a in apres))
                self.assertTrue(any(re.search(r" restart django_core .* nginx$", a) for a in apres))
                self.assertIn(f"ROLLBACK vers {A[:9]} effectué", banc.journal)
                self.assertEqual((banc.d / "HEAD").read_text().strip(), A)
                self.assertEqual(banc.lire("last_deployed_commit"), A)
        banc = self.banc("sans_commit_sain", changes=lot, last="")
        rc, _ = banc.jouer(FAIL="manage.py migrate")
        self.assertNotEqual(rc, 0)
        self.assertIn("ECHEC sans retour arrière (aucun commit sain)", banc.journal)
        self.assertNotIn("ROLLBACK", banc.journal)

    def test_requirements_et_meryem_ne_sont_pas_des_docs(self):
        """ADCG7 — seuls *.md/*.markdown et docs/** (hors docs/meryem/) sont « docs »."""
        banc = self.banc("requirements",
                         changes="backend/django_core/requirements.txt\ndocs/CODEMAP.md\n")
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie + banc.journal)
        self.assertIsNotNone(banc.index(r"prod\.yml build django_core$"))
        self.assertIn("rebuild ciblé", banc.journal)
        self.assertEqual(banc.lire("last_deployed_commit"), B)
        banc = self.banc("meryem", changes="docs/meryem/guide.md\n")
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie + banc.journal)
        self.assertIsNotNone(banc.index("publier_documents_meryem"))
        self.assertEqual(banc.lire("last_deployed_commit"), B)
        banc = self.banc("docs", changes="docs/CODEMAP.md\n")
        banc.jouer()
        self.assertIn("docs/markdown uniquement", banc.journal)
        self.assertIsNone(banc.index("manage.py"))

    def test_caddy_invalide_fait_echouer_le_deploy(self):
        """ADCG8 — validate en échec : 0 reload ; reload en échec : ECHEC ; sinon OK."""
        lot = "backend/caddy/Caddyfile\n"
        for nom, fail in {"validate": "caddy validate", "reload": "caddy reload"}.items():
            with self.subTest(nom):
                banc = self.banc(nom, changes=lot)
                rc, _ = banc.jouer(FAIL=fail)
                self.assertNotEqual(rc, 0)
                self.assertIn("ECHEC", banc.journal)
                self.assertEqual(banc.lire("last_deployed_commit"), A)
                if nom == "validate":
                    self.assertEqual(banc.compte("caddy reload"), 0, banc.appels)
        banc = self.banc("vert", changes=lot)
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie + banc.journal)
        self.assertLess(banc.index("caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile"),
                        banc.index("caddy reload"))
        self.assertIn("— OK", banc.journal)

    def test_fichiers_embarques_declenchent_leur_service(self):
        """ADCG10 — worker du site, image minio, postgresql.conf monté."""
        banc = self.banc("worker", changes="apps/web/worker/deadLetter.mjs\n")
        self.assertEqual(banc.jouer()[0], 0, banc.journal)
        self.assertIsNotNone(banc.index(r"prod\.yml build frontend$"))
        banc = self.banc("minio", changes="backend/minio/Dockerfile\n")
        self.assertEqual(banc.jouer()[0], 0, banc.journal)
        self.assertLess(banc.index(r"prod\.yml build minio$"), banc.index(r"prod\.yml up -d"))
        banc = self.banc("pgconf", changes="backend/db/postgresql.conf\n")
        self.assertEqual(banc.jouer(PENDING_RESTART="1")[0], 0, banc.journal)
        self.assertIsNotNone(banc.index(r"exec -T db sh -c psql .*SELECT pg_reload_conf\(\)"))
        self.assertIn("AVERTISSEMENT : postgresql.conf exige un redémarrage de db", banc.journal)
        self.assertEqual(banc.compte(r" restart db"), 0)
        banc = self.banc("pgconf_sans_restart", changes="backend/db/postgresql.conf\n")
        banc.jouer()
        self.assertNotIn("exige un redémarrage", banc.journal)

    def test_commit_deploye_passe_aux_conteneurs(self):
        """ADCG19 — `up -d` reçoit DEPLOYED_SHA = B ; le compose prod le passe aux 4 services."""
        banc = self.banc(changes="backend/django_core/apps/crm/views.py\n")
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie + banc.journal)
        i_up = banc.index(r"prod\.yml up -d --remove-orphans$")
        self.assertEqual(banc.appels[i_up + 1], f"env DEPLOYED_SHA={B}")
        compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
        for service in ("django_core", "celery_worker", "celery_worker_interactive", "celery_beat"):
            bloc = re.search(rf"(?ms)^  {service}:\n(.*?)(?=^  \S)", compose.replace("\r\n", "\n")).group(1)
            self.assertIn("DEPLOYED_SHA: ${DEPLOYED_SHA:-}", bloc, service)
        banc = self.banc("docs", changes="docs/CODEMAP.md\n")
        banc.jouer()
        self.assertIsNone(banc.index("DEPLOYED_SHA"))

    def test_zero_downtime_drapeau_lu_puis_efface(self):
        banc = self.banc(changes=LOT_ECRAN_API)
        rc, _ = banc.jouer(_remote().replace("ZERO_DOWNTIME=0", "ZERO_DOWNTIME=1"))
        self.assertEqual(rc, 0)
        self.assertIsNotNone(banc.lire("zero_downtime"))
        rc, sortie = banc.jouer()
        self.assertEqual(rc, 0, sortie)
        self.assertIsNotNone(banc.index(r"--scale django_core=2"))
        self.assertIsNone(banc.lire("zero_downtime"))


if __name__ == "__main__":
    unittest.main()
