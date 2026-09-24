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
   - `format_version` est l'ENTIER 2 (CALX370 : `postes_pertes` et
     `variantes` rejoignent le fichier, qui se RÉIMPORTE), jamais une date ;
   - les quatorze clés sont TOUJOURS présentes, même sur un calepinage vide ;
   - `provenance` (CALX314) est une liste {libelle, valeur}, sans valeur vide ;
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

// CALX314 — `provenance` : la composition partagée avec le XLSX et le DXF.
const CLES = [
  'format_version', 'produit_le', 'calepinage', 'site', 'equipements',
  'roof_layout', 'layout_hash', 'version_moteur', 'resultat', 'pertes',
  'avertissements', 'provenance',
  // CALX370 — format 2 : ce que la réimportation restitue.
  'postes_pertes', 'variantes',
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

test('format_version est l’entier 2, sur les deux exemples', () => {
  for (const cle of ['exemple', 'exemple_vide']) {
    assert.equal(CONTRAT[cle].format_version, 2)
    assert.ok(Number.isInteger(CONTRAT[cle].format_version))
    assert.match(CONTRAT[cle].produit_le, /Z$/)
  }
})

test('la provenance est une liste {libelle, valeur}, jamais une valeur vide', () => {
  for (const cle of ['exemple', 'exemple_vide']) {
    const lignes = CONTRAT[cle].provenance
    assert.ok(Array.isArray(lignes) && lignes.length > 0)
    for (const ligne of lignes) {
      assert.deepEqual(Object.keys(ligne).sort(), ['libelle', 'valeur'])
      assert.ok(String(ligne.valeur).trim().length > 0, ligne.libelle)
    }
  }
  const empreinte = CONTRAT.exemple_vide.provenance
    .find((ligne) => ligne.libelle === 'Empreinte du calepinage')
  assert.equal(empreinte.valeur, 'non calculée')
})

test('les quatorze clés sont toujours présentes, même vides', () => {
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

test('CALX370 — une variante porte nom/retenue/roof_layout/layout_hash/resultat', () => {
  const cles = ['layout_hash', 'nom', 'resultat', 'retenue', 'roof_layout']
  for (const variante of CONTRAT.exemple.variantes) {
    assert.deepEqual(Object.keys(variante).sort(), cles)
    assert.equal(typeof variante.retenue, 'boolean')
  }
  assert.equal(CONTRAT.exemple.variantes.filter((v) => v.retenue).length, 1)
  assert.deepEqual(CONTRAT.exemple_vide.variantes, [])
  assert.deepEqual(CONTRAT.exemple_vide.postes_pertes, [])
})
