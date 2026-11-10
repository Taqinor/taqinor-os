"""Le nocturne release-verify lance vitest avant astro build (web-full) et le spec NTI18N47 ne clique qu'une fois face à AGNR73."""
SONDE = {"constat": "C-ADCG-036", "sha": "ce4e5fc4f",
         "attendu": "web-full : index(npm test) < index(npm run build) ; spec : 1 clic « Créer le devis » + retour anticipé AGNR73"}

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[4]
RV = RACINE / ".github/workflows/release-verify.yml"
SPEC = RACINE / "frontend/e2e/i18n-quote-journey.spec.js"
HOOK = RACINE / "frontend/src/features/ventes/quote/hooks/usePersistanceDevis.js"
AIDE = RACINE / "apps/web/tests/builtHtmlHelper.ts"


def _index(steps, motif):
    return next((i for i, s in enumerate(steps) if re.search(motif, s.get("run") or "")), None)


def sonde(ctx=None):
    steps = yaml.safe_load(RV.read_text(encoding="utf-8"))["jobs"]["web-full"]["steps"]
    i_test, i_build = _index(steps, r"^\s*npm test\b"), _index(steps, r"^\s*npm run build\b")
    lit_dist = AIDE.exists() and "dist/client" in AIDE.read_text(encoding="utf-8")
    ordre_faux = i_test is not None and i_build is not None and i_test < i_build and lit_dist
    spec = SPEC.read_text(encoding="utf-8")
    clics = len(re.findall(r"#gen-form'\)\.getByRole\('button', \{ name: /Créer le devis/ \}\)\.click\(\)", spec))
    hook = HOOK.read_text(encoding="utf-8")
    retour_agnr73 = bool(re.search(r"lignesEcarteesConfirmeRef\.current !== signature\)\s*\{[^}]*return", hook))
    e2e_faux = clics == 1 and retour_agnr73
    return {"repro": ordre_faux or e2e_faux,
            "observe": f"web-full : npm test à l'étape {i_test}, npm run build à l'étape {i_build}, "
                       f"tests lisant dist/client={lit_dist} ; spec NTI18N47 : {clics} clic(s) sur "
                       f"« Créer le devis », retour anticipé AGNR73 au 1er clic={retour_agnr73}"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
