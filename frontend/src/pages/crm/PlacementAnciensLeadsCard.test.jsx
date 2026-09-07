import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* MRY33 — carte Cockpit « Anciens leads à placer dans les cadences ». Charge
   utile venant de l'exemple COMMITTÉ
   (`apps/crm/contract_samples/placement_anciens_leads.json`, PACT10), jamais
   un objet retapé à la main : c'est cette deuxième source de vérité qui
   avait laissé passer l'écran AO mort du 03/08/2026 (test vert, écran mort).
   Si le serveur change de forme, l'exemple change et ce test casse tout
   seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const DONNEES = exempleContrat('crm', 'placement_anciens_leads')

// Même patron que `IdentityRail.test.jsx` : le hook de rôle est mocké plutôt
// qu'un vrai Provider redux — réassignable par test.
const isAdminOrResponsableMock = vi.fn(() => true)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    placerAnciensLeads: vi.fn(),
  },
}))

// Même patron que `ClientForm.test.jsx` : confirmation/toast mockés (le
// composant réel `ui/confirm` n'est pas ce qu'on vérifie ici).
const confirmMock = vi.fn(() => Promise.resolve(true))
vi.mock('../../ui/confirm', () => ({
  useConfirmDialog: () => ({ confirm: (...args) => confirmMock(...args), confirmDelete: vi.fn() }),
  toast: { success: vi.fn(), error: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import { toast } from '../../ui/confirm'
import PlacementAnciensLeadsCard from './PlacementAnciensLeadsCard'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(true)
  confirmMock.mockResolvedValue(true)
  // Aperçu → l'exemple du contrat (restants == a_placer) ; application → tout
  // placé en un lot (applique = a_placer, restants 0). Le contrat ne porte
  // qu'un exemple d'aperçu : une réponse d'application se dérive de lui.
  crmApi.placerAnciensLeads.mockImplementation((body) => Promise.resolve(
    body?.apply
      ? { data: { ...DONNEES, apply: true, applique: DONNEES.a_placer, restants: 0 } }
      : reponseContrat('crm', 'placement_anciens_leads'),
  ))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlacementAnciensLeadsCard (MRY33)', () => {
  it('masquée pour un rôle normal (aucun appel réseau)', () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    const { container } = render(<PlacementAnciensLeadsCard />)
    expect(container).toBeEmptyDOMElement()
    expect(crmApi.placerAnciensLeads).not.toHaveBeenCalled()
  })

  it('« Aperçu » affiche les cinq lignes par étape et le total à placer', async () => {
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(crmApi.placerAnciensLeads).toHaveBeenCalledWith({ apply: false }))
    await waitFor(() => {
      for (const etape of DONNEES.par_etape) {
        expect(screen.getByText(etape.libelle)).toBeInTheDocument()
      }
    })
    expect(screen.getAllByText(new RegExp(String(DONNEES.a_placer))).length).toBeGreaterThan(0)
    expect(screen.getAllByText(new RegExp(String(DONNEES.total_candidats))).length).toBeGreaterThan(0)
    // Le premier lead de l'aperçu (contrat) est bien listé.
    expect(screen.getByText(DONNEES.apercu[0].nom)).toBeInTheDocument()
  })

  it('« Appliquer » est désactivé avant tout aperçu, puis ouvre la confirmation et appelle l\'API avec apply=true, limite=40', async () => {
    render(<PlacementAnciensLeadsCard />)
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    // Le choix du volume (décision fondateur 07/09/2026) est proposé à UN lot
    // par défaut — jamais les 270 d'un coup dans la file de Meryem.
    expect(screen.getByLabelText('Nombre à placer')).toHaveValue(40)

    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    // Placement PARTIEL (40 sur 270) : la confirmation dit les deux nombres
    // et ne promet AUCUN décompte Froid (le moteur décide lead par lead —
    // un chiffre exact n'existe que sur un placement complet).
    const [options] = confirmMock.mock.calls[0]
    expect(options.description).toContain('40')
    expect(options.description).toContain(String(DONNEES.a_placer))
    expect(options.description).not.toContain('208')

    // Le premier lot est envoyé avec `limite: 40` (jamais un unique appel
    // sans borne — PERFORMANCE, incident du 07/09).
    await waitFor(() => expect(crmApi.placerAnciensLeads)
      .toHaveBeenCalledWith({ apply: true, limite: 40 }))
    await waitFor(() => expect(toast.success).toHaveBeenCalled())
  })

  it('placer TOUT (nombre = a_placer) garde la confirmation complète avec le décompte Froid', async () => {
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    fireEvent.change(screen.getByLabelText('Nombre à placer'), {
      target: { value: String(DONNEES.a_placer) },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    // M = somme des codes dormant_* (150 + 58 = 208 sur le contrat).
    const [options] = confirmMock.mock.calls[0]
    expect(options.description).toContain(String(DONNEES.a_placer))
    expect(options.description).toContain('208')
  })

  it('« Appliquer » boucle par lots dans la limite du nombre choisi puis recharge l\'aperçu', async () => {
    crmApi.placerAnciensLeads
      .mockResolvedValueOnce(reponseContrat('crm', 'placement_anciens_leads')) // Aperçu initial
      .mockResolvedValueOnce({ data: { ...DONNEES, apply: true, applique: 40, restants: 230 } }) // lot 1
      .mockResolvedValueOnce({ data: { ...DONNEES, apply: true, applique: 10, restants: 220 } }) // lot 2
      .mockResolvedValueOnce(reponseContrat('crm', 'placement_anciens_leads')) // aperçu rechargé

    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    // Meryem/Reda choisit 50 : un lot plein de 40, puis un lot de 10 —
    // jamais un 3ᵉ lot même s'il reste 220 leads côté serveur.
    fireEvent.change(screen.getByLabelText('Nombre à placer'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())

    await waitFor(() => expect(crmApi.placerAnciensLeads.mock.calls.length).toBe(4))
    expect(crmApi.placerAnciensLeads.mock.calls[0][0]).toEqual({ apply: false })
    expect(crmApi.placerAnciensLeads.mock.calls[1][0]).toEqual({ apply: true, limite: 40 })
    expect(crmApi.placerAnciensLeads.mock.calls[2][0]).toEqual({ apply: true, limite: 10 })
    expect(crmApi.placerAnciensLeads.mock.calls[3][0]).toEqual({ apply: false })

    // Le toast final annonce le CUMUL des deux lots (40 + 10 = 50) ET les
    // restants côté serveur — deux chiffres lus sur la réponse.
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('50')))
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('220'))
  })

  it('un lot qui ne place plus personne arrête la boucle et affiche « Reprendre »', async () => {
    crmApi.placerAnciensLeads
      .mockResolvedValueOnce(reponseContrat('crm', 'placement_anciens_leads')) // Aperçu initial
      .mockResolvedValueOnce({ data: { ...DONNEES, apply: true, applique: 0, restants: 5 } })

    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())

    expect(await screen.findByRole('button', { name: 'Reprendre' })).toBeInTheDocument()
    // Une seule tentative : la boucle s'arrête dès qu'un lot ne place plus
    // personne, même s'il en reste (jamais un bouclage sans fin).
    expect(crmApi.placerAnciensLeads.mock.calls.filter(([body]) => body.apply === true)).toHaveLength(1)
    expect(toast.success).not.toHaveBeenCalled()
  })

  it('Annuler la confirmation n\'appelle jamais l\'API avec apply=true', async () => {
    confirmMock.mockResolvedValueOnce(false)
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    expect(crmApi.placerAnciensLeads).not.toHaveBeenCalledWith({ apply: true })
  })

  it('aucun ancien lead à placer : message et repli, la carte se replie', async () => {
    crmApi.placerAnciensLeads.mockResolvedValue(
      reponseContrat('crm', 'placement_anciens_leads', 'exemple_vide'))
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    expect(await screen.findByText(/Aucun ancien lead à placer/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()
  })
})
