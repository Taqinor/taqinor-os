import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

/* ============================================================================
   CAL103 — LE PANNEAU DE CALQUES.
   ----------------------------------------------------------------------------
   Ce que ce fichier prouve :
     * chaque calque s'allume/s'éteint INDÉPENDAMMENT, et l'hôte reçoit l'ordre ;
     * l'ORDRE DE SUPERPOSITION est déterminé (du fond vers le dessus), pas
       l'ordre d'ajout des couches ;
     * l'état est PERSISTÉ PAR UTILISATEUR (deux utilisateurs ne se marchent pas
       dessus) et restauré à l'ouverture — l'hôte en est informé ;
     * un stockage qui refuse (navigation privée) ne casse rien : état par défaut ;
     * un calque que l'hôte ne sait pas piloter n'est PAS listé (rien d'inventé).
   ========================================================================== */

import PanneauCalques from '../PanneauCalques'
import {
  ORDRE_CALQUES,
  CALQUE_IDS,
  rangCalque,
  etatCalquesParDefaut,
  lireEtatCalques,
  ecrireEtatCalques,
  cleStockage,
} from '../calques'

/** Stockage de test, isolé du navigateur. */
function memStore() {
  const m = new Map()
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, v),
    _dump: () => Object.fromEntries(m),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CAL103 — ordre de superposition déterminé', () => {
  it('les dix calques de la tâche sont déclarés, du fond vers le dessus', () => {
    expect(CALQUE_IDS).toEqual([
      'imagerie',
      'cadastre',
      'photo',
      'plan',
      'trace_client',
      'obstacles',
      'zones',
      'panneaux',
      'ombres',
      'mesures',
    ])
    // L'imagerie est TOUT AU FOND, les mesures TOUT AU-DESSUS.
    expect(rangCalque('imagerie')).toBe(0)
    expect(rangCalque('mesures')).toBe(ORDRE_CALQUES.length - 1)
    // Les panneaux passent au-dessus des zones, qui passent au-dessus des obstacles.
    expect(rangCalque('panneaux')).toBeGreaterThan(rangCalque('zones'))
    expect(rangCalque('zones')).toBeGreaterThan(rangCalque('obstacles'))
    expect(rangCalque('inconnu')).toBe(-1)
  })

  it('le panneau rend les calques DANS cet ordre', () => {
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} onChange={vi.fn()} />)
    const rangs = CALQUE_IDS.map((id) => Number(screen.getByTestId(`pc-calque-${id}`).dataset.rang))
    expect(rangs).toEqual([...rangs].sort((a, b) => a - b))
  })
})

describe('CAL103 — chaque calque s’allume et s’éteint indépendamment', () => {
  it('éteindre un calque prévient l’hôte, et LUI SEUL change', () => {
    const onChange = vi.fn()
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} onChange={onChange} />)
    onChange.mockClear()
    fireEvent.click(screen.getByTestId('pc-visible-zones'))
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('zones', { visible: false, opacite: 1 })
    expect(screen.getByTestId('pc-visible-obstacles').checked).toBe(true)
  })

  it('l’opacité est pilotable et transmise telle quelle', () => {
    const onChange = vi.fn()
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} onChange={onChange} />)
    onChange.mockClear()
    fireEvent.change(screen.getByTestId('pc-opacite-imagerie'), { target: { value: '0.5' } })
    expect(onChange).toHaveBeenCalledWith('imagerie', { visible: true, opacite: 0.5 })
  })

  it('un calque que l’hôte ne sait pas piloter n’est pas listé', () => {
    render(
      <PanneauCalques utilisateurId="u1" stockage={memStore()} disponibles={['imagerie', 'zones']} onChange={vi.fn()} />,
    )
    expect(screen.getByTestId('pc-calque-imagerie')).toBeTruthy()
    expect(screen.getByTestId('pc-calque-zones')).toBeTruthy()
    expect(screen.queryByTestId('pc-calque-cadastre')).toBeNull()
  })
})

describe('CAL103 — persistance PAR UTILISATEUR', () => {
  it('l’état est rangé sous une clé qui porte l’utilisateur', () => {
    const store = memStore()
    render(<PanneauCalques utilisateurId={42} stockage={store} onChange={vi.fn()} />)
    fireEvent.click(screen.getByTestId('pc-visible-ombres'))
    expect(Object.keys(store._dump())).toEqual([cleStockage(42)])
    expect(lireEtatCalques(42, store).ombres.visible).toBe(false)
    // Un AUTRE utilisateur n'est pas affecté : il repart de l'état par défaut.
    expect(lireEtatCalques(7, store)).toEqual(etatCalquesParDefaut())
  })

  it('à l’ouverture, l’état mémorisé est RESTAURÉ et l’hôte en est informé', () => {
    const store = memStore()
    ecrireEtatCalques('u1', { ...etatCalquesParDefaut(), mesures: { visible: false, opacite: 0.4 } }, store)
    const onChange = vi.fn()
    render(<PanneauCalques utilisateurId="u1" stockage={store} onChange={onChange} />)
    expect(screen.getByTestId('pc-visible-mesures').checked).toBe(false)
    expect(onChange).toHaveBeenCalledWith('mesures', { visible: false, opacite: 0.4 })
    // Les autres calques sont annoncés aussi : la carte part de l'état affiché.
    expect(onChange).toHaveBeenCalledTimes(CALQUE_IDS.length)
  })

  it('stockage illisible ou corrompu ⇒ état par défaut, jamais une exception', () => {
    const qui_jette = {
      getItem: () => {
        throw new Error('stockage bloqué')
      },
      setItem: () => {
        throw new Error('stockage bloqué')
      },
    }
    expect(lireEtatCalques('u1', qui_jette)).toEqual(etatCalquesParDefaut())
    expect(() => ecrireEtatCalques('u1', etatCalquesParDefaut(), qui_jette)).not.toThrow()
    const corrompu = memStore()
    corrompu.setItem(cleStockage('u1'), '{pas du json')
    expect(lireEtatCalques('u1', corrompu)).toEqual(etatCalquesParDefaut())
    corrompu.setItem(cleStockage('u1'), JSON.stringify({ zones: { visible: 'oui', opacite: 42 } }))
    expect(lireEtatCalques('u1', corrompu)).toEqual(etatCalquesParDefaut())
  })
})
