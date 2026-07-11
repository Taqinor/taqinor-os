// VX139 — bloc de totaux partagé DevisForm/DevisGenerator, une seule devise
// (formatMAD, jamais un suffixe « DH » codé en dur).

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import QuoteTotalsSummary from './QuoteTotalsSummary'

describe('QuoteTotalsSummary — chaîne canonique Sous-total HT → TVA → Total TTC', () => {
  it('affiche la chaîne complète en MAD (jamais DH)', () => {
    render(
      <QuoteTotalsSummary
        subtotalHT={1000}
        remiseLabel="Remise globale (10%)"
        remiseMontant={100}
        totalHT={900}
        tauxTva={20}
        totalTVA={180}
        totalTTC={1080}
      />,
    )
    expect(screen.getByText('Sous-total HT')).toBeInTheDocument()
    expect(screen.getByText(/^1.000,00 MAD$/)).toBeInTheDocument()
    expect(screen.getByText('Remise globale (10%)')).toBeInTheDocument()
    expect(screen.getByText(/^−100,00 MAD$/)).toBeInTheDocument()
    expect(screen.getByText(/^900,00 MAD$/)).toBeInTheDocument()
    expect(screen.getByText('TVA (20%)')).toBeInTheDocument()
    expect(screen.getByText(/^180,00 MAD$/)).toBeInTheDocument()
    expect(screen.getByText(/^1.080,00 MAD$/)).toBeInTheDocument()
    expect(screen.queryByText(/\bDH\b/)).not.toBeInTheDocument()
  })

  it('masque la ligne de remise quand le montant est nul', () => {
    render(
      <QuoteTotalsSummary
        subtotalHT={1000}
        remiseLabel="Remise globale (0%)"
        remiseMontant={0}
        totalHT={1000}
        tauxTva={20}
        totalTVA={200}
        totalTTC={1200}
      />,
    )
    expect(screen.queryByText(/Remise globale/)).not.toBeInTheDocument()
  })
})
