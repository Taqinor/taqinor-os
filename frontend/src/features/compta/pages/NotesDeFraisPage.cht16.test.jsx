import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CHT16 — Indemnités de frais rattachées au VRAI chantier.
   ----------------------------------------------------------------------------
   L'onglet « Indemnités chantier » de NotesDeFraisPage remplaçait le chantier
   par un texte libre (`libelle_chantier` tapé à la main, jamais rapproché
   d'un vrai enregistrement `installations.Installation`). `ChantierSelect`
   (réutilisé de btp_chantier, patron déjà éprouvé par VisasDocuments) rend
   maintenant une VRAIE sélection de chantier (`installation_id`, validé
   société côté serializer — voir apps/compta/tests/
   test_cht16_indemnite_chantier_installation.py) ; `libelle_chantier` reste
   le repli/héritage pour les enregistrements antérieurs à CHT16, toujours
   affiché tel quel dans la colonne « Chantier ».

   Contrat partagé (PACT10) : la charge utile d'exemple vient du MÊME fichier
   que le backend affirme (`apps/compta/contract_samples/
   indemnite_chantier.json`) — jamais un objet inventé à la main.
   ========================================================================== */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// PACT10 — l'exemple committé, lu depuis le fichier réel (jamais recopié).
const INDEMNITE_CHANTIER_EXEMPLE = exempleContrat('compta', 'indemnite_chantier')

const mocks = vi.hoisted(() => ({
  indemnitesChantierList: vi.fn(),
  indemnitesChantierCreate: vi.fn(() => Promise.resolve({ data: { id: 900 } })),
}))

const empty = () => Promise.resolve({ data: [] })
const res = () => ({ list: empty, create: empty, update: empty })

vi.mock('../../../api/comptaApi', () => ({
  default: {
    downloadBlob: vi.fn(),
    notesFrais: res(),
    rapportsNotesFrais: res(),
    plafondsNotesFrais: res(),
    baremesIndemnite: res(),
    indemnitesChantier: {
      list: (...args) => mocks.indemnitesChantierList(...args),
      create: (...args) => mocks.indemnitesChantierCreate(...args),
      update: () => Promise.resolve({ data: {} }),
    },
  },
}))

vi.mock('../../../api/rhApi', () => ({
  default: {
    getEmployes: () => Promise.resolve({
      data: [{ id: 7, nom: 'Alaoui', prenom: 'Yassine' }],
    }),
  },
}))

// ChantierSelect (btp_chantier/useChantiers.js) lit ce client — un seul
// chantier réel, jamais un texte libre.
vi.mock('../../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 88, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import NotesDeFraisPage from './NotesDeFraisPage.jsx'

function withProviders(ui, { route = '/frais?onglet=indemnitesChantier' } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.indemnitesChantierList.mockResolvedValue({
    data: [
      // Enregistrement LEGACY (antérieur à CHT16) : pas d'installation_id,
      // seulement le repli `libelle_chantier` — doit rester intact.
      {
        id: 12, reference: 'IND-202601-0003', employe_nom: 'Yassine Amrani',
        libelle_chantier: 'Chantier historique Rabat', installation_id: null,
        date_deplacement: '2026-01-05', montant_total: '250.00', statut: 'brouillon',
      },
    ],
  })
})

describe('NotesDeFraisPage — Indemnités chantier (CHT16)', () => {
  it('sélectionne un VRAI chantier (ChantierSelect) au lieu du texte libre', async () => {
    withProviders(<NotesDeFraisPage />)
    fireEvent.click(await screen.findByRole('button', { name: /Nouveau/ }))

    // Le sélecteur de chantier réutilisé de btp_chantier — pas un champ texte.
    const chantierSelect = await screen.findByLabelText('Chantier')
    expect(chantierSelect.tagName).toBe('SELECT')
    expect(document.querySelector('#cd-libelle_chantier')).toBeNull()

    const user = userEvent.setup()
    await user.selectOptions(
      chantierSelect,
      within(chantierSelect).getByRole('option', { name: /Villa Zenith/ }))

    // Employé : Combobox réel (patron VX229 déjà éprouvé). `getByRole` est
    // scopé par nom — le `<select>` du chantier est LUI AUSSI un
    // `combobox` ARIA implicite (élément `<select>` natif).
    const employeCombobox = screen.getByRole('combobox', { name: 'Employé' })
    fireEvent.click(employeCombobox)
    fireEvent.click(await screen.findByText('Alaoui Yassine'))

    fireEvent.change(document.querySelector('#ic-date'), { target: { value: '2026-09-10' } })

    fireEvent.click(screen.getByRole('button', { name: /^Enregistrer$/ }))

    await waitFor(() => {
      expect(mocks.indemnitesChantierCreate).toHaveBeenCalledWith(
        expect.objectContaining({ installation_id: '88', employe: 7 }))
    })
  })

  it('un enregistrement antérieur à CHT16 (sans installation_id) reste affiché via son libellé legacy', async () => {
    withProviders(<NotesDeFraisPage />)
    await waitFor(() => expect(
      screen.getAllByText('Chantier historique Rabat').length).toBeGreaterThan(0))
  })

  it('le contrat committé porte bien `installation_id` (PACT10 — contre le mock inventé)', () => {
    expect(INDEMNITE_CHANTIER_EXEMPLE).toHaveProperty('installation_id')
    expect(INDEMNITE_CHANTIER_EXEMPLE).toHaveProperty('libelle_chantier')
  })
})
