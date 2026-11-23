/* Nouveau fichier car : EtapeToit.jsx est un composant neuf (écran guidé de l'étape Toit, maquettes Main /
   ToitSombre) sans module de test voisin ; le script du constructeur ne tourne pas sous vitest : le DOM qu'il
   possède (`rp9-*`) est posé à la main, comme il l'écrit, et l'écran est jugé sur ce qu'il LIT et CLIQUE.
   Ce qui est prouvé : blocs et libellés de la maquette dans l'ordre, crochets e2e, figures lues dans le DOM du
   constructeur (bloc omis sans donnée), renvoi de chaque geste au vrai contrôle `rp9-*`, la règle « À confirmer »,
   « Confirmer » = la requête de « Enregistrer la pente », « Je ne la connais pas » n'écrit rien, le compte des
   contrôles, et la feuille 51-etape-toit.css sans couleur littérale (thème sombre par les jetons). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
let builderApi

function rendre(props = {}, avant = null) {
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
  document.body.appendChild(hote)
  const coque = { noeuds: { surCarte, panneau: null, pied: null }, prendrePied: () => () => {} }
  return render(
    <MemoryRouter>
      <ContexteCoque.Provider value={coque}>
        <EtapeToit calepinageId={7} builderApi={builderApi} documentVivant={null} {...props} />
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
    expect(within(carte).getByText('Valeur de départ, pas une mesure. Confirmez-la ou mesurez-la avant d\'envoyer le devis.')).toBeInTheDocument()
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
    expect(within(surCarte).getByText('Cliquez sur un coin pour le déplacer, ou double-cliquez sur un bord pour ajouter un point.')).toBeInTheDocument()
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
    expect(cs(traits[0]).background).toContain('--cal-action')
    expect(cs(traits[1]).background).toContain('--cal-action')
    expect(cs(traits[2]).background).toContain('--cal-progression-a-venir')
    expect(cs(traits[0]).height).toBe('4px')
    const rang = screen.getByText('Étape 2 sur 5')
    expect(cs(rang).fontSize).toBe('0.75rem')
    const titre = screen.getByTestId('cal-panneau-etape-titre')
    expect(titre).toHaveTextContent('Les panneaux')
    expect(cs(titre).fontSize).toBe('1.5rem')
    expect(cs(titre).fontFamily).toBe('var(--font-display)')
    const bouton = screen.getByRole('button', { name: 'Raccorder les panneaux' })
    expect(cs(bouton).height).toBe('52px')
    expect(cs(bouton).borderRadius).toBe('var(--cal-rayon-pile)')
    expect(cs(bouton).fontSize).toBe('0.9375rem')
    expect(cs(bouton).fontWeight).toBe('700')
    expect(cs(bouton).boxShadow).toBe('var(--cal-action-ombre)')
  })

  it('panneau caché ou tiroir (tablette) : aucun trait — la tablette garde sa tête actuelle', async () => {
    const { default: PanneauEtape } = await import('../PanneauEtape')
    const { rerender } = render(<PanneauEtape numero={1} titre="Le toit" tiroir />)
    expect(screen.queryByTestId('cal-progression-etapes')).toBeNull()
    rerender(<PanneauEtape numero={1} titre="Le toit" cache />)
    expect(screen.queryByTestId('cal-progression-etapes')).toBeNull()
  })
})
