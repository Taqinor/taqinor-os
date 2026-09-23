import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

/* ============================================================================
   CALX312 — l'export JSON « projet + résultats », vu depuis le NAVIGATEUR.
   ----------------------------------------------------------------------------
   CONTRAT PARTAGÉ (PACT10) : ce test IMPORTE l'exemple committé
   `contract_samples/export_projet.json` (CALX293) — celui que le test backend
   `test_calx312_export_projet.py` affirme contre le document RÉELLEMENT
   servi — au lieu d'écrire un payload à la main. Un tiers (ou un écran) qui
   lit ce fichier peut donc compter sur ce qui est vérifié ici :
   - `format_version` est l'ENTIER 1, jamais une date ;
   - les onze clés sont TOUJOURS présentes, même sur un calepinage vide ;
   - un calepinage non simulé exporte `resultat: null` et `pertes: []` ;
   - aucune clé de la famille prix_* / cout_* / marge_* n'y figure (D5) ;
   - la route servie existe côté serveur (`url_path='export-projet.json'`).
   Lecture de SOURCES uniquement : zéro réseau, zéro dépendance.
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))

function racineDepot() {
  let dossier = resolve(here)
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du depot introuvable depuis ${here}`)
}

const APP = join(racineDepot(), 'backend', 'django_core', 'apps', 'calepinage')
const CONTRAT = JSON.parse(
  readFileSync(join(APP, 'contract_samples', 'export_projet.json'), 'utf8'),
)

const CLES = [
  'format_version', 'produit_le', 'calepinage', 'site', 'equipements',
  'roof_layout', 'layout_hash', 'version_moteur', 'resultat', 'pertes',
  'avertissements',
]

function clesDeMontant(noeud, chemin = '<racine>') {
  const trouvees = []
  if (Array.isArray(noeud)) {
    noeud.forEach((item, rang) => {
      trouvees.push(...clesDeMontant(item, `${chemin}[${rang}]`))
    })
  } else if (noeud && typeof noeud === 'object') {
    for (const [cle, valeur] of Object.entries(noeud)) {
      if (/^(prix|cout|marge)(_|$)/i.test(cle)) trouvees.push(`${chemin}.${cle}`)
      trouvees.push(...clesDeMontant(valeur, `${chemin}.${cle}`))
    }
  }
  return trouvees
}

test("la route de l'export est celle que le serveur déclare", () => {
  assert.equal(
    CONTRAT.endpoint,
    'GET /api/django/calepinage/calepinages/<int:pk>/export-projet.json/',
  )
  const vues = readFileSync(join(APP, 'views', 'documents.py'), 'utf8')
  assert.ok(vues.includes("url_path='export-projet.json'"),
    "aucune @action ne sert url_path='export-projet.json'")
})

test('format_version est l’entier 1, sur les deux exemples', () => {
  for (const cle of ['exemple', 'exemple_vide']) {
    assert.equal(CONTRAT[cle].format_version, 1)
    assert.ok(Number.isInteger(CONTRAT[cle].format_version))
    assert.match(CONTRAT[cle].produit_le, /Z$/)
  }
})

test('les onze clés sont toujours présentes, même vides', () => {
  assert.deepEqual(Object.keys(CONTRAT.exemple).sort(), [...CLES].sort())
  assert.deepEqual(Object.keys(CONTRAT.exemple_vide).sort(), [...CLES].sort())
})

test('un calepinage non simulé : resultat null, pertes vides, motif dit', () => {
  const vide = CONTRAT.exemple_vide
  assert.equal(vide.resultat, null)
  assert.deepEqual(vide.pertes, [])
  assert.ok(vide.avertissements.length > 0)
  for (const cle of ['altitude_m', 'fuseau']) {
    assert.ok(cle in vide.site)
    assert.equal(vide.site[cle], null)
  }
})

test('chaque poste de pertes porte poste/libelle/pct/source', () => {
  for (const poste of CONTRAT.exemple.pertes) {
    assert.deepEqual(Object.keys(poste).sort(),
      ['libelle', 'pct', 'poste', 'source'])
  }
})

test('aucune clé de montant (prix_* / cout_* / marge_*) — D5', () => {
  assert.deepEqual(clesDeMontant(CONTRAT.exemple), [])
  assert.deepEqual(clesDeMontant(CONTRAT.exemple_vide), [])
  assert.deepEqual(clesDeMontant({ a: { prix_achat: 1 } }), ['<racine>.a.prix_achat'])
})
