/* Nouveau fichier car : écran neuf (EtapePanneaux.jsx, maquettes Panneaux et Tablette), aucun module de test voisin.
   Le script du toit ne tourne pas sous vitest : on pose dans le document les contrôles `rp9-*` qu'il écrit
   (mêmes ids, mêmes éléments) et l'on prouve ce que React rend — structure, ordre, libellés mot pour mot,
   hooks — et que chaque geste part au VRAI contrôle ; les replis honnêtes (sans facture, sans avis d'ombrage). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, renderHook, screen, cleanup, within, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: { calepinages: {
    designContext: vi.fn(), cibleFactures: vi.fn(), modulesDisponibles: vi.fn(), entreeElectrique: vi.fn(), resultat: vi.fn(),
  } },
}))

import { MODULE_PAR_DEFAUT_ATELIER } from '@roofpro/moduleSelect'
import { choisirPaletteAcces } from '@rooflib/shadingEngine'
import calepinageApi from '../../../../../api/calepinageApi'
import { exempleContrat, reponseContrat } from '../../../../../test/fixtures/contractSamples'
import { ContexteCoque } from '../contexteCoque'
import { sousTitrePose } from '../projet'
import EtapePanneaux from './EtapePanneaux'
import { usePoseVivante } from './panneaux/constructeur'
import { jourMois, ligneModule } from './panneaux/formats'
import { lireServi, oublierLecturesServies } from './panneaux/lectures'

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
    <input id="rp9-need-input" value="${c.besoin}" ${c.besoinDesactive ? 'disabled' : ''}>
    <p id="rp9-need-note">${c.note}</p>
    <p id="rp9-reco-panels">${c.panneaux}</p><p id="rp9-reco-kwc">${c.kwc}</p>
    <p id="rp9-reco-prod">${c.prod}</p><p id="rp9-reco-cover">${c.cover}</p>
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
    <button id="rp9-heatmap-toggle" aria-pressed="false">carte</button>
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
    await waitFor(() => expect(facture).toHaveTextContent('12 panneaux · 6,96 kWc · ≈ 144 % de la consommation'), { timeout: 3000 })
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
    await waitFor(() => expect(facture).toHaveTextContent('Couvrir la factureRecommandé1 panneau · 0,71 kWc · sur 6 nécessaires'))
    expect(facture).not.toHaveTextContent('4,26')
    expect(facture).not.toHaveTextContent('6 panneaux')
    fireEvent.click(facture)
    expect(surInput).not.toHaveBeenCalled() // le besoin 6 est déjà la cible posée : rien à renvoyer, la pose reste 1
  })

  // ACAL1331 (D-ACAL-76) — calepinage vierge : le constructeur a posé la taille de la cible et l'a dite dans sa note ;
  // le Guidé la DIT sous « Combien de panneaux ? ». Le commercial ajuste (« + ») : la note change, la phrase part.
  it('ACAL1331 — la taille posée d’elle-même est dite ; ajustée, la phrase part', async () => {
    const phrase = 'Posé d’après la facture : 12 panneaux · 6,96 kWc — ajustez si besoin.'
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

  it('ni l’une ni l’autre : aucune carte choisie et « Pose actuelle : N panneaux · kWc »', async () => {
    monterConstructeur({ besoin: '30', panneaux: '30 × 580 W', kwc: '17,40 kWc', prod: '28 700 kWh/an', cover: '431 %',
      note: '30 posés — il reste de la place sur le toit, laissée libre.' })
    rendre()
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('Recommandé'))
    expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('cal-panneaux-option-max')).toHaveAttribute('aria-pressed', 'false')
    expect(document.querySelector('[data-zone="pose-actuelle"]')).toHaveTextContent('Pose actuelle : 30 panneaux · 17,40 kWc')
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
    expect(recus).toEqual([])
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
})

describe('étape Panneaux — sur la carte', () => {
  it('puce : les quatre chiffres lus ; un chiffre absent est omis', () => {
    monterConstructeur()
    rendre()
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    for (const t of ['Panneaux', '12', 'Puissance', '6,96 kWc', 'Production · estimation', '11 480 kWh / an', 'De la consommation', '≈ 82 %']) {
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
    expect(puce).toHaveTextContent('Production · estimation')
    expect(puce).not.toHaveTextContent('52 695')
  })

  it('puce : résultat périmé → l’estimation du constructeur, nommée « estimation »', async () => {
    servir({ resultat: { simule: true, simulation_perimee: true,
      production: { total: { p50_kwh: 52695, complete: true } }, pose: { total_modules: 36 } } })
    monterConstructeur()
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    const puce = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(puce).toHaveTextContent('Production · estimation')
    expect(puce).toHaveTextContent('11 480 kWh / an')
    expect(puce).not.toHaveTextContent('52 695')
  })

  it('légende d’ensoleillement : titre, dégradé, bornes ; le titre est le vrai bouton « carte d’accès solaire »', () => {
    choisirPaletteAcces('atelier') // posée par le démarrage de l'atelier (useAtelierBoot), plus par l'étape
    const { espion } = monterConstructeur()
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
    monterConstructeur()
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
