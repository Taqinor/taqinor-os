/* Nouveau fichier car : écran neuf (EtapePanneaux.jsx, maquettes Panneaux et Tablette), aucun module de test voisin.
   Le script du toit ne tourne pas sous vitest : on pose dans le document les contrôles `rp9-*` qu'il écrit
   (mêmes ids, mêmes éléments) et l'on prouve ce que React rend — structure, ordre, libellés mot pour mot,
   hooks — et que chaque geste part au VRAI contrôle ; les replis honnêtes (sans facture, sans avis d'ombrage). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: { calepinages: { designContext: vi.fn(), modulesDisponibles: vi.fn(), entreeElectrique: vi.fn(), resultat: vi.fn() } },
}))

import { MODULE_PAR_DEFAUT_ATELIER } from '@roofpro/moduleSelect'
import calepinageApi from '../../../../../api/calepinageApi'
import { ContexteCoque } from '../contexteCoque'
import EtapePanneaux from './EtapePanneaux'
import { jourMois, ligneModule } from './panneaux/formats'

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

/** Les réponses servies : design-context (lead, taille des factures), catalogue, entrée électrique, résultat. */
function servir({
  cible = { panneaux: 12, kwc: 6.96, module_wc: 580 }, motif = '',
  materiel = { module: null, modules_par_pan: [] }, resultat = { simule: false },
} = {}) {
  calepinageApi.calepinages.designContext.mockResolvedValue({
    data: { calepinage: { lead: 42 }, consommation_lead: { facture_mensuelle_mad: 900, motif }, cible_factures: cible },
  })
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

  it('module : pans sans module mais étude électrique qui en désigne un → état honnête, jamais le défaut du script', async () => {
    servir({ materiel: { module: null, modules_par_pan: [
      { pan: 'A', designation: 'Canadien Solar 710 Wc', produit_id: 1 }, { pan: 'B', designation: 'Canadien Solar 710 Wc', produit_id: 1 },
    ] } })
    const { racine } = monterConstructeur()
    racine.querySelector('#rp9-pan-module-mention').textContent =
      `${MODULE_PAR_DEFAUT_ATELIER.libelle} — aucun module du catalogue n’est posé sur ce site.`
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    await waitFor(() => expect(carte.querySelector('.cal-pan-module-nom')).toHaveTextContent('Aucun panneau choisi sur ce toit'))
    expect(carte.querySelector('.cal-pan-module-ligne')).toHaveTextContent('L’étude électrique utilise : Canadien Solar 710 Wc')
    expect(carte).not.toHaveTextContent('Module par défaut') // le défaut du script n'est pas présenté comme le panneau
    expect(carte.querySelector('[data-zone="aucun-module"]')).toHaveTextContent('Choisissez le panneau de ce toit dans la liste.')
  })

  it('module : plusieurs modèles dans l’étude électrique → « N modèles » ; le module écrit sur le pan prime', async () => {
    servir({ materiel: { module: null, modules_par_pan: [
      { pan: 'A', designation: 'Canadien Solar 710 Wc', produit_id: 1 }, { pan: 'B', designation: 'Jinko 580 Wc', produit_id: null },
    ] } })
    monterConstructeur()
    rendre()
    const carte = screen.getByTestId('cal-panneaux-module')
    await waitFor(() => expect(carte.querySelector('.cal-pan-module-ligne'))
      .toHaveTextContent('L’étude électrique utilise : 2 modèles (Canadien Solar 710 Wc · Jinko 580 Wc)'))
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
