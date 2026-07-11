// Garde-fou VX53 — compat tactile des affordances hover.
//
// Bug visé : sur écran tactile (pas de vrai survol), un `:hover` non gardé
// reste "collé" après un tap (sticky hover) — le bouton/lien garde l'état
// visuel de survol jusqu'au tap suivant ailleurs. Le correctif enveloppe
// chaque `:hover` porteur d'affordance dans `@media (hover: hover)` : la
// règle ne s'applique alors que sur un vrai pointeur fin (souris), jamais
// sur tactile. Ce test verrouille l'invariant : aucun `:hover` ne doit
// rester déclaré hors d'un bloc `@media (hover: hover)` dans les deux
// fichiers balayés par VX53.
//
// Exécuté en CI : node --test src/hover-compat.layout.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

// Retire les commentaires CSS avant analyse (un commentaire peut mentionner
// ":hover" en prose sans que ce soit une vraie règle).
function stripComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, '')
}

// Repère chaque règle brute "sélecteur { … }" au niveau racine (pas dans un
// @media) qui porte un :hover dans son sélecteur — ce sont les hover NON
// gardés que VX53 doit avoir éliminés.
function unguardedHoverSelectors(rawSource) {
  const source = stripComments(rawSource)
  const found = []
  let i = 0
  const n = source.length
  while (i < n) {
    const ch = source[i]
    if (ch === '@') {
      // Saute tout le bloc @-rule (statement ou bloc) sans l'inspecter — les
      // :hover DANS un @media (hover: hover) sont par définition gardés.
      let j = i
      while (j < n && source[j] !== '{' && source[j] !== ';') j++
      if (source[j] === ';') { i = j + 1; continue }
      let depth = 1
      let k = j + 1
      while (k < n && depth > 0) {
        if (source[k] === '{') depth++
        else if (source[k] === '}') depth--
        k++
      }
      i = k
      continue
    }
    if (/\s/.test(ch)) { i++; continue }
    const brace = source.indexOf('{', i)
    if (brace === -1) break
    const selector = source.slice(i, brace)
    let depth = 1
    let k = brace + 1
    while (k < n && depth > 0) {
      if (source[k] === '{') depth++
      else if (source[k] === '}') depth--
      k++
    }
    if (selector.includes(':hover')) found.push(selector.trim())
    i = k
  }
  return found
}

test('index.css : aucun :hover non gardé par @media (hover: hover)', () => {
  const css = readFileSync(join(here, 'index.css'), 'utf8')
  const unguarded = unguardedHoverSelectors(css)
  assert.deepEqual(unguarded, [],
    `:hover non gardé(s) trouvé(s) dans index.css (doivent être dans @media (hover: hover)) : ${unguarded.join(' | ')}`)
})

test('records-panels.css : aucun :hover non gardé par @media (hover: hover)', () => {
  const css = readFileSync(join(here, 'components', 'records-panels.css'), 'utf8')
  const unguarded = unguardedHoverSelectors(css)
  assert.deepEqual(unguarded, [],
    `:hover non gardé(s) trouvé(s) dans records-panels.css : ${unguarded.join(' | ')}`)
})

test('AgentChat.jsx : la hauteur plein-écran utilise dvh (repli barre d’URL iOS)', () => {
  const jsx = readFileSync(join(here, 'pages', 'ia', 'AgentChat.jsx'), 'utf8')
  assert.ok(jsx.includes('h-[calc(100dvh-7rem)]'),
    'AgentChat doit utiliser 100dvh (et non 100vh) pour ne pas déborder sous la barre d’URL iOS')
  assert.ok(!jsx.includes('h-[calc(100vh-7rem)]'),
    'AgentChat ne doit plus utiliser 100vh (remplacé par 100dvh)')
})
