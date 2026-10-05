import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* ============================================================================
   SPL292 — le lecteur de SOURCE multi-fichiers de `calepinageApi.js`.
   ----------------------------------------------------------------------------
   La façade `api/calepinageApi.js` s'éclate en fragments (`api/calepinage/
   <theme>.js`, `export const <theme> = { … }`, corps d'objet à 4 espaces) que
   la façade compose par une ligne `    ...<theme>,` à la position exacte de la
   plage déplacée. Les gardes qui lisent le SOURCE (`calepinageApi.test.mjs`,
   `calepinageApi.usage.test.mjs`) passeraient à vide sur la façade seule :
   elles lisent donc CE texte recomposé.

   `lireSourceCalepinageApi()` rend le texte de la façade où chaque ligne
   `    ...<fragment>,` est remplacée par le CORPS du fragment correspondant
   (les lignes entre `export const <fragment> = {` et le `}` de colonne 0),
   suivi de `_base.js` — donc, pour un fragment au corps indenté comme
   l'original, EXACTEMENT le texte d'avant le déplacement. Une ligne de spread
   dont le fragment est introuvable (ex. `...crud('calepinages'),`) reste telle
   quelle. Lecture d'OCTETS décodés UTF-8, fins de ligne conservées.
   ========================================================================== */

const ICI = dirname(fileURLToPath(import.meta.url))
const DOSSIER_API_DEFAUT = dirname(ICI) // frontend/src/api

const RE_SPREAD = /^ {4}\.\.\.([A-Za-z_$][\w$]*),\s*$/
const RE_IMPORT_FRAGMENT = /^import\s*\{([^}]*)\}\s*from\s*'\.\/calepinage\/([\w-]+)'/

/** Les fichiers de fragment déclarés par les imports de la façade. */
function fragmentsImportes(lignes) {
  const out = new Map()
  for (const ligne of lignes) {
    const m = RE_IMPORT_FRAGMENT.exec(ligne)
    if (!m) continue
    for (const nom of m[1].split(',').map((s) => s.trim()).filter(Boolean)) {
      out.set(nom, `${m[2]}.js`)
    }
  }
  return out
}

/** Les lignes de corps de `export const <nom> = { … }`, ou null. */
export function corpsDuFragment(texte, nom) {
  const lignes = texte.split('\n')
  const ouverture = new RegExp(`^export const ${nom.replace(/\$/g, '\\$')} = \\{\\s*$`)
  const debut = lignes.findIndex((l) => ouverture.test(l))
  if (debut < 0) return null
  const fin = lignes.findIndex((l, i) => i > debut && /^\}\s*$/.test(l))
  if (fin < 0) return null
  return lignes.slice(debut + 1, fin)
}

export function lireSourceCalepinageApi(dossierApi = DOSSIER_API_DEFAUT) {
  const facade = readFileSync(join(dossierApi, 'calepinageApi.js'), 'utf8')
  const lignes = facade.split('\n')
  const fichiers = fragmentsImportes(lignes)
  const sortie = []
  for (const ligne of lignes) {
    const m = RE_SPREAD.exec(ligne)
    const fichier = m && (fichiers.get(m[1]) ?? `${m[1]}.js`)
    const chemin = fichier && join(dossierApi, 'calepinage', fichier)
    const corps = chemin && existsSync(chemin)
      ? corpsDuFragment(readFileSync(chemin, 'utf8'), m[1])
      : null
    if (corps) sortie.push(...corps)
    else sortie.push(ligne)
  }
  const base = join(dossierApi, 'calepinage', '_base.js')
  const suffixe = existsSync(base) ? `\n${readFileSync(base, 'utf8')}` : ''
  return sortie.join('\n') + suffixe
}

export default lireSourceCalepinageApi
