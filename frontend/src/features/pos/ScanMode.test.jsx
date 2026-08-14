import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ScanMode from './ScanMode'
import { traiterScan, attacherRaccourcisClavier, SCAN_DEBOUNCE_MS } from './scanApi'

/* NTRET22 — mode scan douchette en flux continu + raccourcis clavier.
   Couvre le débounce anti-double-scan (pur, sans I/O), les raccourcis
   clavier (F2/F4/Échap), et le rendu du champ (aucun Provider requis — pas
   de useSelector ici, contrairement à PinLock). */

describe('traiterScan (débounce anti-double-scan)', () => {
  it('accepte un premier scan', () => {
    const { accepte, dernier } = traiterScan('EAN123', null, 1000)
    expect(accepte).toBe(true)
    expect(dernier).toEqual({ code: 'EAN123', ts: 1000 })
  })

  it('rejette un doublon du même code sous le délai de rebond', () => {
    const premier = traiterScan('EAN123', null, 1000)
    const second = traiterScan('EAN123', premier.dernier, 1000 + SCAN_DEBOUNCE_MS - 1)
    expect(second.accepte).toBe(false)
    // Le « dernier » scan accepté est conservé tel quel — pas écrasé par le
    // doublon rejeté (sinon une rafale infinie de doublons rapides ne
    // laisserait plus jamais passer le même code).
    expect(second.dernier).toEqual(premier.dernier)
  })

  it('accepte un second scan du même code au-delà du délai', () => {
    const premier = traiterScan('EAN123', null, 1000)
    const second = traiterScan('EAN123', premier.dernier, 1000 + SCAN_DEBOUNCE_MS + 1)
    expect(second.accepte).toBe(true)
    expect(second.dernier).toEqual({ code: 'EAN123', ts: 1000 + SCAN_DEBOUNCE_MS + 1 })
  })

  it('un scan d’un AUTRE code sous le délai est accepté normalement (pas un doublon)', () => {
    const premier = traiterScan('EAN123', null, 1000)
    const second = traiterScan('EAN999', premier.dernier, 1010)
    expect(second.accepte).toBe(true)
    expect(second.dernier).toEqual({ code: 'EAN999', ts: 1010 })
  })

  it('un code vide/blanc est toujours rejeté', () => {
    expect(traiterScan('', null, 1000).accepte).toBe(false)
    expect(traiterScan('   ', null, 1000).accepte).toBe(false)
  })

  it('une rafale de 10 scans distincts sans perte ni doublon', () => {
    let dernier = null
    const acceptes = []
    for (let i = 0; i < 10; i += 1) {
      const ts = 1000 + i * (SCAN_DEBOUNCE_MS + 10) // au-delà du débounce à chaque fois
      const res = traiterScan(`ART-${i}`, dernier, ts)
      dernier = res.dernier
      if (res.accepte) acceptes.push(res.dernier.code)
    }
    expect(acceptes).toHaveLength(10)
    expect(new Set(acceptes).size).toBe(10) // aucun doublon
  })
})

describe('attacherRaccourcisClavier', () => {
  function fakeTarget() {
    const listeners = {}
    return {
      addEventListener: (type, fn) => { listeners[type] = fn },
      removeEventListener: (type, fn) => { if (listeners[type] === fn) delete listeners[type] },
      trigger: (key) => listeners.keydown?.({ key, preventDefault: () => {} }),
    }
  }

  it('F2 appelle onNouveauTicket, F4 appelle onEncaisser, Échap appelle onAnnulerLigne', () => {
    const target = fakeTarget()
    const handlers = {
      onNouveauTicket: vi.fn(),
      onEncaisser: vi.fn(),
      onAnnulerLigne: vi.fn(),
    }
    attacherRaccourcisClavier(handlers, target)
    target.trigger('F2')
    target.trigger('F4')
    target.trigger('Escape')
    expect(handlers.onNouveauTicket).toHaveBeenCalledTimes(1)
    expect(handlers.onEncaisser).toHaveBeenCalledTimes(1)
    expect(handlers.onAnnulerLigne).toHaveBeenCalledTimes(1)
  })

  it('une touche sans handler fourni ne lève jamais', () => {
    const target = fakeTarget()
    attacherRaccourcisClavier({}, target)
    expect(() => target.trigger('F2')).not.toThrow()
  })

  it('la fonction de nettoyage retire l’écouteur', () => {
    const target = fakeTarget()
    const handlers = { onNouveauTicket: vi.fn() }
    const cleanup = attacherRaccourcisClavier(handlers, target)
    cleanup()
    target.trigger('F2')
    expect(handlers.onNouveauTicket).not.toHaveBeenCalled()
  })
})

describe('<ScanMode /> — composant', () => {
  it('actif=false ne rend rien', () => {
    const { container } = render(<ScanMode actif={false} onScan={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('Entrée sur un code valide appelle onScan puis vide le champ', async () => {
    const user = userEvent.setup()
    const onScan = vi.fn()
    render(<ScanMode actif onScan={onScan} />)
    const input = screen.getByLabelText('Scan douchette continu')
    await user.type(input, 'EAN123{Enter}')
    expect(onScan).toHaveBeenCalledWith('EAN123')
    expect(input).toHaveValue('')
  })

  it('le bouton « Raccourcis » affiche l’aide des raccourcis clavier', async () => {
    const user = userEvent.setup()
    render(<ScanMode actif onScan={vi.fn()} />)
    expect(screen.queryByTestId('scan-mode-aide')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Raccourcis' }))
    expect(screen.getByTestId('scan-mode-aide')).toBeInTheDocument()
  })
})
