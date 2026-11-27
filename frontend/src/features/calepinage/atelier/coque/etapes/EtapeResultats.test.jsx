/* Nouveau fichier car : EtapeResultats.jsx est un composant neuf (écran de l'étape Résultats, maquettes
   Resultats / ResultatsIncomplet) sans module de test voisin ; les tests de ses pièces existantes
   restent dans production/*.test.jsx.
   Ce qui est prouvé : l'ordre et les libellés de la maquette, la règle « figure servie ou bloc omis »,
   aucun code technique à l'écran, le pied et son bouton, la carte « au plus » du résultat incomplet. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { exempleContrat } from '../../../../../test/fixtures/contractSamples'
import { formatNumber } from '../../../../../lib/format'
import { feuilleAuDoigt } from '../../../__tests__/feuilleAuDoigt'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(), exportCsv: vi.fn(), simuler: vi.fn(), explications: vi.fn(),
      pertes: vi.fn(), enregistrerPertes: vi.fn(), designContext: vi.fn(), parcours: vi.fn(), get: vi.fn(),
    },
    moteur: { resultat: vi.fn() },
    parametres: { get: vi.fn() },
  },
}))
vi.mock('../../../../../hooks/useHasPermission', () => ({ useHasPermission: () => true }))
vi.mock('../../../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import calepinageApi from '../../../../../api/calepinageApi'
import ventesApi from '../../../../../api/ventesApi'
import EtapeResultats from './EtapeResultats'
import CoqueAtelier from '../CoqueAtelier'
import { formaterHeureBrouillon } from '../../contexteAtelier'
import { oublierLecturesServies } from './panneaux/lectures'
import PanneauPertesUnifie from '../../PanneauPertesUnifie'
import RailGuide from '../../../commun/RailGuide'
import { publierRefus } from '../../../production/refusPublie'

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
// GET calepinages/<id>/resultat/ (la forme servie, cf. contract_samples/calepinage_resultat.json) : la garde de formes apparie par
// NOM de fonction et confond ce `resultat` avec `moteur.resultat` (job) : l'enveloppe axios passe par ce helper, pas par un littéral.
const lecture = (data) => ({ data })
const Lieu = () => <p data-testid="lieu">{useLocation().search}</p>
const rendre = (props = {}) => render(
  <MemoryRouter><EtapeResultats calepinageId={1} {...props} /><Lieu /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  oublierLecturesServies()
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
    expect(lignes[2]).toMatch(/Poussière.*non compté/) // ACAL1676 — le poste non compté est montré, sans barre
    expect(lignes[3]).toMatch(/Chaleur.*− 6,4 %/)
    expect(lignes[4]).toMatch(/Électricité produite.*81,4 %/)
    expect(document.body.textContent).not.toMatch(/CALX\d|ACAL\d|ohmique_dc|ombrage_proche/)
    expect(within(carte).getByText(/Voir les \d+ étapes/)).toBeInTheDocument()
  })

  it('tuile sans valeur servie : omise (jamais 0), sauf la consommation qui dit « — » et son motif (ACAL1631)', async () => {
    const d = COMPLET()
    d.autoconsommation.taux_couverture = null
    d.autoconsommation.motif_absence = 'Aucune courbe de consommation horaire pour ce calepinage.'
    d.validation.ecart_pct = null
    servir(d)
    rendre()
    const tuiles = await screen.findByTestId('cal-resultats-tuiles')
    const labels = [...tuiles.querySelectorAll('.cal-res-tuile-label')].map((n) => n.textContent)
    expect(labels).toEqual(['Production la première année', 'De la consommation', 'Pertes au total'])
    const conso = tuiles.querySelector('[data-tuile="couverture"]')
    expect(conso.querySelector('.cal-res-tuile-valeur').textContent).toBe('—')
    expect(conso).toHaveTextContent('Aucune courbe de consommation horaire pour ce calepinage.')
    expect(tuiles).not.toHaveTextContent('non calculée')
    expect(tuiles).not.toHaveTextContent('0 %')
  })

  it('ACAL1631 — consommation absente sans motif servi : « — » et la phrase de repli de la tuile jumelle', async () => {
    const d = COMPLET()
    d.autoconsommation.taux_couverture = null
    d.autoconsommation.motif_absence = ''
    servir(d)
    rendre()
    const conso = (await screen.findByTestId('cal-resultats-tuiles')).querySelector('[data-tuile="couverture"]')
    expect(conso.querySelector('.cal-res-tuile-valeur').textContent).toBe('—')
    expect(conso).toHaveTextContent('Aucune consommation connue.')
  })

  it('ACAL1631 — « Mois par mois » sans consommation servie : une ligne le dit avec le motif servi', async () => {
    const d = COMPLET_MAQUETTE()
    d.autoconsommation.par_mois = d.autoconsommation.par_mois.map((m) => ({ ...m, consommation_kwh: null }))
    d.autoconsommation.motif_absence = 'Aucune courbe de consommation horaire pour ce calepinage.'
    servir(d)
    rendre()
    const mois = await screen.findByTestId('cal-resultats-mois')
    expect(within(mois).getByTestId('cal-res-mois-sans-conso'))
      .toHaveTextContent('Consommation non tracée : Aucune courbe de consommation horaire pour ce calepinage.')
  })

  it('ACAL1631 — consommation servie : aucune ligne d’absence', async () => {
    servir(COMPLET_MAQUETTE())
    rendre()
    const mois = await screen.findByTestId('cal-resultats-mois')
    expect(within(mois).queryByTestId('cal-res-mois-sans-conso')).toBeNull()
  })

  /* T4-X7-005 — 3 panneaux 710 W sur un Deye 5 kW : 0 kWh, pertes 100 %, et aucune phrase sur l'étape ; la cause (tension
     par forte chaleur sous la plage de l'onduleur) n'était que dans Documents / Électrique. */
  it('T4-X7-005 — production nulle : la cause servie et le geste (étape Électrique) sont dits sur l’étape', async () => {
    const d = COMPLET()
    d.production.total.p50_kwh = 0
    const raison = 'par forte chaleur, la tension des panneaux (105,4 V) tombe sous la plage de travail de cet onduleur (150,0 V)'
    d.electrique.verdicts = d.electrique.verdicts.map((v) => (v.code === 'vmp_hot_over_mppt_min'
      ? { ...v, conforme: false, raison } : v))
    servir(d)
    rendre()
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveAttribute('data-zone', 'production-nulle')
    expect(alerte).toHaveTextContent('La simulation de la pose donne 0 kWh par an.')
    expect(alerte).toHaveTextContent(`Cause : Par forte chaleur, la tension des panneaux (105,4 V) tombe sous la plage`)
    fireEvent.click(within(alerte).getByRole('button', { name: 'Aller à l’étape Électrique' }))
    // le premier panneau de l'étape Électrique (parcoursGuide.premierOngletEtape), comme un clic sur le rail
    expect(screen.getByTestId('lieu').textContent).toMatch(/onglet=(equipements-electriques|cheminement-cables|raccordement|verdict-electrique|materiel-electrique|saisies-electriques|decisions-electriques|controle-chaine|schema)/)
  })

  it('T4-U4-012 — production NON nulle mais chaînes sous la plage de l’onduleur : une phrase dit que le raccordement perd l’essentiel', async () => {
    const d = COMPLET()
    const raison = 'par forte chaleur, la tension des panneaux (140,5 V) tombe sous la plage de travail de cet onduleur (150,0 V)'
    d.electrique.verdicts = d.electrique.verdicts.map((v) => (v.code === 'vmp_hot_over_mppt_min'
      ? { ...v, conforme: false, raison } : v))
    servir(d)
    rendre()
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveAttribute('data-zone', 'cablage-perd-la-production')
    // aucun chiffre de perte servi pour la fenêtre MPPT : jamais « l'essentiel », la seule phrase du serveur
    expect(alerte).not.toHaveTextContent('l’essentiel')
    expect(alerte).toHaveTextContent('la production des heures où les panneaux chauffent est perdue')
    expect(alerte).toHaveTextContent('Cause : Par forte chaleur, la tension des panneaux (140,5 V)')
    expect(alerte).not.toHaveTextContent('borne de fiche')
    expect(document.querySelector('[data-zone="production-nulle"]')).toBeNull()
    fireEvent.click(within(alerte).getByRole('button', { name: 'Aller à l’étape Électrique' }))
    expect(screen.getByTestId('lieu').textContent).toMatch(/onglet=/)
  })

  it.each([
    [63.5, 'fait perdre l’essentiel de la production : 63,5 %'],
    [4.2, 'fait perdre la production des heures les plus chaudes : 4,2 %'],
  ])('T4-U4-012 — la phrase suit la perte SERVIE de la fenêtre MPPT (%s %%)', async (perte, phrase) => {
    const d = COMPLET()
    d.electrique.verdicts = d.electrique.verdicts.map((v) => (v.code === 'vmp_hot_over_mppt_min'
      ? { ...v, conforme: false, raison: 'par forte chaleur, la tension des panneaux (140,5 V) tombe sous la plage' } : v))
    d.cascade.etapes = [...(d.cascade.etapes ?? []), { etape: 'mppt', libelle: 'Fenêtre MPPT', perte_pct: perte }]
    servir(d)
    rendre()
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(phrase)
  })

  it('T4-X7-005 — production non nulle : aucune alerte de production nulle', async () => {
    servir(COMPLET())
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(document.querySelector('[data-zone="production-nulle"]')).toBeNull()
  })

  it('pied : année basse et dernière année servies ; bouton = action de l’étape, sinon URL de l’étape Documents', async () => {
    servir(COMPLET())
    const onClick = vi.fn()
    const { unmount } = rendre({ action: { libelle: 'Préparer les documents', onClick } })
    const pied = await screen.findByTestId('cal-resultats-pied')
    expect(pied).toHaveTextContent('Année basse (variabilité météo seule, 9 années sur 10 au-dessus) : 11 900 kWh · Dans 2 ans : 12 929 kWh')
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
      'Année basse (variabilité météo seule, 9 années sur 10 au-dessus) : 11 900 kWh · Dans 2 ans : 12 929 kWhPréparer les documents')
    // Ordre global : tuiles, milieu (mois puis pertes), pied.
    const ordre = [...racine.children].map((n) => n.getAttribute('data-testid') || n.className)
    // ACAL1630 : l'exemple du contrat sert une supposition (`suppose[]`) — sa section vient entre le milieu et le pied.
    expect(ordre.slice(0, 4)).toEqual(['cal-resultats-tuiles', 'cal-res-milieu', 'acal980-suppose', 'cal-resultats-pied'])
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
    expect(reperes).toHaveLength(4)
    expect(reperes[0]).toBe('0') // T4-X7-005 — l'axe part de 0
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
    expect(lien).toHaveAttribute('href', expect.stringContaining('/calepinage/reglages/demarrage-rapide?reglages=')) // T4-B4-003 : avec SES réglages
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

  it('ACAL1939 — « Voir les étapes » défile jusqu’au détail APRÈS son montage, pas avant (sinon le contenu n’existe pas encore)', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    data.cascade.a_renseigner.etapes_comptees = 4
    data.cascade.a_renseigner.etapes_a_compter = 22
    servir(data)
    const defilements = []
    const origine = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = function defiler(options) {
      defilements.push({ zone: this.getAttribute('data-zone'), ouvert: this.open === true, options })
    }
    try {
      rendre()
      const autres = await screen.findByTestId('acal700-autres')
      fireEvent.click(within(autres).getByRole('button', { name: 'Voir les étapes' }))
      await waitFor(() => expect(defilements.length).toBeGreaterThan(0))
      // Le détail est déjà ouvert (monté) quand on y défile, et c'est bien lui qu'on amène à l'écran.
      expect(defilements.every((d) => d.zone === 'avance' && d.ouvert)).toBe(true)
      expect(defilements[0].options).toEqual({ block: 'start' })
    } finally {
      Element.prototype.scrollIntoView = origine
    }
  })

  it('ACAL1940 — sans onduleur désigné : « Aucun onduleur désigné » et « Désigner » vers l’Électrique, pas « Absent de la fiche du panneau »', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    const [societe] = data.cascade.a_renseigner.lignes
    const mppt = { etape: 'mppt', libelle: 'Fenêtre MPPT', nature: 'fiche_panneau', section: 'fiche_module', cle: 'vmp_v',
      libelle_champ: 'vmp_v', unite: '', ou_trouver: 'Fiche technique du panneau', cible: { onglet: 'fiches', champ: 'vmp_v' } }
    data.cascade.a_renseigner.lignes = [societe, mppt]
    servir(data)
    const sansOnduleur = { manque: [{ code: 'materiel_designe', etape: 'electrique', gravite: 'a_regler', nombre: 1,
      cible: { onglet: 'electrique', champ: '' }, message: 'onduleur non désigné — désignez-le dans l’onglet Matériel électrique' }] }
    rendre({ parcours: sansOnduleur })
    const lignes = await screen.findAllByTestId('acal700-ligne')
    const ligne = lignes.find((l) => l.textContent.includes('onduleur'))
    expect(ligne).toHaveTextContent('Aucun onduleur désigné')
    expect(ligne).not.toHaveTextContent('Absent de la fiche du panneau')
    const lien = within(ligne).getByRole('link', { name: 'Désigner' })
    expect(lien.getAttribute('href')).toMatch(/^\/calepinage\/1\?.*onglet=/)
    expect(lien.getAttribute('href')).not.toContain('fiches')
    cleanup()
    // Onduleur DÉSIGNÉ mais fiche incomplète : même code, cause « <rôle> : <champ> » (pret_a_envoyer) — jamais « Aucun onduleur désigné ».
    cleanup()
    servir(data)
    rendre({ parcours: { manque: [{ code: 'materiel_designe', etape: 'electrique', gravite: 'a_regler', nombre: 1,
      cible: { onglet: 'electrique', champ: '' }, message: 'onduleur : tension MPPT min' }] } })
    const incomplete = (await screen.findAllByTestId('acal700-ligne')).find((l) => l.textContent.includes('onduleur'))
    expect(incomplete).not.toHaveTextContent('Aucun onduleur désigné')
    expect(incomplete).toHaveTextContent('Absent de la fiche du panneau')
    expect(within(incomplete).getByRole('link', { name: 'Renseigner' }).getAttribute('href')).toContain('fiches')
    cleanup()
    // Un onduleur désigné (aucune ligne « matériel » à compléter) : le cas courant garde sa raison de fiche et « Renseigner ».
    servir(data)
    rendre({ parcours: { manque: [] } })
    const lignes2 = await screen.findAllByTestId('acal700-ligne')
    const fiche = lignes2.find((l) => l.textContent.includes('onduleur'))
    expect(fiche).toHaveTextContent('Absent de la fiche du panneau')
    expect(within(fiche).getByRole('link', { name: 'Renseigner' })).toBeInTheDocument()
  })

  it('ACAL1652 — deux étapes qui demandent le même champ : UNE ligne qui nomme les deux, un seul « à renseigner »', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    const [salissure, mismatch] = data.cascade.a_renseigner.lignes
    // Le même champ servi pour deux étapes (le cas du coefficient de température) : mêmes `section` et `cle`, étapes différentes.
    const jumelle = { ...mismatch, etape: 'chaleur', libelle: 'Chaleur', section: salissure.section, cle: salissure.cle, cible: salissure.cible }
    data.cascade.a_renseigner.lignes = [salissure, jumelle, mismatch]
    servir(data)
    rendre()
    const lignes = await screen.findAllByTestId('acal700-ligne')
    expect(lignes.filter((l) => l.textContent.includes('Chaleur'))).toHaveLength(1)
    const commune = lignes.find((l) => l.textContent.includes('Chaleur'))
    expect(commune.textContent).toContain(' et ')
    expect(commune.textContent).toMatch(/Salissure|poussi/i)
    expect(lignes.filter((l) => within(l).queryByTestId('acal700-renseigner'))).toHaveLength(2)
    expect(screen.getByTestId('acal1833-compteur')).toHaveTextContent(/^2 /)
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

  it('ACAL1934 — un réglage rempli mais illisible dit sa cause servie, et « Démarrage rapide » ne le compte pas comme vide', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const modele = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_ligne_a_renseigner_avec_motif')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    data.cascade.a_renseigner.lignes = [...data.cascade.a_renseigner.lignes, modele]
    data.cascade.a_renseigner.etapes_a_compter += 1
    servir(data)
    rendre()
    const lignes = await screen.findAllByTestId('acal700-ligne')
    expect(lignes).toHaveLength(4)
    const chaleur = lignes[3]
    expect(chaleur).toHaveTextContent('aucune ligne « south » dans la table société des coefficients par type de pose')
    expect(chaleur).not.toHaveTextContent('Aucune valeur pour votre société')
    expect(within(chaleur).getByRole('link', { name: 'Renseigner' })).toBeInTheDocument()
    // Les trois lignes SANS motif servi gardent leur raison : le cas commun ne change pas.
    for (const l of lignes.slice(0, 3)) expect(l).toHaveTextContent('Aucune valeur pour votre société')
    // 3 vides sur 4 : la ligne au motif n'est pas un réglage vide.
    expect(screen.getByTestId('acal700-demarrage-texte')).toHaveTextContent(/réglages vides/)
    expect(screen.getByTestId('acal700-demarrage-texte')).not.toHaveTextContent(/4 réglages|des 4/)
    expect(screen.getByTestId('acal700-demarrage-texte')).toHaveTextContent(/3 réglages vides/)
  })

  it('« Démarrage rapide » ne compte que ce que « Remplir » remplit (même liste que la page Démarrage rapide)', async () => {
    const base = COMPLET()
    const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const data = { ...base, production: borne.production, simulation: borne.simulation, cascade: JSON.parse(JSON.stringify(borne.cascade)) }
    // D-ACAL-82 : salissure et LID ont désormais une valeur de départ ; les deux lignes sans valeur publiée sont ici
    // deux réglages qui n'en ont toujours pas (fenêtres d'arrêt, modèle de dégradation).
    const SANS_VALEUR = ['indisponibilite_fenetres', 'modele_degradation']
    data.cascade.a_renseigner.lignes = data.cascade.a_renseigner.lignes.map((l, i) => (i < 2 ? { ...l, cle: SANS_VALEUR[i] } : l))
    const cles = data.cascade.a_renseigner.lignes.map((l) => l.cle)
    expect(cles).toHaveLength(3) // deux réglages sans valeur publiée ; écarts entre panneaux : valeur publiée
    servir(data)
    rendre()
    // T4-B4-003 — UN compte, lu partout : « 3 réglages vides » (compteur), dont 1 a une valeur publiée. Chaque « Remplir »
    // dit « 1 des 3 » (jamais « les 1 réglages vides » à côté de « 3 réglages vides ») et mène à la page Démarrage
    // rapide avec CE réglage seul coché (`?reglages=`), qui annonce donc le même nombre.
    expect(await screen.findByTestId('acal1833-compteur')).toHaveTextContent('3 réglages vides')
    const texte = await screen.findByTestId('acal700-demarrage-texte')
    expect(texte).toHaveTextContent(/^Remplir 1 des 3 réglages vides avec des valeurs publiées/)
    const remplir = screen.getAllByRole('link', { name: /^Remplir/ })
    expect(remplir.length).toBeGreaterThan(0)
    for (const lien of remplir) {
      expect(lien).toHaveTextContent('Remplir 1 des 3 réglages vides')
      expect(lien).toHaveAttribute('href', '/calepinage/reglages/demarrage-rapide?reglages=lid_par_techno')
    }
    expect(screen.getByTestId('acal700-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages/demarrage-rapide?reglages=lid_par_techno')
    cleanup()
    // Aucune ligne remplissable : jamais « Remplir » promis.
    data.cascade.a_renseigner.lignes = data.cascade.a_renseigner.lignes.filter((l) => SANS_VALEUR.includes(l.cle))
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

/* Item 14 (T4-U1-023) — obstacles ou voisins hauts posés : le serveur sert `ombres_non_mesurees` (à régler, phrase qui
   les nomme) au lieu de `acces_solaire_absent` ; la tuile « Ombres proches » et la liste le disent. */
describe('Étape Résultats — ombres posées mais pas encore comptées (T4-U1-023)', () => {
  const OMBRES = 'Ce toit porte 1 obstacle et 1 objet voisin qui font de l’ombre, mais cette ombre n’est pas encore comptée sur les panneaux posés : ouvrez le calcul des ombres du toit, puis enregistrez et relancez la simulation.'
  it('tuile « Ombres proches : à compter » et la phrase servie ; jamais « Aucune ombre n’est signalée »', async () => {
    servir(JAMAIS())
    const manque = MANQUE().map((m) => (m.code === 'acces_solaire_absent'
      ? { ...m, code: 'ombres_non_mesurees', gravite: 'a_regler', message: OMBRES } : m))
    render(<MemoryRouter><EtapeResultats calepinageId={5} parcours={{ manque }}
      action={{ libelle: 'Préparer les documents', onClick: vi.fn() }} /></MemoryRouter>)
    const sur = await screen.findByTestId('acal700-sur')
    expect(sur).toHaveTextContent('Ombres proches')
    expect(sur).toHaveTextContent('à compter')
    expect(sur).not.toHaveTextContent('à renseigner')
    expect(document.body.textContent).toContain(OMBRES)
    expect(document.body.textContent).not.toContain('Aucune ombre n’est signalée')
  })
})

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
    // R5B-N5 (rejeu 26/11) — la ligne des ombres menait à `?onglet=production`, l'écran même : « Renseigner » ne faisait
    // rien de visible. Elle ouvre l'étape Panneaux (premier onglet `fiches`), où l'ombre de chaque panneau se calcule.
    expect(lignes.map((l) => l.querySelector('[data-testid="cal-avant-renseigner"]').getAttribute('href'))).toEqual([
      '/calepinage/reglages#norme', '/calepinage/5?onglet=fiches', '/calepinage/reglages'])
    expect(lignes.map((l) => l.querySelector('[data-testid="cal-avant-renseigner"]').textContent)).toEqual([
      'Renseigner', 'Voir les ombres', 'Renseigner'])
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

  // T4-B4-007 — les phrases servies pour l'étape Électrique (relevées sur 1930, pile de revue) : chaque ligne dit en
  // clair « À compléter : <quoi> » et le geste ; aucune phrase de développeur, aucune ligne « À compléter » sans objet.
  it('étape Électrique : chaque ligne nomme ce qui est à compléter, jamais de phrase de développeur', async () => {
    servir(JAMAIS())
    const SERVI_1930 = [
      { code: 'verdict_electrique', message: 'À compléter', etape: 'electrique', gravite: 'a_regler', nombre: 1, cible: { onglet: 'verdict-electrique', champ: '' } },
      { code: 'materiel_designe', message: "module PV non désigné — désignez-le dans l'onglet Matériel électrique ; onduleur non désigné — désignez-le dans l'onglet Matériel électrique", etape: 'electrique', gravite: 'a_regler', nombre: 1, cible: { onglet: 'materiel-electrique', champ: '' } },
      { code: 'chutes_tension', message: "aucun cheminement n'est tracé sur ce plan : il n'y a pas de tronçon à mesurer. Tracez les liaisons dans l'atelier, ou saisissez leurs longueurs — un calepinage sans tracé n'a pas 0 % de chute, il n'a PAS de chute calculable.", etape: 'electrique', gravite: 'a_regler', nombre: 1, cible: { onglet: 'cheminement-cables', champ: '' } },
      { code: 'terre_protections', message: "Aucune norme électrique n'est choisie : les câbles et les protections ne sont pas calculés. Choisissez une norme dans les réglages du calepinage de votre société pour les calculer.", etape: 'electrique', gravite: 'a_regler', nombre: 1, cible: { onglet: 'decisions-electriques', champ: '' } },
      { code: 'divers', message: 'longueur de dossier (16 modules par chaîne) : les fiches ne permettent pas de calculer la fenêtre de tension — repli assumé, jamais présenté comme un calcul', etape: 'resultats', gravite: 'info', nombre: 14, cible: { onglet: 'production', champ: '' } },
    ]
    render(<MemoryRouter><EtapeResultats calepinageId={5} parcours={{ manque: SERVI_1930 }} /></MemoryRouter>)
    const lignes = await screen.findAllByTestId('cal-avant-ligne')
    const titres = lignes.map((l) => l.querySelector('.cal-resinc-nom').textContent.replace('?', '').trim())
    expect(titres).toEqual([
      'À compléter : le verdict électrique', 'À compléter : le panneau et l’onduleur', 'À compléter : le tracé des câbles',
      'Choisir la norme électrique de votre société', 'À vérifier : 14 valeurs supposées par le calcul'])
    const visible = lignes.map((l) => [...l.querySelectorAll('.cal-resinc-nom, .cal-resinc-raison')].map((n) => n.textContent).join(' ')).join(' ')
    expect(visible).not.toMatch(/PAS de chute|repli assumé|jamais présenté|désignez-le dans l'onglet/)
    expect(within(lignes[1]).getByText('Choisissez-les dans « Matériel électrique » (étape Électrique).')).toBeInTheDocument()
  })

  it('aucun poste à renseigner : la liste le dit au lieu de rester vide', async () => {
    servir(JAMAIS())
    render(<MemoryRouter><EtapeResultats calepinageId={5} parcours={{ manque: [] }} /></MemoryRouter>)
    expect(await screen.findByText('Rien d’autre à renseigner : vous pouvez lancer la simulation.')).toBeInTheDocument()
  })
})

/* ACAL1987 (D-ACAL-90 renversée) — la simulation part seule : `simulation_automatique` de `GET resultat/`, contrat
   `calepinage_resultat.json` (`exemple_vide` pour l'état, `acal1987_simulation_automatique` pour une pose incomplète). */
describe('Étape Résultats — la simulation part seule (ACAL1987)', () => {
  const INCOMPLETE = () => exempleContrat('calepinage', 'calepinage_resultat', 'acal1987_simulation_automatique')
  const avecAuto = (auto) => ({ ...JAMAIS(), simulation_automatique: { ...JAMAIS().simulation_automatique, ...auto } })

  it('en file : « Simulation en cours… » sans bouton de calcul, puis le résultat sans clic', async () => {
    const enCours = avecAuto({ en_cours: true, job_id: 7 })
    calepinageApi.calepinages.resultat
      .mockResolvedValueOnce({ data: enCours })
      .mockResolvedValueOnce({ data: enCours })
      .mockResolvedValue({ data: COMPLET() })
    rendre({ intervalleMs: 5 })
    expect(await screen.findByText('Simulation en cours…')).toBeInTheDocument()
    expect(document.querySelector('[data-zone="simulation-en-cours"]')).toHaveAttribute('role', 'status')
    expect(screen.queryByRole('button', { name: 'Lancer la simulation' })).toBeNull()
    expect(await screen.findByTestId('cal-resultats-tuiles')).toBeInTheDocument()
    expect(screen.queryByText('Simulation en cours…')).toBeNull()
    expect(calepinageApi.calepinages.resultat.mock.calls.length).toBeGreaterThanOrEqual(3)
  })

  it('ACAL1650 — guidé : la pastille Résultats du rail compte les manquants de la simulation automatique, et les retire au démontage sans effacer le bouton de calcul', async () => {
    const etats = { toit: 'fait', panneaux: 'fait', electrique: 'fait', resultats: 'a_faire' }
    const parcoursServi = [1, 2, 3, 4, 5].map((n) => ({ code: `x${n}`, message: `Point ${n}`, etape: 'resultats', gravite: 'a_regler', nombre: 1, cible: { onglet: 'reglages', champ: '' } }))
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: avecAuto(INCOMPLETE()) })
    const nManquants = INCOMPLETE().manquants.length
    const { unmount } = render(
      <MemoryRouter>
        <RailGuide vertical calepinageId={1} etapeActive="resultats" etats={etats} manque={parcoursServi} onChoisir={() => {}} />
        <EtapeResultats calepinageId={1} />
      </MemoryRouter>,
    )
    const pastille = () => within(screen.getByTestId('cal-etape-resultats'))
    expect(pastille().getByText('5 à régler')).toBeInTheDocument() // avant la lecture : le parcours servi
    await waitFor(() => expect(pastille().getByText(`${nManquants} à régler`)).toBeInTheDocument())
    // le bouton de calcul publie aussi : démonter l'étape ne retire que la publication de l'étape
    publierRefus(1, [{ champ: 'a', motif: 'A' }, { champ: 'b', motif: 'B' }, { champ: 'c', motif: 'C' }], 'autre')
    unmount()
    cleanup()
    render(<MemoryRouter><RailGuide vertical calepinageId={1} etapeActive="resultats" etats={etats} manque={parcoursServi} onChoisir={() => {}} /></MemoryRouter>)
    expect(within(screen.getByTestId('cal-etape-resultats')).getByText('3 à régler')).toBeInTheDocument()
    publierRefus(1, [], 'autre')
    await waitFor(() => expect(within(screen.getByTestId('cal-etape-resultats')).getByText('5 à régler')).toBeInTheDocument())
  })

  it('pose incomplète : « Il manque … » avec les phrases servies ; le bouton de calcul reste', async () => {
    rendreAvec(avecAuto(INCOMPLETE()))
    const zone = await waitFor(() => {
      const z = document.querySelector('[data-zone="simulation-manque"]')
      expect(z).not.toBeNull()
      return z
    })
    expect(zone).toHaveTextContent('Il manque une chose pour que la simulation parte seule :')
    expect(zone).toHaveTextContent(INCOMPLETE().manquants[0].motif)
    expect(screen.getByRole('button', { name: 'Lancer la simulation' })).toBeInTheDocument()
    expect(screen.queryByText('Simulation en cours…')).toBeNull()
  })

  it('rien en file ni rien qui manque (état servi par défaut) : aucun des deux blocs', async () => {
    rendreAvec(JAMAIS())
    await screen.findByTestId('cal-avant-simulation')
    expect(document.querySelector('[data-zone="simulation-manque"]')).toBeNull()
    expect(document.querySelector('[data-zone="simulation-en-cours"]')).toBeNull()
  })
})

/* ACAL1653 — à la fin d'une simulation, le bandeau d'enregistrement passe à « Simulation à jour · HH:MM » sans recharger :
   la barre écoute le résultat publié par l'étape (même canal que le résumé Expert). */
describe('Étape Résultats — le bandeau suit la fin du calcul (ACAL1653)', () => {
  // ACAL1653 (revue) — par la VRAIE coque : sa lecture de l'ouverture (`etatPropre`) primait sur la fin du calcul publiée.
  it('fin de simulation : le bandeau de la coque dit l\'heure du calcul qui vient de finir, pas celle de la lecture d\'avant', async () => {
    const ancien = { ...COMPLET(), simulation_perimee: false, calcule_le: '2026-11-26T13:10:00Z' }
    const recent = { ...COMPLET(), simulation_perimee: false, calcule_le: '2026-11-26T14:32:00Z' }
    calepinageApi.calepinages.parcours.mockResolvedValue({ data: { etapes: [], manque: [] } })
    calepinageApi.calepinages.get.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.resultat
      .mockResolvedValueOnce(lecture(ancien)) // la lecture de la coque à l'ouverture
      .mockResolvedValue(lecture(recent)) // celle de l'étape Résultats : le calcul vient de finir
    render(
      <MemoryRouter initialEntries={['/calepinage/1?onglet=production']}>
        <Routes><Route path="/calepinage/:id" element={(
          <CoqueAtelier calepinageId={1} titre="Pose" retour={{ to: "/calepinage", libelle: "Calepinages" }} enregistreLe="2026-11-26T12:00:00Z"
            enregistrement={{ libelle: 'Enregistrer le calepinage', enregistreLe: '2026-11-26T12:00:00Z' }} />
        )} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByTestId('cal-resultats-tuiles')
    const attendu = `Simulation à jour · ${formaterHeureBrouillon('2026-11-26T14:32:00Z')}`
    await waitFor(() => expect(screen.getByRole('button', { name: new RegExp(attendu) })).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: new RegExp(formaterHeureBrouillon('2026-11-26T13:10:00Z')) })).toBeNull()
  })
})

/* ACAL1653 (revue) — la pastille « N à régler » du rail est relue quand le calcul se termine (la VRAIE coque). */
describe('Étape Résultats — la pastille du rail est relue à la fin du calcul (ACAL1653)', () => {
  it('trois points à régler avant le calcul, un seul après : le rail dit le compte servi après le calcul', async () => {
    const ancien = { ...COMPLET(), simulation_perimee: false, calcule_le: '2026-11-26T13:10:00Z' }
    const recent = { ...COMPLET(), simulation_perimee: false, calcule_le: '2026-11-26T14:32:00Z' }
    const ligne = (n) => ({ code: `p${n}`, message: `Point ${n}`, etape: 'resultats', gravite: 'a_regler', nombre: 1, cible: { onglet: 'reglages', champ: '' } })
    const etapes = [{ cle: 'toit', etat: 'fait' }, { cle: 'panneaux', etat: 'fait' }, { cle: 'electrique', etat: 'fait' }, { cle: 'resultats', etat: 'en_cours' }]
    calepinageApi.calepinages.parcours
      .mockResolvedValueOnce({ data: { etapes, manque: [ligne(1), ligne(2), ligne(3)] } })
      .mockResolvedValue({ data: { etapes, manque: [ligne(1)] } })
    calepinageApi.calepinages.get.mockResolvedValue({ data: {} })
    calepinageApi.calepinages.resultat
      .mockResolvedValueOnce(lecture(ancien))
      .mockResolvedValue(lecture(recent))
    render(
      <MemoryRouter initialEntries={['/calepinage/1?onglet=production']}>
        <Routes><Route path="/calepinage/:id" element={(
          <CoqueAtelier calepinageId={1} titre="Pose" retour={{ to: '/calepinage', libelle: 'Calepinages' }} enregistreLe="2026-11-26T12:00:00Z"
            enregistrement={{ libelle: 'Enregistrer le calepinage', enregistreLe: '2026-11-26T12:00:00Z' }} />
        )} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByTestId('cal-resultats-tuiles')
    await waitFor(() => expect(within(screen.getByTestId('cal-etape-resultats')).getByText('1 à régler')).toBeInTheDocument())
    expect(calepinageApi.calepinages.parcours.mock.calls.length).toBeGreaterThanOrEqual(2)
  })
})

describe('Étape Résultats — calcul à refaire (simulation périmée)', () => {
  it('même mise en page, titre « Calcul à refaire », bouton de relance, aucun bandeau en plus', async () => {
    rendreAvec(PERIME())
    await screen.findByTestId('cal-avant-simulation')
    expect(screen.getByTestId('cal-avant-simulation')).toHaveAttribute('data-etat', 'perime')
    expect(screen.getByTestId('cal-avant-titre')).toHaveTextContent('Calcul à refaire')
    // T4-X3-012 — le motif nomme AUSSI les réglages de la société (ils périment le calcul sans toucher au toit).
    expect(screen.getByTestId('cal-avant-phrase')).toHaveTextContent('ou un réglage de votre société a changé depuis le dernier calcul')
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

  // T4-X7-010 — au doigt (tablette), le lien du devis mesurait 114 × 18 : une cible d'au moins 44 px de haut.
  it('T4-X7-010 — au doigt, le lien du devis est une cible de 44 px de haut', async () => {
    const style = feuilleAuDoigt('src/styles/calepinage/54-etape-resultats.css')
    try {
      rendreAvec({ ...JAMAIS(), production_devis: PROD() })
      const lien = await screen.findByRole('link', { name: PROD().reference })
      expect(getComputedStyle(lien).minHeight).toBe('44px')
    } finally { style.remove() }
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

  // ACAL1755 (D-ACAL-86 : un seul chiffre, le plus réaliste ; D-ACAL-96 : un devis envoyé n'est jamais modifié, la révision est proposée).
  describe('ACAL1755 — un seul chiffre, ou les deux nommés avec « Réviser le devis »', () => {
    const zone = () => document.querySelector('[data-zone="production-devis"]')

    it('simulation et devis portent le même chiffre : UN seul chiffre, ni deuxième ligne ni bouton', async () => {
      const d = COMPLET()
      d.production_devis = { ...PROD(), production_annuelle_kwh: d.production.total.p50_kwh }
      servir(d)
      rendre()
      await screen.findByRole('link', { name: PROD().reference })
      expect(zone()).toHaveAttribute('data-chiffre', 'un-seul')
      expect(zone()).toHaveTextContent(`Production : ${kwh(d.production.total.p50_kwh)}`)
      expect(zone()).not.toHaveTextContent('Production simulée de la pose')
      expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
    })

    it('devis envoyé, chiffres différents : les deux nommés, le devis n’est pas touché, « Réviser le devis » crée la V2', async () => {
      const d = { ...COMPLET(), production_devis: PROD() }
      servir(d)
      ventesApi.reviserDevis.mockResolvedValue({ data: { id: 99, reference: 'DEV-V2' } })
      rendre()
      await screen.findByRole('link', { name: PROD().reference })
      expect(zone()).toHaveAttribute('data-chiffre', 'deux')
      expect(zone()).toHaveTextContent('Le devis envoyé n’est pas modifié')
      fireEvent.click(screen.getByRole('button', { name: 'Réviser le devis' }))
      await waitFor(() => expect(ventesApi.reviserDevis).toHaveBeenCalledWith(PROD().devis))
      expect(ventesApi.reviserDevis).toHaveBeenCalledTimes(1)
    })

    it('devis lié sans statut reçu (écart servi seul) : les deux chiffres nommés, aucun bouton de révision', async () => {
      const d = COMPLET()
      d.ecart_devis = { devis: 412, reference: 'DEV-202610-0042', production_devis_kwh: 12600, p50_calepinage_kwh: 13000, ecart_pct: 3.2, mention: '' }
      servir(d)
      rendre()
      await screen.findByRole('link', { name: 'DEV-202610-0042' })
      expect(zone()).toHaveTextContent(`Production retenue par le devis : ${kwh(12600)}`)
      expect(zone()).toHaveTextContent(`Production simulée de la pose : ${kwh(d.production.total.p50_kwh)}`)
      expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
    })

    it('simulation incomplète (plafond) : jamais comparée au devis', async () => {
      const base = COMPLET()
      const borne = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
      servir({ ...base, production: borne.production, simulation: borne.simulation, cascade: borne.cascade, production_devis: PROD() })
      rendre()
      await screen.findByRole('link', { name: PROD().reference })
      expect(zone()).toHaveTextContent('La simulation de la pose est incomplète')
      expect(zone()).not.toHaveTextContent('Production simulée de la pose')
      expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
    })
  })
})

/* ACAL2015 (C4-E5, D-ACAL-96) — Résultats montre LA conception (bloc `conception` de `GET resultat/`) : UN chiffre par valeur
   sans devis et en brouillon ; un devis ENVOYÉ différent est NOMMÉ (« devis DEV-… envoyé le … : … ») avec « Réviser le devis ».
   Les lignes d'écart du mock sont construites sur `ecart_devis` du contrat `conception_lead.json` (ventes). */
describe('Étape Résultats — la conception, et l’écart avec le devis envoyé (ACAL2015)', () => {
  const kwh = (n) => `${formatNumber(n, { decimals: 0 })} kWh par an`.replace(/\s+/g, ' ')
  const LIGNE = () => exempleContrat('ventes', 'conception_lead', 'exemple').ecart_devis[0]
  const SERVI = () => JSON.parse(JSON.stringify(exempleContrat('calepinage', 'calepinage_resultat', 'acal2015_conception')))
  const zone = () => document.querySelector('[data-zone="production-conception"]')
  const sans = () => ({ ...SERVI(), devis_envoye: null })

  it('sans devis : la conception ET la pose simulée, chacune sous son nom exact (relecture E5 M1)', async () => {
    servir({ ...COMPLET(), conception: sans() })
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(zone()).toHaveAttribute('data-chiffre', 'un-seul')
    expect(zone()).toHaveTextContent(`Production de la conception : ${kwh(sans().production_annuelle_kwh)}`)
    // Mutant « libellé d'avant » : « Production la première année » à côté d'un autre chiffre de production.
    expect(document.querySelector('[data-tuile="heros"]')).toHaveTextContent('Production simulée de la pose')
    expect(document.body).not.toHaveTextContent('Production la première année')
    expect(screen.getByTestId('cal-resultats-mois')).toHaveTextContent('Mois par mois · Production simulée de la pose')
    expect(document.body).not.toHaveTextContent('Production retenue par le devis')
    expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
  })

  it('D-ACAL-109 / 110 — les phrases servies sur le matériel désigné sont affichées telles quelles ; aucune sans désignation', async () => {
    const bloc = sans()
    servir({ ...COMPLET(), conception: bloc })
    const { unmount } = rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    const dites = [...document.querySelectorAll('[data-zone="designation-conception"]')].map((p) => p.textContent)
    expect(bloc.designations.length).toBeGreaterThan(0)
    expect(dites).toEqual(bloc.designations)
    unmount()
    servir({ ...COMPLET(), conception: { ...sans(), designations: [] } })
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(document.querySelector('[data-zone="designation-conception"]')).toBeNull()
  })

  it('brouillon lié (écart de l’atelier servi) : toujours UN seul chiffre, aucun bouton', async () => {
    const d = { ...COMPLET(), conception: sans() }
    d.ecart_devis = { devis: 412, reference: 'DEV-202610-0042', production_devis_kwh: 12600, p50_calepinage_kwh: 13000, ecart_pct: 3.2, mention: '' }
    servir(d)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(zone()).toHaveAttribute('data-chiffre', 'un-seul')
    expect(document.body).not.toHaveTextContent('Production retenue par le devis')
    expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
  })

  it('devis envoyé différent : la conception, puis le devis NOMMÉ avec sa date, et « Réviser le devis » crée la V2', async () => {
    const bloc = SERVI()  // le devis envoyé range 6 047 kWh (contrat), la conception 8 198
    bloc.devis_envoye.ecart_devis = [LIGNE(), { ...LIGNE(), valeur: 'production_annuelle', devis: 6047, conception: 8198 }]
    servir({ ...JAMAIS(), conception: bloc })
    ventesApi.reviserDevis.mockResolvedValue({ data: { id: 99, reference: 'DEV-V2' } })
    rendre()
    await screen.findByRole('link', { name: bloc.devis_envoye.reference })
    expect(zone()).toHaveAttribute('data-chiffre', 'deux')
    expect(zone()).toHaveTextContent(`Production de la conception : ${kwh(bloc.production_annuelle_kwh)}`)
    expect(zone()).toHaveTextContent(`Devis ${bloc.devis_envoye.reference} envoyé le 10/11/2026 : ${kwh(6047)}`)
    expect(zone()).toHaveTextContent('Le devis envoyé n’est pas modifié')
    fireEvent.click(screen.getByRole('button', { name: 'Réviser le devis' }))
    // T4-X5-011 — la V2 née de ce bouton est composée sur la conception courante du lead.
    await waitFor(() => expect(ventesApi.reviserDevis)
      .toHaveBeenCalledWith(bloc.devis_envoye.devis, { sur_la_conception: true }))
  })

  it('T4-X7-006 — la révision est dite telle qu’elle est (copie remise sur la conception, la pose par la resynchronisation)', async () => {
    const bloc = SERVI()
    bloc.devis_envoye.ecart_devis = [LIGNE(), { ...LIGNE(), valeur: 'production_annuelle', devis: 6047, conception: 8198 }]
    servir({ ...JAMAIS(), conception: bloc })
    rendre()
    await screen.findByRole('link', { name: bloc.devis_envoye.reference })
    const phrase = document.querySelector('[data-zone="reviser-explique"]')
    expect(phrase).toHaveTextContent('copie de ce devis remise sur la conception du lead si elle a changé depuis')
    expect(phrase).toHaveTextContent('Votre pose n’y entre qu’en resynchronisant cette nouvelle version')
    expect(zone()).not.toHaveTextContent('crée une nouvelle version sur la conception.')
  })

  it('T4-X7-006 — après la révision, la V2 liée qui ne porte pas la pose reste NOMMÉE ; à jour ou absente : rien', async () => {
    const lie = { devis: 2892, reference: 'DEV-202611-0161', statut: 'brouillon', a_jour: false }
    servir({ ...JAMAIS(), conception: { ...sans(), devis_lie: lie } })
    const { unmount } = rendre()
    const ligne = await waitFor(() => {
      const el = document.querySelector('[data-zone="devis-lie-pose"]')
      expect(el).not.toBeNull()
      return el
    })
    expect(ligne).toHaveTextContent('Le devis lié DEV-202611-0161 ne porte pas votre pose : « Resynchroniser le devis »')
    expect(within(ligne).getByRole('link', { name: 'DEV-202611-0161' })).toHaveAttribute('href', '/ventes/devis?devis=2892')
    unmount()
    servir({ ...JAMAIS(), conception: { ...sans(), devis_lie: { ...lie, a_jour: true } } })
    rendre()
    await screen.findByText(/Production de la conception/)
    expect(document.querySelector('[data-zone="devis-lie-pose"]')).toBeNull()
  })

  it('devis envoyé au même chiffre de production : UN seul chiffre, pas de bouton', async () => {
    const bloc = SERVI()
    bloc.devis_envoye.ecart_devis = [LIGNE()]
    bloc.devis_envoye.production_annuelle_kwh = bloc.production_annuelle_kwh
    servir({ ...JAMAIS(), conception: bloc })
    rendre()
    await screen.findByRole('link', { name: bloc.devis_envoye.reference })
    expect(zone()).toHaveAttribute('data-chiffre', 'un-seul')
    expect(zone()).toHaveTextContent(`Production de la conception : ${kwh(bloc.production_annuelle_kwh)}`)
    expect(zone()).not.toHaveTextContent(`Devis ${bloc.devis_envoye.reference} envoyé le`)
    expect(zone()).toHaveTextContent('porte le même chiffre')
    expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
  })

  /* T4-X5-001 — la production de la conception est celle de SA taille (`chiffrage.kwc` du design-context, le même
     lecteur que la bande Panneaux et la vue client) : à côté d'une pose d'une autre taille, la ligne nomme les deux. */
  const contexteDeTaille = (kwc, panneaux) => ({
    data: { chiffrage: { kwc: { valeur: kwc, unite: 'kWc', etat: 'servi' } }, cible: { panneaux, kwc } },
  })
  const kwc = (n) => `${formatNumber(n, { decimals: 2 })} kWc`.replace(/\s+/g, ' ')
  // Serveur d'avant T4-X7-013 (bloc sans sa taille) : la taille se lit sur le design-context.
  const sansTaille = () => { const b = sans(); delete b.puissance_kwc; delete b.nb_panneaux; return b }

  /* T4-X7-013 — « 5 677 kWh … calculée pour 3,85 kWc (7 panneaux de 550 W) » : la production d'une conception refaite au
     module de la pose (5 × 710 W), à côté de la taille d'une lecture plus ancienne. La taille vient du MÊME bloc. */
  it('T4-X7-013 — la production de la conception porte SA taille servie, jamais celle d’une autre lecture', async () => {
    const d = { ...COMPLET(), conception: { ...sans(), production_annuelle_kwh: 5677, puissance_kwc: 3.55, nb_panneaux: 5 } }
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { chiffrage: { kwc: { valeur: 3.85, unite: 'kWc', etat: 'servi' } }, cible: { panneaux: 7, kwc: 3.85, panel_watt: 550 } },
    })
    servir(d)
    rendre()
    await waitFor(() => expect(zone()).toHaveTextContent(
      `Production de la conception : ${kwh(5677)}, calculée pour la conception du lead : ${kwc(3.55)} (5 panneaux) — `))
    expect(zone()).not.toHaveTextContent('3,85')
    expect(zone()).not.toHaveTextContent('550 W')
  })

  it('T4-X7-013 — conception servie à la taille de la pose : UNE ligne, même si le design-context dit une autre taille', async () => {
    const d = { ...COMPLET(), conception: sans() }  // bloc : 8,64 kWc · 12 panneaux, comme la pose du contrat
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(3.85, 7))
    servir(d)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    await waitFor(() => expect(calepinageApi.calepinages.designContext).toHaveBeenCalled())
    expect(zone()).toHaveTextContent(`Production de la conception : ${kwh(sans().production_annuelle_kwh)}`)
    expect(zone()).not.toHaveTextContent('votre pose en compte')
    expect(zone()).not.toHaveTextContent('3,85')
  })

  it('T4-X5-001 — conception d’une autre taille que la pose : sa taille, son chiffre, et la pose renvoyée à sa simulation', async () => {
    const d = { ...COMPLET(), conception: sansTaille() }  // pose du contrat : 12 panneaux · 8,64 kWc
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(2.13, 3))
    servir(d)
    rendre()
    // Le motif de la bande Panneaux et de la vue client (`affichageErp.ts::raisonSansValeur`), mot pour mot.
    await waitFor(() => expect(zone()).toHaveTextContent(
      `Production de la conception : ${kwh(sans().production_annuelle_kwh)}, calculée pour la conception du lead : `
      + `${kwc(2.13)} (3 panneaux) — votre pose en compte ${kwc(d.pose.kwc)} (${d.pose.total_modules} panneaux).`))
    expect(zone()).toHaveTextContent('La production simulée de votre pose est ci-dessous.')
  })

  it('T4-X3-009 — la conception compte 8 panneaux de 550 W : la ligne NOMME son panneau, jamais un « 8 » nu', async () => {
    const d = { ...COMPLET(), conception: sansTaille() }
    calepinageApi.calepinages.designContext.mockResolvedValue({
      data: { chiffrage: { kwc: { valeur: 4.4, unite: 'kWc', etat: 'servi' } }, cible: { panneaux: 8, kwc: 4.4, panel_watt: 550 } },
    })
    servir(d)
    rendre()
    await waitFor(() => expect(zone()).toHaveTextContent(
      `calculée pour la conception du lead : ${kwc(4.4)} (8 panneaux de 550 W) — votre pose en compte`))
  })

  it('T4-X5-001 — même taille que la pose : UNE ligne, sans renvoi', async () => {
    const d = { ...COMPLET(), conception: sans() }
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(d.pose.kwc, d.pose.total_modules))
    servir(d)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    await waitFor(() => expect(calepinageApi.calepinages.designContext).toHaveBeenCalled())
    expect(zone()).toHaveTextContent(`Production de la conception : ${kwh(sans().production_annuelle_kwh)}`)
    expect(zone()).not.toHaveTextContent('votre pose en compte')
  })

  /* T4-X9-008 — la jauge « De la consommation » (74 %) posée à côté de « Production simulée de la pose » était la part de
     la CONCEPTION (4,40 kWc), pas celle de la pose (5,68 kWc) : à une autre taille, la phrase remplace le chiffre. */
  it('T4-X9-008 — conception d’une autre taille : la jauge dit la phrase des deux tailles, aucun pourcentage', async () => {
    const d = { ...COMPLET(), conception: sansTaille() }  // pose du contrat : 12 panneaux · 8,64 kWc
    d.autoconsommation = { ...d.autoconsommation, taux_source: 'conception' }  // serveur : taux de la conception publiés
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(2.13, 3))
    servir(d)
    rendre()
    const tuile = () => document.querySelector('[data-tuile="couverture"]')
    await waitFor(() => expect(tuile()).toHaveTextContent(
      `Part de la consommation calculée pour la conception du lead : ${kwc(2.13)} — votre pose en compte ${kwc(d.pose.kwc)}.`))
    expect(tuile()).not.toHaveTextContent('%')
    expect(tuile().querySelector('svg')).toBeNull()
  })

  /* T4-X7-002 — conception « 7 panneaux + batterie » (76 %), pose de 5 panneaux sans batterie : le serveur trouve l'écart
     et publie les taux de la POSE (`taux_source: 'autre_installation'`) ; la jauge les montre, aucune phrase d'une autre taille. */
  it('T4-X7-002 — écart réel (`autre_installation`) : la jauge montre CE pourcentage, jamais la phrase de la conception', async () => {
    const d = { ...COMPLET(), conception: sansTaille() }
    d.autoconsommation = { ...d.autoconsommation, taux_source: 'autre_installation', taux_couverture: 0.474 }
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(2.13, 3))
    servir(d)
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.designContext).toHaveBeenCalled())
    const tuile = () => document.querySelector('[data-tuile="couverture"]')
    await waitFor(() => expect(tuile()).toHaveTextContent('47 %'))
    expect(tuile()).not.toHaveTextContent('calculée pour la conception du lead')
  })

  /* Revue du 25/11 — `'pose'` sans écart = aucun taux de conception au moment de la simulation : l'écran fait comme avant
     (deux tailles connues et différentes ⇒ la phrase des deux tailles), jamais comme pour un écart réel. */
  it('T4-X7-002 — aucun taux de conception (`pose`) : comme avant, la phrase des deux tailles quand elles diffèrent', async () => {
    const d = { ...COMPLET(), conception: sansTaille() }
    d.autoconsommation = { ...d.autoconsommation, taux_source: 'pose' }
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(2.13, 3))
    servir(d)
    rendre()
    const tuile = () => document.querySelector('[data-tuile="couverture"]')
    await waitFor(() => expect(tuile()).toHaveTextContent(
      `Part de la consommation calculée pour la conception du lead : ${kwc(2.13)} — votre pose en compte ${kwc(d.pose.kwc)}.`))
  })

  it('T4-X9-008 — même taille : la jauge garde son pourcentage', async () => {
    const d = { ...COMPLET(), conception: sans() }
    calepinageApi.calepinages.designContext.mockResolvedValue(contexteDeTaille(d.pose.kwc, d.pose.total_modules))
    servir(d)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    await waitFor(() => expect(calepinageApi.calepinages.designContext).toHaveBeenCalled())
    expect(document.querySelector('[data-tuile="couverture"]')).toHaveTextContent('%')
  })

  /* Relecture E5 M2 — « porte le même chiffre » n'est dit que si la production RANGÉE par le devis (servie) l'égale. */
  it('M2 — aucune ligne d’écart mais le devis a retenu « avec » à 6 047 kWh : les deux chiffres nommés et « Réviser »', async () => {
    const bloc = SERVI()
    bloc.devis_envoye.ecart_devis = []  // l'écart de ventes compare l'option DU DEVIS : il peut ne rien dire
    bloc.devis_envoye.option = 'avec'
    servir({ ...JAMAIS(), conception: bloc })
    rendre()
    await screen.findByRole('link', { name: bloc.devis_envoye.reference })
    expect(zone()).toHaveAttribute('data-chiffre', 'deux')  // mutant « absence de ligne = même chiffre » : un-seul
    expect(zone()).not.toHaveTextContent('porte le même chiffre')
    expect(zone()).toHaveTextContent(
      `Devis ${bloc.devis_envoye.reference} envoyé le 10/11/2026 (option avec batterie) : ${kwh(6047)}`)
    expect(screen.getByRole('button', { name: 'Réviser le devis' })).toBeInTheDocument()
  })

  it('M2 — le devis envoyé ne range aucune production : il le DIT, jamais « le même chiffre »', async () => {
    const bloc = SERVI()
    bloc.devis_envoye.ecart_devis = []
    bloc.devis_envoye.production_annuelle_kwh = null
    servir({ ...JAMAIS(), conception: bloc })
    rendre()
    await screen.findByRole('link', { name: bloc.devis_envoye.reference })
    expect(zone()).toHaveTextContent(`Le devis envoyé ${bloc.devis_envoye.reference} ne porte pas de production enregistrée.`)
    expect(zone()).not.toHaveTextContent('porte le même chiffre')
    expect(screen.queryByRole('button', { name: 'Réviser le devis' })).toBeNull()
  })
})

/* ACAL1912 (rejeu T3-VAGUEC du 23/11) — Guidé > Résultats dit les panneaux posés mais non raccordés : la phrase SERVIE en tête
   de `avertissements`, et la production rapportée aux panneaux COMPTÉS (jamais « 13 panneaux » à côté d'un productible
   de 9). Tout vient de `GET resultat/` : `production.hors_chaine.modules`, `pose.*`, `production.total.kwc`. */
describe('Étape Résultats — panneaux posés mais non raccordés (ACAL1912)', () => {
  // Revue lot 6 (ACAL1623) — l'exemple du contrat : la phrase sur SA clé, la « borne haute » EN TÊTE des avertissements.
  const SERVI = exempleContrat('calepinage', 'calepinage_resultat', 'acal1623_non_raccordes')
  const PHRASE = SERVI.panneaux_non_raccordes.phrase
  const BORNE = SERVI.avertissements[0]
  const NON_RACCORDES = () => {
    const d = COMPLET()
    d.pose = { ...d.pose, total_modules: 13, kwc: 9.23 }
    d.production.total.kwc = 6.39
    d.production.hors_chaine = { modules: 4, p50_kwh: 3300 }
    d.panneaux_non_raccordes = SERVI.panneaux_non_raccordes
    d.avertissements = [...SERVI.avertissements, 'Longueur de chaîne à vérifier.']
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
    // La « borne haute » est en tête des avertissements : elle ne titre jamais ce bloc.
    expect(BORNE).not.toBe(PHRASE)
    expect(zone()).not.toHaveTextContent(BORNE)
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

describe('ACAL1268 (D-ACAL-66 = outil_pose) — l’étape Résultats d’un lead de pompage', () => {
  const CONTEXTE = (marche) => {
    const c = JSON.parse(JSON.stringify(exempleContrat('calepinage', 'calepinage_design_context')))
    c.chiffrage.marche = marche
    return c
  }

  it('pompage : ni production, ni couverture, ni économies, ni réseau ; un renvoi vers le devis agricole et le pied', async () => {
    servir(COMPLET())
    const contexte = CONTEXTE('agricole')
    rendre({ contexte })
    const pied = await screen.findByTestId('cal-resultats-pied')
    expect(pied).toBeInTheDocument()
    expect(screen.queryByTestId('cal-resultats-tuiles')).toBeNull()
    expect(screen.queryByTestId('cal-resultats-mois')).toBeNull()
    expect(screen.queryByTestId('cal-resultats-pertes')).toBeNull()
    const carte = document.querySelector('[data-zone="pompage-outil-pose"]')
    expect(carte).toHaveTextContent('sans économies ni énergie du réseau')
    // Sans devis agricole servi : la création, dite comme telle.
    expect(within(carte).getByRole('link', { name: 'Créer le devis agricole' }))
      .toHaveAttribute('href', `/ventes/devis/nouveau?lead=${contexte.calepinage.lead}`)
    cleanup()
    servir(COMPLET())
    rendre({ contexte: { ...contexte, cible: { ...contexte.cible, devis_agricole: { id: 42, reference: 'DEV-AGR-42' } } } })
    // Avec le devis agricole servi : le lien ouvre CE devis, jamais un formulaire vierge.
    expect(await screen.findByRole('link', { name: 'Ouvrir le devis agricole DEV-AGR-42' }))
      .toHaveAttribute('href', '/ventes/devis?devis=42')
    expect(document.body.textContent).not.toMatch(/kWh par an|autoconsommation/i)
  })

  it('pas un pompage : le rendu est identique octet pour octet à celui sans contexte', async () => {
    servir(COMPLET())
    const { container, unmount } = rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    const sansContexte = container.innerHTML
    unmount()
    servir(COMPLET())
    const { container: autre } = rendre({ contexte: CONTEXTE('residentiel') })
    await screen.findByTestId('cal-resultats-tuiles')
    expect(autre.innerHTML).toBe(sansContexte)
    expect(document.querySelector('[data-zone="pompage-outil-pose"]')).toBeNull()
  })
})

/* ACAL1630 — « Ce qui est supposé » (`suppose[]` de `GET resultat/`) rendu par l'étape Résultats, sous la production. */
describe('Étape Résultats — ce qui est supposé (ACAL1630)', () => {
  it('suppose servi ⇒ section rendue sous la production, une ligne par repli avec son champ à renseigner', async () => {
    const d = COMPLET()
    d.suppose = [
      { code: 'longueur_chaine_dossier', libelle: 'Longueur de chaîne de dossier : 16 modules', valeur: 16, champ: 'fiche technique du module et de l’onduleur' },
      { code: 'allee_par_defaut', libelle: 'Allée : 0,60 m', valeur: 0.6, champ: 'panneau Allées de l’atelier' },
    ]
    servir(d)
    rendre()
    const section = await screen.findByTestId('acal980-suppose')
    expect(section).toHaveTextContent('Ce qui est supposé')
    expect(within(section).getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByTestId('acal980-longueur_chaine_dossier')).toHaveTextContent('Longueur de chaîne de dossier : 16 modules')
    expect(screen.getByTestId('acal980-allee_par_defaut')).toHaveTextContent('À renseigner : panneau Allées de l’atelier')
    expect(screen.getByTestId('cal-resultats-tuiles').compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('ACAL1630 (revue) — un repli qui porte sa cible mène au champ ; sans cible, le champ reste du texte', async () => {
    const d = COMPLET()
    d.suppose = [
      { code: 'longueur_chaine_dossier', libelle: 'Longueur : 16 modules', valeur: 16, champ: 'fiche technique du module et de l’onduleur', cible: { onglet: 'fiches' } },
      { code: 'allee_par_defaut', libelle: 'Allée : 0,60 m', valeur: 0.6, champ: 'panneau Allées de l’atelier', cible: { onglet: 'reglages', champ: 'allees' } },
      { code: 'sans_cible', libelle: 'Autre repli', valeur: 1, champ: 'un champ sans cible' },
    ]
    servir(d)
    rendre()
    const fiches = await screen.findByTestId('acal980-longueur_chaine_dossier')
    expect(within(fiches).getByRole('link', { name: /fiche technique du module/ })).toHaveAttribute('href', '/calepinage/1?onglet=fiches')
    expect(within(screen.getByTestId('acal980-allee_par_defaut')).getByRole('link', { name: /Allées de l’atelier/ }))
      .toHaveAttribute('href', '/calepinage/reglages/allees')
    const sans = screen.getByTestId('acal980-sans_cible')
    expect(sans).toHaveTextContent('À renseigner : un champ sans cible')
    expect(within(sans).queryByRole('link')).toBeNull()
  })

  it('aucune supposition servie ⇒ aucune section', async () => {
    const d = COMPLET()
    d.suppose = []
    servir(d)
    rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(screen.queryByTestId('acal980-suppose')).toBeNull()
  })
})

/* ACAL1638 — « Le devis annonce » à l'étape Résultats guidée : le chiffre IMPRIMÉ par le devis lié et l'écart servi
   (`ecart_devis`, ACAL104) avec l'étude technique. Sans devis lié, aucune ligne. */
describe('Étape Résultats — « Le devis annonce » (ACAL1638)', () => {
  const ECART = { devis: 412, reference: 'DEV-202610-0042', production_devis_kwh: 12600, p50_calepinage_kwh: 13000, ecart_pct: 3.2, mention: '' }

  it('devis lié ⇒ la ligne dit ce que le devis imprime et l’écart avec l’étude technique', async () => {
    const d = COMPLET()
    d.ecart_devis = ECART
    servir(d)
    rendre()
    const ligne = await screen.findByTestId('acal1638-devis-annonce')
    expect(ligne).toHaveTextContent(/^Le devis annonce : 12\s600 kWh\/an \(étude technique : \+3,2 %\)$/)
  })

  it('sans devis lié, ou écart non servi ⇒ aucune ligne ; sans écart servi, le chiffre seul', async () => {
    servir(COMPLET())
    const { unmount } = rendre()
    await screen.findByTestId('cal-resultats-tuiles')
    expect(screen.queryByTestId('acal1638-devis-annonce')).toBeNull()
    unmount()
    const d = COMPLET()
    d.ecart_devis = { ...ECART, ecart_pct: null }
    servir(d)
    rendre()
    expect(await screen.findByTestId('acal1638-devis-annonce')).toHaveTextContent(/^Le devis annonce : 12\s600 kWh\/an$/)
  })
})

/* ACAL1676 — les cinq postes de « Du soleil au réseau », le poste non compté avec son motif ; les barres ne cumulent que
   les postes comptés. ACAL1632 — la note « valeurs publiées » : noms en clair, pertes seulement. ACAL1933 — la phrase
   des étapes que PVGIS compte et pas nous. */
describe('Étape Résultats — « Du soleil au réseau » à cinq postes (ACAL1676)', () => {
  const avecOmbresNonComptees = () => {
    const d = COMPLET_MAQUETTE()
    const [ombres, ...autres] = d.cascade.postes_lisibles.postes
    d.cascade.postes_lisibles.postes = [
      { ...ombres, perte_kwh: null, perte_pct: null, statut: 'non_compte', cause: 'aucun obstacle saisi',
        etapes: [{ etape: 'ombrage_proche', motif_omission: 'Le document de toiture ne porte aucun obstacle saisi : l’ombre portée par les objets hauts du toit ne peut pas être comptée (ACAL1676, texte technique long).' }] },
      ...autres,
    ]
    d.cascade.postes_lisibles.arrivee_pct = 84.4
    return d
  }

  it('cinq postes : « Ombres proches — non compté : aucun obstacle saisi », sans barre ; les barres ne cumulent que les postes comptés', async () => {
    servir(avecOmbresNonComptees())
    rendre()
    const carte = await screen.findByTestId('cal-resultats-pertes')
    const postes = [...carte.querySelectorAll('.cal-res-poste[data-statut]')]
    expect(postes).toHaveLength(5)
    const ombres = carte.querySelector('[data-poste="ombres_proches"]')
    expect(ombres).toHaveTextContent('Ombres proches')
    expect(ombres).toHaveTextContent('non compté')
    // La CAUSE courte servie (`cause`), jamais le paragraphe technique de `etapes[].motif_omission`.
    expect(ombres).toHaveTextContent('non compté — aucun obstacle saisi')
    expect(ombres).not.toHaveTextContent('document de toiture')
    expect(ombres.querySelector('.cal-res-piste')).toBeNull()
    // Les quatre autres : le restant part de 100 (le poste non compté ne retire rien).
    const pistes = [...carte.querySelectorAll('.cal-res-poste[data-statut="compte"] .cal-res-piste')]
    expect(pistes).toHaveLength(4)
    expect(Number.parseFloat(pistes[0].firstElementChild.style.width)).toBeCloseTo(97, 5)
    expect(Number.parseFloat(pistes[3].firstElementChild.style.width)).toBeCloseTo(100 - 3 - 6.4 - 4.5 - 3.1, 5)
  })
})

describe('Étape Résultats — poste non compté sans `cause` servie (ACAL1676)', () => {
  it('ancienne réponse : « non compté » seul, aucun paragraphe brut recopié', async () => {
    const d = COMPLET_MAQUETTE()
    const [ombres, ...autres] = d.cascade.postes_lisibles.postes
    d.cascade.postes_lisibles.postes = [
      { ...ombres, perte_kwh: null, perte_pct: null, statut: 'non_compte',
        etapes: [{ etape: 'ombrage_proche', motif_omission: 'Paragraphe technique du serveur qui ne doit pas être recopié.' }] },
      ...autres,
    ]
    servir(d)
    rendre()
    const carte = await screen.findByTestId('cal-resultats-pertes')
    const poste = carte.querySelector('[data-poste="ombres_proches"]')
    expect(poste).toHaveTextContent('non compté')
    expect(poste).not.toHaveTextContent('Paragraphe technique')
    expect(poste).not.toHaveTextContent('non compté —')
  })
})

describe('Étape Résultats — note des valeurs publiées (ACAL1632)', () => {
  it('la note nomme chaque réglage en clair, ne compte que les pertes : aucune clé « electrique_societe.* »', async () => {
    const d = COMPLET_MAQUETTE()
    const ref = 'Profil de départ — PVsyst, Array and system losses'
    d.simulation = { ...d.simulation, reglages_utilises: {
      ...d.simulation.reglages_utilises,
      'electrique_societe.seuil_bas_dc_ac': { valeur: 0.8, source: 'profil', reference: ref },
      'electrique_societe.tolerance_polystring_bloquante_pct': { valeur: 10, source: 'profil', reference: ref },
      'electrique_societe.tolerance_polystring_acceptable_pct': { valeur: 5, source: 'profil', reference: ref },
    } }
    servir(d)
    rendre()
    const note = await screen.findByTestId('acal698-texte-note')
    expect(note).toHaveTextContent('3 réglages utilisent des valeurs publiées')
    expect(note).not.toHaveTextContent('electrique_societe')
    expect(note).not.toHaveTextContent(/seuil_bas|polystring|taille minimale|entre chaînes/i)
    expect(note).not.toHaveTextContent('_')
  })
})

describe('Étape Résultats — étapes que PVGIS compte et pas nous (ACAL1933)', () => {
  it('omises_vs_pvgis servie : « sans la chaleur des panneaux, que PVGIS compte », aucune mention d’égalité', async () => {
    const d = COMPLET_MAQUETTE()
    d.validation.pertes_totales = { ...d.validation.pertes_totales, egales: false,
      omises_vs_pvgis: [{ etape: 'thermique', libelle: 'Échauffement des modules', designation: 'la chaleur des panneaux' }] }
    servir(d)
    rendre()
    const tuile = (await screen.findByTestId('cal-resultats-tuiles')).querySelector('[data-tuile="ecart-pvgis"]')
    expect(tuile).toHaveTextContent('sans la chaleur des panneaux, que PVGIS compte')
    expect(tuile).not.toHaveTextContent('pertes système égales')
  })

  it('rien d’omis (liste vide) : pas de phrase « que PVGIS compte »', async () => {
    const d = COMPLET_MAQUETTE()
    d.validation.pertes_totales = { ...d.validation.pertes_totales, omises_vs_pvgis: [] }
    servir(d)
    rendre()
    const tuile = (await screen.findByTestId('cal-resultats-tuiles')).querySelector('[data-tuile="ecart-pvgis"]')
    expect(tuile).not.toHaveTextContent('que PVGIS compte')
  })
})
