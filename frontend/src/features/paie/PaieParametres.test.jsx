import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR3 — l'onboarding paie (création/édition d'un ProfilPaie) n'existait pas
   hors Django admin : ProfilsTab n'offrait que les dialogues étroits STC et
   Régime d'exonération. On couvre ici (a) l'ouverture du dialogue de création
   depuis le bouton « Nouveau profil » et (b) l'édition d'un profil existant
   via l'action de ligne, câblée sur `paieApi.saveProfil` (déjà create-or-
   update côté serveur). L'API paie + rh est mockée : aucun appel réseau réel. */
const ok = (data) => Promise.resolve({ data })

vi.mock('../../api/paieApi', () => ({
  default: {
    getParametres: vi.fn(() => Promise.resolve({ data: [] })),
    getBaremes: vi.fn(() => Promise.resolve({ data: [] })),
    getRubriques: vi.fn(() => Promise.resolve({ data: [] })),
    getProfils: vi.fn(() => Promise.resolve({ data: [] })),
    saveProfil: vi.fn(() => Promise.resolve({ data: {} })),
    getRegimesMutuelle: vi.fn(() => Promise.resolve({ data: [] })),
    getAdhesionsMutuelle: vi.fn(() => Promise.resolve({ data: [] })),
    getPeriodes: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/rhApi', () => ({
  default: {
    getEmployes: vi.fn(() => Promise.resolve({
      data: [{ id: 5, nom: 'Amrani', prenom: 'Yassine' }],
    })),
  },
}))

import paieApi from '../../api/paieApi'
import PaieParametres from './PaieParametres.jsx'

function wrap(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>,
  )
}

const PROFIL = {
  id: 42, employe: 5, employe_nom: 'Amrani Yassine',
  type_remuneration: 'mensuel', salaire_base: '6000.00',
  numero_cnss: '', banque: '', rib: '',
  affilie_cnss: true, affilie_amo: true, affilie_cimr: false,
  regime_exoneration: 'aucun', actif: true,
}

describe('PaieParametres — ProfilsTab (WIR3, onboarding paie)', () => {
  beforeEach(() => {
    paieApi.getProfils.mockResolvedValue(ok([]))
    paieApi.saveProfil.mockClear()
  })

  it('bouton « Nouveau profil » ouvre le dialogue de création', async () => {
    wrap(<PaieParametres />)
    await userEvent.click(screen.getByRole('tab', { name: 'Profils' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Nouveau profil' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Nouveau profil de paie')).toBeInTheDocument()
    expect(within(dialog).getByText('Employé')).toBeInTheDocument()
  })

  it('éditer un profil existant enregistre les modifications via saveProfil', async () => {
    paieApi.getProfils.mockResolvedValue(ok([PROFIL]))
    wrap(<PaieParametres />)
    await userEvent.click(screen.getByRole('tab', { name: 'Profils' }))

    const row = (await screen.findAllByText('Amrani Yassine'))
      .map((el) => el.closest('tr')).find(Boolean)
    expect(row).toBeTruthy()
    await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
    await userEvent.click(await screen.findByText('Éditer le profil'))

    const dialog = await screen.findByRole('dialog')
    const ribInput = within(dialog).getByLabelText('RIB')
    await userEvent.clear(ribInput)
    await userEvent.type(ribInput, '011780000012345678901234')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(paieApi.saveProfil).toHaveBeenCalledWith(
      42, expect.objectContaining({ rib: '011780000012345678901234' })))
    // L'employé n'est jamais renvoyé en édition (OneToOne immuable).
    expect(paieApi.saveProfil.mock.calls[0][1]).not.toHaveProperty('employe')
  })
})
