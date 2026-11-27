/* Nouveau fichier car : EtapeToit.jsx est un composant neuf (écran guidé de l'étape Toit, maquettes Main /
   ToitSombre) sans module de test voisin ; le script du constructeur ne tourne pas sous vitest : le DOM qu'il
   possède (`rp9-*`) est posé à la main, comme il l'écrit, et l'écran est jugé sur ce qu'il LIT et CLIQUE.
   Ce qui est prouvé : blocs et libellés de la maquette dans l'ordre, crochets e2e, figures lues dans le DOM du
   constructeur (bloc omis sans donnée), renvoi de chaque geste au vrai contrôle `rp9-*`, la règle « À confirmer »,
   « Confirmer » = la requête de « Enregistrer la pente », « Je ne la connais pas » n'écrit rien, le compte des
   contrôles, et la feuille 51-etape-toit.css sans couleur littérale (thème sombre par les jetons). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, renderHook, screen, cleanup, within, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import process from 'node:process'

const layout = vi.fn()
const designContext = vi.fn()
const cibleFactures = vi.fn() // H3 — la taille des factures, lue à part du design-context
const enregistrerSectionLayout = vi.fn()
vi.mock('../../../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: (...a) => layout(...a),
      designContext: (...a) => designContext(...a),
      cibleFactures: (...a) => cibleFactures(...a),
      enregistrerSectionLayout: (...a) => enregistrerSectionLayout(...a),
      releveVisite: vi.fn(async () => ({ data: null })),
    },
    parametres: { suggestionPenteDisponible: vi.fn(async () => ({ data: { disponible: false } })) },
  },
}))

const { default: EtapeToit } = await import('./EtapeToit')
const { ContexteCoque } = await import('../contexteCoque')
const H = await import('./EtapeToit.helpers')
const { oublierLecturesServies } = await import('./panneaux/lectures')

/* Le DOM que le constructeur possède, tel qu'il l'écrit (ids, textes, attributs) : 2 pans, contour fermé,
   facture connue, une cheminée et un chauffe-eau. */
const CONSTRUCTEUR = `
  <div class="rp9-map-wrap"><div><button id="rp9-finish" disabled>Terminer le tracé</button>
    <button id="rp9-undo-point" hidden>Annuler le dernier point</button></div>
    <div class="maplibregl-ctrl-compass"><span class="maplibregl-ctrl-icon" style="transform: scale(1) rotateX(0deg) rotateZ(0deg)"></span></div></div>
  <div class="cal-coque-groupe" data-groupe="toit">
    <div><button id="rp9-clear">Effacer</button><button id="rp9-add-area">+ Ajouter une zone</button>
      <div id="rp9-formes-toit"></div>
      <form id="rp9-toit-cotes" hidden><input name="longueur"><input name="largeur"><input name="orientation"></form>
      <p><span id="rp9-area-value">~54 m²</span></p></div>
    <div id="rp9-config">
      <button data-rooftype="flat" aria-pressed="false">Toit plat</button>
      <button data-rooftype="pitched" aria-pressed="true">Toit en pente</button>
      <span id="rp9-pitch-value">22°</span><span id="rp9-facing-value">Sud · 180°</span>
      <p id="rp9-pitch-note">Pente : 22° par défaut — à confirmer</p>
      <div><button id="rp9-obstacle" aria-pressed="false">Ajouter un obstacle (cheminée…)</button>
        <details id="rp9-objets-site"><ul>
          <li><button data-objet="o1" data-pan="area-1">Cheminée · 0,6 × 0,6 m · hauteur 1,2 m · Relevé sur place · Pan 1</button></li>
          <li><button data-objet="o2" data-pan="area-2">Chauffe-eau solaire · 2,0 × 1,2 m · hauteur — · Non renseignée · Pan 2</button></li>
        </ul></details></div>
      <div><button id="rp9-mesure-distance" data-mesure-kind="distance" aria-pressed="false">Distance</button>
        <button id="rp9-mesure-finish" hidden>Terminer la mesure</button><button id="rp9-mesure-cancel" hidden>Annuler</button></div>
    </div>
  </div>
  <div id="rp9-areas-window">
    <div id="rp9-pan-geometry"><input id="rp9-pan-largeur" value="8,6"><input id="rp9-pan-longueur" value="12,4">
      <button id="rp9-pan-coter">Appliquer les cotes</button></div>
    <ul id="rp9-areas-list"><li data-area-row="area-1"></li><li data-area-row="area-2"></li></ul>
    <table><tbody>
      <tr data-pan-stat="area-1"><td>Pan 1</td><td>0</td><td>0</td><td>180°</td><td>22°</td><td>54</td><td>—</td></tr>
      <tr data-pan-stat="area-2"><td>Pan 2</td><td>0</td><td>0</td><td>0°</td><td>22°</td><td>53</td><td>—</td></tr>
    </tbody></table>
  </div>
  <dl><dd id="rp9-reco-kwc">7,2 kWc</dd><dd id="rp9-reco-cover">104 %</dd><dd id="rp9-reco-savings">≈ 9 000 MAD/an</dd></dl>
  <button id="rp9-layout-undo" disabled>↶ Annuler</button><button id="rp9-layout-redo" disabled>↷ Rétablir</button>`

const ZONE = { id: 'area-1', label: 'Pan 1', pitchDeg: 22, facingAzimuthDeg: 180, roofType: 'pitched' }
const $ = (id) => document.getElementById(id)
let surCarte
let pied
let builderApi

/** ACAL1971 — l'URL courante du routeur, lue pour prouver que `champ` est retiré une fois consommé. */
function SondeUrl() {
  return <span data-testid="sonde-url" hidden>{useLocation().search}</span>
}

function rendre(props = {}, avant = null, url = '/') {
  const hote = document.createElement('div')
  hote.className = 'rp9-host cal-coque'
  hote.dataset.avance = '0'
  hote.dataset.etape = 'toit'
  hote.innerHTML = CONSTRUCTEUR
  avant?.(hote)
  surCarte = document.createElement('div')
  surCarte.className = 'cal-coque-sur-carte'
  hote.appendChild(surCarte)
  const panneau = document.createElement('div')
  hote.appendChild(panneau)
  pied = document.createElement('div')
  hote.appendChild(pied)
  document.body.appendChild(hote)
  const coque = { noeuds: { surCarte, panneau: null, pied }, prendrePied: () => () => {} }
  return render(
    <MemoryRouter initialEntries={[url]}>
      <ContexteCoque.Provider value={coque}>
        <EtapeToit calepinageId={7} builderApi={builderApi} documentVivant={null} {...props} />
        <SondeUrl />
      </ContexteCoque.Provider>
    </MemoryRouter>,
    { container: panneau },
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  builderApi = { panActifId: () => 'area-1', appliquerVue: vi.fn() }
  designContext.mockResolvedValue({ data: { calepinage: { lead: 42 } } })
  cibleFactures.mockResolvedValue({ data: { cible_factures: { panneaux: 11, kwc: 6.93, module_wc: 630 } } })
  layout.mockResolvedValue({ data: { roof_layout: { zones: [ZONE, { ...ZONE, id: 'area-2', label: 'Pan 2' }] }, empreinte_document: 'jeton-1' } })
  enregistrerSectionLayout.mockImplementation(async (_id, corps) => ({ data: {
    empreinte_document: 'jeton-2',
    roof_layout: { zones: [{ ...ZONE, ...corps.champs }, { ...ZONE, id: 'area-2', label: 'Pan 2' }] },
  } }))
})
afterEach(() => { cleanup(); document.body.innerHTML = ''; vi.useRealTimers(); oublierLecturesServies() })

describe('Étape Toit — le panneau de la maquette Main', () => {
  it('Guidé sans contour : la coque porte data-sans-toit (champ d’adresse visible) ; avec contour : retiré', async () => {
    const { unmount } = rendre({}, (hote) => hote.querySelector('#rp9-add-area').remove())
    const coque = document.querySelector('.cal-coque')
    expect(coque.dataset.sansToit).toBe('1')
    unmount()
    expect(coque.dataset.sansToit).toBeUndefined()
    cleanup(); document.body.innerHTML = ''
    rendre()
    expect(document.querySelector('.cal-coque').dataset.sansToit).toBeUndefined()
  })

  // ACAL1945 — le moteur lit ce drapeau pour ne montrer aucun panneau posé à l'étape Toit du Guidé ; Expert : la 3D reste.
  it('ACAL1945 — Guidé : la coque porte data-pose-masquee tant que l’étape Toit est montée, et le moteur en est prévenu à l’entrée et à la sortie ; Expert : aucun drapeau', () => {
    const signaux = vi.fn()
    document.addEventListener('cal:pose-etape', signaux)
    const { unmount } = rendre()
    const coque = document.querySelector('.cal-coque')
    expect(coque.dataset.poseMasquee).toBe('1')
    expect(signaux).toHaveBeenCalledTimes(1)
    unmount()
    expect(coque.dataset.poseMasquee).toBeUndefined()
    expect(signaux).toHaveBeenCalledTimes(2)
    cleanup(); document.body.innerHTML = ''
    rendre({}, (hote) => { hote.dataset.expert = '1' })
    expect(document.querySelector('.cal-coque').dataset.poseMasquee).toBeUndefined()
    document.removeEventListener('cal:pose-etape', signaux)
  })

  // R5B-N7 (rejeu 26/11) — toit 10 × 8 créé en 2 pans : « Largeur » relisait 4 sans dire que ce sont les cotes d'UN pan.
  it('R5B-N7 — plusieurs pans : les cotes sont dites celles du pan sélectionné ; un seul pan : rien de plus', async () => {
    rendre()
    const dims = screen.getByTestId('cal-toit-dimensions').closest('.cal-toit-bloc-dimensions')
    expect(dims.querySelector('[data-zone="cotes-du-pan"]')).toHaveTextContent('Cotes du pan sélectionné — le toit en compte 2.')
    cleanup()
    document.body.innerHTML = ''
    rendre({}, (hote) => hote.querySelector('#rp9-areas-list li[data-area-row="area-2"]').remove())
    expect(screen.getByTestId('cal-toit-dimensions')).toBeInTheDocument()
    expect(document.querySelector('[data-zone="cotes-du-pan"]')).toBeNull()
  })

  it('blocs dans l’ordre de la maquette, libellés mot pour mot, crochets e2e', async () => {
    rendre()
    const titres = [...document.querySelectorAll('.cal-etape-toit h2')].map((n) => n.textContent)
    expect(titres).toEqual(['Forme', 'Dimensions', 'Pente et orientation', 'Obstacles · 2']) // ACAL1827 — le nombre est dit
    const dims = screen.getByTestId('cal-toit-dimensions')
    expect(within(dims).getByLabelText('Longueur')).toHaveValue('12,4')
    expect(within(dims).getByLabelText('Largeur')).toHaveValue('8,6')
    expect([...dims.querySelectorAll('.cal-toit-saisie > span')].map((n) => n.textContent)).toEqual(['m', 'm'])
    const carte = screen.getByTestId('cal-toit-pente-carte')
    await waitFor(() => expect(within(carte).getByText('22° · face sud')).toBeInTheDocument())
    expect(within(carte).getByText('À confirmer')).toBeInTheDocument()
    expect(within(carte).getByText('Valeur de départ, pas une mesure : confirmez-la ou mesurez-la.')).toBeInTheDocument()
    expect(screen.getByTestId('cal-toit-pente-confirmer')).toHaveTextContent('Confirmer')
    expect(screen.getByTestId('cal-toit-pente-inconnue')).toHaveTextContent('Je ne la connais pas')
    const obstacles = screen.getByTestId('cal-toit-obstacles')
    expect(within(obstacles).getByRole('button', { name: '+ Ajouter' })).toBeInTheDocument()
    const lignes = within(obstacles).getAllByRole('option').map((li) => [
      li.querySelector('.cal-toit-obstacle-nom').textContent, li.querySelector('.cal-toit-obstacle-cotes').textContent,
    ])
    expect(lignes).toEqual([['Cheminée', '0,6 × 0,6 m · 1,2 m'], ['Chauffe-eau solaire', '2,0 × 1,2 m']])
  })

  it('sans obstacle : l’en-tête et « + Ajouter » seuls, aucune ligne inventée', () => {
    rendre({}, (hote) => hote.querySelectorAll('#rp9-objets-site li').forEach((n) => n.remove()))
    const bloc = screen.getByTestId('cal-toit-obstacles')
    expect(within(bloc).queryByRole('listbox')).toBeNull()
    expect(within(bloc).getAllByRole('button').map((b) => b.textContent)).toEqual(['+ Ajouter'])
  })

  it('clic sur une ligne d’obstacle = clic sur sa ligne du tableau « Objets du site » ; « + Ajouter » = `rp9-obstacle`', () => {
    rendre()
    const ligneScript = document.querySelector('[data-objet="o2"]')
    const surLigne = vi.fn()
    ligneScript.addEventListener('click', surLigne)
    fireEvent.click(screen.getAllByRole('option')[1])
    expect(surLigne).toHaveBeenCalledTimes(1)
    expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
    const ajouter = vi.fn()
    $('rp9-obstacle').addEventListener('click', ajouter)
    fireEvent.click(screen.getByRole('button', { name: '+ Ajouter' }))
    expect(ajouter).toHaveBeenCalledTimes(1)
  })
})

describe('ACAL1971 — « Régler » d’un obstacle fautif', () => {
  it('?champ=<id de l’obstacle> : l’obstacle est sélectionné à l’arrivée, comme un clic sur sa ligne', async () => {
    const surLigne = vi.fn()
    rendre({}, (hote) => hote.querySelector('[data-objet="o2"]').addEventListener('click', surLigne), '/?onglet=pente&champ=o2')
    await waitFor(() => expect(surLigne).toHaveBeenCalledTimes(1))
    expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'false')
  })

  it('après l’arrivée : ↓ avance depuis l’obstacle visé, et `champ` est retiré de l’URL (onglet gardé) pour qu’un remontage ne le rejoue pas', async () => {
    const surLigne = vi.fn()
    rendre({}, (hote) => hote.querySelector('[data-objet="o2"]').addEventListener('click', surLigne), '/?onglet=pente&champ=o1')
    const liste = await screen.findByRole('listbox')
    await waitFor(() => expect(screen.getByTestId('sonde-url')).toHaveTextContent('?onglet=pente'))
    expect(screen.getByTestId('sonde-url').textContent).not.toContain('champ')
    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(liste, { key: 'ArrowDown' })
    expect(liste).toHaveAttribute('aria-activedescendant', 'cal-toit-obstacle-1')
    fireEvent.keyDown(liste, { key: 'Enter' })
    expect(surLigne).toHaveBeenCalledTimes(1)
    expect(screen.getAllByRole('option')[1]).toHaveAttribute('aria-selected', 'true')
  })

  it('un champ qui n’est pas un obstacle ne sélectionne rien', async () => {
    rendre({}, null, '/?onglet=pente&champ=inconnu')
    await screen.findAllByRole('option')
    screen.getAllByRole('option').forEach((o) => expect(o).toHaveAttribute('aria-selected', 'false'))
  })
})

describe('Étape Toit — « Pente et orientation »', () => {
  it('« Confirmer » envoie la requête de « Enregistrer la pente » (même section, même source) ; « À confirmer » disparaît', async () => {
    rendre()
    await waitFor(() => expect(screen.getByText('22° · face sud')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('cal-toit-pente-confirmer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    expect(enregistrerSectionLayout).toHaveBeenCalledWith(7, {
      cle: 'zones', zone_id: 'area-1', champs: { pitchDeg: 22, pitchSource: { mode: 'degres', degres: 22 } }, base_empreinte: 'jeton-1',
    })
    await waitFor(() => expect(screen.queryByText('À confirmer')).toBeNull())
    expect(within(screen.getByTestId('cal-toit-pente-carte')).getByRole('status')).toHaveTextContent('Pente enregistrée sur le pan « Pan 1 ».')
  })

  it('« Je ne la connais pas » : rien n’est écrit, la valeur reste « À confirmer », la visite la vérifiera', async () => {
    rendre()
    await waitFor(() => expect(screen.getByText('22° · face sud')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('cal-toit-pente-inconnue'))
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
    expect(screen.getByText('À confirmer')).toBeInTheDocument()
    expect(within(screen.getByTestId('cal-toit-pente-carte')).getByRole('status')).toHaveTextContent('elle sera vérifiée à la visite. Rien n’est enregistré.')
    expect(screen.queryByTestId('cal-toit-pente-confirmer')).toBeNull()
  })

  it('une pente déjà confirmée (`pitchSource` posé) : ni « À confirmer » ni boutons ; « Modifier la pente » reste', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [{ ...ZONE, pitchDeg: 30, facingAzimuthDeg: 135, pitchSource: { mode: 'degres', degres: 30 } }] }, empreinte_document: 'j' } })
    rendre()
    await waitFor(() => expect(screen.getByText('30° · face sud-est')).toBeInTheDocument())
    expect(screen.queryByText('À confirmer')).toBeNull()
    expect(screen.queryByTestId('cal-toit-pente-confirmer')).toBeNull()
    expect(screen.getByText('Modifier la pente').tagName).toBe('SUMMARY')
  })

  it('pan pas encore enregistré : la pente du script s’affiche, « À confirmer » suit sa mention `rp9-pitch-note`', async () => {
    builderApi = { panActifId: () => 'area-9', appliquerVue: vi.fn() }
    rendre()
    expect(await screen.findByText('22° · face sud')).toBeInTheDocument()
    expect(screen.getByText('À confirmer')).toBeInTheDocument()
  })

  it('ACAL1428 — pan absent du document servi : « Confirmer » confirme le pan vivant, sans écriture ni « Enregistrez d’abord »', async () => {
    builderApi = { panActifId: () => 'area-9', appliquerVue: vi.fn() }
    const surPuce = vi.fn()
    rendre({}, (hote) => {
      // le moteur : un clic sur la puce « ~22° » écrit pitchSource sur le pan et retire la mention « à confirmer »
      const puce = document.createElement('button')
      puce.dataset.pitch = '22'
      puce.addEventListener('click', () => { surPuce(); hote.querySelector('#rp9-pitch-note').textContent = '' })
      hote.appendChild(puce)
    })
    expect(await screen.findByText('22° · face sud')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('cal-toit-pente-confirmer'))
    expect(surPuce).toHaveBeenCalledTimes(1)
    expect(within(screen.getByTestId('cal-toit-pente-carte')).getByRole('status')).toHaveTextContent('Pente confirmée')
    expect(within(screen.getByTestId('cal-toit-pente-carte')).getByRole('status')).not.toHaveTextContent('Enregistrez d’abord')
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByText('À confirmer')).toBeNull())
  })
})

describe('Critique ACAL1428 × ACAL1429 — toit PLAT tracé, pas encore enregistré', () => {
  it('« Confirmer » confirme le pan vivant (même chemin que la pente), sans « Enregistrez d’abord » ni écriture', async () => {
    builderApi = { panActifId: () => 'area-9', appliquerVue: vi.fn() }
    const surPuce = vi.fn()
    rendre({}, (hote) => {
      hote.querySelector('[data-rooftype="flat"]').setAttribute('aria-pressed', 'true')
      hote.querySelector('[data-rooftype="pitched"]').setAttribute('aria-pressed', 'false')
      const puce = document.createElement('button')
      puce.dataset.pitch = '22'
      puce.addEventListener('click', () => { surPuce(); hote.querySelector('#rp9-pitch-note').textContent = '' })
      hote.appendChild(puce)
    })
    const carte = screen.getByTestId('cal-toit-pente-carte')
    await waitFor(() => expect(within(carte).getByText('Toit plat')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('cal-toit-pente-confirmer'))
    expect(surPuce).toHaveBeenCalledTimes(1)
    expect(within(carte).getByRole('status')).toHaveTextContent('Toit plat confirmé')
    expect(within(carte).getByRole('status')).not.toHaveTextContent('Enregistrez d’abord')
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })
})

describe('ACAL1429 — toit plat jamais confirmé', () => {
  const PLAT = { id: 'area-1', label: 'Pan 1', roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180 }

  it('pastille « À confirmer » et deux actions ; « Confirmer » écrit pitchSource {mode: plat} et 0°', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [PLAT] }, empreinte_document: 'jeton-1' } })
    enregistrerSectionLayout.mockImplementation(async (_id, corps) => ({ data: {
      empreinte_document: 'jeton-2', roof_layout: { zones: [{ ...PLAT, ...corps.champs }] } } }))
    rendre()
    const carte = screen.getByTestId('cal-toit-pente-carte')
    await waitFor(() => expect(within(carte).getByText('Toit plat')).toBeInTheDocument())
    expect(within(carte).getByText('À confirmer')).toBeInTheDocument()
    expect(screen.getByTestId('cal-toit-pente-inconnue')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('cal-toit-pente-confirmer'))
    await waitFor(() => expect(enregistrerSectionLayout).toHaveBeenCalledTimes(1))
    expect(enregistrerSectionLayout.mock.calls[0][1].champs).toEqual({ pitchDeg: 0, pitchSource: { mode: 'plat' } })
    await waitFor(() => expect(within(carte).queryByText('À confirmer')).toBeNull())
    expect(within(carte).getByText('Toit plat')).toBeInTheDocument()
  })

  it('ACAL1922 : le serveur rend le pan SANS pitchSource = écriture non retenue : la carte GARDE « À confirmer », le refus est dit, la conception est relue', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [PLAT] }, empreinte_document: 'jeton-1' } })
    enregistrerSectionLayout.mockImplementation(async () => ({ data: {
      empreinte_document: 'jeton-2', roof_layout: { zones: [PLAT] } } }))
    rendre()
    const carte = screen.getByTestId('cal-toit-pente-carte')
    await waitFor(() => expect(within(carte).getByText('Toit plat')).toBeInTheDocument())
    const lectures = layout.mock.calls.length
    fireEvent.click(screen.getByTestId('cal-toit-pente-confirmer'))
    await waitFor(() => expect(within(carte).getByRole('status')).toHaveTextContent('n’a pas été retenue'))
    expect(within(carte).getByText('À confirmer')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-toit-plat-confirme')).toBeNull()
    await waitFor(() => expect(layout.mock.calls.length).toBeGreaterThan(lectures)) // relu, pas un écho
  })

  it('ACAL1922 : le serveur rend le pan avec pitchSource ⇒ « Toit plat · confirmé », sans bouton', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [PLAT] }, empreinte_document: 'jeton-1' } })
    enregistrerSectionLayout.mockImplementation(async (_id, corps) => ({ data: {
      empreinte_document: 'jeton-2', roof_layout: { zones: [{ ...PLAT, ...corps.champs }] } } }))
    rendre()
    const carte = screen.getByTestId('cal-toit-pente-carte')
    await waitFor(() => expect(within(carte).getByText('Toit plat')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('cal-toit-pente-confirmer'))
    await waitFor(() => expect(within(carte).queryByText('À confirmer')).toBeNull())
    expect(within(carte).getByTestId('cal-toit-plat-confirme')).toHaveTextContent('confirmé')
    expect(screen.queryByTestId('cal-toit-pente-confirmer')).toBeNull()
  })

  it('un plat déjà confirmé (pitchSource plat) : ni pastille ni actions', async () => {
    layout.mockResolvedValue({ data: { roof_layout: { zones: [{ ...PLAT, pitchSource: { mode: 'plat' } }] }, empreinte_document: 'jeton-1' } })
    rendre()
    await waitFor(() => expect(within(screen.getByTestId('cal-toit-pente-carte')).getByText('Toit plat')).toBeInTheDocument())
    expect(screen.queryByText('À confirmer')).toBeNull()
    expect(screen.queryByTestId('cal-toit-pente-confirmer')).toBeNull()
  })
})

describe('Étape Toit — sur la carte', () => {
  it('puce « Surface du toit | Pans | Besoin d’après la facture » : surface et pans du constructeur, besoin servi', async () => {
    rendre()
    const puce = within(surCarte).getByTestId('cal-sur-carte-resume')
    await waitFor(() => expect([...puce.querySelectorAll('.cal-indicateur')].map((n) => n.textContent))
      .toEqual(['Surface du toit107 m²', 'Pans2', "Besoin d'après la facture≈ 6,93 kWc"]))
    expect(cibleFactures).toHaveBeenCalledWith(7)
  })

  it('« Besoin » vient SEULEMENT de `cible_factures.kwc` : jamais la puissance posée/recommandée du constructeur', async () => {
    // Recette M2, calepinage 5 : la reco du constructeur (39,60 kWc, « 809 % ») n'est pas un besoin de facture.
    cibleFactures.mockResolvedValue({ data: { cible_factures: null } })
    rendre()
    $('rp9-reco-kwc').textContent = '39,60 kWc'
    $('rp9-reco-cover').textContent = '809 %'
    await waitFor(() => expect(cibleFactures).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 600))
    const puce = within(surCarte).getByTestId('cal-sur-carte-resume')
    expect([...puce.querySelectorAll('.cal-indicateur')].map((n) => n.textContent)).toEqual(['Surface du toit107 m²', 'Pans2'])
    expect(within(surCarte).queryByText(/39,60/)).toBeNull()
    expect(H.texteBesoin(null)).toBeNull()
    expect(H.texteBesoin({ panneaux: 10, kwc: null })).toBeNull()
    expect(H.texteBesoin({ panneaux: 10, kwc: 7.2 })).toBe('≈ 7,20 kWc')
  })

  it('H2 — lecture de la facture en cours : la puce n’affirme rien ; en échec : « Lecture impossible — réessayer »', async () => {
    let finir
    cibleFactures.mockImplementation(() => new Promise((ok, ko) => { finir = { ok, ko } }))
    rendre()
    const puce = within(surCarte).getByTestId('cal-sur-carte-resume')
    const blocs = () => [...puce.querySelectorAll('.cal-indicateur')].map((n) => n.textContent)
    await waitFor(() => expect(cibleFactures).toHaveBeenCalledTimes(1))
    expect(blocs()).toEqual(['Surface du toit107 m²', 'Pans2']) // en chargement : aucun besoin, aucune absence dite
    await act(async () => { finir.ko(new Error('timeout of 20000ms exceeded')) })
    const reessayer = await within(surCarte).findByRole('button', { name: 'Lecture impossible — réessayer' })
    expect(blocs()[2]).toBe("Besoin d'après la factureLecture impossible — réessayer")
    cibleFactures.mockResolvedValue({ data: { cible_factures: { panneaux: 4, kwc: 2.84, module_wc: 710 } } })
    fireEvent.click(reessayer)
    await waitFor(() => expect(blocs()).toEqual(['Surface du toit107 m²', 'Pans2', "Besoin d'après la facture≈ 2,84 kWc"]))
    expect(cibleFactures).toHaveBeenCalledTimes(2)
  })

  it('H2/H3 — le design-context de l’atelier (`contexte`) prime : aucune seconde lecture ; la taille, lue à part', async () => {
    cibleFactures.mockResolvedValue({ data: { cible_factures: { panneaux: 4, kwc: 2.84, module_wc: 710 } } })
    rendre({ contexte: { calepinage: { lead: 42 } } })
    const puce = within(surCarte).getByTestId('cal-sur-carte-resume')
    await waitFor(() => expect([...puce.querySelectorAll('.cal-indicateur')].map((n) => n.textContent)[2])
      .toBe("Besoin d'après la facture≈ 2,84 kWc"))
    expect(designContext).not.toHaveBeenCalled()
    expect(cibleFactures).toHaveBeenCalledTimes(1)
  })

  it('T4-X7-018 — un tracé à l’échelle du pays : « trop petite pour une rangée » à côté d’une surface vaste = alerte, sans refus', async () => {
    rendre()
    document.querySelectorAll('[data-pan-stat]').forEach((n) => n.remove())
    const statut = document.createElement('p')
    statut.id = 'rp9-status'
    statut.textContent = 'Surface trop petite pour une rangée — élargissez le tracé.'
    document.body.querySelector('.rp9-host').appendChild(statut)
    $('rp9-area-value').textContent = '~120 534 611 780 m²'
    expect(H.traceHorsEchelle(document, H.lireSurface(document))).toBe(true)
    // Une vraie petite surface au même message : aucune alerte d'échelle.
    $('rp9-area-value').textContent = '~3 m²'
    expect(H.traceHorsEchelle(document, H.lireSurface(document))).toBe(false)
    // Surface vaste sans le message du script : aucune alerte.
    $('rp9-area-value').textContent = '~120 534 611 780 m²'
    statut.textContent = 'Calcul prêt.'
    expect(H.traceHorsEchelle(document, H.lireSurface(document))).toBe(false)
  })

  it('T4-X7-018 — tracé hors échelle : aucune surface absurde, la phrase contradictoire masquée, « Poser les panneaux » désactivé avec son motif', async () => {
    rendre({ action: { libelle: 'Poser les panneaux', onClick: vi.fn() } }, (hote) => {
      const statut = document.createElement('p')
      statut.id = 'rp9-status'
      statut.textContent = 'Surface trop petite pour une rangée — élargissez le tracé.'
      hote.appendChild(statut)
      hote.querySelectorAll('[data-pan-stat]').forEach((n) => n.remove())
      hote.querySelector('#rp9-area-value').textContent = '~868 298 030 010 m²'
    })
    const action = await within(pied).findByTestId('cal-action-etape-suivante')
    expect(action).toBeDisabled()
    expect(action).toHaveAttribute('title', expect.stringContaining('Retracez'))
    expect(within(surCarte).queryByText(/868/)).toBeNull() // aucune surface absurde imprimée par l'atelier
    expect(within(surCarte).queryByTestId('cal-sur-carte-resume')).toBeNull()
    await waitFor(() => expect($('rp9-status')).toHaveAttribute('data-contredit', '1'))
    // Le même message avec une vraie petite surface : rien n'est masqué, ni désactivé, la puce garde son chiffre.
    cleanup(); document.body.innerHTML = ''
    rendre({ action: { libelle: 'Poser les panneaux', onClick: vi.fn() } }, (hote) => {
      const statut = document.createElement('p')
      statut.id = 'rp9-status'
      statut.textContent = 'Surface trop petite pour une rangée — élargissez le tracé.'
      hote.appendChild(statut)
      hote.querySelectorAll('[data-pan-stat]').forEach((n) => n.remove())
      hote.querySelector('#rp9-area-value').textContent = '~3 m²'
    })
    expect(within(pied).queryByTestId('cal-action-etape-suivante')).toBeNull()
    expect(within(surCarte).getByTestId('cal-sur-carte-resume')).toBeInTheDocument()
    expect($('rp9-status')).not.toHaveAttribute('data-contredit')
  })

  it('T4-X7-018 — au doigt, l’aide du contour dit « Touchez deux fois », jamais « Double-cliquez »', () => {
    vi.useFakeTimers()
    const ancien = window.matchMedia
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} })
    rendre()
    $('rp9-add-area').disabled = true
    $('rp9-finish').disabled = false
    act(() => { vi.advanceTimersByTime(600) })
    $('rp9-finish').disabled = true
    $('rp9-add-area').disabled = false
    act(() => { vi.advanceTimersByTime(600) })
    expect(within(surCarte).getByText('Glissez un coin pour le déplacer. Touchez deux fois un bord pour ajouter un point.')).toBeInTheDocument()
    window.matchMedia = ancien
  })

  it('sans contour, pas de puce', () => {
    rendre()
    document.querySelectorAll('[data-pan-stat]').forEach((n) => n.remove())
    $('rp9-area-value').textContent = '—'
    expect(H.lireSurface(document)).toBeNull()
  })

  it('barre d’outils : 4 outils | annuler · rétablir | Plan · 3D, dans l’ordre de la maquette', () => {
    rendre()
    const barre = within(surCarte).getByRole('toolbar', { name: 'Outils du plan' })
    expect(barre).toHaveAttribute('data-testid', 'cal-barre-outils-carte')
    expect(within(barre).getAllByRole('button').map((b) => b.getAttribute('aria-label') || b.textContent))
      .toEqual(['Sélectionner', 'Ajouter un pan', 'Ajouter un obstacle', 'Mesurer', 'Annuler', 'Rétablir', 'Plan', '3D'])
    expect(within(barre).getByRole('button', { name: 'Sélectionner' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(barre).getByRole('button', { name: 'Plan' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(barre).getByRole('button', { name: 'Rétablir' })).toBeDisabled()
  })

  // T4-X8-009 — au téléphone (390 px), la barre défile (427 px dans 364) et « 3D » commençait à x = 387 : le choix
  // Plan / 3D passe EN TÊTE de la barre (ordre visuel seul, l'ordre lu reste celui de la maquette), suivi de son filet ;
  // les autres outils peuvent défiler. jsdom n'évalue pas les @media : les règles du bloc téléphone sont posées seules.
  it('T4-X8-009 — téléphone : Plan / 3D en tête de la barre, jamais coupé au bord droit', () => {
    const source = document.createElement('style')
    source.textContent = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/56-coque-responsive.css'), 'utf8')
    document.head.appendChild(source)
    const telephone = [...source.sheet.cssRules].filter((r) => r.media && r.media.mediaText === '(max-width: 639px)')
      .flatMap((r) => [...r.cssRules].map((x) => x.cssText))
    source.remove()
    const style = document.createElement('style')
    style.textContent = telephone.join(' ')
    document.head.appendChild(style)
    try {
      rendre()
      const barre = within(surCarte).getByRole('toolbar', { name: 'Outils du plan' })
      const ordre = (el) => Number(getComputedStyle(el).order || 0)
      const vue = within(barre).getByRole('group', { name: 'Vue' })
      const filets = [...barre.querySelectorAll('.cal-barre-outils-separateur')]
      const outils = within(barre).getAllByRole('button').filter((b) => !vue.contains(b))
      expect(getComputedStyle(vue).flexShrink).toBe('0')
      for (const b of outils) expect(ordre(vue)).toBeLessThan(ordre(b))
      expect(ordre(vue)).toBeLessThan(ordre(filets[filets.length - 1]))
      for (const b of outils) expect(ordre(filets[filets.length - 1])).toBeLessThan(ordre(b))
    } finally { style.remove() }
  })

  it('chaque outil clique le VRAI contrôle du constructeur', async () => {
    rendre()
    const barre = within(surCarte).getByRole('toolbar')
    const espion = (id) => { const f = vi.fn(); $(id).addEventListener('click', f); return f }
    const obstacle = espion('rp9-obstacle')
    const zone = espion('rp9-add-area')
    const mesure = espion('rp9-mesure-distance')
    fireEvent.click(within(barre).getByRole('button', { name: 'Ajouter un obstacle' }))
    fireEvent.click(within(barre).getByRole('button', { name: 'Ajouter un pan' }))
    fireEvent.click(within(barre).getByRole('button', { name: 'Mesurer' }))
    expect([obstacle, zone, mesure].map((f) => f.mock.calls.length)).toEqual([1, 1, 1])
    // Pendant un tracé, « Annuler » retire le dernier point ; sinon l'historique de pose.
    const point = espion('rp9-undo-point')
    $('rp9-undo-point').hidden = false
    await waitFor(() => expect(within(barre).getByRole('button', { name: 'Annuler' })).not.toBeDisabled())
    fireEvent.click(within(barre).getByRole('button', { name: 'Annuler' }))
    expect(point).toHaveBeenCalledTimes(1)
    fireEvent.click(within(barre).getByRole('button', { name: '3D' }))
    expect(builderApi.appliquerVue).toHaveBeenCalledWith('trois-quarts')
  })

  it('la bulle « Contour tracé » paraît quand un tracé EN COURS se ferme, puis s’efface', () => {
    vi.useFakeTimers()
    rendre()
    $('rp9-add-area').disabled = true
    $('rp9-finish').disabled = false
    act(() => { vi.advanceTimersByTime(600) })
    expect(within(surCarte).queryByText('Contour tracé')).toBeNull()
    $('rp9-finish').disabled = true
    $('rp9-add-area').disabled = false
    act(() => { vi.advanceTimersByTime(600) })
    expect(within(surCarte).getByText('Contour tracé')).toBeInTheDocument()
    expect(within(surCarte).getByText('Glissez un coin pour le déplacer. Double-cliquez un bord pour ajouter un point.')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(9000) })
    expect(within(surCarte).queryByText('Contour tracé')).toBeNull()
  })

  it('l’étape s’ouvre en « Plan » : la caméra du dessus est posée à l’entrée', () => {
    vi.useFakeTimers()
    rendre()
    act(() => { vi.advanceTimersByTime(10) })
    expect(builderApi.appliquerVue).toHaveBeenCalledWith('dessus')
    expect(builderApi.appliquerVue).not.toHaveBeenCalledWith('trois-quarts')
  })
})

/* ACAL1445 — l'étape Toit face à Main / ToitSombre : bulle de consigne tant qu'aucun coin n'est déplacé, bloc « Soleil »
   à côté de la barre d'outils, boussole sous la pile de zoom, « Je ne la connais pas » sur une ligne. */
describe('ACAL1445 — bulle, bloc Soleil, boussole', () => {
  const SOLEIL = '<input id="rp9-sun-date" type="date" value="2028-06-21"><input id="rp9-sun-hour" type="range" min="6" max="18" value="14">'
  let style
  beforeEach(() => {
    style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css', '51-etape-toit.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove() })

  it('un toit déjà tracé s’ouvre avec la bulle « Contour tracé » ; un coin déplacé (historique actif) la retire', () => {
    vi.useFakeTimers()
    rendre()
    expect(within(surCarte).getByText('Contour tracé')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(20000) }) // pas de minuteur : elle reste tant que rien n'est déplacé
    expect(within(surCarte).getByText('Contour tracé')).toBeInTheDocument()
    $('rp9-layout-undo').disabled = false // le moteur a gardé le déplacement d'un coin
    act(() => { vi.advanceTimersByTime(600) })
    expect(within(surCarte).queryByText('Contour tracé')).toBeNull()
    $('rp9-layout-undo').disabled = true // annuler jusqu'au début ne la ramène pas : le coin a bien été déplacé
    act(() => { vi.advanceTimersByTime(600) })
    expect(within(surCarte).queryByText('Contour tracé')).toBeNull()
  })

  it('sans contour fermé, pas de bulle', () => {
    rendre({}, (hote) => hote.querySelector('#rp9-add-area').remove())
    expect(within(surCarte).queryByText('Contour tracé')).toBeNull()
  })

  it('bloc « Soleil » : le jour et l’heure du soleil du constructeur, jamais inventés', () => {
    rendre({}, (hote) => { hote.insertAdjacentHTML('beforeend', SOLEIL) })
    const bloc = within(surCarte).getByTestId('cal-toit-soleil')
    expect(bloc).toHaveTextContent('Soleil21 juin · 14 h')
    expect(bloc).toHaveAttribute('aria-label', 'Soleil : 21 juin · 14 h')
    expect(bloc.tagName).not.toBe('BUTTON') // un repère, pas un contrôle de plus : l'heure se règle à l'étape Panneaux
    cleanup(); document.body.innerHTML = ''
    rendre() // le constructeur ne donne ni date ni heure : le bloc n'affirme rien
    expect(within(surCarte).queryByTestId('cal-toit-soleil')).toBeNull()
  })

  it('boussole : sous la pile de zoom, rien d’autre à cacher en Guidé sur cette étape', () => {
    rendre({}, (hote) => hote.insertAdjacentHTML('beforeend', '<div id="rp9-compass" class="rp9-compass"><div class="rp9-compass-arrow"><span>N</span><span>S</span></div></div>'))
    expect(getComputedStyle($('rp9-compass')).display).not.toBe('none')
  })

  it('« Je ne la connais pas » tient sur une ligne', () => {
    rendre()
    const bouton = screen.getByTestId('cal-toit-pente-inconnue')
    expect(getComputedStyle(bouton).whiteSpace).toBe('nowrap')
  })
})

/* ACAL1827 — l'étape Toit à sa maquette v2 (Main) : compte des obstacles, carte de pente avec son cadran, « Confirmer » et
   « Je ne la connais pas » côte à côte, champs de dimensions et lignes d'obstacles aux mesures de la maquette. */
describe('ACAL1827 — l’étape Toit à sa maquette v2', () => {
  let style
  beforeEach(() => {
    style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css', '51-etape-toit.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove() })
  const cs = (el) => getComputedStyle(el)

  it('l’en-tête des obstacles porte leur nombre ; sans obstacle, l’en-tête seul', () => {
    rendre()
    const tete = within(screen.getByTestId('cal-toit-obstacles')).getByRole('heading', { level: 2 })
    expect(tete).toHaveTextContent('Obstacles · 2')
    cleanup(); document.body.innerHTML = ''
    rendre({}, (hote) => hote.querySelectorAll('#rp9-objets-site li').forEach((n) => n.remove()))
    expect(within(screen.getByTestId('cal-toit-obstacles')).getByRole('heading', { level: 2 })).toHaveTextContent(/^Obstacles$/)
  })

  it('la carte de pente porte un cadran dont l’aiguille suit la face lue ; sans face lue, pas d’aiguille', async () => {
    rendre()
    const carte = screen.getByTestId('cal-toit-pente-carte')
    const cadran = await within(carte).findByRole('img', { name: 'Face sud, 180°' })
    expect(cadran.querySelector('[data-aiguille]')).toHaveAttribute('transform', 'rotate(180 32 32)')
    cleanup(); document.body.innerHTML = ''
    builderApi = { panActifId: () => 'area-9', appliquerVue: vi.fn() }
    rendre({}, (hote) => { hote.querySelector('#rp9-facing-value').textContent = '' })
    await waitFor(() => expect(screen.getByTestId('cal-toit-pente-carte')).toHaveTextContent('22°'))
    expect(within(screen.getByTestId('cal-toit-pente-carte')).queryByRole('img')?.querySelector('[data-aiguille]') ?? null).toBeNull()
  })

  it('« Confirmer » et « Je ne la connais pas » : deux colonnes 1:1, hors de la carte crème', async () => {
    rendre()
    const confirmer = await screen.findByTestId('cal-toit-pente-confirmer')
    const inconnue = screen.getByTestId('cal-toit-pente-inconnue')
    const actions = confirmer.parentElement
    expect(inconnue.parentElement).toBe(actions)
    expect(cs(actions).display).toBe('grid')
    expect(cs(actions).gridTemplateColumns).toBe('repeat(2, minmax(0, 1fr))')
    expect(actions.closest('.cal-toit-pente-cadre')).toBeNull() // les boutons sont sous la carte crème, pas dedans
    expect(cs(confirmer).height).toBe('44px')
    expect(cs(inconnue).height).toBe('44px')
    expect(cs(inconnue).borderRadius).toBe('var(--cal-rayon-bouton)')
  })

  it('intitulés de section 13 px demi-gras en texte 2 ; champs de dimensions 44 px, rayon 10, fond des jetons', () => {
    rendre()
    const titre = document.querySelector('.cal-etape-toit .cal-section-etape-tete h2')
    expect(cs(titre).fontSize).toBe('0.8125rem')
    expect(cs(titre).color).toBe('var(--cal-texte-2)')
    const champ = document.querySelector('.cal-toit-saisie')
    expect(cs(champ).height).toBe('44px')
    expect(cs(champ).borderRadius).toBe('10px')
    expect(cs(champ).background).toBe('var(--cal-surface)')
    expect(cs(document.querySelector('.cal-toit-champ > label')).color).toBe('var(--cal-texte-3)')
  })

  it('« Modifier la pente » se lit sur la ligne de l’intitulé et ne prend aucune ligne de plus tant qu’elle est fermée', async () => {
    rendre()
    const resume = await screen.findByText('Modifier la pente')
    expect(cs(resume).position).toBe('absolute')
    expect(cs(resume.closest('details')).marginTop).toBe('-10px')
  })

  it('lignes d’obstacles de 40 px dans un cadre de rayon 12, nom 14 px, cotes 13 px en texte 3', () => {
    rendre()
    const ligne = document.querySelector('.cal-toit-obstacles > li')
    expect(cs(ligne).minHeight).toBe('40px')
    expect(cs(document.querySelector('.cal-toit-obstacles')).borderRadius).toBe('var(--cal-rayon-tuile)')
    const cotes = document.querySelector('.cal-toit-obstacle-cotes')
    expect(cs(cotes).fontSize).toBe('0.8125rem')
    expect(cs(cotes).color).toBe('var(--cal-texte-3)')
  })
})

/* Le script, réduit à ce que fait « + Ajouter une zone » (`addArea`) : une zone vide ACTIVE (« à tracer »), le
   pan d'avant passe en « Voir », le bouton se désactive ; « × » la supprime, « Voir » réactive un pan. */
function scriptZones(hote) {
  const liste = hote.querySelector('#rp9-areas-list')
  const ligne = (id, actif, aTracer) => `<li data-area-row="${id}">${id} — ${aTracer ? '— panneaux · à tracer' : '30 panneaux · 21,6 kWc'}
    ${actif ? '<span>● active</span>' : `<button data-area-select="${id}">Voir</button>`}<button data-area-del="${id}">×</button></li>`
  const etat = { zones: [{ id: 'area-1', aTracer: false }], active: 'area-1' }
  const peindre = () => { liste.innerHTML = etat.zones.map((z) => ligne(z.id, z.id === etat.active, z.aTracer)).join('') }
  peindre()
  hote.querySelectorAll('[data-pan-stat="area-2"]').forEach((n) => n.remove())
  const ajouter = hote.querySelector('#rp9-add-area')
  ajouter.addEventListener('click', () => {
    etat.zones.push({ id: 'area-2', aTracer: true })
    etat.active = 'area-2'
    ajouter.disabled = true
    hote.querySelector('#rp9-area-value').textContent = '—'
    hote.querySelector('#rp9-reco-kwc').textContent = '—'
    hote.querySelector('#rp9-pan-geometry').hidden = true
    peindre()
  })
  liste.addEventListener('click', (e) => {
    const del = e.target.closest('[data-area-del]')?.dataset.areaDel
    const voir = e.target.closest('[data-area-select]')?.dataset.areaSelect
    if (del) { etat.zones = etat.zones.filter((z) => z.id !== del); etat.active = etat.zones[0].id; ajouter.disabled = false }
    if (voir) etat.active = voir
    hote.querySelector('#rp9-area-value').textContent = '~54 m²'
    peindre()
  })
  return { etat, fermerZone2: () => { etat.zones[1].aTracer = false; ajouter.disabled = false; peindre() } }
}

describe('Étape Toit — « Ajouter un pan » sur un toit existant (jamais destructif)', () => {
  it('le bouton dit ce qu’il fait ; pendant l’ajout la puce et les cotes gardent le toit ; Échap retire la zone vide', async () => {
    let script
    rendre({}, (hote) => { script = scriptZones(hote) })
    const barre = within(surCarte).getByRole('toolbar')
    const puce = () => [...within(surCarte).getByTestId('cal-sur-carte-resume').querySelectorAll('.cal-indicateur')].map((n) => n.textContent)
    await waitFor(() => expect(puce()).toEqual(['Surface du toit54 m²', 'Pans1', 'Besoin d\'après la facture≈ 6,93 kWc']))
    fireEvent.click(within(barre).getByRole('button', { name: 'Ajouter un pan' }))
    expect(script.etat.zones.map((z) => z.id)).toEqual(['area-1', 'area-2'])
    await waitFor(() => expect(within(barre).getByRole('button', { name: 'Ajouter un pan' })).toHaveAttribute('aria-pressed', 'true'))
    expect(within(surCarte).getByText('Nouveau pan')).toBeInTheDocument()
    expect(puce()).toEqual(['Surface du toit54 m²', 'Pans1', 'Besoin d\'après la facture≈ 6,93 kWc'])
    expect(screen.getByLabelText('Longueur')).toHaveValue('12,4')
    expect(screen.getByLabelText('Longueur')).toBeDisabled()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(script.etat.zones.map((z) => z.id)).toEqual(['area-1'])
    expect(script.etat.active).toBe('area-1')
    await waitFor(() => expect(within(barre).getByRole('button', { name: 'Ajouter un pan' })).toHaveAttribute('aria-pressed', 'false'))
    expect(within(surCarte).queryByText('Nouveau pan')).toBeNull()
  })

  it('ACAL1329 — outil de tracé : nom selon la présence d’un toit ; l’ajout n’écrit rien avant le dernier point', async () => {
    rendre({}, (hote) => { hote.querySelector('#rp9-add-area').disabled = true }) // aucun toit fermé
    const barre = within(surCarte).getByRole('toolbar')
    expect(within(barre).getByRole('button', { name: 'Tracer un contour' })).toBeInTheDocument()
    expect(within(barre).queryByRole('button', { name: 'Ajouter un pan' })).toBeNull()
    cleanup(); document.body.innerHTML = ''
    let script
    rendre({}, (hote) => { script = scriptZones(hote) }) // un toit enregistré
    const bouton = () => within(surCarte).getByRole('button', { name: 'Ajouter un pan' })
    fireEvent.click(bouton())
    await waitFor(() => expect(bouton()).toHaveAttribute('aria-pressed', 'true'))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(script.etat.zones.map((z) => z.id)).toEqual(['area-1'])
    // L'écran n'écrit jamais lui-même : ni section, ni document, pendant l'ajout ni à son annulation.
    expect(enregistrerSectionLayout).not.toHaveBeenCalled()
  })

  it('re-cliquer annule aussi ; un contour fermé termine l’ajout et garde le nouveau pan', async () => {
    let script
    rendre({}, (hote) => { script = scriptZones(hote) })
    const bouton = () => within(surCarte).getByRole('button', { name: 'Ajouter un pan' })
    fireEvent.click(bouton())
    await waitFor(() => expect(bouton()).toHaveAttribute('aria-pressed', 'true'))
    fireEvent.click(bouton())
    expect(script.etat.zones.map((z) => z.id)).toEqual(['area-1'])
    fireEvent.click(bouton())
    await waitFor(() => expect(bouton()).toHaveAttribute('aria-pressed', 'true'))
    script.fermerZone2()
    await waitFor(() => expect(bouton()).toHaveAttribute('aria-pressed', 'false'), { timeout: 3000 })
    expect(script.etat.zones.map((z) => z.id)).toEqual(['area-1', 'area-2'])
  })
})

describe('Étape Toit — Dimensions renvoyées au constructeur', () => {
  it('contour fermé : la saisie reste sous le curseur, puis part dans les cotes du pan (« Appliquer les cotes »)', () => {
    rendre()
    const coter = vi.fn()
    $('rp9-pan-coter').addEventListener('click', coter)
    const longueur = screen.getByLabelText('Longueur')
    fireEvent.change(longueur, { target: { value: '12,5' } })
    expect(longueur).toHaveValue('12,5')
    fireEvent.blur(longueur)
    expect($('rp9-pan-longueur').value).toBe('12,5')
    expect($('rp9-pan-largeur').value).toBe('8,6')
    expect(coter).toHaveBeenCalledTimes(1)
  })

  it('avant tout contour : Entrée soumet « Créer le toit » du script avec longueur × largeur', () => {
    rendre({}, (hote) => {
      hote.querySelector('#rp9-toit-cotes').hidden = false
      hote.querySelector('#rp9-pan-geometry').hidden = true
    })
    const soumis = vi.fn((e) => e.preventDefault())
    $('rp9-toit-cotes').addEventListener('submit', soumis)
    expect(screen.getByRole('button', { name: 'Créer le toit' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Longueur'), { target: { value: '12,5' } })
    fireEvent.change(screen.getByLabelText('Largeur'), { target: { value: '8' } })
    fireEvent.submit(screen.getByTestId('cal-toit-dimensions'))
    expect(soumis).toHaveBeenCalledTimes(1)
    const form = $('rp9-toit-cotes')
    expect([form.querySelector('[name=longueur]').value, form.querySelector('[name=largeur]').value]).toEqual(['12,5', '8'])
    expect(screen.getByLabelText('Longueur')).toHaveValue('12,5')
  })
})

describe('Étape Toit — budget de contrôles et thème', () => {
  it('contrôles visibles de l’écran (panneau + calques de carte) : 13 (sélecteur de calepinage-mesures-ecran)', () => {
    rendre()
    const SEL = 'button, a[href], input, select, textarea, [role=tab]'
    const panneau = [...document.querySelectorAll('.cal-etape-toit')].flatMap((n) => [...n.querySelectorAll(SEL)])
    const carte = [...surCarte.querySelectorAll(SEL)]
    // Panneau : Longueur, Largeur, Confirmer, Je ne la connais pas, + Ajouter (les lignes d'obstacles sont des
    // options d'une liste à UNE tabulation ; « Modifier la pente » est un <summary>). Carte : 8 de la barre.
    expect(panneau.length).toBe(5)
    expect(carte.length).toBe(8)
  })

  it('51-etape-toit.css : aucune couleur littérale, toutes les couleurs passent par les jetons', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/51-etape-toit.css'), 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/url\("data:[^"]*"\)/g, 'url()') // masques des pictogrammes MapLibre : forme seule, jamais une couleur
    expect(css).not.toMatch(/rgba?\(|hsla?\(|#[0-9a-fA-F]{3,8}\b/)
    expect(css).not.toMatch(/:\s*(white|black|gray|grey)\b/i)
    expect(css).not.toMatch(/\.dark\b/)
  })

  it('six tuiles de forme illustrées en guidé (Plat, 2 pans, 4 pans, En L, En T, Tracé libre) ; « 1 pan » masqué', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/51-etape-toit.css'), 'utf8')
    for (const forme of ['flat', 'gable', 'hip', 'l_gable', 't_gable', 'libre']) {
      expect(css.includes(`[data-forme='${forme}'] { --cal-forme: url("data:image/svg+xml,`), forme).toBe(true)
    }
    expect(css).toContain("#rp9-formes-toit > [data-forme='shed']")
    expect(css).toContain('grid-template-columns: repeat(3, minmax(0, 1fr))')
  })
})

/* ACAL1803 — la tête et le pied v2 du panneau d'étape : cinq traits (fait / actif / à venir lus du parcours servi),
   « Étape n sur 5 » 12 px, titre Archivo 24 px, bouton d'étape 52 px rayon 14 en 15 px graisse 700 à ombre dorée.
   Le panneau est RENDU ; la feuille 49 + 50 est chargée dans le DOM de test et lue par getComputedStyle. */
describe('ACAL1803 — tête et pied du panneau d’étape (maquettes v2)', () => {
  let style
  beforeEach(() => {
    style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove(); cleanup() })

  it('le panneau d’étape rend cinq traits, l’actif au rang de l’étape, les faits lus du parcours', async () => {
    const { default: PanneauEtape } = await import('../PanneauEtape')
    const { BoutonOr } = await import('../primitives')
    render(
      <div className="rp9-host cal-coque">
        <PanneauEtape numero={2} total={5} titre="Les panneaux" etats={{ toit: 'fait', panneaux: 'en_cours' }}
          pied={<BoutonOr plein fleche>Raccorder les panneaux</BoutonOr>} />
      </div>,
    )
    const traits = [...screen.getByTestId('cal-progression-etapes').children]
    expect(traits.map((t) => t.getAttribute('data-etat'))).toEqual(['fait', 'actif', 'a-venir', 'a-venir', 'a-venir'])
    expect(screen.getByTestId('cal-progression-etapes')).toHaveAttribute('aria-hidden', 'true')
    const cs = (el) => getComputedStyle(el)
    // ACAL2003 — seul le trait de l'étape COURANTE est doré ; les faites sont neutres soutenues, les autres claires.
    expect(cs(traits[0]).background).toContain('--cal-progression-faite')
    expect(cs(traits[1]).background).toContain('--cal-action')
    expect(cs(traits[2]).background).toContain('--cal-progression-a-venir')
    expect(traits.map((t) => cs(t).background.includes('--cal-action'))).toEqual([false, true, false, false, false])
    expect(cs(traits[0]).height).toBe('4px')
    const rang = screen.getByText('Étape 2 sur 5')
    expect(cs(rang).fontSize).toBe('0.75rem')
    const titre = screen.getByTestId('cal-panneau-etape-titre')
    expect(titre).toHaveTextContent('Les panneaux')
    expect(cs(titre).fontSize).toBe('1.5rem')
    expect(cs(titre).fontFamily).toBe('var(--cal-police-titre)') // ACAL1941 — Archivo en tête (49-jetons-v2.css)
    const bouton = screen.getByRole('button', { name: 'Raccorder les panneaux' })
    expect(cs(bouton).height).toBe('52px')
    expect(cs(bouton).borderRadius).toBe('var(--cal-rayon-pile)')
    expect(cs(bouton).fontSize).toBe('0.9375rem')
    expect(cs(bouton).fontWeight).toBe('700')
    expect(cs(bouton).boxShadow).toBe('var(--cal-action-ombre)')
  })

  it('ACAL2003 — aux cinq étapes, un seul trait est doré : celui de l’étape courante', async () => {
    const { default: PanneauEtape } = await import('../PanneauEtape')
    const { ETAPES } = await import('../../parcoursGuide')
    const etats = Object.fromEntries(ETAPES.map((e) => [e.cle, 'fait']))
    for (let n = 1; n <= 5; n += 1) {
      const { unmount } = render(
        <div className="rp9-host cal-coque"><PanneauEtape numero={n} total={5} titre="x" etats={etats} /></div>,
      )
      const dores = [...screen.getByTestId('cal-progression-etapes').children]
        .map((t) => getComputedStyle(t).background.includes('--cal-action'))
      expect(dores.filter(Boolean)).toHaveLength(1)
      expect(dores[n - 1]).toBe(true)
      unmount()
    }
  })

  it('panneau caché ou tiroir (tablette) : aucun trait — la tablette garde sa tête actuelle', async () => {
    const { default: PanneauEtape } = await import('../PanneauEtape')
    const { rerender } = render(<PanneauEtape numero={1} titre="Le toit" tiroir />)
    expect(screen.queryByTestId('cal-progression-etapes')).toBeNull()
    rerender(<PanneauEtape numero={1} titre="Le toit" cache />)
    expect(screen.queryByTestId('cal-progression-etapes')).toBeNull()
  })
})

/* ACAL2001 — un message ne cache jamais le bouton d'action : tant que l'atelier est monté, le Toaster de l'ERP
   (bas droite) se pose à gauche du panneau d'étape. Le crochet est RENDU, la feuille 50 est chargée dans le DOM de
   test et lue par getComputedStyle sur une région sonner posée comme sonner la pose. */
describe('ACAL2001 — les messages se posent hors du bouton d’étape', () => {
  let style
  beforeEach(() => {
    style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove(); cleanup() })

  function regionToasts(position = ['bottom', 'right']) {
    const ol = document.createElement('ol')
    ol.setAttribute('data-sonner-toaster', 'true')
    ol.setAttribute('data-y-position', position[0])
    ol.setAttribute('data-x-position', position[1])
    document.body.appendChild(ol)
    return ol
  }

  it('dans l’atelier, la région des messages quitte le coin du bouton ; hors atelier rien ne change', async () => {
    const { useToastsHorsDuBouton } = await import('../toastsAtelier')
    function Atelier() { useToastsHorsDuBouton(); return null }
    const ol = regionToasts()
    expect(getComputedStyle(ol).right).not.toBe('var(--cal-toast-droite)')
    const { unmount } = render(<Atelier />)
    expect(document.body).toHaveAttribute('data-cal-atelier', '1')
    expect(getComputedStyle(ol).right).toBe('var(--cal-toast-droite)')
    expect(getComputedStyle(ol).bottom).toBe('var(--cal-toast-bas)')
    expect(getComputedStyle(document.body).getPropertyValue('--cal-toast-droite')).toBe('416px')
    unmount()
    expect(document.body).not.toHaveAttribute('data-cal-atelier')
    expect(getComputedStyle(ol).right).not.toBe('var(--cal-toast-droite)')
    ol.remove()
  })

  /* T3-VAGUEC (S3) — au bureau le message du bas (356 × 54) tombait à 16 px du bord, sur la moitié droite de la barre du soleil
     et de la barre d'outils (rangée de 69 px depuis le bord). Il se pose au-dessus de cette rangée, avec un jeu de 8 px. */
  it('au bureau, la région des messages est relevée au-dessus de la barre du soleil et de la barre d’outils', async () => {
    const { useToastsHorsDuBouton } = await import('../toastsAtelier')
    function Atelier() { useToastsHorsDuBouton(); return null }
    render(<Atelier />)
    const bas = parseFloat(getComputedStyle(document.body).getPropertyValue('--cal-toast-bas'))
    expect(bas).toBeGreaterThanOrEqual(69 + 8 + 16) // rangée du bas (69) + jeu (8) + marge de la région au bord (16)
  })

  it('une région en haut (téléphone) n’est pas déplacée', async () => {
    const { useToastsHorsDuBouton } = await import('../toastsAtelier')
    function Atelier() { useToastsHorsDuBouton(); return null }
    const ol = regionToasts(['top', 'center'])
    render(<Atelier />)
    expect(getComputedStyle(ol).right).not.toBe('var(--cal-toast-droite)')
    ol.remove()
  })
})

/* T3-VAGUEC (S3) — « Affiner ma consommation » : le panneau d'étape ne fait que 384 px, mais les quatre tuiles chiffrées du
   bandeau de synthèse suivaient `sm:grid-cols-4`, réglé sur la FENÊTRE (≥ 640 px) : quatre colonnes de ~78 px, libellés et
   montants superposés. Le vrai balisage partagé est rendu sous `.rp9-host` avec la règle Tailwind d'origine (posée sans sa
   requête de média, que jsdom n'évalue pas) et la feuille du constructeur : le bandeau passe à deux colonnes. */
describe('« Affiner ma consommation » — les quatre tuiles chiffrées ne se chevauchent pas', () => {
  let style
  let hote
  beforeEach(async () => {
    const { CONS_WINDOW_HTML } = await import('@roofpro/consumptionMarkup')
    style = document.createElement('style')
    style.textContent = `.sm\\:grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }\n${
      readFileSync(resolve(process.cwd(), 'src/styles/roofbuilder.css'), 'utf8')}`
    document.head.appendChild(style)
    hote = document.createElement('div')
    hote.className = 'rp9-host'
    hote.innerHTML = CONS_WINDOW_HTML
    document.body.appendChild(hote)
  })
  afterEach(() => { style.remove(); hote.remove() })

  it('le bandeau de synthèse tient en deux colonnes dans le panneau, ses quatre tuiles y sont toutes', () => {
    const bandeau = hote.querySelector('#rp9-cons-panel > dl')
    expect(bandeau.children).toHaveLength(4)
    expect(getComputedStyle(bandeau).getPropertyValue('grid-template-columns').trim()).toMatch(/^repeat\(2,/)
    for (const libelle of bandeau.querySelectorAll('dt')) expect(getComputedStyle(libelle).overflowWrap).toBe('anywhere')
  })
})

/* ACAL1904 — la carte d'adresse (#rp9-search) du calepinage sans toit : la pile de zoom reste libre, un clic de tracé hors
   des champs passe à la carte, la carte ne tient que la hauteur d'un champ tant qu'on n'écrit pas. Le composant de la
   carte est RENDU ; les feuilles 49 + 50 sont chargées dans le DOM de test et lues par getComputedStyle. */
describe('ACAL1904 — carte d’adresse sans toit', () => {
  let style
  beforeEach(() => {
    style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css']
      .map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove() })
  const cs = (el) => getComputedStyle(el)

  async function rendreCarte() {
    const { default: BuilderCarte } = await import('../../BuilderCarte.jsx')
    const hote = document.createElement('div')
    hote.className = 'rp9-host cal-coque'
    hote.dataset.avance = '0'
    hote.dataset.sansToit = '1'
    const scene = document.createElement('div')
    scene.className = 'cal-coque-scene'
    hote.appendChild(scene)
    document.body.appendChild(hote)
    render(<BuilderCarte chipClass="rp9-chip" inputClass="rp9-input" mapWrapRef={{ current: null }}
      basculerPleinEcran3d={() => {}} contourClientBrut={null} photoToit={null} photoToitVisible={false}
      pleinEcran3d={false} toitClientVisible={false} />, { container: scene })
    // Ce que le moteur de dessin ajoute à côté du champ (mapDraw.ts : notes de pays et de source, champs « Date de la photo »).
    const parent = document.getElementById('rp9-address').parentElement
    parent.insertAdjacentHTML('beforeend', '<span id="rp9-geocode-country" class="rp9-geocode-country">Recherche limitée au pays : MA</span>'
      + '<span id="rp9-image-source" class="rp9-image-source">Source</span>'
      + '<label class="rp9-image-capture">Date de la photo <input id="rp9-image-date"></label>')
    hote.insertAdjacentHTML('beforeend', '<div class="maplibregl-ctrl-top-right"><div class="maplibregl-ctrl maplibregl-ctrl-group"><button class="maplibregl-ctrl-zoom-in"></button></div></div>')
    return document.getElementById('rp9-search')
  }

  it('la carte laisse la pile de zoom libre : elle s’arrête avant elle, à la largeur d’une pile + sa marge', async () => {
    const carte = await rendreCarte()
    const pile = document.querySelector('.maplibregl-ctrl-top-right')
    const droiteCarte = parseFloat(cs(carte).right)
    const largeurZoom = parseFloat(cs(pile.querySelector('button')).width)
    expect(cs(carte).position).toBe('absolute')
    expect(largeurZoom).toBe(44)
    expect(droiteCarte).toBeGreaterThanOrEqual(parseFloat(cs(pile).right) + largeurZoom)
  })

  // T4-X5-017 — plein écran : la pile zoom / plein écran / boussole restait décalée de la largeur du panneau d'étape
  // (au milieu de l'écran, x ≈ 985 sur 1 440) alors qu'aucune pièce ne couvre plus la carte.
  it('T4-X5-017 — en plein écran, la pile de la carte suit le bord de l’écran (16 px), plus la place du panneau', async () => {
    // jsdom n'évalue pas les @media : on applique, par le CSSOM, les règles du BUREAU (≥ 640 px, sans borne haute),
    // comme sur l'écran de 1 440 px du constat.
    const source = document.createElement('style')
    source.textContent = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/56-coque-responsive.css'), 'utf8')
    document.head.appendChild(source)
    const bureau = [...source.sheet.cssRules].filter((r) => r.media && /min-width: 640px/.test(r.media.mediaText)
      && !/max-width/.test(r.media.mediaText)).flatMap((r) => [...r.cssRules].map((x) => x.cssText))
    source.remove()
    const responsive = document.createElement('style')
    responsive.textContent = bureau.join('\n')
    document.head.appendChild(responsive)
    // T4-X5-017 (rejeu X9) — la boussole de l'étape Panneaux (52-etape-panneaux.css) restait à la place du panneau.
    const panneaux = document.createElement('style')
    panneaux.textContent = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/52-etape-panneaux.css'), 'utf8')
    document.head.insertBefore(panneaux, responsive)
    try {
      await rendreCarte()
      document.querySelector('.cal-coque').dataset.etape = 'panneaux'
      const enveloppe = document.querySelector('[data-testid="rp9-map-wrap"]')
      enveloppe.setAttribute('data-plein-ecran', '1')
      document.getElementById('rp9-map').insertAdjacentHTML('beforeend', '<div class="maplibregl-ctrl-top-right" data-test="dans-la-carte"></div>')
      const pile = document.querySelector('[data-test="dans-la-carte"]')
      expect(cs(pile).right).toBe('16px')
      expect(cs(pile).top).toBe('16px')
      const boussole = document.getElementById('rp9-compass')
      expect(boussole.closest('[data-testid="rp9-map-wrap"]')).toBe(enveloppe) // même conteneur que la pile
      expect(cs(boussole).right).toBe('16px')
      // Le recadrage tardif de l'entrée d'étape ne compte plus les pièces : aucune ne couvre une carte en plein écran.
      const { margesCouvertes } = await import('../cadrageZoneLibre')
      expect(margesCouvertes(document)).toEqual({ haut: 0, bas: 0, gauche: 0, droite: 0 })
    } finally {
      responsive.remove()
      panneaux.remove()
    }
  })

  it('un clic hors des champs traverse la carte ; les champs, le bouton et les suggestions le reçoivent', async () => {
    const carte = await rendreCarte()
    expect(cs(carte).pointerEvents).toBe('none')
    for (const el of [document.getElementById('rp9-address'), carte.querySelector('button[type="submit"]'),
      document.getElementById('rp9-image-date'), document.getElementById('rp9-suggestions')]) {
      expect(cs(el).pointerEvents).toBe('auto')
    }
  })

  it('au repos la carte ne tient que la hauteur d’un champ ; elle ne déplie notes et date que pendant la saisie', async () => {
    const carte = await rendreCarte()
    expect(parseFloat(cs(carte).paddingTop)).toBeLessThanOrEqual(8)
    for (const id of ['rp9-geocode-country', 'rp9-image-source']) expect(cs(document.getElementById(id)).display).toBe('none')
    expect(cs(document.querySelector('.rp9-image-capture')).display).toBe('none')
  })

  it('pendant la saisie (le focus est dans la carte), les notes et les champs de la date se déplient', async () => {
    await rendreCarte()
    document.getElementById('rp9-address').focus() // (lu AVANT toute autre lecture : jsdom garde le style calculé jusqu'à une mutation)
    expect(cs(document.getElementById('rp9-geocode-country')).display).toBe('block')
    expect(cs(document.getElementById('rp9-image-source')).display).toBe('block')
    expect(cs(document.querySelector('.rp9-image-capture')).display).toBe('block')
  })
})

/* ACAL1907 — rien de la carte ne dépasse ni ne se cache. Mesurable sans navigateur : la hauteur de la bande d'alertes publiée
   sur la coque (le composant est RENDU), les règles de la feuille lues par getComputedStyle (jsdom n'évalue pas les @media : celles-ci
   sont lues sur les règles ANALYSÉES). Non mesurable sans navigateur : la place réelle des pièces à l'écran (voir le rapport). */
describe('ACAL1907 — pièces de la carte', () => {
  let style
  const feuilles = ['49-jetons-v2.css', '50-coque-atelier.css', '56-coque-responsive.css']
  beforeEach(() => {
    style = document.createElement('style')
    style.textContent = feuilles.map((f) => readFileSync(resolve(process.cwd(), `src/styles/calepinage/${f}`), 'utf8')).join('\n')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove() })
  const regleMedia = (media, hote) => [...style.sheet.cssRules]
    .filter((r) => r.type === 4 && r.media.mediaText.includes(media))
    .flatMap((m) => [...m.cssRules]).filter((r) => r.selectorText && hote.matches(r.selectorText))

  it('la pile de zoom suit la bande d’alertes : sa hauteur (+ l’écart de 16 px) est publiée sur la coque, 0 sans alerte', async () => {
    const { BandeauAlertes } = await import('../BandeauxCoque')
    const observateurs = []
    const ancien = globalThis.ResizeObserver
    globalThis.ResizeObserver = class { constructor(cb) { this.cb = cb; observateurs.push(this) } observe() {} disconnect() {} }
    let hauteur = 52
    const descripteur = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight')
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      configurable: true, get() { return this.classList?.contains('cal-coque-alertes') ? hauteur : 0 },
    })
    try {
      const hote = document.createElement('div')
      hote.className = 'rp9-host cal-coque'
      document.body.appendChild(hote)
      render(<BandeauAlertes><p>GPS corrigé</p></BandeauAlertes>, { container: hote })
      expect(hote.style.getPropertyValue('--cal-alertes-h')).toBe('68px')
      hauteur = 0 // l'alerte disparaît : la bande n'occupe plus rien
      act(() => { observateurs.forEach((o) => o.cb()) })
      expect(hote.style.getPropertyValue('--cal-alertes-h')).toBe('0px')
      // La feuille ajoute cette hauteur au décalage haut des contrôles de la carte (pile de zoom, plein écran, boussole).
      const coque = document.createElement('div')
      coque.className = 'rp9-host cal-coque'
      document.body.appendChild(coque)
      const [regle] = regleMedia('min-width: 640px', coque).filter((r) => r.style.getPropertyValue('--cal-libre-haut'))
      expect(regle, 'règle du décalage haut au bureau').toBeTruthy()
      expect(regle.style.getPropertyValue('--cal-libre-haut')).toContain('var(--cal-alertes-h')
    } finally {
      globalThis.ResizeObserver = ancien
      if (descripteur) Object.defineProperty(HTMLElement.prototype, 'offsetHeight', descripteur)
      else delete HTMLElement.prototype.offsetHeight
    }
  })

  it('Expert > Résultats : la carte reste montée mais n’est plus visible autour du panneau plein', () => {
    document.body.innerHTML = '<div class="rp9-host cal-coque" data-expert="1" data-etape="resultats"><main class="cal-coque-centre"></main></div>'
    const centre = document.querySelector('.cal-coque-centre')
    const regles = regleMedia('min-width: 640px', centre).filter((r) => r.style.getPropertyValue('visibility'))
    expect(regles.map((r) => r.style.getPropertyValue('visibility'))).toEqual(['hidden'])
    expect(centre).toBeInTheDocument() // jamais démonté
  })

  it('« Localiser » : 44 px comme un champ, bouton secondaire (jamais l’aplat doré), centré sur la rangée dès 640 px', async () => {
    const { default: BuilderCarte } = await import('../../BuilderCarte.jsx')
    const hote = document.createElement('div')
    hote.className = 'rp9-host cal-coque'
    hote.dataset.avance = '1'
    document.body.appendChild(hote)
    render(<BuilderCarte chipClass="rp9-chip" inputClass="rp9-input" mapWrapRef={{ current: null }}
      basculerPleinEcran3d={() => {}} contourClientBrut={null} photoToit={null} photoToitVisible={false}
      pleinEcran3d={false} toitClientVisible={false} />, { container: hote })
    const bouton = hote.querySelector('#rp9-search button[type="submit"]')
    expect(bouton).toHaveTextContent('Localiser')
    const c = getComputedStyle(bouton)
    expect(c.height).toBe('44px')
    expect(c.background).toContain('--cal-surface')
    expect(c.background).not.toMatch(/--cal-action|--primary|brass/)
    expect(regleMedia('min-width: 640px', bouton).map((r) => r.style.getPropertyValue('align-self'))).toContain('center')
  })
})

// T4-X5-017 — la carte passait en plein écran sans que le toit soit recadré : il restait à sa place d'avant.
/* T4-X7-019 — la bulle « 1 · Localisez le toit… » du constructeur (`#rp9-etat-vide`, posée en style inline à 12 px du haut
   de la carte) passait SOUS le bandeau du projet : dès 640 px la carte est plein écran sous les pièces. Elle se pose
   dans la zone libre, sous la carte d'adresse, centrée entre le rail et le panneau d'étape. */
describe('T4-X7-019 — la bulle de consigne n’est jamais sous le bandeau', () => {
  it('dès 640 px (bureau et tablette) : sous la zone libre et la carte d’adresse, centrée entre rail et panneau', () => {
    // jsdom ne fait pas primer `!important` sur le style inline : la règle est lue et appliquée à l'élément par `matches`.
    const source = document.createElement('style')
    source.textContent = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/56-coque-responsive.css'), 'utf8')
    document.head.appendChild(source)
    const large = [...source.sheet.cssRules].filter((r) => r.media && r.media.mediaText === '(min-width: 640px)')
      .flatMap((r) => [...r.cssRules])
    const hote = document.createElement('div')
    hote.innerHTML = '<div class="rp9-host cal-coque" data-avance="0" data-cadre="carte"><div class="rp9-map-wrap"><div id="rp9-map">'
      + '<div id="rp9-etat-vide" style="position:absolute;left:50%;top:12px">1</div></div></div></div>'
    document.body.appendChild(hote)
    try {
      const bulle = hote.querySelector('#rp9-etat-vide')
      const regles = large.filter((r) => r.selectorText && bulle.matches(r.selectorText) && r.style.getPropertyValue('top'))
      expect(regles).toHaveLength(1)
      expect(regles[0].style.getPropertyValue('top')).toBe('calc(var(--cal-libre-haut) + 84px)')
      expect(regles[0].style.getPropertyValue('left')).toBe('calc((var(--cal-libre-gauche) + 100% - var(--cal-libre-droite)) / 2)')
      // jsdom perd la priorité : elle est lue dans la feuille (`!important` est requis contre le style inline du moteur).
      const brut = source.textContent.split(String.fromCharCode(13)).join('')
      const bloc = brut.slice(brut.indexOf('#rp9-etat-vide {'), brut.indexOf('}', brut.indexOf('#rp9-etat-vide {')))
      expect(bloc).toMatch(/top: calc\(var\(--cal-libre-haut\) \+ 84px\) !important;/)
      expect(bloc).toMatch(/left: calc\(.*\) !important;/)
    } finally { source.remove(); hote.remove() }
  })
})

/* T4-X8-008 / T4-X8-006 / R5D-N4 — Expert au téléphone : le tiroir se réduit comme en guidé, le centre défile dans ses limites
   (les puces du tracé ne passent plus sur la barre des étapes), la barre des étapes est au-dessus. Règles lues dans la feuille
   et appliquées aux éléments par `matches` (jsdom ne lit pas les requêtes de média). */
describe('T4-X8-008 — Expert au téléphone : tiroir réductible, rien ne déborde sur la barre des étapes', () => {
  it('le tiroir Expert réduit mesure --cal-tiroir (96 px), centre défilant, rail au-dessus', () => {
    const source = document.createElement('style')
    source.textContent = readFileSync(resolve(process.cwd(), 'src/styles/calepinage/56-coque-responsive.css'), 'utf8')
    document.head.appendChild(source)
    const tel = [...source.sheet.cssRules].filter((r) => r.media && r.media.mediaText === '(max-width: 639px)')
      .flatMap((r) => [...r.cssRules])
    const hote = document.createElement('div')
    hote.innerHTML = '<div class="cal-coque" data-expert="1"><div class="cal-coque-corps"><div class="cal-coque-centre">'
      + '<div class="cal-coque-scene"><div class="rp9-map-wrap" data-plein-ecran="1"></div></div></div><nav class="cal-rail"></nav>'
      + '<aside class="cal-panneau-etape" data-tiroir="1" data-deplie="0"><div class="cal-panneau-etape-corps"></div></aside></div></div>'
    document.body.appendChild(hote)
    try {
      const prop = (el, nom) => tel.filter((r) => r.selectorText && r.style.getPropertyValue(nom) && el.matches(r.selectorText))
        .map((r) => r.style.getPropertyValue(nom))
      expect(prop(hote.querySelector('.cal-coque'), '--cal-tiroir').pop()).toBe('96px')
      expect(prop(hote.querySelector('.cal-panneau-etape'), 'height')).toContain('var(--cal-tiroir)')
      expect(prop(hote.querySelector('.cal-panneau-etape-corps'), 'display')).toContain('none')
      expect(prop(hote.querySelector('.cal-coque-centre'), 'overflow-y')).toContain('auto')
      expect(prop(hote.querySelector('.cal-rail'), 'z-index').pop()).toBe('calc(var(--z-base) + 40)')
      // Le plein écran de repli de la carte passe au-dessus du rail (+40) et sous la feuille « Avancé » (+45).
      expect(prop(hote.querySelector('.rp9-map-wrap'), 'z-index').pop()).toBe('calc(var(--z-base) + 42)')
      // Déplié : le tiroir n'est plus réduit (la hauteur pleine du bloc téléphone s'applique seule).
      hote.querySelector('.cal-panneau-etape').setAttribute('data-deplie', '1')
      expect(prop(hote.querySelector('.cal-panneau-etape-corps'), 'display')).not.toContain('none')
    } finally { source.remove(); hote.remove() }
  })
})

/* T4-X8-011 — le tiroir du bas se déplie au toucher ET au balayage (la poignée de 96 × 20 px était la seule prise, sans geste). */
describe('T4-X8-011 — geste du tiroir', () => {
  it('décision : balayage haut ≥ 40 px ouvre, bas ≥ 40 px referme, toucher < 10 px bascule, entre les deux rien', async () => {
    const { decisionGesteTiroir } = await import('../gesteTiroir')
    expect(decisionGesteTiroir({ dy: -60, deplie: false })).toBe('ouvrir')
    expect(decisionGesteTiroir({ dy: -60, deplie: true })).toBeNull()
    expect(decisionGesteTiroir({ dy: 60, deplie: true })).toBe('fermer')
    expect(decisionGesteTiroir({ dy: 60, deplie: false })).toBeNull()
    expect(decisionGesteTiroir({ dy: 3, deplie: false })).toBe('basculer')
    expect(decisionGesteTiroir({ dy: -25, deplie: false })).toBeNull()
    expect(decisionGesteTiroir({ dy: Number.NaN, deplie: false })).toBeNull()
  })

  it('le composant : toucher de la poignée ou du titre bascule, balayage haut ouvre (sans double bascule), le bureau n’a aucun geste', async () => {
    const { default: PanneauEtape } = await import('../PanneauEtape')
    const onDeplier = vi.fn()
    const monter = (props) => render(<PanneauEtape titre="Les panneaux" refCorps={() => {}} refPied={() => {}} {...props} />)
    const { unmount } = monter({ tiroir: true, deplie: false, onDeplier })
    const poignee = screen.getByRole('button', { name: 'Agrandir ou réduire le panneau du bas' })
    // toucher sur la poignée : son clic
    fireEvent.click(poignee)
    expect(onDeplier).toHaveBeenLastCalledWith(true)
    // balayage vers le haut sur la poignée : ouvre UNE fois, le clic qui suit est avalé
    onDeplier.mockClear()
    fireEvent.pointerDown(poignee, { clientY: 700, pointerId: 1 })
    fireEvent.pointerUp(poignee, { clientY: 640, pointerId: 1 })
    fireEvent.click(poignee, { detail: 1 }) // un vrai click de pointeur (detail >= 1)
    expect(onDeplier.mock.calls).toEqual([[true]])
    // toucher et balayage sur la rangée du titre
    onDeplier.mockClear()
    const tete = screen.getByTestId('cal-panneau-etape-titre').parentElement
    fireEvent.pointerDown(tete, { clientY: 700, pointerId: 2 })
    fireEvent.pointerUp(tete, { clientY: 698, pointerId: 2 })
    expect(onDeplier.mock.calls).toEqual([[true]])
    onDeplier.mockClear()
    fireEvent.pointerDown(tete, { clientY: 700, pointerId: 3 })
    fireEvent.pointerUp(tete, { clientY: 650, pointerId: 3 })
    expect(onDeplier.mock.calls).toEqual([[true]])
    // un balayage sur le titre, puis l'activation AU CLAVIER de la poignée (click sans pointerdown, detail 0) : elle bascule
    onDeplier.mockClear()
    fireEvent.pointerDown(tete, { clientY: 700, pointerId: 5 })
    fireEvent.pointerUp(tete, { clientY: 650, pointerId: 5 })
    expect(onDeplier.mock.calls).toEqual([[true]])
    onDeplier.mockClear()
    fireEvent.click(poignee, { detail: 0 })
    expect(onDeplier.mock.calls).toEqual([[true]])
    // un balayage tactile sur la poignée SANS click derrière, puis le drapeau retombe : le click suivant (même avec detail 1) bascule
    onDeplier.mockClear()
    vi.useFakeTimers()
    try {
      fireEvent.pointerDown(poignee, { clientY: 700, pointerId: 6 })
      fireEvent.pointerUp(poignee, { clientY: 640, pointerId: 6 })
      expect(onDeplier.mock.calls).toEqual([[true]])
      vi.advanceTimersByTime(400)
      onDeplier.mockClear()
      fireEvent.click(poignee, { detail: 1 })
      expect(onDeplier.mock.calls).toEqual([[true]])
    } finally { vi.useRealTimers() }
    unmount()
    // hors tiroir (bureau, tablette) : ni poignée ni geste
    onDeplier.mockClear()
    monter({ tiroir: false, onDeplier })
    const tete2 = screen.getByTestId('cal-panneau-etape-titre').parentElement
    fireEvent.pointerDown(tete2, { clientY: 700, pointerId: 4 })
    fireEvent.pointerUp(tete2, { clientY: 700, pointerId: 4 })
    expect(onDeplier).not.toHaveBeenCalled()
  })
})

describe('T4-X5-017 — plein écran de la carte (useAtelierVues)', () => {
  // T4-X5-017 (rejeu X9) — le toit restait dans la moitié gauche : la coque re-cadrait dans la zone libre (pièces comptées)
  // après la bascule. Le recadrage passe par LE cadrage de la coque, à l'entrée ET à la sortie, au rendu du nouvel état.
  it('entrer puis sortir du plein écran recadre le toit chaque fois, par le cadrage de la coque ; rien au montage', async () => {
    const { useAtelierVues } = await import('../../useAtelierVues')
    const { ZOOM_MAX_CADRAGE_ATELIER } = await import('../../useAtelierBoot')
    const cadrerToit = vi.fn(() => true)
    const { result } = renderHook(() => useAtelierVues({ builderApi: { current: { cadrerToit } }, calepinageId: 1, devisId: null }))
    // jsdom n'a pas l'API plein écran : la bascule prend le repli CSS (`enPleinEcran: true`), comme Safari iPhone.
    result.current.mapWrapRef.current = document.createElement('div')
    await new Promise((fin) => { requestAnimationFrame(fin) })
    expect(cadrerToit).not.toHaveBeenCalled()
    await act(async () => { result.current.basculerPleinEcran3d() })
    await waitFor(() => expect(result.current.pleinEcran3d).toBe(true))
    await waitFor(() => expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: 0 }))
    await act(async () => { result.current.basculerPleinEcran3d() })
    await waitFor(() => expect(result.current.pleinEcran3d).toBe(false))
    await waitFor(() => expect(cadrerToit).toHaveBeenCalledTimes(2))
  })
})
