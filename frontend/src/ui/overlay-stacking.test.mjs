// Garde de superposition (z-index) — verrouille le contrat exposé par l'e2e
// (devis.spec « .ldp-panel .modal-close ») après que l'en-tête est devenu
// COLLANT (I136 : `.header { position: sticky; z-index: var(--z-sticky) }`).
//
// Règle : tout overlay plein écran (`fixed inset-0`) DOIT se situer au-dessus de
// l'en-tête collant. Le barème de profondeur (tokens.css) est :
//   --z-sticky 1100  <  --z-overlay 1200  <  --z-modal 1300  <  --z-popover 1400
// Les overlays doivent donc utiliser le barème (`z-[var(--z-overlay)]` / modal),
// jamais une valeur en dur < 1200 (z-50, z-[1000]…), sinon l'en-tête recouvre
// leur bord supérieur (bouton de fermeture inatteignable).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')

function walk(dir) {
  const out = []
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules' || e.name.startsWith('.')) continue
    const p = join(dir, e.name)
    if (e.isDirectory()) out.push(...walk(p))
    else if (/\.jsx$/.test(e.name)) out.push(p)
  }
  return out
}

test('tout overlay `fixed inset-0` est au-dessus de l\'en-tête collant (barème --z-*)', () => {
  const offenders = []
  for (const file of walk(SRC)) {
    const text = readFileSync(file, 'utf8')
    for (const line of text.split('\n')) {
      if (!line.includes('fixed inset-0')) continue
      // OK si l'overlay utilise le barème de tokens (z-[var(--z-overlay|modal|…)]).
      if (/z-\[var\(--z-(overlay|modal|popover|toast)\)\]/.test(line)) continue
      // Sinon, toute classe z en dur sous le tier overlay est interdite.
      if (/z-(\d+|\[\s*\d+\s*\])/.test(line)) {
        offenders.push(`${relative(SRC, file)} :: ${line.trim().slice(0, 100)}`)
      }
    }
  }
  assert.deepEqual(
    offenders,
    [],
    `Overlays plein écran sous l'en-tête collant (utiliser z-[var(--z-overlay)] / modal) :\n` +
      offenders.join('\n'),
  )
})

test('les overlays legacy d\'index.css (.modal-overlay) utilisent le barème --z-*', () => {
  // VX133 — `.ldp-overlay`/`.ldp-panel` bespoke sont retirés d'index.css : les
  // deux consommateurs (LeadDevisPanel, InstallationDetail) sont migrés sur
  // `Sheet`/`SheetContent`, dont l'overlay Radix (`z-[var(--z-overlay)]`,
  // Sheet.jsx) est déjà couvert par le test `fixed inset-0` ci-dessus.
  const css = readFileSync(join(SRC, 'index.css'), 'utf8')
  const block = (name) => {
    const m = css.match(new RegExp(`\\${name}\\s*\\{([^}]*)\\}`))
    return m ? m[1] : ''
  }
  const modal = block('.modal-overlay')
  assert.match(modal, /z-index:\s*var\(--z-(overlay|modal)/, '.modal-overlay doit utiliser var(--z-overlay|modal)')
})
