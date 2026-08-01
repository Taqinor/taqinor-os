// NTMOB11 — mode `multiple` (pellicule + géoloc best-effort) de CameraCapture.
// Même patron de mocks caméra que VoiceRecorder.test.jsx (getUserMedia/tracks),
// étendu au canvas (snap → Blob) et à `navigator.geolocation`.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CameraCapture from './CameraCapture'

function installCameraMocks() {
  const track = { stop: vi.fn() }
  navigator.mediaDevices = {
    getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [track] })),
  }
  HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve())
  Object.defineProperty(HTMLVideoElement.prototype, 'videoWidth', {
    configurable: true, value: 640,
  })
  Object.defineProperty(HTMLVideoElement.prototype, 'videoHeight', {
    configurable: true, value: 480,
  })
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() }))
  HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/jpeg;base64,fake')
  HTMLCanvasElement.prototype.toBlob = vi.fn((cb) => {
    cb(new Blob(['x'], { type: 'image/jpeg' }))
  })
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
}

function installGeolocation(behavior) {
  navigator.geolocation = {
    getCurrentPosition: vi.fn((onSuccess, onError) => {
      if (behavior === 'success') {
        onSuccess({ coords: { latitude: 33.5, longitude: -7.6, accuracy: 12 } })
      } else {
        onError(new Error('refused'))
      }
    }),
  }
}

async function takeOnePhoto(user) {
  await user.click(await screen.findByRole('button', { name: /prendre la photo|photo suivante/i }))
}

describe('CameraCapture — NTMOB11 (mode multiple + géoloc)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    installCameraMocks()
  })
  afterEach(() => {
    cleanup()
    delete navigator.geolocation
  })

  it('mode simple (inchangé) : confirmer une photo appelle onCapture(file, geo) puis onClose', async () => {
    installGeolocation('success')
    const onCapture = vi.fn()
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<CameraCapture onCapture={onCapture} onClose={onClose} />)

    await takeOnePhoto(user)
    await user.click(await screen.findByRole('button', { name: /utiliser cette photo/i }))

    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1))
    const [file, geo] = onCapture.mock.calls[0]
    expect(file).toBeInstanceOf(File)
    expect(geo).toEqual({ latitude: 33.5, longitude: -7.6, precision_m: 12 })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('géoloc refusée → geo est null, la capture n’est jamais bloquée', async () => {
    installGeolocation('error')
    const onCapture = vi.fn()
    const user = userEvent.setup()
    render(<CameraCapture onCapture={onCapture} onClose={vi.fn()} />)

    await takeOnePhoto(user)
    await user.click(await screen.findByRole('button', { name: /utiliser cette photo/i }))

    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1))
    expect(onCapture.mock.calls[0][1]).toBeNull()
  })

  it('mode multiple : plusieurs photos appellent onCapture à chaque fois SANS fermer, jusqu’à « Terminé »', async () => {
    installGeolocation('success')
    const onCapture = vi.fn()
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<CameraCapture onCapture={onCapture} onClose={onClose} multiple />)

    // 1re photo.
    await takeOnePhoto(user)
    await user.click(await screen.findByRole('button', { name: /garder et continuer/i }))
    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(1))
    expect(onClose).not.toHaveBeenCalled()

    // 2e photo — le bouton devient « Photo suivante », la pellicule affiche 1 miniature.
    expect(await screen.findByText('1 photo')).toBeInTheDocument()
    await takeOnePhoto(user)
    await user.click(await screen.findByRole('button', { name: /garder et continuer/i }))
    await waitFor(() => expect(onCapture).toHaveBeenCalledTimes(2))
    expect(onClose).not.toHaveBeenCalled()
    expect(await screen.findByText('2 photos')).toBeInTheDocument()

    // Fichiers distincts (jamais le même nom, malgré la valeur par défaut partagée).
    const names = onCapture.mock.calls.map(([file]) => file.name)
    expect(new Set(names).size).toBe(2)

    // Validation finale.
    await user.click(await screen.findByRole('button', { name: /terminé/i }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
