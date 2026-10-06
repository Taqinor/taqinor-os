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
  purgerBrouillonsOrphelins, memoriserReprise, consommerReprise,
} from './brouillon.js'

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
  tic(1) // le sondage détecte le changement
  assert.equal(storage._donnees.size, 1)
  gestionnaire.arreter()
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
