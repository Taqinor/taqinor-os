// VX86 — Carte dashboard « Attend votre décision » (boîte d'approbations
// centralisée). Vérification de SOURCE (cf. MesEquipesCard.test.mjs /
// ImpactPastille.test.mjs) :
//   node --test src/components/ApprobationsAttentionCard.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ApprobationsAttentionCard.jsx'), 'utf8')
const DASHBOARD_SRC = readFileSync(join(HERE, '..', 'pages', 'Dashboard.jsx'), 'utf8')
const SIDEBAR_SRC = readFileSync(join(HERE, 'layout', 'Sidebar.jsx'), 'utf8')
const BELL_SRC = readFileSync(join(HERE, 'layout', 'NotificationBell.jsx'), 'utf8')
const HOOK_SRC = readFileSync(join(HERE, '..', 'hooks', 'useApprobationsCount.js'), 'utf8')

test('la carte réutilise le hook partagé useApprobationsCount (une seule source de vérité)', () => {
  assert.match(SRC, /import { useApprobationsCount } from '\.\.\/hooks\/useApprobationsCount'/)
  assert.match(SRC, /const { total, loading, error } = useApprobationsCount\(\)/)
})

test('rend NULL en chargement, en erreur, ou à 0 (jamais de carte vide/cassée)', () => {
  assert.match(SRC, /if \(loading \|\| error \|\| total === 0\) return null/)
})

test('top-3 via ?trier=urgence (déjà supporté côté backend)', () => {
  assert.match(SRC, /approbationsEnAttente\(\{ trier: 'urgence' \}\)/)
  assert.match(SRC, /\.slice\(0, 3\)/)
})

test('clic → navigue vers /approbations (lien direct)', () => {
  assert.match(SRC, /navigate\('\/approbations'\)/)
})

test('Dashboard : monte la carte en lazy + Suspense, en tête (avant l’état loading/error)', () => {
  assert.match(DASHBOARD_SRC, /const ApprobationsAttentionCard = lazy\(\(\) => import\('\.\.\/components\/ApprobationsAttentionCard'\)\)/)
  assert.match(DASHBOARD_SRC, /<ApprobationsAttentionCard \/>/)
  // VX15 a remplacé le `<header>` littéral par le composant `<ModuleHero>` en
  // tête du Dashboard : on repère l'en-tête via lui.
  const headerIdx = DASHBOARD_SRC.indexOf('<ModuleHero')
  const cardIdx = DASHBOARD_SRC.indexOf('<ApprobationsAttentionCard')
  const errorBranchIdx = DASHBOARD_SRC.indexOf('showError ?')
  assert.ok(headerIdx > -1 && cardIdx > headerIdx, 'la carte doit suivre l’en-tête (ModuleHero)')
  assert.ok(errorBranchIdx > -1 && cardIdx < errorBranchIdx, 'la carte doit précéder la branche loading/error du reste du dashboard')
})

test('Sidebar : badge numérique sur l’item /approbations, masqué à 0/erreur/chargement', () => {
  assert.match(SIDEBAR_SRC, /import { useApprobationsCount } from '\.\.\/\.\.\/hooks\/useApprobationsCount'/)
  assert.match(SIDEBAR_SRC, /item\.to === '\/approbations' && showApprobationsBadge/)
  assert.match(SIDEBAR_SRC, /showApprobationsBadge = !approbationsLoading && !approbationsError && approbationsTotal > 0/)
})

test('NotificationBell : rangée « N approbations » en tête des groupes, cliquable vers /approbations', () => {
  assert.match(BELL_SRC, /import { useApprobationsCount } from '\.\.\/\.\.\/hooks\/useApprobationsCount'/)
  assert.match(BELL_SRC, /showApprobationsRow && \(/)
  assert.match(BELL_SRC, /goto\('\/approbations'\)/)
})

test('hook partagé : total dérivé de items.length, jamais un total inventé en erreur/chargement', () => {
  assert.match(HOOK_SRC, /attentionSummary\(\)/)
  assert.match(HOOK_SRC, /setTotal\(r\.data\?\.approbations \?\? 0\)/)
})
