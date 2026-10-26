import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CONTRAT from '../../../../backend/django_core/apps/installations/contract_samples/intervention_serials_attendus.json'

/* Revue chantier 26/10/2026 — écran « N° série » : jauge par produit depuis
   `serials-attendus` (PAYLOAD = l'exemple du contrat, jamais inventé), choix
   du composant dans une liste fermée (produit envoyé), scanner code-barres
   qui remplit le numéro (source « scan »), repli quand le navigateur ne sait
   pas scanner. */

const outbox = vi.hoisted(() => ({
  enqueue: vi.fn(() => Promise.resolve('op-1')),
  queuePhoto: vi.fn(() => Promise.resolve('photo-1')),
  FIELD_OPS: { SERIAL: 'intervention.serial' },
  withOfflineFallback: async (onlineCall) => {
    const data = await onlineCall('cle-1')
    return { queued: false, data }
  },
}))
vi.mock('./offline/fieldOutbox', () => ({
  withOfflineFallback: outbox.withOfflineFallback,
  queuePhoto: outbox.queuePhoto,
  FIELD_OPS: outbox.FIELD_OPS,
}))

const api = vi.hoisted(() => ({
  getSerials: vi.fn(),
  getSerialsAttendus: vi.fn(),
  ajouterSerial: vi.fn(),
  supprimerSerial: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

vi.mock('../../pages/preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))

const scanner = vi.hoisted(() => ({ supported: true, onDetected: null }))
vi.mock('../pwa/useBarcodeScanner', () => ({
  barcodeScanSupported: () => scanner.supported,
  default: ({ onDetected }) => {
    scanner.onDetected = onDetected
    return {
      supported: true, active: true, error: null,
      videoRef: { current: null }, start: () => {}, stop: () => {},
    }
  },
}))

const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, success: toasts.success, error: toasts.error } }
})

import { SerialsPanel } from './InterventionCapturePanels'

const INTERVENTION = { id: 12 }

beforeEach(() => {
  scanner.supported = true
  scanner.onDetected = null
  api.getSerials.mockResolvedValue({ data: [] })
  api.getSerialsAttendus.mockResolvedValue({ data: CONTRAT.exemple })
  api.ajouterSerial.mockResolvedValue({ data: { id: 1 } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SerialsPanel — séries attendues (revue chantier 26/10/2026)', () => {
  it('affiche la progression globale et par produit', async () => {
    render(<SerialsPanel intervention={INTERVENTION} />)
    const bloc = await screen.findByTestId('serials-progression')
    expect(bloc.textContent).toContain('N° de série : 3/11 relevés')
    expect(bloc.textContent).toContain('Panneau Canadian Solar 710W 2/10')
    expect(bloc.textContent).toContain('Onduleur Huawei 10 kW triphasé 1/1')
  })

  it('le relevé part du produit choisi dans la liste fermée', async () => {
    const user = userEvent.setup()
    render(<SerialsPanel intervention={INTERVENTION} />)
    const liste = await screen.findByRole('combobox', { name: 'Composant' })
    // Un seul produit encore incomplet (les panneaux) : défaut automatique.
    expect(liste.value).toBe('34')
    await user.type(screen.getByLabelText('N° de série'), 'CS710-0003')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))
    await waitFor(() => expect(api.ajouterSerial).toHaveBeenCalled())
    const [, corps] = api.ajouterSerial.mock.calls[0]
    expect(corps).toMatchObject({
      produit: 34, designation: 'Panneau Canadian Solar 710W',
      numero_serie: 'CS710-0003', capture_source: 'saisie',
      caracteristiques: { fabricant: 'Canadian Solar' },
    })
  })

  it('plusieurs produits incomplets : aucun défaut, ajout refusé sans choix', async () => {
    const user = userEvent.setup()
    const deux = JSON.parse(JSON.stringify(CONTRAT.exemple))
    deux.produits.forEach((p) => { p.releve = 0; p.manquant = p.attendu })
    api.getSerialsAttendus.mockResolvedValue({ data: deux })
    render(<SerialsPanel intervention={INTERVENTION} />)
    const liste = await screen.findByRole('combobox', { name: 'Composant' })
    expect(liste.value).toBe('')
    expect(screen.getByRole('option', { name: 'Choisir le composant…' })).toBeTruthy()
    await user.type(screen.getByLabelText('N° de série'), 'INV-0001')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))
    expect((await screen.findByRole('alert')).textContent).toBe('Choisissez le composant')
    expect(api.ajouterSerial).not.toHaveBeenCalled()
    await user.selectOptions(liste, String(deux.produits[1].produit_id))
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))
    await waitFor(() => expect(api.ajouterSerial).toHaveBeenCalled())
    expect(api.ajouterSerial.mock.calls[0][1].produit).toBe(deux.produits[1].produit_id)
  })

  it('« Autre composant » rouvre la désignation libre', async () => {
    const user = userEvent.setup()
    render(<SerialsPanel intervention={INTERVENTION} />)
    const liste = await screen.findByRole('combobox', { name: 'Composant' })
    await user.selectOptions(liste, 'Autre composant')
    await user.type(
      screen.getByPlaceholderText('Composant (onduleur, panneau…)'), 'Smart meter')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))
    await waitFor(() => expect(api.ajouterSerial).toHaveBeenCalled())
    const [, corps] = api.ajouterSerial.mock.calls[0]
    expect(corps.produit).toBeUndefined()
    expect(corps.designation).toBe('Smart meter')
  })

  it('le scan remplit le numéro et marque la source « scan »', async () => {
    const user = userEvent.setup()
    render(<SerialsPanel intervention={INTERVENTION} />)
    await screen.findByRole('combobox', { name: 'Composant' })
    await user.click(screen.getByRole('button', { name: /Scanner/ }))
    await waitFor(() => expect(scanner.onDetected).toBeTypeOf('function'))
    act(() => { scanner.onDetected('CS710-0042') })
    expect(screen.getByLabelText('N° de série').value).toBe('CS710-0042')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))
    await waitFor(() => expect(api.ajouterSerial).toHaveBeenCalled())
    expect(api.ajouterSerial.mock.calls[0][1]).toMatchObject({
      numero_serie: 'CS710-0042', capture_source: 'scan' })
  })

  it('navigateur sans scanner : message de repli, saisie manuelle', async () => {
    scanner.supported = false
    const user = userEvent.setup()
    render(<SerialsPanel intervention={INTERVENTION} />)
    await screen.findByRole('combobox', { name: 'Composant' })
    await user.click(screen.getByRole('button', { name: /Scanner/ }))
    expect(screen.getByRole('status').textContent).toBe(
      'Scanner non disponible sur ce navigateur — saisissez le numéro')
  })

  it('doublon refusé par le serveur : message sous le champ', async () => {
    const user = userEvent.setup()
    api.ajouterSerial.mockRejectedValue({
      response: { status: 400, data: { numero_serie: 'N° de série déjà relevé.' } },
    })
    render(<SerialsPanel intervention={INTERVENTION} />)
    await screen.findByRole('combobox', { name: 'Composant' })
    await user.type(screen.getByLabelText('N° de série'), 'CS710-0001')
    await user.click(screen.getByRole('button', { name: /Ajouter le relevé/ }))
    expect((await screen.findByRole('alert')).textContent).toBe(
      'N° de série déjà relevé.')
  })
})
