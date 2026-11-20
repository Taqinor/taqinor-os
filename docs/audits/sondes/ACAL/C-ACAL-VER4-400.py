# flake8: noqa  (sonde HÔTE du vérifie ACAL du 20/11/2026 — sans Django, sans base, sans Docker ; exige `node` ≥ 22.6)
"""C-ACAL-VER4-400 — la section « zones » (ACAL366) écrase les retouches NON enregistrées de pente/azimut de TOUS les pans.

`SaisiePente.jsx` (enregistrement de pente ET `decider` des suggestions IGN) et `atelier/PanneauReleve.jsx` poussent
`roof_layout.zones` RENDU par le serveur — tous les pans, à leurs valeurs STOCKÉES — dans
`builderApi.appliquerSection('zones', …)`. `hydratation.ts::appliquerZonesSection` pose `pitchDeg`, `facingAzimuthDeg`,
`facingManual` de CHAQUE zone rendue sur le pan vivant (et, pour le pan actif, sur `ctx.pitchDeg`/`ctx.facingAzimuthDeg`)
sans les comparer au document relu : une pente retouchée à l'écran et pas encore enregistrée (puce 30°, curseur) retombe
sur la valeur stockée dès qu'un AUTRE pan reçoit sa pente, ou qu'une suggestion IGN est décidée (`SaisiePente.jsx` dit
pourtant « sa scène n'est pas touchée »). L'« Enregistrer le calepinage » suivant écrit l'ancienne valeur.

Exécute la VRAIE fonction `appliquerZonesSection` (+ `copie`) extraite du source TypeScript, lancée par `node` (types
effacés nativement). Rejeu complémentaire (vitest, boot devis réel, copie hors dépôt) : puce 30° sur le pan actif puis
`appliquerSection('zones', zones stockées + pitchSuggestion)` ⇒ `serializeLayout().zones[0].pitchDeg` = 15 (attendu 30)."""
SONDE = {"constat": "C-ACAL-VER4-400", "sha": "5a77c93d99",
         "attendu": "une section 'zones' ne change que les champs que le serveur a réellement changés ; "
                    "les retouches non enregistrées des autres pans (et du pan actif) restent"}
import json, pathlib, re, shutil, subprocess, tempfile

RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "apps/web").is_dir(): RACINE = pathlib.Path.cwd()
SOURCE = RACINE / "apps/web/src/scripts/roofPro11/hydratation.ts"


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
// Pan z1 ACTIF : stocké 15°, retouché à l'écran à 30° (non enregistré) — l'état vivant du pan actif est ctx.pitchDeg.
// Pan z2 : stocké 20°, retouché à 40° (non enregistré) — l'enregistrement de pan EST l'état vivant.
const ctx = {
  activeAreaId: 'z1', pitchDeg: 30, facingAzimuthDeg: 180, facingManual: false,
  areas: [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180 }, { id: 'z2', pitchDeg: 40, facingAzimuthDeg: 90 }],
  documentRelu: { zones: [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180 }, { id: 'z2', pitchDeg: 20, facingAzimuthDeg: 90 }] },
};
// (a) decider une suggestion IGN sur z1 : le serveur rend les zones STOCKÉES + la décision.
// (b) puis l'onglet Pente enregistre 35° sur z2 : z1 rendu à 15° stocké.
appliquerZonesSection(ctx, [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180, pitchSuggestion: { degres: 34, decision: 'refusee' } },
                            { id: 'z2', pitchDeg: 20, facingAzimuthDeg: 90 }]);
const apresDecision = { actif: ctx.pitchDeg, z2: ctx.areas[1].pitchDeg };
ctx.pitchDeg = 30; ctx.areas[1].pitchDeg = 40;
appliquerZonesSection(ctx, [{ id: 'z1', pitchDeg: 15, facingAzimuthDeg: 180 },
                            { id: 'z2', pitchDeg: 35, facingAzimuthDeg: 90, pitchSource: { mode: 'degres', degres: 35 } }]);
console.log(JSON.stringify({ apresDecision, apresPenteAutrePan: { actif: ctx.pitchDeg, z2: ctx.areas[1].pitchDeg } }));
"""


def sonde(ctx=None):
    texte = SOURCE.read_text(encoding="utf-8")
    fonction = _extraire(texte, "function appliquerZonesSection(")
    copie = _extraire(texte, "function copie<T>(")
    filtre = bool(re.search(r"documentRelu|relues", fonction.split("for (const z of zones)")[1].split("if (actif)")[0]))
    node = shutil.which("node")
    if not node:
        return {"repro": None, "motif": "node absent : sonde non jouable", "compare_au_relu_avant_ecriture": filtre}
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "sonde_ver4_400.mts"
        f.write_text("type Ctx = any;\n" + copie + "\n" + fonction + "\n" + HARNAIS, encoding="utf-8")
        r = subprocess.run([node, str(f)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return {"repro": None, "motif": "node en erreur", "stderr": r.stderr[-800:]}
    sortie = json.loads(r.stdout.strip().splitlines()[-1])
    print(json.dumps(sortie, ensure_ascii=False))
    perdu = sortie["apresDecision"] != {"actif": 30, "z2": 40} or sortie["apresPenteAutrePan"]["actif"] != 30
    return {"repro": perdu, "sortie": sortie, "compare_au_relu_avant_ecriture": filtre}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
