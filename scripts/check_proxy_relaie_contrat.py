#!/usr/bin/env python3
"""GARDE CI (stage-names) — ADEV72 : un proxy relaie CHAQUE clé obligatoire du contrat.

CLASSE C-ADEV-020 : « champ requis côté serveur, jamais envoyé par le
consommateur ». `proposition-accept.ts` ne relayait pas `entreprise` alors que
le serveur l'exigeait (400 `entreprise.raison_sociale` en prod, corrigé par
CIW305). Cette garde généralise le contrôle.

Pour chaque proxy `apps/web/src/pages/api/proposition-*.ts` déclaré dans
`PROXYS`, les clés de corps OBLIGATOIRES sont lues dans les contrats partagés
`apps/web/src/contract_samples/*.json` :

  * `proposal_accept.json` -> `corps.<clé>` dont la description dit OBLIGATOIRE ;
  * `acceptation_entreprise.json` -> `regles.en_ligne` : les `entreprise.<clé>`
    nommées OBLIGATOIRES (raison_sociale, signataire_qualite, ice).

Une clé est « relayée » quand son nom figure comme identifiant dans le source
du proxy (commentaires retirés : lecture structurelle du corps relayé, pas un
simple mot de prose). Sinon la garde échoue en nommant le proxy et la clé.

DETTE_CONNUE : clés obligatoires dont le consommateur n'est pas encore bâti
(ratchet : une entrée morte fait échouer la garde).

Usage : python scripts/check_proxy_relaie_contrat.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = Path("apps") / "web" / "src"
# proxy -> contrats (fichiers de contract_samples) qui décrivent son corps.
PROXYS = {
    "proposition-accept.ts": ("proposal_accept.json", "acceptation_entreprise.json"),
}
# (proxy, clé) -> pourquoi la clé obligatoire n'est pas (encore) relayée.
DETTE_CONNUE = {}
_RE_ENTREPRISE = re.compile(r"`entreprise\.(\w+)`")


def cles_obligatoires(contrat: dict) -> set:
    """Clés de corps déclarées OBLIGATOIRES par un contrat partagé."""
    cles = set()
    corps = contrat.get("corps")
    if isinstance(corps, dict):
        for cle, texte in corps.items():
            if isinstance(texte, str) and "OBLIGATOIRE" in texte.upper():
                cles.add(cle)
    regle = (contrat.get("regles") or {}).get("en_ligne") if isinstance(
        contrat.get("regles"), dict) else None
    if isinstance(regle, str) and "OBLIGATOIRE" in regle.upper():
        cles.update(_RE_ENTREPRISE.findall(regle))
    return cles


def _sans_commentaires(texte: str) -> str:
    texte = re.sub(r"/\*[\s\S]*?\*/", "", texte)
    return re.sub(r"(?m)(?<![:'\"`])//.*$", "", texte)


def cle_relayee(cle: str, source: str) -> bool:
    return re.search(r"(?<![\w$])" + re.escape(cle) + r"(?![\w$])",
                     _sans_commentaires(source)) is not None


def manques(root: Path = ROOT, proxys: dict | None = None) -> set:
    """{(proxy, clé)} des clés obligatoires non relayées."""
    proxys = PROXYS if proxys is None else proxys
    sortie = set()
    for proxy, contrats in proxys.items():
        chemin = root / WEB / "pages" / "api" / proxy
        if not chemin.is_file():
            sortie.add((proxy, "<proxy introuvable>"))
            continue
        source = chemin.read_text(encoding="utf-8")
        obligatoires = set()
        for nom in contrats:
            fichier = root / WEB / "contract_samples" / nom
            if fichier.is_file():
                obligatoires |= cles_obligatoires(json.loads(fichier.read_text(encoding="utf-8")))
        for cle in obligatoires:
            if not cle_relayee(cle, source):
                sortie.add((proxy, cle))
    return sortie


def verifier(root: Path = ROOT, proxys: dict | None = None,
             dette: dict | None = None) -> list:
    dette = DETTE_CONNUE if dette is None else dette
    trouves = manques(root, proxys)
    erreurs = []
    for proxy, cle in sorted(trouves - set(dette)):
        erreurs.append(f"{proxy} : la clé obligatoire `{cle}` du contrat partagé n'est "
                       "pas relayée au backend (le serveur répondrait 400).")
    for proxy, cle in sorted(set(dette) - trouves):
        erreurs.append(f"entrée MORTE de DETTE_CONNUE : {proxy} / {cle} est désormais "
                       "relayée — retirez-la.")
    return erreurs


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    erreurs = verifier()
    if erreurs:
        print("check_proxy_relaie_contrat: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_proxy_relaie_contrat: OK — {len(PROXYS)} proxy(s), "
          f"{len(DETTE_CONNUE)} dette(s) connue(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
