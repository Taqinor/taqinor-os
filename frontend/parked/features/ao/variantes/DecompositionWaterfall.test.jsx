import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import DecompositionWaterfall, { geometrie, marchesFautives } from './DecompositionWaterfall'

/* ============================================================================
   AOF104 + PACT172 — Done = le cas réel 112 → 126 se rend avec ses 8 marches,
   le bandeau d'échec est testé, le composant est exportable en image pour la
   planche. RÉPARATION 07/08/2026 : la forme des fixtures est désormais celle
   RÉELLEMENT rendue par `GET /ao/calepinage/variantes/:id/marches/`
   (`calepinage_service.calculer_marches` / `core/calepinage/echelle.py`) —
   `depart`/`arrivee` sont des ENTIERS, chaque marche porte `code`/`modules`/
   `attendu` (jamais `lettre`/`valeur_apres`/`reproduit`), et le récit + les
   motifs d'honnêteté sont des phrases SERVEUR (`recit`, `motifs`).
   ========================================================================== */

// Cas RÉEL de la session AO : 112 (calcul historique) → 126 (calcul courant),
// 8 marches A→H. Toutes les valeurs viennent du serveur. `attendu` n'est posé
// que sur les marches dont un ancien calcul avait figé un chiffre (ici :
// toutes, pour rejouer le contrôle d'honnêteté).
const MARCHES_112_126 = [
  { code: 'A', libelle: 'Faîtage relevé', modules: 118, delta: 6, attendu: 118 },
  { code: 'B', libelle: 'Muret est écarté', modules: 122, delta: 4, attendu: 122 },
  { code: 'C', libelle: 'Allée ramenée à 1,20 m', modules: 127, delta: 5, attendu: 127 },
  { code: 'D', libelle: 'Rive nord recotée', modules: 124, delta: -3, attendu: 124 },
  { code: 'E', libelle: 'Segment court fusionné', modules: 127, delta: 3, attendu: 127 },
  { code: 'F', libelle: 'Dégagement cheminée', modules: 125, delta: -2, attendu: 125 },
  { code: 'G', libelle: 'Kit paysage en rive', modules: 129, delta: 4, attendu: 129 },
  { code: 'H', libelle: 'Contrainte onduleur', modules: 126, delta: -3, attendu: 126 },
]

const DECOMPOSITION = {
  recit: 'A (112) → H (126) : +14 modules en 8 marches',
  depart: 112,
  arrivee: 126,
  gain_total: 14,
  honnete: true,
  motifs: [],
  marches: MARCHES_112_126,
}

const AVEC_MARCHE_FAUTIVE = {
  ...DECOMPOSITION,
  honnete: false,
  motifs: ["marche C (Allée ramenée à 1,20 m) : attendu 127 modules, le moteur courant en rend 130 — "
    + 'le récit « ancien → aujourd’hui » serait FAUX'],
  marches: MARCHES_112_126.map((m) => (m.code === 'C' ? { ...m, modules: 130 } : m)),
}

describe('geometrie — dessin pur, aucune valeur métier inventée', () => {
  it('chaîne les marches depuis le départ (nombre) et retombe sur la valeur d’arrivée', () => {
    const geo = geometrie({ depart: DECOMPOSITION.depart, marches: MARCHES_112_126 })
    expect(geo.barres).toHaveLength(8)
    expect(geo.barres[0].avant).toBe(112)
    expect(geo.barres[0].apres).toBe(118)
    expect(geo.total).toBe(126)
  })

  it('déduit `modules` du delta quand le serveur ne l’envoie pas', () => {
    const geo = geometrie({ depart: 100, marches: [{ code: 'A', delta: 12 }] })
    expect(geo.barres[0].apres).toBe(112)
  })

  it('une marche descendante est marquée comme telle (couleur distincte)', () => {
    const geo = geometrie({ depart: DECOMPOSITION.depart, marches: MARCHES_112_126 })
    expect(geo.barres.find((b) => b.code === 'D').monte).toBe(false)
    expect(geo.barres.find((b) => b.code === 'A').monte).toBe(true)
  })
})

describe('marchesFautives', () => {
  it('ne retient QUE les marches dont `modules` diverge de leur `attendu` déclaré', () => {
    expect(marchesFautives(MARCHES_112_126)).toEqual([])
    expect(marchesFautives(AVEC_MARCHE_FAUTIVE.marches).map((m) => m.code)).toEqual(['C'])
  })

  it('une marche sans `attendu` n’est JAMAIS traitée comme fautive', () => {
    expect(marchesFautives([{ code: 'A', modules: 5 }])).toEqual([])
  })
})

describe('DecompositionWaterfall — le cas réel 112 → 126', () => {
  it('rend les 8 marches A→H avec leur code, leur libellé et leur delta SIGNÉ', () => {
    const { container } = render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(container.querySelectorAll('svg g[data-marche]')).toHaveLength(8)
    for (const code of ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']) {
      expect(container.querySelector(`g[data-marche="${code}"]`)).not.toBeNull()
    }
    // Delta SIGNÉ, lu dans la marche concernée (deux marches valent -3 : on
    // n'interroge jamais le document entier pour un chiffre non unique).
    expect(container.querySelector('g[data-marche="A"]').textContent).toContain('+6')
    const gD = container.querySelector('g[data-marche="D"]').textContent
    expect(gD).toMatch(/^[-−]3/)
    expect(gD).not.toContain('+3')
    expect(screen.getByText('Allée ramenée à 1,20 m')).toBeInTheDocument()
  })

  it('annonce le récit SERVEUR en texte ET dans le nom accessible du dessin', () => {
    render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(screen.getByText(DECOMPOSITION.recit)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /de 112 à 126/ })).toBeInTheDocument()
  })

  it('affiche le badge « reproduit l’ancien calcul ✓ » quand le serveur a vérifié (`honnete`)', () => {
    render(<DecompositionWaterfall decomposition={DECOMPOSITION} />)
    expect(screen.getByText(/Reproduit l’ancien calcul/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('sans marche renvoyée : message explicite, jamais un dessin vide', () => {
    render(<DecompositionWaterfall decomposition={{ depart: 1, marches: [] }} />)
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

  it('`honnete: false` seul (sans marche fautive nommable) suffit à lever le bandeau', () => {
    render(<DecompositionWaterfall decomposition={{ ...DECOMPOSITION, honnete: false, motifs: ['le serveur signale une incohérence'] }} />)
    const alerte = screen.getByRole('alert')
    expect(alerte).toHaveTextContent('Récit non vérifié — ne pas publier')
    expect(alerte).toHaveTextContent('le serveur signale une incohérence')
  })

  it('BLOQUE l’export, et le bouton porte le MOTIF SERVEUR (jamais un bouton grisé muet)', async () => {
    const exporterImage = vi.fn()
    render(<DecompositionWaterfall decomposition={AVEC_MARCHE_FAUTIVE} exporterImage={exporterImage} />)
    const bouton = screen.getByRole('button', { name: /Export bloqué/ })
    expect(bouton).toBeDisabled()
    expect(screen.getByText(AVEC_MARCHE_FAUTIVE.motifs[0])).toBeInTheDocument()
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
