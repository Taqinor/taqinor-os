// ACAL727 — la rampe imprimée sous la carte de chaleur du rapport d'ombrage
// (serveur : `rapport_ombrage.STOPS_LEGENDE`) doit rester celle de
// `solarAccessColorRGB` (apps/web/src/lib/shadingEngine.ts). Source partagée :
// `contract_samples/legende_acces_solaire.json`, relue ici comme côté serveur.
// Mutant : changer le jaune de la fonction ⇒ ce test rougit.
//   node --test src/features/calepinage/legendeAccesSolaire.contrat.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const lire = (relatif) => readFileSync(fileURLToPath(new URL(relatif, import.meta.url)), 'utf8')

const CONTRAT = JSON.parse(lire(
  '../../../../backend/django_core/apps/calepinage/contract_samples/legende_acces_solaire.json'))
const SOURCE = lire('../../../../apps/web/src/lib/shadingEngine.ts')

// Le fichier TypeScript importe d'autres modules sans extension : on en
// extrait la seule fonction PURE (signature retirée) plutôt que de l'importer.
// Extraction par appariement d'accolades, indifférente aux fins de ligne.
function solarAccessColorRGB() {
  const source = SOURCE.replace(/\r\n/g, '\n')
  const signature = /export function solarAccessColorRGB\s*\(access: number\)\s*:\s*\{[^}]*\}\s*\{/.exec(source)
  assert.ok(signature, 'solarAccessColorRGB introuvable dans shadingEngine.ts')
  const debut = signature.index + signature[0].length
  let profondeur = 1
  let i = debut
  for (; i < source.length && profondeur > 0; i += 1) {
    if (source[i] === '{') profondeur += 1
    else if (source[i] === '}') profondeur -= 1
  }
  assert.equal(profondeur, 0, 'accolade fermante de solarAccessColorRGB introuvable')
  return new Function('access', source.slice(debut, i - 1))
}

test('les trois stops du contrat sont ceux de solarAccessColorRGB', () => {
  const couleur = solarAccessColorRGB()
  assert.equal(CONTRAT.exemple.stops.length, 3)
  for (const { acces, rgb } of CONTRAT.exemple.stops) {
    const { r, g, b } = couleur(acces)
    assert.deepEqual([r, g, b], rgb, `accès ${acces}`)
  }
})
