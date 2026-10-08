import { describe, it, expect, afterEach, vi } from 'vitest'
import { screen, cleanup } from '@testing-library/react'

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

/* APAR31 — toute erreur 400 du profil (ICE, RIB, IF…) s'affiche SOUS son
   champ dans Paramètres › Société, plus seulement e-mail/téléphone. */

import { renderSocieteSection as renderSection } from '../../test/societeSectionHarness'

describe('APAR31 — erreur 400 sous le champ fautif', () => {
  afterEach(cleanup)

  it('ICE de 14 chiffres : message sous le champ ICE, champ invalide', () => {
    const msg = "L'ICE doit comporter exactement 15 chiffres (reçu 14 caractère(s))."
    renderSection({ saveError: { ice: [msg] } })
    const input = screen.getByPlaceholderText('000000000000000')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute('aria-describedby', 'pe-ice-error')
    expect(screen.getByText(msg)).toBeInTheDocument()
  })

  it('RIB et IF : chaque message sous son propre champ', () => {
    renderSection({ saveError: { rib: ['RIB trop long.'], identifiant_fiscal: ['IF invalide.'] } })
    expect(screen.getByPlaceholderText('RIB 24 chiffres / IBAN')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('RIB trop long.')).toHaveAttribute('id', 'pe-rib-error')
    expect(screen.getByText('IF invalide.')).toHaveAttribute('id', 'pe-identifiant_fiscal-error')
  })

  it('sans erreur : aucun champ marqué invalide', () => {
    renderSection()
    expect(screen.getByPlaceholderText('000000000000000')).not.toHaveAttribute('aria-invalid', 'true')
  })
})
