import { describe, it, expect, afterEach, vi } from 'vitest'
import { screen, cleanup } from '@testing-library/react'

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

import { renderSocieteSection as renderSection } from '../../test/societeSectionHarness'

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

describe('ERR-QAH-PARAMETRES-EMAIL-ERREUR-HORS-CHAMP — Email', () => {
  afterEach(cleanup)

  it("erreur 400 DRF sur email : le champ est marqué invalide et le message s'affiche dessous", () => {
    renderSection({ saveError: { email: ['Saisissez une adresse e-mail valide.'] } })
    const input = screen.getByPlaceholderText('contact@entreprise.ma')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Saisissez une adresse e-mail valide.')).toBeInTheDocument()
  })
})

describe('ERR-PAR-LOGO-APERCU-MINIO-CSP — mediaUrl (aperçu du logo)', () => {
  const interne = 'http://minio:9000/erp-uploads/logos/x.png?X-Amz-Signature=abc&X-Amz-Expires=3600'

  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

  it("sans VITE_API_URL : jamais l'hôte Docker interne, query présignée intacte", async () => {
    vi.stubEnv('VITE_API_URL', '')
    vi.resetModules()
    const { mediaUrl } = await import('./peConstants')
    const out = new URL(mediaUrl(interne))
    expect(out.hostname).not.toBe('minio')
    expect(out.pathname).toBe('/erp-uploads/logos/x.png')
    expect(out.search).toBe('?X-Amz-Signature=abc&X-Amz-Expires=3600')
  })

  it('avec VITE_API_URL : comportement inchangé (hôte API, port 9000)', async () => {
    vi.stubEnv('VITE_API_URL', 'http://api.local:8000')
    vi.resetModules()
    const { mediaUrl } = await import('./peConstants')
    expect(mediaUrl(interne)).toBe(
      'http://api.local:9000/erp-uploads/logos/x.png?X-Amz-Signature=abc&X-Amz-Expires=3600',
    )
  })
})
