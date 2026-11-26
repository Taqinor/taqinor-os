/* Nouveau fichier car : écran neuf (EtapePanneaux.jsx, maquettes Panneaux et Tablette), aucun module de test voisin.
   Le script du toit ne tourne pas sous vitest : on pose dans le document les contrôles `rp9-*` qu'il écrit
   (mêmes ids, mêmes éléments) et l'on prouve ce que React rend — structure, ordre, libellés mot pour mot,
   hooks — et que chaque geste part au VRAI contrôle ; les replis honnêtes (sans facture, sans avis d'ombrage). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, renderHook, screen, cleanup, within, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: { calepinages: {
    designContext: vi.fn(), cibleFactures: vi.fn(), modulesDisponibles: vi.fn(), entreeElectrique: vi.fn(), resultat: vi.fn(),
    explications: vi.fn(), // ACAL1728 — le registre des « ? »
  } },
}))

import { MODULE_PAR_DEFAUT_ATELIER } from '@roofpro/moduleSelect'
import { choisirPaletteAcces } from '@rooflib/shadingEngine'
import calepinageApi from '../../../../../api/calepinageApi'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { exempleContrat, fichierContrat, reponseContrat } from '../../../../../test/fixtures/contractSamples'
import { ContexteCoque } from '../contexteCoque'
import { sousTitrePose } from '../projet'
import EtapePanneaux from './EtapePanneaux'
import { usePoseVivante } from './panneaux/constructeur'
import { jourMois, ligneModule } from './panneaux/formats'
import { lireServi, oublierLecturesServies } from './panneaux/lectures'

// ACAL1728 — le registre SERVI des « ? » (`data/explications.json`, lu comme `explications.garde.test.js`).
const REGISTRE = JSON.parse(readFileSync(
  join(fichierContrat('calepinage', 'x'), '..', '..', 'data', 'explications.json'), 'utf8')).entrees

const CATALOGUE = [
  { module: { id: 'produit-1', libelle: 'Jinko Tiger Neo 580 Wc', pmaxWc: 580, longueurMm: 2278, largeurMm: 1134 },
    selectionnable: true, motif: null },
  { module: { id: 'produit-2', libelle: 'Trina 600 Wc', pmaxWc: null, longueurMm: null, largeurMm: null },
    selectionnable: false, motif: 'la puissance crête (Wc) est absente de la fiche' },
]

/** Le DOM que le script écrit (ids `rp9-*`), tel que BuilderToit / InspecteurBuilder / zones.ts le rendent. */
function monterConstructeur(o = {}) {
  const c = {
    besoin: '12', besoinDesactive: false, note: '', panneaux: '12 × 580 W', kwc: '6,96 kWc',
    prod: '11 480 kWh/an', cover: '82 %', orient: 'auto', ombre: null, heure: '15', date: '2028-12-21',
    saison: 'winter', ...o,
  }
  const racine = document.createElement('div')
  racine.id = 'faux-constructeur'
  racine.innerHTML = `
    <input id="rp9-need-input" value="${c.besoin}" ${c.besoinDesactive ? 'disabled' : ''} ${c.lePlus ? 'data-le-plus="1"' : ''}>
    <p id="rp9-need-note">${c.note}</p>
    <p id="rp9-reco-panels">${c.panneaux}</p><p id="rp9-reco-kwc">${c.kwc}</p>
    <p id="rp9-reco-prod">${c.prod}</p><p id="rp9-reco-cover">${c.cover}</p>
    ${c.tailles ? `<p id="rp9-reco-tailles">${c.tailles}</p>` : ''}
    ${['auto', 'portrait', 'landscape'].map((v) => `<button data-orient="${v}" aria-pressed="${v === c.orient}">${v}</button>`).join('')}
    <select id="rp9-pan-module-select">
      <option value="">Module par défaut de l'atelier</option>
      <option value="produit-1">Jinko Tiger Neo 580 Wc</option>
      <option value="produit-2" disabled>Trina 600 Wc — la puissance crête (Wc) est absente de la fiche</option>
    </select>
    <span id="rp9-pan-module-mention">module de départ, à confirmer</span>
    <span id="rp9-pan-module-erreur" hidden></span>
    <input id="rp9-sun-hour" type="range" min="6" max="${c.heureMax ?? 18}" value="${c.heure}">
    <input id="rp9-sun-date" type="date" value="${c.date}">
    <button data-sun-season="winter" aria-pressed="${c.saison === 'winter'}">w</button>
    <button data-sun-season="summer" aria-pressed="${c.saison === 'summer'}">s</button>
    <button id="rp9-sun-play-day" aria-pressed="false">play</button>
    <button id="rp9-heatmap-toggle" aria-pressed="${c.carte ? 'true' : 'false'}">carte</button>
    <div id="rp9-solar-access">${c.ombre ? `<div>Proposition — retirer les <span class="fig">${c.ombre}</span> module(s) dont l’accès solaire est sous 80 % (seuil de votre société)</div><button id="rp9-solar-access-apply">Retirer ces modules</button>` : ''}</div>`
  document.body.appendChild(racine)
  const espion = (sel, evt = 'click') => {
    const fn = vi.fn()
    racine.querySelector(sel).addEventListener(evt, fn)
    return fn
  }
  return { racine, espion }
}

let noeudCarte
function rendre(props = {}) {
  noeudCarte = document.createElement('div')
  document.body.appendChild(noeudCarte)
  return render(
    <MemoryRouter>
      <ContexteCoque.Provider value={{ noeuds: { surCarte: noeudCarte }, prendrePied: () => () => {} }}>
        <EtapePanneaux calepinageId={7} {...props} />
      </ContexteCoque.Provider>
    </MemoryRouter>,
  )
}

/** Les réponses servies : design-context (lead), taille des factures (H3 : `cible-factures/`, lue à part), catalogue,
    entrée électrique, résultat. */
function servir({
  cible = { panneaux: 12, kwc: 6.96, module_wc: 580 }, motif = '',
  materiel = { module: null, modules_par_pan: [] }, resultat = { simule: false },
} = {}) {
  calepinageApi.calepinages.designContext.mockResolvedValue({
    data: { calepinage: { lead: 42 }, consommation_lead: { facture_mensuelle_mad: 900, motif } },
  })
  calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: cible } })
  calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: { modules: CATALOGUE } })
  calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { materiel } })
  calepinageApi.calepinages.resultat.mockResolvedValue({ data: resultat })
  calepinageApi.calepinages.explications.mockResolvedValue({ data: { entrees: REGISTRE } })
}

beforeEach(() => servir())
afterEach(() => {
  cleanup()
  document.getElementById('faux-constructeur')?.remove()
  noeudCarte?.remove()
  vi.clearAllMocks()
  oublierLecturesServies()
})

describe('formats', () => {
  it('ligne du modèle : puissance et cotes servies, jamais une valeur supposée', () => {
    expect(ligneModule(CATALOGUE[0].module)).toBe('580 Wc · 2,28 × 1,13 m')
    expect(ligneModule(CATALOGUE[1].module)).toBe('')
  })
  it('jour et mois du champ date du constructeur', () => {
    expect(jourMois('2028-12-21')).toBe('21 décembre')
    expect(jourMois('')).toBe('')
  })
})

/* Item 14 (T4-U1-023) — l'étape Panneaux n'avait « aucune carte d'avis d'ombrage » sur un toit qui porte une cheminée
   et un voisin haut : la phrase servie (`parcours.manque`, code `ombres_non_mesurees`) y est dite. */
describe('étape Panneaux — ombres posées mais pas encore comptées (T4-U1-023)', () => {
  it('la carte dit la phrase servie, sans bouton « Retirer »', async () => {
    monterConstructeur()
    servir()
    const message = 'Ce toit porte 1 obstacle et 1 objet voisin qui font de l’ombre, mais cette ombre n’est pas encore comptée sur les panneaux posés : ouvrez le calcul des ombres du toit, puis enregistrez et relancez la simulation.'
    rendre({ parcours: { manque: [{ code: 'ombres_non_mesurees', etape: 'resultats', gravite: 'a_regler', nombre: 1, message,
      cible: { onglet: 'production', champ: '' } }] } })
    const carte = await screen.findByTestId('cal-panneaux-ombres-non-comptees')
    expect(carte).toHaveTextContent('Ombres à compter')
    expect(carte).toHaveTextContent(message)
    expect(within(carte).queryByRole('button', { name: /Retirer/ })).toBeNull()
  })
})

describe('étape Panneaux — panneau de droite', () => {
  it('rend les blocs de la maquette dans l’ordre, libellés mot pour mot', async () => {
    monterConstructeur()
    document.getElementById('rp9-pan-module-select').value = 'produit-1' // le modèle posé sur le pan
    rendre()
    const titres = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(titres).toEqual(['Combien de panneaux ?', 'Sens de pose'])
    expect(screen.getByText('Panneau')).toBeInTheDocument()
    const ordre = ['Panneau', 'Combien de panneaux ?', 'Sens de pose']
      .map((t) => screen.getByText(t).compareDocumentPosition(screen.getByText('Sens de pose')))
    expect(ordre[0] & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(await screen.findByText('Recommandé')).toBeInTheDocument() // la facture servie est lue
    for (const libelle of ['Couvrir la facture', 'Le plus de panneaux', 'Portrait', 'Paysage', 'Au mieux']) {
      expect(screen.getByText(libelle)).toBeInTheDocument()
    }
    // pas de second bouton d'étape (le pied « Raccorder les panneaux → » est celui de la coque) ni d'« En stock »
    expect(screen.queryByText(/Raccorder/)).toBeNull()
    expect(document.body).not.toHaveTextContent('En stock')
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-module')).toHaveTextContent('580 Wc · 2,28 × 1,13 m'))
  })

  it('carte du modèle : le choix part au vrai sélecteur (comme le sélecteur du pan)', async () => {
    const { espion } = monterConstructeur()
    const surChange = espion('#rp9-pan-module-select', 'change')
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    expect(within(carte).getByText('module de départ, à confirmer')).toBeInTheDocument()
    fireEvent.click(within(carte).getByRole('button', { name: /Module par défaut/ }))
    const options = within(carte).getAllByRole('option')
    expect(options).toHaveLength(3)
    // la fiche incomplète reste visible, grisée, avec son motif servi
    await waitFor(() => expect(options[2]).toHaveTextContent('la puissance crête (Wc) est absente de la fiche'))
    expect(within(options[2]).getByRole('button')).toBeDisabled()
    fireEvent.click(within(options[1]).getByRole('button'))
    expect(document.getElementById('rp9-pan-module-select').value).toBe('produit-1')
    expect(surChange).toHaveBeenCalledTimes(1)
  })

  it('D-ACAL-71 — le menu dit « En stock » sur la ligne servie, rien sur celle qui ne l’est pas', async () => {
    monterConstructeur()
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({
      data: { modules: [{ ...CATALOGUE[0], en_stock: true }, { ...CATALOGUE[1], en_stock: null }] },
    })
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    fireEvent.click(within(carte).getByRole('button', { name: /Module par défaut/ }))
    await waitFor(() => expect(within(carte).getAllByRole('option')[1]).toHaveTextContent('En stock · 580 Wc · 2,28 × 1,13 m'))
    expect(within(carte).getAllByRole('option')[2]).not.toHaveTextContent(/stock/i)
  })

  it('D-ACAL-169 — le panneau par défaut de la société porte la pastille « Par défaut », les autres modèles aucune', async () => {
    monterConstructeur()
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({
      data: { modules: [{ ...CATALOGUE[0], par_defaut: true }, CATALOGUE[1]] },
    })
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    fireEvent.click(within(carte).getByRole('button', { name: /Module par défaut/ }))
    await waitFor(() => expect(within(within(carte).getAllByRole('option')[1]).getByTestId('cal-pan-par-defaut')).toHaveTextContent('Par défaut'))
    expect(within(carte).getAllByTestId('cal-pan-par-defaut')).toHaveLength(1)
    expect(within(carte).getAllByRole('option')[2]).not.toHaveTextContent('Par défaut')
  })

  it('lane E9 (T4-X2-001) — module de 710 W pour une conception de 8 × 550 W : la carte dit la puissance et le compte servi, la pose reçoit 6', async () => {
    monterConstructeur({ besoin: '12' })
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    const catalogue = [{ ...CATALOGUE[0], module: { ...CATALOGUE[0].module, libelle: 'Module 710 Wc', pmaxWc: 710 } }]
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: {
      modules: catalogue, panneaux_selon_watt: { 710: 6, 715: 6 }, kwc_selon_watt: { 710: 4.26, 715: 4.29 } } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 8, kwc: 4.4, module_wc: 550 }, refus: '', calcul_en_cours: false } })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    // T4-X8-011 — UN compte et UN kWc qui vont ensemble (6 × 710 W = 4,26 kWc, les deux SERVIS), puis la conception
    // dite dans une seconde phrase complète — jamais « 4,40 kWc — 6 panneaux de 710 W ».
    await waitFor(() => expect(facture.querySelector('.cal-pan-option-ligne')).toHaveTextContent('6 panneaux de 710 W · 4,26 kWc'))
    expect(facture.querySelector('[data-zone="conception-du-lead"]'))
      .toHaveTextContent('La conception du lead compte 8 panneaux de 550 W, 4,4 kWc.')
    expect(facture).not.toHaveTextContent('4,40 kWc —')
    fireEvent.click(facture)
    expect(document.getElementById('rp9-need-input').value).toBe('6')
  })

  /* D-ACAL-110 (rejeu R5B, 26/11) — conception 7 × 710 W = 4,97 kWc, module 715 W choisi : la carte disait « 7 panneaux de
     715 W · 5 kWc » et « La conception du lead compte 7 panneaux de 710 W, 4,97 kWc. » sans dire que le panneau (ou le
     nombre) n'est pas celui de la conception. Une phrase simple, aux valeurs SERVIES (`panneaux_selon_watt`). */
  it.each([
    [715, { 715: 7 }, { 715: 5.0 }, 'Ce panneau de 715 W n’est pas celui de la conception du lead ; le nombre de panneaux reste 7.'],
    [550, { 550: 9 }, { 550: 4.95 }, 'Ce panneau de 550 W n’est pas celui de la conception du lead : il en faut 9 au lieu de 7.'],
  ])('D-ACAL-110 — module de %s W : la phrase dit que le panneau diffère et ce que devient le nombre', async (wc, table, tableKwc, attendu) => {
    monterConstructeur({ besoin: '7' })
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    const catalogue = [{ ...CATALOGUE[0], module: { ...CATALOGUE[0].module, libelle: `Module ${wc} Wc`, pmaxWc: wc } }]
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: {
      modules: catalogue, panneaux_selon_watt: table, kwc_selon_watt: tableKwc } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 7, kwc: 4.97, module_wc: 710 }, refus: '', calcul_en_cours: false } })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture.querySelector('[data-zone="conception-du-lead"]')).toHaveTextContent(attendu))
    expect(facture.querySelector('[data-zone="conception-du-lead"]'))
      .toHaveTextContent('La conception du lead compte 7 panneaux de 710 W, 4,97 kWc.')
  })

  it('lane E9 (T4-X2-001) — module absent de la table servie : la puissance seule, aucun compte, rien à poser', async () => {
    monterConstructeur({ besoin: '12' })
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    const catalogue = [{ ...CATALOGUE[0], module: { ...CATALOGUE[0].module, pmaxWc: 710 } }]
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: { modules: catalogue, panneaux_selon_watt: {} } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 8, kwc: 4.4, module_wc: 550 }, refus: '', calcul_en_cours: false } })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture.querySelector('[data-zone="conception-du-lead"]'))
      .toHaveTextContent('La conception du lead compte 8 panneaux de 550 W, 4,4 kWc.'))
    expect(facture.querySelector('.cal-pan-option-ligne')).toBeNull() // aucun compte servi pour 710 W : aucun compte dit
    expect(facture).toBeDisabled()
  })

  it('T4-X8-011 — module choisi dont la fiche n’est pas (encore) lue : la puissance POSÉE par le constructeur compte, jamais « 7 panneaux » de 550 W sous un module de 710 W', async () => {
    monterConstructeur({ besoin: '5', panneaux: '5 × 710 W', kwc: '3,55 kWc' })
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    // le catalogue servi ne porte pas (encore) la fiche du module choisi
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: {
      modules: [], panneaux_selon_watt: { 710: 5 }, kwc_selon_watt: { 710: 3.55 } } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 7, kwc: 3.85, module_wc: 550 }, refus: '', calcul_en_cours: false } })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture.querySelector('.cal-pan-option-ligne')).toHaveTextContent('5 panneaux de 710 W · 3,55 kWc'))
    expect(facture.querySelector('[data-zone="conception-du-lead"]'))
      .toHaveTextContent('La conception du lead compte 7 panneaux de 550 W, 3,85 kWc.')
    expect(facture).not.toHaveTextContent('7 panneaux · 3,85 kWc')
    expect(facture).toHaveAttribute('aria-pressed', 'true') // le besoin posé (5) EST la cible du module : carte choisie
  })

  it('T4-X8-011 — même module que la conception : une ligne, son compte et son kWc, aucune seconde phrase', async () => {
    monterConstructeur()
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('12 panneaux · 6,96 kWc · Factures du lead'))
    expect(facture.querySelector('[data-zone="conception-du-lead"]')).toBeNull()
  })

  it('lane E9 — la conception recalculée depuis l’ouverture : la carte « Couvrir la facture » dit pourquoi, jamais en silence', async () => {
    monterConstructeur()
    const raison = 'Recalculé le 25/11 à 10 h 05 : matériel désigné à l’atelier : Module 580 Wc / Onduleur 6 kW'
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: {
      calepinage: { lead: 42 }, consommation_lead: { facture_mensuelle_mad: 900, motif: '' }, cible: { version: 1 } } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 12, kwc: 6.96, module_wc: 580, version: 2, raison }, refus: '', calcul_en_cours: false } })
    rendre()
    expect(await screen.findByText(`Conception recalculée : ${raison}`)).toHaveAttribute('data-zone', 'conception-recalculee')
    // Même version que celle ouverte : rien n'est dit.
    cleanup()
    oublierLecturesServies()
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 12, kwc: 6.96, module_wc: 580, version: 1, raison }, refus: '', calcul_en_cours: false } })
    rendre()
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('12 panneaux'))
    expect(document.querySelector('[data-zone="conception-recalculee"]')).toBeNull()
  })

  it('« Couvrir la facture » = la taille servie des factures (cible_factures), jamais la pose posée (55 panneaux, 809 %)', async () => {
    // Calepinage 5 tel que relevé : cible enregistrée 60, 55 tiennent au module par défaut, 809 %.
    const { espion } = monterConstructeur({
      besoin: '60', panneaux: '55 × 720 W', kwc: '39,60 kWc', prod: '53 856 kWh/an', cover: '809 %',
      note: '60 au devis — seuls 55 tiennent en plein sud (toit ou obstacles).',
    })
    const surInput = espion('#rp9-need-input', 'input')
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('Couvrir la factureRecommandé12 panneaux · 6,96 kWc'))
    expect(facture).not.toHaveTextContent('809')
    expect(facture).not.toHaveTextContent('%') // le pourcentage n'est dit qu'à côté de la taille posée
    expect(facture).toHaveAttribute('aria-pressed', 'false')
    // la pose actuelle = tout ce qui tient (55) : « Le plus de panneaux », son % nommé pour ce qu'il est
    const max = screen.getByTestId('cal-panneaux-option-max')
    expect(max).toHaveAttribute('aria-pressed', 'true')
    expect(max).toHaveTextContent('55 panneaux · 39,60 kWc · ≈ 809 % de la consommation')
    expect(document.body).not.toHaveTextContent('de la facture')
    fireEvent.click(facture)
    expect(document.getElementById('rp9-need-input').value).toBe('12')
    expect(surInput).toHaveBeenCalledTimes(1)
    // le script a posé 12 panneaux : la carte devient la choisie, avec SA part lue sur le script
    document.getElementById('rp9-need-note').textContent = 'Il reste de la place sur le toit, laissée libre.'
    document.getElementById('rp9-reco-panels').textContent = '12 × 720 W'
    document.getElementById('rp9-reco-kwc').textContent = '8,64 kWc'
    document.getElementById('rp9-reco-prod').textContent = '9 589 kWh/an'
    document.getElementById('rp9-reco-cover').textContent = '144 %'
    await waitFor(() => expect(facture).toHaveTextContent('12 panneaux · 6,96 kWc · Factures du lead · ≈ 144 % de la consommation'), { timeout: 3000 })
    expect(facture).toHaveAttribute('aria-pressed', 'true')
    expect(max).toHaveAttribute('aria-pressed', 'false')
    // l'autre carte garde les chiffres lus quand elle était posée
    expect(max).toHaveTextContent('55 panneaux · 39,60 kWc')
    fireEvent.click(max)
    expect(document.getElementById('rp9-need-input').value).toBe('400')
  })

  it('tiennent < cible : la carte dit ce qui tient, jamais la taille irréalisable', async () => {
    const { espion } = monterConstructeur({
      besoin: '6', panneaux: '1 × 710 W', kwc: '0,71 kWc', cover: '14 %',
      note: '6 au devis — seuls 1 tiennent en plein sud (toit ou obstacles).',
    })
    servir({ cible: { panneaux: 6, kwc: 4.26, module_wc: 710 } })
    const surInput = espion('#rp9-need-input', 'input')
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('Couvrir la factureRecommandé1 panneau · 0,71 kWc · 6 cible (Factures du lead) · 5 de moins que la cible'))
    expect(facture).not.toHaveTextContent('4,26')
    expect(facture).not.toHaveTextContent('6 panneaux')
    fireEvent.click(facture)
    expect(surInput).not.toHaveBeenCalled() // le besoin 6 est déjà la cible posée : rien à renvoyer, la pose reste 1
  })

  // ACAL1331 (D-ACAL-76) — calepinage vierge : le constructeur a posé la taille de la cible et l'a dite dans sa note ;
  // le Guidé la DIT sous « Combien de panneaux ? ». Le commercial ajuste (« + ») : la note change, la phrase part.
  it('ACAL1331 — la taille posée d’elle-même est dite ; ajustée, la phrase part', async () => {
    const phrase = 'Posé d’après les factures du lead : 12 panneaux · 6,96 kWc — ajustez si besoin.'
    monterConstructeur({ besoin: '12', note: phrase })
    rendre()
    const dite = () => document.querySelector('[data-zone="taille-auto"]')
    await waitFor(() => expect(dite()).toHaveTextContent(phrase))
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveAttribute('aria-pressed', 'true'))
    document.getElementById('rp9-need-input').value = '13'
    document.getElementById('rp9-need-note').textContent = '13 posés / 13 cible — il reste de la place sur le toit, laissée libre.'
    await waitFor(() => expect(dite()).toBeNull(), { timeout: 3000 })
  })

  it('la carte non choisie garde ses chiffres : « Le plus de panneaux » dès l’ouverture, la part de la facture après le clic, le sens dit', async () => {
    monterConstructeur({
      besoin: '12', panneaux: '12 × 710 W', kwc: '8,52 kWc', cover: '63 %', orient: 'portrait',
      note: '12 posés — seuls 20 tiennent en plein sud.',
    })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    const max = screen.getByTestId('cal-panneaux-option-max')
    await waitFor(() => expect(facture).toHaveTextContent('≈ 63 % de la consommation'))
    expect(max).toHaveTextContent('20 panneaux · 14,20 kWc') // 20 × 710 W, lu de la pose, dès l'ouverture
    fireEvent.click(max)
    expect(document.getElementById('rp9-need-input').value).toBe('400')
    // le script pose tout ce qui tient et bascule le sens de pose
    document.getElementById('rp9-reco-panels').textContent = '20 × 710 W'
    document.getElementById('rp9-reco-kwc').textContent = '14,20 kWc'
    document.getElementById('rp9-reco-cover').textContent = '105 %'
    document.getElementById('rp9-need-note').textContent = '12 posés — seuls 20 tiennent en plein sud.'
    document.querySelector('[data-orient="portrait"]').setAttribute('aria-pressed', 'false')
    document.querySelector('[data-orient="landscape"]').setAttribute('aria-pressed', 'true')
    await waitFor(() => expect(document.querySelector('[data-zone="sens-bascule"]')).toHaveTextContent('passé de Portrait à Paysage'), { timeout: 3000 })
    expect(max).toHaveAttribute('aria-pressed', 'true')
    expect(facture).toHaveTextContent('≈ 63 % de la consommation') // gardée, pas perdue au clic
    expect(facture).not.toHaveTextContent('105')
  })

  it('lead C&I : la carte dit la raison servie (cible-factures/ refus), sans renvoyer renseigner une facture saisie', async () => {
    servir()
    calepinageApi.calepinages.cibleFactures.mockResolvedValue(reponseContrat('calepinage', 'calepinage_cible_factures', 'exemple_refus'))
    rendre()
    await screen.findByText(exempleContrat('calepinage', 'calepinage_cible_factures', 'exemple_refus').refus)
    expect(screen.getByTestId('cal-panneaux-option-facture')).toBeDisabled()
    expect(screen.queryByText('Renseigner la facture du lead')).toBeNull()
    expect(document.body).not.toHaveTextContent('Aucune taille ne se tire des factures')
  })

  /* Relecture E5 B1 — le lead n'a encore aucune conception : son premier calcul est en file (`calcul_en_cours`). L'étape le
     dit (jamais « 0 panneau »), relit d'elle-même un nombre BORNÉ de fois, offre « Actualiser » ; après les relectures,
     la phrase dit le geste (modifier la fiche du lead). */
  it('B1 — conception en cours de calcul : dite, relue d’elle-même, « Actualiser » ; puis le geste', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      servir()
      calepinageApi.calepinages.cibleFactures.mockResolvedValue(
        reponseContrat('calepinage', 'calepinage_cible_factures', 'exemple_en_cours'))
      rendre()
      const note = await screen.findByText(/La conception du lead est en cours de calcul/)
      expect(note).toHaveTextContent('la taille s’affichera ici dans quelques secondes')
      expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('calcul en cours')
      expect(screen.getByTestId('cal-panneaux-option-facture')).not.toHaveTextContent('0 panneau')
      expect(document.body).not.toHaveTextContent('Aucune taille ne se tire des factures')
      for (let i = 0; i < 5; i += 1) {
        await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
      }
      await screen.findByText(/n’est toujours pas calculée/)
      const appels = calepinageApi.calepinages.cibleFactures.mock.calls.length
      expect(appels).toBe(6)  // une lecture + cinq relectures, jamais plus (mutant « sans borne » : rouge)
      await act(async () => { await vi.advanceTimersByTimeAsync(9000) })
      expect(calepinageApi.calepinages.cibleFactures.mock.calls.length).toBe(appels)
      expect(screen.getByRole('link', { name: 'Ouvrir la fiche du lead' })).toHaveAttribute('href', '/crm/leads/42')
      calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
        cible_factures: { panneaux: 9, kwc: 5.22, module_wc: 580 }, refus: '', calcul_en_cours: false } })
      fireEvent.click(screen.getByTestId('cal-panneaux-actualiser-conception'))
      await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('9 panneaux'))
      expect(screen.queryByText(/en cours de calcul/)).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('Critique ACAL1517 — facture ABSENTE : le refus servi est dit ET le lien « Renseigner la facture du lead » reste là', async () => {
    servir()
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { calepinage: { lead: 42 }, consommation_lead: { facture_mensuelle_mad: null, source: 'lead', motif: '' } },
    })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: null, refus: 'Aucune facture ni consommation sur ce lead : rien ne dimensionne le devis.' } })
    rendre()
    await screen.findByText(/rien ne dimensionne le devis/)
    const lien = await screen.findByRole('link', { name: 'Renseigner la facture du lead' })
    expect(lien).toHaveAttribute('href', '/crm/leads/42')
  })

  // R6-N4 — lead R5A-4 (facture 900 MAD + taille souhaitée 6 kWc) : le serveur nomme la cause dans `refus`, dite telle quelle ;
  // sans cause servie, un lead qui porte une facture ne lit jamais « Aucune taille ne se tire des factures » ni le lien
  // « Renseigner la facture du lead ».
  it('R6-N4 — facture saisie : la cause servie est dite, et sans cause jamais « aucune taille » ni « renseigner la facture »', async () => {
    servir({ cible: null })
    const CAUSE = 'La taille de ce lead vient de la taille souhaitée sur sa fiche (6 kWc ; conception : 9 panneaux · 6,39 kWc), pas de ses factures.'
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: null, refus: CAUSE } })
    rendre()
    await screen.findByText(CAUSE)
    expect(document.body).not.toHaveTextContent('Aucune taille ne se tire des factures')
    expect(screen.queryByRole('link', { name: 'Renseigner la facture du lead' })).toBeNull()
    cleanup()
    oublierLecturesServies()
    servir({ cible: null })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: null, refus: '' } })
    rendre()
    await screen.findByText(/La facture de ce lead est renseignée, mais le moteur n’en a tiré aucune taille/)
    expect(document.body).not.toHaveTextContent('Aucune taille ne se tire des factures')
    expect(screen.queryByRole('link', { name: 'Renseigner la facture du lead' })).toBeNull()
  })

  // R6-N4 — taille souhaitée SANS facture : il ne manque rien, la phrase n'est pas suivie du lien de saisie d'une facture.
  it('R6-N4 — taille souhaitée sur la fiche, sans facture : la cause est dite, aucun lien « Renseigner la facture du lead »', async () => {
    servir({ cible: null })
    const CAUSE = 'La taille de ce lead vient de la taille souhaitée sur sa fiche (6 kWc ; conception : 9 panneaux · 6,39 kWc), pas de ses factures.'
    calepinageApi.calepinages.designContext.mockResolvedValue({ data: {
      calepinage: { lead: 42 }, consommation_lead: { facture_mensuelle_mad: null, motif: '' },
      cible: { source: 'lead', panneaux: 9, kwc: 6.39 } } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: null, refus: CAUSE } })
    rendre()
    await screen.findByText(CAUSE)
    expect(screen.queryByRole('link', { name: 'Renseigner la facture du lead' })).toBeNull()
  })

  // T4-X9-013 — calepinage SANS lead : « Ville inconnue du moteur : renseigner la ville ou le point GPS du lead. » sous
  // « Couvrir la facture », alors qu'aucun lead n'existe (refus du moteur sur la conception du calepinage porteur).
  it('T4-X9-013 — sans lead : aucune phrase qui demande de remplir le lead (refus et motif du moteur tus)', async () => {
    servir()
    const VILLE = 'Ville inconnue du moteur : renseigner la ville ou le point GPS du lead.'
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { calepinage: { lead: null }, consommation_lead: { facture_mensuelle_mad: null, motif: VILLE } },
    })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: null, refus: VILLE } })
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.cibleFactures).toHaveBeenCalled())
    await screen.findByTestId('cal-panneaux-option-facture')
    expect(screen.queryByText(/Ville inconnue du moteur/)).toBeNull()
    expect(screen.queryByRole('link', { name: 'Renseigner la facture du lead' })).toBeNull()
    // Reste de G2 (orchestrateur) : la phrase de repli ne nomme pas « ce lead » quand il n'y en a pas.
    expect(document.body).not.toHaveTextContent('factures de ce lead')
    expect(document.body).toHaveTextContent('Ce calepinage n’a pas de lead : aucune taille n’est tirée d’une facture.')
  })

  it('T4-X8-012 — « le plus de panneaux » posé : le champ du constructeur dit le besoin de la facture (7 = la cible), la carte choisie reste « Le plus de panneaux »', async () => {
    monterConstructeur({ besoin: '7', lePlus: true, panneaux: '9 × 580 W', kwc: '5,22 kWc',
      note: 'Vous avez choisi le plus de panneaux possible : 9 posés. Le besoin de la facture : 7.' })
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    servir({ cible: { panneaux: 7, kwc: 4.06, module_wc: 580 } })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('7 panneaux · 4,06 kWc'))
    expect(facture).toHaveAttribute('aria-pressed', 'false')
    const max = screen.getByTestId('cal-panneaux-option-max')
    expect(max).toHaveAttribute('aria-pressed', 'true')
    expect(max).toHaveTextContent('9 panneaux · 5,22 kWc')
    expect(document.body).not.toHaveTextContent('400')
  })

  it('ni l’une ni l’autre : aucune carte choisie et « Pose actuelle : N panneaux · kWc »', async () => {
    monterConstructeur({ besoin: '30', panneaux: '30 × 580 W', kwc: '17,40 kWc', prod: '28 700 kWh/an', cover: '431 %',
      note: '30 posés — il reste de la place sur le toit, laissée libre.' })
    rendre()
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('Recommandé'))
    expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('cal-panneaux-option-max')).toHaveAttribute('aria-pressed', 'false')
    expect(document.querySelector('[data-zone="pose-actuelle"]')).toHaveTextContent('Pose actuelle : 30 panneaux · 17,40 kWc')
  })

  /* ACAL1613 — lead à 900 MAD/mois, 4 panneaux recommandés, 13 posés : la carte « Couvrir la facture » non posée disait
     « 4 panneaux · 2,84 kWc » sans pourcentage. Elle dit la part SERVIE (`chiffrage.couverture_pct` du design-context,
     contrat `calepinage_design_context.json`) à SA taille, par la fonction du constructeur ; une autre taille : rien. */
  const chiffrageServi = (kwc, pct) => ({
    ...exempleContrat('calepinage', 'calepinage_design_context', 'exemple').chiffrage,
    kwc: { valeur: kwc, unite: 'kWc', source: 'conception', etat: 'servi' },
    couverture_pct: { valeur: pct, unite: '%', source: 'conception', etat: 'servi' },
  })
  it.each([
    ['la conception servie a la taille de la carte', 2.84, '4 panneaux · 2,84 kWc · Factures du lead · ≈ 54 % de la consommation'],
    ['la conception servie a une autre taille', 3.55, null],
  ])('ACAL1613 — la carte recommandée non posée dit sa part : %s', async (_cas, kwcServi, attendu) => {
    servir({ cible: { panneaux: 4, kwc: 2.84, module_wc: 710 } })
    monterConstructeur({ besoin: '13', panneaux: '13 × 710 W', kwc: '9,23 kWc', cover: '—',
      note: '13 posés — il reste de la place sur le toit, laissée libre.' })
    rendre({ contexte: { calepinage: { lead: 42 }, consommation_lead: { facture_mensuelle_mad: 900, motif: '' },
      chiffrage: chiffrageServi(kwcServi, 54.0) } })
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('4 panneaux · 2,84 kWc'))
    expect(facture).toHaveAttribute('aria-pressed', 'false')
    if (attendu) expect(facture).toHaveTextContent(attendu)
    else expect(facture).not.toHaveTextContent('%')
  })

  it('sans taille tirée des factures : « Couvrir la facture » grisée avec le motif servi et le lien vers le lead', async () => {
    servir({ cible: null, motif: 'Aucune facture sur le lead.' })
    monterConstructeur({
      besoin: '—', besoinDesactive: true, panneaux: '22 × 580 W', kwc: '12,76 kWc', cover: '—',
      note: 'Indiquez votre facture pour dimensionner le nombre de panneaux.',
    })
    rendre()
    const carte = screen.getByTestId('cal-panneaux-option-facture')
    expect(carte).toBeDisabled()
    expect(carte).not.toHaveTextContent('Recommandé')
    expect(carte).not.toHaveTextContent(/\d/)
    await waitFor(() => expect(carte.parentElement).toHaveTextContent('Aucune facture sur le lead.'))
    // tout ce qui tient est déjà posé : « Le plus de panneaux » est l'option en vigueur
    expect(screen.getByTestId('cal-panneaux-option-max')).toHaveAttribute('aria-pressed', 'true')
    const lien = await screen.findByRole('link', { name: 'Renseigner la facture du lead' })
    expect(lien).toHaveAttribute('href', '/crm/leads/42')
  })

  it('H2 — facture en cours de lecture : jamais « Aucune taille… » ; en échec : « Lecture impossible — réessayer »', async () => {
    let finir
    calepinageApi.calepinages.cibleFactures.mockImplementation(() => new Promise((ok, ko) => { finir = { ok, ko } }))
    monterConstructeur()
    rendre()
    const section = screen.getByTestId('cal-panneaux-option-facture').parentElement
    await waitFor(() => expect(calepinageApi.calepinages.cibleFactures).toHaveBeenCalledTimes(1))
    expect(section.querySelector('[data-zone="facture-lecture"]')).toHaveTextContent('Lecture de la facture du lead…')
    expect(section).not.toHaveTextContent(/Aucune taille|Renseigner la facture/)
    await act(async () => { finir.ko(new Error('timeout of 20000ms exceeded')) })
    const reessayer = await within(section).findByRole('button', { name: 'réessayer' })
    expect(section.querySelector('[data-zone="facture-echec"]')).toHaveTextContent('Lecture impossible — réessayer')
    expect(section).not.toHaveTextContent(/Aucune taille|Renseigner la facture/)
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: { panneaux: 4, kwc: 2.84, module_wc: 710 } } })
    fireEvent.click(reessayer)
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('Couvrir la factureRecommandé4 panneaux · 2,84 kWc'))
    expect(section).not.toHaveTextContent(/Aucune taille|Lecture impossible/)
  })

  it('H2 — Toit et Panneaux lisent la MÊME ressource : une lecture en vol ou fraîche est partagée, un échec jamais gardé', async () => {
    const a = lireServi('contexte', 7)
    const b = lireServi('contexte', 7)
    expect(a).toBe(b)
    await a
    expect(lireServi('contexte', 7)).toBe(a) // fraîche : la même réponse (Toit → Panneaux ne relit pas)
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(1)
    oublierLecturesServies()
    calepinageApi.calepinages.designContext.mockRejectedValueOnce(new Error('timeout'))
    await expect(lireServi('contexte', 7)).rejects.toThrow('timeout')
    await lireServi('contexte', 7) // l'échec n'est pas gardé : relu
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(3)
  })

  it('H2/H3 — le design-context de l’atelier (`contexte`) prime : aucune seconde lecture ; la taille, lue à part', async () => {
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: { cible_factures: { panneaux: 4, kwc: 2.84, module_wc: 710 } } })
    monterConstructeur()
    rendre({ contexte: { calepinage: { lead: 40 } } })
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture'))
      .toHaveTextContent('Couvrir la factureRecommandé4 panneaux · 2,84 kWc'))
    expect(calepinageApi.calepinages.designContext).not.toHaveBeenCalled()
    expect(calepinageApi.calepinages.cibleFactures).toHaveBeenCalledTimes(1)
  })

  it('module : pans sans module mais étude électrique qui en désigne un → état honnête, jamais le défaut du script', async () => {
    servir({ materiel: { module: null, modules_par_pan: [
      { pan: 'A', designation: 'Canadien Solar 710 Wc', produit_id: 1 }, { pan: 'B', designation: 'Canadien Solar 710 Wc', produit_id: 1 },
    ] } })
    const { racine } = monterConstructeur()
    racine.querySelector('#rp9-pan-module-mention').textContent =
      `${MODULE_PAR_DEFAUT_ATELIER.libelle} — aucun module du catalogue n’est posé sur ce site.`
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    // H2 — la liste dit LA MÊME phrase avant et après la lecture de l'étude électrique (tablette = bureau) : aucun
    // panneau choisi + le module par défaut avec lequel l'atelier calcule ; l'étude électrique est dite à part.
    const nom = carte.querySelector('.cal-pan-module-nom')
    const ligne = carte.querySelector('.cal-pan-module-ligne')
    expect(nom).toHaveTextContent('Aucun panneau choisi sur ce toit')
    expect(ligne).toHaveTextContent(`Module par défaut · ${ligneModule(MODULE_PAR_DEFAUT_ATELIER)}`)
    await waitFor(() => expect(carte.querySelector('[data-zone="module-etude"]'))
      .toHaveTextContent('L’étude électrique utilise : Canadien Solar 710 Wc.'))
    expect(nom).toHaveTextContent('Aucun panneau choisi sur ce toit')
    expect(ligne).toHaveTextContent(`Module par défaut · ${ligneModule(MODULE_PAR_DEFAUT_ATELIER)}`)
    expect(nom).not.toHaveTextContent('Module par défaut') // le défaut n'est jamais présenté comme le panneau du projet
    expect(carte.querySelector('[data-zone="aucun-module"]')).toHaveTextContent('Choisissez le panneau de ce toit dans la liste.')
  })

  it('module : plusieurs modèles dans l’étude électrique → « N modèles » ; le module écrit sur le pan prime', async () => {
    servir({ materiel: { module: null, modules_par_pan: [
      { pan: 'A', designation: 'Canadien Solar 710 Wc', produit_id: 1 }, { pan: 'B', designation: 'Jinko 580 Wc', produit_id: null },
    ] } })
    monterConstructeur()
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    await waitFor(() => expect(carte.querySelector('[data-zone="module-etude"]'))
      .toHaveTextContent('L’étude électrique utilise : 2 modèles (Canadien Solar 710 Wc · Jinko 580 Wc).'))
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    await waitFor(() => expect(carte.querySelector('.cal-pan-module-nom')).toHaveTextContent('Jinko Tiger Neo 580 Wc'), { timeout: 3000 })
    expect(carte.querySelector('[data-zone="aucun-module"]')).toBeNull()
  })

  it('ouvrir l’étape est en LECTURE SEULE : aucun input/change/click envoyé au constructeur, même après les sondages', async () => {
    const { racine } = monterConstructeur({ besoin: '60', panneaux: '55 × 720 W', note: '60 au devis — seuls 55 tiennent.' })
    const recus = []
    for (const type of ['input', 'change', 'click']) racine.addEventListener(type, (e) => recus.push(`${type}:${e.target.id || e.target.outerHTML.slice(0, 40)}`), true)
    servir({ resultat: { simule: true, simulation_perimee: false, production: { total: { p50_kwh: 1, complete: true } }, pose: {} },
      materiel: { module: null, modules_par_pan: [{ pan: 'A', designation: 'Canadien Solar 710 Wc', produit_id: 1 }] } })
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalled())
    await new Promise((r) => { setTimeout(r, 1300) }) // > 3 sondages de 400 ms
    // ACAL1981 — un seul geste, d'AFFICHAGE : la carte d'accès allumée à l'entrée (jamais sérialisée, rien de modifié).
    expect(recus).toEqual(['click:rp9-heatmap-toggle'])
    expect(document.getElementById('rp9-need-input').value).toBe('60')
    expect(document.getElementById('rp9-pan-module-select').value).toBe('')
  })

  it('sens de pose : trois segments branchés sur data-orient ; le re-clic sur le sens posé ne part pas', () => {
    const { espion } = monterConstructeur({ orient: 'portrait' })
    const paysage = espion('[data-orient="landscape"]')
    const portrait = espion('[data-orient="portrait"]')
    const auto = espion('[data-orient="auto"]')
    rendre()
    const groupe = within(screen.getByTestId('cal-panneaux-sens-pose'))
    expect(groupe.getAllByRole('button').map((b) => b.textContent)).toEqual(['Portrait', 'Paysage', 'Au mieux'])
    expect(groupe.getByRole('button', { name: 'Portrait' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(groupe.getByRole('button', { name: 'Portrait' }))
    expect(portrait).not.toHaveBeenCalled()
    fireEvent.click(groupe.getByRole('button', { name: 'Paysage' }))
    expect(paysage).toHaveBeenCalledTimes(1)
    fireEvent.click(groupe.getByRole('button', { name: 'Au mieux' }))
    expect(auto).toHaveBeenCalledTimes(1)
  })

  it('alerte d’ombrage : absente sans avis du constructeur', () => {
    monterConstructeur()
    rendre()
    expect(screen.queryByTestId('cal-panneaux-ombre')).toBeNull()
  })

  it('alerte d’ombrage : « Retirer ces 2 panneaux » part au vrai bouton, « Garder » la range', async () => {
    const { espion } = monterConstructeur({ ombre: 2 })
    const retirer = espion('#rp9-solar-access-apply')
    rendre()
    const alerte = screen.getByTestId('cal-panneaux-ombre')
    expect(alerte).toHaveTextContent('2 panneaux à l’ombre')
    expect(alerte).toHaveTextContent('Ils reçoivent moins de soleil que le seuil réglé par votre société.')
    fireEvent.click(within(alerte).getByRole('button', { name: 'Retirer ces 2 panneaux' }))
    expect(retirer).toHaveBeenCalledTimes(1)
    fireEvent.click(within(alerte).getByRole('button', { name: 'Garder' }))
    await waitFor(() => expect(screen.queryByTestId('cal-panneaux-ombre')).toBeNull())
    expect(retirer).toHaveBeenCalledTimes(1)
  })

  // ACAL1728 (reprise d'ACAL869) — l'étape guidée n'offrait ni l'alignement des rangées ni Annuler / Rétablir dans son panneau.
  it('ACAL1728 — « Personnaliser la disposition » : alignement des rangées, Annuler et Rétablir renvoyés aux vrais contrôles', () => {
    const { racine, espion } = monterConstructeur()
    racine.insertAdjacentHTML('beforeend', `
      <button id="rp9-layout-undo">u</button><button id="rp9-layout-redo" disabled>r</button>
      <select id="rp9-alignement-select"><option value="gauche">Gauche (pavage d’origine)</option>
        <option value="centre">Centre</option><option value="droite">Droite</option>
        <option value="justifie">Justifié (jeux égaux)</option></select>`)
    const annuler = espion('#rp9-layout-undo')
    const aligne = espion('#rp9-alignement-select', 'change')
    rendre()
    const bloc = screen.getByTestId('cal-panneaux-disposition')
    expect(within(bloc).getByText('Personnaliser la disposition')).toBeInTheDocument()
    const rangees = within(bloc).getByRole('group', { name: 'Alignement des rangées' })
    expect(within(rangees).getAllByRole('button').map((b) => b.textContent)).toEqual(['Gauche', 'Centre', 'Droite', 'Justifié'])
    fireEvent.click(within(rangees).getByRole('button', { name: 'Centre' }))
    expect(document.getElementById('rp9-alignement-select').value).toBe('centre')
    expect(aligne).toHaveBeenCalledTimes(1)
    fireEvent.click(within(bloc).getByRole('button', { name: 'Annuler' }))
    expect(annuler).toHaveBeenCalledTimes(1)
    expect(within(bloc).getByRole('button', { name: 'Rétablir' })).toBeDisabled() // le vrai contrôle est désactivé
  })
})

describe('étape Panneaux — sur la carte', () => {
  it('T4-X7-002 — la part servie (énergie autoconsommée ÷ consommation de la conception) porte le nom de la tuile des Résultats', () => {
    // Le constructeur de l'ERP montre `chiffrage.couverture_pct` : la MÊME grandeur que « De la consommation » des Résultats.
    // « Production ÷ consommation » la nommait mal (≈ 76 % pour une pose dont production ÷ consommation fait 94 %).
    monterConstructeur()
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('De la consommation')
    expect(puce).toHaveTextContent('≈ 82 %')
    expect(puce).not.toHaveTextContent('Production ÷ consommation')
  })

  it('T4-X7-002 — écart réel trouvé par la simulation (`autre_installation`) : aucune part de la conception', async () => {
    servir({ resultat: { simule: false, autoconsommation: { taux_source: 'autre_installation', taux_couverture: 0.474 } } })
    monterConstructeur()
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    await waitFor(() => expect(within(noeudCarte).getByTestId('cal-sur-carte-resume')).not.toHaveTextContent('De la consommation'))
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).not.toHaveTextContent('82 %')
    expect(document.body).not.toHaveTextContent('82 % de la consommation')
  })

  // Revue du 25/11 — `'pose'` = aucun taux de conception au moment de la simulation (conception pas encore complète,
  // pas de lead…) ; `'conception'` = ses taux ; aucune clé = résultat rangé d'avant : la part servie reste dite.
  for (const [cas, autoconsommation] of [
    ['aucun taux de conception (`pose`)', { taux_source: 'pose', taux_couverture: 0.474 }],
    ['taux de la conception (`conception`)', { taux_source: 'conception', taux_couverture: 0.82 }],
    ['résultat rangé sans la clé', { taux_couverture: 0.82 }],
  ]) {
    it(`T4-X7-002 — ${cas} : la part servie de la conception reste dite`, async () => {
      servir({ resultat: { simule: false, autoconsommation } })
      monterConstructeur()
      rendre()
      await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
      await new Promise((r) => setTimeout(r, 50))
      const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
      expect(puce).toHaveTextContent('De la consommation')
      expect(puce).toHaveTextContent('≈ 82 %')
    })
  }

  /* ACAL1728 (reprise d'ACAL876) — aucun « ? » sur la barre de chiffres de l'étape guidée : chacun a le sien (phrase du
     registre servi), qui s'ouvre à Entrée comme à Espace. */
  it('ACAL1728 — un « ? » par chiffre de la barre, ouvert à Entrée et à Espace avec la phrase servie', async () => {
    const user = userEvent.setup()
    monterConstructeur()
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    const aides = () => within(puce).queryAllByRole('button', { name: 'Pourquoi ce chiffre ?' })
    await waitFor(() => expect(aides().map((b) => b.dataset.grandeur))
      .toEqual(['toit.reco_panneaux', 'toit.reco_puissance', 'toit.reco_production', 'toit.reco_couverture']))
    const phrase = (cle) => REGISTRE.find((e) => e.cle === cle).phrase
    aides()[3].focus()
    await user.keyboard('{Enter}')
    expect(await screen.findByText(phrase('toit.reco_couverture'))).toBeInTheDocument()
    await user.keyboard('{Escape}')
    aides()[0].focus()
    await user.keyboard(' ')
    expect(await screen.findByText(phrase('toit.reco_panneaux'))).toBeInTheDocument()
  })

  /* ACAL1749 — base e2e : « 148 panneaux » et « Puissance 0,00 kWc » pour le même calepinage (document sans `modules[]` :
     le constructeur n'écrit ni la puissance du module ni le « × W »). Jamais 0,00 : « module à choisir ». */
  it('ACAL1749 — panneaux posés sans module : la puissance dit « module à choisir », jamais 0,00 kWc', async () => {
    monterConstructeur({ besoin: '148', panneaux: '148 panneaux', kwc: '0,00 kWc', prod: '—', cover: '—',
      note: '148 posés — il reste de la place sur le toit, laissée libre.' })
    const { container } = rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('Panneaux148')
    expect(puce).toHaveTextContent('Puissancemodule à choisir')
    for (const ecran of [container, noeudCarte]) expect(ecran).not.toHaveTextContent('0,00') // le DOM du script, lui, le garde
    await waitFor(() => expect(document.querySelector('[data-zone="pose-actuelle"]'))
      .toHaveTextContent('Pose actuelle : 148 panneaux · module à choisir'))
  })

  it('puce : les quatre chiffres lus ; un chiffre absent est omis', () => {
    monterConstructeur()
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    for (const t of ['Panneaux', '12', 'Puissance', '6,96 kWc', 'Production · conception', '11 480 kWh / an', 'De la consommation', '≈ 82 %']) {
      expect(puce).toHaveTextContent(t)
    }
    cleanup()
    document.getElementById('faux-constructeur').remove()
    monterConstructeur({ prod: '—', cover: '—' })
    rendre()
    const reduite = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(reduite).not.toHaveTextContent('Production')
    expect(reduite).not.toHaveTextContent('De la consommation')
  })

  it('puce : production PUBLIÉE fraîche et complète → le libellé de l’étape Résultats, jamais « estimation »', async () => {
    servir({ resultat: { simule: true, simulation_perimee: false,
      production: { total: { p50_kwh: 52695, kwc: 25.56, complete: true } }, pose: { total_modules: 36, kwc: 25.56 } } })
    monterConstructeur({ panneaux: '36 × 710 W', kwc: '25,56 kWc', prod: '39 255 kWh/an', cover: '590 %' })
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    await waitFor(() => expect(puce).toHaveTextContent('Production la première année'))
    expect(puce).toHaveTextContent('52 695 kWh')
    expect(puce).toHaveTextContent('36')
    expect(puce).toHaveTextContent('25,56 kWc')
    expect(puce).not.toHaveTextContent('39 255') // l'estimation du navigateur n'est plus dite à côté
    expect(puce).not.toHaveTextContent('estimation')
  })

  it('puce : résultat publié INCOMPLET (traité comme périmé par le devis) → l’estimation, nommée « estimation »', async () => {
    servir({ resultat: { simule: true, simulation_perimee: false,
      production: { total: { p50_kwh: 52695, complete: false } }, pose: { total_modules: 36 } } })
    monterConstructeur()
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('Production · conception')
    expect(puce).not.toHaveTextContent('52 695')
  })

  it('puce : résultat périmé → l’estimation du constructeur, nommée « estimation »', async () => {
    servir({ resultat: { simule: true, simulation_perimee: true,
      production: { total: { p50_kwh: 52695, complete: true } }, pose: { total_modules: 36 } } })
    monterConstructeur()
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('Production · conception')
    expect(puce).toHaveTextContent('11 480 kWh / an')
    expect(puce).not.toHaveTextContent('52 695')
  })

  // T4-X2-002 (rejeu X9) — même pose, simulation faite : après « Enregistrer », la bande passait de « Production la première
  // année 6 926 kWh » à une autre phrase sans rien dire. La simulation périmée est DITE, avec le geste pour la refaire.
  it('T4-X2-002 — simulation périmée : la bande dit « Simulation à refaire » et où la relancer, une fois', async () => {
    servir({ resultat: { simule: true, simulation_perimee: true,
      production: { total: { p50_kwh: 6926, complete: true } }, pose: { total_modules: 6 } } })
    monterConstructeur({ prod: '—', cover: '—' })
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    await waitFor(() => expect(puce).toHaveTextContent(
      'Simulation à refaire : le toit ou un réglage de votre société a changé depuis le dernier calcul. Relancez-la à l’étape Les résultats.'))
    expect(puce.textContent.split('Simulation à refaire').length).toBe(2)
    expect(puce).not.toHaveTextContent('6 926')
  })

  it('ACAL2022 — pendant le dessin : « au prochain enregistrement » à la place de la production, jamais une estimation', () => {
    monterConstructeur({ prod: 'production au prochain enregistrement', cover: '—' })
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('Production')
    expect(puce).toHaveTextContent('au prochain enregistrement')
    expect(puce).not.toHaveTextContent('estimation')
    expect(puce).not.toHaveTextContent('kWh')
    expect(puce).toHaveTextContent('6,96 kWc') // seuls les panneaux et le kWc posés
  })

  // T4-X9-006 — la phrase débordait de la bande (une case de chiffre, sans retour à la ligne) et disait « 4,4 kWc » quand
  // la carte voisine disait « 4,40 kWc » : elle est lue sous les cartes du constructeur et dite UNE fois, en texte courant.
  it('M5 / T4-X9-006 — pose d’une autre taille : la bande dit la phrase en texte courant (deux décimales), aucune case « Production »', () => {
    monterConstructeur({ prod: '—', cover: '—', tailles: 'Production et économie calculées pour la conception du lead : 21,60 kWc — votre pose en compte 6,96 kWc.' })
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    const phrase = puce.querySelector('.cal-pan-puce-phrase')
    expect(phrase).toHaveTextContent('Production et économie calculées pour la conception du lead : 21,60 kWc — votre pose en compte 6,96 kWc.')
    expect(puce.textContent.split('calculées pour la conception').length).toBe(2) // une seule fois
    expect(puce).not.toHaveTextContent('prochain enregistrement')
    expect(puce).not.toHaveTextContent('Production · conception') // aucune production en kWh n'est servie
  })

  it('ACAL2022 (T4-X2-009) — champ au sol : la bande dit qu’elle compte CE pan et donne le total du site', () => {
    monterConstructeur({ panneaux: '5 × 710 W', kwc: '3,55 kWc' })
    // le document : le toit (5 × 710 W) + un champ au sol de 18 modules — comme la barre projet « 23 panneaux · 16,33 kWc »
    const builderApi = { serializeLayout: () => ({
      zones: [{ geometry: { count: 5, kwc: 3.55 } }],
      poseSurfaces: [{ kind: 'sol', id: 'sol-1', engine: { modules: 18 }, moduleWc: 710 }],
    }) }
    rendre({ builderApi })
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('Panneaux · ce pan')
    expect(puce).toHaveTextContent('Puissance · ce pan')
    expect(puce).toHaveTextContent('Total du site')
    expect(puce).toHaveTextContent('23 panneaux · 16,33 kWc')
    cleanup()
    document.getElementById('faux-constructeur').remove()
    monterConstructeur({ panneaux: '5 × 710 W', kwc: '3,55 kWc' }) // un seul pan : ni « ce pan » ni total (rien de plus que la barre)
    rendre({ builderApi: { serializeLayout: () => ({ zones: [{ geometry: { count: 5, kwc: 3.55 } }] }) } })
    const seul = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(seul).not.toHaveTextContent('ce pan')
    expect(seul).not.toHaveTextContent('Total du site')
  })

  it('ACAL2022 (T4-X2-001) — la carte « Couvrir la facture » nomme la conception ; la pose posée (autre module) se dit à part', async () => {
    // conception : 8 panneaux de 550 W = 4,40 kWc ; le pan porte un module de 710 W : 8 posés = 5,68 kWc, jamais « 8 panneaux 4,40 kWc » pour la pose.
    servir({ cible: { panneaux: 8, kwc: 4.4, module_wc: 550 } })
    monterConstructeur({ besoin: '8', panneaux: '8 × 710 W', kwc: '5,68 kWc', cover: '—', note: '' })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('8 panneaux · 4,40 kWc · Factures du lead'))
    expect(facture).toHaveAttribute('aria-pressed', 'true')
    expect(document.querySelector('[data-zone="pose-posee"]')).toHaveTextContent('Posé : 8 panneaux · 5,68 kWc')
    expect(facture).not.toHaveTextContent('5,68')
    // même module : aucune seconde phrase
    cleanup()
    document.getElementById('faux-constructeur').remove()
    monterConstructeur({ besoin: '8', panneaux: '8 × 550 W', kwc: '4,40 kWc', cover: '—', note: '' })
    rendre()
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('8 panneaux · 4,40 kWc · Factures du lead'))
    expect(document.querySelector('[data-zone="pose-posee"]')).toBeNull()
  })

  // ACAL1981 — la légende ne décrit que des panneaux TEINTÉS ; l'étape allume la carte d'accès à l'entrée (maquette).
  // Suites des écrans v2 (24/11) — éteinte d'un clic sur son titre, la carte d'accès ne se rallumait plus qu'en « Avancé » :
  // la légende disparaissait avec son bouton. Le BOUTON reste où la maquette pose la légende ; dégradé et bornes, eux, ne
  // décrivent que des panneaux teintés.
  it('aucun panneau teinté ⇒ ni dégradé ni bornes, mais le bouton « Ensoleillement de chaque panneau » reste ; l’entrée allume, la sortie rend', () => {
    const { espion } = monterConstructeur()
    const carte = espion('#rp9-heatmap-toggle')
    const { unmount } = rendre()
    expect(carte).toHaveBeenCalledTimes(1) // allumée à l'entrée (le faux script ne bascule pas : rien n'est teinté)
    const bloc = within(noeudCarte).getByTestId('cal-carte-soleil')
    expect(bloc.querySelector('.cal-pan-degrade')).toBeNull()
    expect(bloc).not.toHaveTextContent('Plein soleil')
    const titre = within(bloc).getByRole('button', { name: 'Ensoleillement de chaque panneau' })
    expect(titre).toHaveAttribute('aria-pressed', 'false')
    expect(titre).toHaveAttribute('title', 'Colorer les panneaux')
    fireEvent.click(titre) // se rallume d'ici, sans passer par « Avancé »
    expect(carte).toHaveBeenCalledTimes(2)
    document.getElementById('rp9-heatmap-toggle').setAttribute('aria-pressed', 'false')
    expect(within(noeudCarte).getByRole('button', { name: 'Lire la journée' })).toBeInTheDocument() // le lecteur reste
    document.getElementById('rp9-heatmap-toggle').setAttribute('aria-pressed', 'true')
    unmount()
    expect(carte).toHaveBeenCalledTimes(3) // éteinte en sortie : l'Électrique teint par chaîne (ACAL1621)
  })

  it('légende d’ensoleillement : titre, dégradé, bornes ; le titre est le vrai bouton « carte d’accès solaire »', () => {
    choisirPaletteAcces('atelier') // posée par le démarrage de l'atelier (useAtelierBoot), plus par l'étape
    const { espion } = monterConstructeur({ carte: true })
    const carte = espion('#rp9-heatmap-toggle')
    rendre()
    const bloc = within(noeudCarte).getByTestId('cal-carte-soleil')
    const titre = within(bloc).getByRole('button', { name: 'Ensoleillement de chaque panneau' })
    expect(bloc).toHaveTextContent('Ombragé')
    expect(bloc).toHaveTextContent('Plein soleil')
    // la rampe de la maquette (palette « atelier » posée par l'écran), lue de la MÊME fonction que la carte
    const fond = bloc.querySelector('.cal-pan-degrade').style.background
    expect(fond).toContain('rgb(31, 59, 115) 0%')
    expect(fond).toContain('rgb(245, 158, 11) 100%')
    expect(bloc).not.toHaveTextContent('Touchez le titre')
    fireEvent.click(titre)
    expect(carte).toHaveBeenCalledTimes(1)
  })

  it('lecteur du soleil : ▶, curseur d’heure, date et saisons renvoyés aux vrais contrôles', () => {
    const { espion } = monterConstructeur({ heureMax: '19' })
    const lecture = espion('#rp9-sun-play-day')
    const heure = espion('#rp9-sun-hour', 'input')
    const ete = espion('[data-sun-season="summer"]')
    rendre()
    const bloc = within(noeudCarte).getByTestId('cal-carte-soleil')
    expect(bloc).toHaveTextContent('21 décembre · 15 h')
    expect(bloc).toHaveTextContent('6 h')
    expect(bloc).toHaveTextContent('19 h') // bornes lues sur le vrai curseur
    expect(within(bloc).getByRole('slider').style.getPropertyValue('--cal-pan-rempli')).toBe('69%')
    fireEvent.click(within(bloc).getByRole('button', { name: 'Lire la journée' }))
    expect(lecture).toHaveBeenCalledTimes(1)
    fireEvent.change(within(bloc).getByRole('slider'), { target: { value: '9' } })
    expect(document.getElementById('rp9-sun-hour').value).toBe('9')
    expect(heure).toHaveBeenCalledTimes(1)
    expect(within(bloc).getByRole('button', { name: 'Hiver' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(bloc).getByRole('button', { name: 'Été' }))
    expect(ete).toHaveBeenCalledTimes(1)
  })
})

/* ACAL1519 — « K-COLONNE-ETROITE » : les grilles du panneau de droite (bloc « Total — toutes les zones »,
   bandeau de « Déplacer les panneaux ») suivent la largeur de la COLONNE (colonnes automatiques), jamais un
   point de rupture de la fenêtre. Prouvé sur le DOM RENDU. */
describe('panneau de droite — grilles suivant la colonne, pas la fenêtre (ACAL1519)', () => {
  const POINT_DE_RUPTURE = /(?:^|\s)(?:sm|md|lg|xl|2xl):grid-cols-/
  const AUTO = 'grid-cols-[repeat(auto-fit,minmax(7rem,1fr))]'

  it('le bloc « Total » et la pose rendent des grilles à colonnes automatiques sans classe de fenêtre', async () => {
    const { default: InspecteurBuilder } = await import('../../InspecteurBuilder.jsx')
    const { default: BuilderPose } = await import('../../BuilderPose.jsx')
    const { container } = render(<MemoryRouter><InspecteurBuilder estCalepinage /><BuilderPose /></MemoryRouter>)
    for (const id of ['rp9-areas-window', 'rp9-layout-panel']) {
      const grilles = [...container.querySelector(`#${id}`).querySelectorAll('dl')]
        .filter((el) => el.className.includes('grid-cols-['))
      expect(grilles.length, `${id} : grille à colonnes automatiques`).toBeGreaterThanOrEqual(1)
      for (const g of grilles) expect(g.className).toContain(AUTO)
    }
    // Le bloc « Affiner ma consommation » (#rp9-cons-window) vient du balisage partagé @roofpro : hors périmètre.
    for (const el of container.querySelectorAll('[class*="grid-cols-"]')) {
      if (el.closest('#rp9-cons-window')) continue
      expect(el.className, 'grille liée à la largeur de la fenêtre').not.toMatch(POINT_DE_RUPTURE)
    }
  })
})

/* T4-X8-008 — Expert au téléphone tactile : « Placement libre » demande une carte visible (« Cliquez sur le toit… (Échap) ») ;
   elle n'a que 63 px sous le tiroir. Le geste n'est pas offert, et UNE phrase dit où il se fait. Rien ne change ailleurs. */
describe('T4-X8-008 — le placement libre n’est pas offert au téléphone tactile', () => {
  afterEach(() => { delete window.matchMedia })
  const doubler = (tactile, telephone) => {
    window.matchMedia = (q) => ({
      matches: (q === '(hover: none) and (pointer: coarse)' && tactile) || (q === '(max-width: 639px)' && telephone),
      media: q, addEventListener() {}, removeEventListener() {},
    })
  }
  for (const [nom, tactile, telephone, offert] of [
    ['téléphone tactile', true, true, false], ['tablette tactile', true, false, true], ['petite fenêtre à la souris', false, true, true],
  ]) {
    it(`${nom} : placement libre ${offert ? 'offert' : 'non offert, la phrase le dit'}`, async () => {
      doubler(tactile, telephone)
      const { default: BuilderPose } = await import('../../BuilderPose.jsx')
      const { container } = render(<MemoryRouter><BuilderPose expert /></MemoryRouter>)
      expect(container.querySelector('#rp9-layout-mode-free').hidden).toBe(!offert)
      expect(container.querySelector('#rp9-free-add').hidden).toBe(!offert)
      const phrase = screen.queryByTestId('cal-placement-libre-ailleurs')
      if (offert) expect(phrase).toBeNull()
      else expect(phrase).toHaveTextContent(/^Le placement libre se fait sur une tablette ou au bureau\.$/)
    })
  }
})

describe('retraits du panneau de droite — règle CSS suivant la colonne (ACAL1519)', () => {
  it('.rp9-host .rp9-setbacks : colonnes automatiques, aucune règle de fenêtre ne la redéfinit', async () => {
    // (`?raw` rend '' sous vitest : la feuille est lue du disque puis chargée dans le DOM de test.)
    const { readFileSync } = await import('node:fs')
    const css = readFileSync(`${globalThis.process.cwd()}/src/styles/roofbuilder.css`, 'utf8')
    const style = document.createElement('style')
    style.textContent = css
    document.head.appendChild(style)
    try {
      const regles = [...style.sheet.cssRules]
      const bloc = regles.find((r) => r.selectorText === '.rp9-host .rp9-setbacks')
      expect(bloc, 'règle .rp9-host .rp9-setbacks').toBeTruthy()
      expect(bloc.cssText).toMatch(/auto-fit/)
      const enFenetre = regles.filter((r) => r.type === 4 /* CSSMediaRule */)
        .flatMap((m) => [...m.cssRules]).filter((r) => (r.selectorText || '').includes('.rp9-setbacks'))
      expect(enFenetre).toHaveLength(0)
    } finally {
      style.remove()
    }
  })
})

/* ACAL1524 / ACAL1443 — la feuille de l'atelier est chargée dans le DOM de test et lue par getComputedStyle. */
describe('feuille de l’atelier — boutons refusés et champs de la photo (ACAL1524, ACAL1443)', () => {
  let style
  beforeEach(async () => {
    const { readFileSync } = await import('node:fs')
    style = document.createElement('style')
    style.textContent = readFileSync(`${globalThis.process.cwd()}/src/styles/roofbuilder.css`, 'utf8')
    document.head.appendChild(style)
  })
  afterEach(() => { style.remove(); document.body.innerHTML = '' })

  it('ACAL1524 : un bouton rp9-btn désactivé se distingue d’un bouton actif, « Déplacer » compris', () => {
    document.body.innerHTML = `<div class="rp9-host">
      <button id="actif" class="rp9-btn">a</button><button id="off" class="rp9-btn" disabled>b</button>
      <button id="rp9-layout-toggle" disabled>c</button><button id="toggle-actif" class="x">d</button>
      <p id="motif" class="rp9-motif-refus">m</p></div>`
    const cs = (id) => getComputedStyle(document.getElementById(id))
    for (const id of ['off', 'rp9-layout-toggle']) {
      expect(cs(id).borderStyle, id).toBe('dashed')
      expect(cs(id).cursor, id).toBe('not-allowed')
      expect(cs(id).background, id).toContain('--muted')
      expect(cs(id).color, id).toContain('--muted-foreground')
      expect(cs(id).opacity, `${id} : l'opacité seule rendait le refus invisible`).toBe('1')
    }
    expect(cs('actif').borderStyle).not.toBe('dashed')
    expect(cs('actif').cursor).not.toBe('not-allowed')
    expect(cs('motif').color).toContain('--muted-foreground')
  })

  it('ACAL1443 : .rp9-image-capture-input est un vrai champ (bordure, fond, 44 px)', () => {
    document.body.innerHTML = '<div class="rp9-host"><input id="champ" class="rp9-image-capture-input"></div>'
    const c = getComputedStyle(document.getElementById('champ'))
    // jsdom ne déplie pas `border: 1px solid var(--…)` : on lit la règle qui s'applique à l'élément.
    const regle = [...style.sheet.cssRules].find((r) => r.selectorText && document.getElementById('champ').matches(r.selectorText))
    expect(regle, 'règle appliquée au champ').toBeTruthy()
    expect(regle.style.getPropertyValue('border')).toMatch(/^1px solid/)
    expect(c.background).toContain('--muted')
    expect(parseFloat(c.minHeight)).toBeGreaterThanOrEqual(2.75)
  })

  it('ACAL2030 — Expert : chaque champ du constructeur a un libellé et le cadre du champ du Guidé', () => {
    document.body.innerHTML = `<div class="rp9-host cal-coque" data-expert="1">
      <div id="rp9-studio"><form id="rp9-search"><label for="rp9-address" class="sr-only">Adresse</label>
        <div><input id="rp9-address" type="text">
          <label class="rp9-image-capture">Date de la photo (AAAA-MM-JJ) <input id="rp9-image-date" type="text" class="rp9-image-capture-input"></label></div></form>
      <aside id="rp9-studio-inspecteur"><details id="rp9-chassis" open><summary>Avancé — châssis N × M</summary>
        <label class="flex min-h-11" for="rp9-chassis-rangs">Rangs par châssis<input type="text" id="rp9-chassis-rangs" class="rp9-input w-24"></label>
        <input data-cons-charge-champ="km_par_jour" aria-label="Kilomètres par jour"></details></aside></div></div>`
    // La DERNIÈRE règle de la feuille qui vise l'élément et déclare la propriété (jsdom ne déplie pas les raccourcis).
    const vise = (el, sel) => { try { return el.matches(sel) } catch { return false } } // pseudo-éléments inconnus de jsdom
    const valeur = (el, prop) => [...style.sheet.cssRules]
      .filter((r) => r.selectorText && vise(el, r.selectorText) && r.style.getPropertyValue(prop))
      .map((r) => r.style.getPropertyValue(prop)).pop()
    for (const champ of document.querySelectorAll('input')) {
      const nom = (champ.labels?.[0]?.textContent || champ.getAttribute('aria-label') || '').trim()
      expect(nom, `${champ.id || champ.outerHTML} : libellé`).not.toBe('')
      expect(valeur(champ, 'border'), `${nom} : cadre`).toBe('1px solid var(--cal-filet-fort)')
      expect(valeur(champ, 'background'), `${nom} : fond`).toBe('var(--cal-surface)')
      expect(valeur(champ, 'border-radius'), `${nom} : rayon`).toBe('var(--cal-rayon-champ)')
      expect(valeur(champ, 'min-height'), `${nom} : hauteur`).toBe('44px')
    }
    // L'adresse : son libellé « Adresse » est VISIBLE en Expert (plus seulement pour les lecteurs d'écran).
    expect(valeur(document.querySelector('label[for="rp9-address"]'), 'position')).toBe('static')
    // Guidé : rien ne change (le cadre est celui de l'Expert et de la feuille « Avancé » seulement).
    document.querySelector('.cal-coque').dataset.expert = '0'
    expect(valeur(document.getElementById('rp9-chassis-rangs'), 'background')).not.toBe('var(--cal-surface)')
  })
})

/* ACAL1340 — la palette d'ensoleillement n'est PAS posée par l'étape Panneaux : le démarrage de l'atelier
   (`useAtelierBoot`, couvert par ToitureDesign.calepinage.test.jsx « F6 ») la pose pour toute étape et pour le
   mode Expert. Charger le module de l'étape ne doit rien changer à la palette active (le site public garde
   la sienne). */
describe('palette d’ensoleillement — posée au démarrage, sans passer par l’étape', () => {
  it('charger l’étape Panneaux ne touche pas la palette active (rouge → vert du site conservé)', async () => {
    vi.resetModules()
    const moteur = await import('@rooflib/shadingEngine')
    moteur.choisirPaletteAcces('site')
    await import('./EtapePanneaux')
    expect(moteur.couleurAccesActive(0)).toEqual(moteur.solarAccessColorRGB(0))
  })
})

/* ACAL1818 / ACAL1906 — le curseur « Heure du soleil » se touche sur 44 px, QUEL QUE SOIT le pointeur (le relevé a mesuré 17 px sur
   un téléphone émulé qui n'était pas `pointer: coarse`) ; la piste dessinée garde ses 6 px et la carte sa hauteur. Le curseur
   est RENDU par l'étape ; les feuilles 49 + 50 + 52 sont chargées dans le DOM de test et lues par getComputedStyle. */
describe('curseur « Heure du soleil » — zone tactile (ACAL1818, ACAL1906)', () => {
  it('le curseur rendu a une zone de 44 px sans media query ; sa piste se dessine dans les 6 px du contenu ; la marge rend la hauteur', async () => {
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css', '52-etape-panneaux.css']
      .map((f) => readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/${f}`, 'utf8')).join('\n')
    document.head.appendChild(style)
    document.body.classList.add('cal-coque')
    try {
      monterConstructeur()
      rendre()
      const curseur = await screen.findByRole('slider', { name: 'Heure du soleil' })
      const c = getComputedStyle(curseur)
      const [haut, haut1, bas] = [c.height, c.paddingTop, c.paddingBottom].map(parseFloat)
      expect(haut, 'zone tactile').toBeGreaterThanOrEqual(44)
      expect(haut - haut1 - bas, 'la piste reste fine : 6 px de contenu').toBe(6)
      expect(c.backgroundClip).toBe('content-box')
      // La carte ne grandit pas : zone − marges négatives = la piste de 6 px d'avant.
      expect(haut + parseFloat(c.marginTop) + parseFloat(c.marginBottom)).toBe(6)
    } finally {
      style.remove()
      document.body.classList.remove('cal-coque')
    }
  })
})

/* ACAL1829 — l'étape Panneaux à sa maquette v2 : cartes de taille (Archivo, chiffres gras, choisie = filet bleu nuit sur
   papier), sens de pose à pictogrammes, légende 268 × 56, vignette du panneau, alerte « À surveiller », chiffres à unité
   réduite. Le panneau est RENDU ; les feuilles 49 + 50 + 52 sont chargées dans le DOM de test et lues par getComputedStyle. */
describe('ACAL1829 — l’étape Panneaux à sa maquette v2', () => {
  let style
  beforeEach(async () => {
    const { readFileSync } = await import('node:fs')
    style = document.createElement('style')
    style.textContent = ['49-jetons-v2.css', '50-coque-atelier.css', '52-etape-panneaux.css']
      .map((f) => readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/${f}`, 'utf8')).join('\n')
    document.head.appendChild(style)
    document.body.classList.add('cal-coque') // les feuilles de la coque visent `.cal-coque …`
  })
  afterEach(() => { style.remove(); document.body.classList.remove('cal-coque') })
  const cs = (el) => getComputedStyle(el)

  it('cartes de taille : titre Archivo, chiffres en gras, choisie sur papier ; l’autre carte blanche', async () => {
    monterConstructeur()
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    await waitFor(() => expect(facture).toHaveTextContent('12 panneaux · 6,96 kWc'))
    expect([...facture.querySelectorAll('b')].map((b) => b.textContent)).toEqual(['12', '6,96', '82 %'])
    expect(cs(facture.querySelector('.cal-pan-option-nom')).fontFamily).toBe('var(--font-display)')
    expect(cs(facture).borderRadius).toBe('14px')
    expect(facture).toHaveAttribute('aria-pressed', 'true')
    expect(cs(facture).background).toContain('--cal-choisi-fond')
    const max = screen.getByTestId('cal-panneaux-option-max')
    expect(cs(max).borderRadius).toBe('14px')
    expect(cs(max).background).toContain('--cal-surface')
    expect(cs(document.querySelector('.cal-pan-badge')).borderRadius).toBe('11px')
  })

  it('T4-X8-011 — la phrase de la conception se replie : ni troncature ni ligne unique sur une phrase qui porte un nombre', async () => {
    monterConstructeur({ besoin: '12' })
    document.getElementById('rp9-pan-module-select').value = 'produit-1'
    const catalogue = [{ ...CATALOGUE[0], module: { ...CATALOGUE[0].module, pmaxWc: 710 } }]
    calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: {
      modules: catalogue, panneaux_selon_watt: { 710: 6 }, kwc_selon_watt: { 710: 4.26 } } })
    calepinageApi.calepinages.cibleFactures.mockResolvedValue({ data: {
      cible_factures: { panneaux: 8, kwc: 4.4, module_wc: 550 }, refus: '', calcul_en_cours: false } })
    rendre()
    const facture = screen.getByTestId('cal-panneaux-option-facture')
    const phrase = await waitFor(() => {
      const el = facture.querySelector('[data-zone="conception-du-lead"]')
      expect(el).not.toBeNull()
      return el
    })
    for (const el of [phrase, ...facture.querySelectorAll('.cal-pan-option-ligne > span')]) {
      expect(el.className).not.toMatch(/truncate|ellipsis/)
    }
    expect(cs(phrase).whiteSpace).not.toBe('nowrap')
    expect(cs(phrase).textOverflow).not.toBe('ellipsis')
    expect(cs(phrase).overflow).not.toBe('hidden')
    expect(phrase.closest('.cal-pan-option-ligne')).toBeNull() // jamais dans la ligne des chiffres (ses morceaux ne se coupent pas)
  })

  it('sens de pose : pictogrammes portrait et paysage, « Au mieux » sans ; segments de 44 px sur piste v2', () => {
    monterConstructeur()
    rendre()
    const groupe = screen.getByRole('group', { name: 'Sens de pose' })
    const [portrait, paysage, auto] = within(groupe).getAllByRole('button')
    expect(portrait.querySelector('svg')).not.toBeNull()
    expect(paysage.querySelector('svg')).not.toBeNull()
    expect(auto.querySelector('svg')).toBeNull()
    expect(cs(portrait).height).toBe('44px')
    expect(cs(groupe).borderRadius).toBe('var(--cal-rayon-tuile)')
  })

  it('légende : 268 × 56, rayon 18, mots seuls (aucun accès par module n’est servi, aucun chiffre inventé)', () => {
    monterConstructeur({ carte: true })
    rendre()
    const legende = document.querySelector('.cal-pan-legende')
    expect(cs(legende).width).toBe('268px')
    expect(cs(legende).minHeight).toBe('56px')
    expect(cs(legende).borderRadius).toBe('var(--cal-rayon-outils)')
    expect(legende).toHaveTextContent('Ensoleillement de chaque panneauOmbragéPlein soleil')
    expect(legende.textContent).not.toMatch(/\d/)
  })

  it('modèle : vignette du panneau à gauche du nom, carte de 64 px', async () => {
    monterConstructeur()
    rendre()
    const bouton = screen.getByRole('button', { name: /Module par défaut|Panneau/ })
    const vignette = bouton.querySelector('.cal-pan-vignette')
    expect(vignette).not.toBeNull()
    expect(vignette.compareDocumentPosition(bouton.querySelector('.cal-pan-module-texte')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(cs(bouton).height).toBe('64px')
    expect(cs(bouton).borderRadius).toBe('12px')
  })

  it('alerte d’ombrage : carte « à surveiller » aux jetons, deux pastilles de panneaux, boutons de 44 px', () => {
    monterConstructeur({ ombre: 2 })
    rendre()
    const alerte = screen.getByTestId('cal-panneaux-ombre')
    expect(cs(alerte).background).toContain('--cal-surveiller-fond')
    expect(alerte.querySelectorAll('.cal-pan-alerte-pastille > span')).toHaveLength(2)
    expect(cs(within(alerte).getByRole('button', { name: 'Garder' })).height).toBe('44px')
  })

  it('puce : l’unité des chiffres est réduite et grise, le texte reste celui du constructeur', () => {
    monterConstructeur()
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    const puissance = [...puce.querySelectorAll('.cal-indicateur')].find((n) => n.textContent.startsWith('Puissance'))
    expect(puissance.querySelector('.cal-unite')).toHaveTextContent('kWc')
    expect(puissance.querySelector('.cal-indicateur-valeur')).toHaveTextContent('6,96 kWc')
    expect(cs(puissance.querySelector('.cal-unite')).fontSize).toBe('0.8125rem')
    expect(cs(puce).height).toBe('62px')
  })
})

/* T3-VAGUEC / T3-VAGUEC2 (S3) — l'en-tête de pose (« 16 panneaux · 11,36 kWc · 1 onduleur 5 kW ») lisait le résultat SERVI :
   après un changement de module ou des retraits, il restait sur l'ancienne pose jusqu'à l'enregistrement. Tant que la scène
   n'est pas enregistrée, il dit la pose que la carte AFFICHE (lue sur le constructeur, comme « Pose actuelle »). */
describe('en-tête de pose — suit la pose affichée tant que la scène n’est pas enregistrée', () => {
  const servi = { pose: { total_modules: 16, kwc: 11.36 }, electrique: { onduleurs: [{ nombre: 1, taille_kw: 5 }] } }

  it('sousTitrePose : la pose vivante prime sur la servie ; un retrait total dit « Aucun panneau posé »', () => {
    expect(sousTitrePose(servi)).toBe('16 panneaux · 11,36 kWc · 1 onduleur 5 kW')
    expect(sousTitrePose(servi, { panneaux: 5, kwc: '3,60 kWc' })).toBe('5 panneaux · 3,60 kWc · 1 onduleur 5 kW')
    expect(sousTitrePose(servi, { panneaux: 1, kwc: null })).toBe('1 panneau · 1 onduleur 5 kW') // rien d’inventé : pas de kWc lu
    expect(sousTitrePose(servi, { panneaux: 0, kwc: '0,00 kWc' })).toBe('Aucun panneau posé')
    expect(sousTitrePose(servi, null)).toBe('16 panneaux · 11,36 kWc · 1 onduleur 5 kW')
  })

  /* T4-U4-016 / T4-U4-024 — UN compte : pans + champ au sol + ombrière, lu sur le DOCUMENT du constructeur (la carte
     « Recommandation » ne compte que le pan), suivi quand le document change — pas seulement après un rechargement. */
  it('T4-U4-016 / T4-U4-024 — avec le constructeur : pan 12 + sol 28 + ombrière 16 = « 56 panneaux · 39,76 kWc », suivi', async () => {
    monterConstructeur({ panneaux: '12 × 710 W', kwc: '8,52 kWc' })
    const pan = { id: 'z1', vertices: [[0, 0], [1, 0], [1, 1]], geometry: { count: 12, kwc: 8.52 } }
    const sol = { kind: 'sol', id: 'sol-1', moduleWc: 710, engine: { modules: 28 } }
    const omb = { kind: 'ombriere', id: 'omb-1', moduleWc: 710, engine: { modules: 16 } }
    let doc = { zones: [pan], poseSurfaces: [sol] }
    const builderApi = { serializeLayout: () => doc }
    const { result } = renderHook(() => usePoseVivante(true, builderApi))
    expect(result.current).toEqual({ panneaux: 40, kwc: '28,40 kWc' })
    doc = { zones: [pan], poseSurfaces: [sol, omb] } // « Enregistrer l'ombrière » : la carte du pan ne bouge pas
    await waitFor(() => expect(result.current).toEqual({ panneaux: 56, kwc: '39,76 kWc' }), { timeout: 3000 })
    expect(sousTitrePose({ pose: { total_modules: 54, kwc: 38.34 } }, result.current)).toBe('56 panneaux · 39,76 kWc')
  })

  it('usePoseVivante : lit la carte du constructeur, la suit quand le module change, se tait hors scène modifiée', async () => {
    monterConstructeur({ panneaux: '16 × 710 W', kwc: '11,36 kWc' })
    const { result, rerender } = renderHook(({ actif }) => usePoseVivante(actif), { initialProps: { actif: true } })
    expect(result.current).toEqual({ panneaux: 16, kwc: '11,36 kWc' })
    act(() => {
      document.getElementById('rp9-reco-panels').textContent = '5 × 720 W'
      document.getElementById('rp9-reco-kwc').textContent = '3,60 kWc'
    })
    await waitFor(() => expect(result.current).toEqual({ panneaux: 5, kwc: '3,60 kWc' }))
    act(() => { document.getElementById('rp9-reco-panels').textContent = '—' }) // la carte n'affirme plus rien
    await waitFor(() => expect(result.current).toBeNull())
    rerender({ actif: false })
    expect(result.current).toBeNull()
  })
})

/* T4-X7-012 (décision du 25/11 : « Add a button ») — en Guidé, retirer un panneau demandait de passer en Expert
   (« Un de moins »). Le bouton renvoie au script le besoin = pose affichée − 1 (le script choisit le panneau) ; grisé
   avec sa raison quand rien ne peut partir. */
describe('étape Panneaux — « Retirer un panneau » (T4-X7-012)', () => {
  it('renvoie au script la pose − 1', () => {
    const { espion } = monterConstructeur({ besoin: '12', panneaux: '12 × 580 W', kwc: '6,96 kWc' })
    const surInput = espion('#rp9-need-input', 'input')
    rendre()
    const bouton = screen.getByTestId('cal-panneaux-retirer-un')
    expect(bouton).toHaveTextContent('Retirer un panneau')
    expect(bouton).toBeEnabled()
    fireEvent.click(bouton)
    expect(surInput).toHaveBeenCalledTimes(1)
    expect(document.getElementById('rp9-need-input').value).toBe('11')
  })

  it('« le plus de panneaux » : part de la pose (9), jamais du besoin de la facture affiché (12)', () => {
    monterConstructeur({ besoin: '12', lePlus: true, panneaux: '9 × 710 W', kwc: '6,39 kWc',
      note: 'Le plus de panneaux possible : 9 posés.' })
    rendre()
    fireEvent.click(screen.getByTestId('cal-panneaux-retirer-un'))
    expect(document.getElementById('rp9-need-input').value).toBe('8')
  })

  it('grisé avec sa raison : lecture seule, aucun panneau, un seul panneau, aucune taille choisie', () => {
    const cas = [
      [{}, { lectureSeule: true }, 'Ce calepinage est en lecture seule : la pose ne se modifie pas ici.'],
      [{ panneaux: '—', kwc: '—' }, {}, 'Aucun panneau posé à retirer.'],
      [{ besoin: '1', panneaux: '1 × 580 W', kwc: '0,58 kWc' }, {}, 'Il reste un seul panneau sur ce pan : il ne se retire pas ici.'],
      [{ besoin: '—', besoinDesactive: true }, {}, 'Choisissez d’abord une taille ci-dessus.'],
    ]
    for (const [constructeur, props, raison] of cas) {
      const { espion } = monterConstructeur(constructeur)
      const surInput = espion('#rp9-need-input', 'input')
      rendre(props)
      const bouton = screen.getByTestId('cal-panneaux-retirer-un')
      expect(bouton).toBeDisabled()
      expect(bouton).toHaveAttribute('title', raison)
      expect(document.querySelector('[data-zone="retrait-impossible"]')).toHaveTextContent(raison)
      fireEvent.click(bouton)
      expect(surInput).not.toHaveBeenCalled()
      cleanup()
      document.getElementById('faux-constructeur')?.remove()
      noeudCarte?.remove()
    }
  })
})
