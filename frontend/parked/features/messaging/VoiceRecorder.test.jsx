import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock de l'instance axios (l'upload du mémo passe par /chat/messages/upload/).
vi.mock('../../api/axios', () => ({
  default: { post: vi.fn(() => Promise.resolve({ data: { id: 1, kind: 'voice' } })) },
}))
vi.mock('../../lib/toast', () => ({ toastError: vi.fn() }))

import api from '../../api/axios'
import VoiceRecorder from './VoiceRecorder'

// ── Faux MediaRecorder + getUserMedia, pilotables depuis les tests. ──
class FakeMediaRecorder {
  constructor(stream) {
    this.stream = stream
    this.mimeType = 'audio/webm'
    this.ondataavailable = null
    this.onstop = null
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['x'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

function installMediaMocks() {
  globalThis.MediaRecorder = FakeMediaRecorder
  const track = { stop: vi.fn() }
  navigator.mediaDevices = {
    getUserMedia: vi.fn(() => Promise.resolve({ getTracks: () => [track] })),
  }
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
}

describe('VoiceRecorder (S17)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    installMediaMocks()
  })
  afterEach(() => {
    cleanup()
    delete globalThis.MediaRecorder
  })

  it('ne rend rien si l’enregistrement n’est pas supporté', () => {
    delete globalThis.MediaRecorder
    const { container } = render(<VoiceRecorder conversationId={1} />)
    expect(container.firstChild).toBeNull()
  })

  it('enregistre, prévisualise puis envoie le mémo vocal avec kind=voice', async () => {
    const onSent = vi.fn()
    render(<VoiceRecorder conversationId={42} onSent={onSent} />)

    await userEvent.click(screen.getByLabelText('Enregistrer une note vocale'))
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled()

    // En cours d'enregistrement : bouton « Arrêter » visible.
    const stopBtn = await screen.findByLabelText('Arrêter l’enregistrement')
    await userEvent.click(stopBtn)

    // Aperçu : on peut envoyer.
    const sendBtn = await screen.findByLabelText('Envoyer la note vocale')
    await userEvent.click(sendBtn)

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const [url, fd] = api.post.mock.calls[0]
    expect(url).toBe('/chat/messages/upload/')
    expect(fd.get('kind')).toBe('voice')
    expect(fd.get('conversation')).toBe('42')
    expect(fd.get('file')).toBeInstanceOf(File)
    await waitFor(() => expect(onSent).toHaveBeenCalledWith({ id: 1, kind: 'voice' }))
  })

  it('le bouton supprimer abandonne l’aperçu sans envoyer', async () => {
    render(<VoiceRecorder conversationId={1} />)
    await userEvent.click(screen.getByLabelText('Enregistrer une note vocale'))
    await userEvent.click(await screen.findByLabelText('Arrêter l’enregistrement'))
    await userEvent.click(await screen.findByLabelText('Supprimer la note vocale'))
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Enregistrer une note vocale')).toBeInTheDocument()
  })

  // ── VX173 — mimeType négocié (fin du blob mp4 étiqueté « webm ») ──────────
  it('WebKit (MediaRecorder mp4-only) : le mémo envoyé est bien audio/mp4, jamais "webm" en dur', async () => {
    // Simule Safari : webm non supporté, seul mp4 l'est — la négociation
    // (`pickAudioMimeType`, source unique partagée avec useVoiceChat.js) doit
    // choisir mp4 et le passer en option au constructeur.
    class FakeMediaRecorderMp4Only {
      static isTypeSupported(type) { return type === 'audio/mp4' }
      constructor(stream, options) {
        this.stream = stream
        this.mimeType = options?.mimeType || ''
        this.ondataavailable = null
        this.onstop = null
      }
      start() { this.state = 'recording' }
      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob(['x'], { type: this.mimeType || 'audio/mp4' }) })
        this.onstop?.()
      }
    }
    globalThis.MediaRecorder = FakeMediaRecorderMp4Only

    render(<VoiceRecorder conversationId={7} />)
    await userEvent.click(screen.getByLabelText('Enregistrer une note vocale'))
    await userEvent.click(await screen.findByLabelText('Arrêter l’enregistrement'))
    await userEvent.click(await screen.findByLabelText('Envoyer la note vocale'))

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    const [, fd] = api.post.mock.calls[0]
    const file = fd.get('file')
    expect(file.type).toBe('audio/mp4')
    expect(file.name.endsWith('.m4a')).toBe(true)
    expect(file.type).not.toBe('audio/webm')
  })
})
