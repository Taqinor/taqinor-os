# flake8: noqa  (sonde HÔTE du vérifie ACAL du 20/11/2026 — sans Django, sans base, sans Docker ; exige `node` ≥ 22.6)
"""C-ACAL-VER4-401 — section « zones » (ACAL366) sur un pan ABSENT du document relu : `facingAzimuthSource`,
`facingAzimuthPrecisionDeg` et la décision `pitchSuggestion` ne sont posés NULLE PART, l'enregistrement complet suivant
(remplacement entier côté serveur, `services/layout.py::enregistrer_layout`) les efface.

La tâche place `facingAzimuthSource` / `facingAzimuthPrecisionDeg` « sur l'enregistrement de pan de `ctx.areas` » et
SEULE `pitchSuggestion` dans `ctx.documentRelu.zones`. `hydratation.ts::appliquerZonesSection` range les trois dans
`documentRelu.zones[pan]` et SEULEMENT si ce pan y figure (`for (const cle of relue ? [...] : [])`). Or `documentRelu`
n'est posé qu'au boot (`appliquerHydratationAuCtx`, `h.documentRelu`) et jamais rafraîchi après « Enregistrer » : tout pan
tracé dans la session en est absent. `prefill.ts::serializeLayout` n'émet pas ces clés depuis le pan (elles ne sont pas
dans `CLES_PAN_ATELIER` ; seule la réconciliation les recopie du relu).

Exécute la VRAIE fonction `appliquerZonesSection` (+ `copie`) extraite du source TypeScript, lancée par `node`.
Rejeu complémentaire (vitest, boot devis réel, copie hors dépôt) : calepinage rouvert sans pan, pan tracé dans la
session, `appliquerSection('zones', [pan + facingAzimuthSource 'releve', précision 5, pitchSuggestion])` ⇒
`serializeLayout().zones[0]` = `{facingAzimuthDeg: 200}` sans source, précision ni décision."""
SONDE = {"constat": "C-ACAL-VER4-401", "sha": "5a77c93d99",
         "attendu": "les champs CHAMPS_SECTION_ZONE rendus par le serveur sont gardés pour tout pan vivant, "
                    "qu'il figure ou non dans le document relu au boot"}
import json, pathlib, shutil, subprocess, tempfile

RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "apps/web").is_dir(): RACINE = pathlib.Path.cwd()
SOURCE = RACINE / "apps/web/src/scripts/roofPro11/hydratation.ts"
PREFILL = RACINE / "apps/web/src/scripts/roofPro11/prefill.ts"


def _extraire(texte, debut):
    i = texte.index(debut)
    j = texte.index("{", texte.index(")", i))
    prof = 0
    for k in range(j, len(texte)):
        prof += {"{": 1, "}": -1}.get(texte[k], 0)
        if prof == 0:
            return texte[i:k + 1]
    raise ValueError(debut)


HARNAIS = r"""
// Calepinage rouvert avec z1 ; z2 tracé dans la session puis enregistré (absent du document relu au boot).
const ctx = {
  activeAreaId: 'z1', pitchDeg: 15, facingAzimuthDeg: 180, facingManual: false,
  areas: [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180 }, { id: 'z2', pitchDeg: 20, facingAzimuthDeg: 90 }],
  documentRelu: { zones: [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180 }] },
};
appliquerZonesSection(ctx, [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180 },
  { id: 'z2', pitchDeg: 20, facingAzimuthDeg: 200, facingManual: true, facingAzimuthSource: 'releve',
    facingAzimuthPrecisionDeg: 5, pitchSuggestion: { degres: 34, decision: 'refusee' } }]);
const pan = ctx.areas[1];
const relu = (ctx.documentRelu.zones.find((z) => z.id === 'z2')) || null;
console.log(JSON.stringify({ pan, relu }));
"""


def sonde(ctx=None):
    texte = SOURCE.read_text(encoding="utf-8")
    fonction = _extraire(texte, "function appliquerZonesSection(")
    copie = _extraire(texte, "function copie<T>(")
    prefill = PREFILL.read_text(encoding="utf-8")
    cles_pan = prefill[prefill.index("const CLES_PAN_ATELIER"):].split("]);")[0]
    emis_depuis_pan = "facingAzimuthSource" in cles_pan
    node = shutil.which("node")
    if not node:
        return {"repro": None, "motif": "node absent : sonde non jouable", "serialiseur_emet_depuis_le_pan": emis_depuis_pan}
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "sonde_ver4_401.mts"
        f.write_text("type Ctx = any;\n" + copie + "\n" + fonction + "\n" + HARNAIS, encoding="utf-8")
        r = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return {"repro": None, "motif": "node en erreur", "stderr": r.stderr[-800:]}
    sortie = json.loads(r.stdout.strip().splitlines()[-1])
    print(json.dumps(sortie, ensure_ascii=False))
    ou = {cle: ("pan" if cle in sortie["pan"] else "relu" if (sortie["relu"] or {}).get(cle) is not None else "NULLE PART")
          for cle in ("facingAzimuthSource", "facingAzimuthPrecisionDeg", "pitchSuggestion")}
    perdu = any(v == "NULLE PART" for v in ou.values()) or (
        any(v == "pan" for v in ou.values()) and not emis_depuis_pan)
    return {"repro": perdu, "rangement": ou, "serialiseur_emet_depuis_le_pan": emis_depuis_pan, "sortie": sortie}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
