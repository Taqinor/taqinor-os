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
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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

