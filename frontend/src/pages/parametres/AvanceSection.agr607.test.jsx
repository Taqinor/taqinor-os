import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

/* AGR607 — Paramètres › Avancé : « Écart de recette pompage toléré (%) »,
   réglage société SANS défaut (AGR606). Vide = envoyé null avec l'aide « non
   saisi : l'écart sera affiché sans verdict » ; une valeur tapée part telle
   quelle (jamais arrondie) ; le 400 du serveur s'affiche SOUS le champ ;
   enregistrer → rouvrir → enregistrer sans toucher = même PATCH. */

import { EcartRecettePompageField } from './AvanceSection'
import { CHAMP_ECART_RECETTE, nombreOuNull } from './peConstants'

afterEach(() => cleanup())

const champ = () => screen.getByLabelText('Écart de recette pompage toléré (%)')

describe('AGR607 — écart de recette pompage toléré', () => {
  it('vide : step="any", aide « sans verdict », envoyé null', () => {
    render(<EcartRecettePompageField form={{ [CHAMP_ECART_RECETTE]: '' }}
                                     set={vi.fn()} />)
    expect(champ()).toHaveAttribute('step', 'any')
    expect(champ()).toHaveAttribute('name', CHAMP_ECART_RECETTE)
    expect(champ()).toHaveValue(null)
    expect(screen.getByText(/l'écart sera affiché sans verdict/)).toBeInTheDocument()
    expect(nombreOuNull('')).toBeNull()
  })

  it('une valeur tapée est envoyée telle quelle (jamais arrondie)', () => {
    const set = vi.fn()
    render(<EcartRecettePompageField form={{ [CHAMP_ECART_RECETTE]: '' }} set={set} />)
    fireEvent.change(champ(), { target: { value: '12.375' } })
    expect(set).toHaveBeenCalled()
    expect(set.mock.calls.at(-1)[0].target.name).toBe(CHAMP_ECART_RECETTE)
    expect(nombreOuNull('12.375')).toBe('12.375')
    expect(nombreOuNull('12,5')).toBe('12.5')
  })

  it('le refus 400 du serveur s’affiche sous le champ', () => {
    const message = "L'écart de recette pompage toléré doit être compris entre 0 (exclu) et 100 %."
    render(<EcartRecettePompageField form={{ [CHAMP_ECART_RECETTE]: '150' }}
                                     set={vi.fn()}
                                     erreur={{ [CHAMP_ECART_RECETTE]: [message] }} />)
    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(champ()).toHaveAttribute('aria-invalid', 'true')
    expect(champ()).toHaveAttribute('aria-describedby', 'pe-ecart-recette-erreur')
    expect(screen.queryByText(/sans verdict/)).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = même PATCH', () => {
    // Rouvrir = la valeur servie, affichée telle quelle dans le champ ; le
    // PATCH suivant (sans toucher) renvoie exactement la même valeur.
    for (const servi of ['7.25', null]) {
      const form = { [CHAMP_ECART_RECETTE]: servi ?? '' }
      render(<EcartRecettePompageField form={form} set={vi.fn()} />)
      const premier = nombreOuNull(form[CHAMP_ECART_RECETTE])
      const second = nombreOuNull(champ().value)
      expect(second).toBe(premier)
      expect(premier).toBe(servi)
      cleanup()
    }
  })
})
