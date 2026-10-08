import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

/* APAR31 — toute erreur 400 du profil (ICE, RIB, IF…) s'affiche SOUS son
   champ dans Paramètres › Société, plus seulement e-mail/téléphone. */

import SocieteSection from './SocieteSection'

function noop() {}

const FORM_VIDE = {
  nom: '', adresse: '', email: '', telephone: '',
  rib: '', banque: '', siret: '', tva_intra: '',
  instructions_paiement: '', conditions_generales: '',
  ice: '', identifiant_fiscal: '', rc: '', patente: '', cnss: '',
  couleur_principale: '#1d4ed8',
}

function renderSection({ saveError = null } = {}) {
  const store = configureStore({
    reducer: {
      parametres: (s = { error: saveError }) => s,
      auth: (s = { user: { company_est_demo: false } }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <SocieteSection
        accent="#1d4ed8" profile={null} form={FORM_VIDE}
        set={noop} uploading={false} dispatch={noop}
      />
    </Provider>,
  )
}

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
