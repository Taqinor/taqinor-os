import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* WIR210 — hors réseau, la consommation matériel (F11) et les n° de série (F9)
   étaient PERDUS alors que les handlers de rejeu serveur
   (`intervention.consommation_ligne`, `intervention.serial`) existaient déjà :
   les deux appels n'étaient simplement pas enveloppés dans
   `withOfflineFallback`.

   LA distinction qui compte : un échec RÉSEAU (pas de `response`) enfile
   l'opération ; une erreur APPLICATIVE (4xx, donc avec `response`) reste
   VISIBLE et n'est jamais enfilée silencieusement. */

const withOfflineFallbackMock = vi.fn()
vi.mock('./offline/fieldOutbox', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    withOfflineFallback: (...a) => withOfflineFallbackMock(...a),
  }
})

vi.mock('../../api/installationsApi', () => ({
  default: {
    getSerials: vi.fn(),
    ajouterSerial: vi.fn(),
    supprimerSerial: vi.fn(),
    getConsommation: vi.fn(),
    modifierLigneConsommation: vi.fn(),
    ajouterLigneConsommation: vi.fn(),
    validerConsommation: vi.fn(),
  },
}))

const toastMock = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  return { ...actual, toast: toastMock }
})

vi.mock('../../pages/preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))

import installationsApi from '../../api/installationsApi'
import { FIELD_OPS } from './offline/fieldOutbox'
import { SerialsPanel, ConsommationPanel } from './InterventionCapturePanels'

const INTERVENTION = { id: 12, reference: 'INT-001' }

// Par défaut : l'appel en ligne passe (comportement inchangé).
const enLigne = () => withOfflineFallbackMock.mockImplementation(
  async (appel) => ({ queued: false, data: await appel() }))
// Réseau coupé : withOfflineFallback enfile et renvoie queued.
const horsLigne = () => withOfflineFallbackMock.mockResolvedValue(
  { queued: true, clientOpId: 'op-1' })
// Erreur applicative : withOfflineFallback relaie l'erreur (jamais d'enfilage).
const erreurAppli = (err) => withOfflineFallbackMock.mockRejectedValue(err)

beforeEach(() => {
  vi.clearAllMocks()
  installationsApi.getSerials.mockResolvedValue({ data: [] })
  installationsApi.ajouterSerial.mockResolvedValue({ data: { id: 1 } })
  installationsApi.modifierLigneConsommation.mockResolvedValue({ data: {} })
  installationsApi.getConsommation.mockResolvedValue({
    data: {
      valide: false,
      lignes: [{
        id: 55, designation: 'Câble 6mm²', quantite_prevue: '50.00',
        quantite_utilisee: '0.00', variance: 0, justification: '',
        justification_requise: false, hors_nomenclature: false,
      }],
    },
  })
})
afterEach(() => { cleanup() })

describe('WIR210 — capture terrain hors-ligne', () => {
  it('n° de série : échec réseau → enfilé sous FIELD_OPS.SERIAL', async () => {
    horsLigne()
    render(<SerialsPanel intervention={INTERVENTION} />)
    await waitFor(() => expect(installationsApi.getSerials).toHaveBeenCalled())

    fireEvent.change(screen.getByPlaceholderText(/N° de série/), { target: { value: 'SN-9' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter le relev/ }))

    await waitFor(() => expect(withOfflineFallbackMock).toHaveBeenCalled())
    const [, opType, payload] = withOfflineFallbackMock.mock.calls[0]
    expect(opType).toBe(FIELD_OPS.SERIAL)
    expect(payload).toMatchObject({ intervention: 12, numero_serie: 'SN-9' })
    expect(toastMock.success).toHaveBeenCalledWith(
      expect.stringMatching(/Hors ligne/))
  })

  it('consommation : échec réseau → enfilé sous FIELD_OPS.CONSOMMATION_LIGNE', async () => {
    horsLigne()
    render(<ConsommationPanel intervention={INTERVENTION} />)
    await waitFor(() => expect(installationsApi.getConsommation).toHaveBeenCalled())

    const champ = await screen.findByDisplayValue('0.00')
    fireEvent.change(champ, { target: { value: '42' } })
    fireEvent.blur(champ)

    await waitFor(() => expect(withOfflineFallbackMock).toHaveBeenCalled())
    const [, opType, payload] = withOfflineFallbackMock.mock.calls[0]
    expect(opType).toBe(FIELD_OPS.CONSOMMATION_LIGNE)
    // Le rejeu serveur (`_h_consommation_ligne`) attend intervention + ligne.
    expect(payload).toMatchObject({ intervention: 12, ligne: 55, quantite_utilisee: '42' })
    expect(toastMock.success).toHaveBeenCalledWith(
      expect.stringMatching(/Hors ligne/))
  })

  it('consommation : un 4xx applicatif reste VISIBLE, jamais enfilé', async () => {
    erreurAppli({ response: { status: 400, data: { detail: 'Quantité invalide.' } } })
    render(<ConsommationPanel intervention={INTERVENTION} />)
    await waitFor(() => expect(installationsApi.getConsommation).toHaveBeenCalled())

    const champ = await screen.findByDisplayValue('0.00')
    fireEvent.change(champ, { target: { value: '-1' } })
    fireEvent.blur(champ)

    await waitFor(() => expect(toastMock.error).toHaveBeenCalled())
    expect(toastMock.success).not.toHaveBeenCalledWith(
      expect.stringMatching(/Hors ligne/))
  })

  it('n° de série enfilé AVEC photo : la perte de la plaque est annoncée en FR', async () => {
    horsLigne()
    render(<SerialsPanel intervention={INTERVENTION} />)
    await waitFor(() => expect(installationsApi.getSerials).toHaveBeenCalled())

    // Une photo de plaque est choisie : la file JSON ne transporte pas de
    // binaire et le rejeu serveur crée le relevé SANS photo — on le DIT.
    const fichier = new File(['x'], 'plaque.jpg', { type: 'image/jpeg' })
    const input = document.querySelector('input[type="file"]')
    Object.defineProperty(input, 'files', { value: [fichier], configurable: true })
    fireEvent.change(input)

    fireEvent.change(screen.getByPlaceholderText(/N° de série/), { target: { value: 'SN-9' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter le relev/ }))

    await waitFor(() => expect(toastMock.warning).toHaveBeenCalledWith(
      expect.stringMatching(/Photo de plaque non enfilée/)))
  })

  it('en ligne : comportement inchangé (message nominal, pas de mention hors-ligne)', async () => {
    enLigne()
    render(<ConsommationPanel intervention={INTERVENTION} />)
    await waitFor(() => expect(installationsApi.getConsommation).toHaveBeenCalled())

    const champ = await screen.findByDisplayValue('0.00')
    fireEvent.change(champ, { target: { value: '10' } })
    fireEvent.blur(champ)

    await waitFor(() => expect(installationsApi.modifierLigneConsommation)
      .toHaveBeenCalledWith(12, { ligne: 55, quantite_utilisee: '10' }))
    expect(toastMock.success).not.toHaveBeenCalledWith(
      expect.stringMatching(/Hors ligne/))
  })
})
