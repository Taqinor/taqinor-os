import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { reponseContrat } from '../../test/fixtures/contractSamples'

/* Revue chantier 26/10/2026 — suivi AUTOMATIQUE pendant la session
   d'intervention (en route / sur site), jamais caché (loi 09-08 / CNDP
   17-2014). Remplace l'interrupteur NTMOB9 (OFF par défaut). Vérifie :
   (1) rien hors session ouverte ; (2) avec `gps_consentement: 'actif'`,
   `watchPosition` démarre SEUL et la puce discrète « Suivi actif » s'affiche
   (fondateur 27/10/2026 — plus de gros bandeau ; refus de l'appareil ⇒ puce
   orange « Suivi interrompu ») ; (3) haute
   précision seulement sur site ; (4) `'a_accepter'` ⇒ carte de la notice,
   aucun suivi, et « J'ai lu et j'accepte » appelle `accepterConsentementGps`
   puis démarre le suivi ; (5) `'absent'` ⇒ ligne discrète ; (6) un 403 coupe
   le suivi ; (7) hors ligne ⇒ tampon puis lot au retour du réseau ; (8)
   « Mes positions du jour » se charge à l'ouverture du volet. La notice vient
   du contrat committé (PACT10), jamais d'une charge utile inventée. */

const pingPosition = vi.fn()
const pingPositionsBatch = vi.fn()
const getMonConsentementGps = vi.fn()
const accepterConsentementGps = vi.fn()
const getMesPositions = vi.fn()

vi.mock('../../api/installationsApi', () => ({
  default: {
    pingPosition: (...a) => pingPosition(...a),
    pingPositionsBatch: (...a) => pingPositionsBatch(...a),
    getMonConsentementGps: (...a) => getMonConsentementGps(...a),
    accepterConsentementGps: (...a) => accepterConsentementGps(...a),
    getMesPositions: (...a) => getMesPositions(...a),
  },
}))

import GpsTrackingToggle, { MesPositionsDuJour, viderTamponsGpsEnAttente } from './GpsTrackingToggle'

const watchPosition = vi.fn()
const clearWatch = vi.fn()
let enLigne = true

const interv = (extra) => ({
  id: 7, statut: 'en_route', installation_reference: 'CH-2026-007',
  gps_consentement: 'actif', ...extra,
})

const position = { coords: { latitude: 33.5, longitude: -7.6, accuracy: 12 }, timestamp: 1767225600000 }

beforeEach(() => {
  for (const f of [pingPosition, pingPositionsBatch, getMonConsentementGps,
    accepterConsentementGps, getMesPositions, watchPosition, clearWatch]) f.mockReset()
  enLigne = true
  window.localStorage.clear()
  getMonConsentementGps.mockResolvedValue(reponseContrat('installations', 'gps_mon_consentement'))
  vi.stubGlobal('navigator', {
    get onLine() { return enLigne },
    geolocation: { watchPosition, clearWatch },
  })
})

afterEach(() => {
  // Démonte AVANT de retirer le mock `navigator.geolocation` : le nettoyage
  // de l'effet (`clearWatch`) doit encore trouver le mock en place.
  cleanup()
  vi.unstubAllGlobals()
})

describe('GpsTrackingToggle — suivi automatique (revue chantier 26/10/2026)', () => {
  it("n'affiche rien et ne suit pas hors session d'intervention ouverte", () => {
    render(<GpsTrackingToggle intervention={interv({ statut: 'prete' })} />)
    expect(screen.queryByTestId('gps-tracking-toggle')).not.toBeInTheDocument()
    expect(watchPosition).not.toHaveBeenCalled()
  })

  it("avec un consentement actif, démarre seul et affiche la puce discrète « Suivi actif »", async () => {
    watchPosition.mockImplementation((success) => { success(position); return 42 })
    pingPosition.mockResolvedValue({ data: {} })
    render(<GpsTrackingToggle intervention={interv()} />)

    expect(watchPosition).toHaveBeenCalledTimes(1)
    expect(watchPosition.mock.calls[0][2]).toEqual(
      expect.objectContaining({ enableHighAccuracy: false }))
    // Fondateur 27/10/2026 — puce discrète au lieu du gros bandeau, jamais cachée.
    const puce = screen.getByTestId('gps-suivi-puce')
    expect(puce.textContent).toContain('Suivi actif')
    expect(puce.getAttribute('title')).toContain('intervention CH-2026-007')
    expect(puce.querySelector('.bg-success')).not.toBeNull()
    expect(screen.queryByText(/Position partagée avec votre responsable/)).not.toBeInTheDocument()
    // Aucun interrupteur : le technicien n'a rien à faire.
    expect(screen.queryByRole('switch')).not.toBeInTheDocument()
    await waitFor(() => expect(pingPosition).toHaveBeenCalledWith(
      expect.objectContaining({
        lat: 33.5, lng: -7.6, intervention: 7,
        captured_at: new Date(position.timestamp).toISOString(),
      })))
  })

  it('haute précision seulement sur site', () => {
    watchPosition.mockReturnValue(1)
    render(<GpsTrackingToggle intervention={interv({ statut: 'sur_site' })} />)
    expect(watchPosition.mock.calls[0][2]).toEqual(
      expect.objectContaining({ enableHighAccuracy: true }))
  })

  it("« Pourquoi ? » ouvre la notice servie par le serveur dans une fenêtre", async () => {
    const user = userEvent.setup()
    watchPosition.mockReturnValue(1)
    render(<GpsTrackingToggle intervention={interv()} />)
    await user.click(screen.getByRole('button', { name: /Pourquoi/ }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    const notice = await screen.findByTestId('gps-notice')
    expect(notice.textContent).toContain('non encore déclaré')
    expect(notice.textContent).toContain('30 jours')
  })

  it("appareil qui refuse la géolocalisation : puce orange « Suivi interrompu », aucun ping", () => {
    watchPosition.mockImplementation((_ok, echec) => { echec({ code: 1 }); return 8 })
    render(<GpsTrackingToggle intervention={interv()} />)
    const puce = screen.getByTestId('gps-suivi-puce')
    expect(puce.textContent).toContain('Suivi interrompu — autorisez la géolocalisation')
    expect(puce.className).toContain('text-warning')
    expect(puce.querySelector('.bg-warning')).not.toBeNull()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(pingPosition).not.toHaveBeenCalled()
  })

  it("consentement à accepter : carte de la notice, aucun suivi, puis accord ⇒ suivi", async () => {
    const user = userEvent.setup()
    watchPosition.mockReturnValue(5)
    accepterConsentementGps.mockResolvedValue({ data: {} })
    render(<GpsTrackingToggle intervention={interv({ gps_consentement: 'a_accepter' })} />)

    expect(await screen.findByTestId('gps-carte-accord')).toBeInTheDocument()
    expect(await screen.findByTestId('gps-notice')).toBeInTheDocument()
    expect(watchPosition).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /J'ai lu et j'accepte/ }))
    expect(accepterConsentementGps).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(watchPosition).toHaveBeenCalledTimes(1))
    expect(screen.getByTestId('gps-tracking-toggle')).toBeInTheDocument()
  })

  it("consentement absent : ligne discrète, aucun suivi", () => {
    render(<GpsTrackingToggle intervention={interv({ gps_consentement: 'absent' })} />)
    expect(screen.getByTestId('gps-non-active').textContent)
      .toContain('Suivi de position non activé pour vous')
    expect(watchPosition).not.toHaveBeenCalled()
  })

  it('un 403 serveur coupe le suivi (clearWatch) et le dit', async () => {
    watchPosition.mockImplementation((success) => { success(position); return 42 })
    pingPosition.mockRejectedValue({ response: { status: 403 } })
    render(<GpsTrackingToggle intervention={interv()} />)
    await waitFor(() => expect(clearWatch).toHaveBeenCalledWith(42))
    expect(await screen.findByText(/refusé par le serveur/)).toBeInTheDocument()
  })

  it('hors ligne : garde la position puis l\'envoie en lot au retour du réseau', async () => {
    enLigne = false
    let rappel
    watchPosition.mockImplementation((success) => { rappel = success; return 3 })
    pingPositionsBatch.mockResolvedValue({ data: { enregistrees: 1, doublons: 0 } })
    render(<GpsTrackingToggle intervention={interv()} />)

    act(() => { rappel(position) })
    expect(pingPosition).not.toHaveBeenCalled()

    enLigne = true
    act(() => { window.dispatchEvent(new Event('online')) })
    await waitFor(() => expect(pingPositionsBatch).toHaveBeenCalledWith(7, [
      expect.objectContaining({ lat: 33.5, lng: -7.6, captured_at: expect.any(String) }),
    ]))
  })

  it('F2 : le tampon hors-ligne part AVANT le relevé live suivant', async () => {
    enLigne = false
    let rappel
    watchPosition.mockImplementation((success) => { rappel = success; return 3 })
    pingPositionsBatch.mockResolvedValue({ data: { enregistrees: 1, doublons: 0 } })
    pingPosition.mockResolvedValue({ data: {} })
    const now = vi.spyOn(Date, 'now').mockReturnValue(1767225600000)
    render(<GpsTrackingToggle intervention={interv()} />)

    act(() => { rappel(position) })
    expect(window.localStorage.getItem('gps-tampon-7')).not.toBeNull()

    enLigne = true
    now.mockReturnValue(1767225600000 + 61 * 1000) // throttle 60 s passé
    act(() => { rappel({ ...position, timestamp: 1767225661000 }) })
    await waitFor(() => expect(pingPosition).toHaveBeenCalledTimes(1))
    expect(pingPositionsBatch).toHaveBeenCalledTimes(1)
    expect(pingPositionsBatch.mock.invocationCallOrder[0])
      .toBeLessThan(pingPosition.mock.invocationCallOrder[0])
    expect(window.localStorage.getItem('gps-tampon-7')).toBeNull()
    now.mockRestore()
  })

  it('F3 : reprend au montage le tampon laissé dans localStorage et l\'envoie', async () => {
    const garde = [{ lat: 33.5, lng: -7.6, accuracy_m: 9, captured_at: '2026-10-26T09:00:00.000Z' }]
    window.localStorage.setItem('gps-tampon-7', JSON.stringify(garde))
    watchPosition.mockReturnValue(1)
    pingPositionsBatch.mockResolvedValue({ data: { enregistrees: 1, doublons: 0 } })
    render(<GpsTrackingToggle intervention={interv()} />)
    await waitFor(() => expect(pingPositionsBatch).toHaveBeenCalledWith(7, garde))
    await waitFor(() => expect(window.localStorage.getItem('gps-tampon-7')).toBeNull())
  })

  it('F3 : session fermée hors ligne ⇒ le tampon survit au démontage puis part depuis « Ma journée »', async () => {
    enLigne = false
    let rappel
    watchPosition.mockImplementation((success) => { rappel = success; return 3 })
    pingPositionsBatch.mockResolvedValue({ data: { enregistrees: 1, doublons: 0 } })
    const { unmount } = render(<GpsTrackingToggle intervention={interv()} />)
    act(() => { rappel(position) })
    unmount()
    expect(pingPositionsBatch).not.toHaveBeenCalled()
    expect(JSON.parse(window.localStorage.getItem('gps-tampon-7'))).toHaveLength(1)

    enLigne = true
    await viderTamponsGpsEnAttente()
    expect(pingPositionsBatch).toHaveBeenCalledWith(7, [
      expect.objectContaining({ lat: 33.5, lng: -7.6 }),
    ])
    expect(window.localStorage.getItem('gps-tampon-7')).toBeNull()
  })

  it('démonter arrête watchPosition (clearWatch)', () => {
    watchPosition.mockReturnValue(99)
    const { unmount } = render(<GpsTrackingToggle intervention={interv()} />)
    unmount()
    expect(clearWatch).toHaveBeenCalledWith(99)
  })
})

describe('MesPositionsDuJour (droit d\'accès)', () => {
  it("ne charge rien tant que le volet est fermé, puis liste mes positions", async () => {
    const user = userEvent.setup()
    getMesPositions.mockResolvedValue({
      data: [{
        id: 1, technicien: 3, technicien_nom: 'ahmed', intervention: 7,
        lat: '33.573150', lng: '-7.589800', accuracy_m: '8.00',
        captured_at: '2026-10-26T09:15:00+01:00', distance_site_km: '0.005',
        hors_perimetre: false,
      }],
    })
    render(<MesPositionsDuJour />)
    expect(getMesPositions).not.toHaveBeenCalled()
    await user.click(screen.getByText('Mes positions du jour'))
    await waitFor(() => expect(getMesPositions).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/0\.005 km du chantier/)).toBeInTheDocument()
  })
})
