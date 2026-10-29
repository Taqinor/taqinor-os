/* ENF19 — socle commun des tests SectionsPane (lead change + rendu des
   sections) : nettoyage après test et props de base, écrits une seule fois. */
import { vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Le repli des sections est PERSISTÉ (localStorage `taqinor.lw.collapsed`) et
// les choix de l'utilisatrice priment sur le repli automatique : sans ce
// nettoyage, un test qui replie une section dicterait l'état d'ouverture de
// tous les suivants. À passer à `afterEach`.
export function nettoyerSectionsPane() {
  cleanup()
  vi.clearAllMocks()
  try { localStorage.clear() } catch { /* noop */ }
}

export function sectionsPaneBase(mode) {
  return {
    setField: vi.fn(),
    errors: {},
    mode,
    refData: { users: [], tagOptions: [], motifOptions: [] },
  }
}
