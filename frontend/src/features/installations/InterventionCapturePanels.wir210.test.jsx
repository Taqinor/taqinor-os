import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR210 — hors-ligne terrain : la consommation matériel (F11) et les n° de
   série (F9) partaient en direct et étaient PERDUS sans réseau, alors que les
   handlers serveur `intervention.consommation_ligne` / `intervention.serial`
   existaient depuis N91. Ce test vérifie le CÂBLAGE :
   (1) échec RÉSEAU → op enfilée avec le bon op_type et la bonne charge ;
   (2) erreur APPLICATIVE 4xx → jamais enfilée, elle reste visible ;
   (3) la photo de plaque part dans la file BINAIRE existante ;
   hors périmètre (inchangés) : `addExtra` et `validerConsommation`. */

const outbox = vi.hoisted(() => {
  const enqueue = vi.fn(() => Promise.resolve('op-1'))
  return {
    enqueue,
    queuePhoto: vi.fn(() => Promise.resolve('photo-1')),
    FIELD_OPS: {
      SERIAL: 'intervention.serial',
      CONSOMMATION_LIGNE: 'intervention.consommation_ligne',
    },
    // Reproduit fidèlement la règle du vrai helper : pas de `response` axios
    // = panne réseau (on enfile) ; sinon c'est une erreur applicative (on
    // relance, jamais d'enfilage).
    withOfflineFallback: async (onlineCall, opType, payload) => {
      try {
        const data = await onlineCall()
        return { queued: false, data }
      } catch (err) {
        if (err?.response) throw err
        const clientOpId = await enqueue(opType, payload)
        return { queued: true, clientOpId }
      }
    },
  }
})

vi.mock('./offline/fieldOutbox', () => ({
  withOfflineFallback: outbox.withOfflineFallback,
  queuePhoto: outbox.queuePhoto,
  FIELD_OPS: outbox.FIELD_OPS,
}))

const api = vi.hoisted(() => ({
  getSerials: vi.fn(),
  ajouterSerial: vi.fn(),
  supprimerSerial: vi.fn(),
  getConsommation: vi.fn(),
  modifierLigneConsommation: vi.fn(),
  ajouterLigneConsommation: vi.fn(),
  validerConsommation: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

vi.mock('../../pages/preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))

const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, success: toasts.success, error: toasts.error } }
})

import { SerialsPanel, ConsommationPanel } from './InterventionCapturePanels'

const INTERVENTION = { id: 42 }

const CONSOMMATION = {
  valide: false,
  lignes: [
    {
      id: 5, designation: 'Panneau 450W', quantite_prevue: '10',
      quantite_utilisee: '10', variance: 0, justification: '',
      justification_requise: false, hors_nomenclature: false,
    },
  ],
}

// axios : une panne réseau n'a PAS de `response` ; un refus serveur en a une.
const erreurReseau = () => Object.assign(new Error('Network Error'), { response: undefined })
const erreur400 = () => ({ response: { status: 400, data: { detail: 'Quantité invalide.' } } })

beforeEach(() => {
  api.getSerials.mockResolvedValue({ data: [] })
  api.ajouterSerial.mockResolvedValue({ data: { id: 1 } })
  api.getConsommation.mockResolvedValue({ data: CONSOMMATION })
  api.modifierLigneConsommation.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ConsommationPanel — WIR210 hors-ligne (F11)', () => {
  it('échec réseau → op enfilée en `intervention.consommation_ligne`', async () => {
    const user = userEvent.setup()
    api.modifierLigneConsommation.mockRejectedValue(erreurReseau())
    render(<ConsommationPanel intervention={INTERVENTION} />)

    const champ = await screen.findByDisplayValue('10')
    await user.clear(champ)
    await user.type(champ, '12')
    await user.tab()

    await waitFor(() => expect(outbox.enqueue).toHaveBeenCalledWith(
      'intervention.consommation_ligne',
      { intervention: 42, ligne: 5, quantite_utilisee: '12' },
    ))
    expect(toasts.success).toHaveBeenCalledWith(
      'Hors ligne — enregistré, synchro au retour du réseau.')
  })

  it('erreur applicative 4xx → JAMAIS enfilée, elle reste visible', async () => {
    const user = userEvent.setup()
    api.modifierLigneConsommation.mockRejectedValue(erreur400())
    render(<ConsommationPanel intervention={INTERVENTION} />)

    const champ = await screen.findByDisplayValue('10')
    await user.clear(champ)
    await user.type(champ, '12')
    await user.tab()

    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith('Mise à jour impossible.'))
    expect(outbox.enqueue).not.toHaveBeenCalled()
  })
})

describe('SerialsPanel — WIR210 hors-ligne (F9)', () => {
  it('échec réseau → op enfilée en `intervention.serial`', async () => {
    const user = userEvent.setup()
    api.ajouterSerial.mockRejectedValue(erreurReseau())
    render(<SerialsPanel intervention={INTERVENTION} />)

    await user.type(
      await screen.findByPlaceholderText('Composant (onduleur, panneau…)'), 'Onduleur')
    await user.type(screen.getByPlaceholderText('N° de série (optionnel)'), 'SN-1234')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))

    await waitFor(() => expect(outbox.enqueue).toHaveBeenCalledWith(
      'intervention.serial',
      { intervention: 42, designation: 'Onduleur', numero_serie: 'SN-1234' },
    ))
    expect(toasts.success).toHaveBeenCalledWith(
      'Hors ligne — enregistré, synchro au retour du réseau.')
    // Aucune photo choisie : la file binaire n'est pas sollicitée.
    expect(outbox.queuePhoto).not.toHaveBeenCalled()
  })

  it('erreur applicative 4xx → JAMAIS enfilée, le détail serveur reste visible', async () => {
    const user = userEvent.setup()
    api.ajouterSerial.mockRejectedValue({
      response: { status: 400, data: { detail: 'N° déjà relevé.' } },
    })
    render(<SerialsPanel intervention={INTERVENTION} />)

    await user.type(
      await screen.findByPlaceholderText('Composant (onduleur, panneau…)'), 'Onduleur')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))

    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith('N° déjà relevé.'))
    expect(outbox.enqueue).not.toHaveBeenCalled()
  })
})
