import test from 'node:test'
import assert from 'node:assert/strict'
import {
  GOTO_SHORTCUTS, GLOBAL_SHORTCUTS, CREATE_SHORTCUTS, EDIT_SHORTCUTS,
  isTypingTarget, isMacPlatform, quickSearchShortcutLabel, filterShortcutGroups,
  buildAppShortcuts,
} from './shortcuts.js'

test('isTypingTarget: vrai pour les champs de saisie', () => {
  assert.equal(isTypingTarget({ tagName: 'INPUT' }), true)
  assert.equal(isTypingTarget({ tagName: 'TEXTAREA' }), true)
  assert.equal(isTypingTarget({ tagName: 'SELECT' }), true)
  assert.equal(isTypingTarget({ tagName: 'DIV', isContentEditable: true }), true)
})

test('isTypingTarget: rôles ARIA de saisie', () => {
  const mk = (role) => ({ tagName: 'DIV', getAttribute: (a) => (a === 'role' ? role : null) })
  assert.equal(isTypingTarget(mk('textbox')), true)
  assert.equal(isTypingTarget(mk('combobox')), true)
  assert.equal(isTypingTarget(mk('searchbox')), true)
  assert.equal(isTypingTarget(mk('button')), false)
})

test('isTypingTarget: faux pour le reste et tolère null', () => {
  assert.equal(isTypingTarget({ tagName: 'BUTTON' }), false)
  assert.equal(isTypingTarget({ tagName: 'DIV' }), false)
  assert.equal(isTypingTarget(null), false)
})

// ODY28 — une entrée porte SOIT `to` (navigation), SOIT `event` (overlay sans
// URL, ex. le lanceur d'applications) — jamais les deux, jamais aucun des deux.
test('GOTO_SHORTCUTS: bien formés (keys "g x" + route absolue OU événement + libellé)', () => {
  assert.ok(GOTO_SHORTCUTS.length >= 4)
  for (const s of GOTO_SHORTCUTS) {
    assert.match(s.keys, /^g [a-z]$/)
    assert.equal(!!s.to !== !!s.event, true, `« ${s.keys} » doit porter to XOR event`)
    if (s.to) assert.ok(s.to.startsWith('/'))
    if (s.event) assert.match(s.event, /^taqinor:/)
    assert.ok(s.label && s.label.length > 0)
  }
  // pas de lettre de raccourci en double
  const letters = GOTO_SHORTCUTS.map((s) => s.keys.split(' ')[1])
  assert.equal(new Set(letters).size, letters.length)
})

// ODY28 — « g g » = Menu d'accueil : la sortie CLAVIER du mode immersion,
// jumelle du bouton ⊞ de l'en-tête (ODY5).
test('GOTO_SHORTCUTS: « g g » mène au Menu d’accueil (/apps)', () => {
  const home = GOTO_SHORTCUTS.find((s) => s.keys === 'g g')
  assert.ok(home, '« g g » manquant')
  assert.equal(home.to, '/apps')
})

// ODY28 — fin du DOUBLE gestionnaire : « g a » naviguait vers /approbations
// PENDANT que le listener privé d'AppLauncher.jsx ouvrait le lanceur. Le sort
// tranché : « g a » reste la navigation historique, le lanceur prend « g o ».
test('ODY28: « g a » navigue (approbations) et le lanceur a son binding propre « g o »', () => {
  const approbations = GOTO_SHORTCUTS.find((s) => s.keys === 'g a')
  assert.equal(approbations.to, '/approbations')
  assert.equal(approbations.event, undefined)

  const launcher = GOTO_SHORTCUTS.find((s) => s.event === 'taqinor:app-launcher')
  assert.ok(launcher, 'aucun raccourci n’ouvre le lanceur')
  assert.equal(launcher.keys, 'g o')
  assert.equal(launcher.to, undefined)
  // Un seul déclencheur du lanceur dans toute la table.
  assert.equal(GOTO_SHORTCUTS.filter((s) => s.event === 'taqinor:app-launcher').length, 1)
})

test('ODY28: les 10 bindings historiques sont CONSERVÉS tels quels', () => {
  const historiques = {
    'g d': '/dashboard', 'g l': '/crm/leads', 'g c': '/crm', 'g v': '/ventes/devis',
    'g f': '/ventes/factures', 'g s': '/stock', 'g h': '/chantiers', 'g t': '/sav',
    'g p': '/planification', 'g a': '/approbations',
  }
  for (const [keys, to] of Object.entries(historiques)) {
    const hit = GOTO_SHORTCUTS.find((s) => s.keys === keys)
    assert.ok(hit, `binding historique « ${keys} » disparu`)
    assert.equal(hit.to, to, `« ${keys} » a changé de destination`)
  }
})

/* ── ODY28 — bindings « g + lettre » déclarés par les apps ─────────────── */
const APPS = [
  { key: 'crm', shortcut: 'r', nav: { label: 'CRM', items: [{ to: '/crm/cockpit' }] } },
  { key: 'ventes', shortcut: 'w', nav: { label: 'VENTES', items: [{ to: '/ventes/cockpit' }] } },
]

test('buildAppShortcuts: aucune app ne déclare `shortcut` ⇒ liste vide (comportement inchangé)', () => {
  const { bindings, conflicts } = buildAppShortcuts(
    [{ key: 'crm', nav: { label: 'CRM', items: [{ to: '/crm' }] } }],
    GOTO_SHORTCUTS,
  )
  assert.deepEqual(bindings, [])
  assert.deepEqual(conflicts, [])
})

test('buildAppShortcuts: un `shortcut` déclaré mène au cockpit de l’app', () => {
  const { bindings } = buildAppShortcuts(APPS, GOTO_SHORTCUTS)
  assert.deepEqual(
    bindings.map((b) => [b.keys, b.to]),
    [['g r', '/crm/cockpit'], ['g w', '/ventes/cockpit']],
  )
  assert.match(bindings[0].label, /CRM/)
})

test('buildAppShortcuts: le NOYAU gagne toujours, la collision est REMONTÉE', () => {
  const { bindings, conflicts } = buildAppShortcuts(
    [{ key: 'crm', shortcut: 'd', nav: { label: 'CRM', items: [{ to: '/crm/cockpit' }] } }],
    GOTO_SHORTCUTS,
  )
  assert.deepEqual(bindings, [])
  assert.deepEqual(conflicts, [{ keys: 'g d', app: 'crm', wins: 'noyau' }])
})

test('buildAppShortcuts: entre apps, l’ordre du registre tranche (et le perdant est listé)', () => {
  const { bindings, conflicts } = buildAppShortcuts([
    { key: 'crm', shortcut: 'r', nav: { label: 'CRM', items: [{ to: '/crm/cockpit' }] } },
    { key: 'rh', shortcut: 'R', nav: { label: 'RH', items: [{ to: '/rh' }] } },
  ], GOTO_SHORTCUTS)
  assert.deepEqual(bindings.map((b) => b.appKey), ['crm'])
  assert.deepEqual(conflicts, [{ keys: 'g r', app: 'rh', wins: 'crm' }])
})

test('buildAppShortcuts: tolère les entrées malformées (pas de lettre, pas de cockpit, rien)', () => {
  const { bindings } = buildAppShortcuts([
    null,
    { key: 'a', shortcut: 'ab', nav: { items: [{ to: '/a' }] } },   // pas UNE lettre
    { key: 'b', shortcut: '1', nav: { items: [{ to: '/b' }] } },    // pas une lettre
    { key: 'c', shortcut: 'z' },                                     // pas de cockpit
  ], GOTO_SHORTCUTS)
  assert.deepEqual(bindings, [])
  assert.deepEqual(buildAppShortcuts(null).bindings, [])
})

test('GLOBAL_SHORTCUTS: contient un raccourci "K" (⌘ ou Ctrl selon plateforme) et ?', () => {
  const keys = GLOBAL_SHORTCUTS.map((s) => s.keys)
  assert.ok(keys.some((k) => k.includes('K')))
  assert.ok(keys.includes('?'))
})

// VX73 — la plateforme RÉELLE de l'ERP est Windows/Linux : le glyphe ⌘ codé en
// dur mentait. quickSearchShortcutLabel() détecte la plateforme au lieu de
// supposer macOS.
test('isMacPlatform: détecte macOS via navigator.platform', () => {
  assert.equal(isMacPlatform({ platform: 'MacIntel' }), true)
  assert.equal(isMacPlatform({ platform: 'Win32' }), false)
  assert.equal(isMacPlatform({ platform: 'Linux x86_64' }), false)
  assert.equal(isMacPlatform(null), false)
  assert.equal(isMacPlatform(undefined), false)
})

test('isMacPlatform: retombe sur navigator.userAgentData.platform si présent', () => {
  assert.equal(isMacPlatform({ userAgentData: { platform: 'macOS' } }), true)
  assert.equal(isMacPlatform({ userAgentData: { platform: 'Windows' } }), false)
})

test('quickSearchShortcutLabel: "⌘ K" sur Mac, "Ctrl K" sur Windows/Linux (la plateforme réelle de l\'ERP)', () => {
  assert.equal(quickSearchShortcutLabel({ platform: 'MacIntel' }), '⌘ K')
  assert.equal(quickSearchShortcutLabel({ platform: 'Win32' }), 'Ctrl K')
  assert.equal(quickSearchShortcutLabel({ platform: 'Linux x86_64' }), 'Ctrl K')
})

// NTUX18 — cheatsheet enrichie : raccourcis d'édition (NTUX8) + recherche EN
// DIRECT filtrant les groupes de la cheatsheet.
test('EDIT_SHORTCUTS: bien formés (keys + libellé), couvre Tab/Maj+Tab/Entrée/Échap', () => {
  assert.ok(EDIT_SHORTCUTS.length >= 4)
  for (const s of EDIT_SHORTCUTS) {
    assert.ok(s.keys && s.keys.length > 0)
    assert.ok(s.label && s.label.length > 0)
  }
  const keys = EDIT_SHORTCUTS.map((s) => s.keys)
  assert.ok(keys.includes('Tab'))
  assert.ok(keys.includes('Entrée'))
  assert.ok(keys.includes('Échap'))
})

test('filterShortcutGroups: requête vide renvoie tous les groupes inchangés', () => {
  const groups = [{ title: 'Créer', items: CREATE_SHORTCUTS }, { title: 'Édition', items: EDIT_SHORTCUTS }]
  assert.deepEqual(filterShortcutGroups(groups, ''), groups)
  assert.deepEqual(filterShortcutGroups(groups, '   '), groups)
})

test('filterShortcutGroups: "créer" filtre vers les raccourcis de création (insensible à la casse)', () => {
  const groups = [
    { title: 'Créer', items: CREATE_SHORTCUTS },
    { title: 'Édition', items: EDIT_SHORTCUTS },
  ]
  const result = filterShortcutGroups(groups, 'CRÉER')
  assert.equal(result.length, 1)
  assert.equal(result[0].title, 'Créer')
  assert.equal(result[0].items.length, CREATE_SHORTCUTS.length)
})

test('filterShortcutGroups: un groupe sans correspondance disparaît entièrement', () => {
  const groups = [
    { title: 'Créer', items: CREATE_SHORTCUTS },
    { title: 'Édition', items: EDIT_SHORTCUTS },
  ]
  const result = filterShortcutGroups(groups, 'cellule')
  assert.deepEqual(result.map((g) => g.title), ['Édition'])
})

test('filterShortcutGroups: aucune correspondance nulle part renvoie une liste vide', () => {
  const groups = [{ title: 'Créer', items: CREATE_SHORTCUTS }]
  assert.deepEqual(filterShortcutGroups(groups, 'zzz-introuvable'), [])
})
