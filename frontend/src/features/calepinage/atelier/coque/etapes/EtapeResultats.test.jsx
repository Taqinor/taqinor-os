/* Nouveau fichier car : EtapeResultats.jsx est un composant neuf (écran de l'étape Résultats, maquettes
   Resultats / ResultatsIncomplet) sans module de test voisin ; les tests de ses pièces existantes
   restent dans production/*.test.jsx.
   Ce qui est prouvé : l'ordre et les libellés de la maquette, la règle « figure servie ou bloc omis »,
   aucun code technique à l'écran, le pied et son bouton, la carte « au plus » du résultat incomplet. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { exempleContrat } from '../../../../../test/fixtures/contractSamples'
import { formatNumber } from '../../../../../lib/format'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(), exportCsv: vi.fn(), simuler: vi.fn(), explications: vi.fn(),
      pertes: vi.fn(), enregistrerPertes: vi.fn(),
    },
    moteur: { resultat: vi.fn() },
    parametres: { get: vi.fn() },
  },
}))
vi.mock('../../../../../hooks/useHasPermission', () => ({ useHasPermission: () => true }))

import calepinageApi from '../../../../../api/calepinageApi'
import EtapeResultats from './EtapeResultats'
import PanneauPertesUnifie from '../../PanneauPertesUnifie'

const COMPLET = () => {
  const base = JSON.parse(JSON.stringify(exempleContrat('calepinage', 'calepinage_resultat', 'exemple')))
  base.cascade.postes_lisibles = {
    depart_kwh: 16800, arrivee_kwh: 13700, arrivee_pct: 81.4, total_pct: 18.6, motif_absence: '',
    postes: [
      { poste: 'ombres_proches', libelle: 'Ombres proches', perte_kwh: 504, perte_pct: 3.0, statut: 'compte', etapes: [] },
      { poste: 'poussiere', libelle: 'Poussière', perte_kwh: null, perte_pct: null, statut: 'non_compte', etapes: [] },
      { poste: 'chaleur', libelle: 'Chaleur', perte_kwh: 1075, perte_pct: 6.4, statut: 'compte', etapes: [] },
    ],
  }
  return base
}
const servir = (data) => calepinageApi.calepinages.resultat.mockResolvedValue({ data })
const Lieu = () => <p data-testid="lieu">{useLocation().search}</p>
const rendre = (props = {}) => render(
  <MemoryRouter><EtapeResultats calepinageId={1} {...props} /><Lieu /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.explications.mockResolvedValue({ data: { entrees: [] } })
  calepinageApi.calepinages.pertes.mockResolvedValue({ data: { postes: [], catalogue: [] } })
  calepinageApi.parametres.get.mockResolvedValue({ data: {} })
})
afterEach(() => { cleanup() })

describe('Étape Résultats — résultat complet (maquette Resultats)', () => {
  it('quatre tuiles dans l’ordre, puis « Mois par mois » et « Du soleil au réseau », puis le pied', async () => {
    servir(COMPLET())
    rendre()
    const tuiles = await screen.findByTestId('cal-resultats-tuiles')
    const labels = [...tuiles.querySelectorAll('.cal-res-tuile-label')].map((n) => n.textContent)
    expect(labels).toEqual(['Production la première année', 'De la consommation', 'Pertes au total', 'Écart avec PVGIS'])
    const valeurDe = (cle) => tuiles.querySelector(`[data-tuile="${cle}"] .cal-res-tuile-valeur`).textContent.replace(/\s/g, ' ')
    expect(valeurDe('heros')).toBe('13 000 kWh') // P50 servi
    expect(within(tuiles).getByText('1 505 kWh par kWc · année moyenne (P50)')).toBeInTheDocument()
    expect(valeurDe('couverture')).toBe('71 %') // taux_couverture 0,71
    const mois = screen.getByTestId('cal-resultats-mois')
    expect(within(mois).getByText('Mois par mois')).toBeInTheDocument()
    expect(mois.querySelectorAll('.cal-res-mois-noms span')).toHaveLength(12)
    expect(mois.querySelectorAll('.cal-res-mois-paire')).toHaveLength(12)
    const ordre = [tuiles, mois, screen.getByTestId('cal-resultats-pertes'), screen.getByTestId('cal-resultats-pied')]
    for (let i = 1; i < ordre.length; i += 1) {
      expect(ordre[i - 1].compareDocumentPosition(ordre[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
  })

  it('« Du soleil au réseau » : libellés lisibles servis, pourcentages servis, poste non compté omis, aucun code technique', async () => {
    servir(COMPLET())
    rendre()
    const carte = await screen.findByTestId('cal-resultats-pertes')
    const lignes = [...carte.querySelectorAll('.cal-res-poste')].map((li) => li.textContent)
    expect(lignes[0]).toContain('Soleil reçu par les panneaux')
    expect(lignes[1]).toMatch(/Ombres proches.*− 3,0 %/)
    expect(lignes[2]).toMatch(/Chaleur.*− 6,4 %/)
    expect(lignes[3]).toMatch(/Électricité produite.*81,4 %/)
    expect(carte).not.toHaveTextContent('Poussière')
    expect(document.body.textContent).not.toMatch(/CALX\d|ACAL\d|ohmique_dc|ombrage_proche/)
    expect(within(carte).getByText(/Voir les \d+ étapes/)).toBeInTheDocument()
  })

  it('tuile sans valeur servie : omise (jamais 0 ni tiret)', async () => {
    const d = COMPLET()
    d.autoconsommation.taux_couverture = null
    d.validation.ecart_pct = null
    servir(d)
    rendre()
    const tuiles = await screen.findByTestId('cal-resultats-tuiles')
    const labels = [...tuiles.querySelectorAll('.cal-res-tuile-label')].map((n) => n.textContent)
    expect(labels).toEqual(['Production la première année', 'Pertes au total'])
    expect(tuiles).not.toHaveTextContent('non calculée')
  })

  it('pied : année basse et dernière année servies ; bouton = action de l’étape, sinon URL de l’étape Documents', async () => {
    servir(COMPLET())
    const onClick = vi.fn()
    const { unmount } = rendre({ action: { libelle: 'Préparer les documents', onClick } })
    const pied = await screen.findByTestId('cal-resultats-pied')
    expect(pied).toHaveTextContent('Année basse (9 fois sur 10 au-dessus) : 11 900 kWh · Dans 2 ans : 12 929 kWh')
    fireEvent.click(within(pied).getByRole('button', { name: /Préparer les documents/ }))
    expect(onClick).toHaveBeenCalledTimes(1)
    unmount()
    servir(COMPLET())
    rendre()
    fireEvent.click(within(await screen.findByTestId('cal-resultats-pied')).getByRole('button', { name: /Préparer les documents/ }))
    expect(screen.getByTestId('lieu')).toHaveTextContent('onglet=documents')
  })

  it('l’ancien contenu reste atteignable : « Détail des pertes et réglages » monte le diagramme et l’édition des postes', async () => {
    servir(COMPLET())
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(screen.queryByTestId('cal-pertes-unifie')).toBeNull()
    fireEvent.click(screen.getByText('Détail des pertes et réglages'))
    expect(await screen.findByTestId('cal-pertes-unifie')).toBeInTheDocument()
  })

  it('PanneauPertesUnifie (point d’entrée du parcours guidé) rend cet écran', async () => {
    servir(COMPLET())
    render(<MemoryRouter><PanneauPertesUnifie calepinageId={1} /></MemoryRouter>)
    expect(await screen.findByTestId('cal-resultats-tuiles')).toBeInTheDocument()
  })
})

/* F4 — LE RÉSULTAT COMPLET, vérifiable sans pile : aucun calepinage réel n'a toutes ses pertes renseignées,
   donc le contrat `calepinage_resultat.json › exemple` (incomplet sur la cascade : postes non comptés) est
   COMPLÉTÉ ici à partir de la forme documentée du sérialiseur (`cascade.postes_lisibles` : 5 postes
   `compte`, `plages.total`, `simulation.reglages_utilises` du profil de départ). Chaque assertion reprend
   un bloc de `Resultats.dc.html`, dans l'ordre de la maquette. */
const COMPLET_MAQUETTE = () => {
  const d = COMPLET()
  d.cascade.postes_lisibles = {
    depart_kwh: 16800, arrivee_kwh: 13675, arrivee_pct: 81.4, total_pct: 18.6, motif_absence: '',
    postes: [
      ['ombres_proches', 'Ombres proches', 3.0], ['poussiere', 'Poussière', 3.0], ['chaleur', 'Chaleur', 6.4],
      ['cables_et_onduleur', 'Câbles et onduleur', 4.5], ['autres', 'Autres pertes', 3.1],
    ].map(([poste, libelle, pct]) => ({ poste, libelle, perte_kwh: pct * 168, perte_pct: pct, statut: 'compte', etapes: [] })),
  }
  d.cascade.plages = { ...d.cascade.plages, total: { statut: 'dans_la_plage' } }
  // `pertes_totales.egales` (ACAL1606) : le bloc `validation` servi par la simulation (contrat `calepinage_simulation.json`).
  d.validation = { ...d.validation, pertes_totales: exempleContrat('calepinage', 'calepinage_simulation', 'exemple').validation.pertes_totales }
  d.production.total.total_loss_pct = 18.6
  const ref = 'Profil de départ — PVsyst, Array and system losses'
  d.simulation = { ...d.simulation, reglages_utilises: {
    b0_iam: { valeur: 0.05, source: 'profil', reference: ref },
    mismatch_fabricant_pct: { valeur: 2, source: 'profil', reference: ref },
    albedo_mensuel: { valeur: 0.2, source: 'profil', reference: ref },
  } }
  return d
}

describe('Étape Résultats — résultat complet, bloc par bloc (maquette Resultats)', () => {
  it('même structure, mêmes mots, même ordre que Resultats.dc.html', async () => {
    servir(COMPLET_MAQUETTE())
    const { container } = rendre({ action: { libelle: 'Préparer les documents', onClick: vi.fn() } })
    await screen.findByTestId('cal-resultats-tuiles')
    const texte = (n) => n.textContent.replace(/\s+/g, ' ').trim()
    const racine = container.querySelector('.cal-res')
    // 1. Héros + 3 tuiles : libellé, chiffre, phrase — dans l'ordre.
    const tuiles = [...screen.getByTestId('cal-resultats-tuiles').children].map((t) => [...t.children].map(texte))
    expect(tuiles).toEqual([
      ['Production la première année', '13 000 kWh', '1 505 kWh par kWc · année moyenne (P50)'],
      ['De la consommation', '71 %', 'Pourquoi ce chiffre ?'],
      ['Pertes au total', '18,6 %', 'Dans la plage habituelle'],
      ['Écart avec PVGIS', '− 2,0 %', 'Même site, mêmes panneaux, à pertes système égales · dans ±5 %'],
    ])
    // 2. « Mois par mois » : titre, légende, 12 paires de barres, 12 initiales J F M A M J J A S O N D.
    const mois = screen.getByTestId('cal-resultats-mois')
    // ACAL1832 : la pastille du mois choisi (le plus fort) porte la légende, avec les valeurs servies de ce mois.
    expect(texte(mois.querySelector('.cal-res-entete'))).toMatch(/^Mois par mois[A-Zé][\wéû]+ [\d ]+ kWh produits[\d ]+ kWh consommés$/)
    expect(mois.querySelectorAll('.cal-res-mois-paire')).toHaveLength(12)
    mois.querySelectorAll('.cal-res-mois-paire').forEach((p) => expect(p.children).toHaveLength(2))
    expect([...mois.querySelectorAll('.cal-res-mois-noms span')].map(texte).join('')).toBe('JFMAMJJASOND')
    // 3. « Du soleil au réseau » : 7 lignes, dans l'ordre de la maquette, puis la note.
    const pertes = screen.getByTestId('cal-resultats-pertes')
    expect([...pertes.querySelectorAll('.cal-res-poste')].map(texte)).toEqual([
      'Soleil reçu par les panneaux100 %', 'Ombres proches− 3,0 %', 'Poussière− 3,0 %', 'Chaleur− 6,4 %',
      'Câbles et onduleur− 4,5 %', 'Autres pertes− 3,1 %', 'Électricité produite81,4 %',
    ])
    expect(texte(pertes.querySelector('.cal-res-entete'))).toMatch(/^Du soleil au réseauVoir les \d+ étapes$/)
    expect(texte(pertes.querySelector('.cal-res-info'))).toBe(
      '3 réglages utilisent des valeurs publiées, non mesurées sur ce chantier (reflets du verre, écarts entre panneaux, réflexion du sol). Voir les sources')
    // 4. Pied : phrase + bouton doré, après les deux cartes.
    expect(texte(screen.getByTestId('cal-resultats-pied'))).toBe(
      'Année basse (9 fois sur 10 au-dessus) : 11 900 kWh · Dans 2 ans : 12 929 kWhPréparer les documents')
    // Ordre global : tuiles, milieu (mois puis pertes), pied.
    const ordre = [...racine.children].map((n) => n.getAttribute('data-testid') || n.className)
    expect(ordre.slice(0, 3)).toEqual(['cal-resultats-tuiles', 'cal-res-milieu', 'cal-resultats-pied'])
  })
})

describe('Étape Résultats — squelette de chargement (ACAL1822)', () => {
  it('le squelette de Résultats rend deux blocs aux boîtes de la mise en page, `role="status"`, sans lien de retour', async () => {
    calepinageApi.calepinages.resultat.mockReturnValue(new Promise(() => {})) // réponse qui n'arrive pas
    const { container } = rendre()
    const etat = await screen.findByRole('status')
    expect(etat).toHaveAttribute('aria-label', 'Chargement…')
    expect(etat).toHaveClass('cal-res-squelette')
    const blocs = etat.querySelectorAll('.cal-res-squelette-bloc')
    expect(blocs).toHaveLength(2)
    expect(blocs[0]).toHaveClass('cal-res-squelette-heros')
    // La carte héros (colonne de 540 px) puis « Pour un résultat complet » : la grille de l'écran incomplet.
    expect(container.querySelector('.cal-res-squelette')).toBe(etat)
    // Rien au-dessus du squelette : le contenu ne descend pas à l'arrivée des données.
    expect(etat.previousElementSibling).toBeNull()
  })

  it('une erreur de lecture garde le lien de retour et le message, pas le squelette', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('boom'))
    rendre()
    expect(await screen.findByTestId('cal236-erreur')).toBeInTheDocument()
    expect(document.querySelector('.cal-res-squelette')).toBeNull()
    // Une vraie erreur garde son message d'erreur et propose aussi « Réessayer ».
    expect(screen.getByTestId('cal-reessayer-lecture')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-calcul-lent')).toBeNull()
  })

  // ACAL1905 — une réponse LENTE n'est pas une connexion coupée : un délai dépassé (axios ECONNABORTED) se dit « Calcul en
  // cours… » (information, pas erreur) avec « Réessayer », qui relit `GET resultat/` ; jamais « La connexion a expiré ».
  it('ACAL1905 — délai dépassé : « Calcul en cours… » et « Réessayer » relit, puis le résultat s’affiche', async () => {
    const delai = Object.assign(new Error('timeout of 60000ms exceeded'), { code: 'ECONNABORTED' })
    servir(COMPLET())
    calepinageApi.calepinages.resultat.mockRejectedValueOnce(delai) // 1re lecture : délai dépassé ; la relecture aboutit
    rendre()
    const info = await screen.findByTestId('cal-calcul-lent')
    expect(info).toHaveTextContent('Calcul en cours…')
    expect(document.body.textContent).not.toMatch(/connexion a expiré|Résultats indisponibles/)
    expect(screen.queryByTestId('cal236-erreur')).toBeNull()
    fireEvent.click(screen.getByTestId('cal-reessayer-lecture'))
    expect(await screen.findByTestId('cal-resultats-tuiles')).toBeInTheDocument()
    expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2)
  })
})

/* ACAL1832 — l'écran Résultats complet à sa maquette v2 : chiffres dessinés, anneau, réglettes, mois par mois, pistes. */
describe('Étape Résultats — résultat complet à la maquette v2 (ACAL1832)', () => {
  const nombres = (liste) => liste.map((n) => Number.parseFloat(n))

  it('la carte héros rend douze mini-barres servies (le mois le plus fort est plein) ; sans série servie, aucune', async () => {
    const d = COMPLET_MAQUETTE()
    servir(d)
    const { unmount } = rendre()
    const barres = [...(await screen.findByTestId('cal-res-minibarres')).children]
    expect(barres).toHaveLength(12)
    const servi = d.production.mensuel.map((m) => m.p50_kwh)
    const fort = servi.indexOf(Math.max(...servi))
    expect(barres.map((b) => b.dataset.fort)).toEqual(barres.map((_, i) => (i === fort ? 'oui' : undefined)))
    expect(nombres(barres.map((b) => b.style.height))[fort]).toBe(100)
    unmount()
    const sans = COMPLET_MAQUETTE()
    sans.production.mensuel = []
    sans.autoconsommation.par_mois = []
    servir(sans)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(screen.queryByTestId('cal-res-minibarres')).toBeNull()
  })

  it('Demande croisée — la tuile « Écart avec PVGIS » dit « à pertes système égales » seulement quand `pertes_totales.egales` est servi vrai', async () => {
    const d = COMPLET_MAQUETTE()
    d.validation.pertes_totales = { ...d.validation.pertes_totales, egales: false }
    servir(d)
    const { unmount } = rendre()
    const tuile = (await screen.findByTestId('cal-resultats-tuiles')).querySelector('[data-tuile="ecart-pvgis"]')
    expect(tuile).toHaveTextContent('Même site, mêmes panneaux · dans ±5 %')
    expect(tuile).not.toHaveTextContent('pertes système égales')
    unmount()
    servir(COMPLET_MAQUETTE())
    rendre()
    expect((await screen.findByTestId('cal-resultats-tuiles')).querySelector('[data-tuile="ecart-pvgis"]'))
      .toHaveTextContent('Même site, mêmes panneaux, à pertes système égales · dans ±5 %')
  })

  it('anneau de la consommation : l’arc est la part servie (71 %), nommée pour les lecteurs d’écran', async () => {
    servir(COMPLET_MAQUETTE())
    rendre()
    const anneau = (await screen.findByTestId('cal-resultats-tuiles')).querySelector('[data-tuile="couverture"] svg')
    expect(anneau).toHaveAttribute('role', 'img')
    expect(anneau).toHaveAttribute('aria-label', '71 % de la consommation couverte')
    const [arc, total] = nombres(anneau.querySelector('.cal-res-anneau-arc').getAttribute('stroke-dasharray').split(' '))
    expect(arc / total).toBeCloseTo(0.71, 2)
  })

  it('réglette des pertes : bande habituelle SERVIE et repère à la valeur ; sans bande servie, pas de réglette', async () => {
    const d = COMPLET_MAQUETTE()
    d.cascade.plages.total = { statut: 'dans_la_plage', min: 10, max: 20, unite: '%' }
    servir(d)
    const { unmount } = rendre()
    const regle = await screen.findByTestId('cal-res-regle-pertes')
    const plage = regle.querySelector('.cal-res-regle-plage')
    const haut = Math.max(20, 18.6) * 1.35
    expect(Number.parseFloat(plage.style.left)).toBeCloseTo((10 / haut) * 100, 1)
    expect(Number.parseFloat(plage.style.width)).toBeCloseTo((10 / haut) * 100, 1)
    expect(Number.parseFloat(regle.querySelector('.cal-res-regle-repere').style.left)).toBeCloseTo((18.6 / haut) * 100, 1)
    unmount()
    const sans = COMPLET_MAQUETTE() // plages.total sans min / max
    servir(sans)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(screen.queryByTestId('cal-res-regle-pertes')).toBeNull()
    expect(screen.getByText('Dans la plage habituelle')).toBeInTheDocument()
  })

  it('« Mois par mois » : le mois le plus fort est choisi, un toucher change la pastille ; courbe de consommation servie seulement', async () => {
    const d = COMPLET_MAQUETTE()
    servir(d)
    const { unmount } = rendre()
    const mois = await screen.findByTestId('cal-resultats-mois')
    const pastille = within(mois).getByTestId('cal-res-mois-choisi')
    const paires = [...mois.querySelectorAll('.cal-res-mois-paire')]
    const choisi = paires.findIndex((p) => p.getAttribute('aria-pressed') === 'true')
    expect(pastille).toHaveTextContent(['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'][choisi])
    const autre = (choisi + 1) % 12
    fireEvent.click(paires[autre])
    expect(paires[autre]).toHaveAttribute('aria-pressed', 'true')
    expect(paires[choisi]).toHaveAttribute('aria-pressed', 'false')
    expect(mois.querySelectorAll('.cal-res-courbe-trait')).toHaveLength(1)
    expect(mois.querySelector('.cal-res-courbe-trait').getAttribute('points').split(' ')).toHaveLength(12)
    expect(mois.querySelectorAll('.cal-res-point')).toHaveLength(12)
    // Repères ronds de l'échelle, au-dessus du plus grand mois servi.
    const reperes = [...mois.querySelectorAll('.cal-res-axe span')].map((s) => s.textContent.replace(/\s/g, ''))
    expect(reperes).toHaveLength(3)
    unmount()
    const sans = COMPLET_MAQUETTE()
    sans.autoconsommation.par_mois = sans.autoconsommation.par_mois.map((m) => ({ ...m, consommation_kwh: null }))
    servir(sans)
    rendre()
    const mois2 = await screen.findByTestId('cal-resultats-mois')
    expect(mois2.querySelector('.cal-res-courbe')).toBeNull()
    expect(mois2.querySelector('.cal-res-point')).toBeNull()
    expect(within(mois2).getByTestId('cal-res-mois-choisi')).not.toHaveTextContent('consommés')
    expect(mois2).not.toHaveTextContent('Journée type') // aucune série horaire servie : pas de bascule
  })

  it('« Du soleil au réseau » : chaque piste porte le restant puis CETTE perte (les pourcentages servis)', async () => {
    servir(COMPLET_MAQUETTE())
    rendre()
    const carte = await screen.findByTestId('cal-resultats-pertes')
    const pistes = [...carte.querySelectorAll('.cal-res-poste[data-statut] .cal-res-piste')]
    expect(pistes).toHaveLength(5)
    expect(pistes.map((p) => Number.parseFloat(p.querySelector('.cal-res-perte').style.width))).toEqual([3, 3, 6.4, 4.5, 3.1])
    const restes = pistes.map((p) => Number.parseFloat(p.firstElementChild.style.width))
    expect(restes[0]).toBeCloseTo(97, 5)
    expect(restes[4]).toBeCloseTo(80, 5) // cumul visuel des pourcentages servis (100 − 3 − 3 − 6,4 − 4,5 − 3,1)
  })
})

describe('Étape Résultats — pertes nommées en clair', () => {
  it('« Salissure / LID » deviennent les mots de la maquette, le terme technique reste en infobulle', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    servir({ ...base, production: borne.production, simulation: borne.simulation, cascade: borne.cascade })
    rendre()
    const lignes = await screen.findAllByTestId('acal700-ligne')
    const noms = lignes.map((l) => l.querySelector('.cal-resinc-nom'))
    expect(noms.map((n) => n.textContent.trim())).toEqual([
      'Poussière sur les panneaux', 'Écarts entre panneaux', 'Vieillissement de la première année'])
    expect(noms[0]).toHaveAttribute('title', 'Salissure')
    expect(noms[2]).toHaveAttribute('title', 'LID (première exposition)')
    expect(document.body.textContent).not.toMatch(/Salissure|LID|mismatch/)
  })
})

describe('Étape Résultats — résultat incomplet (maquette ResultatsIncomplet)', () => {
  it('ACAL1708 — « Voir les valeurs » ouvre la page Démarrage rapide, pas la page des réglages', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    servir({ ...base, production: borne.production, simulation: borne.simulation, cascade: borne.cascade })
    rendre()
    const lien = await screen.findByTestId('acal700-lien-reglages')
    expect(lien).toHaveTextContent('Voir les valeurs')
    expect(lien).toHaveAttribute('href', '/calepinage/reglages/demarrage-rapide')
  })

  it('carte « au plus » et « Pour un résultat complet » côte à côte, sans tuiles ni pied', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    servir({ ...base, production: borne.production, simulation: borne.simulation, cascade: borne.cascade })
    rendre()
    const bloc = await screen.findByTestId('acal700-incomplet')
    const haut = bloc.querySelector('.cal-resinc-haut')
    expect(haut.children).toHaveLength(2)
    expect(haut.children[0]).toHaveTextContent('Production la première année · au plus')
    expect(haut.children[1]).toHaveTextContent('Pour un résultat complet')
    expect(within(bloc).getAllByText('Renseigner').length).toBeGreaterThan(0)
    expect(screen.queryByTestId('cal-resultats-tuiles')).toBeNull()
    // ACAL1958 — incomplet : le bouton de l'étape, sans la phrase de durée (valeurs non publiées).
    const pied = screen.getByTestId('cal-resultats-pied')
    expect(within(pied).getByRole('button', { name: /Préparer les documents/ })).toBeInTheDocument()
    expect(pied.querySelector('.cal-res-pied-ligne').textContent).toBe('')
  })

  it('Demande croisée — le compte annoncé égale les lignes listées, ou dit « et N autres » avec « Voir les étapes » qui ouvre le détail', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    data.cascade.a_renseigner.etapes_comptees = 4
    data.cascade.a_renseigner.etapes_a_compter = 22 // 18 pertes non comptées, 3 lignes à renseigner ici
    servir(data)
    rendre()
    const phrase = await screen.findByTestId('acal700-plafond')
    expect(phrase).toHaveTextContent('18 pertes ne sont pas encore comptées')
    const lignes = screen.getAllByTestId('acal700-ligne')
    expect(lignes).toHaveLength(3)
    // 18 annoncées, 3 listées : la ligne « et 15 autres » comble l'écart, avec son lien.
    const autres = screen.getByTestId('acal700-autres')
    expect(autres).toHaveTextContent('et 15 autres')
    expect(screen.queryByTestId('cal-pertes-unifie')).toBeNull()
    fireEvent.click(within(autres).getByRole('button', { name: 'Voir les étapes' }))
    expect(await screen.findByTestId('cal-pertes-unifie')).toBeInTheDocument()
    cleanup()
    // Compte = lignes : aucune ligne « et N autres ».
    data.cascade.a_renseigner.etapes_comptees = 1
    data.cascade.a_renseigner.etapes_a_compter = 4
    servir(data)
    rendre()
    expect((await screen.findByTestId('acal700-plafond'))).toHaveTextContent('3 pertes ne sont pas encore comptées')
    expect(screen.queryByTestId('acal700-autres')).toBeNull()
  })

  it('Demande croisée — « Démarrage rapide » ne compte que les lignes `reglage_societe` (pas les lignes de fiche panneau)', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    // Deux lignes à valeur publiée : l'une est un réglage de la société, l'autre une donnée de la fiche du panneau.
    const [societe, , fiche] = data.cascade.a_renseigner.lignes
    data.cascade.a_renseigner.lignes = [
      { ...societe, cle: 'mismatch_fabricant_pct', nature: 'reglage_societe' },
      { ...fiche, cle: 'b0_iam', nature: 'fiche_panneau' },
    ]
    servir(data)
    rendre()
    const texte = await screen.findByTestId('acal700-demarrage-texte')
    expect(texte).toHaveTextContent(/^Remplir le réglage vide avec des valeurs publiées/)
    expect(texte).not.toHaveTextContent('2 réglages')
    expect(screen.getByTestId('acal1833-compteur')).toHaveTextContent('2 à renseigner') // toutes les lignes listées
    // Aucune ligne de société : le bouton or « Voir les valeurs » n'est jamais promis.
    cleanup()
    data.cascade.a_renseigner.lignes = [{ ...fiche, cle: 'b0_iam', nature: 'fiche_panneau' }]
    servir(data)
    rendre()
    expect(await screen.findByTestId('acal700-demarrage-texte')).toHaveTextContent('Aucune valeur publiée n’existe')
  })

  it('« Démarrage rapide » ne compte que ce que « Remplir » remplit (même liste que la page Démarrage rapide)', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: borne.cascade }
    const cles = data.cascade.a_renseigner.lignes.map((l) => l.cle)
    expect(cles).toHaveLength(3) // salissure + LID : aucune valeur publiée ; écarts entre panneaux : valeur publiée
    servir(data)
    rendre()
    const texte = await screen.findByTestId('acal700-demarrage-texte')
    expect(texte).toHaveTextContent(/^Remplir le réglage vide avec des valeurs publiées/)
    expect(texte).not.toHaveTextContent('3 réglages')
    cleanup()
    // Aucune ligne remplissable : jamais « Remplir » promis.
    data.cascade.a_renseigner.lignes = data.cascade.a_renseigner.lignes.filter((l) => ['salissure_mensuelle_pct', 'lid_par_techno'].includes(l.cle))
    servir(data)
    rendre()
    expect(await screen.findByTestId('acal700-demarrage-texte')).toHaveTextContent('Aucune valeur publiée n’existe pour ces réglages')
  })
})

/* F7 — l'état « pas encore simulé » (jamais lancé / périmé), mêmes cartes que le résultat incomplet. Payloads =
   contrat `calepinage_resultat.json` (`exemple_vide`, `exemple_perime`) + `parcours.manque` tel que
   `parcours_guide.regrouper_manque` le sert pour le cas capturé (norme × 3, production non simulée, accès solaire,
   températures non sourcées). */
const JARGON = /document de toiture|accès solaire par module|silence est explicite|OMIS|non sourcées|NF C 15|UTE C/
const MANQUE = () => [
  { code: 'norme_absente', etape: 'electrique', gravite: 'a_regler', nombre: 3, cible: { onglet: 'reglages', champ: 'norme' },
    message: 'aucune norme électrique sélectionnée : les calculs qui en dépendent (sections de câble) sont OMIS. NF C 15-100 / UTE C 15-712-1' },
  { code: 'production_non_simulee', etape: 'resultats', gravite: 'a_regler', nombre: 1, cible: { onglet: 'production', champ: '' },
    message: 'Production non simulée dans ce résultat : la pose et l’électricité sont connues, la production ne l’est pas.' },
  { code: 'acces_solaire_absent', etape: 'resultats', gravite: 'info', nombre: 1, cible: { onglet: 'production', champ: '' },
    message: 'Le document de toiture ne porte aucun accès solaire par module : aucun écart d’ombrage n’est signalé. Le silence est explicite.' },
  { code: 'coefficients_non_sources', etape: 'resultats', gravite: 'info', nombre: 1, cible: { onglet: 'reglages', champ: '' },
    message: 'températures de référence, non sourcées' },
]
const JAMAIS = () => JSON.parse(JSON.stringify(exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide')))
const PERIME = () => JSON.parse(JSON.stringify(exempleContrat('calepinage', 'calepinage_resultat', 'exemple_perime')))
const rendreAvec = (data) => {
  servir(data)
  return render(
    <MemoryRouter><EtapeResultats calepinageId={5} parcours={{ manque: MANQUE() }}
      action={{ libelle: 'Préparer les documents', onClick: vi.fn() }} /></MemoryRouter>,
  )
}

describe('Étape Résultats — pas encore simulé (jamais lancé)', () => {
  it('carte sombre + « Pour un résultat complet » + « Ce qui est déjà sûr », dans cet ordre, sans jargon', async () => {
    rendreAvec(JAMAIS())
    const bloc = await screen.findByTestId('cal-avant-simulation')
    const haut = bloc.querySelector('.cal-resinc-haut')
    expect(haut.children).toHaveLength(2)
    expect(screen.getByTestId('cal-avant-titre')).toHaveTextContent('Production pas encore calculée')
    expect(within(haut.children[0]).getByRole('button', { name: 'Lancer la simulation' })).toBeInTheDocument()
    expect(haut.children[1]).toHaveTextContent('Pour un résultat complet')
    const ordre = [haut, screen.getByTestId('acal700-sur')]
    expect(ordre[0].compareDocumentPosition(ordre[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(screen.getByTestId('acal700-sur')).getByText('12')).toBeInTheDocument() // pose.total_modules
    expect(screen.getByTestId('acal700-sur')).toHaveTextContent('8,64 kWc') // pose.kwc : chiffre et unité sont deux nœuds
    expect(bloc).not.toHaveTextContent(JARGON)
    expect(document.body.textContent).not.toMatch(JARGON)
    expect(screen.queryByText('Ce qui manque encore :')).toBeNull()
    // ACAL1958 — avant simulation : le bouton de l'étape est là, au même gabarit ; aucune phrase de durée.
    const pied = screen.getByTestId('cal-resultats-pied')
    expect(within(pied).getByRole('button', { name: /Préparer les documents/ })).toBeInTheDocument()
    expect(pied.querySelector('.cal-res-pied-ligne').textContent).toBe('')
    expect(screen.queryByTestId('cal-resultats-tuiles')).toBeNull()
  })

  it('lignes numérotées en clair, comptes fusionnés, cibles conservées, phrase servie derrière le « ? »', async () => {
    rendreAvec(JAMAIS())
    const lignes = await screen.findAllByTestId('cal-avant-ligne')
    const texte = (n) => n.textContent.replace(/\s+/g, ' ').trim()
    expect(lignes.map((l) => texte(l.querySelector('.cal-resinc-nom')))).toEqual([
      'Choisir la norme électrique de votre société?', 'Ombrage panneau par panneau?', 'Températures de référence?'])
    expect(lignes.map((l) => l.querySelector('.cal-resinc-rang').textContent)).toEqual(['1', '2', '3'])
    expect(lignes.map((l) => l.querySelector('[data-testid="cal-avant-renseigner"]').getAttribute('href'))).toEqual([
      '/calepinage/reglages#norme', '/calepinage/5?onglet=production', '/calepinage/reglages'])
    expect(lignes.map((l) => l.querySelector('[data-testid="cal-avant-renseigner"]').textContent)).toEqual([
      'Renseigner', 'Renseigner', 'Renseigner'])
    // « Production à calculer — Voir » doublait le bouton « Lancer la simulation » de la carte sombre : retirée de la liste.
    expect(screen.queryByText('Production à calculer')).toBeNull()
    // La phrase servie est gardée, derrière le « ? » (infobulle + révélée au clic), jamais dans la ligne.
    const aide = within(lignes[0]).getByTestId('cal-avant-aide')
    expect(aide).toHaveAttribute('title', expect.stringContaining('NF C 15-100'))
    expect(within(lignes[0]).queryByTestId('cal-avant-servi')).toBeNull()
    fireEvent.click(aide)
    expect(within(lignes[0]).getByTestId('cal-avant-servi')).toHaveTextContent('OMIS')
  })

  it('« Lancer la simulation » appelle la même requête que le bouton existant', async () => {
    calepinageApi.calepinages.simuler.mockResolvedValue({ status: 200, data: {} })
    rendreAvec(JAMAIS())
    fireEvent.click(await screen.findByRole('button', { name: 'Lancer la simulation' }))
    expect(calepinageApi.calepinages.simuler).toHaveBeenCalledWith(5)
  })

  it('aucun poste à renseigner : la liste le dit au lieu de rester vide', async () => {
    servir(JAMAIS())
    render(<MemoryRouter><EtapeResultats calepinageId={5} parcours={{ manque: [] }} /></MemoryRouter>)
    expect(await screen.findByText('Rien d’autre à renseigner : vous pouvez lancer la simulation.')).toBeInTheDocument()
  })
})

describe('Étape Résultats — calcul à refaire (simulation périmée)', () => {
  it('même mise en page, titre « Calcul à refaire », bouton de relance, aucun bandeau en plus', async () => {
    rendreAvec(PERIME())
    await screen.findByTestId('cal-avant-simulation')
    expect(screen.getByTestId('cal-avant-simulation')).toHaveAttribute('data-etat', 'perime')
    expect(screen.getByTestId('cal-avant-titre')).toHaveTextContent('Calcul à refaire')
    expect(screen.getByTestId('cal-avant-titre')).toHaveAttribute('title', expect.stringContaining('19/09/2026'))
    expect(screen.getByTestId('calx48-lancer-bouton')).toHaveAttribute('data-etat', 'perime')
    expect(screen.getByText('Pour un résultat complet')).toBeInTheDocument()
    expect(screen.queryByTestId('calx48-perime')).toBeNull()
    expect(document.body.textContent).not.toMatch(JARGON)
  })
})

/* ACAL1956 — la production RETENUE PAR LE DEVIS envoyé : bloc servi `production_devis` (exemple du contrat). */
describe('Étape Résultats — production retenue par le devis (ACAL1956)', () => {
  const PROD = () => exempleContrat('calepinage', 'calepinage_resultat', 'exemple_ecart_devis').production_devis
  const kwh = (n) => `${formatNumber(n, { decimals: 0 })} kWh par an`.replace(/\s+/g, ' ')

  it('sans devis lié : aucun bloc', async () => {
    rendreAvec(JAMAIS())
    await screen.findByTestId('cal-avant-simulation')
    expect(screen.queryByText(/Production retenue par le devis/)).toBeNull()
  })

  it('devis envoyé sans simulation : le chiffre du devis, le lien vers le devis et l’invitation à simuler', async () => {
    rendreAvec({ ...JAMAIS(), production_devis: PROD() })
    await screen.findByRole('link', { name: PROD().reference })
    const zone = document.querySelector('[data-zone="production-devis"]')
    expect(zone).toHaveTextContent(`Production retenue par le devis : ${kwh(PROD().production_annuelle_kwh)}`)
    expect(screen.getByRole('link', { name: PROD().reference })).toHaveAttribute('href', `/ventes/devis?devis=${PROD().devis}`)
    expect(zone).toHaveTextContent('Simulez la pose pour la comparer à ce chiffre.')
    expect(screen.getByRole('button', { name: 'Lancer la simulation' })).toBeInTheDocument()
  })

  it('devis envoyé avec simulation : les deux chiffres côte à côte, chacun nommé', async () => {
    const data = { ...COMPLET(), production_devis: PROD() }
    servir(data)
    rendre()
    await screen.findByRole('link', { name: PROD().reference })
    const zone = document.querySelector('[data-zone="production-devis"]')
    expect(zone).toHaveTextContent(`Production retenue par le devis : ${kwh(PROD().production_annuelle_kwh)}`)
    expect(zone).toHaveTextContent(`Production simulée de la pose : ${kwh(data.production.total.p50_kwh)}`)
  })
})

/* ACAL1912 (rejeu T3-VAGUEC du 23/11) — Guidé > Résultats dit les panneaux posés mais non raccordés : la phrase SERVIE en tête
   de `avertissements`, et la production rapportée aux panneaux COMPTÉS (jamais « 13 panneaux » à côté d'un productible
   de 9). Tout vient de `GET resultat/` : `production.hors_chaine.modules`, `pose.*`, `production.total.kwc`. */
describe('Étape Résultats — panneaux posés mais non raccordés (ACAL1912)', () => {
  const PHRASE = '4 panneaux ne sont raccordés à aucun onduleur : ils ne sont pas comptés dans la production (leur énergie possible est donnée à part, « hors chaîne »).'
  const NON_RACCORDES = () => {
    const d = COMPLET()
    d.pose = { ...d.pose, total_modules: 13, kwc: 9.23 }
    d.production.total.kwc = 6.39
    d.production.hors_chaine = { modules: 4, p50_kwh: 3300 }
    d.avertissements = [PHRASE, 'Longueur de chaîne à vérifier.']
    return d
  }
  const zone = () => document.querySelector('[data-zone="non-raccordes"]')

  it('résultat complet : la phrase servie et les deux comptes (comptés / posés), une seule fois', async () => {
    servir(NON_RACCORDES())
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(zone()).not.toBeNull()
    expect(zone()).toHaveTextContent(PHRASE)
    expect(zone()).toHaveTextContent('Production comptée sur 9 des 13 panneaux posés (6,39 kWc sur 9,23 kWc).')
    expect(document.body.textContent.split(PHRASE)).toHaveLength(2)
    expect(zone()).not.toHaveTextContent('Longueur de chaîne')
  })

  it('résultat incomplet : même avertissement au-dessus de « Ce qui est déjà sûr »', async () => {
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const d = NON_RACCORDES()
    servir({ ...d, production: { ...borne.production, hors_chaine: d.production.hors_chaine }, simulation: borne.simulation, cascade: borne.cascade })
    rendre()
    await screen.findByTestId('acal700-incomplet')
    expect(zone()).toHaveTextContent(PHRASE)
    expect(zone()).toHaveTextContent('13 panneaux posés')
  })

  it('tous les panneaux raccordés (ou rien de servi) : aucun bloc', async () => {
    const d = NON_RACCORDES()
    d.production.hors_chaine = { modules: 0, p50_kwh: 0 }
    servir(d)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(zone()).toBeNull()
    cleanup()
    servir(COMPLET())
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(zone()).toBeNull()
  })
})
