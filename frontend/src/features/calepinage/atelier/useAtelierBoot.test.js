import { describe, it, expect, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { fallbackPerKwc } from '@rooflib/productionEngine'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import api from '../../../api/axios'
import calepinageApi from '../../../api/calepinageApi'
import {
  productionAtelierDepuisChiffrage, adresseSansDoublon, MESSAGE_ACCES_REFUSE,
  cadrerToitAtelier, ZOOM_MAX_CADRAGE_ATELIER, hauteurCouverteParTiroir,
  useAtelierBoot, imageryDesReglages, // ACAL1421
} from './useAtelierBoot'
import { reglagesAtelierDesParametres } from './contexteAtelier' // ACAL1754
import { resolveImageryProvider } from '@rooflib/roofConfig' // ACAL1754 — le résolveur de la carte, lu tel quel

// ACAL1421 — le boot réel du hook, réseau et constructeur doublés (les charges servies viennent des contrats).
const { initRoofToolPro8 } = vi.hoisted(() => ({ initRoofToolPro8: vi.fn() }))
vi.mock('@roofbuilder', () => ({ initRoofToolPro8 }))
vi.mock('../../../api/axios', () => ({ default: { get: vi.fn() } }))
vi.mock('../../../api/calepinageApi', () => ({ default: { parametres: { get: vi.fn() }, calepinages: {} } }))
vi.mock('../../../api/crmApi', () => ({ default: { getRoofFootprint: vi.fn(() => Promise.resolve({ data: {} })) } }))

/* ACAL994 — la production de l'atelier ERP vient du bloc `chiffrage` servi par design-context
   (ACAL993) quand il est servi ; sinon le repli de table, étiqueté « estimation ». Les valeurs
   viennent de l'exemple COMMITTÉ du contrat, jamais d'une charge utile écrite à la main. */
const CTX = exempleContrat('calepinage', 'calepinage_design_context')
const CHIFFRAGE = CTX.chiffrage
const CFG = { panels: 100 }

describe('productionAtelierDepuisChiffrage (ACAL994)', () => {
  it('chiffrage servi ⇒ kWc × production par kWc = la production servie par le serveur', () => {
    const parKwc = productionAtelierDepuisChiffrage(CHIFFRAGE)(CFG)
    expect(CHIFFRAGE.production_annuelle_kwh.etat).toBe('servi')
    expect(parKwc.annualKwh * CHIFFRAGE.kwc.valeur)
      .toBeCloseTo(CHIFFRAGE.production_annuelle_kwh.valeur, 6)
    expect(parKwc.monthlyKwh).toHaveLength(12)
    expect(parKwc.monthlyKwh.reduce((a, b) => a + b, 0)).toBeCloseTo(parKwc.annualKwh, 6)
    // Valeur NAVIGATEUR tant que rien n'est enregistré : la source reste « estimation ».
    expect(parKwc.source).toBe('estimate')
  })

  it('non servi ⇒ le repli de table, jamais le chiffre du serveur', () => {
    const repli = fallbackPerKwc().annualKwh
    for (const etat of ['non_servi', 'indisponible']) {
      const bloc = { ...CHIFFRAGE, production_annuelle_kwh: { ...CHIFFRAGE.production_annuelle_kwh, etat } }
      expect(productionAtelierDepuisChiffrage(bloc)(CFG).annualKwh).toBe(repli)
    }
  })

  it('aucun chiffrage ou kWc non servi ⇒ le repli de table', () => {
    const repli = fallbackPerKwc().annualKwh
    expect(productionAtelierDepuisChiffrage(undefined)(CFG).annualKwh).toBe(repli)
    expect(productionAtelierDepuisChiffrage(null)(CFG).annualKwh).toBe(repli)
    const sansKwc = { ...CHIFFRAGE, kwc: { ...CHIFFRAGE.kwc, etat: 'non_servi' } }
    expect(productionAtelierDepuisChiffrage(sansKwc)(CFG).annualKwh).toBe(repli)
  })
})

describe('ACAL1421 — `imagery` passé à initRoofToolPro8', () => {
  it('boot d’un lead : le pays réglé par la société part en `imagery` (aucune seconde lecture des réglages)', async () => {
    const LEAD = exempleContrat('crm', 'lead')
    api.get.mockImplementation((url) => Promise.resolve(
      url === '/ventes/roof-config/' ? { data: { available: true, maptilerKey: 'K' } } : { data: LEAD }))
    calepinageApi.parametres.get.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    window.__taqinorRoofBooted = false
    const rien = () => {}
    const ctx = {
      cibleId: '7', leadId: '7', estCalepinage: false, builderApi: { current: null }, reducedMotion: false,
      setBrouillonPropose: rien, setBuilderApiActuel: rien, setBuilderReady: rien, setContexte: rien,
      setCatalogueIndisponible: rien, setContourMessage: rien, setHashBaseBrouillon: rien, setLead: rien,
      setLoadError: rien, setStatus: rien, setSceneHydratee: rien, setRepereErreur: rien,
    }
    try {
      renderHook(() => useAtelierBoot(ctx))
      await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalledTimes(1))
      const pays = exempleContrat('calepinage', 'parametres_calepinage').imagerie.pays
      expect(initRoofToolPro8.mock.calls[0][0].imagery).toEqual({ pays })
      expect(calepinageApi.parametres.get).toHaveBeenCalledTimes(1)
    } finally {
      window.__taqinorRoofBooted = false
    }
  })

  it('société muette (réglages illisibles ou sans pays) : AUCUN contexte, le fond satellite historique ne change pas', () => {
    expect(imageryDesReglages(null)).toBeUndefined()
    expect(imageryDesReglages({ pays: null })).toBeUndefined()
    expect(imageryDesReglages({ pays: '' })).toBeUndefined()
    expect(imageryDesReglages({ pays: 'fr' })).toEqual({ pays: 'fr' })
  })

  // ACAL1754 — le fournisseur CHOISI par la société passe à la carte (avec les fournisseurs admis et la mention
  // légale saisie) : la carte prend le sien, pas le premier disponible. Mutant : ne passer que `pays` ⇒ maptiler.
  it('le fournisseur choisi, les fournisseurs admis et l’attribution passent ; la carte prend le choisi', () => {
    const section = exempleContrat('calepinage', 'site_imagerie').imagerie
    const reglages = reglagesAtelierDesParametres({ imagerie: section })
    expect(imageryDesReglages(reglages)).toEqual({
      pays: section.pays,
      fournisseur_imagerie: section.fournisseur_imagerie,
      fournisseurs_autorises: section.fournisseurs_autorises,
      attribution: section.attribution,
    })
    const choisiMapbox = reglagesAtelierDesParametres({ imagerie: { pays: 'ma', fournisseur_imagerie: 'mapbox', fournisseurs_autorises: [] } })
    const fournisseur = resolveImageryProvider(imageryDesReglages(choisiMapbox), { maptilerKey: 'K', mapboxToken: 'T' })
    expect(fournisseur?.id).toBe('mapbox')
    // Section déclarée sans valeur : aucun contexte (comportement historique).
    const vide = exempleContrat('calepinage', 'site_imagerie', 'exemple_section_declaree_sans_valeur').imagerie
    expect(imageryDesReglages(reglagesAtelierDesParametres({ imagerie: vide }))).toBeUndefined()
  })

  // ACAL1754 (CI) — le builder reçoit la clé `imagerie` SEULEMENT quand un vrai réglage d'imagerie existe ; un pays
  // seul laisse `reglagesAtelier` comme avant (pas de clé), et le contexte vient alors de `pays`.
  it('pays seul : aucune clé `imagerie` ; un réglage d’imagerie présent : la clé porte pays + les clés réglées', () => {
    const paysSeul = reglagesAtelierDesParametres({ imagerie: { pays: 'ma' } })
    expect('imagerie' in paysSeul).toBe(false)
    expect(imageryDesReglages(paysSeul)).toEqual({ pays: 'ma' })
    const present = reglagesAtelierDesParametres({ imagerie: { pays: 'ma', attribution: '© Société' } })
    expect(present.imagerie).toEqual({ pays: 'ma', attribution: '© Société' })
    expect(imageryDesReglages(present)).toEqual({ pays: 'ma', attribution: '© Société' })
  })

  // ACAL1754 (correctif) — une société qui n'a réglé que l'attribution ou les fournisseurs admis n'a PAS de pays :
  // aucun contexte (un contexte sans pays changerait le fond de carte) ; avec le pays, `pays` reste dans le contexte.
  it('attribution ou fournisseurs admis SANS pays : aucun contexte ; avec pays, pays est gardé', () => {
    const seule = reglagesAtelierDesParametres({ imagerie: { attribution: '© Société' } })
    expect(imageryDesReglages(seule)).toBeUndefined()
    const admis = reglagesAtelierDesParametres({ imagerie: { fournisseurs_autorises: ['mapbox'] } })
    expect(imageryDesReglages(admis)).toBeUndefined()
    const avecPays = reglagesAtelierDesParametres({ imagerie: { pays: 'ma', attribution: '© Société' } })
    expect(imageryDesReglages(avecPays)).toEqual({ pays: 'ma', attribution: '© Société' })
  })
})

describe('R2-03 / R2-20', () => {
  it('la ville déjà portée par l’adresse n’est pas répétée', () => {
    expect(adresseSansDoublon('Quartier Founty, Agadir', 'Agadir')).toBe('Quartier Founty, Agadir')
    expect(adresseSansDoublon('Quartier Founty, agadir', 'Agadir ')).toBe('Quartier Founty, agadir')
    expect(adresseSansDoublon('12 rue des Oliviers', 'Casablanca')).toBe('12 rue des Oliviers, Casablanca')
    expect(adresseSansDoublon('', 'Casablanca')).toBe('Casablanca')
    expect(adresseSansDoublon(null, null)).toBe('')
  })

  it('un 403 dit le refus de droit, jamais « introuvable — réessayez »', () => {
    expect(MESSAGE_ACCES_REFUSE).toBe('Vous n’avez pas accès à ce calepinage.')
  })
})

describe('F6 — cadrage du toit par l’atelier ERP', () => {
  it('demande le cadrage avec le plafond relevé de l’atelier (22, le site public garde 19)', () => {
    const cadrerToit = vi.fn(() => true)
    expect(cadrerToitAtelier({ cadrerToit })).toBe(true)
    expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: 0 })
    expect(ZOOM_MAX_CADRAGE_ATELIER).toBe(22)
  })
  it('H1 — tablette : le cadrage vise la partie de la carte AU-DESSUS du tiroir (pixels couverts mesurés)', () => {
    const boite = (top, bottom) => ({ getBoundingClientRect: () => ({ top, bottom }) })
    const racine = (tiroir) => ({
      getElementById: (id) => (id === 'rp9-map' ? boite(64, 820) : null),
      querySelector: () => tiroir,
    })
    expect(hauteurCouverteParTiroir(racine(boite(540, 820)))).toBe(280)
    expect(hauteurCouverteParTiroir(racine(null)), 'bureau : aucun tiroir').toBe(0)
    expect(hauteurCouverteParTiroir(null)).toBe(0)
    const cadrerToit = vi.fn(() => true)
    cadrerToitAtelier({ cadrerToit }, racine(boite(540, 820)))
    expect(cadrerToit).toHaveBeenCalledWith({ zoomMax: ZOOM_MAX_CADRAGE_ATELIER, basPx: 280 })
  })
  it('sans constructeur ou sans `cadrerToit` : rien, jamais une erreur', () => {
    expect(cadrerToitAtelier(null)).toBe(false)
    expect(cadrerToitAtelier({})).toBe(false)
  })
})

/* T4-X9-013 — le bandeau d'un calepinage SANS lead disait « Ville inconnue du moteur : renseigner la ville ou le point
   GPS du lead. » (refus servi du moteur, `design-context` › `cible.refus`) : sans lead, aucune phrase sur une conception. */
describe('T4-X9-013 — libelleCibleEstimee : sans lead, rien', () => {
  it('refus servi : dit avec un lead, tu sans lead', async () => {
    const { libelleCibleEstimee } = await import('./contexteAtelier')
    const cible = { source: 'factures', panneaux: 0, refus: 'Ville inconnue du moteur : renseigner la ville ou le point GPS du lead.' }
    expect(libelleCibleEstimee(cible)).toBe(cible.refus)
    expect(libelleCibleEstimee(cible, { sansLead: true })).toBeNull()
  })
})

/* T4-X2-006 — calepinage SANS lead, enregistré PUIS simulé (simulation automatique, partie après l'enregistrement) : la
   vue Expert ne montrait que l'estimation de l'atelier (« ≈ 21 735 kWh/an (estimation) ») et le Total « production au
   prochain enregistrement », jamais les 27 197 kWh simulés. La lecture est refaite tant que la simulation tourne, et la
   production simulée fraîche part au constructeur dans le bloc `chiffrage` (case « Production » du Total). */
describe('T4-X2-006 — la production simulée fraîche de la pose (useSimulationFraiche, chiffrageAvecSimulation)', () => {
  it('simulation en cours puis faite : le P50 frais est relu, sans geste', async () => {
    const { useSimulationFraiche, INTERVALLE_SIMULATION_MS } = await import('./simulationFraiche')
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      calepinageApi.calepinages.resultat = vi.fn()
        .mockResolvedValueOnce({ data: { simule: false, simulation_automatique: { en_cours: true } } })
        .mockResolvedValue({ data: { simule: true, simulation_perimee: false, production: { total: { p50_kwh: 27197 } } } })
      const { result } = renderHook(() => useSimulationFraiche(1975, 'enregistre-11h03'))
      await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(1))
      expect(result.current).toBeNull()
      await vi.advanceTimersByTimeAsync(INTERVALLE_SIMULATION_MS)
      await waitFor(() => expect(result.current).toBe(27197))
    } finally { vi.useRealTimers() }
  })

  it('simulation périmée : aucun P50 (jamais un chiffre d’un autre document)', async () => {
    const { p50Frais } = await import('./simulationFraiche')
    expect(p50Frais({ simule: true, simulation_perimee: true, production: { total: { p50_kwh: 27197 } } })).toBeNull()
    expect(p50Frais({ simule: true, simulation_perimee: false, production: { total: { p50_kwh: 27197 } } })).toBe(27197)
  })

  /* T4-X8-013 — Résultats montrait « Production simulée de la pose 6 009 kWh » pendant que la feuille « Avancé » disait
     « ≈ 5 390 kWh/an (estimation) » : la lecture du résumé, faite avant la simulation, n'était jamais refaite. Le résultat
     que l'étape Résultats relit est PUBLIÉ : le résumé (et le Total du constructeur) le reprennent, sans seconde lecture. */
  it('T4-X8-013 — le résultat relu par l’étape Résultats met à jour le P50 du résumé ; un autre calepinage, non', async () => {
    const { useSimulationFraiche, publierResultat } = await import('./simulationFraiche')
    calepinageApi.calepinages.resultat = vi.fn().mockResolvedValue({ data: { simule: false } })
    const { result } = renderHook(() => useSimulationFraiche(1978, 'enregistre-15h53'))
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(result.current).toBeNull())
    const frais = { simule: true, simulation_perimee: false, production: { total: { p50_kwh: 6009 } } }
    act(() => publierResultat(9999, frais))
    expect(result.current).toBeNull()
    act(() => publierResultat('1978', frais))
    expect(result.current).toBe(6009)
    act(() => publierResultat(1978, { ...frais, simulation_perimee: true }))
    expect(result.current).toBeNull()
    expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(1)
  })

  it('le bloc `chiffrage` du constructeur porte la simulation fraîche ; sans elle, il reste tel quel', async () => {
    const { chiffrageAvecSimulation } = await import('./simulationFraiche')
    const sansLead = { production_annuelle_kwh: { valeur: null, etat: 'non_servi' } }
    expect(chiffrageAvecSimulation(sansLead, 27197)).toEqual({ ...sansLead, simulation: { p50_kwh: 27197, a_jour: true } })
    expect(chiffrageAvecSimulation(null, 27197)).toEqual({ simulation: { p50_kwh: 27197, a_jour: true } })
    expect(chiffrageAvecSimulation(sansLead, null)).toBe(sansLead)
  })
})

/* ACAL1957 — après « Générer le devis » (201), l'atelier RELIT design-context : le bandeau et la cible lisent les
   panneaux du devis créé, jamais le contexte d'avant la création (« Aucune ligne de panneau dans ce devis »). */
describe('ACAL1957 — après generer-devis, le contexte relu porte la cible du devis', () => {
  it('201 annoncé ⇒ design-context relu, la cible servie (source devis) remplace l’ancienne ; un autre calepinage n’y touche pas', async () => {
    const { annoncerDevisGenere } = await import('./contexteAtelier')
    calepinageApi.calepinages.designContext = vi.fn(() => Promise.resolve({ data: CTX }))
    const setContexte = vi.fn()
    // Sans `cibleId`, le boot ne part pas : seule l'écoute du devis généré est en jeu.
    const { unmount } = renderHook(() => useAtelierBoot({ calepinageId: 2046, estCalepinage: true, setContexte }))
    act(() => annoncerDevisGenere(9999))
    expect(calepinageApi.calepinages.designContext).not.toHaveBeenCalled()
    act(() => annoncerDevisGenere('2046'))
    await waitFor(() => expect(setContexte).toHaveBeenCalledWith(CTX))
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledWith(2046)
    expect(setContexte.mock.calls[0][0].cible).toMatchObject({ source: 'devis', panneaux: CTX.cible.panneaux })
    unmount()
    act(() => annoncerDevisGenere(2046))
    expect(calepinageApi.calepinages.designContext).toHaveBeenCalledTimes(1)
  })
})

/* Revue ACAL1946 — l'issue de « Générer le devis » vit le temps de l'atelier : le quitter (la page se démonte, y compris
   à la déconnexion) puis rouvrir le MÊME calepinage ne montre plus « Devis … créé » ; une réponse arrivée après la
   fermeture ne repose rien. Vrais `useAtelierBoot` et `BoutonDevis`. */
describe('Revue ACAL1946 — quitter l’atelier oublie l’issue du devis', () => {
  const DETAIL_VIDE = exempleContrat('calepinage', 'calepinage_detail', 'exemple_vide')
  async function ouvrir() {
    const { createElement: h } = await import('react')
    const { render } = await import('@testing-library/react')
    const { MemoryRouter } = await import('react-router-dom')
    const { default: BoutonDevis } = await import('../BoutonDevis')
    function Atelier() {
      useAtelierBoot({ calepinageId: DETAIL_VIDE.id, estCalepinage: true, setContexte: () => {} })
      return h(MemoryRouter, null, h(BoutonDevis, { calepinageId: DETAIL_VIDE.id, detail: DETAIL_VIDE }))
    }
    return render(h(Atelier))
  }

  it('créé, quitté, rouvert ⇒ aucune carte ; réponse tardive après fermeture ⇒ jetée', async () => {
    const { screen, cleanup } = await import('@testing-library/react')
    const userEvent = (await import('@testing-library/user-event')).default
    calepinageApi.calepinages.designContext = vi.fn(() => new Promise(() => {}))
    calepinageApi.calepinages.genererDevis = vi.fn(() => Promise.resolve({ data: { devis: 44, reference: 'DEV-2611-0044' } }))
    const premier = await ouvrir()
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    expect(await screen.findByTestId('cal-devis-cree')).toHaveTextContent('Devis DEV-2611-0044 créé')
    premier.unmount() // on quitte l'atelier
    const rouvert = await ouvrir()
    await screen.findByTestId('cal-generer-devis')
    expect(screen.queryByTestId('cal-devis-cree')).toBeNull()
    rouvert.unmount()

    const attente = {}
    calepinageApi.calepinages.genererDevis = vi.fn(() => new Promise((ok) => { attente.ok = ok }))
    const second = await ouvrir()
    await userEvent.click(await screen.findByTestId('cal-generer-devis'))
    await waitFor(() => expect(calepinageApi.calepinages.genererDevis).toHaveBeenCalledTimes(1))
    second.unmount() // fermé pendant la requête
    await act(async () => { attente.ok({ data: { devis: 45, reference: 'DEV-2611-0045' } }) })
    await ouvrir()
    await screen.findByTestId('cal-generer-devis')
    expect(screen.queryByTestId('cal-devis-cree')).toBeNull()
    cleanup()
  })
})
