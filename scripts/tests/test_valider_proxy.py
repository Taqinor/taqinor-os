"""ADCG9 — `scripts/valider-proxy.sh` rend un code non nul quand le Caddyfile ou
nginx.conf est invalide, et nomme le fichier fautif.

Un FAUX `docker` (en tête du PATH) imite les deux validateurs : `caddy validate`
refuse un Caddyfile qui porte une directive inconnue, `nginx -t` refuse un
nginx.conf aux accolades déséquilibrées. Le vrai docker tourne en CI (étape
« Valider la configuration du proxy » du job backend-lint-fast).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "valider-proxy.sh"

FAUX_DOCKER = r"""#!/bin/bash
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


def _bash() -> str | None:
    if sys.platform == "win32":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        return str(git_bash) if git_bash.is_file() else None
    return shutil.which("bash")


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
        faux.write_text(FAUX_DOCKER, encoding="utf-8", newline="\n")
        faux.chmod(0o755)
        self.journal = self.tmp / "journal.txt"

    def _lancer(self, chemin=None):
        env = dict(os.environ)
        env["PATH"] = chemin if chemin is not None else str(self.bin) + os.pathsep + env.get("PATH", "")
        env["VALIDER_PROXY_RACINE"] = self.depot.as_posix()
        env["FAUX_DOCKER_JOURNAL"] = self.journal.as_posix()
        return subprocess.run([BASH, SCRIPT.as_posix()], capture_output=True, text=True,
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


if __name__ == "__main__":
    unittest.main()
