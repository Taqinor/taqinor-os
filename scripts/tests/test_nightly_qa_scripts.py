"""Tests QAH11 — garde-fous dans le TEXTE de scripts/setup-nightly-qa.ps1 et
scripts/nightly-qa.ps1.

Les deux scripts ne s'executent PAS en CI (ils pilotent Docker Desktop, le
planificateur de taches Windows et `claude -p` sur la machine de Reda) : ce
test lit leur source et verrouille les regles qui ne doivent jamais regresser :
- jamais de drapeau `--force` (en particulier sur `seed_demo`) ;
- jamais d'URL de production — la seule cible est http://localhost ;
- le kill switch docs/qa-explorer.config.yml est lu AVANT toute commande git,
  docker, claude ou schtasks ; « skill pas encore cree » sort proprement avant
  docker et claude ;
- `schtasks /Create ... /F` (creer OU remplacer : relancer = mise a jour, jamais
  de doublon), quotidien, 23:00 par defaut ;
- aucune installation silencieuse ; aucun contact avec les crons GitHub ;
- compatibles Windows PowerShell 5.1 (ASCII seul, ni `&&`, ni `||`, ni `??`).

Stdlib pure (unittest). Run:
    python -m unittest scripts.tests.test_nightly_qa_scripts -v
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
SETUP = ROOT / "scripts" / "setup-nightly-qa.ps1"
NIGHTLY = ROOT / "scripts" / "nightly-qa.ps1"
# AMET99 : les etapes stack / migrations / seed_demo vivent dans pile_locale.ps1,
# appele par setup-nightly-qa.ps1 (survivant unique) : il fait partie de la chaine.
PILE = ROOT / "scripts" / "pile_locale.ps1"
MCP = ROOT / ".mcp.json"
GITIGNORE = ROOT / ".gitignore"

PROD_MARKERS = (
    "api.taqinor.ma",
    "178.105.192.116",
    "178-105-192-116",
    "sslip.io",
    "taqinor.ma",
    "workers.dev",
)

# Une invocation de commande native : le mot en tete d'instruction ou apres
# `{`, `(`, `|`, `&` — jamais un morceau de chemin (`.claude/skills/...`).
INVOCATION = re.compile(
    r"(?<![\w./\\'\"-])(git|docker|claude|schtasks|taskkill)\s+[\w/-]"
)


def _code(path):
    """Source sans commentaires (`# ...` en debut de ligne et blocs `<# #>`)."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<#.*?#>", "", text, flags=re.S)
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines)


def _chaine(path):
    """Source du script + celle de pile_locale.ps1 quand il la delegue (AMET99)."""
    code = _code(path)
    if "pile_locale.ps1" in code:
        code += "\n" + _code(PILE)
    return code


def _first_invocation(code):
    m = INVOCATION.search(code)
    return (m.start(), m.group(0)) if m else (len(code), None)


class TestCommun(unittest.TestCase):
    def test_les_deux_scripts_existent(self):
        self.assertTrue(SETUP.is_file(), SETUP)
        self.assertTrue(NIGHTLY.is_file(), NIGHTLY)
        self.assertTrue(PILE.is_file(), PILE)

    def test_ascii_seulement_pour_powershell_5_1(self):
        for path in (SETUP, NIGHTLY, PILE):
            data = path.read_bytes()
            non_ascii = [b for b in data if b > 127]
            self.assertEqual(non_ascii, [], f"{path.name} : octets non-ASCII")

    def test_aucun_octet_de_controle_ps1(self):
        # AANA86 (C-AANA-VER4-012) : un 0x08 a la place de \b cassait Test-Path.
        for path in sorted((ROOT / "scripts").glob("*.ps1")):
            bad = [(i, b) for i, b in enumerate(path.read_bytes()) if b < 32 and b not in (9, 10, 13)]
            self.assertEqual(bad, [], f"{path.name} : octets de controle (position, octet)")

    def test_jamais_de_force(self):
        for path in (SETUP, NIGHTLY, PILE):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("--force", text, path.name)
            for ln in text.splitlines():
                if "seed_demo" in ln:
                    self.assertNotRegex(ln, r"(?i)-force\b", f"{path.name} : {ln}")

    def test_seed_demo_bien_appele_sans_forcage(self):
        for path in (SETUP, NIGHTLY, PILE):
            if path is PILE:
                continue  # c'est lui qui porte l'appel ; SETUP le delegue (chaine)
            self.assertRegex(
                _chaine(path),
                r"docker compose exec -T django_core python manage\.py seed_demo \}",
                path.name,
            )

    def test_jamais_d_url_de_prod(self):
        for path in (SETUP, NIGHTLY, PILE):
            text = path.read_text(encoding="utf-8")
            for marker in PROD_MARKERS:
                self.assertNotIn(marker, text, f"{path.name} : {marker}")
            for url in re.findall(r"https?://[^\s'\"`)]+", text):
                url = url.rstrip(".,;:")
                self.assertRegex(
                    url, r"^http://(localhost|127\.0\.0\.1)(/|:|$)",
                    f"{path.name} : URL hors stack locale : {url}",
                )

    def test_syntaxe_powershell_5_1(self):
        for path in (SETUP, NIGHTLY, PILE):
            code = _code(path)
            for op in ("&&", "||", "??"):
                self.assertNotIn(op, code, f"{path.name} : operateur {op}")

    def test_ne_touche_jamais_aux_crons_github(self):
        for path in (SETUP, NIGHTLY, PILE):
            code = _code(path)
            self.assertNotIn(".github", code, path.name)
            self.assertNotIn("gh workflow", code, path.name)

    def test_logs_ignores_par_git(self):
        lines = [ln.strip() for ln in GITIGNORE.read_text(encoding="utf-8").splitlines()]
        self.assertIn("logs/", lines)


class TestNightly(unittest.TestCase):
    def setUp(self):
        self.code = _code(NIGHTLY)

    def test_kill_switch_lu_avant_toute_commande(self):
        self.assertIn("'docs/qa-explorer.config.yml'", self.code)
        lecture = self.code.find("$KillSwitch = Read-KillSwitch $ConfigPath")
        self.assertGreater(lecture, -1, "lecture du kill switch introuvable")
        pos, cmd = _first_invocation(self.code)
        self.assertLess(
            lecture, pos,
            f"une commande ({cmd!r}) precede la lecture du kill switch",
        )
        # enabled: false -> sortie AVANT le verrou, git, docker, claude.
        sortie = self.code.find("if ($KillSwitch.State -eq 'false')")
        self.assertGreater(sortie, lecture)
        self.assertLess(sortie, pos)
        self.assertLess(sortie, self.code.find("nightly-qa.lock"))

    def test_refus_si_une_passe_tourne_encore_avant_git(self):
        verrou = self.code.find("nightly-qa.lock")
        self.assertGreater(verrou, -1)
        self.assertIn("exit 2", self.code)
        self.assertLess(verrou, _first_invocation(self.code)[0])

    def test_skill_absent_sortie_propre_avant_docker_et_claude(self):
        absent = self.code.find("Test-Path -LiteralPath $SkillPath")
        self.assertGreater(absent, -1)
        self.assertIn("SKILL PAS ENCORE CREE", self.code)
        self.assertLess(absent, self.code.find("docker compose up -d --build"))
        self.assertLess(absent, self.code.find("Start-Process -FilePath $claudeExe"))

    def test_verrou_single_writer_test_backend(self):
        self.assertIn("name=erp-agentique-django_core-run", self.code)
        self.assertLess(
            self.code.find("Get-TestBackendLock\n"),
            self.code.find("Start-Process -FilePath $claudeExe"),
        )

    def test_claude_headless_sur_l_abonnement(self):
        self.assertIn("$SkillRel = '.claude/skills/' + $Skill + '/SKILL.md'", self.code)
        self.assertIn("[string]$Skill = 'qa-explorer'", self.code)
        self.assertIn("'run the ' + $Skill + ' skill ('", self.code)
        self.assertIn("-p \"", self.code)
        self.assertIn("--model opus", self.code)
        self.assertIn("--permission-mode dontAsk", self.code)
        self.assertIn("Remove-Item Env:ANTHROPIC_API_KEY", self.code)

    def test_journal_horodate_et_code_de_sortie(self):
        self.assertIn("'logs\\nightly-qa'", self.code)
        self.assertIn("Get-Date -Format 'yyyyMMdd-HHmmss'", self.code)
        self.assertIn("exit $ExitCode", self.code)
        self.assertRegex(self.code, r"return 1\b")

    def test_gc_workspace_appele_en_fin_de_passe(self):
        # ADCG22 : apres la passe claude, avant exit $ExitCode, encadre, sans docker.
        appel = self.code.find("scripts\\gc-workspace.ps1') -MaxAgeDays 14 -SansDocker")
        self.assertGreater(appel, self.code.find("Start-Process -FilePath $claudeExe"))
        self.assertGreater(appel, self.code.find("Write-Log ('fin : code de sortie ' + $ExitCode)"))
        self.assertLess(appel, self.code.rfind("exit $ExitCode"))
        bloc = self.code[self.code.find("if ($script:PasseLancee) {"):self.code.rfind("exit $ExitCode")]
        self.assertIn("try {", bloc)
        self.assertIn("} catch { Write-Log (", bloc)
        self.assertNotIn("$ExitCode =", bloc)

    def test_outils_mcp_autorises_correspondent_a_mcp_json(self):
        serveurs = json.loads(MCP.read_text(encoding="utf-8"))["mcpServers"]
        for nom in ("playwright", "chrome-devtools"):
            self.assertIn(nom, serveurs)
            self.assertIn(f"'mcp__{nom}'", self.code)


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.code = _chaine(SETUP)

    def test_schtasks_en_mode_creer_ou_remplacer(self):
        # Les invocations reelles (pas les libelles/messages entre apostrophes).
        creations = re.findall(r"(?<![\w'\"])schtasks /Create [^\n}]*", self.code)
        self.assertTrue(creations, "aucun schtasks /Create")
        for c in creations:
            self.assertRegex(c, r"/F\b", f"schtasks /Create sans /F : {c}")
            self.assertIn("/SC DAILY", c)
            self.assertIn("/ST", c)
        self.assertNotIn("schtasks /Delete", self.code)

    def test_noms_heures_et_options(self):
        self.assertIn("$TaskQa = 'TAQINOR nightly QA'", self.code)
        self.assertIn("$TaskAutopilot = 'TAQINOR error-autopilot'", self.code)
        self.assertIn("[string]$Time = '23:00'", self.code)
        self.assertIn("[switch]$WithErrorAutopilot", self.code)
        self.assertIn("[string]$ErrorAutopilotTime = '12:00'", self.code)
        self.assertIn("' -Skill error-autopilot'", self.code)
        self.assertIn("scripts\\nightly-qa.ps1", self.code)

    def test_prerequis_verifies_jamais_installes(self):
        for sonde in ("claude auth status", "node --version", "docker info",
                      "docker compose version", "Get-Command git"):
            self.assertIn(sonde, self.code, sonde)
        for installeur in ("winget", "choco ", "npm install", "Install-Module",
                           "msiexec", "Invoke-WebRequest -Uri 'http"):
            self.assertNotIn(installeur, self.code, installeur)

    def test_depot_env_stack_et_rappel_mcp(self):
        self.assertIn("git pull --ff-only origin main", self.code)
        self.assertIn("'.env.example'", self.code)
        self.assertIn("docker compose up -d --build", self.code)
        self.assertIn("/mcp", self.code)
        serveurs = json.loads(MCP.read_text(encoding="utf-8"))["mcpServers"]
        for nom in ("playwright", "chrome-devtools"):
            self.assertIn(f'"{nom}"', self.code, f"rappel /mcp sans {nom}")
            args = " ".join(serveurs[nom]["args"])
            self.assertNotIn("@latest", args)
            self.assertRegex(args, r"@\d+\.\d+\.\d+", f"{nom} : version non epinglee")
        self.assertIn("serena", serveurs)


class TestProblemesProd(unittest.TestCase):
    """BPQ5 : le tri du matin passe par nightly-qa.ps1 SANS docker, seed ni Playwright."""

    def setUp(self):
        self.code = _code(NIGHTLY)

    def test_skill_et_config_propres(self):
        self.assertIn("'qa-explorer', 'error-autopilot', 'problemes-prod'", self.code)
        self.assertIn("'docs/problemes-prod.config.yml'", self.code)
        self.assertIn("PROBLEMES_PROD_STATUS", self.code)
        self.assertTrue((ROOT / ".claude/skills/problemes-prod/SKILL.md").exists())
        cfg = (ROOT / "docs/problemes-prod.config.yml").read_text(encoding="utf-8")
        self.assertRegex(cfg, r"(?m)^enabled\s*:\s*true")
        for cle in ("max_minutes", "max_findings_per_run", "base_url"):
            self.assertIn(cle + ":", cfg)

    def test_branche_sans_docker(self):
        # Les etapes docker (pile, migrations, verrou test-backend) sont sautees.
        debut = self.code.find("if ($Skill -ne 'problemes-prod') {")
        fin = self.code.find("$claudeExe = Resolve-ClaudeExe")
        self.assertGreater(debut, -1)
        self.assertGreater(fin, debut)
        bloc = self.code[debut:fin]
        for etape in ("Start-DockerDesktop", "docker compose up -d --build",
                      "Get-TestBackendLock", "migrate --noinput"):
            self.assertIn(etape, bloc, etape)
        self.assertNotIn("Start-DockerDesktop", self.code[fin:].split("function")[0])

    def test_skill_en_lecture_seule(self):
        texte = (ROOT / ".claude/skills/problemes-prod/SKILL.md").read_text(encoding="utf-8")
        for garde in ("Jamais d'ecriture en production", "Signature:", "check_err_prod.py",
                      "PROBLEMES_PROD_STATUS", "gh pr merge --auto --merge"):
            self.assertIn(garde, texte, garde)


LANCEUR = ROOT / "scripts" / "nightly-qa-lanceur.ps1"
PWSH = shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(PWSH, "pwsh/powershell absent")
class TestLanceur(unittest.TestCase):
    """ADCG15 : lanceur hors depot, trace lisible quand nightly-qa.ps1 manque."""

    def _lancer(self, depot, appdata):
        env = dict(os.environ, LOCALAPPDATA=str(appdata))
        r = subprocess.run(
            [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LANCEUR), "-Depot", str(depot)],
            env=env, capture_output=True, text=True, timeout=120,
        )
        journal = Path(appdata) / "taqinor" / "nightly-qa.log"
        return r.returncode, journal.read_text(encoding="utf-8-sig").splitlines()

    def test_script_absent_laisse_une_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            depot = Path(tmp) / "depot"
            (depot / "scripts").mkdir(parents=True)
            code, lignes = self._lancer(depot, Path(tmp) / "appdata")
            self.assertEqual(code, 3)
            self.assertEqual(len(lignes), 2, lignes)
            self.assertIn("lancement", lignes[0])
            self.assertIn("ECHEC lancement : scripts\\nightly-qa.ps1 absent", lignes[1])
            self.assertIn("(git status : ", lignes[1])
            self.assertRegex(lignes[1], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d  ")

    def test_script_present_code_transmis(self):
        with tempfile.TemporaryDirectory() as tmp:
            depot = Path(tmp) / "depot"
            (depot / "scripts").mkdir(parents=True)
            (depot / "scripts" / "nightly-qa.ps1").write_text("param([string]$Skill)\nexit 0\n", encoding="ascii")
            code, lignes = self._lancer(depot, Path(tmp) / "appdata")
            self.assertEqual(code, 0)
            self.assertIn("lancement", lignes[0])
            self.assertTrue(lignes[-1].endswith("fin code 0"), lignes)
            code, lignes = self._lancer(depot, Path(tmp) / "appdata")
            self.assertEqual(len(lignes), 4, "lignes horodatees conservees")

    def test_setup_copie_et_enregistre_le_lanceur(self):
        code = _code(SETUP)
        self.assertIn("'taqinor\\nightly-qa-lanceur.ps1'", code)
        self.assertIn("Copy-Item -LiteralPath (Join-Path $RepoRoot 'scripts\\nightly-qa-lanceur.ps1')", code)
        self.assertIn("$tr = Get-TaskCommand $Lanceur $ExtraArgs", code)
        self.assertIn("' -Depot '", code)


class TestDernierPassage(unittest.TestCase):
    """ADCG16 : contrôle « dernier passage » lu dans le journal hors dépôt."""

    def _main(self, contenu):
        import contextlib
        import importlib.util
        import io
        from datetime import datetime, timedelta
        spec = importlib.util.spec_from_file_location(
            "nightly_qa_dernier_passage", ROOT / "scripts" / "nightly_qa_dernier_passage.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        maintenant = datetime(2026, 11, 10, 8, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "nightly-qa.log"
            if contenu is not None:
                lignes = [f"{maintenant - timedelta(hours=h):%Y-%m-%d %H:%M:%S}  {t}" for h, t in contenu]
                journal.write_text("\n".join(lignes) + "\n", encoding="utf-8-sig")
            sortie = io.StringIO()
            with contextlib.redirect_stdout(sortie):
                code = mod.main(["--journal", str(journal)], maintenant=maintenant)
        return code, sortie.getvalue()

    def test_plus_de_36_h_rend_un(self):
        code, texte = self._main([(40, "fin code 0"), (10, "ECHEC lancement : scripts\\nightly-qa.ps1 absent")])
        self.assertEqual(code, 1)
        self.assertIn("dernier passage réussi : 2026-11-08 16:00 (il y a 40 h)", texte)
        self.assertIn("dernière tentative : 2026-11-09 22:00 ECHEC lancement", texte)

    def test_passage_de_cette_nuit_rend_zero(self):
        code, _ = self._main([(30, "fin code 1"), (8, "lancement skill qa-explorer"), (6, "fin code 0")])
        self.assertEqual(code, 0)

    def test_aucun_passage_consigne(self):
        for contenu in (None, [(2, "fin code 1")]):
            code, texte = self._main(contenu)
            self.assertEqual(code, 1)
            self.assertIn("aucun passage consigné", texte)

    def test_appele_par_le_setup(self):
        self.assertIn("scripts\\nightly_qa_dernier_passage.py", _code(SETUP))


if __name__ == "__main__":
    unittest.main()

    def test_tache_rattrape_une_nuit_manquee(self):
        # ERR-JPB-NIGHTLY-QA-TACHE-FRAGILE : sans StartWhenAvailable, une nuit
        # manquee (PC eteint/en veille) est perdue sans trace.
        self.assertIn("-StartWhenAvailable", self.code)
        self.assertIn("-WakeToRun", self.code)


class TestNightlyRobustesse(unittest.TestCase):
    def setUp(self):
        self.code = _code(NIGHTLY)

    def test_verrou_a_ttl_et_pid_verifie(self):
        # TTL > max_minutes + 30 ; le PID doit etre un powershell LANCANT nightly-qa.
        verrou = self.code.find("nightly-qa.lock")
        bloc = self.code[verrou:verrou + 2500]
        self.assertIn("LastWriteTime", bloc)
        self.assertIn("$script:MaxMinutes + 30", bloc)
        self.assertIn("Win32_Process", bloc)
        self.assertIn("nightly-qa", bloc[bloc.find("Win32_Process"):])

    def test_journal_de_bord_hors_depot_avant_toute_etape(self):
        self.assertIn("$env:LOCALAPPDATA", self.code)
        self.assertIn("nightly-qa.log", self.code)
        self.assertLess(self.code.find("nightly-qa.log"),
                        self.code.find("Read-KillSwitch $ConfigPath"))


# --- Tests fusionnes depuis test_deploy_prod.py ---
# ADCG6 — le message final de `scripts/deploy-prod.ps1` suit le JOURNAL du serveur.
#
# Le script est lancé par PowerShell (pwsh, présent sur les exécuteurs ubuntu ;
# Windows PowerShell en repli sur un poste) avec `ssh` / `scp` remplacés par des
# FONCTIONS PowerShell (résolues avant les exécutables) : aucune connexion réelle.
#
# Run : python -m unittest scripts.tests.test_deploy_prod -v
PS1 = ROOT / "scripts" / "deploy-prod.ps1"


ENVELOPPE = r'''[Console]::OutputEncoding = [Text.Encoding]::UTF8
function scp { $global:LASTEXITCODE = 0 }
function ssh {
    foreach ($ligne in ($env:FAUX_SSH_SORTIE -split '\|')) { $ligne }
    $global:LASTEXITCODE = [int]$env:FAUX_SSH_RC
}
& '__PS1__'
exit $LASTEXITCODE
'''


def _powershell():
    return shutil.which("pwsh") or shutil.which("powershell")


class DeployProdTests(unittest.TestCase):
    def jouer(self, sortie, rc):
        shell = _powershell()
        self.assertTrue(shell, "pwsh introuvable : ce test ne se saute jamais")
        with tempfile.TemporaryDirectory() as d:
            enveloppe = Path(d) / "enveloppe.ps1"
            enveloppe.write_text(ENVELOPPE.replace("__PS1__", str(PS1)), encoding="utf-8-sig")
            r = subprocess.run(
                [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(enveloppe)],
                env={**os.environ, "FAUX_SSH_SORTIE": sortie, "FAUX_SSH_RC": str(rc),
                     "USERPROFILE": d}, capture_output=True, timeout=120)
        return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")

    def test_message_suit_le_journal_du_serveur(self):
        rc, sortie = self.jouer(
            "Deploiement lance|[2026-11-10T10:00:00Z] DEPLOY b4c5d6e — ECHEC (x)|"
            "[2026-11-10T10:01:00Z] ROLLBACK vers a1b2c3d effectué", 1)
        self.assertEqual(rc, 1, sortie)
        self.assertIn("ECHEC — retour arrière vers a1b2c3d effectué", sortie)

        rc, sortie = self.jouer("Deploiement lance|DEPLOY b4c5d6e — ECHEC", 1)
        self.assertEqual(rc, 1, sortie)
        self.assertIn("ECHEC SANS retour arrière : DEPLOY b4c5d6e — ECHEC", sortie)
        self.assertNotIn("retour arrière vers", sortie)
        self.assertNotIn("rollback automatique", sortie.lower())

        rc, sortie = self.jouer("Deploiement lance|DEPLOY b4c5d6e — OK", 0)
        self.assertEqual(rc, 0, sortie)
        self.assertIn("Deploiement termine", sortie)
        self.assertNotIn("sslip.io", PS1.read_text(encoding="utf-8"))


# --- Tests fusionnes depuis test_e2e_local.py ---
# ADCG23 — `scripts/e2e-local.sh stop` n'arrête que les services que `up` a démarrés.
#
# Un FAUX `docker` (en tête du PATH) journalise ses appels ; l'état du script vit
# dans un dossier jetable (`E2E_ETAT_DIR`), jamais dans le /tmp du poste.
#     python -m unittest scripts.tests.test_e2e_local -v
SCRIPT = ROOT / "scripts" / "e2e-local.sh"


FAUX_DOCKER = '#!/bin/bash\necho "$*" >> "$FAUX_DOCKER_JOURNAL"\nexit 0\n'


def _bash() -> str | None:
    if sys.platform == "win32":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        return str(git_bash) if git_bash.is_file() else None
    return shutil.which("bash")


@unittest.skipUnless(_bash(), "bash introuvable")
class E2eLocalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "bin").mkdir()
        faux = self.tmp / "bin" / "docker"
        faux.write_text(FAUX_DOCKER, encoding="utf-8", newline="\n")
        faux.chmod(0o755)
        self.journal = self.tmp / "journal.txt"
        self.etat = self.tmp / "etat"
        self.etat.mkdir()

    def _stop(self):
        env = dict(os.environ, E2E_ETAT_DIR=self.etat.as_posix(),
                   FAUX_DOCKER_JOURNAL=self.journal.as_posix())
        env["PATH"] = str(self.tmp / "bin") + os.pathsep + env.get("PATH", "")
        res = subprocess.run([_bash(), SCRIPT.as_posix(), "stop"], capture_output=True, text=True,
                             encoding="utf-8", env=env, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        appels = self.journal.read_text(encoding="utf-8").splitlines() if self.journal.exists() else []
        return res.stdout, [a for a in appels if a.startswith("compose stop")]

    def test_stop_ne_coupe_que_ce_que_up_a_demarre(self):
        (self.etat / "taqinor-e2e-services.txt").write_text("minio\n", encoding="utf-8", newline="\n")
        _, arrets = self._stop()
        self.assertEqual(arrets, ["compose stop minio"])
        self.assertFalse((self.etat / "taqinor-e2e-services.txt").exists(), "état non effacé après stop")

    def test_sans_etat_rien_n_est_arrete(self):
        sortie, arrets = self._stop()
        self.assertEqual(arrets, [])
        self.assertIn("services laissés en marche (non démarrés par up)", sortie)

    def test_up_ne_retient_que_les_services_absents(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        releve = texte.index("docker compose ps --services --status running")
        self.assertLess(releve, texte.index("docker compose up -d db redis minio"))
        self.assertNotIn("docker compose stop db redis minio", texte)


# --- Tests fusionnes depuis test_gc_workspace.py ---
# ADCG21 — scripts/gc-workspace.ps1 exécuté sur un dépôt git temporaire (en -WhatIf).
#
# Le script se résout par `$PSScriptRoot` : on le copie sous `scripts/` du dépôt de test.
# Run:
#     python -m unittest scripts.tests.test_gc_workspace -v
SCRIPT_GC = ROOT / "scripts" / "gc-workspace.ps1"


def _git(depot, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=depot, capture_output=True, text=True, check=True,
    ).stdout


@unittest.skipUnless(PWSH and shutil.which("git"), "pwsh/powershell ou git absent")
class GcWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.depot = Path(self._tmp.name)
        _git(self.depot, "init", "-q", "-b", "main")
        (self.depot / "a.txt").write_text("a\n", encoding="utf-8")
        _git(self.depot, "add", "a.txt")
        _git(self.depot, "commit", "-q", "-m", "a")
        _git(self.depot, "branch", "worktree-agent-x")
        _git(self.depot, "checkout", "-q", "-b", "worktree-agent-y")
        (self.depot / "b.txt").write_text("b\n", encoding="utf-8")
        _git(self.depot, "add", "b.txt")
        _git(self.depot, "commit", "-q", "-m", "b")
        _git(self.depot, "checkout", "-q", "main")
        (self.depot / "scripts").mkdir()
        shutil.copy(SCRIPT_GC, self.depot / "scripts" / "gc-workspace.ps1")

    def tearDown(self):
        self._tmp.cleanup()

    def _lancer(self, *extra):
        r = subprocess.run(
            [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(self.depot / "scripts" / "gc-workspace.ps1"), "-WhatIf", *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_branche_worktree_agent_fusionnee_supprimee(self):
        sortie = self._lancer()
        self.assertIn("delete merged branch worktree-agent-x", sortie)
        self.assertNotIn("delete merged branch worktree-agent-y", sortie)
        garde = sortie[sortie.index("KEEP (non fusionn"):]
        self.assertIn("- worktree-agent-y", garde)
        branches = _git(self.depot, "branch", "--format=%(refname:short)").split()
        self.assertEqual(sorted(branches), ["main", "worktree-agent-x", "worktree-agent-y"])

    def test_sans_docker_garde_le_cache(self):
        # ADCG22 : la passe nocturne appelle -SansDocker (cache de build garde chaud).
        self.assertIn("docker builder prune", self._lancer())
        sortie = self._lancer("-SansDocker")
        self.assertNotIn("docker builder prune", sortie)
        self.assertIn("worktrees supprimes : 0", sortie)


# --- Tests fusionnes depuis test_valider_proxy.py ---
# ADCG9 — `scripts/valider-proxy.sh` rend un code non nul quand le Caddyfile ou
# nginx.conf est invalide, et nomme le fichier fautif.
#
# Un FAUX `docker` (en tête du PATH) imite les deux validateurs : `caddy validate`
# refuse un Caddyfile qui porte une directive inconnue, `nginx -t` refuse un
# nginx.conf aux accolades déséquilibrées. Le vrai docker tourne en CI (étape
# « Valider la configuration du proxy » du job backend-lint-fast).
SCRIPT_PROXY = ROOT / "scripts" / "valider-proxy.sh"


FAUX_DOCKER_PROXY = r"""#!/bin/bash
echo "$*" >> "$FAUX_DOCKER_JOURNAL"
[ "$1" = build ] && exit 0
for a in "$@"; do
  case "$a" in
    *:/etc/caddy:ro)
      grep -q directive_inconnue "${a%:/etc/caddy:ro}/Caddyfile" \
        && { echo "Error: unrecognized directive: directive_inconnue" >&2; exit 1; } ;;
    *:/etc/nginx/nginx.conf:ro)
      f="${a%:/etc/nginx/nginx.conf:ro}"
      [ "$(tr -cd '{' < "$f" | wc -c)" = "$(tr -cd '}' < "$f" | wc -c)" ] \
        || { echo "nginx: [emerg] unexpected end of file" >&2; exit 1; } ;;
  esac
done
exit 0
"""


BASH = _bash()


@unittest.skipUnless(BASH, "bash introuvable")
class ValiderProxyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.depot = self.tmp / "depot"
        shutil.copytree(ROOT / "backend" / "caddy", self.depot / "backend" / "caddy")
        shutil.copytree(ROOT / "backend" / "nginx", self.depot / "backend" / "nginx")
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        faux = self.bin / "docker"
        faux.write_text(FAUX_DOCKER_PROXY, encoding="utf-8", newline="\n")
        faux.chmod(0o755)
        self.journal = self.tmp / "journal.txt"

    def _lancer(self, chemin=None):
        env = dict(os.environ)
        env["PATH"] = chemin if chemin is not None else str(self.bin) + os.pathsep + env.get("PATH", "")
        env["VALIDER_PROXY_RACINE"] = self.depot.as_posix()
        env["FAUX_DOCKER_JOURNAL"] = self.journal.as_posix()
        return subprocess.run([BASH, SCRIPT_PROXY.as_posix()], capture_output=True, text=True,
                              encoding="utf-8", env=env, timeout=60)

    def test_depot_reel_valide_deux_ok(self):
        res = self._lancer()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("OK backend/caddy/Caddyfile", res.stdout)
        self.assertIn("OK backend/nginx/nginx.conf", res.stdout)
        journal = self.journal.read_text(encoding="utf-8")
        self.assertIn("caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile", journal)
        self.assertIn("nginx -t", journal)
        for hote in ("django_core", "fastapi_ia", "frontend"):
            self.assertIn(f"--add-host {hote}:", journal)

    def test_config_invalide_rend_un(self):
        caddyfile = self.depot / "backend" / "caddy" / "Caddyfile"
        caddyfile.write_text(caddyfile.read_text(encoding="utf-8").replace(
            "{$PUBLIC_HOSTNAME}, api.taqinor.ma {", "{$PUBLIC_HOSTNAME}, api.taqinor.ma {\n\tdirective_inconnue", 1),
            encoding="utf-8", newline="\n")
        res = self._lancer()
        self.assertEqual(res.returncode, 1)
        self.assertIn("ECHEC backend/caddy/Caddyfile", res.stderr)
        self.assertIn("OK backend/nginx/nginx.conf", res.stdout)

    def test_nginx_sans_accolade_fermante_rend_un(self):
        conf = self.depot / "backend" / "nginx" / "nginx.conf"
        texte = conf.read_text(encoding="utf-8")
        conf.write_text(texte[:texte.rindex("}")], encoding="utf-8", newline="\n")
        res = self._lancer()
        self.assertEqual(res.returncode, 1)
        self.assertIn("ECHEC backend/nginx/nginx.conf", res.stderr)
        self.assertIn("OK backend/caddy/Caddyfile", res.stdout)

    def test_docker_absent_rend_deux_jamais_vert(self):
        vide = self.tmp / "vide"
        vide.mkdir()
        res = self._lancer(chemin=str(vide))
        self.assertEqual(res.returncode, 2)
        self.assertIn("docker absent", res.stderr)
