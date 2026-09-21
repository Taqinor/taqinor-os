/* CAL195 — le panneau « schéma unifilaire » du module calepinage.

   Ce qui est prouvé ici : l'écran AFFICHE ce que le serveur compose et
   n'invente rien. Le SVG serveur est inséré tel quel ; `svg: null` n'est
   jamais un cadre vide — les motifs du serveur (`manquantes`, `bloquants`)
   sont rendus AU CARACTÈRE PRÈS, jamais reformulés côté écran. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { schemaUnifilaire: vi.fn() } },
}))

// CALX236 — `telechargerBlob` est le SEUL point de sortie du navigateur
// (création de l'élément `<a>` + clic) : le mocker prouve QUOI est
// téléchargé (blob + nom), sans dépendre du DOM réel du téléchargement.
const telechargerBlob = vi.fn()
vi.mock('./exportImage', () => ({
  telechargerBlob: (...args) => telechargerBlob(...args),
}))

import calepinageApi from '../../api/calepinageApi'
import SchemaUnifilairePanel from './SchemaUnifilairePanel'

const servir = (data) => {
  calepinageApi.calepinages.schemaUnifilaire.mockResolvedValue({ data })
}

const rendre = () => render(
  <MemoryRouter><SchemaUnifilairePanel calepinageId={12} /></MemoryRouter>,
)

/* CALX236 — jsdom n'implémente ni `getContext('2d')` ni `URL.createObjectURL`
   nativement (même constat que `features/ged/capture.js`) : on les stub
   globalement, comme `CameraCapture.test.jsx`/`DocumentScanCapture.test.jsx`
   du même dépôt. `FakeImage` déclenche `onload` en microtâche — aucun
   décodage d'image réel n'est nécessaire pour prouver le CÂBLAGE de l'export. */
class FakeImage {
  set src(_v) {
    this.width = 300
    this.height = 150
    queueMicrotask(() => this.onload?.())
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.Image = FakeImage
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake-url')
  globalThis.URL.revokeObjectURL = vi.fn()
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() }))
  HTMLCanvasElement.prototype.toBlob = vi.fn((cb) => cb({ type: 'image/png', size: 42 }))
})
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

describe('SchemaUnifilairePanel — export PNG/SVG depuis le navigateur (CALX236)', () => {
  it('le bouton d’export est ABSENT tant que `svg` vaut `null`', async () => {
    servir({ calepinage: 12, svg: null, bloquants: [], manquantes: [] })

    rendre()

    await screen.findByTestId('cal195-sans-motif')
    expect(screen.queryByTestId('calx236-export')).toBeNull()
    expect(screen.queryByTestId('calx236-exporter-png')).toBeNull()
  })

  it('le clic appelle UNE FOIS l’export, et le nom de fichier porte la référence du calepinage', async () => {
    servir({
      calepinage: 12, svg: '<svg data-testid="planche"><title>SLD</title></svg>',
      bloquants: [], manquantes: [],
    })
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx236-exporter-png'))

    await vi.waitFor(() => expect(telechargerBlob).toHaveBeenCalledTimes(1))
    const [blob, nom] = telechargerBlob.mock.calls[0]
    expect(blob.type).toBe('image/png')
    expect(nom).toBe('calepinage-12-schema-unifilaire.png')
    expect(screen.queryByTestId('calx236-erreur-export')).toBeNull()
  })

  it('aucun appel réseau supplémentaire pour le PNG : `schemaUnifilaire` n’est appelée qu’UNE fois', async () => {
    servir({
      calepinage: 12, svg: '<svg data-testid="planche"><title>SLD</title></svg>',
      bloquants: [], manquantes: [],
    })
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx236-exporter-png'))
    await vi.waitFor(() => expect(telechargerBlob).toHaveBeenCalledTimes(1))

    expect(calepinageApi.calepinages.schemaUnifilaire).toHaveBeenCalledTimes(1)
  })

  it('le lien SVG télécharge le TEXTE déjà reçu, tel quel', async () => {
    const svg = '<svg data-testid="planche"><title>SLD</title></svg>'
    servir({ calepinage: 7, svg, bloquants: [], manquantes: [] })
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx236-telecharger-svg'))

    expect(telechargerBlob).toHaveBeenCalledTimes(1)
    const [blob, nom] = telechargerBlob.mock.calls[0]
    expect(blob.type).toBe('image/svg+xml;charset=utf-8')
    expect(nom).toBe('calepinage-7-schema-unifilaire.svg')
  })

  it('un échec de rastérisation revient en MOTIF affichable, jamais un écran cassé', async () => {
    servir({
      calepinage: 12, svg: '<svg data-testid="planche"><title>SLD</title></svg>',
      bloquants: [], manquantes: [],
    })
    HTMLCanvasElement.prototype.toBlob = vi.fn((cb) => cb(null))
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx236-exporter-png'))

    expect(await screen.findByTestId('calx236-erreur-export')).toHaveTextContent(
      'Rendu PNG indisponible',
    )
    expect(telechargerBlob).not.toHaveBeenCalled()
  })
})
