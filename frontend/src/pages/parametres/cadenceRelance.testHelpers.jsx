/* Harnais partagé des tests CadenceRelanceEditor.* (ENF19). */
import { vi, beforeEach, afterEach } from 'vitest'
import { render, act, cleanup } from '@testing-library/react'
import { createElement } from 'react'
import { ThemeProvider } from '../../design/ThemeProvider'

/** parametresApi minimal : aucun message, aucune étape, écriture acceptée. */
export const cadenceApiVide = () => ({
  default: {
    getMessages: vi.fn(async () => ({ data: [] })),
    getCadenceRelance: vi.fn(async () => ({ data: [] })),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
})

/** Monte l'éditeur dans son thème et attend la fin des effets de montage. */
export async function monterEditeur(Editor) {
  await act(async () => {
    render(
      <ThemeProvider>
        {createElement(Editor)}
      </ThemeProvider>,
    )
  })
}

/** Remet les appels à zéro avant chaque test et démonte après. */
export function declarerHooksCadence(parametresApi) {
  beforeEach(() => {
    parametresApi.getCadenceRelance.mockClear()
    parametresApi.updateCadenceRelanceEtape.mockClear()
  })
  afterEach(() => cleanup())
}
