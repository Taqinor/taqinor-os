// ERR-QAH-VISITES-PHOTOS-CAMERA-BLOQUEE (30/09/2026) — l'en-tête
// Permissions-Policy servi par nginx pour TOUT l'ERP
// (backend/nginx/security-headers.conf.template) ne doit JAMAIS interdire
// caméra / micro / géolocalisation à l'origine de l'appli elle-même : avec
// `camera=()`, getUserMedia (CameraCapture.jsx), le géomarquage des photos
// (navigator.geolocation) et la dictée vocale (MicDicteeButton.jsx) étaient
// refusés — en production aussi — et aucune visite technique (5 photos
// obligatoires) ne pouvait plus être terminée. La forme attendue est
// `(self)` : l'appli y a droit, une iframe tierce jamais (donc pas `*`).
// Pas de rendu : on lit la source, comme ios-polish.test.mjs.
//
// Exécuté en CI : node --test src/features/pwa/permissions-policy.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
// src/features/pwa → ../../../../ = racine du dépôt
const gabarit = readFileSync(
  join(here, '..', '..', '..', '..', 'backend', 'nginx', 'security-headers.conf.template'),
  'utf8',
)

// Directives ACTIVES uniquement (les lignes commentées `#` n'en font pas partie).
const lignes = gabarit
  .split(/\r?\n/)
  .filter((ligne) => /^\s*add_header\s+Permissions-Policy\s/i.test(ligne))

// « camera=(self), microphone=(self) » → { camera: 'self', microphone: 'self' }
function directives(valeur) {
  const out = {}
  for (const morceau of valeur.split(',')) {
    const m = morceau.trim().match(/^([a-z-]+)=\((.*)\)$/i)
    if (m) out[m[1].toLowerCase()] = m[2].trim()
  }
  return out
}

function valeurPolitique() {
  assert.equal(lignes.length, 1,
    'le gabarit doit poser UN seul en-tête Permissions-Policy (hors commentaires)')
  const m = lignes[0].match(/Permissions-Policy\s+"([^"]*)"/i)
  assert.ok(m, 'la valeur de Permissions-Policy doit être entre guillemets')
  return m[1]
}

test('caméra, micro et géolocalisation : autorisés pour la SEULE origine de l’appli', () => {
  const d = directives(valeurPolitique())
  for (const fonctionnalite of ['camera', 'microphone', 'geolocation']) {
    assert.equal(d[fonctionnalite], 'self',
      `${fonctionnalite} doit valoir (self) — « () » bloque la fonction pour l’appli elle-même`
      + ' (visites terrain impossibles à terminer), « * » l’ouvre aux iframes tierces')
  }
})

test('jamais de joker « * » : aucune fonctionnalité ouverte aux iframes tierces', () => {
  const valeur = valeurPolitique()
  assert.ok(!valeur.includes('*'), `pas de « * » dans Permissions-Policy : ${valeur}`)
})
