// EDC6 (suite, mesuré en direct le 09/10/2026) — le rappel DIFFÉRÉ de Radix.
// Sur un pointeur tactile (tablette, téléphone — et le navigateur de test),
// `DismissableLayer` reporte « pointeur hors panneau » à l'événement `click`.
// Un tap sur « Rester » dans la boîte « Quitter sans enregistrer ? » la ferme
// d'abord (React, synchrone), PUIS le rappel différé arrive sur le panneau,
// redevenu la couche la plus haute : il prenait ce tap pour un tap sur le
// voile et REDEMANDAIT la confirmation — la boîte ne se fermait jamais.
// `estGesteHorsPanneau` ignore une cible décrochée du document ou vivant dans
// une autre couche. Même montage que LeadDevisPanelSorties.test.jsx (vrai
// ConfirmProvider, générateur mocké qui pousse `onDirtyChange`).
// Run : npx vitest run src/pages/crm/leads/LeadDevisPanelSortiesDifferees.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import ConfirmProvider from '../../../providers/ConfirmProvider'
import authReducer from '../../../features/auth/store/authSlice'

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

vi.mock('../../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(),
    getProposalPdf: vi.fn(() => new Promise(() => {})),
    reviserDevis: vi.fn(),
    creerDevisAuto: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))

const { generateur } = vi.hoisted(() => ({ generateur: { props: null } }))
vi.mock('../../ventes/DevisGenerator', () => ({
  default: (props) => {
    generateur.props = props
    return <div data-testid="generateur-monte"><input aria-label="Qté" defaultValue="1" /></div>
  },
}))

import ventesApi from '../../../api/ventesApi'
import LeadDevisPanel from './LeadDevisPanel'
import { estGesteHorsPanneau } from './gesteHorsPanneau'

const LEAD = { id: 77, nom: 'Khalid' }
const envoye = () => ({
  data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
})

function rendre(props = {}) {
  const onClose = vi.fn()
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Magasinier', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ConfirmProvider>
          <LeadDevisPanel lead={LEAD} mode="edit" existingDevisId={413}
                          onClose={onClose} {...props} />
        </ConfirmProvider>
      </MemoryRouter>
    </Provider>,
  )
  return { onClose }
}

async function ouvrirEditionModifiee() {
  const rendu = rendre()
  await screen.findByTestId('generateur-monte')
  await act(async () => { await new Promise((r) => setTimeout(r, 5)) })
  await act(async () => { generateur.props.onDirtyChange(true) })
  return rendu
}

/** Tap tactile : pointerdown « touch » (Radix diffère au click) puis click. */
async function tapTactile(el) {
  fireEvent.pointerDown(el, { pointerType: 'touch', button: 0, isPrimary: true })
  await act(async () => { fireEvent.click(el) })
  // Le rappel différé de Radix (click sur le document, puis setTimeout 0).
  await act(async () => { await new Promise((r) => setTimeout(r, 20)) })
}

beforeEach(() => {
  vi.clearAllMocks()
  generateur.props = null
  ventesApi.getProposalPdf.mockImplementation(() => new Promise(() => {}))
  ventesApi.getDevisById.mockResolvedValue(envoye())
})

describe('EDC6 (suite) — « Rester » au doigt ferme la boîte, et elle reste fermée', () => {
  it('tap tactile sur « Rester » : plus de boîte, éditeur conservé, panneau ouvert', async () => {
    const { onClose } = await ouvrirEditionModifiee()
    await userEvent.keyboard('{Escape}')
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent(/Quitter sans enregistrer/)

    await tapTactile(screen.getByRole('button', { name: 'Rester' }))

    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    // Et elle ne revient pas (le rappel différé ne redemande rien).
    await act(async () => { await new Promise((r) => setTimeout(r, 60)) })
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(screen.getByTestId('generateur-monte')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('tap tactile sur « Quitter » : aperçu du devis existant, une seule confirmation', async () => {
    const { onClose } = await ouvrirEditionModifiee()
    await userEvent.keyboard('{Escape}')
    await screen.findByRole('alertdialog')

    await tapTactile(screen.getByRole('button', { name: 'Quitter' }))

    await waitFor(() => expect(screen.queryByTestId('generateur-monte')).toBeNull())
    await act(async () => { await new Promise((r) => setTimeout(r, 60)) })
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(screen.queryByRole('button', { name: /Télécharger le PDF/ })).not.toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('estGesteHorsPanneau — module pur', () => {
  const panneau = document.createElement('div')
  panneau.setAttribute('role', 'dialog')

  it('cible décrochée du document (sa couche vient de se fermer) ⇒ pas un geste de sortie', () => {
    const boite = document.createElement('div')
    boite.setAttribute('role', 'alertdialog')
    const bouton = document.createElement('button')
    boite.appendChild(bouton)
    expect(bouton.isConnected).toBe(false)
    expect(estGesteHorsPanneau(bouton, panneau)).toBe(false)
  })

  it('cible dans une autre couche montée (confirmation, popover) ⇒ pas un geste de sortie', () => {
    const boite = document.createElement('div')
    boite.setAttribute('role', 'alertdialog')
    const bouton = document.createElement('button')
    boite.appendChild(bouton)
    document.body.appendChild(boite)
    try {
      expect(estGesteHorsPanneau(bouton, panneau)).toBe(false)
    } finally {
      boite.remove()
    }
    const popover = document.createElement('div')
    popover.setAttribute('data-radix-popper-content-wrapper', '')
    const option = document.createElement('div')
    popover.appendChild(option)
    document.body.appendChild(popover)
    try {
      expect(estGesteHorsPanneau(option, panneau)).toBe(false)
    } finally {
      popover.remove()
    }
  })

  it('cible sur le voile (hors toute couche) ⇒ geste de sortie ; cible sans closest ⇒ sortie', () => {
    const voile = document.createElement('div')
    document.body.appendChild(voile)
    try {
      expect(estGesteHorsPanneau(voile, panneau)).toBe(true)
    } finally {
      voile.remove()
    }
    expect(estGesteHorsPanneau(null, panneau)).toBe(true)
    expect(estGesteHorsPanneau({}, panneau)).toBe(true)
  })
})
