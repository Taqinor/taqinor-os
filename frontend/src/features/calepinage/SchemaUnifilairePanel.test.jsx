/* CAL195 — le panneau « schéma unifilaire » du module calepinage.

   Ce qui est prouvé ici : l'écran AFFICHE ce que le serveur compose et
   n'invente rien. Le SVG serveur est inséré tel quel ; `svg: null` n'est
   jamais un cadre vide — les motifs du serveur (`manquantes`, `bloquants`)
   sont rendus AU CARACTÈRE PRÈS, jamais reformulés côté écran. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/calepinageApi', () => ({
  default: { calepinages: { schemaUnifilaire: vi.fn(), sldDxf: vi.fn(), enregistrerEditionSld: vi.fn() } },
}))

// CALX236 — `telechargerBlob` est le SEUL point de sortie du navigateur
// (création de l'élément `<a>` + clic) : le mocker prouve QUOI est
// téléchargé (blob + nom), sans dépendre du DOM réel du téléchargement.
const telechargerBlob = vi.fn()
vi.mock('./exportImage', () => ({
  telechargerBlob: (...args) => telechargerBlob(...args),
}))

import calepinageApi from '../../api/calepinageApi'
import SchemaUnifilairePanel, { PlancheSchema, SchemaEnBlocs } from './SchemaUnifilairePanel'
import {
  motifDuRefusDxf, corpsEdition, couperTexte, echelleAjustee, estHorsReseau, lignesCartouche, lignesLegende, phraseCoteReseau, planDepuisDocument, planSchemaEnBlocs,
} from './SchemaUnifilairePanel.helpers'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'
import { OPTIONS_TELECHARGEMENT } from './documents/telechargement'

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

describe('SchemaUnifilairePanel — croquis de principe grisé (ACAL1028)', () => {
  it('fiche incomplète : croquis et légende AU-DESSUS de la liste, sans aucune valeur ni nombre', async () => {
    servir({ calepinage: 12, svg: null, bloquants: [], manquantes: ['module : Isc (A)'] })

    rendre()

    const croquis = await screen.findByTestId('acal1028-croquis')
    expect(screen.getByTestId('acal1028-legende')).toHaveTextContent(
      'Croquis de principe, sans valeur : votre schéma s’affichera quand les champs ci-dessous seront remplis.')
    expect(croquis.textContent).not.toMatch(/\d/)
    const liste = screen.getByTestId('cal195-manquantes')
    expect(croquis.compareDocumentPosition(liste) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // La liste du serveur reste mot pour mot.
    expect(screen.getByText('module : Isc (A)')).toBeInTheDocument()
  })

  it('ACAL1427 — croquis : cinq libellés en texte réel (14 px) dans une colonne, jamais un SVG mis à l’échelle', async () => {
    servir({ calepinage: 12, svg: null, bloquants: [], manquantes: ['module : Isc (A)'] })
    rendre()
    const croquis = await screen.findByTestId('acal1028-croquis')
    expect(croquis.querySelector('svg')).toBeNull()
    for (const nom of ['Modules', 'Coffret DC', 'Onduleur', 'Protections AC', 'Réseau']) {
      expect(within(croquis).getByText(nom)).toHaveClass('text-sm')
    }
    expect(within(croquis).getByRole('list')).toHaveClass('flex-col')
  })

  it('bloquants seuls, schéma réel ou rien à dire : aucun croquis', async () => {
    servir({ calepinage: 12, svg: null, manquantes: [], bloquants: ['MPPT 1 : 3 chaînes'] })
    rendre()
    await screen.findByTestId('cal195-bloquants')
    expect(screen.queryByTestId('acal1028-croquis')).toBeNull()
    cleanup()

    servir({ calepinage: 12, svg: '<svg><title>SLD</title></svg>', bloquants: [], manquantes: ['reste un manque'] })
    rendre()
    await screen.findByTestId('cal195-svg')
    expect(screen.queryByTestId('acal1028-croquis')).toBeNull()
    cleanup()

    servir({ calepinage: 12, svg: null, bloquants: [], manquantes: [] })
    rendre()
    await screen.findByTestId('cal195-sans-motif')
    expect(screen.queryByTestId('acal1028-croquis')).toBeNull()
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

/* CALX235 — le troisième bouton : le DXF, produit par le SERVEUR depuis le
   même dessin (le SVG et le DXF ne peuvent donc pas diverger). C'est le SEUL
   appel réseau de ce panneau, et le seul export que le navigateur ne sait pas
   fabriquer seul. */
describe('SchemaUnifilairePanel — export DXF (CALX235/236)', () => {
  const AVEC_SCHEMA = {
    calepinage: 7, svg: '<svg data-testid="planche"><title>SLD</title></svg>',
    bloquants: [], manquantes: [],
  }

  it('le bouton DXF est ABSENT tant que `svg` vaut `null`', async () => {
    servir({ calepinage: 12, svg: null, bloquants: [], manquantes: [] })

    rendre()

    await screen.findByTestId('cal195-sans-motif')
    expect(screen.queryByTestId('calx235-telecharger-dxf')).toBeNull()
  })

  it('le clic télécharge le fichier du SERVEUR, nommé d’après le calepinage', async () => {
    servir(AVEC_SCHEMA)
    const fichier = { type: 'image/vnd.dxf', size: 128 }
    calepinageApi.calepinages.sldDxf.mockResolvedValue({ data: fichier })
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx235-telecharger-dxf'))

    await vi.waitFor(() => expect(telechargerBlob).toHaveBeenCalledTimes(1))
    // L'appel porte l'identifiant de l'ÉCRAN (la route), le nom de fichier la
    // référence que CETTE réponse publie : les deux ne se confondent pas.
    expect(calepinageApi.calepinages.sldDxf).toHaveBeenCalledWith(12, OPTIONS_TELECHARGEMENT)
    const [blob, nom] = telechargerBlob.mock.calls[0]
    expect(blob).toBe(fichier)
    expect(nom).toBe('calepinage-7-schema-unifilaire.dxf')
  })

  it('un DXF trop long dit le délai en français (R3)', async () => {
    servir(AVEC_SCHEMA)
    calepinageApi.calepinages.sldDxf.mockRejectedValue({ code: 'ECONNABORTED' })
    const user = userEvent.setup()
    rendre()
    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx235-telecharger-dxf'))
    expect(await screen.findByTestId('calx236-erreur-export'))
      .toHaveTextContent("Le serveur n'a pas fini de préparer ce document en 2 minutes.")
  })

  it('un refus du serveur affiche SON motif, jamais un motif reformulé', async () => {
    servir(AVEC_SCHEMA)
    const motif = 'module : Isc (A) manque sur la fiche — aucun DXF produit.'
    calepinageApi.calepinages.sldDxf.mockRejectedValue({
      response: {
        status: 400,
        data: { text: async () => JSON.stringify({ schema: motif }) },
      },
    })
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('cal195-svg')
    await user.click(screen.getByTestId('calx235-telecharger-dxf'))

    expect(await screen.findByTestId('calx236-erreur-export'))
      .toHaveTextContent(motif)
    expect(telechargerBlob).not.toHaveBeenCalled()
  })

  it('motifDuRefusDxf ne devine rien quand le corps est illisible', async () => {
    await expect(motifDuRefusDxf(new Error('réseau')))
      .resolves.toContain('n’a pas pu être produit')
  })
})

/* ACAL161 — l'éditeur de libellés et de repères. Les réponses viennent de l'exemple COMMITTÉ
   `calepinage_sld.json` (avant et après édition), jamais d'un objet tapé à la main. */
describe('SchemaUnifilairePanel — édition des libellés et repères (ACAL161)', () => {
  const AVANT = exempleContrat('calepinage', 'calepinage_sld', 'exemple')
  const APRES = exempleContrat('calepinage', 'calepinage_sld', 'exemple_apres_edition')
  const REFUS = exempleContrat('calepinage', 'calepinage_sld', 'refus_clef_inconnue')
  const champ = (rubrique, clef) => document.getElementById(`acal161-${rubrique}-${clef}`)

  it('modifier un libellé poste {libelles:{clef:texte}} et le SVG relu porte le texte', async () => {
    servir({ ...AVANT, svg: '<svg><text>Avant</text></svg>' })
    calepinageApi.calepinages.enregistrerEditionSld.mockResolvedValue({
      data: { ...APRES, svg: '<svg><text>Comptage renommé</text></svg>' },
    })

    rendre()
    const champLibelle = await screen.findByLabelText(/Libellé — compteur_production/)
    await userEvent.clear(champLibelle)
    await userEvent.type(champLibelle, 'Comptage renommé')
    await userEvent.click(screen.getByTestId('acal161-enregistrer'))

    expect(calepinageApi.calepinages.enregistrerEditionSld)
      .toHaveBeenCalledWith(12, { libelles: { compteur_production: 'Comptage renommé' } })
    // Le SVG relu (réponse du POST, édition appliquée) porte le texte.
    expect(await screen.findByText('Comptage renommé', { selector: 'text' })).toBeInTheDocument()
    expect(calepinageApi.calepinages.schemaUnifilaire).toHaveBeenCalledTimes(1)
  })

  it('un repère modifié part, un champ vidé envoie null, sans toucher = aucun envoi', async () => {
    servir(AVANT)
    calepinageApi.calepinages.enregistrerEditionSld.mockResolvedValue({ data: APRES })

    rendre()
    await screen.findByTestId('acal161-edition')
    expect(screen.getByTestId('acal161-enregistrer')).toBeDisabled()

    await userEvent.clear(champ('reperes', 'ddr'))
    await userEvent.type(champ('reperes', 'disjoncteur_ac'), 'QAC2')
    await userEvent.click(screen.getByTestId('acal161-enregistrer'))

    const [, corps] = calepinageApi.calepinages.enregistrerEditionSld.mock.calls[0]
    expect(corps).toEqual({ reperes: { ddr: null, disjoncteur_ac: 'QAC1QAC2' } })
  })

  it('refus nommé sous le champ visé, mot pour mot', async () => {
    servir(AVANT)
    calepinageApi.calepinages.enregistrerEditionSld.mockRejectedValue({ response: { status: 400, data: REFUS } })

    rendre()
    await screen.findByTestId('acal161-edition')
    await userEvent.type(champ('libelles', 'ddr'), ' x')
    await userEvent.click(screen.getByTestId('acal161-enregistrer'))

    // La clef du refus de l'exemple est `edition.positions.coffret_ac` : aucune ligne ne la porte,
    // le message reste visible en bandeau, jamais avalé.
    expect(await screen.findByTestId('acal161-bandeau')).toHaveTextContent(REFUS['edition.positions.coffret_ac'])
  })

  it('un libellé refusé s’affiche sous son champ', async () => {
    servir(AVANT)
    calepinageApi.calepinages.enregistrerEditionSld.mockRejectedValue({
      response: { status: 400, data: { 'edition.libelles.ddr': 'Le libellé « ddr » ne peut pas contenir de montant.' } },
    })

    rendre()
    await screen.findByTestId('acal161-edition')
    await userEvent.type(champ('libelles', 'ddr'), ' 1000 MAD')
    await userEvent.click(screen.getByTestId('acal161-enregistrer'))

    expect(await screen.findByTestId('acal161-erreur-libelles-ddr')).toHaveTextContent('montant')
  })

  it('aucun éditeur sans bloc dessiné (svg nul)', async () => {
    servir({ calepinage: 12, svg: null, blocs: [], edition: {}, bloquants: [], manquantes: ['fiche'] })

    rendre()
    await screen.findByTestId('cal195-panneau')
    expect(screen.queryByTestId('acal161-edition')).toBeNull()
  })

  it('corpsEdition ne renvoie que les rubriques modifiées', () => {
    const blocs = [{ clef: 'a', titre: 'A', repere: '' }]
    expect(corpsEdition(blocs, { libelles: { a: 'A' }, reperes: {} })).toEqual({})
    expect(corpsEdition(blocs, { libelles: {}, reperes: { a: 'R1' } })).toEqual({ reperes: { a: 'R1' } })
  })
})

/* ── ACAL1301 — le sous-écran « Schéma » : planche, légende et cartouche (maquette `Schema.dc.html`) ── */
describe('PlancheSchema, légende et cartouche (ACAL1301)', () => {
  const SVG = exempleContrat('calepinage', 'calepinage_sld').svg

  it('la planche insère le SVG SERVI entier, avec zoom ± et déplacement au clavier', async () => {
    render(<PlancheSchema balisage={{ __html: SVG }} note="Dessiné tout seul à partir du raccordement : 2 chaînes de 6 panneaux." />)
    const vue = screen.getByTestId('csch-vue')
    // Le SVG servi, entier : son `viewBox` est gardé (la planche le cadre sans le couper).
    expect(screen.getByTestId('csch-svg').querySelector('svg[viewBox="0 0 842 595"]')).not.toBeNull()
    expect(screen.getByTestId('csch-svg')).toHaveTextContent('Champ PV')
    expect(screen.getByRole('heading', { name: 'Schéma électrique' })).toBeTruthy()
    expect(screen.getByText('Des panneaux jusqu’au réseau · sans échelle')).toBeTruthy()
    const u = userEvent.setup()
    await u.click(screen.getByRole('button', { name: 'Zoomer' }))
    expect(vue).toHaveAttribute('data-echelle', '1.25')
    await u.click(screen.getByRole('button', { name: 'Dézoomer' }))
    await u.click(screen.getByRole('button', { name: 'Dézoomer' }))
    expect(vue).toHaveAttribute('data-echelle', '0.8')
    vue.focus()
    await u.keyboard('{ArrowLeft}')
    expect(screen.getByTestId('csch-svg').style.transform).toContain('translate(40px, 0px)')
    expect(screen.getByText(/2 chaînes de 6 panneaux/)).toBeTruthy()
  })

  it('S2 — echelleAjustee : tout le dessin tient dans le cadre, jamais agrandi, 1 sans mesure', () => {
    expect(echelleAjustee(296, 872)).toBe(0.339)
    expect(echelleAjustee(436, 872)).toBe(0.5)
    expect(echelleAjustee(1200, 872)).toBe(1)
    expect(echelleAjustee(0, 872)).toBe(1)
    expect(echelleAjustee(undefined, 872)).toBe(1)
    expect(echelleAjustee(300, null)).toBe(1)
  })

  it('S2 — dans un cadre étroit (tablette), le schéma en blocs démarre à l’échelle qui le fait tenir, puis le zoom reprend', async () => {
    const clientWidth = vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(436)
    const ancien = globalThis.ResizeObserver
    globalThis.ResizeObserver = class { observe() {} disconnect() {} }
    try {
      render(<PlancheSchema dessin={<svg />} largeurDessin={872} />)
      const vue = screen.getByTestId('csch-vue')
      await waitFor(() => expect(vue).toHaveAttribute('data-echelle', '0.5'))
      expect(screen.getByTestId('csch-blocs').style.width).toBe('872px')
      const u = userEvent.setup()
      await u.click(screen.getByRole('button', { name: 'Zoomer' }))
      expect(vue).toHaveAttribute('data-echelle', '0.625')
      // Dézoomer sous l'échelle de départ est permis (le départ n'est jamais un plancher plus haut que 0,5).
      expect(screen.getByRole('button', { name: 'Dézoomer' })).not.toBeDisabled()
    } finally {
      clientWidth.mockRestore()
      globalThis.ResizeObserver = ancien
    }
  })

  it('sans SVG : pas de zoom, les motifs (enfants) à la place', () => {
    render(<PlancheSchema balisage={null}><p>motif du serveur</p></PlancheSchema>)
    expect(screen.queryByRole('button', { name: 'Zoomer' })).toBeNull()
    expect(screen.getByText('motif du serveur')).toBeTruthy()
  })

  it('la légende ne nomme que les signes du SVG servi', () => {
    const plein = '<svg><line x1="0" y1="0" x2="1" y2="1" stroke="#1f3a5f"/></svg>'
    expect(lignesLegende(plein).map((l) => l.cle)).toEqual(['liaison'])
    const complet = `${plein.slice(0, -6)}<line x1="0" y1="0" x2="1" y2="0" stroke-dasharray="4 3"/><text>6,0 mm²</text></svg>`
    expect(lignesLegende(complet).map((l) => l.libelle)).toEqual([
      'Liaison entre deux organes', 'Liaison à la terre', 'Section du câble, puis sa longueur'])
    expect(lignesLegende(null)).toEqual([])
  })

  it('le cartouche lit le détail SERVI ; un champ non servi est omis (jamais une valeur inventée)', () => {
    const detail = structuredClone(exempleContrat('calepinage', 'calepinage_detail'))
    const le = detail.versions.derniere_le
    const heure = new Date(le).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    expect(lignesCartouche(detail)).toEqual([
      { libelle: 'Projet', valeur: 'Toiture — bâtiment principal — Casablanca' },
      { libelle: 'Date', valeur: new Date(le).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) },
      { libelle: 'Version', valeur: `Enregistrée à ${heure}` }, // l'empreinte technique n'est plus montrée quand l'heure est servie
      { libelle: 'Auteur', valeur: "Utilisateur d'essai" },
    ])
    detail.responsable = null
    detail.cree_par = null
    detail.layout_hash = ''
    detail.versions = null
    const sans = lignesCartouche(detail)
    expect(sans.map((l) => l.libelle)).toEqual(['Projet', 'Date'])
    expect(sans.find((l) => l.libelle === 'Date').valeur)
      .toBe(new Date(detail.modifie_le).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }))
    expect(lignesCartouche(null)).toEqual([])
  })
})

/* ── F3 (tour 2) — le schéma EN BLOCS de la maquette `Schema.dc.html`, composé depuis les données SERVIES ── */
describe('planSchemaEnBlocs / SchemaEnBlocs (maquette Schema, tour 2)', () => {
  const echantillons = () => ({
    schema: structuredClone(exempleContrat('calepinage', 'calepinage_sld')),
    resultat: structuredClone(exempleContrat('calepinage', 'calepinage_resultat')),
  })

  it('blocs servis seulement : chaînes rangées 1..n avec LEUR couleur servie, coffrets, onduleur, compteur, TGBT', () => {
    const { schema, resultat } = echantillons()
    // La table servie donne les chaînes dans l'ordre des modules : la 2 avant la 1.
    resultat.electrique.affectation.reverse()
    const plan = planSchemaEnBlocs(schema, resultat)
    expect(plan.chaines.map((c) => [c.chaine, c.nombre, c.couleur, c.mppt])).toEqual([
      [1, 2, 'rgb(30, 144, 255)', 1], [2, 2, 'rgb(255, 140, 0)', 2]])
    expect(plan.chaines[0].libelle).toBe('Chaîne 1 · 2 panneaux')
    expect(plan.chaines[0].detail).toBe('2 × 720 Wc') // chainage.puissance_module_wc servi
    // Le coffret DC est servi sans organe de protection : la boîte dit ce que le serveur en publie.
    expect(plan.coffretDc.organes).toEqual([])
    expect(plan.coffretDc.detail.join(' ')).toBe('2 chaîne(s) raccordée(s)')
    // Côté réseau : disjoncteur + différentiel servis (aucun parafoudre AC : non dessiné), compteur, TGBT ; pas de « reseau ».
    expect(plan.blocsAc.map((b) => b.cle)).toEqual(['coffret_ac', 'compteur', 'tgbt'])
    expect(plan.blocsAc[0].organes.map((o) => [o.nom, o.detail])).toEqual([
      ['Disjoncteur', 'calibre : note de calcul'], ['Différentiel', 'protège les personnes']])
    expect(plan.onduleur.puissance).toBe('10 kW')
    expect(plan.onduleur.designation).toEqual([]) // le bloc servi s'appelle « Onduleur » : pas répété
    expect(plan.onduleur.entrees).toBe('2 entrées : 1 et 2')
    // Tient dans la planche de 1440 × 900 sans réduire le texte (≈ 880 × 680 px utiles).
    expect(plan.largeur).toBeLessThanOrEqual(880)
    expect(plan.hauteur).toBeLessThanOrEqual(680)
  })

  it('sections : écrites seulement si TOUS les tronçons du côté la partagent ; longueur seulement pour un tronçon unique', () => {
    const { schema, resultat } = echantillons()
    let plan = planSchemaEnBlocs(schema, resultat)
    const etiquettes = (p) => p.liaisons.filter((l) => l.etiquette).map((l) => l.etiquette.lignes.join(' / '))
    // DC : 6 mm² partout ; AC : deux tronçons de 10 mm² ⇒ section, mais AUCUNE longueur attribuée.
    expect(etiquettes(plan)).toEqual(['6 mm²', 'entrée 1 · 6 mm²', '6 mm²', 'entrée 2 · 6 mm²', '10 mm²'])
    resultat.troncons.troncons[1].section_mm2 = 4 // deux sections DC différentes
    resultat.troncons.troncons = resultat.troncons.troncons.filter((t) => t.id !== 'ch4') // un seul tronçon AC
    plan = planSchemaEnBlocs(schema, resultat)
    expect(etiquettes(plan)).toEqual(['entrée 1', 'entrée 2', '10 mm² / 35 m'])
    resultat.troncons = null // aucun cheminement : aucune section, aucune longueur
    plan = planSchemaEnBlocs(schema, resultat)
    expect(etiquettes(plan)).toEqual(['entrée 1', 'entrée 2'])
    expect(plan.legende.map((l) => l.cle)).not.toContain('section')
  })

  it('légende = ce que le dessin emploie ; terre seulement si le schéma servi en trace une', () => {
    const { schema, resultat } = echantillons()
    let plan = planSchemaEnBlocs(schema, resultat)
    expect(plan.terre).toBeNull()
    expect(plan.legende.map((l) => l.libelle)).toEqual([
      'Chaîne 1 · entrée 1', 'Chaîne 2 · entrée 2', 'Côté réseau (courant alternatif)', 'Section du câble, puis sa longueur'])
    expect(plan.legende[0].couleur).toBe('rgb(30, 144, 255)')
    schema.svg = schema.svg.replace('</svg>', '<line x1="0" y1="0" x2="9" y2="0" stroke-dasharray="4 3"/></svg>')
    plan = planSchemaEnBlocs(schema, resultat)
    expect(plan.terre.libelle).toBe('Terre : coffrets, onduleur et structure')
    expect(plan.legende.map((l) => l.cle)).toContain('terre')
  })

  it('rien de servi pour dessiner (aucun onduleur ou aucune chaîne) ⇒ null : l’écran garde le schéma détaillé', () => {
    const { schema, resultat } = echantillons()
    expect(planSchemaEnBlocs({ ...schema, blocs: schema.blocs.filter((b) => b.clef !== 'onduleur') }, resultat)).toBeNull()
    resultat.electrique.affectation = []
    expect(planSchemaEnBlocs(schema, resultat)).toBeNull()
    expect(planSchemaEnBlocs(null, null)).toBeNull()
  })

  it('quatre chaînes de quinze (calepinage de revue) : rangées compactes, le dessin tient toujours dans la planche', () => {
    const { schema, resultat } = echantillons()
    resultat.electrique.affectation = [3, 1, 4, 2].flatMap((chaine) => Array.from({ length: 15 }, (_, i) => ({
      module: `m${chaine}-${i}`, chaine, mppt: chaine, onduleur: 1, couleur_chaine: `rgb(${chaine}, 0, 0)` })))
    const plan = planSchemaEnBlocs(schema, resultat)
    expect(plan.chaines.map((c) => c.chaine)).toEqual([1, 2, 3, 4])
    expect(plan.chaines.every((c) => c.glyphes.n === 15 && c.glyphes.l > 8)).toBe(true)
    expect(plan.hauteur).toBeLessThanOrEqual(690)
    expect(plan.largeur).toBeLessThanOrEqual(880)
  })

  it('le dessin : textes de 12 à 20 px, un clic ouvre la section où la valeur se règle, un glisser n’ouvre rien', () => {
    const { schema, resultat } = echantillons()
    const plan = planSchemaEnBlocs(schema, resultat)
    const onOuvrir = vi.fn()
    render(<PlancheSchema balisage={{ __html: schema.svg }} dessin={<SchemaEnBlocs plan={plan} onOuvrir={onOuvrir} />} />)
    const blocs = screen.getByTestId('csch-blocs')
    for (const texte of ['Côté panneaux · courant continu', 'Côté réseau · courant alternatif', 'Coffret côté panneaux',
      'Coffret côté réseau', 'Onduleur', '10 kW', 'continu → alternatif', 'Chaîne 1 · 2 panneaux', 'entrée 1 · 6 mm²']) {
      expect(blocs).toHaveTextContent(texte)
    }
    // Aucune classe de texte sous 12 px dans le dessin.
    const classes = [...blocs.querySelectorAll('text')].map((t) => t.getAttribute('class'))
    expect(classes.every((c) => /csch-t(12|14|16|20)/.test(c))).toBe(true)
    // Le SVG détaillé du serveur n'est pas monté dans cette vue.
    expect(screen.queryByTestId('csch-svg')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Chaîne 1 · 2 panneaux, entrée 1/ }))
    expect(onOuvrir).toHaveBeenLastCalledWith('controle-chaine')
    fireEvent.keyDown(screen.getByTestId('csch-bloc-onduleur'), { key: 'Enter' })
    expect(onOuvrir).toHaveBeenLastCalledWith('materiel-electrique')
    fireEvent.click(screen.getByTestId('csch-bloc-coffret_ac'))
    expect(onOuvrir).toHaveBeenLastCalledWith('equipements-electriques')
    onOuvrir.mockClear()
    const vue = screen.getByTestId('csch-vue')
    const chaine = screen.getByTestId('csch-chaine-2')
    fireEvent.pointerDown(chaine, { clientX: 10, clientY: 10, pointerId: 1 })
    fireEvent.pointerMove(chaine, { clientX: 60, clientY: 10, pointerId: 1 })
    fireEvent.pointerUp(chaine, { clientX: 60, clientY: 10, pointerId: 1 })
    fireEvent.click(chaine)
    expect(onOuvrir).not.toHaveBeenCalled()
    expect(blocs.style.transform).toContain('translate(50px, 0px)')
    expect(vue).toHaveAttribute('data-vue', 'blocs')
  })

  it('côté réseau pas encore servi : réseau, compteur et coffret EN CREUX, sans aucune valeur ; servi, ils les remplace', () => {
    const { schema, resultat } = echantillons()
    schema.blocs = schema.blocs.filter((b) => !['disjoncteur_ac', 'parafoudre_ac', 'ddr', 'compteur_production', 'tgbt', 'reseau'].includes(b.clef))
    resultat.simule = false
    resultat.hors_reseau = null // jamais simulé : le site est raccordé au réseau tant qu'on n'a pas dit le contraire
    resultat.troncons = null
    const plan = planSchemaEnBlocs(schema, resultat)
    expect(plan.coteReseauACalculer).toBe(true)
    expect(plan.blocsAc.map((b) => [b.cle, b.aCalculer])).toEqual([['coffret_ac', true], ['compteur', true], ['reseau', true]])
    // Aucune étiquette de section ni de longueur ; la légende n'annonce pas un trait « réseau » servi.
    expect(plan.liaisons.filter((l) => l.aCalculer).every((l) => l.etiquette === null)).toBe(true)
    expect(plan.legende.map((l) => l.cle)).not.toContain('ac')
    const aCalculer = vi.fn()
    render(<PlancheSchema balisage={{ __html: schema.svg }}
      dessin={<SchemaEnBlocs plan={plan} coteReseau={{ texte: phraseCoteReseau(resultat), onOuvrir: aCalculer }} />} />)
    const blocs = screen.getByTestId('csch-blocs')
    for (const texte of ['Coffret côté réseau', 'Compteur', 'Réseau du', 'distributeur']) expect(blocs).toHaveTextContent(texte)
    expect(blocs.querySelectorAll('[data-a-calculer="true"]')).toHaveLength(3)
    expect(blocs.textContent).not.toMatch(/mm²| \d+ m(?![a-zé])/)
    expect(screen.getByTestId('csch-a-calculer')).toHaveTextContent('Lancez la simulation pour dimensionner le côté réseau')
    fireEvent.click(screen.getByTestId('csch-a-calculer'))
    expect(aCalculer).toHaveBeenCalledTimes(1) // ouvre l'étape Résultats (onglet production)
  })

  it('côté réseau : site déclaré hors réseau ⇒ rien dessiné ; simulé sans norme ⇒ la phrase nomme la norme', () => {
    const { schema, resultat } = echantillons()
    schema.blocs = schema.blocs.filter((b) => !['disjoncteur_ac', 'compteur_production', 'tgbt', 'reseau', 'ddr'].includes(b.clef))
    resultat.hors_reseau = { banque: null, jours_autonomie: 2 } // bloc chiffré, sans `motif_absence`
    expect(estHorsReseau(resultat)).toBe(true)
    const plan = planSchemaEnBlocs(schema, resultat)
    expect(plan.coteReseauACalculer).toBe(false)
    expect(plan.blocsAc).toEqual([])
    resultat.hors_reseau = { motif_absence: 'Ce calepinage n’est pas déclaré hors réseau' }
    expect(estHorsReseau(resultat)).toBe(false)
    expect(phraseCoteReseau({ simule: true })).toMatch(/norme électrique/)
    expect(phraseCoteReseau({ simule: false })).toMatch(/Lancez la simulation/)
  })

  it('couperTexte : mots entiers, n lignes au plus, … au bout', () => {
    expect(couperTexte('Huawei Onduleur réseau Huawei 50kW TRIPHASE', 22, 3)).toEqual(['Huawei Onduleur réseau', 'Huawei 50kW TRIPHASE'])
    expect(couperTexte('Compteur de production', 12)).toEqual(['Compteur de', 'production'])
    expect(couperTexte('un deux trois quatre cinq', 5, 2)).toEqual(['un', 'deux…'])
    expect(couperTexte(null, 10)).toEqual([])
  })
})

/* ── LOT 6 — le MÊME dessin, lu sur le document `schema_electrique` du contrat (ventes/schema_electrique.json) ── */
describe('planDepuisDocument — le document schema_electrique (lot 6)', () => {
  const doc = (option, variante = 'exemple') => structuredClone(
    exempleContrat('ventes', 'schema_electrique', variante).schema_electrique.options[option])
  const dessiner = (plan) => {
    render(<PlancheSchema balisage={null} dessin={<SchemaEnBlocs plan={plan} />} />)
    return screen.getByTestId('csch-blocs')
  }

  it('avec batterie : quatre chaînes aux quatre couleurs du contrat, onduleur, côté réseau ET la carte batterie', () => {
    const plan = planDepuisDocument(doc('avec_batterie'))
    expect(plan.chaines.map((c) => [c.chaine, c.nombre, c.couleur, c.mppt])).toEqual([
      [1, 12, 'rgb(36, 130, 214)', 1], [2, 12, 'rgb(232, 125, 33)', 1],
      [3, 12, 'rgb(46, 163, 89)', 2], [4, 12, 'rgb(184, 64, 158)', 2]])
    expect(plan.onduleur.designation.join(' ')).toBe('Deye SUN-20K-SG05LP3')
    expect(plan.onduleur.entrees).toBe('2 entrées : 1 et 2')
    expect(plan.blocsAc.map((b) => b.cle)).toEqual(['coffret_ac', 'compteur', 'tgbt', 'reseau'])
    expect(plan.batterie.lignes).toEqual(['Dyness BX51100', '3 unités', '15,36 kWh au total', '51,2 V'])
    expect(plan.legende.map((l) => l.libelle)).toContain('Liaison batterie')
    // La carte est dans la bande courant continu, à gauche de l'onduleur, et ne le recouvre pas.
    expect(plan.batterie.x + plan.batterie.l).toBeLessThan(plan.onduleur.x)
    expect(plan.batterie.y + plan.batterie.h).toBeLessThan(plan.bandes[0].h)
    const blocs = dessiner(plan)
    for (const texte of ['Batterie', 'Dyness BX51100', '3 unités', '15,36 kWh au total', '51,2 V',
      'Chaîne 4 · 12 panneaux', 'Côté réseau · courant alternatif', 'Compteur ONEE']) {
      expect(blocs).toHaveTextContent(texte)
    }
    expect(screen.getByTestId('csch-bloc-batterie')).toBeInTheDocument()
    expect(screen.getByTestId('csch-lien-batterie')).toBeInTheDocument()
    // La batterie n'ajoute aucune largeur : le côté réseau reste dans la planche de 1440 px.
    expect(plan.largeur).toBeLessThanOrEqual(880)
  })

  it('sans batterie : aucune carte, aucune liaison, aucune ligne de légende « batterie »', () => {
    const plan = planDepuisDocument(doc('sans_batterie'))
    expect(plan.batterie).toBeUndefined()
    expect(plan.chaines.map((c) => c.nombre)).toEqual([18, 17])
    expect(plan.legende.map((l) => l.libelle)).not.toContain('Liaison batterie')
    dessiner(plan)
    expect(screen.queryByTestId('csch-bloc-batterie')).toBeNull()
    expect(screen.queryByTestId('csch-lien-batterie')).toBeNull()
  })

  it('une valeur null est omise, jamais remplacée : niveau standard (tension et calibres absents)', () => {
    const d = doc('avec_batterie', 'exemple_standard')
    const plan = planDepuisDocument(d)
    expect(plan.batterie.lignes).toEqual(['Dyness BX51100', '3 unités', '15,36 kWh au total'])
    d.batterie.capacite_kwh = null
    d.batterie.designation = null
    expect(planDepuisDocument(d).batterie.lignes).toEqual(['3 unités'])
    // Sections nulles : aucune étiquette « mm² » ni longueur sur les liaisons.
    expect(plan.liaisons.every((l) => !l.etiquette?.lignes.some((t) => /mm²| m$/.test(t)))).toBe(true)
    expect(dessiner(plan).textContent).not.toMatch(/—|–|\bnull\b|undefined|NaN/)
  })

  it('champ sans découpage : UN champ au nombre réel de panneaux, aucune chaîne inventée, côté réseau en creux', () => {
    const plan = planDepuisDocument(doc('sans_batterie', 'exemple_champ_sans_repartition'))
    expect(plan.chaines).toHaveLength(1)
    expect(plan.chaines[0].libelle).toBe('Champ · 35 panneaux')
    expect(plan.chaines[0].couleur).toBeNull()
    expect(plan.chaines[0].mppt).toBeNull()
    expect(plan.coteReseauACalculer).toBe(true)
    expect(plan.blocsAc.every((b) => b.aCalculer)).toBe(true)
    expect(plan.legende[0].libelle).toBe('Champ de panneaux')
  })

  it('hors réseau : rien côté réseau ; sans panneau ni chaîne : null', () => {
    const d = doc('avec_batterie')
    d.cote_reseau = { etat: 'hors_reseau', motif: null }
    d.coffret_ac = null; d.compteur_production = null; d.tgbt = null; d.reseau = null
    const plan = planDepuisDocument(d)
    expect(plan.blocsAc).toEqual([])
    expect(plan.coteReseauACalculer).toBe(false)
    const vide = doc('sans_batterie', 'exemple_champ_sans_repartition')
    vide.panneaux.nombre = 0
    expect(planDepuisDocument(vide)).toBeNull()
    expect(planDepuisDocument(null)).toBeNull()
    expect(planDepuisDocument({})).toBeNull()
  })

  it('aucun montant : le dessin ne contient ni prix ni devise, avec ou sans batterie', () => {
    for (const option of ['avec_batterie', 'sans_batterie']) {
      cleanup()
      const texte = dessiner(planDepuisDocument(doc(option))).textContent
      expect(texte).not.toMatch(/\bDH\b|\bMAD\b|€|\$|\bprix\b|\bHT\b|\bTTC\b|\bachat\b/i)
    }
  })

  it('un libellé édité (parafoudre DC renommé) s\'affiche par le chemin du document', () => {
    const plan = planDepuisDocument(doc('avec_batterie'), { parafoudre_dc: 'Protection foudre toit' })
    expect(plan.coffretDc.organes.find((o) => o.clef === 'parafoudre_dc').nom).toBe('Protection foudre toit')
    expect(plan.coffretDc.organes.find((o) => o.clef === 'sectionneur_dc').nom).toBe('Sectionneur')
    expect(dessiner(plan)).toHaveTextContent('Protection foudre toit')
  })

  it('ACAL1551 — la coupure d’urgence DC servie (organe_dc) est dessinée dans le coffret DC sous SA désignation', () => {
    const d = doc('avec_batterie')
    d.coffret_dc.organes.push({ clef: 'organe_dc', repere: 'SOC1', titre: 'Coupure d’urgence DC (arrêt rapide)', calibre: null, quantite: 1 })
    const plan = planDepuisDocument(d)
    const organe = plan.coffretDc.organes.find((o) => o.clef === 'organe_dc')
    expect(organe.nom).toBe('Coupure d’urgence DC (arrêt rapide)')
    expect(organe.detail).toBe('décision société')
    expect(plan.coffretDc.organes.map((o) => o.clef).at(-1)).toBe('organe_dc')
    expect(dessiner(plan)).toHaveTextContent('Coupure d’urgence DC (arrêt rapide)')
  })

  it.each([100, 400])('champ de %i panneaux : tuiles bornées et lisibles, le nombre écrit reste le vrai', (n) => {
    const d = doc('sans_batterie', 'exemple_champ_sans_repartition')
    d.panneaux.nombre = n
    const plan = planDepuisDocument(d)
    const g = plan.chaines[0].glyphes
    expect(g.n).toBeLessThanOrEqual(24)
    expect(g.l).toBeGreaterThan(3)
    expect(plan.chaines[0].libelle).toBe(`Champ · ${n} panneaux`)
    expect(plan.chaines[0].detail).toBe(`${n} × 715 Wc`)
    const blocs = dessiner(plan)
    const tuiles = [...blocs.querySelectorAll('rect.csch-glyphe')]
    expect(tuiles).toHaveLength(g.n)
    expect(tuiles.every((t) => Number(t.getAttribute('width')) > 0)).toBe(true)
  })

  it('étage moyenne tension : ses blocs entre le coffret et le compteur, « à confirmer », sans rien recouvrir', () => {
    const d = doc('avec_batterie')
    d.etage_mt = [
      { clef: 'cellule_mt', titre: 'Cellule MT', detail: 'à confirmer' },
      { clef: 'transfo', titre: 'Transformateur MT/BT', detail: 'à confirmer' }]
    const base = planDepuisDocument(doc('avec_batterie'))
    const plan = planDepuisDocument(d)
    expect(plan.blocsAc.map((b) => b.cle)).toEqual(['coffret_ac', 'mt-cellule_mt', 'mt-transfo', 'compteur', 'tgbt', 'reseau'])
    // Aucun recouvrement horizontal dans la chaîne alternative, de la gauche vers l'onduleur.
    const rangee = [...plan.blocsAc].sort((a, b) => a.x - b.x)
    rangee.forEach((b, i) => {
      const suivant = rangee[i + 1] ?? plan.onduleur
      expect(b.x + b.l).toBeLessThan(suivant.x)
    })
    expect(Math.min(...plan.blocsAc.map((b) => b.x))).toBeGreaterThanOrEqual(0)
    // Les blocs côté réseau n'ont pas bougé ; l'onduleur et la batterie ont glissé de la largeur ajoutée.
    expect(plan.blocsAc.find((b) => b.cle === 'reseau').x).toBe(base.blocsAc.find((b) => b.cle === 'reseau').x)
    const w = plan.largeur - base.largeur
    expect(plan.onduleur.x - base.onduleur.x).toBe(w)
    expect(plan.batterie.x - base.batterie.x).toBe(w)
    // Chaque liaison alternative relie deux blocs voisins ; les entrées des chaînes atteignent l'onduleur déplacé.
    expect(plan.liaisons.filter((l) => /^ac\d/.test(l.cle))).toHaveLength(6)
    expect(plan.liaisons.filter((l) => l.couleur).map((l) => l.points.at(-1)[0]).filter((x) => x === plan.onduleur.x).length).toBeGreaterThan(0)
    const blocs = dessiner(plan)
    expect(blocs).toHaveTextContent('Cellule MT')
    expect(blocs).toHaveTextContent('Transformateur')
    expect(screen.getByTestId('csch-bloc-mt-cellule_mt')).toHaveTextContent('à confirmer')
    // Basse tension : aucun bloc MT.
    expect(base.blocsAc.some((b) => b.aConfirmer)).toBe(false)
  })

  it('plusieurs groupes d\'onduleurs : tous listés, aucun total ni puissance d\'un seul groupe', () => {
    const d = doc('avec_batterie')
    d.onduleurs.push({ designation: 'Huawei SUN2000-10KTL', puissance_kw: 10, nombre: 2, nb_entrees: 2 })
    const plan = planDepuisDocument(d)
    expect(plan.onduleur.puissance).toBeNull()
    expect(plan.onduleur.entrees).toBeNull()
    expect(plan.onduleur.designation.join(' ')).not.toContain('…')
    expect(plan.onduleur.designation.join(' ')).toMatch(/^1 × Deye.*SUN-20K-SG05LP3.*20 kW 2 × Huawei.*SUN2000-10KTL.*10 kW$/)
    const blocs = dessiner(plan)
    expect(blocs).toHaveTextContent('SUN2000-10KTL')
    expect(blocs).toHaveTextContent('SUN-20K-SG05LP3')
  })

  it('deux dessins montés ensemble : un identifiant de flèche par instance', () => {
    const plan = planDepuisDocument(doc('avec_batterie'))
    render(<><SchemaEnBlocs plan={plan} /><SchemaEnBlocs plan={plan} /></>)
    const ids = [...document.querySelectorAll('marker')].map((m) => m.id)
    expect(ids).toHaveLength(2)
    expect(new Set(ids).size).toBe(2)
    const liens = [...document.querySelectorAll('[data-testid="csch-lien-batterie"]')]
    expect(liens.map((l) => l.getAttribute('marker-end'))).toEqual(ids.map((i) => `url(#${i})`))
  })

  // Tous les états que porte `calepinage_sld.json` (clés `exemple*`), puis leurs variantes extrêmes : chacun se dessine sans
  // lever, sans « undefined / NaN / null » à l'écran ; un état sans document (`exemple_vide`) ne dessine rien.
  const etats = Object.keys(documentContrat('calepinage', 'calepinage_sld')).filter((k) => k.startsWith('exemple'))
  const variantes = {
    tel_quel: () => {},
    onduleur_sans_fiche: (d) => { d.onduleurs = [{ designation: null, puissance_kw: null, nombre: null, nb_entrees: null }] },
    micro_onduleurs: (d) => { d.onduleurs = [{ designation: 'Micro-onduleur 400 W', puissance_kw: 0.4, nombre: 24, nb_entrees: 1 }] },
    cote_reseau_a_calculer: (d) => {
      Object.assign(d, { coffret_ac: null, compteur_production: null, tgbt: null, reseau: null,
        cote_reseau: { etat: 'a_calculer', motif: 'Le côté réseau n’est pas encore dimensionné.' } })
    },
    champ_de_300_panneaux: (d) => { d.chaines_reparties = false; d.chaines = []; d.panneaux.nombre = 300 },
    sans_module: (d) => { d.panneaux.module = { designation: null, puissance_wc: null } },
  }
  describe.each(etats)('état « %s » de calepinage_sld.json', (etat) => {
    it.each(Object.keys(variantes))('%s : dessiné sans lever', (variante) => {
      const d = structuredClone(exempleContrat('calepinage', 'calepinage_sld', etat).schema_electrique)
      if (d === null) { expect(planDepuisDocument(d)).toBeNull(); return }
      variantes[variante](d)
      const plan = planDepuisDocument(d, {})
      expect(plan).not.toBeNull()
      expect(dessiner(plan).textContent).not.toMatch(/undefined|NaN|\bnull\b/)
    })
  })

  it('aucun onduleur servi : aucun bloc onduleur inventé (pas de plan)', () => {
    const d = doc('avec_batterie')
    d.onduleurs = []
    expect(planDepuisDocument(d)).toBeNull()
  })

  it('un clic sur la batterie ouvre la section où elle se règle', () => {
    const onOuvrir = vi.fn()
    render(<PlancheSchema balisage={null} dessin={<SchemaEnBlocs plan={planDepuisDocument(doc('avec_batterie'))} onOuvrir={onOuvrir} />} />)
    fireEvent.click(screen.getByTestId('csch-bloc-batterie'))
    expect(onOuvrir).toHaveBeenLastCalledWith('materiel-electrique')
  })
})
