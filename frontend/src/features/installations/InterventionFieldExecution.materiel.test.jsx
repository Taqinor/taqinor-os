import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* ERR-QAH-CHANTIERS-PREPARATION-MATERIEL-DISAPPEARS — cocher la première
   ligne de matériel dans l'onglet « Préparation » faisait disparaître les 10
   lignes (« Aucun matériel à préparer. »), le corps affichait « 0 % »
   alors que le badge d'onglet disait « 10% », et « Confirmer « Tout est
   chargé » » s'activait à tort.

   Root cause : `withOfflineFallback` (offline/fieldOutbox.js) enveloppe la
   réponse en ligne dans `{ queued: false, data: <réponse axios brute> }` —
   `data` est l'objet AxiosResponse, pas encore désenveloppé. `toggleMateriel`
   faisait `setPrep(r.data)`, posant `prep` = l'objet AxiosResponse (pas de
   `materiel`/`outils`/`completion`), au lieu de `r.data.data` (le corps JSON
   réellement renvoyé par `cocher-materiel`, miroir de `_prep_response` côté
   serveur). Reproduit ici avec le MÊME wrapper réel (pas un mock simplifié)
   que `InterventionCapturePanels.wir210.test.jsx` utilise pour le même
   helper, afin que ce test capture le vrai bug d'enveloppe. */

const outbox = vi.hoisted(() => ({
  FIELD_OPS: { COCHER_MATERIEL: 'intervention.cocher_materiel', COCHER_OUTIL: 'intervention.cocher_outil' },
  enqueue: vi.fn(() => Promise.resolve('op-1')),
  // Reproduit fidèlement le vrai helper offline/fieldOutbox.js : `data` est la
  // réponse AXIOS BRUTE (`{data: ...}`) renvoyée par l'appel en ligne, jamais
  // désenveloppée ici — exactement le piège du bug réel.
  withOfflineFallback: async (onlineCall) => {
    const data = await onlineCall()
    return { queued: false, data }
  },
}))

vi.mock('./offline/fieldOutbox', () => ({
  withOfflineFallback: outbox.withOfflineFallback,
  FIELD_OPS: outbox.FIELD_OPS,
  queuePhoto: vi.fn(),
  OutboxQuotaError: class OutboxQuotaError extends Error {},
}))

const api = vi.hoisted(() => ({
  getPreparation: vi.fn(),
  cocherMateriel: vi.fn(),
  cocherOutil: vi.fn(),
  confirmerCharge: vi.fn(),
  commanderManques: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, success: toasts.success, error: toasts.error } }
})

// `../../ui` re-exports `ErrorBoundary`, qui importe `../lib/monitoring`, qui
// tente un `import("@sentry/react")` dynamique littéral (chunk paresseux,
// no-op sans DSN) — un package absent de ce node_modules partagé (jamais une
// dépendance déclarée, cf. package.json/package-lock.json) fait échouer
// l'ANALYSE STATIQUE de Vite au transform, même si l'appel réel est dans un
// try/catch. Sans rapport avec ce correctif : on neutralise juste ce module
// pour pouvoir exécuter ce test sur ce host.
vi.mock('../../lib/monitoring', () => ({
  captureException: vi.fn(), initMonitoring: vi.fn(), suivreSocieteDuStore: vi.fn(),
}))

import { PreparationPanel } from './InterventionFieldExecution'

const INTERVENTION = { id: 11 }

// Miroir de `InterventionPreparationSerializer` (10 lignes matériel, 0 outil) :
// c'est exactement la forme du corps que `cocher-materiel`/`preparation`
// renvoient côté serveur (`_prep_response`).
function prepPayload(materielCharge) {
  return {
    materiel: Array.from({ length: 10 }, (_, i) => ({
      id: i + 1, designation: `Ligne ${i + 1}`, quantite_requise: 1,
      charge: materielCharge.includes(i + 1), manquant: false,
    })),
    outils: [],
    completion: materielCharge.length === 0 ? 0 : materielCharge.length * 10,
    nb_manques: 0,
    tout_charge: false,
    kit_nom: null,
  }
}

beforeEach(() => {
  api.getPreparation.mockResolvedValue({ data: prepPayload([]) })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PreparationPanel — ERR-QAH-CHANTIERS-PREPARATION-MATERIEL-DISAPPEARS', () => {
  it('cocher la première ligne garde les 10 lignes, 1 cochée, 10 % — jamais « Aucun matériel »', async () => {
    const user = userEvent.setup()
    // Réponse réelle de `cocher-materiel` : 10 lignes, la 1ʳᵉ chargée, 10 %.
    api.cocherMateriel.mockResolvedValue({ data: prepPayload([1]) })
    render(<MemoryRouter><PreparationPanel intervention={INTERVENTION} /></MemoryRouter>)

    const cases = await screen.findAllByRole('checkbox')
    expect(cases).toHaveLength(10)
    await user.click(cases[0])

    // Les 10 lignes restent visibles — jamais « Aucun matériel à préparer. ».
    await waitFor(() => expect(screen.getAllByRole('checkbox')).toHaveLength(10))
    expect(screen.queryByText('Aucun matériel à préparer.')).not.toBeInTheDocument()
    // 1 case cochée, 10 % affiché (badge + corps sont le MÊME `completion`).
    expect(screen.getAllByRole('checkbox')
      .filter((c) => c.getAttribute('aria-checked') === 'true')).toHaveLength(1)
    expect(screen.getByText('10%')).toBeInTheDocument()
    // « Confirmer « Tout est chargé » » ne s'active pas tant que tout n'est
    // pas coché (9 lignes encore décochées) — le bug l'activait à tort en
    // vidant `prep.materiel` (every() sur un tableau vide = true).
    expect(screen.getByRole('button', { name: 'Confirmer « Tout est chargé »' }))
      .toBeDisabled()
  })
})
