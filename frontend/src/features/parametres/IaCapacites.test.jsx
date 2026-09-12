import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* NTAI6 — Paramètres → IA : capacités actives.
   Vérifie ce qui compte : le MOTIF d'une capacité inactive est lisible, une
   capacité jamais appelée dit « aucune mesure » (et non « 0 ms »), et aucune
   clé d'API ne peut s'afficher (le serveur n'en renvoie pas). */

const { capabilities, budgetStatut } = vi.hoisted(() => ({
  capabilities: vi.fn(() => Promise.resolve({
    data: [
      {
        capacite: 'llm',
        fournisseur_choisi: 'groq',
        fournisseur_actif: 'groq',
        label: 'Groq',
        configure: true,
        motif: '',
        appels: 12,
        latence_p50_ms: 340,
        derniere_erreur: '',
        derniere_erreur_le: null,
      },
      {
        capacite: 'ocr',
        fournisseur_choisi: 'noop',
        fournisseur_actif: 'noop',
        label: 'Aucun OCR (saisie manuelle)',
        configure: false,
        motif: 'Aucun fournisseur sélectionné pour cette capacité.',
        appels: null,
        latence_p50_ms: null,
        derniere_erreur: '',
        derniere_erreur_le: null,
      },
    ],
  })),
  budgetStatut: vi.fn(() => Promise.resolve({ data: { configure: false } })),
}))

vi.mock('../../api/aiGovernanceApi', () => ({
  default: { capabilities, budgetStatut },
}))

import IaCapacites from './IaCapacites'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('IaCapacites (NTAI6)', () => {
  it('affiche l\'état de chaque capacité, motif compris', async () => {
    render(<IaCapacites />)

    expect(await screen.findByText('Génération de texte')).toBeInTheDocument()
    expect(screen.getByText('OCR — lecture de documents')).toBeInTheDocument()
    expect(screen.getByText(
      'Aucun fournisseur sélectionné pour cette capacité.')).toBeInTheDocument()
    expect(screen.getByText('Aucune mesure pour le moment.')).toBeInTheDocument()
    expect(capabilities).toHaveBeenCalled()
  })

  it('affiche un état d\'erreur quand le serveur ne répond pas', async () => {
    capabilities.mockReturnValueOnce(Promise.reject(new Error('boom')))
    render(<IaCapacites />)

    expect(await screen.findByText('État indisponible')).toBeInTheDocument()
  })
})
