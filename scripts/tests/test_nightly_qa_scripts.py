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
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SETUP = ROOT / "scripts" / "setup-nightly-qa.ps1"
NIGHTLY = ROOT / "scripts" / "nightly-qa.ps1"
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


def _first_invocation(code):
    m = INVOCATION.search(code)
    return (m.start(), m.group(0)) if m else (len(code), None)


class TestCommun(unittest.TestCase):
    def test_les_deux_scripts_existent(self):
        self.assertTrue(SETUP.is_file(), SETUP)
        self.assertTrue(NIGHTLY.is_file(), NIGHTLY)

    def test_ascii_seulement_pour_powershell_5_1(self):
        for path in (SETUP, NIGHTLY):
            data = path.read_bytes()
            non_ascii = [b for b in data if b > 127]
            self.assertEqual(non_ascii, [], f"{path.name} : octets non-ASCII")

    def test_jamais_de_force(self):
        for path in (SETUP, NIGHTLY):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("--force", text, path.name)
            for ln in text.splitlines():
                if "seed_demo" in ln:
                    self.assertNotRegex(ln, r"(?i)-force\b", f"{path.name} : {ln}")

    def test_seed_demo_bien_appele_sans_forcage(self):
        for path in (SETUP, NIGHTLY):
            self.assertRegex(
                _code(path),
                r"docker compose exec -T django_core python manage\.py seed_demo \}",
                path.name,
            )

    def test_jamais_d_url_de_prod(self):
        for path in (SETUP, NIGHTLY):
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
        for path in (SETUP, NIGHTLY):
            code = _code(path)
            for op in ("&&", "||", "??"):
                self.assertNotIn(op, code, f"{path.name} : operateur {op}")

    def test_ne_touche_jamais_aux_crons_github(self):
        for path in (SETUP, NIGHTLY):
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

    def test_outils_mcp_autorises_correspondent_a_mcp_json(self):
        serveurs = json.loads(MCP.read_text(encoding="utf-8"))["mcpServers"]
        for nom in ("playwright", "chrome-devtools"):
            self.assertIn(nom, serveurs)
            self.assertIn(f"'mcp__{nom}'", self.code)


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.code = _code(SETUP)

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


if __name__ == "__main__":
    unittest.main()
