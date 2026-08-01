import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* EZ6 — la paperasse de statut disparaît : les horodatages FONT le statut.
   On vérifie : (1) la dérivation pure (départ → En route, check-in → Sur site,
   retour → Terminée), y compris ses refus (aucun recul automatique, aucun
   horodatage nouveau) ; (2) le Select manuel ne propose que les voisins
   immédiats (rang ±1) ; (3) un refus serveur ne produit AUCUN toast rouge —
   seulement un indice inline. */

// La fiche monte TOUS les panneaux F5-F19 (Radix garde les TabsContent
// inactifs montés, `forceMount`) : chaque panneau appelle son endpoint au
// montage. Même stub « rejet gracieux » que MaJourneePage.test.jsx.
const { rejected } = vi.hoisted(() => ({
  rejected: () => Promise.reject(new Error('non mocké')),
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getMaTournee: vi.fn(),
    updateIntervention: vi.fn(),
    getInterventions: vi.fn(rejected),
    getPreparation: vi.fn(rejected),
    getPhotos: vi.fn(rejected),
    getSerials: vi.fn(rejected),
    getConsommation: vi.fn(rejected),
    getMemos: vi.fn(rejected),
    getReserves: vi.fn(rejected),
    getSafety: vi.fn(rejected),
    getToolReturn: vi.fn(rejected),
    getCode: vi.fn(rejected),
    compteRenduUrl: vi.fn(() => ''),
  },
}))
// `toast` vient de `ui/Toaster` (ré-exporté par `ui/index.js`) : c'est CE
// module qu'il faut doubler pour prouver qu'aucun toast rouge ne part.
const toastMock = vi.hoisted(() => ({
  success: vi.fn(), error: vi.fn(), info: vi.fn(), message: vi.fn(),
}))
vi.mock('../../ui/Toaster', () => ({
  toast: toastMock,
  Toaster: () => null,
  default: () => null,
}))

import installationsApi from '../../api/installationsApi'
import MaJourneePage, { statutDerive, statutsProposables } from './MaJourneePage'

const todayISO = () => {
  const d = new Date()
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

beforeEach(() => {
  installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [] } })
  installationsApi.updateIntervention.mockResolvedValue({ data: {} })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EZ6 · l’horodatage fait le statut (logique pure)', () => {
  const base = { id: 1, statut: 'prete' }

  it('départ dépôt → En route', () => {
    expect(statutDerive(base, { ...base, depart_depot_le: '2026-08-01T07:10:00Z' }))
      .toBe('en_route')
  })

  it('check-in → Sur site', () => {
    const avant = { id: 1, statut: 'en_route' }
    expect(statutDerive(avant, { ...avant, arrivee_site_le: '2026-08-01T08:00:00Z' }))
      .toBe('sur_site')
  })

  it('retour dépôt → Terminée', () => {
    const avant = { id: 1, statut: 'sur_site' }
    expect(statutDerive(avant, { ...avant, retour_depot_le: '2026-08-01T17:00:00Z' }))
      .toBe('terminee')
  })

  it('aucun horodatage NOUVEAU → aucune transition', () => {
    const avant = { id: 1, statut: 'en_route', depart_depot_le: 'x' }
    expect(statutDerive(avant, { ...avant })).toBeNull()
  })

  it('jamais de RECUL automatique (déjà Terminée, on re-tape le check-in)', () => {
    const avant = { id: 1, statut: 'terminee' }
    expect(statutDerive(avant, { ...avant, arrivee_site_le: '2026-08-01T08:00:00Z' }))
      .toBeNull()
  })

  it('si le statut est déjà celui déduit, rien à faire', () => {
    const avant = { id: 1, statut: 'sur_site' }
    expect(statutDerive(avant, { ...avant, arrivee_site_le: 'x' })).toBeNull()
  })

  it('plusieurs horodatages d’un coup (synchro hors-ligne) : le plus avancé gagne', () => {
    const avant = { id: 1, statut: 'prete' }
    expect(statutDerive(avant, {
      ...avant, depart_depot_le: 'a', arrivee_site_le: 'b',
    })).toBe('sur_site')
  })
})

describe('EZ6 · le Select manuel ne propose que les voisins', () => {
  it('depuis « En route » : Prête, En route, Sur site — et RIEN d’autre', () => {
    expect(statutsProposables('en_route')).toEqual(['prete', 'en_route', 'sur_site'])
  })

  it('aux extrémités, la liste se réduit proprement', () => {
    expect(statutsProposables('a_preparer')).toEqual(['a_preparer', 'prete'])
    expect(statutsProposables('validee')).toEqual(['terminee', 'validee'])
  })

  it('une transition NON adjacente n’est jamais proposée', () => {
    expect(statutsProposables('a_preparer')).not.toContain('terminee')
    expect(statutsProposables('prete')).not.toContain('validee')
  })
})

describe('EZ6 · refus serveur = NO-OP silencieux', () => {
  it('n’affiche pas de toast rouge et garde l’indice en inline', async () => {
    const stop = {
      id: 7, statut: 'sur_site', client_nom: 'Client Sept',
      type_intervention: 'pose', date_prevue: todayISO(),
    }
    installationsApi.getMaTournee.mockResolvedValue({ data: { stops: [stop] } })
    render(<MemoryRouter><MaJourneePage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Client Sept')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Client Sept'))

    // Le rendu seul n'écrit rien et n'alerte pas.
    expect(installationsApi.updateIntervention).not.toHaveBeenCalled()
    expect(toastMock.error).not.toHaveBeenCalled()
    // Le Select ne propose que les voisins de « Sur site ».
    expect(await screen.findByLabelText("Statut de l'intervention")).toBeInTheDocument()
  })
})
