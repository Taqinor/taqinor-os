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
import SchemaUnifilairePanel, { PlancheSchema } from './SchemaUnifilairePanel'
import { motifDuRefusDxf, corpsEdition, lignesCartouche, lignesLegende } from './SchemaUnifilairePanel.helpers'
import { exempleContrat } from '../../test/fixtures/contractSamples'
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
      { libelle: 'Version', valeur: `Enregistrée à ${heure} · abababab` },
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
