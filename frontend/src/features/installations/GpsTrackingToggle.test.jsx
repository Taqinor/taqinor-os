import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTMOB9 — suivi de position `watchPosition` derrière un consentement
   explicite, limité à la session d'intervention ouverte ('en_route'/
   'sur_site'). Vérifie : (1) rien ne s'affiche hors session ouverte,
   (2) l'interrupteur reste OFF par défaut (jamais de tracking silencieux),
   (3) l'activer démarre `watchPosition` et remonte via `pingPosition`,
   (4) un 403 (consentement absent) coupe proprement et bascule le message,
   (5) désactiver / démonter arrête `watchPosition` (`clearWatch`). */

const pingPosition = vi.fn()

vi.mock('../../api/installationsApi', () => ({
  default: {
    pingPosition: (...a) => pingPosition(...a),
  },
}))

import GpsTrackingToggle from './GpsTrackingToggle'

const watchPosition = vi.fn()
const clearWatch = vi.fn()

beforeEach(() => {
  pingPosition.mockReset()
  watchPosition.mockReset()
  clearWatch.mockReset()
  vi.stubGlobal('navigator', {
    ...globalThis.navigator,
    geolocation: { watchPosition, clearWatch },
  })
})

afterEach(() => {
  // Démonte AVANT de retirer le mock `navigator.geolocation` : le nettoyage
  // de l'effet (`clearWatch`) doit encore trouver le mock en place.
  cleanup()
  vi.unstubAllGlobals()
})

describe('GpsTrackingToggle (NTMOB9)', () => {
  it("n'affiche rien hors session d'intervention ouverte", () => {
    render(<GpsTrackingToggle intervention={{ id: 1, statut: 'prete' }} />)
    expect(screen.queryByTestId('gps-tracking-toggle')).not.toBeInTheDocument()
  })

  it("l'interrupteur est visible mais OFF par défaut pendant une session ouverte (jamais de tracking silencieux)", () => {
    render(<GpsTrackingToggle intervention={{ id: 1, statut: 'sur_site' }} />)
    const interrupteur = screen.getByRole('switch', {
      name: 'Activer le suivi de position pendant cette intervention',
    })
    expect(interrupteur).not.toBeChecked()
    expect(watchPosition).not.toHaveBeenCalled()
  })

  it('activer l\'interrupteur démarre watchPosition et remonte la position via pingPosition', async () => {
    const user = userEvent.setup()
    watchPosition.mockImplementation((success) => {
      success({ coords: { latitude: 33.5, longitude: -7.6, accuracy: 12 } })
      return 42
    })
    pingPosition.mockResolvedValue({ data: {} })
    render(<GpsTrackingToggle intervention={{ id: 7, statut: 'en_route' }} />)

    await user.click(screen.getByRole('switch', {
      name: 'Activer le suivi de position pendant cette intervention',
    }))

    expect(watchPosition).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(pingPosition).toHaveBeenCalledWith(
      expect.objectContaining({ lat: 33.5, lng: -7.6, intervention: 7 }),
    ))
  })

  it('un 403 (aucun consentement actif) coupe proprement et affiche le repli pointage manuel', async () => {
    const user = userEvent.setup()
    watchPosition.mockImplementation((success) => {
      success({ coords: { latitude: 33.5, longitude: -7.6, accuracy: 12 } })
      return 42
    })
    pingPosition.mockRejectedValue({ response: { status: 403 } })
    render(<GpsTrackingToggle intervention={{ id: 7, statut: 'en_route' }} />)

    const interrupteur = screen.getByRole('switch', {
      name: 'Activer le suivi de position pendant cette intervention',
    })
    await user.click(interrupteur)

    await waitFor(() => expect(interrupteur).not.toBeChecked())
    expect(await screen.findByText(/pointage manuel/)).toBeInTheDocument()
  })

  it('désactiver arrête watchPosition (clearWatch)', async () => {
    const user = userEvent.setup()
    watchPosition.mockReturnValue(99)
    render(<GpsTrackingToggle intervention={{ id: 7, statut: 'en_route' }} />)

    const interrupteur = screen.getByRole('switch', {
      name: 'Activer le suivi de position pendant cette intervention',
    })
    await user.click(interrupteur) // on
    expect(watchPosition).toHaveBeenCalledTimes(1)
    await user.click(interrupteur) // off
    expect(clearWatch).toHaveBeenCalledWith(99)
  })
})
