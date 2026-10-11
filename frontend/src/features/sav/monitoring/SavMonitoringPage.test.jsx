import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// ASAV100-103 — écran SAV/monitoring (D-ASAV-4 option (b)). Les réponses
// viennent des exemples COMMITTÉS que le test backend affirme (PACT10) —
// jamais un mock écrit à la main.
import ABONNEMENTS from '../../../../../backend/django_core/apps/monitoring/contract_samples/abonnements_monitoring.json'

const serveur = vi.hoisted(() => ({ abonnements: null, creations: [], resiliations: [] }))

vi.mock('../../../api/monitoringApi', () => ({
  default: {
    getConfigs: vi.fn(() => Promise.resolve({ data: { results: [
      { id: 5, installation: 87 },
    ] } })),
    getAbonnements: vi.fn(() => Promise.resolve({ data: serveur.abonnements })),
    creerAbonnement: vi.fn((data) => {
      serveur.creations.push(data)
      return Promise.resolve({ data: ABONNEMENTS.exemple.results[0] })
    }),
    resilierAbonnement: vi.fn((id, motif) => {
      serveur.resiliations.push({ id, motif })
      const reponse = ABONNEMENTS.exemple_resiliation.reponse
      serveur.abonnements = { ...ABONNEMENTS.exemple, results: [reponse] }
      return Promise.resolve({ data: reponse })
    }),
  },
}))
vi.mock('../../../api/installationsApi', () => ({
  default: {
    getInstallations: vi.fn(() => Promise.resolve({ data: { results: [
      { id: 87, reference: 'CHT-87', client_nom: 'Alami' },
    ] } })),
  },
}))

import SavMonitoringPage from './SavMonitoringPage'

afterEach(() => {
  cleanup()
  serveur.creations.length = 0
  serveur.resiliations.length = 0
})

describe('SavMonitoringPage — ASAV100 abonnements de supervision', () => {
  it('liste les abonnements servis, en crée un et le résilie (motif obligatoire)', async () => {
    serveur.abonnements = ABONNEMENTS.exemple
    const user = userEvent.setup()
    render(<SavMonitoringPage />)

    const section = await screen.findByRole('region', { name: 'Abonnements de supervision' })
    const ligne = await within(section).findByRole('listitem')
    expect(ligne).toHaveTextContent('CHT-87 — Alami')
    expect(ligne).toHaveTextContent('Actif')
    expect(ligne).toHaveTextContent('Mensuel')

    // Création : système auto-sélectionné (un seul supervisé), montant saisi.
    await user.type(screen.getByLabelText('Montant par période (MAD)'), '150', { delay: null })
    await user.click(screen.getByRole('button', { name: "Créer l'abonnement" }))
    await waitFor(() => expect(serveur.creations).toHaveLength(1))
    expect(serveur.creations[0]).toMatchObject({
      installation_id: 87, periodicite: 'mensuel', montant: '150',
    })

    // Résiliation : le motif part au serveur, l'état revient du serveur.
    await user.click(await screen.findByRole('button', { name: 'Résilier' }))
    await user.type(screen.getByLabelText('Motif de résiliation'), 'Client a vendu la maison.', { delay: null })
    await user.click(screen.getByRole('button', { name: 'Confirmer la résiliation' }))
    await waitFor(() => expect(serveur.resiliations).toEqual([
      { id: ABONNEMENTS.exemple.results[0].id, motif: 'Client a vendu la maison.' },
    ]))
    await waitFor(() => expect(within(section).getByRole('listitem')).toHaveTextContent('Résilié'))
    expect(screen.queryByRole('button', { name: 'Résilier' })).not.toBeInTheDocument()
  }, 60000)
})
