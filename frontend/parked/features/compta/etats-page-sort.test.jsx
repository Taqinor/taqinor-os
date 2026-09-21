import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* VX232(b) — EtatsPage.jsx : `GenericTable` migre du <table> HTML nu vers le
   primitif partagé `pages/reporting/Table.jsx` ; en prime un clic sur un
   en-tête trie la colonne (une balance rendue reste un ordre serveur figé
   sinon). Aucun appel réseau réel — comptaApi est mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const empty = () => Promise.resolve({ data: [] })

vi.mock('../../api/comptaApi', () => ({
  default: {
    downloadBlob: vi.fn(),
    exercices: { list: empty },
    etats: {
      balance: () => Promise.resolve({
        data: {
          lignes: [
            { compte: '7111', libelle: 'Ventes', debit: 0, credit: 5000 },
            { compte: '6111', libelle: 'Achats', debit: 2000, credit: 0 },
          ],
        },
      }),
      grandLivre: empty, cpc: empty, bilan: empty, esg: empty, etic: empty,
      tableauFlux: empty, tableauImmobilisations: empty, journalItems: empty,
      balanceAgeeFournisseurs: empty, continuiteSequences: empty, controleIce: empty,
      dossierCloture: empty,
    },
  },
}))

function mount(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('EtatsPage — GenericTable migré au primitif Table partagé, tri au clic (VX232)', () => {
  it('rend la balance via le tableau partagé (pas un <table> nu) et trie au clic d’en-tête', async () => {
    const { default: EtatsPage } = await import('./pages/EtatsPage.jsx')
    mount(<EtatsPage />)

    // Ordre serveur : « 7111 » (Ventes) avant « 6111 » (Achats).
    const firstCompteCell = await screen.findByText('7111')
    let rows = firstCompteCell.closest('table').querySelectorAll('tbody tr')
    expect(within(rows[0]).getByText('7111')).toBeInTheDocument()

    // report-table est le nom de classe posé par le primitif partagé.
    expect(firstCompteCell.closest('table')).toHaveClass('report-table')

    // Clic sur l'en-tête « compte » → tri ascendant → « 6111 » passe en tête.
    fireEvent.click(screen.getByRole('button', { name: /^compte/ }))
    await waitFor(() => {
      rows = firstCompteCell.closest('table').querySelectorAll('tbody tr')
      expect(within(rows[0]).getByText('6111')).toBeInTheDocument()
    })
  }, 30000)
})
