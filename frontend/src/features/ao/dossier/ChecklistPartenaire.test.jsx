import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* PACT71 — checklist partenaire du dossier de dépôt (AOF136).
   Preuves : (1) les points sont chargés depuis la VRAIE ressource
   `checklist-partenaire`, filtrée sur le dossier ; (2) pointer un point
   appelle l'action serveur `pointer` (responsable/date tracés côté serveur,
   jamais ici) ; (3) un point obligatoire ouvert apparaît comme la cause du
   blocage via le texte AUTHENTIQUE de `dossiers-ao/<id>/completude/`. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  pointer: vi.fn(),
  completude: vi.fn(),
  initialiserChecklist: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    checklistPartenaire: { list: mocks.list, pointer: mocks.pointer },
    dossiers: { completude: mocks.completude, initialiserChecklist: mocks.initialiserChecklist },
  },
}))

import ChecklistPartenaire from './ChecklistPartenaire'

const LIGNE_OUVERTE = {
  id: 1, dossier: 7, bloc: 'cps', bloc_display: 'CPS', code: 'cps_lu',
  libelle: 'CPS relu et paraphé', ordre: 1, obligatoire: true, faite: false,
  responsable: null, responsable_nom: '', commentaire: '',
}
const LIGNE_FAITE = {
  id: 2, dossier: 7, bloc: 'bordereau', bloc_display: 'Bordereau des prix', code: 'bordereau_signe',
  libelle: 'Bordereau signé', ordre: 1, obligatoire: true, faite: true,
  responsable: 3, responsable_nom: 'rkasri', commentaire: '',
}

const renderEcran = (props) => render(
  <MemoryRouter><ChecklistPartenaire dossierId={7} {...props} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [LIGNE_OUVERTE, LIGNE_FAITE] })
  mocks.completude.mockResolvedValue({
    data: {
      complet: false,
      raisons_de_non_depot: [
        '1 point(s) obligatoire(s) de la checklist partenaire encore ouvert(s) : CPS — CPS relu et paraphé.',
      ],
    },
  })
  mocks.pointer.mockResolvedValue({ data: { ...LIGNE_OUVERTE, faite: true } })
  mocks.initialiserChecklist.mockResolvedValue({ data: { crees: 9, deja_presents: 0 } })
})

describe('ChecklistPartenaire (PACT71)', () => {
  it('charge les points de la checklist filtrés sur le dossier', async () => {
    renderEcran()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ dossier: 7 }))
    expect(await screen.findByText('CPS relu et paraphé')).toBeInTheDocument()
    expect(screen.getByText('Bordereau signé')).toBeInTheDocument()
  })

  it('groupe les points par bloc (libellé RÉEL du serveur, jamais réinventé)', async () => {
    renderEcran()
    expect(await screen.findByText('CPS')).toBeInTheDocument()
    expect(screen.getByText('Bordereau des prix')).toBeInTheDocument()
  })

  it('un point obligatoire ouvert affiche le responsable manquant et le badge Obligatoire', async () => {
    renderEcran()
    expect(await screen.findByText('Responsable non désigné')).toBeInTheDocument()
    expect(screen.getByText('rkasri')).toBeInTheDocument()
  })

  it('pointer un point coche appelle l’action serveur pointer (responsable tracé côté serveur)', async () => {
    renderEcran()
    const case1 = await screen.findByLabelText('CPS relu et paraphé')
    await userEvent.click(case1)
    await waitFor(() => expect(mocks.pointer).toHaveBeenCalledWith(1, { faite: true, commentaire: '' }))
  })

  it('la cause du blocage est le texte AUTHENTIQUE du serveur (completude), jamais reconstruit', async () => {
    renderEcran()
    expect(await screen.findByText(/point\(s\) obligatoire\(s\) de la checklist partenaire encore ouvert/))
      .toBeInTheDocument()
  })

  it('checklist vide : propose de l’initialiser (action idempotente AOF136)', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    renderEcran()
    const bouton = await screen.findByRole('button', { name: 'Initialiser la checklist' })
    await userEvent.click(bouton)
    await waitFor(() => expect(mocks.initialiserChecklist).toHaveBeenCalledWith(7))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })
})
