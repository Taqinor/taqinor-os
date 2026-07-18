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
    saveParametre: vi.fn(() => Promise.resolve({ data: {} })),
    getBaremes: vi.fn(() => Promise.resolve({ data: [] })),
    saveBareme: vi.fn(() => Promise.resolve({ data: {} })),
    getRubriques: vi.fn(() => Promise.resolve({ data: [] })),
    saveRubrique: vi.fn(() => Promise.resolve({ data: {} })),
    getProfils: vi.fn(() => Promise.resolve({ data: [] })),
    saveProfil: vi.fn(() => Promise.resolve({ data: {} })),
    getRegimesMutuelle: vi.fn(() => Promise.resolve({ data: [] })),
    saveRegimeMutuelle: vi.fn(() => Promise.resolve({ data: {} })),
    getAdhesionsMutuelle: vi.fn(() => Promise.resolve({ data: [] })),
    saveAdhesionMutuelle: vi.fn(() => Promise.resolve({ data: {} })),
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

/* WIR38 — `PaieParametres.jsx` ne permettait que le semis en masse (constantes,
   barème IR, rubriques, mutuelle) : aucune édition fine d'une seule ligne.
   On couvre ici les 4 dialogues ajoutés (pattern `RegimeExonerationDialog`),
   chacun câblé sur son `paieApi.save*` déjà construit côté serveur. */

describe('PaieParametres — ParametresTab (WIR38, édition fine d’une constante légale)', () => {
  const PARAM = {
    id: 7, date_effet: '2026-01-01', smig: '3111.00', plafond_cnss: '6000.00',
    taux_cnss_salarial: '0.0448', taux_amo_salarial: '0.0226',
    actif: true, valide_par_fondateur: true,
  }
  beforeEach(() => {
    paieApi.getParametres.mockResolvedValue(ok([PARAM]))
    paieApi.saveParametre.mockClear()
  })

  it('éditer une constante légale l’enregistre individuellement, sans re-seed complet',
    async () => {
      wrap(<PaieParametres />)
      // Onglet actif par défaut : Paramètres sociaux.
      const row = (await screen.findAllByText('2026-01-01'))
        .map((el) => el.closest('tr')).find(Boolean)
      expect(row).toBeTruthy()
      await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
      await userEvent.click(await screen.findByText('Éditer la constante'))

      const dialog = await screen.findByRole('dialog')
      const smigInput = within(dialog).getByLabelText('SMIG')
      await userEvent.clear(smigInput)
      await userEvent.type(smigInput, '3200')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

      await waitFor(() => expect(paieApi.saveParametre).toHaveBeenCalledWith(
        7, expect.objectContaining({ smig: 3200 })))
    })
})

describe('PaieParametres — BaremeTab (WIR38, édition d’un palier IR)', () => {
  const BAREME = {
    id: 11, libelle: 'Barème 2026', date_effet: '2026-01-01', actif: true,
    tranches: [
      { id: 101, borne_min: 0, borne_max: 3000, taux: 0, somme_a_deduire: 0, ordre: 1 },
      { id: 102, borne_min: 3001, borne_max: 5000, taux: 0.1, somme_a_deduire: 300, ordre: 2 },
    ],
  }
  beforeEach(() => {
    paieApi.getBaremes.mockResolvedValue(ok([BAREME]))
    paieApi.saveBareme.mockClear()
  })

  it('éditer un palier renvoie le tableau complet des tranches (les autres ne se perdent jamais)',
    async () => {
      wrap(<PaieParametres />)
      await userEvent.click(screen.getByRole('tab', { name: 'Barème IR' }))

      const editButtons = await screen.findAllByRole(
        'button', { name: 'Éditer le palier' })
      expect(editButtons).toHaveLength(2)
      await userEvent.click(editButtons[1]) // 2e palier (3 001 → 5 000)

      const dialog = await screen.findByRole('dialog')
      const tauxInput = within(dialog).getByLabelText(/^Taux/)
      await userEvent.clear(tauxInput)
      await userEvent.type(tauxInput, '0.12')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

      await waitFor(() => expect(paieApi.saveBareme).toHaveBeenCalled())
      const [baremeId, payload] = paieApi.saveBareme.mock.calls[0]
      expect(baremeId).toBe(11)
      // Le 1er palier (non édité) reste présent — jamais perdu.
      expect(payload.tranches).toHaveLength(2)
      expect(payload.tranches[0]).toMatchObject({ borne_min: 0, borne_max: 3000 })
      expect(payload.tranches[1]).toMatchObject({ taux: 0.12 })
    })
})

describe('PaieParametres — RubriquesTab (WIR38, édition fine d’une rubrique)', () => {
  const RUBRIQUE = {
    id: 21, code: 'PRIME', libelle: 'Prime', type: 'gain',
    imposable: true, soumis_cnss: true, soumis_amo: true, actif: true,
  }
  beforeEach(() => {
    paieApi.getRubriques.mockResolvedValue(ok([RUBRIQUE]))
    paieApi.saveRubrique.mockClear()
  })

  it('éditer une rubrique l’enregistre individuellement, sans re-seed complet',
    async () => {
      wrap(<PaieParametres />)
      await userEvent.click(screen.getByRole('tab', { name: 'Rubriques' }))

      const row = (await screen.findAllByText('PRIME'))
        .map((el) => el.closest('tr')).find(Boolean)
      expect(row).toBeTruthy()
      await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
      await userEvent.click(await screen.findByText('Éditer la rubrique'))

      const dialog = await screen.findByRole('dialog')
      const libelleInput = within(dialog).getByLabelText('Libellé')
      await userEvent.clear(libelleInput)
      await userEvent.type(libelleInput, 'Prime exceptionnelle')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

      await waitFor(() => expect(paieApi.saveRubrique).toHaveBeenCalledWith(
        21, expect.objectContaining({
          libelle: 'Prime exceptionnelle', code: 'PRIME',
        })))
    })
})

describe('PaieParametres — MutuelleTab (WIR38, édition fine d’un régime)', () => {
  const REGIME = {
    id: 31, libelle: 'Prévoyance groupe', mode: 'pourcentage',
    palier: 'celibataire', part_salariale: '50.00', part_patronale: '150.00',
    actif: true,
  }
  beforeEach(() => {
    paieApi.getRegimesMutuelle.mockResolvedValue(ok([REGIME]))
    paieApi.getAdhesionsMutuelle.mockResolvedValue(ok([]))
    paieApi.saveRegimeMutuelle.mockClear()
  })

  it('éditer un régime de mutuelle enregistre les modifications via saveRegimeMutuelle',
    async () => {
      wrap(<PaieParametres />)
      await userEvent.click(screen.getByRole('tab', { name: 'Mutuelle' }))

      const row = (await screen.findAllByText('Prévoyance groupe'))
        .map((el) => el.closest('tr')).find(Boolean)
      expect(row).toBeTruthy()
      await userEvent.click(within(row).getByLabelText("Plus d'actions sur la ligne"))
      await userEvent.click(await screen.findByText('Éditer le régime'))

      const dialog = await screen.findByRole('dialog')
      const partSalInput = within(dialog).getByLabelText('Part salariale')
      await userEvent.clear(partSalInput)
      await userEvent.type(partSalInput, '75')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

      await waitFor(() => expect(paieApi.saveRegimeMutuelle).toHaveBeenCalledWith(
        31, expect.objectContaining({ part_salariale: 75 })))
    })
})
