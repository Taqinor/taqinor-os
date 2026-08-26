import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR104 — cet écran est le CONSOMMATEUR du cluster réglementaire de ventes
   (FG245, FG268-287), qui était complet côté serveur et appelé nulle part.
   Le test verrouille : un appel réel par ressource, un rendu générique des
   champs renvoyés, et le changement de ressource qui rappelle l'API. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

// WIR224 — le panneau « Échéances à venir » (FG273) est chargé au montage :
// sans ce wrapper dans le mock, les trois tests WIR104 ci-dessous casseraient.
const CALENDRIER_VIDE = {
  today: '2026-08-26', seuil_imminent_jours: 30, validite_accord_jours: 365,
  echeances: [], resume: { expire: 0, imminent: 0, a_venir: 0, sans_echeance: 0 },
}

vi.mock('../../api/ventesApi', () => ({
  default: {
    getReglementaire: vi.fn((resource) => Promise.resolve({
      data: resource === 'dossiers-reglementaires'
        ? [{ id: 1, reference: 'DR-2026-001', operateur: 'ONEE', statut: 'depose' }]
        : [{ id: 2, reference: 'CK-2026-001', etape: 'depot', statut: 'en_cours' }],
    })),
    getCalendrierReglementaire: vi.fn(() => Promise.resolve({
      data: {
        today: '2026-08-26', seuil_imminent_jours: 30, validite_accord_jours: 365,
        echeances: [], resume: { expire: 0, imminent: 0, a_venir: 0, sans_echeance: 0 },
      },
    })),
  },
}))

import ventesApi from '../../api/ventesApi'
import DossiersReglementairesPage from './DossiersReglementairesPage'

describe('DossiersReglementairesPage (WIR104)', () => {
  it('charge la première ressource et rend ses champs', async () => {
    render(<DossiersReglementairesPage />)
    await waitFor(() => expect(ventesApi.getReglementaire)
      .toHaveBeenCalledWith('dossiers-reglementaires'))
    expect(await screen.findByText('DR-2026-001')).toBeInTheDocument()
    expect(screen.getByText('ONEE')).toBeInTheDocument()
  })

  it('rappelle l\'API en changeant de ressource', async () => {
    const user = userEvent.setup()
    render(<DossiersReglementairesPage />)
    await screen.findByText('DR-2026-001')

    await user.click(screen.getByRole('radio', { name: 'Checklists' }))
    await waitFor(() => expect(ventesApi.getReglementaire)
      .toHaveBeenCalledWith('dossiers-checklist'))
    expect(await screen.findByText('CK-2026-001')).toBeInTheDocument()
  })

  it('expose toutes les ressources du cluster', () => {
    render(<DossiersReglementairesPage />)
    for (const label of [
      'Dossiers', 'Checklists', 'Échanges opérateur', 'Subventions',
      'Régularisation 82-21', 'Recette IEC 62446', 'Courbes I-V',
      'Packs as-built', 'Attestations conformité', 'Tests PR réception',
      'Attestations RE', 'Calepinages',
    ]) {
      expect(screen.getAllByRole('radio', { name: label }).length).toBeGreaterThan(0)
    }
  })
})

/* WIR224/FG273 — `GET /ventes/calendrier-reglementaire/` agrégeait depuis
   toujours les échéances des dossiers ET calculait leur statut d'alerte
   (expiré / imminent / à venir). Rien ne le lisait : une échéance DÉPASSÉE
   n'était visible nulle part. Les statuts viennent du SERVEUR — jamais d'un
   recalcul de date côté écran, qui divergerait au premier changement du seuil
   « imminent » (réglage serveur). */
const ECHEANCES = [
  {
    type: 'piece', sous_type: 'depot', dossier_id: 7,
    libelle: 'Attestation ONEE', date_echeance: '2026-07-01',
    statut_alerte: 'expire', jours_restants: -56, relance_due: true,
  },
  {
    type: 'depot', sous_type: 'net_metering', dossier_id: 8,
    libelle: 'Dépôt en instruction — devis 42', date_echeance: '2026-09-05',
    statut_alerte: 'imminent', jours_restants: 10, relance_due: false,
  },
  {
    type: 'validite_accord', sous_type: 'net_metering', dossier_id: 9,
    libelle: 'Date limite MES (validité accord) — devis 42',
    date_echeance: '2027-01-15', statut_alerte: 'a_venir',
    jours_restants: 142, relance_due: false,
  },
]

describe('DossiersReglementairesPage (WIR224 — échéances à venir)', () => {
  it('charge le calendrier au montage et rend les TROIS statuts', async () => {
    ventesApi.getCalendrierReglementaire.mockResolvedValueOnce({
      data: {
        ...CALENDRIER_VIDE,
        echeances: ECHEANCES,
        resume: { expire: 1, imminent: 1, a_venir: 1, sans_echeance: 0 },
      },
    })
    render(<DossiersReglementairesPage />)
    await waitFor(() => expect(ventesApi.getCalendrierReglementaire).toHaveBeenCalled())
    expect(await screen.findByText('Attestation ONEE')).toBeInTheDocument()
    expect(screen.getByText('Dépôt en instruction — devis 42')).toBeInTheDocument()
    expect(screen.getByText(/Date limite MES/)).toBeInTheDocument()
  })

  it('une échéance passée est marquée « expiré » (rouge), avec son retard', async () => {
    ventesApi.getCalendrierReglementaire.mockResolvedValueOnce({
      data: {
        ...CALENDRIER_VIDE,
        echeances: ECHEANCES,
        resume: { expire: 1, imminent: 1, a_venir: 1, sans_echeance: 0 },
      },
    })
    const { container } = render(<DossiersReglementairesPage />)
    await screen.findByText('Attestation ONEE')
    const ligne = container.querySelector('li[data-statut="expire"]')
    expect(ligne).toBeTruthy()
    expect(ligne.className).toMatch(/destructive/)
    // Les jours restants viennent du serveur (négatif = dépassé).
    expect(ligne.textContent).toMatch(/en retard de 56 j/)
    // …et l'écran n'invente aucun statut : la ligne « à venir » n'est pas rouge.
    expect(container.querySelector('li[data-statut="a_venir"]').className)
      .not.toMatch(/destructive/)
  })

  it('cliquer un compteur RECHARGE du serveur avec ?statut=', async () => {
    const user = userEvent.setup()
    ventesApi.getCalendrierReglementaire.mockResolvedValueOnce({
      data: {
        ...CALENDRIER_VIDE,
        echeances: ECHEANCES,
        resume: { expire: 1, imminent: 1, a_venir: 1, sans_echeance: 0 },
      },
    })
    render(<DossiersReglementairesPage />)
    await screen.findByText('Attestation ONEE')

    ventesApi.getCalendrierReglementaire.mockResolvedValueOnce({
      data: {
        ...CALENDRIER_VIDE,
        echeances: [ECHEANCES[1]],
        resume: { expire: 0, imminent: 1, a_venir: 0, sans_echeance: 0 },
      },
    })
    await user.click(screen.getByRole('button', { name: /Imminent/ }))
    await waitFor(() => expect(ventesApi.getCalendrierReglementaire)
      .toHaveBeenCalledWith({ statut: 'imminent' }))
    await waitFor(() => expect(screen.queryByText('Attestation ONEE')).toBeNull())
    // Les compteurs restent ceux de la vue COMPLÈTE : filtrer ne les remet
    // pas à zéro (le serveur ne résume que ce qu'il renvoie).
    expect(screen.getByRole('button', { name: /Expiré/ }).textContent).toMatch(/1/)
  })

  it('écran sain quand il n’y a aucune échéance', async () => {
    render(<DossiersReglementairesPage />)
    expect(await screen.findByText('Aucune échéance')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Expiré/ }).textContent).toMatch(/0/)
  })
})
