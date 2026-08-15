import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* WIR216/XSTK22 — « Mes livraisons » du portail client : le lien de l'email
   de transition (livraison_en_transit/livree) pointait vers une route qui
   n'a jamais existé côté frontend (404 garanti). Cet écran affiche la liste
   scopée au compte connecté (portailApi.livraisons.liste), jamais un
   client_id envoyé par l'écran. */

const liste = vi.fn()
vi.mock('../../../api/portailApi', () => ({
  default: { livraisons: { liste: (...a) => liste(...a) } },
}))

import PortailClientLivraisons from './PortailClientLivraisons'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PortailClientLivraisons (WIR216)', () => {
  it('affiche les livraisons du client avec statut et articles', async () => {
    liste.mockResolvedValue({
      data: {
        results: [
          {
            id: 1, reference: 'LIV-2026-0001', date_prevue: '2026-08-20',
            statut: 'en_transit', statut_display: 'En transit',
            numero_suivi: 'DHL123', articles: [{ designation: 'Onduleur 5kW', quantite: 1 }],
            pod_disponible: false, pod_url: null,
          },
        ],
      },
    })
    render(<PortailClientLivraisons />)

    expect(await screen.findByText('LIV-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('En transit')).toBeInTheDocument()
    expect(screen.getByText(/DHL123/)).toBeInTheDocument()
    expect(screen.getByText(/Onduleur 5kW/)).toBeInTheDocument()
  })

  it('affiche un état vide explicite sans livraison', async () => {
    liste.mockResolvedValue({ data: { results: [] } })
    render(<PortailClientLivraisons />)
    expect(await screen.findByText('Aucune livraison')).toBeInTheDocument()
  })

  it('affiche un message dédié en cas d\'échec de chargement (jamais une page blanche)', async () => {
    liste.mockRejectedValue(new Error('réseau'))
    render(<PortailClientLivraisons />)
    expect(await screen.findByText('Livraisons indisponibles')).toBeInTheDocument()
  })

  it('propose le lien de preuve de livraison quand elle est disponible', async () => {
    liste.mockResolvedValue({
      data: {
        results: [
          {
            id: 2, reference: 'LIV-2026-0002', date_prevue: '2026-08-01',
            statut: 'livree', statut_display: 'Livrée', numero_suivi: '',
            articles: [], pod_disponible: true,
            pod_url: '/api/django/installations/preuves-livraison/9/',
          },
        ],
      },
    })
    render(<PortailClientLivraisons />)
    const lien = await screen.findByRole('link', { name: /Preuve de livraison/ })
    expect(lien).toHaveAttribute('href', '/api/django/installations/preuves-livraison/9/')
  })
})
