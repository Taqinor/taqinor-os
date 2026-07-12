import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* VX229 — `CrudDialog` apprend le Combobox : fin des champs FK « (ID) » tapés
   à la main. Vérifie que (a) le champ Employé de NotesDeFraisPage rend un
   vrai Combobox de recherche « Nom Prénom » (pas un <input> texte), et (b)
   une retenue de garantie référence un tiers RÉEL (Combobox du répertoire
   unifié) au lieu d'un champ texte libre — le tiers choisi est bien envoyé
   (tiers_id/tiers_type/tiers_nom dérivé) à la création. Aucun appel réseau
   réel — comptaApi/rhApi/api(axios) sont mockés. */

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
const res = () => ({ list: empty, get: empty, create: empty, update: empty, remove: empty })

const notesFraisCreate = vi.fn().mockResolvedValue({ data: {} })
const retenueCreate = vi.fn().mockResolvedValue({ data: {} })

vi.mock('../../api/comptaApi', () => ({
  default: {
    downloadBlob: vi.fn(),
    notesFrais: { ...res(), create: (p) => notesFraisCreate(p) },
    rapportsNotesFrais: res(),
    plafondsNotesFrais: res(),
    baremesIndemnite: res(),
    indemnitesChantier: res(),
    retenuesGarantie: {
      ...res(),
      create: (p) => retenueCreate(p),
    },
    cautionsBancaires: res(),
    contratsAvancement: res(),
    travauxEnCours: res(),
    commissionPayoutRuns: res(),
    compensations: res(),
    provisionsPeriode: { rapport: () => Promise.resolve({ data: { lignes: [] } }) },
    pistesAudit: res(),
  },
}))

vi.mock('../../api/rhApi', () => ({
  default: {
    getEmployes: () => Promise.resolve({
      data: [{ id: 7, nom: 'Alaoui', prenom: 'Yassine' }],
    }),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: (url) => {
      if (url === '/tiers/tiers/') {
        return Promise.resolve({
          data: [{ id: 3, type_tiers: 'entreprise', raison_sociale: 'SOMACHOR SA', nom: 'SOMACHOR SA' }],
        })
      }
      return Promise.resolve({ data: [] })
    },
  },
}))

function mount(ui) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: 'Directeur', permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('CrudDialog — champ async Combobox (VX229)', () => {
  it('NotesDeFraisPage : le champ Employé est un Combobox « Nom Prénom », plus un <input> ID', async () => {
    const { default: NotesDeFraisPage } = await import('./pages/NotesDeFraisPage.jsx')
    mount(<NotesDeFraisPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Nouveau note de frais/ }))

    const combobox = await screen.findByRole('combobox')
    expect(combobox).toBeInTheDocument()
    // Aucun <input id="cd-employe"> — le champ FK "(ID)" a disparu (le
    // déclencheur du Combobox garde l'id mais est un <button>, pas un <input>).
    expect(document.querySelector('input#cd-employe')).toBeNull()

    fireEvent.click(combobox)
    fireEvent.click(await screen.findByText('Alaoui Yassine'))
    expect(screen.getByRole('combobox')).toHaveTextContent('Alaoui Yassine')
  }, 30000)

  it('EngagementsPage : une retenue de garantie référence un tiers réel (traçable, pas du texte libre)', async () => {
    const { default: EngagementsPage } = await import('./pages/EngagementsPage.jsx')
    mount(<EngagementsPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle RG/ }))

    // Plus de champ texte libre « Maître d'ouvrage » — un Combobox du répertoire tiers.
    expect(document.querySelector('#cd-tiers_nom')).toBeNull()
    const combobox = await screen.findByRole('combobox', { name: /Maître d.ouvrage/ })
    fireEvent.click(combobox)
    fireEvent.click(await screen.findByText('SOMACHOR SA'))

    fireEvent.change(document.querySelector('#cd-date_constitution'), { target: { value: '2026-07-01' } })
    fireEvent.change(document.querySelector('#cd-base'), { target: { value: '10000' } })

    fireEvent.click(screen.getByRole('button', { name: /^Enregistrer$/ }))

    await waitFor(() => {
      expect(retenueCreate).toHaveBeenCalledWith(expect.objectContaining({
        tiers_id: 3, tiers_type: 'entreprise', tiers_nom: 'SOMACHOR SA',
      }))
    })
  }, 30000)
})
