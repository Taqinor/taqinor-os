import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// VAO32 — verrouille le contrat de `veilleAoApi.js` par lecture de SOURCE (même
// patron que `aoApi.test.mjs`) : `./axios` porte des effets de bord
// (baseURL/intercepteurs) qu'on ne veut pas déclencher pour un simple test de
// contrat URL/forme. Zéro appel réseau, zéro mock du graphe ESM.
//
// La garde « chaque chemin existe côté serveur » n'est PAS dupliquée ici : elle
// vit désormais dans `scripts/check_api_contract.py`, qui résout l'inventaire
// RÉEL des routes depuis `erp_agentique/urls.py` (routeurs + `@action` +
// `path()`) et tourne à chaque commit. Le backend de la veille (VAO21-VAO31)
// sert tous les chemins ci-dessous, `chargerDetail` excepté — retiré parce que
// le collecteur portail reste gaté (voir le test dédié plus bas).

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'veilleAoApi.js'), 'utf8')

function sansCommentaires(texte) {
  return texte.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

test('veilleAoApi utilise la factory partagée (ARC44), jamais un axios.get direct au niveau module', () => {
  assert.match(src, /import \{ makeResourceFactory \} from '\.\/resource'/)
  assert.match(src, /const crud = makeResourceFactory\(api, '\/veille_ao'\)/)
  assert.doesNotMatch(sansCommentaires(src), /axios\.get/)
})

test('les ressources CRUD du groupe VAO7-VAO29 sont toutes déclarées', () => {
  const resources = ['avis', 'sources', 'motsCles', 'reglesExclusion', 'acheteursCibles', 'executions']
  for (const key of resources) {
    assert.match(src, new RegExp(`\\b${key}:`), `ressource manquante : ${key}`)
  }
})

test('VAO23 — le déclenchement manuel appelle EXACTEMENT POST /veille_ao/collecter/ (chemin littéral du texte de tâche)', () => {
  assert.match(src, /declencher:\s*\(\)\s*=>\s*api\.post\('\/veille_ao\/collecter\/'\)/)
})

test('VAO14/VAO34 — retenir/ignorer sont des ACTIONS de service réel, jamais un PATCH générique', () => {
  const bloc = src.slice(src.indexOf('avis: {'), src.indexOf('\n  },', src.indexOf('avis: {')))
  assert.match(bloc, /retenir:\s*\(id,\s*data\)\s*=>\s*api\.post\(`\/veille_ao\/avis\/\$\{id\}\/retenir\/`,\s*data\)/)
  assert.match(bloc, /ignorer:\s*\(id,\s*data\)\s*=>\s*api\.post\(`\/veille_ao\/avis\/\$\{id\}\/ignorer\/`,\s*data\)/)
  assert.doesNotMatch(bloc, /\.\.\.crud\('avis'\)[\s\S]*update:.*retenir/)
})

test('VAO18 — `chargerDetail` est ABSENT tant que le collecteur portail est gaté (VAO2)', () => {
  // L'enrichissement du détail appartient au collecteur portail
  // (VAO15-VAO20), qui attend l'action fondateur VAO2 : ouvrir le compte
  // entreprise du portail et vérifier si le flux RSS authentifié existe — si
  // oui, le collecteur n'est jamais construit. Publier ici un appel vers une
  // route que le backend ne sert pas est le défaut exact qui a tué l'écran
  // « AO > Bibliothèque » en production le 03/08/2026. Ce test garde la place
  // au chaud : il redeviendra une assertion de PRÉSENCE avec le collecteur.
  assert.doesNotMatch(sansCommentaires(src), /chargerDetail/)
  assert.doesNotMatch(sansCommentaires(src), /charger-detail/)
})

test('sante() est un appel agrégé UNIQUE (VAO24/VAO35/VAO37), jamais un axios.get inline dans un écran', () => {
  assert.match(src, /sante:\s*\(\)\s*=>\s*api\.get\('\/veille_ao\/sante\/'\)/)
})

test('export default veilleAoApi', () => {
  assert.match(src, /export default veilleAoApi/)
})
