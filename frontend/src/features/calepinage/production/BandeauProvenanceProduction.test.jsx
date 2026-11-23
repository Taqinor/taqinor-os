/* CALX65 — le bandeau de provenance des deux productions dans l'atelier.

   Ce qui est prouvé ici (Done, PLAN2.md) : sans simulation, UNE SEULE
   mention (celle de l'estimation rapide, avec le mot « forfaitaires ») ;
   avec simulation, les DEUX valeurs et leurs DEUX provenances sont visibles
   côte à côte — les chiffres viennent tels quels du contrat
   `apps/calepinage/contract_samples/calepinage_resultat.json` (PACT10/13 —
   `reponseContrat`, jamais une charge utile écrite à la main). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { formatNumber } from '../../../lib/format'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { resultat: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import { PVGIS_LIVE_LOSS_PCT } from '@rooflib/systemLoss'
import BandeauProvenanceProduction, {
  BandeauBorneHaute, EcartPvgis, IncertitudeSigma, ReglagesUtilises, SourceMeteo, Suppose,
} from './BandeauProvenanceProduction'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

const rendre = () => render(
  <MemoryRouter><BandeauProvenanceProduction calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BandeauProvenanceProduction (CALX65)', () => {
  it('sans simulation : une seule mention, sans PVGIS tant que la carte ne dit pas qu’il a répondu', async () => {
    servir('exemple_vide')
    rendre()

    const bandeau = await screen.findByTestId('calx65-bandeau')
    expect(within(bandeau).getByTestId('calx65-rapide')).toHaveTextContent(
      "Estimation rapide de l'atelier — avant la simulation",
    )
    // UNE SEULE mention (Done) : la moitié « Simulation » n'existe pas.
    expect(within(bandeau).queryByTestId('calx65-simulation')).toBeNull()
  })

  /* ACAL894 — la provenance de la carte (`data-source-prod` de #rp9-reco-why). */
  const carte = (source) => {
    const el = document.createElement('p')
    el.id = 'rp9-reco-why'
    el.dataset.sourceProd = source
    document.body.appendChild(el)
    return el
  }
  afterEach(() => { document.getElementById('rp9-reco-why')?.remove() })

  it('table par latitude ⇒ ni PVGIS ni 20 %', async () => {
    carte('(production estimée — table par latitude)')
    servir('exemple_vide')
    rendre()
    const rapide = await screen.findByTestId('calx65-rapide')
    expect(rapide).not.toHaveTextContent('PVGIS')
    expect(rapide).not.toHaveTextContent('20 %')
  })

  it('PVGIS répondu ⇒ PVGIS et la perte réellement passée au service', async () => {
    carte('(production affinée via PVGIS au GPS exact)')
    servir('exemple_vide')
    rendre()
    expect(await screen.findByTestId('calx65-rapide')).toHaveTextContent(
      `Estimation rapide (PVGIS PVcalc, pertes forfaitaires ${PVGIS_LIVE_LOSS_PCT} %)`,
    )
  })

  it('simulation périmée (CALX70, `production` publiée null) : une seule mention aussi', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('calx65-bandeau')
    expect(screen.queryByTestId('calx65-simulation')).toBeNull()
  })

  it('avec simulation : les deux valeurs et leurs deux provenances, côte à côte', async () => {
    servir('exemple')
    rendre()

    const bandeau = await screen.findByTestId('calx65-bandeau')
    // Les DEUX mentions sont visibles ENSEMBLE (le même bandeau), jamais l'une
    // à la place de l'autre.
    expect(within(bandeau).getByTestId('calx65-rapide')).toHaveTextContent('Estimation rapide')
    const simulation = within(bandeau).getByTestId('calx65-simulation')
    expect(simulation).toHaveTextContent('P50')
    // `formatNumber` insère une espace fine insécable dans « 13 000 » :
    // `getByText` normalise cette espace en comparant, `toHaveTextContent`
    // sur la chaîne attendue ne le ferait pas (piège banqué en lane).
    expect(within(simulation).getByText(/13.000 kWh\/an/)).toBeInTheDocument()
    expect(simulation).toHaveTextContent('chaîne de pertes du')
    // `calcule_le` de l'exemple : 2026-09-19T11:30:00Z → 19/09/2026 (formatDate).
    expect(simulation).toHaveTextContent('19/09/2026')

    const lien = within(simulation).getByTestId('calx65-lien-production')
    expect(lien).toHaveAttribute('href', '/calepinage/1?onglet=production')
    // R2-06 — un total complet ne porte aucune mention de borne haute.
    expect(within(simulation).queryByTestId('calx65-borne-haute')).toBeNull()
  })

  it('R2-06 : un P50 incomplet porte « borne haute » dans la ligne Simulation', async () => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    const incomplet = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute').production.total
    reponse.data.production.total = { ...reponse.data.production.total, ...incomplet }
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    rendre()

    const simulation = await screen.findByTestId('calx65-simulation')
    expect(within(simulation).getByTestId('calx65-borne-haute')).toHaveTextContent(/borne haute/i)
  })
})

/* ACAL52 — le bandeau commun de borne haute et les réglages utilisés. */
describe('BandeauBorneHaute / ReglagesUtilises (ACAL52)', () => {
  const borneHaute = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')

  it('lien vers les réglages', () => {
    render(<MemoryRouter><BandeauBorneHaute total={borneHaute.production.total} /></MemoryRouter>)

    expect(screen.getByTestId('acal52-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages#calx69-section-simulation')
    expect(screen.getByTestId('acal52-mention')).toHaveTextContent('3 pertes non renseignées')
  })

  it('complet ou jamais simulé : aucun bandeau', () => {
    const complet = exempleContrat('calepinage', 'calepinage_resultat', 'exemple').production.total
    const vide = exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide').production.total
    expect(estIncomplet(complet)).toBe(false)
    expect(estIncomplet(vide)).toBe(false)
    expect(estIncomplet(borneHaute.production.total)).toBe(true)
    render(<MemoryRouter><BandeauBorneHaute total={complet} /></MemoryRouter>)
    expect(screen.queryByTestId('acal52-borne-haute')).toBeNull()
  })

  it('réglages utilisés listés', () => {
    render(<ReglagesUtilises simulation={borneHaute.simulation} />)

    const lignes = screen.getAllByTestId('acal52-reglage')
    expect(lignes).toHaveLength(Object.keys(borneHaute.simulation.reglages_utilises).length)
    expect(lignes[1]).toHaveTextContent('tolerance_validation_pct')
    expect(lignes[1]).toHaveTextContent('3')
    expect(lignes[1]).toHaveTextContent('societe')
  })
})

/* ENF15 — les moitiés CLIENTES des contrats `calepinage_meteo.json` (CALX143)
   et `calepinage_incertitude.json` (CALX144) : chaque valeur affichée est celle
   de l'exemple committé, jamais une charge écrite à la main. */
describe('SourceMeteo — deuxième source météo (ACAL745)', () => {
  const meteoDe = (variante) => exempleContrat('calepinage', 'calepinage_meteo', variante).meteo

  it("la ligne dit l'écart annuel servi, le détail mensuel est replié (12 mois), sans verdict", () => {
    const meteo = meteoDe('exemple')
    render(<SourceMeteo meteo={meteo} />)
    const c = meteo.comparaison_base
    const ligne = screen.getByTestId('acal745-ecart')
    expect(ligne.textContent).toContain(`Deuxième source météo (${c.base_comparee})`)
    expect(ligne.textContent).toContain(`par rapport à ${c.base_principale}`)
    expect(ligne.textContent.replace(/\s/g, ' ')).toContain('9,7 %')
    expect(screen.getByTestId('acal745-mensuel')).not.toHaveAttribute('open')
    expect(screen.getAllByTestId(/^acal745-mois-/)).toHaveLength(12)
    expect(ligne.textContent).not.toMatch(/bon|mauvais/i)
  })

  it('ecart_pct null : « non comparée » et le motif servi', () => {
    // Cette variante ne porte que `comparaison_base` : posée sur la source complète.
    const meteo = { ...meteoDe('exemple'), ...meteoDe('exemple_comparaison_sans_ecart') }
    render(<SourceMeteo meteo={meteo} />)
    expect(screen.getByTestId('acal745-ecart')).toHaveTextContent('Deuxième source météo non comparée :')
    expect(screen.getByTestId('acal745-ecart')).toHaveTextContent(meteo.comparaison_base.motif)
    expect(screen.queryByTestId('acal745-mensuel')).toBeNull()
  })

  it('comparaison_base absent : rien', () => {
    const meteo = { ...meteoDe('exemple') }
    delete meteo.comparaison_base
    render(<SourceMeteo meteo={meteo} />)
    expect(screen.queryByTestId('acal745-ecart')).toBeNull()
  })
})

describe('SourceMeteo / IncertitudeSigma (ENF15)', () => {
  it('la source météo affiche les clés servies, « non publié » pour un null', () => {
    const { meteo } = exempleContrat('calepinage', 'calepinage_meteo')
    render(<SourceMeteo meteo={meteo} />)
    const bloc = screen.getByTestId('enf15-source-meteo')
    expect(bloc).toHaveTextContent(meteo.service)
    expect(bloc).toHaveTextContent(meteo.base_rayonnement)
    expect(bloc).toHaveTextContent(meteo.base_meteo)
    expect(bloc).toHaveTextContent(meteo.fenetre_annees)
    expect(bloc).toHaveTextContent(meteo.heure.fuseau_site)
    expect(bloc).toHaveTextContent(`${meteo.horizon.origine} (${meteo.horizon.base_horizon})`)
  })

  it('sans simulation (exemple_vide) : aucun bloc météo', () => {
    const { meteo } = exempleContrat('calepinage', 'calepinage_meteo', 'exemple_vide')
    render(<SourceMeteo meteo={meteo} />)
    expect(screen.queryByTestId('enf15-source-meteo')).toBeNull()
  })

  it('σ composé : une ligne par composante sourcée, méthode et portée nommées', () => {
    const { incertitude } = exempleContrat('calepinage', 'calepinage_incertitude')
    render(<IncertitudeSigma incertitude={incertitude} />)
    const lignes = screen.getAllByTestId('enf15-composante')
    expect(lignes).toHaveLength(incertitude.composantes.length)
    incertitude.composantes.forEach((c, i) => {
      expect(lignes[i]).toHaveTextContent(c.nom)
      expect(lignes[i]).toHaveTextContent(c.source)
    })
    const bloc = screen.getByTestId('enf15-incertitude')
    expect(bloc).toHaveTextContent(incertitude.methode)
    expect(bloc).toHaveTextContent(`portée ${incertitude.portee}`)
    expect(screen.queryByTestId('enf15-incertitude-refus')).toBeNull()
  })

  it('σ refusé : le motif du serveur mot pour mot, aucun σ inventé', () => {
    const { incertitude } = exempleContrat('calepinage', 'calepinage_incertitude', 'exemple_sigma_refuse')
    render(<IncertitudeSigma incertitude={incertitude} />)
    expect(screen.getByTestId('enf15-incertitude-refus')).toHaveTextContent(incertitude.motif_refus)
    expect(screen.getByTestId('enf15-incertitude')).toHaveTextContent('non composée')
    expect(screen.queryByTestId('enf15-composante')).toBeNull()
  })
})

/* ACAL405 — une référence du profil de départ ⇒ « valeur publiée, non mesurée ». */
describe('ReglagesUtilises — valeur publiée (ACAL405)', () => {
  const simulation = (reference) => ({
    reglages_utilises: { b0_iam: { valeur: 0.05, source: 'texte', reference } },
  })

  it('une référence du profil de départ ajoute la mention', () => {
    render(<ReglagesUtilises simulation={simulation('Profil de départ — PVsyst : bo = 0.05')} />)
    expect(screen.getByTestId('acal405-publiee')).toHaveTextContent('valeur publiée, non mesurée')
  })

  it('une saisie ordinaire n’en porte pas', () => {
    render(<ReglagesUtilises simulation={simulation('mesuré sur site')} />)
    expect(screen.queryByTestId('acal405-publiee')).toBeNull()
  })
})

/* ACAL854 — l'écart à PVGIS servi (`validation`), signé, une décimale. */
describe('EcartPvgis (ACAL854)', () => {
  const validation = exempleContrat('calepinage', 'calepinage_resultat', 'exemple').validation
  const rendreEcart = (v) => render(<MemoryRouter><EcartPvgis validation={v} /></MemoryRouter>)

  it('écart servi ⇒ la ligne, signe compris', () => {
    rendreEcart(validation)
    expect(screen.getByTestId('acal854-ecart-pvgis').textContent.replace(/\s/g, ' '))
      .toContain('Comparé à PVGIS au même endroit : −2,0 %')
    expect(screen.queryByTestId('acal854-sans-verdict')).toBeNull()
    expect(screen.getByTestId('acal854-ecart-pvgis')).not.toHaveTextContent('PVcalc')
  })

  it('sans tolérance ⇒ « écart publié sans verdict » et le lien vers le réglage', () => {
    rendreEcart({ ...validation, tolerance_pct: null, verdict: null })
    expect(screen.getByTestId('acal854-sans-verdict')).toHaveTextContent('écart publié sans verdict')
    expect(screen.getByTestId('acal854-lien-tolerance'))
      .toHaveAttribute('href', '/calepinage/reglages#calx69-tolerance_validation_pct')
  })

  it('écart nul (aucune simulation) ⇒ rien', () => {
    rendreEcart(exempleContrat('calepinage', 'calepinage_resultat', 'exemple_perime').validation)
    expect(screen.queryByTestId('acal854-ecart-pvgis')).toBeNull()
    rendreEcart({ ...validation, ecart_pct: null })
    expect(screen.queryByTestId('acal854-ecart-pvgis')).toBeNull()
  })
})

/* ACAL855 — le voyant suit le verdict SERVI, tolérance nommée. */
describe('EcartPvgis — voyant (ACAL855)', () => {
  const validation = exempleContrat('calepinage', 'calepinage_resultat', 'exemple').validation
  const voyant = (v) => {
    render(<MemoryRouter><EcartPvgis validation={v} /></MemoryRouter>)
    return screen.queryByTestId('acal855-voyant')
  }

  it('dans la tolérance ⇒ vert, tolérance servie', () => {
    const v = voyant(validation)
    expect(v).toHaveAttribute('data-verdict', 'vert')
    expect(v.textContent.replace(/\s/g, ' ')).toContain('Dans la tolérance de ±5 % réglée par votre société')
    expect(screen.queryByTestId('acal855-lien-pertes')).toBeNull()
  })

  it('hors tolérance ⇒ orange, lien vers les Pertes, avertissement servi une fois', () => {
    const v = voyant({ ...validation, verdict: 'hors_tolerance', avertissement: 'écart hors tolérance servi' })
    expect(v).toHaveAttribute('data-verdict', 'orange')
    expect(v.textContent.replace(/\s/g, ' ')).toContain('Hors de la tolérance de ±5 %')
    expect(screen.getByTestId('acal855-lien-pertes')).toHaveAttribute('href', '/?onglet=pertes')
    expect(screen.getAllByText('écart hors tolérance servi')).toHaveLength(1)
  })

  it('sans verdict ⇒ aucun voyant', () => {
    expect(voyant({ ...validation, verdict: null, tolerance_pct: null })).toBeNull()
  })
})

/* ACAL698 — la prop facultative `ouvert` pilote le <details>. */
describe('Suppose — « Ce qui est supposé » (ACAL980)', () => {
  const contrat = exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide').suppose

  it('liste chaque repli avec son libellé servi et le champ à renseigner', () => {
    render(<Suppose suppose={contrat} />)
    const bloc = screen.getByTestId('acal980-suppose')
    expect(bloc).toHaveTextContent('Ce qui est supposé')
    expect(within(bloc).getByTestId('acal980-longueur_chaine_dossier')).toHaveTextContent(
      "16 modules par chaîne (longueur retenue au dossier : fiche du module ou de l'onduleur incomplète)",
    )
    expect(within(bloc).getByTestId('acal980-allee_par_defaut')).toHaveTextContent(
      "À renseigner : panneau Allées de l'atelier (largeur de l'allée technique)",
    )
  })

  it('liste vide ou absente : rien', () => {
    const { container, rerender } = render(<Suppose suppose={[]} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<Suppose />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('ReglagesUtilises — prop ouvert (ACAL698)', () => {
  const simulation = { reglages_utilises: { b0_iam: { valeur: 0.05, source: 'texte', reference: 'x' } } }

  it('sans la prop : comportement d’origine, replié', () => {
    render(<ReglagesUtilises simulation={simulation} />)
    expect(screen.getByTestId('acal52-reglages-utilises')).not.toHaveAttribute('open')
  })

  it('ouvert=true déplie, ouvert=false replie', () => {
    const { rerender } = render(<ReglagesUtilises simulation={simulation} ouvert />)
    expect(screen.getByTestId('acal52-reglages-utilises')).toHaveAttribute('open')
    rerender(<ReglagesUtilises simulation={simulation} ouvert={false} />)
    expect(screen.getByTestId('acal52-reglages-utilises')).not.toHaveAttribute('open')
  })
})

/* ACAL995 — ce que le devis annoncera, lu dans `chiffrage` (design-context, ACAL993 ;
   forme `ventes/chiffrage_conception.json`, ACAL991). La simulation vaut la production
   de l'exemple « pose réelle » du même contrat (98 576 kWh) : écart −11,5 %. */
describe('ACAL995 — « Le devis annonce » seulement hors pose réelle', () => {
  const ville = exempleContrat('ventes', 'chiffrage_conception', 'exemple_ville')
  const pose = exempleContrat('ventes', 'chiffrage_conception', 'exemple')
  const simule = () => {
    const r = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    r.data.production.total.p50_kwh = pose.production_annuelle_kwh.valeur
    calepinageApi.calepinages.resultat.mockResolvedValue(r)
  }

  const rendreAvec = (chiffrage) => render(
    <MemoryRouter><BandeauProvenanceProduction calepinageId={1} chiffrage={chiffrage} /></MemoryRouter>,
  )

  it('standard ville ⇒ la ligne et l’écart −11,5 %', async () => {
    simule()
    rendreAvec(ville)
    // Espaces fines de `formatNumber` : comparées après normalisation des deux côtés.
    const espaces = (t) => t.replace(/\s/g, ' ')
    expect(espaces((await screen.findByTestId('acal995-devis-annonce')).textContent)).toBe(espaces(
      `Le devis annonce : ${formatNumber(ville.production_annuelle_kwh.valeur, { decimals: 0 })} kWh/an — `
      + `production standard de la ville (étude technique : −${formatNumber(11.5, { decimals: 1 })} %)`))
  })

  it('calepinage enregistré ⇒ rien', async () => {
    simule()
    rendreAvec(pose)
    await screen.findByTestId('calx65-simulation')
    expect(screen.queryByTestId('acal995-devis-annonce')).toBeNull()
  })

  it('ACAL1274 — pose réelle imprimée ≠ simulation ⇒ la ligne nomme les deux nombres', async () => {
    const r = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    r.data.production.total.p50_kwh = pose.production_annuelle_kwh.valeur * 0.988
    calepinageApi.calepinages.resultat.mockResolvedValue(r)
    rendreAvec(pose)
    const espaces = (t) => t.replace(/\s/g, ' ')
    expect(espaces((await screen.findByTestId('acal995-devis-annonce')).textContent)).toBe(espaces(
      `Le devis annonce : ${formatNumber(pose.production_annuelle_kwh.valeur, { decimals: 0 })} kWh/an — `
      + `pose réelle recalculée par le moteur du devis (étude technique : −${formatNumber(1.2, { decimals: 1 })} %)`))
  })

  it('non servi ⇒ « Le devis n’est pas encore chiffré : <motif servi> »', async () => {
    const vide = exempleContrat('calepinage', 'calepinage_design_context', 'exemple_vide').chiffrage
    simule()
    rendreAvec(vide)
    const motif = vide.omissions.find((o) => o.grandeur === 'production_annuelle_kwh').motif
    expect(await screen.findByTestId('acal995-devis-annonce'))
      .toHaveTextContent(`Le devis n’est pas encore chiffré : ${motif}`)
  })
})
