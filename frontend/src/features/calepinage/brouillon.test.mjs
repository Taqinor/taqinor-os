// CALX68 — BROUILLON LOCAL DE L'ATELIER, ET SA REPRISE. Exécuté en CI :
//   node --test src/features/calepinage/brouillon.test.mjs
//
// Logique PURE (aucun DOM, aucun builder) : `storage` et `obtenirLayout` sont
// injectés, exactement comme `ToitureDesign.jsx` les branche (voir l'en-tête
// de `brouillon.js`). Ce fichier prouve les quatre critères du plan (CALX68) :
//   1. deux gestes ⇒ UN brouillon (même clé, écrasée en place) ;
//   2. un brouillon plus récent que le serveur ⇒ « pertinent » (le bandeau
//      peut s'ouvrir) — et l'inverse (serveur plus récent) ⇒ IGNORÉ ;
//   3. lire/ignorer un brouillon ne touche jamais le serveur ni n'efface rien
//      (« Ignorer » ⇒ document serveur intact) ;
//   4. un `storage` indisponible (absent ou qui lève) ⇒ aucune exception,
//      aucun brouillon jamais rendu « pertinent » (donc aucun bandeau).
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  construireCle, hacherLayout, lireBrouillon, ecrireBrouillon, effacerBrouillon,
  brouillonPertinent, creerGestionnaireBrouillon,
  purgerBrouillonsOrphelins, memoriserReprise, consommerReprise, estPanneReseau,
} from './brouillon.js'
import { baseServeur, brouillonLocalAProposer, creerStockageMiroir, empreinteSansVue, lireBrouillonServeur, sansVue } from './brouillonServeur.js'
import { documentContrat } from '../../test/fixtures/contractSamples.js'

/** Stockage en mémoire — MÊME contrat que `localStorage` (getItem/setItem/removeItem). */
function stockageFactice(donnees = new Map()) {
  return {
    getItem: (cle) => (donnees.has(cle) ? donnees.get(cle) : null),
    setItem: (cle, valeur) => { donnees.set(cle, String(valeur)) },
    removeItem: (cle) => { donnees.delete(cle) },
    // ACAL84 — contrat Web Storage complet (`length`/`key`) pour la purge.
    get length() { return donnees.size },
    key: (i) => [...donnees.keys()][i] ?? null,
    _donnees: donnees,
  }
}

/** Un `storage` qui lève à CHAQUE appel — navigation privée à quota nul. */
function stockageQuiLeve() {
  return {
    getItem: () => { throw new Error('QuotaExceededError') },
    setItem: () => { throw new Error('QuotaExceededError') },
    removeItem: () => { throw new Error('QuotaExceededError') },
  }
}

/** Minuteur factice : ne tourne QUE quand le test appelle `tic()` lui-même —
 *  jamais un vrai timer, pour rester déterministe sous `node --test`. */
function minuteurFactice() {
  const taches = new Map()
  let id = 0
  return {
    minuteur: {
      definir: (fn) => { id += 1; taches.set(id, fn); return id },
      annuler: (idACouper) => { taches.delete(idACouper) },
    },
    tic: (idATic) => taches.get(idATic)?.(),
    actives: () => taches.size,
  }
}

test('construireCle — les trois segments, dans cet ordre, avec repli nommé', () => {
  assert.equal(
    construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'abc123' }),
    'calepinage_brouillon:41:7:abc123',
  )
  assert.equal(
    construireCle({ calepinageId: null, utilisateurId: null, hashBase: null }),
    'calepinage_brouillon:sans-id:anonyme:sans-hash',
  )
})

test('hacherLayout — déterministe, et distingue deux documents différents', () => {
  const a = { zones: [{ id: 'z1' }] }
  const b = { zones: [{ id: 'z2' }] }
  assert.equal(hacherLayout(a), hacherLayout(structuredClone(a)))
  assert.notEqual(hacherLayout(a), hacherLayout(b))
})

test('ecrireBrouillon + lireBrouillon — aller-retour fidèle', () => {
  const storage = stockageFactice()
  const cle = construireCle({ calepinageId: 1, utilisateurId: 2, hashBase: 'h' })
  const ok = ecrireBrouillon(storage, cle, { zones: [] }, '2026-09-21T10:00:00.000Z')
  assert.equal(ok, true)
  const relu = lireBrouillon(storage, cle)
  assert.deepEqual(relu, { layout: { zones: [] }, horodatage: '2026-09-21T10:00:00.000Z' })
})

test('lireBrouillon — absent, corrompu ou de mauvaise forme ⇒ null, jamais une exception', () => {
  const storage = stockageFactice()
  const cle = construireCle({ calepinageId: 1, utilisateurId: 2, hashBase: 'h' })
  assert.equal(lireBrouillon(storage, cle), null) // absent
  storage.setItem(cle, '{ceci-nest-pas-du-json')
  assert.equal(lireBrouillon(storage, cle), null) // corrompu
  storage.setItem(cle, JSON.stringify({ autreChose: true }))
  assert.equal(lireBrouillon(storage, cle), null) // mauvaise forme
})

test('effacerBrouillon — retire l’entrée', () => {
  const storage = stockageFactice()
  const cle = construireCle({ calepinageId: 1, utilisateurId: 2, hashBase: 'h' })
  ecrireBrouillon(storage, cle, { zones: [] })
  assert.equal(effacerBrouillon(storage, cle), true)
  assert.equal(lireBrouillon(storage, cle), null)
})

/* ── Critère 1 — deux gestes ⇒ UN brouillon ─────────────────────────────── */
test('creerGestionnaireBrouillon — deux gestes (repli, sans réglage) écrivent UN SEUL brouillon', () => {
  const storage = stockageFactice()
  let layoutCourant = { zones: [{ id: 'z1' }] }
  const gestionnaire = creerGestionnaireBrouillon({
    storage,
    calepinageId: 41,
    utilisateurId: 7,
    hashBase: 'srv-hash',
    intervalleSecondes: null, // aucun réglage ⇒ repli « à chaque geste »
    obtenirLayout: () => layoutCourant,
  })

  // ACAL84 — la PREMIÈRE vue amorce la référence (scène d'ouverture) : aucune écriture.
  assert.equal(gestionnaire.notifierGeste(), false)
  assert.equal(storage._donnees.size, 0)

  // Geste 1 : un premier tracé.
  layoutCourant = { zones: [{ id: 'z1', vertices: [[0, 0], [1, 0], [1, 1]] }] }
  assert.equal(gestionnaire.notifierGeste(), true)
  assert.equal(storage._donnees.size, 1)

  // Geste 2 : le document a RÉELLEMENT changé (déplacement d'un panneau).
  layoutCourant = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  assert.equal(gestionnaire.notifierGeste(), true)

  // TOUJOURS une seule entrée : même clé, écrasée en place — jamais deux
  // brouillons pour la même session d'édition.
  assert.equal(storage._donnees.size, 1)
  const brouillon = lireBrouillon(storage, gestionnaire.cle)
  assert.deepEqual(brouillon.layout, layoutCourant)
})

test('notifierGeste — n’écrit PAS deux fois pour le même document (rien n’a changé)', () => {
  const storage = stockageFactice()
  let layout = { zones: [{ id: 'z1' }] }
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: null,
    obtenirLayout: () => layout,
  })
  assert.equal(gestionnaire.notifierGeste(), false) // ACAL84 — amorce
  layout = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  assert.equal(gestionnaire.notifierGeste(), true)
  // Même document, un second appel (ex. deux sondages successifs sans geste
  // réel entre les deux) : AUCUNE écriture inutile.
  assert.equal(gestionnaire.notifierGeste(), false)
})

test('ACAL1329 — pan ajouté en cours de tracé : aucune écriture avant le dernier point, une seule ensuite', () => {
  const storage = stockageFactice()
  let layout = { zones: [{ id: 'area-1' }] }
  let enTrace = false
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 5, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: null,
    obtenirLayout: () => layout,
    enPause: () => enTrace,
  })
  assert.equal(gestionnaire.notifierGeste(), false) // amorce : le toit enregistré
  // « Ajouter un pan » puis deux points : le document (vrai) porte la zone ouverte, rien n'est écrit.
  enTrace = true
  layout = { zones: [{ id: 'area-1' }, { id: 'area-2', vertices: [] }] }
  assert.equal(gestionnaire.notifierGeste(), false)
  layout = { zones: [{ id: 'area-1' }, { id: 'area-2', vertices: [[0, 0], [1, 0]] }] }
  assert.equal(gestionnaire.enregistrerMaintenant(), false)
  assert.equal(storage._donnees.size, 0)
  // Dernier point : le pan fermé s'écrit, une fois.
  enTrace = false
  layout = { zones: [{ id: 'area-1' }, { id: 'area-2', vertices: [[0, 0], [1, 0], [1, 1]] }] }
  assert.equal(gestionnaire.notifierGeste(), true)
  assert.equal(gestionnaire.notifierGeste(), false)
  assert.equal(storage._donnees.size, 1)
})

test('notifierGeste — rien à sauvegarder (aucun pan tracé) ⇒ no-op, aucune entrée', () => {
  const storage = stockageFactice()
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: null,
    obtenirLayout: () => null,
  })
  assert.equal(gestionnaire.notifierGeste(), false)
  assert.equal(storage._donnees.size, 0)
})

test('demarrer — intervalle RÉGLÉ : minuterie active, un tic n’écrit qu’un document CHANGÉ, notifierGeste inerte', () => {
  const storage = stockageFactice()
  const { minuteur, tic, actives } = minuteurFactice()
  let layout = { zones: [{ id: 'z1' }] }
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: 300, // réglage utilisateur — la minuterie SEULE écrit
    obtenirLayout: () => layout,
    minuteur,
  })
  gestionnaire.demarrer()
  assert.equal(actives(), 1)
  // Le repli est ÉTEINT quand une minuterie est active.
  assert.equal(gestionnaire.notifierGeste(), false)
  assert.equal(storage._donnees.size, 0)
  // ACAL84 — un tic SANS geste n'écrit rien (même règle que le repli)…
  tic(1)
  assert.equal(storage._donnees.size, 0)
  // …un tic après un vrai changement, si.
  layout = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  tic(1)
  assert.equal(storage._donnees.size, 1)
  gestionnaire.arreter()
  assert.equal(actives(), 0)
})

test('demarrer — sans réglage : sondage de repli, notifierGeste reste directement appelable', () => {
  const storage = stockageFactice()
  const { minuteur, tic, actives } = minuteurFactice()
  let layout = null
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: undefined,
    obtenirLayout: () => layout,
    minuteur,
  })
  gestionnaire.demarrer()
  assert.equal(actives(), 1)
  tic(1) // rien tracé encore
  assert.equal(storage._donnees.size, 0)
  layout = { zones: [{ id: 'z1' }] }
  tic(1) // ACAL84 — la scène vient d'être hydratée : première vue = amorce
  assert.equal(storage._donnees.size, 0)
  layout = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  tic(1) // le sondage détecte le changement…
  assert.equal(storage._donnees.size, 0, 'T4-U4-025 — anti-rebond : rien au tic qui voit le changement')
  tic(1) // …et l'écrit au tic suivant, le document n'ayant plus bougé
  assert.equal(storage._donnees.size, 1)
  gestionnaire.arreter()
})

/* ── T4-U4-025 — le brouillon serveur : aucun PUT sans changement, anti-rebond, jamais pendant un enregistrement ── */
const PERIODE_SONDAGE_MS = 4000
function atelierFactice({ obtenirLayout, enregistrementEnCours, referenceInitiale } = {}) {
  const puts = []
  const deletes = []
  const { minuteur, tic } = minuteurFactice()
  const miroir = creerStockageMiroir({
    base: stockageFactice(), calepinageId: 41,
    envoyer: (id, corps) => { puts.push(corps.layout); return Promise.resolve() },
    effacer: () => { deletes.push(1); return Promise.resolve() },
  })
  const g = creerGestionnaireBrouillon({
    storage: miroir, calepinageId: 41, utilisateurId: 7, hashBase: 'h1',
    intervalleSecondes: null, // le produit : aucun réglage ⇒ sondage de repli
    obtenirLayout, hacher: empreinteSansVue, enregistrementEnCours, referenceInitiale, minuteur,
  })
  const attendre = async (ms) => { for (let t = 0; t < ms; t += PERIODE_SONDAGE_MS) tic(1); await new Promise((r) => setImmediate(r)) }
  return { g, puts, deletes, attendre }
}

test('T4-U4-025 — atelier ouvert 60 s sans geste ⇒ 0 PUT brouillon', async () => {
  const doc = { zones: [{ id: 'z1' }], consumption: { source: { origine: 'atelier', saisi_le: '2026-11-24T17:55:28Z' } } }
  const { g, puts, attendre } = atelierFactice({ obtenirLayout: () => structuredClone(doc) })
  g.demarrer()
  await attendre(60_000)
  assert.equal(puts.length, 0)
})

test('T4-U4-025 — un document qui change à CHAQUE lecture (horodatage recalculé) n’envoie pas un PUT par tic', async () => {
  let n = 0
  const { g, puts, attendre } = atelierFactice({ obtenirLayout: () => ({ zones: [{ id: 'z1' }], saisi_le: `t${n++}` }) })
  g.demarrer()
  await attendre(60_000)
  assert.equal(puts.length, 0, `${puts.length} PUT en 60 s sans geste`)
})

test('T4-U4-025 — une modification ⇒ exactement 1 PUT, après l’anti-rebond', async () => {
  let doc = { zones: [{ id: 'z1' }] }
  const { g, puts, attendre } = atelierFactice({ obtenirLayout: () => doc })
  g.demarrer()
  doc = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  await attendre(PERIODE_SONDAGE_MS)
  assert.equal(puts.length, 0, 'pas encore : le changement vient d’être vu')
  await attendre(60_000)
  assert.equal(puts.length, 1)
  assert.deepEqual(puts[0], doc)
})

test('T4-U4-025 — modifié PENDANT un enregistrement ⇒ rien en vol, envoyé une fois l’enregistrement fini', async () => {
  const enregistre = { zones: [{ id: 'z1' }] }
  let doc = enregistre
  let enVol = false
  const { g, puts, deletes, attendre } = atelierFactice({ obtenirLayout: () => doc, enregistrementEnCours: () => enVol })
  g.demarrer()
  enVol = true // « Enregistrer le calepinage » : le document `enregistre` part au serveur…
  doc = { zones: [{ id: 'z1' }, { id: 'z2' }] } // …et l'utilisateur continue de dessiner
  await attendre(20_000)
  assert.equal(puts.length, 0, 'aucun brouillon pendant l’enregistrement')
  g.effacerEtAmorcer(enregistre) // réponse 2xx : la référence est le document ENREGISTRÉ
  enVol = false
  await attendre(20_000)
  assert.equal(deletes.length, 1)
  assert.equal(puts.length, 1, 'la modification faite pendant l’enregistrement part après lui')
  assert.deepEqual(puts[0], doc)
})

test('T4-U4-025 — la minuterie neuve (clé neuve après enregistrement) part de la référence ENREGISTRÉE', async () => {
  const enregistre = { zones: [{ id: 'z1' }] }
  const doc = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  const { g, puts, attendre } = atelierFactice({ obtenirLayout: () => doc, referenceInitiale: () => empreinteSansVue(enregistre) })
  g.demarrer()
  await attendre(20_000)
  assert.equal(puts.length, 1)
})

/* ── Critère 2 — reprise : plus récent que le serveur ⇒ pertinent ──────── */
test('brouillonPertinent — un brouillon SANS horodatage serveur connu est proposé', () => {
  const storage = stockageFactice()
  const cle = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash' })
  ecrireBrouillon(storage, cle, { zones: [{ id: 'z1' }] }, '2026-09-21T09:30:00.000Z')

  const propose = brouillonPertinent({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash',
  })
  assert.ok(propose)
  assert.equal(propose.horodatage, '2026-09-21T09:30:00.000Z')
})

test('brouillonPertinent — plus RÉCENT que le serveur ⇒ proposé ; plus ANCIEN ⇒ ignoré', () => {
  const storage = stockageFactice()
  const cle = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash' })
  ecrireBrouillon(storage, cle, { zones: [] }, '2026-09-21T09:30:00.000Z')

  assert.ok(brouillonPertinent({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash',
    misAJourServeur: '2026-09-21T09:00:00.000Z', // serveur plus ANCIEN
  }))
  assert.equal(brouillonPertinent({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash',
    misAJourServeur: '2026-09-21T10:00:00.000Z', // serveur plus RÉCENT
  }), null)
})

test('brouillonPertinent — aucun brouillon sous cette clé ⇒ null (pas de bandeau)', () => {
  const storage = stockageFactice()
  assert.equal(brouillonPertinent({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash',
  }), null)
})

test('brouillonPertinent — une clé (hashBase) DIFFÉRENTE ne trouve rien : un enregistrement réussi orpheline l’ancien brouillon', () => {
  const storage = stockageFactice()
  const cle = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'ancien-hash' })
  ecrireBrouillon(storage, cle, { zones: [] }, '2026-09-21T09:30:00.000Z')

  // Le document a été enregistré depuis : le serveur porte un NOUVEAU
  // `layout_hash`, donc la clé change — l'ancien brouillon devient introuvable.
  assert.equal(brouillonPertinent({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'nouveau-hash',
  }), null)
})

/* ── Critère 3 — « Ignorer » ⇒ document serveur intact ──────────────────── */
test('lire/ignorer un brouillon ne modifie JAMAIS le brouillon lui-même (aucune écriture, aucun effacement de sa clé)', () => {
  const donnees = new Map()
  const ecrituresParCle = []
  const effacementsParCle = []
  const storage = stockageFactice(donnees)
  const storageEspionne = {
    // `lireBrouillon`/`brouillonPertinent` sondent l'accessibilité du storage
    // par une écriture+effacement d'une clé SONDE dédiée (voir
    // `stockageUtilisable` dans `brouillon.js`) : ce n'est PAS une écriture du
    // brouillon lui-même. Ce test isole donc les appels touchant LA CLÉ DU
    // BROUILLON, la seule dont l'intégrité importe ici.
    getItem: (c) => storage.getItem(c),
    setItem: (c, v) => { ecrituresParCle.push(c); storage.setItem(c, v) },
    removeItem: (c) => { effacementsParCle.push(c); storage.removeItem(c) },
  }
  const cle = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash' })
  const original = { zones: [{ id: 'z1' }] }
  ecrireBrouillon(storage, cle, original, '2026-09-21T09:30:00.000Z')

  const propose = brouillonPertinent({
    storage: storageEspionne, calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash',
  })
  assert.ok(propose)
  // « Ignorer » : l'appelant ne fait RIEN d'autre que fermer le bandeau — la
  // LECTURE seule ne doit ni réécrire ni effacer la clé du brouillon (donc,
  // a fortiori, ne touche à AUCUN document serveur : cette fonction ne parle
  // qu'à `localStorage`).
  assert.ok(!ecrituresParCle.includes(cle))
  assert.ok(!effacementsParCle.includes(cle))
  // Le brouillon local, lui, reste en place et INCHANGÉ tant que rien ne
  // l'efface explicitement (seul un enregistrement réussi l'efface, CALX68).
  assert.deepEqual(lireBrouillon(storage, cle), {
    layout: original, horodatage: '2026-09-21T09:30:00.000Z',
  })
})

/* ── Critère 4 — localStorage indisponible ⇒ aucune erreur, aucun bandeau ── */
test('storage absent (null) — aucune exception, jamais de brouillon proposé', () => {
  assert.doesNotThrow(() => {
    assert.equal(ecrireBrouillon(null, 'cle', { zones: [] }), false)
    assert.equal(lireBrouillon(null, 'cle'), null)
    assert.equal(effacerBrouillon(null, 'cle'), false)
    assert.equal(brouillonPertinent({
      storage: null, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    }), null)
  })
})

test('storage qui LÈVE (quota nul en navigation privée) — aucune exception, jamais de brouillon proposé', () => {
  const storage = stockageQuiLeve()
  assert.doesNotThrow(() => {
    assert.equal(ecrireBrouillon(storage, 'cle', { zones: [] }), false)
    assert.equal(lireBrouillon(storage, 'cle'), null)
    assert.equal(effacerBrouillon(storage, 'cle'), false)
    assert.equal(brouillonPertinent({
      storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    }), null)
  })
})

test('creerGestionnaireBrouillon avec storage qui lève — notifierGeste/enregistrerMaintenant renvoient false, jamais une exception', () => {
  const storage = stockageQuiLeve()
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: null,
    obtenirLayout: () => ({ zones: [{ id: 'z1' }] }),
  })
  assert.doesNotThrow(() => {
    assert.equal(gestionnaire.notifierGeste(), false)
    assert.equal(gestionnaire.enregistrerMaintenant(), false)
    assert.equal(gestionnaire.effacer(), false)
  })
})

test('obtenirLayout qui lève (builder pas prêt) — jamais une exception, no-op', () => {
  const storage = stockageFactice()
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 1, utilisateurId: 2, hashBase: 'h',
    intervalleSecondes: null,
    obtenirLayout: () => { throw new Error('builder non prêt') },
  })
  assert.doesNotThrow(() => {
    assert.equal(gestionnaire.notifierGeste(), false)
  })
  assert.equal(storage._donnees.size, 0)
})

/* ── Effacement après enregistrement réussi ─────────────────────────────── */
test('effacer() — le brouillon disparaît (appelé par la page après un enregistrement réussi)', () => {
  const storage = stockageFactice()
  let layout = { zones: [{ id: 'z1' }] }
  const gestionnaire = creerGestionnaireBrouillon({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'srv-hash',
    intervalleSecondes: null,
    obtenirLayout: () => layout,
  })
  gestionnaire.notifierGeste() // amorce (ACAL84)
  layout = { zones: [{ id: 'z1' }, { id: 'z2' }] }
  gestionnaire.notifierGeste()
  assert.ok(lireBrouillon(storage, gestionnaire.cle))
  assert.equal(gestionnaire.effacer(), true)
  assert.equal(lireBrouillon(storage, gestionnaire.cle), null)
})

/* ── ACAL84 — aucune écriture sans geste, clé serveur, purge, reprise ───── */
test('premier tic sans geste → aucune écriture (les deux modes)', () => {
  for (const intervalleSecondes of [null, 30]) {
    const storage = stockageFactice()
    const { minuteur, tic } = minuteurFactice()
    const gestionnaire = creerGestionnaireBrouillon({
      storage, calepinageId: 41, utilisateurId: 7, hashBase: 'e'.repeat(64),
      intervalleSecondes,
      obtenirLayout: () => ({ zones: [{ id: 'z1' }] }),
      minuteur,
    })
    gestionnaire.demarrer()
    tic(1)
    tic(1)
    assert.equal(storage._donnees.size, 0, `mode intervalle=${intervalleSecondes}`)
    assert.equal(gestionnaire.enregistrerMaintenant(), false)
    assert.equal(storage._donnees.size, 0)
    gestionnaire.arreter()
  }
})

test('clé = empreinte serveur, purge des autres clés', () => {
  const storage = stockageFactice()
  const empreinte = 'a'.repeat(64)
  // Le jeton SERVEUR (design-context / réponse d'écriture) est la clé, tel quel.
  const courante = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: empreinte })
  assert.equal(courante, `calepinage_brouillon:41:7:${empreinte}`)
  const perimee = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'b'.repeat(64) })
  const autreUtilisateur = construireCle({ calepinageId: 41, utilisateurId: 8, hashBase: 'c'.repeat(64) })
  const autreCalepinage = construireCle({ calepinageId: 42, utilisateurId: 7, hashBase: 'd'.repeat(64) })
  for (const cle of [courante, perimee, autreUtilisateur, autreCalepinage]) {
    ecrireBrouillon(storage, cle, { zones: [] })
  }
  assert.equal(purgerBrouillonsOrphelins({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: empreinte,
  }), 1)
  assert.ok(lireBrouillon(storage, courante))
  assert.equal(lireBrouillon(storage, perimee), null)
  assert.ok(lireBrouillon(storage, autreUtilisateur))
  assert.ok(lireBrouillon(storage, autreCalepinage))
  // Storage défaillant : 0, jamais une exception.
  assert.equal(purgerBrouillonsOrphelins({
    storage: stockageQuiLeve(), calepinageId: 41, utilisateurId: 7, hashBase: empreinte,
  }), 0)
})

test('reprise — mémorisée puis consommée UNE fois au boot suivant', () => {
  const storage = stockageFactice()
  const ids = { calepinageId: 41, utilisateurId: 7 }
  assert.equal(consommerReprise(storage, ids), null)
  assert.equal(memoriserReprise(storage, ids, { zones: [{ id: 'z9' }] }), true)
  assert.deepEqual(consommerReprise(storage, ids), { layout: { zones: [{ id: 'z9' }] } })
  assert.equal(consommerReprise(storage, ids), null)
  assert.equal(memoriserReprise(stockageQuiLeve(), ids, { zones: [] }), false)
  assert.equal(consommerReprise(stockageQuiLeve(), ids), null)
})

/* ACAL400 — le miroir SERVEUR du brouillon (`brouillonServeur.js`). Les
   réponses viennent du contrat committé `calepinage_brouillon.json` (PACT13). */
const CONTRAT_BROUILLON = documentContrat('calepinage', 'calepinage_brouillon')

test('ACAL400 — le miroir écrit en local ET envoie au serveur, puis efface des deux côtés', async () => {
  const envois = []
  const effacements = []
  const local = stockageFactice()
  const miroir = creerStockageMiroir({
    base: local, calepinageId: 41,
    envoyer: (id, corps) => { envois.push([id, corps]); return Promise.resolve() },
    effacer: (id) => { effacements.push(id); return Promise.resolve() },
  })
  const { layout, horodatage, base_empreinte: empreinte } = CONTRAT_BROUILLON.corps_ecriture
  const g = creerGestionnaireBrouillon({
    storage: miroir, calepinageId: 41, utilisateurId: 7, hashBase: empreinte,
    intervalleSecondes: 30, obtenirLayout: (() => {
      let n = 0
      return () => (n++ === 0 ? { zones: [] } : layout)
    })(),
    minuteur: { definir: () => 1, annuler: () => {} },
  })
  g.demarrer() // amorce : aucune écriture
  assert.equal(envois.length, 0)
  assert.equal(g.enregistrerMaintenant(), true)
  assert.ok(lireBrouillon(local, g.cle), 'le localStorage reste la première source')
  assert.equal(envois.length, 1)
  assert.equal(envois[0][0], 41)
  assert.deepEqual(Object.keys(envois[0][1]).sort(), Object.keys(CONTRAT_BROUILLON.corps_ecriture).sort())
  assert.equal(envois[0][1].base_empreinte, empreinte)
  assert.deepEqual(envois[0][1].layout, layout)
  assert.ok(typeof horodatage === 'string')
  g.effacer()
  await new Promise((r) => setTimeout(r, 0)) // R2-04 — le DELETE part en file, après le PUT
  assert.deepEqual(effacements, [41])
  assert.equal(lireBrouillon(local, g.cle), null)
})

test('ACAL400 — « aucun-document » part comme l’empreinte vide ; les autres clés ne partent jamais', () => {
  assert.equal(baseServeur('aucun-document'), '')
  assert.equal(baseServeur(null), '')
  const envois = []
  const miroir = creerStockageMiroir({
    base: stockageFactice(), calepinageId: 4,
    envoyer: (id, corps) => { envois.push(corps); return Promise.resolve() },
  })
  miroir.setItem('__calepinage_brouillon_sonde__', '1')
  miroir.setItem(construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'x' }), '{"layout":{},"horodatage":"t"}')
  assert.equal(envois.length, 0, 'ni la sonde ni un autre calepinage (41 ≠ 4)')
  miroir.setItem(construireCle({ calepinageId: 4, utilisateurId: 7, hashBase: 'aucun-document' }),
    '{"layout":{"zones":[]},"horodatage":"t"}')
  assert.deepEqual(envois, [{ layout: { zones: [] }, horodatage: 't', base_empreinte: '' }])
})

test('ACAL400 — lecture serveur : exemple ⇒ proposé (serveur), exemple_vide ou base différente ⇒ null', async () => {
  const exemple = CONTRAT_BROUILLON.exemple
  const lire = (donnees) => () => Promise.resolve({ data: donnees })
  const propose = await lireBrouillonServeur({
    lire: lire(exemple), calepinageId: 41, hashBase: exemple.base_empreinte,
  })
  assert.deepEqual(propose, { layout: exemple.layout, horodatage: exemple.horodatage, serveur: true })
  assert.equal(await lireBrouillonServeur({
    lire: lire(CONTRAT_BROUILLON.exemple_vide), calepinageId: 41, hashBase: exemple.base_empreinte,
  }), null)
  assert.equal(await lireBrouillonServeur({
    lire: lire(exemple), calepinageId: 41, hashBase: 'autre-empreinte',
  }), null)
  assert.equal(await lireBrouillonServeur({
    lire: () => Promise.reject(new Error('réseau')), calepinageId: 41, hashBase: 'x',
  }), null)
})

test('R2-04 — un brouillon serveur IDENTIQUE au document servi (clés dans un autre ordre) n’est jamais proposé', async () => {
  const exemple = CONTRAT_BROUILLON.exemple
  const lire = () => Promise.resolve({ data: exemple })
  const inverser = (v) => (Array.isArray(v) ? v.map(inverser) : (v && typeof v === 'object'
    ? Object.fromEntries(Object.entries(v).reverse().map(([k, x]) => [k, inverser(x)])) : v))
  const autreOrdre = inverser(exemple.layout)
  assert.equal(await lireBrouillonServeur({
    lire, calepinageId: 41, hashBase: exemple.base_empreinte, layoutServi: autreOrdre,
  }), null)
  assert.ok(await lireBrouillonServeur({
    lire, calepinageId: 41, hashBase: exemple.base_empreinte, layoutServi: { zones: ['autre'] },
  }), 'un document servi différent laisse le brouillon proposé')
})

test('R2-04 — les envois du miroir partent EN FILE : le DELETE ne passe jamais devant un PUT en vol', async () => {
  const journal = []
  let finirPut
  const miroir = creerStockageMiroir({
    base: stockageFactice(), calepinageId: 41,
    envoyer: () => new Promise((resolu) => { journal.push('put-debut'); finirPut = () => { journal.push('put-fin'); resolu() } }),
    effacer: () => { journal.push('delete'); return Promise.resolve() },
  })
  const cle = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'h1' })
  miroir.setItem(cle, JSON.stringify({ layout: { a: 1 }, horodatage: 'x' }))
  miroir.removeItem(cle)
  await Promise.resolve()
  assert.deepEqual(journal, ['put-debut'], 'le DELETE attend la fin du PUT')
  finirPut()
  await new Promise((r) => setTimeout(r, 0))
  assert.deepEqual(journal, ['put-debut', 'put-fin', 'delete'])
})

test('ACAL1248 — un PUT encore en attente quand la clé est effacée ne part plus : aucun PUT entre le PUT en vol et le DELETE', async () => {
  const journal = []
  const termines = []
  const miroir = creerStockageMiroir({
    base: stockageFactice(), calepinageId: 41,
    envoyer: (id, corps) => new Promise((resolu) => {
      journal.push(`put-${corps.layout.n}`); termines.push(() => { journal.push(`fin-${corps.layout.n}`); resolu() })
    }),
    effacer: () => { journal.push('delete'); return Promise.resolve() },
  })
  const cle = construireCle({ calepinageId: 41, utilisateurId: 7, hashBase: 'h1' })
  miroir.setItem(cle, JSON.stringify({ layout: { n: 1 }, horodatage: 'x' })) // en vol
  miroir.setItem(cle, JSON.stringify({ layout: { n: 2 }, horodatage: 'y' })) // en attente
  miroir.removeItem(cle) // enregistrement réussi
  await Promise.resolve()
  termines[0]()
  await new Promise((r) => setTimeout(r, 0))
  assert.deepEqual(journal, ['put-1', 'fin-1', 'delete'], 'le PUT 2, en attente, est annulé par l’effacement')
  // Un brouillon écrit APRÈS l'effacement (même clé) repart normalement.
  miroir.setItem(cle, JSON.stringify({ layout: { n: 3 }, horodatage: 'z' }))
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(journal.at(-1), 'put-3')
})

test('ACAL1248 — enregistrer ôte la référence de l’ancienne minuterie : aucun PUT après le DELETE, une vraie modification repart', async () => {
  const journal = []
  const miroir = creerStockageMiroir({
    base: stockageFactice(), calepinageId: 41,
    envoyer: (id, corps) => { journal.push(`put-${corps.layout.n}`); return Promise.resolve() },
    effacer: () => { journal.push('delete'); return Promise.resolve() },
  })
  let doc = { n: 0 }
  let tic = null
  const g = creerGestionnaireBrouillon({
    storage: miroir, calepinageId: 41, utilisateurId: 7, hashBase: 'h1', intervalleSecondes: 30,
    obtenirLayout: () => doc,
    minuteur: { definir: (fn) => { tic = fn; return 1 }, annuler: () => {} },
  })
  g.demarrer()
  doc = { n: 1 } // l'utilisateur modifie puis clique « Enregistrer » avant le prochain tic
  g.effacerEtAmorcer() // enregistrement réussi : le document courant EST le document servi
  tic() // l'ancienne minuterie, encore vivante jusqu'au prochain rendu
  await new Promise((r) => setTimeout(r, 0))
  assert.deepEqual(journal, ['delete'], 'aucun brouillon fantôme après l’enregistrement')
  doc = { n: 2 }
  tic()
  await new Promise((r) => setTimeout(r, 0))
  assert.deepEqual(journal, ['delete', 'put-2'], 'une modification POSTÉRIEURE reste brouillonnée')
})

test('ACAL1248 — le renvoi après panne (effacer seul) garde la référence : ce qui a changé depuis se re-brouillonne', () => {
  const storage = stockageFactice()
  let doc = { n: 0 }
  let tic = null
  const g = creerGestionnaireBrouillon({
    storage, calepinageId: 41, utilisateurId: 7, hashBase: 'h1', intervalleSecondes: 30,
    obtenirLayout: () => doc, minuteur: { definir: (fn) => { tic = fn; return 1 }, annuler: () => {} },
  })
  g.demarrer()
  doc = { n: 1 }
  g.effacer()
  tic()
  assert.ok(lireBrouillon(storage, g.cle), 'modifié depuis la référence ⇒ re-brouillonné')
})

test('ACAL1345 — trois pans : choisir le pan 2, le 3, revenir au 1 ne change pas l’empreinte et n’écrit aucun brouillon', async () => {
  const sommets = (x) => [[x, 0], [x + 4, 0], [x + 4, 3], [x, 3]]
  const document3Pans = (actif) => ({ // forme réelle de `serializeLayout` : `outline`/`pin` suivent le pan actif
    version: 2, zones: [{ id: 'p1', vertices: sommets(0) }, { id: 'p2', vertices: sommets(10) }, { id: 'p3', vertices: sommets(20) }],
    activeAreaId: actif, outline: sommets({ p1: 0, p2: 10, p3: 20 }[actif]), pin: { lat: 33.5, lng: -7.6 + { p1: 0, p2: 1, p3: 2 }[actif] },
    scene: { sunDay: 172, sunHour: 12 },
  })
  assert.notEqual(hacherLayout(sansVue(document3Pans('p1'))), hacherLayout(sansVue(document3Pans('p2'))),
    'sans neutralisation, le choix du pan CHANGE le document : c’est ce que le test garde')
  const envois = []
  const miroir = creerStockageMiroir({
    base: stockageFactice(), calepinageId: 9,
    envoyer: (id, corps) => { envois.push(corps); return Promise.resolve() },
  })
  let doc = document3Pans('p1')
  let tic = null
  const g = creerGestionnaireBrouillon({
    storage: miroir, calepinageId: 9, utilisateurId: 1, hashBase: 'h', intervalleSecondes: 30,
    obtenirLayout: () => sansVue(doc), hacher: empreinteSansVue,
    minuteur: { definir: (fn) => { tic = fn; return 1 }, annuler: () => {} },
  })
  g.demarrer()
  const reference = empreinteSansVue(doc)
  for (const actif of ['p2', 'p3', 'p1']) {
    doc = document3Pans(actif)
    assert.equal(empreinteSansVue(doc), reference, `pan actif ${actif} : même empreinte`)
    tic()
  }
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(envois.length, 0, 'aucun PUT de brouillon')
  // Une vraie modification, elle, s'écrit — avec le contenu ENTIER (pan actif et épingle compris : la reprise reste fidèle).
  doc = { ...document3Pans('p2'), zones: [{ id: 'p1', vertices: sommets(0) }, { id: 'p2', vertices: sommets(11) }, { id: 'p3', vertices: sommets(20) }] }
  tic()
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(envois.length, 1)
  assert.equal(envois[0].layout.activeAreaId, 'p2')
  assert.ok(envois[0].layout.pin && envois[0].layout.outline)
  // Une épingle posée à la main est une donnée : la déplacer modifie l'empreinte.
  const manuel = { ...document3Pans('p1'), pinSource: 'manuel' }
  assert.notEqual(empreinteSansVue(manuel), empreinteSansVue({ ...manuel, pin: { lat: 34, lng: -7 } }))
})

test('ACAL945 — estPanneReseau : vrai sans réponse ou ERR_NETWORK ; faux pour ECONNABORTED et toute réponse HTTP', () => {
  assert.equal(estPanneReseau(new Error('Network Error')), true)
  assert.equal(estPanneReseau({ code: 'ERR_NETWORK' }), true)
  assert.equal(estPanneReseau({ code: 'ECONNABORTED' }), false)
  assert.equal(estPanneReseau({ code: 'ETIMEDOUT' }), false)
  assert.equal(estPanneReseau({ response: { status: 409, data: {} } }), false)
  assert.equal(estPanneReseau({ response: { status: 500 } }), false)
})

test('H1 — sansVue : l’instant du soleil (`scene`) ne compte pas, le reste du document si ; l’original est intact', () => {
  const ete = { version: 2, zones: [{ id: 'z1' }], scene: { sunDay: 172, sunHour: 15 } }
  const hiver = { version: 2, zones: [{ id: 'z1' }], scene: { sunDay: 355, sunHour: 12 } }
  assert.notEqual(hacherLayout(ete), hacherLayout(hiver))
  assert.equal(hacherLayout(sansVue(ete)), hacherLayout(sansVue(hiver)))
  assert.notEqual(hacherLayout(sansVue({ ...ete, zones: [] })), hacherLayout(sansVue(hiver)))
  assert.deepEqual(ete.scene, { sunDay: 172, sunHour: 15 }, 'jamais muté : un enregistrement garde tout')
  assert.equal(sansVue(null), null)
  const sans = { version: 2 }
  assert.equal(sansVue(sans), sans)
})

test('H1 — gestionnaire de brouillon nourri par sansVue : changer de saison n’écrit AUCUN brouillon', () => {
  const storage = new Map()
  const st = { getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) }
  let doc = { version: 2, zones: [], scene: { sunDay: 355, sunHour: 12 } }
  let tic = null
  const g = creerGestionnaireBrouillon({
    storage: st, calepinageId: 9, utilisateurId: 1, hashBase: 'h', intervalleSecondes: 30,
    obtenirLayout: () => sansVue(doc),
    minuteur: { definir: (fn) => { tic = fn; return 1 }, annuler: () => {} },
  })
  g.demarrer()
  doc = { ...doc, scene: { sunDay: 172, sunHour: 15 } }
  tic()
  assert.equal(storage.has(g.cle), false)
  doc = { ...doc, zones: [{ id: 'z1' }] }
  tic()
  assert.equal(storage.has(g.cle), true)
})

/* T4-U1-013 — « Brouillon local du 15:12 » revenait à chaque réouverture juste après « Conception enregistrée » : un
   brouillon IDENTIQUE au document servi (vue et clés dans un autre ordre comprises) n'a rien de non enregistré. */
test('T4-U1-013 — brouillon local identique au document servi ⇒ jamais proposé ; différent ⇒ proposé', () => {
  const servi = { scene: { jour: 172, heure: 12 }, zones: [{ id: 'z1', geometry: { count: 12, kwc: 8.52 } }], version: 2 }
  const identique = { layout: { version: 2, zones: [{ geometry: { kwc: 8.52, count: 12 }, id: 'z1' }] }, horodatage: '2026-11-24T15:12:00Z' }
  assert.equal(brouillonLocalAProposer(identique, servi), null)
  const different = { layout: { version: 2, zones: [{ id: 'z1', geometry: { count: 13, kwc: 9.23 } }] }, horodatage: '2026-11-24T15:12:00Z' }
  assert.equal(brouillonLocalAProposer(different, servi), different)
  assert.equal(brouillonLocalAProposer(null, servi), null)
  assert.equal(brouillonLocalAProposer(different, null), different)
})

test('T4-U1-013 — brouillon SERVEUR identique au document servi à l’état de vue près ⇒ jamais proposé', async () => {
  const servi = { scene: { jour: 172, heure: 12 }, zones: [{ id: 'z1' }] }
  const lire = () => Promise.resolve({ data: { layout: { zones: [{ id: 'z1' }] }, horodatage: 'h', base_empreinte: 'E1' } })
  assert.equal(await lireBrouillonServeur({ lire, calepinageId: 1, hashBase: 'E1', layoutServi: servi }), null)
})
