import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import MicDicteeButton from './MicDicteeButton'
import { isDictationSupported } from '../ui/DictationButton'

/* MicDicteeButton — bouton micro partagé (dictée), même mécanique que EZ15
   (`ui/DictationButton.jsx`) : détection feature-based, fr-FR, streaming,
   relance après coupure de silence, arrêt volontaire respecté, démontage
   propre. Différence assumée par rapport à EZ15 : un refus de permission
   affiche un message COURT visible sous le bouton (jamais un crash). Aucun
   vrai micro : faux constructeur Web Speech injecté sur `window`. */

class FakeRecognition {
  static derniere = null
  constructor() {
    this.lang = null
    this.continuous = false
    this.interimResults = false
    this.startCount = 0
    this.stopCount = 0
    FakeRecognition.derniere = this
  }
  start() { this.startCount += 1 }
  stop() { this.stopCount += 1 }
}

const installerApi = () => {
  FakeRecognition.derniere = null
  window.webkitSpeechRecognition = FakeRecognition
  return () => { delete window.webkitSpeechRecognition }
}

afterEach(() => {
  cleanup()
  delete window.webkitSpeechRecognition
  delete window.SpeechRecognition
  vi.restoreAllMocks()
})

describe('MicDicteeButton', () => {
  it('SANS l’API du navigateur, aucun bouton n’est rendu (masqué)', () => {
    expect(isDictationSupported(window)).toBe(false)
    const { container } = render(<MicDicteeButton onTexte={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('AVEC l’API, démarre en fr-FR, en continu et en streaming', () => {
    const off = installerApi()
    render(<MicDicteeButton onTexte={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    expect(rec.lang).toBe('fr-FR')
    expect(rec.continuous).toBe(true)
    expect(rec.interimResults).toBe(true)
    expect(rec.startCount).toBe(1)
    off()
  })

  it('remonte UNIQUEMENT les segments FINAUX via onTexte, l’appelant append', () => {
    const off = installerApi()
    const onTexte = vi.fn()
    render(<MicDicteeButton onTexte={onTexte} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere

    rec.onresult({ resultIndex: 0, results: [{ isFinal: false, 0: { transcript: 'bonjour l' } }] })
    expect(onTexte).not.toHaveBeenCalled()

    rec.onresult({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: '  Bonjour l’équipe. ' } }] })
    expect(onTexte).toHaveBeenCalledWith('Bonjour l’équipe.')
    rec.onresult({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: 'Belle journée.' } }] })
    expect(onTexte).toHaveBeenLastCalledWith('Belle journée.')
    expect(onTexte).toHaveBeenCalledTimes(2)
    off()
  })

  it('la coupure auto après un silence RELANCE la dictée', () => {
    const off = installerApi()
    render(<MicDicteeButton onTexte={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    expect(rec.startCount).toBe(1)
    act(() => { rec.onend() })
    expect(rec.startCount).toBe(2)
    off()
  })

  it('un arrêt VOLONTAIRE est respecté (aucune relance)', () => {
    const off = installerApi()
    render(<MicDicteeButton onTexte={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    fireEvent.click(screen.getByRole('button', { name: /arrêter la dictée/i }))
    expect(rec.stopCount).toBe(1)
    act(() => { rec.onend() })
    expect(rec.startCount).toBe(1)
    off()
  })

  it('un refus de permission affiche un message COURT sous le bouton, sans crash', () => {
    const off = installerApi()
    render(<MicDicteeButton onTexte={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    act(() => { rec.onerror({ error: 'not-allowed' }) })
    act(() => { rec.onend() })
    expect(rec.startCount).toBe(1) // pas de relance après un refus de permission
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Autorisez le micro dans votre navigateur pour dicter.')
    off()
  })

  it('une erreur SANS rapport à la permission ne pose aucun message', () => {
    const off = installerApi()
    render(<MicDicteeButton onTexte={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    act(() => { rec.onerror({ error: 'no-speech' }) })
    act(() => { rec.onend() })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    off()
  })

  it('le démontage coupe le micro', () => {
    const off = installerApi()
    const { unmount } = render(<MicDicteeButton onTexte={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    unmount()
    expect(rec.stopCount).toBeGreaterThanOrEqual(1)
    off()
  })
})
