import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'

/* WIR159 — Onglet « Marketplace » : catalogue lecture seule des packages
   d'extension (NTEXT13), consommant `GET /extensions/catalogue/`. */

const CATALOGUE = [
  {
    id: 1, code: 'sav-avance', nom: 'Suivi SAV avancé', version: '1.2.0',
    description: 'Objets et automatisations pour un SAV outillé.',
    categorie: 'Services',
    manifest: {
      custom_object_defs: [{ code: 'ticket_ext' }, { code: 'sla' }],
      automation_rules: [{ code: 'relance' }],
      rapport_definitions: [],
      branded_templates: [],
    },
  },
  {
    id: 2, code: 'chantier-plus', nom: 'Chantier +', version: '0.9.0',
    description: '', categorie: 'Chantiers',
    manifest: {},
  },
]

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get } }))

import MarketplaceSection from './MarketplaceSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('MarketplaceSection (WIR159)', () => {
  it('affiche le catalogue groupé par catégorie avec version et résumé du manifest', async () => {
    get.mockResolvedValue({ data: CATALOGUE })
    render(<MarketplaceSection />)

    // Consomme bien l'endpoint catalogue.
    expect(get).toHaveBeenCalledWith('/extensions/catalogue/')

    const row = await screen.findByTestId('extension-row-sav-avance')
    expect(within(row).getByText('Suivi SAV avancé')).toBeInTheDocument()
    expect(within(row).getByText('v1.2.0')).toBeInTheDocument()
    // Résumé du manifest : 2 objets personnalisés + 1 règle (les familles
    // vides sont omises).
    expect(within(row).getByText(/2 Objets personnalisés/)).toBeInTheDocument()
    expect(within(row).getByText(/1 Règles d'automatisation/)).toBeInTheDocument()

    // Le second package (manifest vide) rend sans résumé.
    expect(screen.getByText('Chantier +')).toBeInTheDocument()
    // Catégories rendues comme titres de groupe.
    expect(screen.getByText('Services')).toBeInTheDocument()
    expect(screen.getByText('Chantiers')).toBeInTheDocument()
  })

  it('affiche un état vide quand le catalogue est vide', async () => {
    get.mockResolvedValue({ data: [] })
    render(<MarketplaceSection />)
    expect(await screen.findByText('Aucun package d\'extension')).toBeInTheDocument()
  })

  it('affiche une erreur de chargement', async () => {
    get.mockRejectedValue(new Error('boom'))
    render(<MarketplaceSection />)
    expect(await screen.findByText(/Impossible de charger le catalogue/)).toBeInTheDocument()
  })
})
