import { test } from 'node:test'
import assert from 'node:assert/strict'

import viteConfig from '../../vite.config.js'

// VX59 — Le plugin `roofBuilderTsPlugin` (vite.config.js) routait auparavant
// les fichiers TS du builder roof-tool vers un id virtuel encodant le chemin
// ABSOLU du disque local (`\0rb:<chemin-absolu-encodé>`), qui fuyait tel quel
// dans le nom du chunk émis par Rollup si `manualChunks` n'avait pas de règle
// dédiée — non portable entre machines/CI et publiant la structure du disque
// local dans un asset. Ce test verrouille les deux garanties attendues :
//   1) `manualChunks` regroupe TOUJOURS les ids virtuels du builder (préfixe
//      `\0rb:`) sous le nom FIXE `roof-tool`, quel que soit le chemin encodé
//      (donc quelle que soit la machine/le point de montage du dépôt) ;
//   2) le nom de chunk ne contient JAMAIS l'un des fragments de chemin
//      absolu qui auraient fuité avec l'ancien encodage (ex. lettre de
//      lecteur Windows, `C%3A`, ou tout chemin brut passé en id).
const RB_PREFIX = '\0rb:'
const manualChunks = viteConfig.build.rollupOptions.output.manualChunks

test('manualChunks groups every roof-tool virtual id under the fixed name "roof-tool"', () => {
  const idsFromDifferentMachinePaths = [
    `${RB_PREFIX}scripts%2Froof-tool-pro11.ts`,
    `${RB_PREFIX}scripts%2FroofPro11%2Fscene3d.ts`,
  ]
  for (const id of idsFromDifferentMachinePaths) {
    assert.equal(manualChunks(id), 'roof-tool')
  }
})

test('manualChunks output is identical across two different absolute-path encodings of the same relative file', () => {
  // Simule ce que produiraient deux machines/CI différentes AVANT le fix :
  // deux chemins absolus distincts pour le même fichier logique.
  const idOnMachineA = `${RB_PREFIX}${encodeURIComponent('C:/dev/taqinor-os/apps/web/src/scripts/roof-tool-pro11.ts')}`
  const idOnMachineB = `${RB_PREFIX}${encodeURIComponent('/home/ci/runner/work/apps/web/src/scripts/roof-tool-pro11.ts')}`
  const chunkA = manualChunks(idOnMachineA)
  const chunkB = manualChunks(idOnMachineB)
  assert.equal(chunkA, chunkB)
  assert.equal(chunkA, 'roof-tool')
})

test('the fixed chunk name never leaks an absolute disk path fragment', () => {
  const id = `${RB_PREFIX}${encodeURIComponent('C:/dev/taqinor-os/.claude/worktrees/agent-a0437c5c4815a58e9/apps/web/src/scripts/roof-tool-pro11.ts')}`
  const chunkName = manualChunks(id)
  assert.ok(!chunkName.includes('C%3A'))
  assert.ok(!chunkName.includes('worktrees'))
  assert.ok(!chunkName.includes('dev'))
  assert.equal(chunkName, 'roof-tool')
})

test('manualChunks leaves non-roof-tool, non-vendor ids untouched (default per-route splitting)', () => {
  assert.equal(manualChunks('/frontend/src/pages/ventes/DevisListe.jsx'), undefined)
})
