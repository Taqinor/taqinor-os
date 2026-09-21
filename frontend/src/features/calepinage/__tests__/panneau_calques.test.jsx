import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

/* ============================================================================
   CAL103 / CALX54 — LE PANNEAU DE CALQUES.
   ----------------------------------------------------------------------------
   Ce que ce fichier prouve :
     * chaque calque s'allume/s'éteint INDÉPENDAMMENT, et l'hôte reçoit l'ordre ;
     * l'ORDRE DE SUPERPOSITION est déterminé (du fond vers le dessus), pas
       l'ordre d'ajout des couches ;
     * l'état est PERSISTÉ PAR UTILISATEUR (deux utilisateurs ne se marchent pas
       dessus) et restauré à l'ouverture — l'hôte en est informé ;
     * un stockage qui refuse (navigation privée) ne casse rien : état par défaut ;
     * CALX54 — la SEULE source des calques proposés est `builderApi.calquesDisponibles()`
       (CALX3) : sans `builderApi`, ou tant qu'il n'est pas prêt, ou si la scène ne
       porte encore aucun calque, le panneau affiche un état vide explicite plutôt
       que la liste statique des dix calques ; un identifiant que `calques.js` ne
       connaît pas n'est jamais inventé ; la liste est relue quand `builderApi`
       change d'identité (le builder devient prêt).
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

/** Double de `builderApi` (CALX3/CALX8) : `calquesDisponibles()` rend `ids`. */
function builderApiAvec(ids) {
  return { calquesDisponibles: () => ids }
}

const TOUS = builderApiAvec([...CALQUE_IDS])

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
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} builderApi={TOUS} onChange={vi.fn()} />)
    const rangs = CALQUE_IDS.map((id) => Number(screen.getByTestId(`pc-calque-${id}`).dataset.rang))
    expect(rangs).toEqual([...rangs].sort((a, b) => a - b))
  })
})

describe('CAL103 — chaque calque s’allume et s’éteint indépendamment', () => {
  it('éteindre un calque prévient l’hôte, et LUI SEUL change', () => {
    const onChange = vi.fn()
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} builderApi={TOUS} onChange={onChange} />)
    onChange.mockClear()
    fireEvent.click(screen.getByTestId('pc-visible-zones'))
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('zones', { visible: false, opacite: 1 })
    expect(screen.getByTestId('pc-visible-obstacles').checked).toBe(true)
  })

  it('l’opacité est pilotable et transmise telle quelle', () => {
    const onChange = vi.fn()
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} builderApi={TOUS} onChange={onChange} />)
    onChange.mockClear()
    fireEvent.change(screen.getByTestId('pc-opacite-imagerie'), { target: { value: '0.5' } })
    expect(onChange).toHaveBeenCalledWith('imagerie', { visible: true, opacite: 0.5 })
  })
})

describe('CAL103 — persistance PAR UTILISATEUR', () => {
  it('l’état est rangé sous une clé qui porte l’utilisateur', () => {
    const store = memStore()
    render(<PanneauCalques utilisateurId={42} stockage={store} builderApi={TOUS} onChange={vi.fn()} />)
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
    render(<PanneauCalques utilisateurId="u1" stockage={store} builderApi={TOUS} onChange={onChange} />)
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

describe('CALX54 — n’offrir que les calques réellement présents dans la scène', () => {
  it('sans `builderApi` (constructeur pas encore prêt) ⇒ état vide, en français, rien d’inventé', () => {
    render(<PanneauCalques utilisateurId="u1" stockage={memStore()} onChange={vi.fn()} />)
    expect(screen.getByTestId('pc-panneau')).toBeTruthy()
    expect(screen.getByTestId('pc-vide').textContent).toMatch(/aucun calque disponible/i)
    for (const id of CALQUE_IDS) expect(screen.queryByTestId(`pc-calque-${id}`)).toBeNull()
  })

  it('`calquesDisponibles()` rendant deux identifiants ⇒ exactement ces deux, avec les libellés de calques.js', () => {
    const onChange = vi.fn()
    render(
      <PanneauCalques
        utilisateurId="u1"
        stockage={memStore()}
        builderApi={builderApiAvec(['zones', 'imagerie'])}
        onChange={onChange}
      />,
    )
    expect(screen.queryByTestId('pc-vide')).toBeNull()
    // Rendus dans l'ORDRE de calques.js (imagerie au fond, zones au-dessus),
    // pas dans l'ordre renvoyé par `calquesDisponibles()`.
    const rendus = screen.getAllByRole('listitem').map((li) => li.dataset.testid)
    expect(rendus).toEqual(['pc-calque-imagerie', 'pc-calque-zones'])
    expect(screen.getByTestId('pc-calque-imagerie').textContent).toContain(
      ORDRE_CALQUES.find((c) => c.id === 'imagerie').label,
    )
    expect(screen.getByTestId('pc-calque-zones').textContent).toContain(
      ORDRE_CALQUES.find((c) => c.id === 'zones').label,
    )
    // Aucun des huit autres calques statiques n'est proposé.
    for (const id of CALQUE_IDS) {
      if (id === 'zones' || id === 'imagerie') continue
      expect(screen.queryByTestId(`pc-calque-${id}`)).toBeNull()
    }
  })

  it('un identifiant inconnu de calques.js est ignoré, jamais inventé', () => {
    render(
      <PanneauCalques
        utilisateurId="u1"
        stockage={memStore()}
        builderApi={builderApiAvec(['zones', 'un-calque-qui-nexiste-pas'])}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getByTestId('pc-calque-zones')).toBeTruthy()
    expect(screen.queryByTestId('pc-calque-un-calque-qui-nexiste-pas')).toBeNull()
  })

  it('`calquesDisponibles()` absente ou qui lève ⇒ état vide, jamais une exception', () => {
    expect(() =>
      render(<PanneauCalques utilisateurId="u1" stockage={memStore()} builderApi={{}} onChange={vi.fn()} />),
    ).not.toThrow()
    expect(screen.getByTestId('pc-vide')).toBeTruthy()

    const quiLeve = {
      calquesDisponibles: () => {
        throw new Error('style pas encore chargé')
      },
    }
    expect(() =>
      render(<PanneauCalques utilisateurId="u2" stockage={memStore()} builderApi={quiLeve} onChange={vi.fn()} />),
    ).not.toThrow()
  })

  it('la scène sans photo ni plan propose 8 bascules, pas 10 ; le dépôt d’un plan fait apparaître « Plan importé »', () => {
    const HUIT = CALQUE_IDS.filter((id) => id !== 'photo' && id !== 'plan')
    const { rerender } = render(
      <PanneauCalques utilisateurId="u1" stockage={memStore()} builderApi={builderApiAvec(HUIT)} onChange={vi.fn()} />,
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(8)
    expect(screen.queryByTestId('pc-calque-plan')).toBeNull()

    // Le builder redevient une NOUVELLE référence (il vient d'installer le
    // calque « Plan importé » sur la scène après le dépôt du plan) : la liste
    // est relue, sans sondage.
    rerender(
      <PanneauCalques
        utilisateurId="u1"
        stockage={memStore()}
        builderApi={builderApiAvec([...HUIT, 'plan'])}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByTestId('pc-calque-plan')).toBeTruthy()
    expect(screen.getByTestId('pc-calque-plan').textContent).toContain(
      ORDRE_CALQUES.find((c) => c.id === 'plan').label,
    )
  })
})
