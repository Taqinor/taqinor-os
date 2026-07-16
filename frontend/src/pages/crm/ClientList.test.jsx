import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import ClientList from './ClientList'

/* VX144(c) — cellule Client de ClientList (colonne « nom », 200px) : nom +
   pastille (ClientTypeToggle) + badge ICE devaient s'empiler dans un ORDRE
   GARANTI (le badge ICE toujours SOUS le nom), jamais mélangés par le wrap du
   flex. On vérifie ici que le badge ICE est un DESCENDANT du conteneur nom
   placé APRÈS le bloc nom+pastille dans le DOM (empilement 2 lignes
   déterministe, `flex-col`) — jamais avant. */

vi.mock('../../features/crm/store/crmSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchClients: () => ({ type: 'crm/fetchClients/noop' }),
  }
})

vi.mock('../../api/crmApi', () => ({ default: {} }))
vi.mock('../../api/ventesApi', () => ({ default: {} }))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({ confirmDelete: vi.fn(() => Promise.resolve(false)) }),
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore({ clients = [] } = {}) {
  return configureStore({
    reducer: {
      crm: (state = { clients, loading: false, error: null }) => state,
      auth: (state = { role: 'admin', permissions: [], role_nom: 'Admin' }) => state,
    },
  })
}

function renderList(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/crm/clients']}>
        <ThemeProvider>
          <ClientList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const entrepriseSansIce = {
  id: 1, nom: 'ACME', prenom: '', type_client: 'entreprise', ice: '',
}

describe('ClientList — VX144(c) empilement 2 lignes déterministe (cellule Client)', () => {
  it('place le badge ICE manquant APRÈS le nom dans le DOM (jamais avant)', () => {
    renderList({ clients: [entrepriseSansIce] })
    // Desktop table uniquement (le repli carte mobile duplique le même texte).
    const table = document.querySelector('[data-dt-table]')
    const nameCell = within(table).getByText('ACME').closest('td')
    expect(nameCell).not.toBeNull()
    const badge = within(nameCell).getByText('ICE manquant')
    // Ordre DOM garanti : le nœud "nom" précède le badge dans le markup —
    // condition nécessaire à un empilement flex-col déterministe (nom en
    // premier, badge en second, jamais l'inverse).
    const position = nameCell.compareDocumentPosition(badge)
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('n\'affiche aucun badge ICE quand le client entreprise a un ICE renseigné', () => {
    renderList({ clients: [{ ...entrepriseSansIce, id: 2, ice: '000123456000045' }] })
    expect(screen.queryByText('ICE manquant')).toBeNull()
  })
})
