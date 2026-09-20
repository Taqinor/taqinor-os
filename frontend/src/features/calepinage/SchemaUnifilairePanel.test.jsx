/* CAL195 — le panneau « schéma unifilaire » du module calepinage.

   Ce qui est prouvé ici : l'écran AFFICHE ce que le serveur compose et
   n'invente rien. Le SVG serveur est inséré tel quel ; `svg: null` n'est
   jamais un cadre vide — les motifs du serveur (`manquantes`, `bloquants`)
   sont rendus AU CARACTÈRE PRÈS, jamais reformulés côté écran. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { schemaUnifilaire: vi.fn() } },
}))

import calepinageApi from '../../api/calepinageApi'
import SchemaUnifilairePanel from './SchemaUnifilairePanel'

const servir = (data) => {
  calepinageApi.calepinages.schemaUnifilaire.mockResolvedValue({ data })
}

const rendre = () => render(
  <MemoryRouter><SchemaUnifilairePanel calepinageId={12} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SchemaUnifilairePanel (CAL195)', () => {
  it('insère le SVG composé par le SERVEUR, tel quel', async () => {
    servir({
      calepinage: 12, svg: '<svg data-testid="planche"><title>SLD</title></svg>',
      bloquants: [], manquantes: [],
    })

    rendre()

    const hote = await screen.findByTestId('cal195-svg')
    expect(hote.querySelector('svg')).not.toBeNull()
    expect(hote.textContent).toContain('SLD')
  })

  it('fiche incomplète : aucun schéma, et les motifs du SERVEUR mot pour mot', async () => {
    servir({
      calepinage: 12, svg: null, bloquants: [],
      manquantes: ['module : Isc (A)', 'onduleur : fenêtre MPPT'],
    })

    rendre()

    expect(await screen.findByTestId('cal195-manquantes')).toBeInTheDocument()
    expect(screen.getByText('module : Isc (A)')).toBeInTheDocument()
    expect(screen.getByText('onduleur : fenêtre MPPT')).toBeInTheDocument()
    expect(screen.queryByTestId('cal195-svg')).toBeNull()
  })

  it('conception non conforme : les bloquants du SERVEUR sont affichés', async () => {
    servir({
      calepinage: 12, svg: null, manquantes: [],
      bloquants: ['MPPT 1 : 3 chaînes pour une entrée admettant 17 A'],
    })

    rendre()

    expect(await screen.findByTestId('cal195-bloquants')).toBeInTheDocument()
    expect(screen.getByText(
      'MPPT 1 : 3 chaînes pour une entrée admettant 17 A')).toBeInTheDocument()
  })

  it('aucun schéma et aucun motif : on le dit, sans cadre vide', async () => {
    servir({ calepinage: 12, svg: null, bloquants: [], manquantes: [] })

    rendre()

    expect(await screen.findByTestId('cal195-sans-motif')).toBeInTheDocument()
    expect(screen.queryByTestId('cal195-svg')).toBeNull()
  })
})
