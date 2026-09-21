import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('../../api/messagesApi', () => ({
  default: { getAttachment: vi.fn(() => Promise.resolve({ data: new Blob(['a'], { type: 'audio/webm' }) })) },
}))

import messagesApi from '../../api/messagesApi'
import VoiceMessage from './VoiceMessage'

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
})

describe('VoiceMessage (S17)', () => {
  it('rend un lecteur audio depuis l’URL directe sans télécharger', () => {
    render(<VoiceMessage messageId={1} attachment={{ id: 9, url: '/f/9', transcript_status: 'disabled' }} />)
    expect(screen.getByLabelText('Note vocale')).toBeInTheDocument()
    expect(messagesApi.getAttachment).not.toHaveBeenCalled()
  })

  it('télécharge le binaire via le proxy quand aucune URL n’est fournie', async () => {
    render(<VoiceMessage messageId={5} attachment={{ id: 7, transcript_status: 'disabled' }} />)
    await waitFor(() => expect(messagesApi.getAttachment).toHaveBeenCalledWith(5, 7))
  })

  it('affiche « Transcription… » tant que le statut est pending', () => {
    render(<VoiceMessage messageId={1} attachment={{ id: 1, url: '/f/1', transcript_status: 'pending' }} />)
    expect(screen.getByText('Transcription…')).toBeInTheDocument()
  })

  it('affiche le transcript quand le statut est done', () => {
    render(<VoiceMessage messageId={1} attachment={{ id: 1, url: '/f/1', transcript_status: 'done', transcript: 'Bonjour tout le monde' }} />)
    expect(screen.getByText('Bonjour tout le monde')).toBeInTheDocument()
  })

  it('n’affiche AUCUNE ligne de transcription quand disabled', () => {
    render(<VoiceMessage messageId={1} attachment={{ id: 1, url: '/f/1', transcript_status: 'disabled' }} />)
    expect(screen.queryByTestId('voice-transcript')).toBeNull()
  })
})
