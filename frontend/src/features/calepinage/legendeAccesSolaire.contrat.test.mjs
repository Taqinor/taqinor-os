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
function solarAccessColorRGB() {
  const debut = SOURCE.indexOf('export function solarAccessColorRGB')
  assert.ok(debut >= 0, 'solarAccessColorRGB introuvable dans shadingEngine.ts')
  const fin = SOURCE.indexOf('\n}\n', debut)
  const bloc = SOURCE.slice(debut, fin)
  const corps = bloc.slice(bloc.indexOf('{ r: number; g: number; b: number } {') + 36)
  return new Function('access', corps)
}

test('les trois stops du contrat sont ceux de solarAccessColorRGB', () => {
  const couleur = solarAccessColorRGB()
  assert.equal(CONTRAT.exemple.stops.length, 3)
  for (const { acces, rgb } of CONTRAT.exemple.stops) {
    const { r, g, b } = couleur(acces)
    assert.deepEqual([r, g, b], rgb, `accès ${acces}`)
  }
})
