import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import DecompositionWaterfall, { geometrie, marchesNonReproduites } from './DecompositionWaterfall'

/* ============================================================================
   AOF104 — Done = le cas réel 112 → 126 se rend avec ses 8 marches, le bandeau
   d'échec est testé, le composant est exportable en image pour la planche.
   ========================================================================== */

// Cas RÉEL de la session AO : 112 (calcul historique) → 126 (calcul courant),
// 8 marches A→H. Toutes les valeurs viennent du serveur.
const MARCHES_112_126 = [
  { lettre: 'A', libelle: 'Faîtage relevé', delta: 6, valeur_apres: 118, reproduit: true },
  { lettre: 'B', libelle: 'Muret est écarté', delta: 4, valeur_apres: 122, reproduit: true },
  { lettre: 'C', libelle: 'Allée ramenée à 1,20 m', delta: 5, valeur_apres: 127, reproduit: true },
  { lettre: 'D', libelle: 'Rive nord recotée', delta: -3, valeur_apres: 124, reproduit: true },
  { lettre: 'E', libelle: 'Segment court fusionné', delta: 3, valeur_apres: 127, reproduit: true },
  { lettre: 'F', libelle: 'Dégagement cheminée', delta: -2, valeur_apres: 125, reproduit: true },
  { lettre: 'G', libelle: 'Kit paysage en rive', delta: 4, valeur_apres: 129, reproduit: true },
  { lettre: 'H', libelle: 'Contrainte onduleur', delta: -3, valeur_apres: 126, reproduit: true },
]

const DECOMPOSITION = {
  depart: { libelle: 'Calcul historique', valeur: 112 },
  arrivee: { libelle: 'Calcul courant', valeur: 126 },
  verifie: true,
  marches: MARCHES_112_126,
}

const AVEC_MARCHE_FAUTIVE = {
  ...DECOMPOSITION,
  verifie: false,
  marches: MARCHES_112_126.map((m) => (m.lettre === 'C' ? { ...m, reproduit: false } : m)),
}

describe('geometrie — dessin pur, aucune valeur métier inventée', () => {
  it('chaîne les marches depuis le départ et retombe sur la valeur d’arrivée', () => {
    const geo = geometrie({ depart: DECOMPOSITION.depart, marches: MARCHES_112_126 })
    expect(geo.barres).toHaveLength(8)
    expect(geo.barres[0].avant).toBe(112)
    expect(geo.barres[0].apres).toBe(118)
    expect(geo.total).toBe(126)
  })

  it('déduit `valeur_apres` du delta quand le serveur ne l’envoie pas', () => {
    const geo = geometrie({ depart: { valeur: 100 }, marches: [{ lettre: 'A', delta: 12 }] })
    expect(geo.barres[0].apres).toBe(112)
  })

  it('une marche descendante est marquée comme telle (couleur distincte)', () => {
    const geo = geometrie({ depart: DECOMPOSITION.depart, marches: MARCHES_112_126 })
    expect(geo.barres.find((b) => b.lettre === 'D').monte).toBe(false)
    expect(geo.barres.find((b) => b.lettre === 'A').monte).toBe(true)
  })
})

describe('marchesNonReproduites', () => {
  it('ne retient QUE les marches explicitement signalées `reproduit: false`', () => {
    expect(marchesNonReproduites(MARCHES_112_126)).toEqual([])
    expect(marchesNonReproduites(AVEC_MARCHE_FAUTIVE.marches).map((m) => m.lettre)).toEqual(['C'])
  })

  it('une marche sans champ `reproduit` n’est PAS traitée comme fautive', () => {
    expect(marchesNonReproduites([{ lettre: 'A' }])).toEqual([])
  })
})

describe('DecompositionWaterfall — le cas réel 112 → 126', () => {
  it('rend les 8 marches A→H avec leur lettre, leur libellé et leur delta SIGNÉ', () => {
    const { container } = render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(container.querySelectorAll('svg g[data-marche]')).toHaveLength(8)
    for (const lettre of ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']) {
      expect(container.querySelector(`g[data-marche="${lettre}"]`)).not.toBeNull()
    }
    // Delta SIGNÉ, lu dans la marche concernée (deux marches valent -3 : on
    // n'interroge jamais le document entier pour un chiffre non unique).
    expect(container.querySelector('g[data-marche="A"]').textContent).toContain('+6')
    const gD = container.querySelector('g[data-marche="D"]').textContent
    expect(gD).toMatch(/^[-−]3/)
    expect(gD).not.toContain('+3')
    expect(screen.getByText('Allée ramenée à 1,20 m')).toBeInTheDocument()
  })

  it('annonce le récit 112 → 126 en texte ET dans le nom accessible du dessin', () => {
    render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(screen.getByText(/Calcul historique 112/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /de 112 à 126/ })).toBeInTheDocument()
  })

  it('affiche le badge « reproduit l’ancien calcul ✓ » quand le serveur a vérifié', () => {
    render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(screen.getByText(/Reproduit l’ancien calcul/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('sans marche renvoyée : message explicite, jamais un dessin vide', () => {
    render(<DecompositionWaterfall decomposition={{ depart: { valeur: 1 }, marches: [] }} />)
    expect(screen.getByText(/Décomposition indisponible/)).toBeInTheDocument()
  })
})

describe('DecompositionWaterfall — GARDE D’HONNÊTETÉ', () => {
  it('marche non reproduite : bandeau rouge « récit non vérifié — ne pas publier », marche NOMMÉE', () => {
    render(<DecompositionWaterfall decomposition={AVEC_MARCHE_FAUTIVE} />)
    const alerte = screen.getByRole('alert')
    expect(alerte).toHaveTextContent('Récit non vérifié — ne pas publier')
    expect(alerte).toHaveTextContent('C — Allée ramenée à 1,20 m')
    expect(screen.queryByText(/Reproduit l’ancien calcul/)).not.toBeInTheDocument()
  })

  it('`verifie: false` seul (sans marche fautive nommée) suffit à lever le bandeau', () => {
    render(<DecompositionWaterfall decomposition={{ ...DECOMPOSITION, verifie: false }} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Récit non vérifié — ne pas publier')
  })

  it('BLOQUE l’export, et le bouton porte SON MOTIF (jamais un bouton grisé muet)', async () => {
    const exporterImage = vi.fn()
    render(<DecompositionWaterfall decomposition={AVEC_MARCHE_FAUTIVE} exporterImage={exporterImage} />)
    const bouton = screen.getByRole('button', { name: /Export bloqué/ })
    expect(bouton).toBeDisabled()
    expect(screen.getByText(/Récit non vérifié — 1 marche\(s\) ne reproduisent pas le chiffre attendu/))
      .toBeInTheDocument()
    await userEvent.click(bouton)
    expect(exporterImage).not.toHaveBeenCalled()
  })
})

describe('DecompositionWaterfall — export pour la planche (svgToPng/AOF75 injecté)', () => {
  it('exporte le SVG via l’exporteur injecté et rend l’image à l’appelant', async () => {
    const exporterImage = vi.fn().mockResolvedValue('data:image/png;base64,ZZZ')
    const onExporte = vi.fn()
    render(
      <DecompositionWaterfall decomposition={DECOMPOSITION} exporterImage={exporterImage} onExporte={onExporte} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /Exporter pour la planche/ }))
    await waitFor(() => expect(onExporte).toHaveBeenCalledWith('data:image/png;base64,ZZZ'))
    expect(exporterImage.mock.calls[0][0].tagName.toLowerCase()).toBe('svg')
    expect(exporterImage.mock.calls[0][1]).toEqual({ largeur: 1000 })
  })

  it('sans exporteur injecté : aucun bouton d’export (jamais un bouton mort)', () => {
    render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(screen.queryByRole('button', { name: /Export/ })).not.toBeInTheDocument()
  })
})
