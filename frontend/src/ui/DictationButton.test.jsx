import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { DictationButton, isDictationSupported, DICTATION_PRIVACY_FR } from './DictationButton'

/* EZ15 — Dictée INLINE au bureau (Web Speech du navigateur).
   ---------------------------------------------------------------------------
   Ce qui doit rester vrai quoi qu'il arrive :
     • sans l'API (Firefox), il n'y a PAS de bouton — le champ est strictement
       celui d'avant, pas un bouton grisé qui promet ce qu'il ne fait pas ;
     • un refus de permission micro n'est pas une panne à toaster ;
     • la coupure automatique après ~60 s de silence RELANCE, sinon la dictée
       meurt au milieu d'une phrase sans que personne ne comprenne pourquoi ;
     • un arrêt volontaire, lui, est respecté (aucune relance).
   Aucun vrai micro : on injecte un faux constructeur Web Speech. */

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

describe('DictationButton (EZ15)', () => {
  it('SANS l’API du navigateur, aucun bouton n’est rendu (champ inchangé)', () => {
    expect(isDictationSupported(window)).toBe(false)
    const { container } = render(<DictationButton onText={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('AVEC l’API, le bouton apparaît avec un nom accessible en français', () => {
    const off = installerApi()
    render(<DictationButton onText={() => {}} label="Dicter la note" />)
    expect(screen.getByRole('button', { name: 'Dicter la note' })).toBeInTheDocument()
    off()
  })

  it('démarre la reconnaissance en fr-FR, en continu et en streaming', () => {
    const off = installerApi()
    render(<DictationButton onText={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    expect(rec.lang).toBe('fr-FR')
    expect(rec.continuous).toBe(true)
    expect(rec.interimResults).toBe(true)   // le texte arrive AU FIL de la parole
    expect(rec.startCount).toBe(1)
    off()
  })

  it('remonte UNIQUEMENT les segments FINAUX, nettoyés', () => {
    const off = installerApi()
    const onText = vi.fn()
    render(<DictationButton onText={onText} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere

    // Un segment provisoire ne doit rien écrire dans le champ.
    rec.onresult({ resultIndex: 0, results: [{ isFinal: false, 0: { transcript: 'le clien' } }] })
    expect(onText).not.toHaveBeenCalled()

    // Deux phrases finales : le cas du « Done = dicter 2 phrases ».
    rec.onresult({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: '  Le client rappelle demain. ' } }] })
    expect(onText).toHaveBeenCalledWith('Le client rappelle demain.')
    rec.onresult({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: 'Il veut un devis batterie.' } }] })
    expect(onText).toHaveBeenLastCalledWith('Il veut un devis batterie.')
    expect(onText).toHaveBeenCalledTimes(2)
    off()
  })

  it('l’état d’écoute est annoncé (aria-pressed), pas seulement colorié', () => {
    const off = installerApi()
    render(<DictationButton onText={() => {}} />)
    const btn = screen.getByRole('button', { name: 'Dicter' })
    expect(btn).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(btn)
    expect(screen.getByRole('button', { name: /arrêter la dictée/i })).toHaveAttribute('aria-pressed', 'true')
    off()
  })

  it('la coupure auto après ~60 s de silence RELANCE la dictée', () => {
    const off = installerApi()
    render(<DictationButton onText={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    expect(rec.startCount).toBe(1)
    rec.onend()                       // le navigateur coupe tout seul
    expect(rec.startCount).toBe(2)    // ... on relance
    off()
  })

  it('un arrêt VOLONTAIRE est respecté (aucune relance)', () => {
    const off = installerApi()
    render(<DictationButton onText={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    fireEvent.click(screen.getByRole('button', { name: /arrêter la dictée/i }))
    expect(rec.stopCount).toBe(1)
    rec.onend()
    expect(rec.startCount).toBe(1)    // pas de redémarrage
    off()
  })

  it('un refus de permission micro arrête proprement, sans relance ni panique', () => {
    const off = installerApi()
    render(<DictationButton onText={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    rec.onerror({ error: 'not-allowed' })
    rec.onend()
    expect(rec.startCount).toBe(1)
    expect(screen.getByRole('button', { name: 'Dicter' })).toHaveAttribute('aria-pressed', 'false')
    off()
  })

  it('le démontage coupe le micro (pas de micro ouvert après fermeture du panneau)', () => {
    const off = installerApi()
    const { unmount } = render(<DictationButton onText={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Dicter' }))
    const rec = FakeRecognition.derniere
    unmount()
    expect(rec.stopCount).toBeGreaterThanOrEqual(1)
    off()
  })

  it('le texte de confidentialité dit la VÉRITÉ (audio envoyé au navigateur)', () => {
    // Ne jamais adoucir : ce n'est pas une transcription locale.
    expect(DICTATION_PRIVACY_FR).toMatch(/Google/)
    expect(DICTATION_PRIVACY_FR).toMatch(/pas une transcription locale/i)
    expect(DICTATION_PRIVACY_FR).toMatch(/HTTPS/)
  })
})
