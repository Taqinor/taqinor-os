/* Nouveau fichier car : EtapeResultats.jsx est un composant neuf (écran de l'étape Résultats, maquettes
   Resultats / ResultatsIncomplet) sans module de test voisin ; les tests de ses pièces existantes
   restent dans production/*.test.jsx.
   Ce qui est prouvé : l'ordre et les libellés de la maquette, la règle « figure servie ou bloc omis »,
   aucun code technique à l'écran, le pied et son bouton, la carte « au plus » du résultat incomplet. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { exempleContrat } from '../../../../../test/fixtures/contractSamples'

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
    expect(within(tuiles).getByText('13 000 kWh')).toBeInTheDocument() // P50 servi
    expect(within(tuiles).getByText('1 505 kWh par kWc · année moyenne (P50)')).toBeInTheDocument()
    expect(within(tuiles).getByText('71 %')).toBeInTheDocument() // taux_couverture 0,71
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
      ['Écart avec PVGIS', '− 2,0 %', 'Même site, mêmes panneaux · dans ±5 %'],
    ])
    // 2. « Mois par mois » : titre, légende, 12 paires de barres, 12 initiales J F M A M J J A S O N D.
    const mois = screen.getByTestId('cal-resultats-mois')
    expect(texte(mois.querySelector('.cal-res-entete'))).toBe('Mois par moisProductionConsommation')
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
    expect(screen.queryByTestId('cal-resultats-pied')).toBeNull()
  })
})
