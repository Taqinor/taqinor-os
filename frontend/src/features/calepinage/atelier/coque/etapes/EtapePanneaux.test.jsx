/* Nouveau fichier car : écran neuf (EtapePanneaux.jsx, maquettes Panneaux et Tablette), aucun module de test voisin.
   Le script du toit ne tourne pas sous vitest : on pose dans le document les contrôles `rp9-*` qu'il écrit
   (mêmes ids, mêmes éléments) et l'on prouve ce que React rend — structure, ordre, libellés mot pour mot,
   hooks — et que chaque geste part au VRAI contrôle ; les replis honnêtes (sans facture, sans avis d'ombrage). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: { calepinages: { get: vi.fn(), modulesDisponibles: vi.fn() } },
}))

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
    <input id="rp9-sun-hour" type="range" min="6" max="18" value="${c.heure}">
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

beforeEach(() => {
  calepinageApi.calepinages.get.mockResolvedValue({ data: { lead: { id: 42 } } })
  calepinageApi.calepinages.modulesDisponibles.mockResolvedValue({ data: { modules: CATALOGUE } })
})
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
    for (const libelle of ['Couvrir la facture', 'Recommandé', 'Le plus de panneaux', 'Portrait', 'Paysage', 'Au mieux']) {
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

  it('« Couvrir la facture » : choisie, badge Recommandé, chiffres lus', () => {
    monterConstructeur()
    rendre()
    const carte = screen.getByTestId('cal-panneaux-option-facture')
    expect(carte).toHaveAttribute('aria-pressed', 'true')
    expect(carte).toHaveTextContent('Recommandé')
    expect(carte).toHaveTextContent('12 panneaux · 6,96 kWc · 82 % de la facture')
    expect(screen.getByTestId('cal-panneaux-option-max')).toHaveAttribute('aria-pressed', 'false')
  })

  it('« Le plus de panneaux » pose le plafond sur le vrai champ, puis « Couvrir la facture » rétablit le besoin', async () => {
    const { espion } = monterConstructeur()
    const surInput = espion('#rp9-need-input', 'input')
    rendre()
    fireEvent.click(screen.getByTestId('cal-panneaux-option-max'))
    expect(document.getElementById('rp9-need-input').value).toBe('400')
    expect(surInput).toHaveBeenCalledTimes(1)
    // le script a posé tout ce qui tient : 22 panneaux
    document.getElementById('rp9-reco-panels').textContent = '22 × 580 W'
    document.getElementById('rp9-reco-kwc').textContent = '12,76 kWc'
    document.getElementById('rp9-reco-cover').textContent = '131 %'
    await waitFor(() => expect(screen.getByTestId('cal-panneaux-option-max'))
      .toHaveTextContent('22 panneaux · 12,76 kWc · dépasse la consommation'), { timeout: 3000 })
    expect(screen.getByTestId('cal-panneaux-option-max')).toHaveAttribute('aria-pressed', 'true')
    // l'autre carte garde ses chiffres d'avant (mémoire de l'option posée tant qu'elle l'était)
    expect(screen.getByTestId('cal-panneaux-option-facture')).toHaveTextContent('12 panneaux · 6,96 kWc · 82 % de la facture')
    fireEvent.click(screen.getByTestId('cal-panneaux-option-facture'))
    expect(document.getElementById('rp9-need-input').value).toBe('12')
  })

  it('sans facture : « Couvrir la facture » grisée avec la raison servie et le lien vers le lead, jamais un besoin inventé', async () => {
    monterConstructeur({
      besoin: '—', besoinDesactive: true, panneaux: '22 × 580 W', kwc: '12,76 kWc', cover: '—',
      note: 'Indiquez votre facture pour dimensionner le nombre de panneaux.',
    })
    rendre()
    const carte = screen.getByTestId('cal-panneaux-option-facture')
    expect(carte).toBeDisabled()
    expect(carte).not.toHaveTextContent('Recommandé')
    expect(carte).not.toHaveTextContent(/\d/)
    expect(carte.parentElement).toHaveTextContent('Indiquez votre facture pour dimensionner le nombre de panneaux.')
    // tout ce qui tient est déjà posé : « Le plus de panneaux » est l'option en vigueur
    expect(screen.getByTestId('cal-panneaux-option-max')).toHaveAttribute('aria-pressed', 'true')
    const lien = await screen.findByRole('link', { name: 'Renseigner la facture du lead' })
    expect(lien).toHaveAttribute('href', '/crm/leads/42')
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
    for (const t of ['Panneaux', '12', 'Puissance', '6,96 kWc', 'Production · estimation', '11 480 kWh / an', 'De la facture', '82 %']) {
      expect(puce).toHaveTextContent(t)
    }
    cleanup()
    document.getElementById('faux-constructeur').remove()
    monterConstructeur({ prod: '—', cover: '—' })
    rendre()
    const reduite = within(noeudCarte).getByTestId('cal-sur-carte-resume')
    expect(reduite).not.toHaveTextContent('Production')
    expect(reduite).not.toHaveTextContent('De la facture')
  })

  it('légende d’ensoleillement : titre, dégradé, bornes ; le titre est le vrai bouton « carte d’accès solaire »', () => {
    const { espion } = monterConstructeur()
    const carte = espion('#rp9-heatmap-toggle')
    rendre()
    const bloc = within(noeudCarte).getByTestId('cal-carte-soleil')
    const titre = within(bloc).getByRole('button', { name: 'Ensoleillement de chaque panneau' })
    expect(bloc).toHaveTextContent('Ombragé')
    expect(bloc).toHaveTextContent('Plein soleil')
    expect(bloc.querySelector('.cal-pan-degrade').style.background).toContain('linear-gradient')
    fireEvent.click(titre)
    expect(carte).toHaveBeenCalledTimes(1)
  })

  it('lecteur du soleil : ▶, curseur d’heure, date et saisons renvoyés aux vrais contrôles', () => {
    const { espion } = monterConstructeur()
    const lecture = espion('#rp9-sun-play-day')
    const heure = espion('#rp9-sun-hour', 'input')
    const ete = espion('[data-sun-season="summer"]')
    rendre()
    const bloc = within(noeudCarte).getByTestId('cal-carte-soleil')
    expect(bloc).toHaveTextContent('21 décembre · 15 h')
    expect(bloc).toHaveTextContent('6 h')
    expect(bloc).toHaveTextContent('18 h')
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
