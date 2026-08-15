// WIR183 — six actions Facture COMPLÈTES côté serveur qui n'avaient aucun
// point d'entrée client : remettre-brouillon, abandonner-solde, retour-client,
// facturer-pénalités (menu de ligne) + consolider et encaissement-groupe
// (actions groupées / menu Exporter).
//
// Assertions au niveau SOURCE (même patron que FactureListFE_SCA41.test.mjs) :
// ce worktree n'a pas de node_modules, FactureList.jsx importe react-redux/ui
// et n'est pas exécutable en isolation.
//   node --test src/pages/ventes/FactureListWIR183Actions.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const LIST = readFileSync(join(HERE, 'FactureList.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')

// ── Les six wrappers pointent sur le chemin serveur EXACT ────────────────────

const WRAPPERS = [
  ['remettreBrouillonFacture', '/ventes/factures/${id}/remettre-brouillon/'],
  ['abandonnerSoldeFacture', '/ventes/factures/${id}/abandonner-solde/'],
  ['retourClientFacture', '/ventes/factures/${id}/retour-client/'],
  ['facturerPenalitesFacture', '/ventes/factures/${id}/facturer-penalites/'],
  ['consoliderFactures', '/ventes/factures/consolider/'],
  ['encaissementGroupeFactures', '/ventes/factures/encaissement-groupe/'],
]

for (const [nom, chemin] of WRAPPERS) {
  test(`WIR183 : ventesApi.${nom} appelle ${chemin}`, () => {
    assert.match(API, new RegExp(`${nom}:`), `${nom} doit exister`)
    assert.ok(API.includes(chemin), `${nom} doit poster sur ${chemin}`)
  })
}

test('WIR183 : abandonner-solde envoie bien le motif OBLIGATOIRE du serveur', () => {
  assert.match(
    API,
    /abandonnerSoldeFacture: \(id, motif\) =>\s*\n?\s*api\.post\([^)]*abandonner-solde\/`, \{ motif \}\)/,
  )
})

test('WIR183 : consolider envoie devis_ids (jamais des ids de factures)', () => {
  assert.match(API, /consoliderFactures: \(devisIds\) =>[\s\S]{0,120}\{ devis_ids: devisIds \}/)
})

// ── Les quatre actions de LIGNE sont réellement déclenchables ────────────────

const ITEMS_LIGNE = [
  ['remettre-brouillon', 'handleRemettreBrouillon'],
  ['abandonner-solde', 'openAbandonSolde'],
  ['retour-client', 'openRetourClient'],
  ['facturer-penalites', 'handleFacturerPenalites'],
]

for (const [testid, handler] of ITEMS_LIGNE) {
  test(`WIR183 : l'item de menu « ${testid} » appelle ${handler}`, () => {
    const idx = LIST.indexOf(`data-testid="${testid}"`)
    assert.notEqual(idx, -1, `l'item ${testid} doit exister dans le menu de ligne`)
    const bloc = LIST.slice(idx, idx + 400)
    assert.match(bloc, new RegExp(`${handler}\\(f\\)`))
  })
}

test('WIR183 : les six actions sont gatées au palier responsable/admin (garde serveur)', () => {
  assert.match(
    LIST,
    /const isResponsable = \['responsable', 'admin'\]\.includes\(/,
  )
  for (const [testid] of ITEMS_LIGNE) {
    const idx = LIST.indexOf(`data-testid="${testid}"`)
    // L'item est rendu dans une garde `isResponsable && …` ouverte juste avant.
    const avant = LIST.slice(Math.max(0, idx - 300), idx)
    assert.match(avant, /isResponsable &&/, `${testid} doit être gaté isResponsable`)
  }
})

test('WIR183 : les handlers/état sont bien transmis à la ligne via rowCtx', () => {
  // Deux occurrences attendues : la destructuration dans FactureRow ET le sac
  // rowCtx construit par le parent — sinon la ligne rendrait un handler
  // `undefined` sans que rien ne rougisse.
  const occurrences = LIST.split('handleRemettreBrouillon, openAbandonSolde, openRetourClient').length - 1
  assert.equal(occurrences, 2)
})

// ── Cas d'erreur : le message FR du serveur est affiché TEL QUEL ─────────────

test('WIR183 : runWirAction affiche le `detail` serveur sans le réécrire', () => {
  const debut = LIST.indexOf('const runWirAction')
  assert.notEqual(debut, -1)
  const bloc = LIST.slice(debut, debut + 900)
  assert.match(bloc, /toast\.error\(err\?\.response\?\.data\?\.detail \?\? "Action impossible\."\)/)
  // Succès : la liste est rechargée depuis le serveur (jamais un état local
  // bricolé — l'effet doit être visible après rechargement).
  assert.match(bloc, /dispatch\(fetchFactures\(\)\)/)
})

test('WIR183 : les quatre handlers passent TOUS par runWirAction', () => {
  for (const nom of ['handleRemettreBrouillon', 'handleFacturerPenalites',
    'confirmerAbandon', 'confirmerRetour', 'confirmerEncaissementGroupe',
    'confirmerConsolidation']) {
    const debut = LIST.indexOf(`const ${nom}`)
    assert.notEqual(debut, -1, `${nom} doit exister`)
    assert.match(LIST.slice(debut, debut + 700), /runWirAction\(/,
      `${nom} doit router son erreur par runWirAction`)
  }
})

// ── Actions GROUPÉES ────────────────────────────────────────────────────────

test('WIR183 : « Encaissement groupé » vit dans la barre de sélection', () => {
  const idx = LIST.indexOf('data-testid="encaissement-groupe"')
  assert.notEqual(idx, -1)
  assert.match(LIST.slice(idx, idx + 300), /setEncaissementOpen\(true\)/)
})

test('WIR183 : l\'encaissement groupé poste la sélection courante + la répartition', () => {
  const debut = LIST.indexOf('const confirmerEncaissementGroupe')
  const bloc = LIST.slice(debut, debut + 800)
  assert.match(bloc, /factures: selectedIds/)
  assert.match(bloc, /montant: encaissement\.montant/)
  assert.match(bloc, /mode: encaissement\.mode/)
  // Le client est déduit des factures sélectionnées, jamais saisi à la main.
  assert.match(bloc, /client: cible\?\.client/)
  // Une fois réparti, la sélection est vidée (plus d'action sur un état périmé).
  assert.match(bloc, /clearSelection\(\)/)
})

test('WIR183 : « Consolider des devis » est proposé et poste des ids de DEVIS', () => {
  const idx = LIST.indexOf('data-testid="consolider-devis"')
  assert.notEqual(idx, -1)
  const debut = LIST.indexOf('const confirmerConsolidation')
  const bloc = LIST.slice(debut, debut + 500)
  assert.match(bloc, /ventesApi\.consoliderFactures\(ids\)/)
})

// ── Retour client : le corps attendu par le serveur ─────────────────────────

test('WIR183 : le retour client poste motif + restocker + lignes {produit, quantite}', () => {
  const debut = LIST.indexOf('const confirmerRetour')
  const bloc = LIST.slice(debut, debut + 900)
  assert.match(bloc, /motif: retourMotif/)
  assert.match(bloc, /restocker: retourRestocker/)
  assert.match(bloc, /produit: l\.produit, quantite: l\.quantite/)
  // Les lignes à quantité nulle ne sont jamais envoyées.
  assert.match(bloc, /toNumber\(l\.quantite\) > 0/)
})

test('WIR183 : les quantités du retour ne sont ni bornées ni snappées par l\'écran', () => {
  const idx = LIST.indexOf('Quantité retournée —')
  assert.notEqual(idx, -1)
  const bloc = LIST.slice(Math.max(0, idx - 300), idx + 200)
  assert.match(bloc, /step="any"/)
})
