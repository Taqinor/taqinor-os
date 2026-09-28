import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// `@sentry/react` n'est pas installé dans cet environnement (dépendance
// optionnelle, chargée seulement si VITE_SENTRY_DSN est configuré — voir
// `lib/monitoring.js`) ; le stub évite l'échec de résolution au transform
// pour la chaîne `../../ui` → `ErrorBoundary.jsx` → `lib/monitoring.js`,
// sans rapport avec ce correctif.
vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

/* ERR-QAH-PARAMETRES-CHAMP-ERREUR-GENERIQUE — « Société & identité » :
   une erreur de validation serveur sur le Téléphone (> 30 caractères,
   `PATCH /api/django/parametres/update/ → 400
   {"telephone":["Assurez-vous que ce champ comporte au plus 30
   caractères."]}`) doit s'afficher SOUS le champ Téléphone, qui doit être
   marqué invalide (`aria-invalid`) — règle fondateur « erreurs → le champ
   fautif ». Avant le correctif, le formulaire n'affichait qu'un bandeau
   générique ailleurs (`ParametresEntreprise.jsx`), sans toucher l'input. */

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
        accent="#1d4ed8"
        profile={null}
        form={FORM_VIDE}
        set={noop}
        uploading={false}
        dispatch={noop}
      />
    </Provider>,
  )
}

describe('ERR-QAH-PARAMETRES-CHAMP-ERREUR-GENERIQUE — Téléphone', () => {
  afterEach(cleanup)

  it('sans erreur serveur : le champ Téléphone reste valide, aucun message dessous', () => {
    renderSection()
    const input = screen.getByPlaceholderText('+212 6 XX XX XX XX')
    expect(input).not.toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByText(/Assurez-vous/)).not.toBeInTheDocument()
  })

  it('erreur 400 DRF sur telephone : le champ est marqué invalide et le message exact s\'affiche dessous', () => {
    renderSection({
      saveError: {
        telephone: ['Assurez-vous que ce champ comporte au plus 30 caractères.'],
      },
    })
    const input = screen.getByPlaceholderText('+212 6 XX XX XX XX')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Assurez-vous que ce champ comporte au plus 30 caractères.')).toBeInTheDocument()
  })
})
