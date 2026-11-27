/* CAL143 — le diagramme de pertes (cascade) du module calepinage.

   Ce qui est prouvé ici : chaque poste vient EXACTEMENT du contrat
   `apps/calepinage/contract_samples/calepinage_resultat.json`
   (`production.pertes`, PACT10/13 — `reponseContrat`), un poste non sourcé
   (`source: null`) reste NOMMÉ (jamais masqué) et sa colonne Source affiche
   « — », et l'absence de pertes (non simulé) dit pourquoi plutôt que
   d'afficher un graphe vide silencieux. */
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { resultat: vi.fn(), simuler: vi.fn() },
    moteur: { resultat: vi.fn() },
  },
}))

/* ACAL125 — le bouton de calcul est sous `calepinage_gerer` (doublure : pas de Provider Redux). */
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => true }))

import calepinageApi from '../../../api/calepinageApi'
import DiagrammePertes from './DiagrammePertes'
import { construireCascadeDetaillee } from './DiagrammePertes.helpers'
import { NOMS_PERTES, nomDePerte } from './nomsPertes'
import { polyfillResizeObserver } from '../../../test/selectNatif'

beforeAll(polyfillResizeObserver)

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

/* CALX48 — `exemple` porte DÉSORMAIS aussi une `cascade` (CALX141), que le
   panneau affiche en PRIORITÉ (Done) : la liste plate reste testée ici avec
   son propre repli, `cascade` retirée — jamais une charge inventée, la même
   `exemple` du contrat, juste amputée de la clé que ces deux tests ne
   couvrent pas. */
const servirSansCascade = (variante = 'exemple') => {
  const donnees = exempleContrat('calepinage', 'calepinage_resultat', variante)
  delete donnees.cascade
  calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
}

const rendre = () => render(
  <MemoryRouter><DiagrammePertes calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DiagrammePertes (CAL143)', () => {
  it('affiche chaque poste du contrat, avec sa source', async () => {
    servirSansCascade()
    rendre()

    const cascade = await screen.findByTestId('cal143-cascade')
    const table = within(cascade).getByRole('table')
    // Postes exacts du contrat (`production.pertes`).
    expect(within(table).getByText('Horizon et ombrage proche')).toBeInTheDocument()
    expect(within(table).getByText('Échauffement cellule au-dessus du STC')).toBeInTheDocument()
    expect(within(table).getByText('Salissure et poussière')).toBeInTheDocument()
    expect(within(table).getByText('Rendement de conversion onduleur')).toBeInTheDocument()
    // Sources françaises lisibles, jamais le code brut.
    expect(within(table).getAllByText('Mesure').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('Hypothèse').length).toBeGreaterThan(0)
  })

  it('poste non sourcé : nommé, jamais masqué, source affichée « — »', async () => {
    servirSansCascade()
    rendre()

    const cascade = await screen.findByTestId('cal143-cascade')
    const table = within(cascade).getByRole('table')
    // `availability` porte `source: null` dans l'exemple.
    expect(within(table).getByText('Indisponibilité réseau et maintenance')).toBeInTheDocument()
    const ligne = within(table).getByText('Indisponibilité réseau et maintenance').closest('tr')
    expect(within(ligne).getByText('—')).toBeInTheDocument()
  })

  it('non simulé (pertes vides) : dit pourquoi, jamais un graphe vide silencieux', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.getByText('Pertes non calculées')).toBeInTheDocument()
    expect(screen.getByText(
      'Calepinage non simulé : la pose est connue, la production ne l\'est pas.',
    )).toBeInTheDocument()
    expect(screen.queryByTestId('cal143-cascade')).toBeNull()
  })

  it('ACAL125 — jamais simulé sans poste (exemple_vide tel quel) : « Lancer » est actif', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal143-panneau')
    const bouton = screen.getByTestId('calx48-lancer-bouton')
    expect(bouton).not.toBeDisabled()
    expect(bouton).toHaveTextContent('Lancer la simulation')
  })

  it('ACAL125 — résultat frais : « Recalculer » est visible', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.getByTestId('calx48-lancer-bouton')).toHaveTextContent('Recalculer')
  })

  it('ACAL52 — résultat incomplet : bandeau borne haute avec lien réglages', async () => {
    // Le `resultat` du contrat, avec production/simulation du contrat de
    // simulation « borne haute » (même construction que les autres helpers).
    const resultatBorneHaute = () => {
      const borneHaute = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
      return {
        ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
        production: borneHaute.production, simulation: borneHaute.simulation,
      }
    }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: resultatBorneHaute() })
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.getByTestId('acal52-borne-haute')).toBeInTheDocument()
    expect(screen.getByTestId('acal52-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages#calx69-section-simulation')
    expect(screen.getAllByTestId('acal52-reglage').length).toBeGreaterThan(0)
  })

  it('ACAL52 — résultat complet : aucun bandeau', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.queryByTestId('acal52-borne-haute')).toBeNull()
  })

  it('erreur réseau : message français, aucune valeur inventée', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('boom'))
    rendre()

    expect(await screen.findByTestId('cal143-erreur')).toHaveTextContent(
      'Diagramme de pertes indisponible.',
    )
  })
})

/* CALX48 — `resultat['cascade'].etapes` (CALX141) prime sur la liste plate
   quand elle existe ; la liste plate reste le repli, en DISANT laquelle des
   deux est affichée. Le contrat `calepinage_pertes_cascade.json` (CALX141),
   PAS seulement `calepinage_resultat.json`, est importé ici pour la forme
   détaillée (rang, énergie avant/après, étape omise, gain). */
describe('DiagrammePertes — cascade séquentielle (CALX48)', () => {
  const donneesAvecCascadeDetaillee = () => ({
    ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
    cascade: exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple').cascade,
  })

  it('cascade servie : rang, énergie avant/après, étape omise NOMMÉE avec son motif et une perte VIDE', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesAvecCascadeDetaillee() })
    rendre()

    const cascade = await screen.findByTestId('calx48-cascade-detaillee')
    const table = within(cascade).getByRole('table')

    // L'étape omise (spectral, D-CALX 16) reste NOMMÉE, jamais masquée.
    const ligneSpectrale = within(table).getByText('Correction spectrale').closest('tr')
    expect(within(ligneSpectrale).getByText(
      // ACAL1323 : le motif servi ne porte plus le code interne « D-CALX 16 » (texte client).
      'Le spectral figure dans la cascade et reste TOUJOURS omis avec '
      + 'son motif, jamais forfaitisé.',
    )).toBeInTheDocument()
    // « perte_pct vide » (Done CALX48) : jamais un 0 % qui prétendrait que
    // l'étape omise n'a rien coûté. NB : `toHaveTextContent('')` serait
    // TOUJOURS vrai (chaîne vide incluse dans tout texte) — on lit le
    // `textContent` normalisé directement.
    expect(ligneSpectrale.querySelector('td[data-label="Perte"]').textContent.trim()).toBe('')

    // Une étape calculée porte sa vraie énergie avant/après et sa perte.
    // `getByText` (pas `toHaveTextContent`) : son normaliseur ramène l'espace
    // fine insécable (U+202F) des milliers de `formatNumber` à une espace
    // normale AVANT comparaison — `toHaveTextContent` ne normalise que le DOM,
    // jamais la chaîne attendue (piège catalogué dans `LANE_RULES_CALX.md` §2).
    const ligneThermique = within(table).getByText(
      'Échauffement de la cellule au-dessus du STC',
    ).closest('tr')
    expect(within(ligneThermique).getByText('16 800 kWh')).toBeInTheDocument()
    expect(within(ligneThermique).getByText('15 456 kWh')).toBeInTheDocument()

    // Le gain bifacial reste visible (parité PVsyst : un gain se lit dans la
    // même cascade qu'une perte, jamais dans un tableau à part).
    expect(within(table).getByText('Gain bifacial en face arrière')).toBeInTheDocument()

    expect(screen.getByTestId('calx48-mention-source'))
      .toHaveTextContent('Chaîne de pertes calculée, étape par étape.')
  })

  it('ACAL444 : étape omise = ligne grisée « omise » avec son motif, sans barre ; aucune largeur fixe de 640 ; ligne dépliable', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesAvecCascadeDetaillee() })
    rendre()

    const cascade = await screen.findByTestId('calx48-cascade-detaillee')
    const lignes = within(cascade).getByTestId('acal444-lignes')
    expect(lignes.querySelectorAll('[width="640"]').length).toBe(0)
    expect(cascade.querySelector('.recharts-wrapper')).toBeNull()

    const omise = within(lignes).getByTestId('acal444-ligne-spectral')
    expect(omise).toHaveAttribute('data-omise', 'true')
    expect(within(omise).getByText('omise')).toBeInTheDocument()
    expect(omise.textContent).toContain('reste TOUJOURS omis avec son motif')
    expect(omise.textContent).not.toContain('D-CALX')
    expect(within(omise).queryByTestId('acal444-barre-spectral')).toBeNull()

    const thermique = within(lignes).getByTestId('acal444-ligne-thermique')
    expect(within(thermique).getByTestId('acal444-barre-thermique')).toBeInTheDocument()
    expect(within(lignes).queryByTestId('acal444-detail-thermique')).toBeNull()
    fireEvent.click(within(thermique).getByRole('button'))
    const detail = within(lignes).getByTestId('acal444-detail-thermique')
    expect(detail.textContent).toContain('temp_coeff_pmax_pct_c')
    expect(detail.textContent).toContain('Fiche produit du module désigné (essai)')
    expect(within(detail).getByText('16 800 kWh')).toBeInTheDocument()
    expect(within(detail).getByText('15 456 kWh')).toBeInTheDocument()
  })

  const avecMppt = (entree) => {
    const d = donneesAvecCascadeDetaillee()
    d.cascade = { ...d.cascade, etapes: [
      ...d.cascade.etapes,
      { ...d.cascade.etapes[2], etape: 'mppt', libelle: 'Fenêtre MPPT', rang: 99, entree },
    ] }
    return d
  }

  it('ACAL735 : la ligne Fenêtre MPPT dépliée dit les heures et l’énergie sous le démarrage ; sans clés, aucune ligne', async () => {
    const mppt = exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple_entrees_onduleur').mppt
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: avecMppt(mppt) })
    rendre()
    const lignes = within(await screen.findByTestId('calx48-cascade-detaillee')).getByTestId('acal444-lignes')
    fireEvent.click(within(within(lignes).getByTestId('acal444-ligne-mppt')).getByRole('button'))
    const ligne = within(lignes).getByTestId('acal735-sous-demarrage')
    expect(ligne.textContent).toContain('2 heures')
    expect(ligne.textContent).toContain('2,0 kWh')
    expect(ligne.textContent).toContain("Information : cette énergie n'est pas retirée en plus")
    cleanup()
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: avecMppt({ modele: 'x' }) })
    rendre()
    const lignes2 = within(await screen.findByTestId('calx48-cascade-detaillee')).getByTestId('acal444-lignes')
    fireEvent.click(within(within(lignes2).getByTestId('acal444-ligne-mppt')).getByRole('button'))
    expect(within(lignes2).getByTestId('acal444-detail-mppt')).toBeInTheDocument()
    expect(within(lignes2).queryByTestId('acal735-sous-demarrage')).toBeNull()
  })

  it('ACAL1948 : la ligne « Reflet sur la vitre » dépliée dit l’entrée servie en objet, en phrase', async () => {
    const d = donneesAvecCascadeDetaillee()
    d.cascade = { ...d.cascade, etapes: [
      ...d.cascade.etapes,
      { ...d.cascade.etapes[2], etape: 'iam', libelle: 'IAM', rang: 98,
        entree: { modele: 'fresnel', indice_verre: 1.526, revetement_ar: true, table_iam: [{ angle_deg: 0, facteur: 1 }] } },
    ] }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: d })
    rendre()
    const lignes = within(await screen.findByTestId('calx48-cascade-detaillee')).getByTestId('acal444-lignes')
    fireEvent.click(within(within(lignes).getByTestId('acal444-ligne-iam')).getByRole('button'))
    const detail = within(lignes).getByTestId('acal444-detail-iam')
    expect(within(detail).getByText('Entrée')).toBeInTheDocument()
    expect(detail.textContent).toContain('Modèle de reflet Fresnel ; indice du verre 1,526 ; revêtement antireflet : oui')
    expect(detail.textContent).not.toContain('[object Object]')
  })

  it('revue lot 6 (ACAL1654) : la ligne dépliée nomme la source par la table de l’écran — « Page publiée », jamais « texte »', async () => {
    const d = donneesAvecCascadeDetaillee()
    d.cascade = { ...d.cascade, etapes: d.cascade.etapes.map((e) => (e.etape === 'thermique' ? { ...e, source: 'texte' } : e)) }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: d })
    rendre()
    const lignes = within(await screen.findByTestId('calx48-cascade-detaillee')).getByTestId('acal444-lignes')
    fireEvent.click(within(within(lignes).getByTestId('acal444-ligne-thermique')).getByRole('button'))
    const detail = within(lignes).getByTestId('acal444-detail-thermique')
    const source = within(detail).getByText('Source').nextElementSibling
    expect(source).toHaveTextContent('Page publiée')
    expect(source.textContent).not.toBe('texte')
  })

  /* ACAL1671 / ACAL1968 — la mention SERVIE d'une entrée (pose retenue du thermique, valeur supposée d'une perte)
     s'affiche telle quelle sous la ligne dépliée ; une entrée non supposée et sans mention n'ajoute rien. */
  const avecEntrees = (entrees) => {
    const d = donneesAvecCascadeDetaillee()
    d.cascade = { ...d.cascade, etapes: d.cascade.etapes.map((e) => (
      entrees[e.etape] ? { ...e, entree: { ...(typeof e.entree === 'object' ? e.entree : {}), ...entrees[e.etape] } } : e)) }
    return d
  }
  const deplier = async (poste) => {
    const lignes = within(await screen.findByTestId('calx48-cascade-detaillee')).getByTestId('acal444-lignes')
    fireEvent.click(within(within(lignes).getByTestId(`acal444-ligne-${poste}`)).getByRole('button'))
    return within(lignes).getByTestId(`acal444-detail-${poste}`)
  }

  it('ACAL1671 : la ligne « Échauffement » dépliée dit la pose retenue, phrase servie telle quelle', async () => {
    const mention = 'par défaut — à confirmer : pose « chassis » lue sur le document, ligne « pose_libre » de la table société (D-ACAL-84).'
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: avecEntrees({ thermique: { mention } }) })
    rendre()
    const detail = await deplier('thermique')
    expect(within(detail).getByTestId('acal1671-mention-thermique')).toHaveTextContent(mention)
  })

  it('ACAL1968 : une étape dont l’entrée est SUPPOSÉE affiche sa mention ; non supposée ou sans mention : rien', async () => {
    const mention = 'supposé — fiche sans tolérance de puissance, écart compté à 0 %.'
    const etape = donneesAvecCascadeDetaillee().cascade.etapes.find((e) => e.etape !== 'thermique' && !e.motif_omission)
    calepinageApi.calepinages.resultat.mockResolvedValue({
      data: avecEntrees({ [etape.etape]: { supposee: true, mention } }) })
    rendre()
    expect(within(await deplier(etape.etape)).getByTestId('acal1968-mention-supposee')).toHaveTextContent(mention)
    cleanup()
    calepinageApi.calepinages.resultat.mockResolvedValue({
      data: avecEntrees({ [etape.etape]: { supposee: false, mention } }) })
    rendre()
    expect(within(await deplier(etape.etape)).queryByTestId('acal1968-mention-supposee')).toBeNull()
  })

  it('ACAL735 : `entree` en objet : aucun plantage, « Entrée » non rendue', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: avecMppt({ modele: 'x' }) })
    rendre()
    const lignes = within(await screen.findByTestId('calx48-cascade-detaillee')).getByTestId('acal444-lignes')
    fireEvent.click(within(within(lignes).getByTestId('acal444-ligne-mppt')).getByRole('button'))
    expect(within(lignes).getByTestId('acal444-detail-mppt').textContent).not.toContain('Entrée')
  })

  it("ACAL750 : en mode expert, l'encadré liste les limites puis les étapes omises ; sans limites, les omises seules", async () => {
    localStorage.setItem('calepinage.mode_expert.anonyme', '1')
    try {
      const d = donneesAvecCascadeDetaillee()
      const limites = d.cascade.limites_connues
      expect(limites.length).toBeGreaterThan(0)
      calepinageApi.calepinages.resultat.mockResolvedValue({ data: d })
      rendre()
      const boite = await screen.findByTestId('acal750-limites')
      expect(boite).not.toHaveAttribute('open')
      for (const l of limites) expect(within(boite).getByText(l.texte_fr)).toBeInTheDocument()
      expect(within(boite).getByTestId('acal750-omises')).toHaveTextContent('Correction spectrale')
      cleanup()
      const sans = donneesAvecCascadeDetaillee()
      delete sans.cascade.limites_connues
      calepinageApi.calepinages.resultat.mockResolvedValue({ data: sans })
      rendre()
      const seule = await screen.findByTestId('acal750-limites')
      expect(within(seule).queryByTestId('acal750-liste')).toBeNull()
      expect(within(seule).getByTestId('acal750-omises')).toBeInTheDocument()
    } finally { localStorage.removeItem('calepinage.mode_expert.anonyme') }
  })

  it('ACAL750 : hors mode expert, aucun encadré', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesAvecCascadeDetaillee() })
    rendre()
    await screen.findByTestId('calx48-cascade-detaillee')
    expect(screen.queryByTestId('acal750-limites')).toBeNull()
  })

  it('cascade absente : la liste plate (D-CALX 11) est affichée, avec la mention « postes saisis, non calculés »', async () => {
    servirSansCascade()
    rendre()

    await screen.findByTestId('cal143-cascade')
    expect(screen.queryByTestId('calx48-cascade-detaillee')).toBeNull()
    expect(screen.getByTestId('calx48-mention-source')).toHaveTextContent(
      'Postes saisis, non calculés',
    )
  })

  it('simulation périmée (CALX70) : le bandeau de péremption remplace un chiffre trompeur', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.getByTestId('calx48-perime')).toHaveTextContent(
      'simulation périmée : le document ou un réglage de la société a changé depuis le calcul du 19/09/2026',
    )
  })
})

/* ACAL140 — les barres viennent des énergies SERVIES (kwh_avant / kwh_apres),
   jamais d'une soustraction de pourcentages relatifs. */
describe('DiagrammePertes — barres depuis les énergies servies (ACAL140)', () => {
  const deuxEtapes = [
    { rang: 1, etape: 'a', libelle: 'Étape A', kwh_avant: 100, kwh_apres: 90, perte_pct: 10, gain: false, source: 'fiche', motif_omission: '' },
    { rang: 2, etape: 'b', libelle: 'Étape B', kwh_avant: 90, kwh_apres: 81, perte_pct: 10, gain: false, source: 'fiche', motif_omission: '' },
  ]

  it('énergie livrée = 100 − total_pct servi', async () => {
    const resultatDeuxEtapes = () => ({
      ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
      cascade: { ...exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple').cascade,
        etapes: deuxEtapes, total_pct: 19 },
    })
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: resultatDeuxEtapes() })
    rendre()

    const cascade = await screen.findByTestId('calx48-cascade-detaillee')
    const table = within(cascade).getByRole('table')
    const ligne = within(table).getByText('Énergie livrée').closest('tr')
    expect(ligne.querySelector('td[data-label="Énergie restante"]').textContent).toMatch(/^81,0/)
    // ACAL1658 — la ligne d'arrivée dit l'énergie livrée (servie) et sa part, non « pertes totales ».
    expect(ligne.querySelector('td[data-label="Perte"]').textContent).toMatch(/^81 kWh · 81,0/)
    expect(ligne.textContent).not.toMatch(/pertes totales/)
    // La même ligne dans la liste de lignes (CascadePertesLignes), jumeau traité ensemble.
    const arrivee = within(cascade).getByTestId('acal444-ligne-arrivee')
    expect(arrivee.textContent).toMatch(/Énergie livrée.*81 kWh · 81,0/)
    expect(arrivee.textContent).not.toMatch(/pertes totales/)
    // La dernière colonne n'est plus libellée « Perte (cumulé) » à tort.
    expect(within(table).queryByText(/\(cumulé\)/)).toBeNull()
    // Les barres : 100 → 90 → 81, pas 100 → 90 → 80.
    const lignes = construireCascadeDetaillee(deuxEtapes, 19)
    expect(lignes[2].niveau).toBeCloseTo(81, 6)
    expect(lignes[3].valeur).toBeCloseTo(81, 6)
  })

  it('revue lot 6 — la source servie en CODE se nomme par la table de l’écran (« texte » → « Page publiée »)', async () => {
    const etapes = [
      { ...deuxEtapes[0], source: 'texte' },
      { ...deuxEtapes[1], source: 'societe' },
    ]
    const resultatAvecSources = () => ({
      ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
      cascade: { ...exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple').cascade,
        etapes, total_pct: 19 },
    })
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: resultatAvecSources() })
    rendre()
    const table = within(await screen.findByTestId('calx48-cascade-detaillee')).getByRole('table')
    expect(within(table).getByText('Page publiée')).toBeInTheDocument()
    expect(within(table).getByText('Réglage société')).toBeInTheDocument()
    expect(within(table).queryByText('texte')).toBeNull()
  })

  it("R3-19 — une étape omise montre le texte lisible du serveur, jamais le chemin du motif", () => {
    const etapes = [
      { rang: 1, etape: 'a', libelle: 'Étape A', kwh_avant: 100, kwh_apres: 90, perte_pct: 10, gain: false, source: 'fiche', motif_omission: '' },
      {
        rang: 2, etape: 'b', libelle: 'Étape B', kwh_avant: 90, kwh_apres: null, perte_pct: null, gain: false, source: null,
        motif_omission: 'Omis. Champ manquant : « ombrage.shading12x24 ».',
        motif_lisible: "Omis. Champ manquant : « matrice d'ombrage 12 mois × 24 heures ».",
      },
      { rang: 3, etape: 'c', libelle: 'Étape C', kwh_avant: 90, kwh_apres: null, perte_pct: null, gain: false, source: null, motif_omission: 'Motif ancien servi sans texte lisible.' },
    ]
    const lignes = construireCascadeDetaillee(etapes, 10)
    expect(lignes[2].motif).toBe("Omis. Champ manquant : « matrice d'ombrage 12 mois × 24 heures ».")
    // Un serveur qui ne sert pas encore la clé : le motif servi, tel quel.
    expect(lignes[3].motif).toBe('Motif ancien servi sans texte lisible.')
  })

  it('gain bifacial au-dessus du niveau courant', () => {
    const etapes = [
      { rang: 1, etape: 'a', libelle: 'Perte', kwh_avant: 100, kwh_apres: 90, perte_pct: 10, gain: false, source: 'fiche', motif_omission: '' },
      { rang: 2, etape: 'bif', libelle: 'Gain bifacial', kwh_avant: 90, kwh_apres: 93, perte_pct: -3.33, gain: true, source: 'fiche', motif_omission: '' },
    ]
    const lignes = construireCascadeDetaillee(etapes, null)
    const gain = lignes[2]
    expect(gain.gain).toBe(true)
    // La barre démarre à 90 (niveau avant) et monte à 93 : au-dessus.
    expect(gain.base).toBeCloseTo(90, 6)
    expect(gain.base + gain.valeur).toBeCloseTo(93, 6)
    // Sans total_pct servi : dernier niveau en énergie.
    expect(lignes[3].valeur).toBeCloseTo(93, 6)
  })

  it('étape omise : hauteur nulle, niveau inchangé', () => {
    const etapes = [
      { rang: 1, etape: 'a', libelle: 'A', kwh_avant: 200, kwh_apres: 180, perte_pct: 10, gain: false, source: 'fiche', motif_omission: '' },
      { rang: 2, etape: 'o', libelle: 'Omise', kwh_avant: 180, kwh_apres: null, perte_pct: null, gain: false, source: null, motif_omission: 'pas de données' },
    ]
    const lignes = construireCascadeDetaillee(etapes, null)
    expect(lignes[2].valeur).toBe(0)
    expect(lignes[2].niveau).toBeCloseTo(90, 6)
  })
})

/* ACAL703 — la pastille « inhabituel » sur les lignes de l'onglet Pertes. */
describe('DiagrammePertes — pastille inhabituel (ACAL703)', () => {
  const CLE_EXPERT = 'calepinage.mode_expert.anonyme'
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  const servirAvecPlages = (plages) => {
    const donnees = exempleContrat('calepinage', 'calepinage_resultat', 'exemple')
    donnees.cascade.plages = plages
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    return donnees.cascade.etapes
  }
  const BANDE = { min: 1, max: 3, unite: '%', url: 'https://exemple.test/source', date_lecture: '2026-11-01' }

  it('expert : pastille texte + infobulle + lien source sur l’étape hors bande ; rien sans entrée', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const etapes = servirAvecPlages({
      etapes: { [exempleContrat('calepinage', 'calepinage_resultat', 'exemple').cascade.etapes[0].etape]: { statut: 'inhabituel', ...BANDE } },
      total: null, motif_absence: '',
    })
    rendre()
    await screen.findByTestId('calx48-cascade-detaillee')
    const id = etapes[0].etape
    const pastille = screen.getByTestId(`acal703-pastille-${id}`)
    expect(pastille).toHaveTextContent('inhabituel')
    expect(within(pastille).getByText('inhabituel')).toHaveAttribute('title', 'Hors de la plage publiée (1,0–3,0 %)')
    expect(within(pastille).getByText('Voir la page source')).toHaveAttribute('href', 'https://exemple.test/source')
    expect(screen.getAllByTestId(/^acal703-pastille-/)).toHaveLength(1)
  })

  it('guidé ou sans bande servie : aucune pastille', async () => {
    servirAvecPlages({ etapes: {}, total: null, motif_absence: 'aucune bande sourcée' })
    rendre()
    await screen.findByTestId('calx48-cascade-detaillee')
    expect(screen.queryAllByTestId(/^acal703-pastille-/)).toHaveLength(0)
  })

  it('« dans_la_plage » ne porte aucune pastille ; la ligne reporte la bande servie', () => {
    const etapes = [{ rang: 1, etape: 'a', libelle: 'A', kwh_avant: 200, kwh_apres: 190, perte_pct: 5, gain: false, source: 'fiche', motif_omission: '' }]
    const plage = { statut: 'dans_la_plage', ...BANDE }
    expect(construireCascadeDetaillee(etapes, null, { etapes: { a: plage } })[1].plage).toEqual(plage)
    expect(construireCascadeDetaillee(etapes, null, null)[1].plage).toBeNull()
  })
})

/* ACAL1652 — la fenêtre MPPT se lit « Plage de tension de l'onduleur » (ce que le calcul fait : couper ce qui sort de la plage
   de tension), jamais « Réglage de la puissance » ; le terme servi reste en infobulle. */
describe('nomsPertes — la fenêtre MPPT en clair (ACAL1652)', () => {
  it('l’étape « mppt » se lit « Plage de tension de l’onduleur », le terme servi reste en infobulle', () => {
    expect(nomDePerte('mppt', 'Fenêtre MPPT')).toEqual({ nom: 'Plage de tension de l’onduleur', technique: 'Fenêtre MPPT' })
    expect(JSON.stringify(NOMS_PERTES)).not.toContain('Réglage de la puissance')
  })
})
