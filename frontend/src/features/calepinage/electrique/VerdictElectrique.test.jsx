/* CALX249 — le panneau « Verdict électrique » de l'atelier.

   D'OÙ VIENT LA FIXTURE, ET POURQUOI PAS UN CONTRAT COMMITTÉ. Le verdict
   publiable de CALX248 (`{publiable, motifs:[{code, statut, libelle,
   source}]}`) voyage sous la clé `publication` de la réponse de
   `POST calepinages/<pk>/evaluer-electrique/`. AUCUN échantillon de
   `backend/django_core/apps/calepinage/contract_samples/` ne porte
   aujourd'hui cette clé : `calepinage_resultat.json` décrit `GET resultat/`,
   qui ne la publie pas, et le seul `publiable` de `calepinage_simulation.json`
   est `quantiles_publiables` (sans rapport). La fixture ci-dessous est donc
   MINIMALE et DOCUMENTÉE : elle ne recopie aucun chiffre, seulement les
   QUATRE clés d'un motif telles que `services/electrique.py:1434-1450`
   (`_motif_publication`) les construit — et le premier test affirme qu'elle
   n'en porte ni plus ni moins.

   Ce qui est prouvé ici :
     1. l'appel part avec un corps VIDE (ni `layout`, ni `entree_electrique`) :
        c'est la seule forme pour laquelle le serveur renseigne `publication` ;
     2. les QUATRE statuts (`bloquant`, `alerte`, `omis`, `sans_source`)
        rendent quatre apparences DISTINCTES, et `non_verifiable` ne prend
        jamais l'apparence de `ok` ;
     3. un motif `sans_source` est signalé comme empêchant l'édition d'un
        document, et figure dans le « pourquoi » du verdict global ;
     4. AUCUN texte n'est composé côté navigateur : le libellé rendu est
        exactement celui du serveur, caractère pour caractère ;
     5. un verdict ABSENT (`publication: null`) rend la phrase du serveur ou la
        phrase fixe « Aucune évaluation enregistrée. » — jamais « Publiable »,
        jamais un chiffre ;
     6. chaque motif se range dans son domaine, et le bouton du domaine mène à
        l'onglet RESPONSABLE, nommé par le registre `atelier/onglets.js`. */
import { describe, it, expect, vi, beforeEach, afterEach, onTestFinished } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within, act } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { MemoryRouter, Route, Routes, useLocation, useSearchParams } from 'react-router-dom'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: {
    evaluerElectrique: vi.fn(), resultat: vi.fn(), enregistrerEntreeElectrique: vi.fn(),
    // ACAL1300 — l'étape Électrique de la coque (fin de fichier) lit aussi ces routes.
    entreeElectrique: vi.fn(), configurationsOnduleur: vi.fn(), pretAEnvoyer: vi.fn(), explications: vi.fn(),
  } },
}))
// ACAL284 — le droit `calepinage_approuver` (défaut gravé) commande « Passer outre ».
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: vi.fn(() => true) }))
// F3 — le registre des explications est lu UNE fois par page (promesse de module) : un test peut imposer
// le sien sans dépendre de l'ordre des tests ; sinon, le vrai crochet.
const registre = vi.hoisted(() => ({ force: null }))
vi.mock('../commun/useExplications', async (original) => {
  const vrai = await original()
  return { ...vrai, default: () => { const lu = vrai.default(); return registre.force ?? lu } }
})

import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { ongletParCle } from '../atelier/onglets'
import VerdictElectrique, { CLE_ONGLET } from './VerdictElectrique'
import EtapeElectrique from './EtapeElectrique'
import { ContexteCoque } from '../atelier/coque/contexteCoque'
import { creerCoucheElectrique } from '@roofpro/electrique3d'
import {
  DOMAINE_AUTRE, DOMAINES, LIBELLE_CODE_INCONNU, domaineDuMotif, grouperMotifs, libelleCode, libelleStatut, motifsRefusants,
  statutAbstention, statutRefuse, tonStatut,
} from './VerdictElectrique.helpers'
import LIBELLES_CODES from './libellesCodesVerdict.json'
import { provenanceLiaisonDc } from './resumeRaccordement'

/** Un motif, dans la forme EXACTE de `_motif_publication` — quatre clés. */
const motif = (code, statut, libelle, source = '') => ({
  code, statut, libelle, source,
})

const MOTIFS = [
  motif('FICHE_INCOMPLETE', 'bloquant',
    'onduleur : fiche technique absente du stock',
    'fiche technique du matériel retenu'),
  motif('CH_VOC_FROID_AU_DESSUS_V_MAX', 'alerte',
    'pan « Sud », chaîne CH1 : Voc à froid au-dessus de V_max',
    'fiche onduleur'),
  motif('NORME_NON_APPLICABLE', 'omis',
    "aucune norme électrique n'est applicable : sections, chutes de tension "
    + 'et check-list de terre sont OMISES',
    'services/norme.py::norme_applicable'),
  motif('elevation_tension', 'sans_source',
    "élévation de tension publiée sans la limite qui la juge"),
  motif('regime_phases', 'non_verifiable',
    'régime du branchement non saisi : aucun contrôle prononcé'),
  motif('chute_cumulee_dc', 'alerte',
    'chute cumulée DC au-dessus de la cible', 'NF C 15-100'),
  motif('TERRE_OMISE', 'omis',
    'liaison équipotentielle : aucune section saisie'),
  motif('SIGNE_DU_FUTUR', 'alerte',
    'un motif dont cet écran ne connaît pas encore le domaine', 'ailleurs'),
]

/** Réponse de `evaluer-electrique` : l'évaluation, plus la clé CALX248. */
const REPONSE = {
  verdict: 'conforme',
  publiable: false,
  bloquants: [],
  alertes: [],
  manquantes: [],
  publication: { publiable: false, motifs: MOTIFS },
}

const servir = (data) => {
  calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data })
}

const rendre = () => render(
  <MemoryRouter><VerdictElectrique calepinageId={12} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('VerdictElectrique (CALX249)', () => {
  it('la fixture porte EXACTEMENT les quatre clés d’un motif serveur', () => {
    for (const entree of MOTIFS) {
      expect(Object.keys(entree).sort())
        .toEqual(['code', 'libelle', 'source', 'statut'])
    }
  })

  it('appelle evaluer-electrique avec un corps VIDE (rien « à chaud »)', async () => {
    servir(REPONSE)

    rendre()

    await screen.findByTestId('calx249-panneau')
    expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalledTimes(1)
    const [idAppele, corps] = calepinageApi.calepinages
      .evaluerElectrique.mock.calls.at(-1)
    expect(idAppele).toBe(12)
    expect(corps).toEqual({})
    expect(corps).not.toHaveProperty('layout')
    expect(corps).not.toHaveProperty('entree_electrique')
  })

  it('rend QUATRE apparences distinctes pour les quatre statuts', async () => {
    servir(REPONSE)

    rendre()

    await screen.findByTestId('calx249-panneau')
    const apparences = [
      screen.getByTestId('calx249-statut-FICHE_INCOMPLETE').className,
      screen.getByTestId('calx249-statut-CH_VOC_FROID_AU_DESSUS_V_MAX').className,
      screen.getByTestId('calx249-statut-NORME_NON_APPLICABLE').className,
      screen.getByTestId('calx249-statut-elevation_tension').className,
    ]
    expect(new Set(apparences).size).toBe(4)
  })

  it('n’affiche JAMAIS une abstention avec l’apparence d’un « ok »', async () => {
    servir(REPONSE)

    rendre()

    await screen.findByTestId('calx249-panneau')
    const vert = tonStatut('ok')
    for (const statut of ['non_verifiable', 'omis', 'sans_source', 'bloquant',
      'alerte', 'statut-que-personne-ne-connait']) {
      expect(tonStatut(statut)).not.toBe(vert)
    }
    expect(screen.getByTestId('calx249-statut-regime_phases').className)
      .not.toBe(screen.getByTestId('calx249-statut-FICHE_INCOMPLETE').className)
  })

  it('signale un motif SANS SOURCE comme empêchant l’édition d’un document',
    async () => {
      servir(REPONSE)

      rendre()

      await screen.findByTestId('calx249-panneau')
      expect(screen.getByTestId('calx249-refuse-elevation_tension').textContent)
        .toContain('Empêche')
      // Il figure aussi dans le POURQUOI du verdict global…
      expect(screen.getByTestId('calx249-empeche-elevation_tension')).toBeTruthy()
      // …et une simple ALERTE, elle, n'empêche rien.
      expect(screen.queryByTestId('calx249-refuse-chute_cumulee_dc')).toBeNull()
      expect(screen.queryByTestId('calx249-empeche-chute_cumulee_dc')).toBeNull()
      expect(statutRefuse('sans_source')).toBe(true)
      expect(statutRefuse('bloquant')).toBe(true)
      expect(statutRefuse('omis')).toBe(false)
      expect(statutRefuse('non_verifiable')).toBe(false)
    })

  it('recopie le libellé du serveur MOT POUR MOT (rien n’est composé ici)',
    async () => {
      servir(REPONSE)

      rendre()

      await screen.findByTestId('calx249-panneau')
      for (const entree of MOTIFS) {
        expect(screen.getByTestId(`calx249-libelle-${entree.code}`).textContent)
          .toBe(entree.libelle)
      }
      // Une source vide ne devient jamais un texte fabriqué à sa place.
      expect(screen.queryByTestId('calx249-source-elevation_tension')).toBeNull()
      expect(screen.getByTestId('calx249-source-chute_cumulee_dc').textContent)
        .toBe('NF C 15-100')
    })

  it('affiche « Non publiable » et NOMME ce qui l’empêche', async () => {
    servir(REPONSE)

    rendre()

    await screen.findByTestId('calx249-panneau')
    expect(screen.getByTestId('calx249-publiable').textContent)
      .toBe('Non publiable')
    expect(screen.getByTestId('calx249-pourquoi-non')).toBeTruthy()
    expect(screen.queryByTestId('calx249-pourquoi-oui')).toBeNull()
    expect(motifsRefusants(MOTIFS).map((m) => m.code))
      .toEqual(['FICHE_INCOMPLETE', 'elevation_tension'])
    expect(screen
      .getByTestId('calx249-empeche-libelle-FICHE_INCOMPLETE').textContent)
      .toBe('onduleur : fiche technique absente du stock')
  })

  it('un dossier TOUT OMIS mais motivé se lit « Publiable »', async () => {
    servir({
      ...REPONSE,
      publication: {
        publiable: true,
        motifs: [MOTIFS[2], MOTIFS[6]],
      },
    })

    rendre()

    await screen.findByTestId('calx249-panneau')
    expect(screen.getByTestId('calx249-publiable').textContent).toBe('Publiable')
    expect(screen.getByTestId('calx249-pourquoi-oui')).toBeTruthy()
    expect(screen.queryByTestId('calx249-pourquoi-non')).toBeNull()
  })

  it('ACAL613 — à compléter : titre et phrase du serveur, ton ambre, lignes gardées', async () => {
    const donnees = exempleContrat('calepinage', 'calepinage_evaluation_electrique', 'exemple_a_completer')
    servir(donnees)

    rendre()

    await screen.findByTestId('calx249-panneau')
    const badge = screen.getByTestId('calx249-publiable')
    expect(badge.textContent).toBe(donnees.publication.titre)
    expect(badge.className).toContain('text-warning')
    expect(badge.className).not.toContain('text-success')
    expect(screen.getByTestId('calx249-pourquoi-oui').textContent).toBe(donnees.publication.phrase)
    expect(screen.queryByText('Publiable')).toBeNull()
    expect(screen.getByTestId('calx249-statut-FICHE_INCOMPLETE')).toBeTruthy()
  })

  it('ACAL613 — prêt garde le vert avec le titre du serveur', async () => {
    const donnees = exempleContrat('calepinage', 'calepinage_evaluation_electrique', 'exemple')
    servir(donnees)

    rendre()

    await screen.findByTestId('calx249-panneau')
    const badge = screen.getByTestId('calx249-publiable')
    expect(badge.textContent).toBe(donnees.publication.titre)
    expect(badge.className).toContain('text-success')
  })

  it('un verdict ABSENT ne devient jamais un « OK » supposé', async () => {
    servir({
      verdict: 'indetermine',
      publiable: false,
      bloquants: [],
      alertes: [],
      manquantes: ['onduleur : aucun produit désigné'],
      publication: null,
    })

    rendre()

    await screen.findByTestId('calx249-panneau')
    expect(screen.getByTestId('calx249-sans-verdict').textContent)
      .toContain('Aucune évaluation enregistrée')
    expect(screen.getByTestId('calx249-manquantes').textContent)
      .toContain('onduleur : aucun produit désigné')
    expect(screen.queryByTestId('calx249-publiable')).toBeNull()
    expect(screen.queryByTestId('calx249-global')).toBeNull()
  })

  it('range chaque motif dans SON domaine, l’inconnu compris', () => {
    expect(domaineDuMotif('FICHE_INCOMPLETE').cle).toBe('fiches')
    expect(domaineDuMotif('CH_PARTITION_NON_EGALE').cle).toBe('chaines')
    expect(domaineDuMotif('NORME_NON_APPLICABLE').cle).toBe('norme')
    expect(domaineDuMotif('RACCORDEMENT_REFUSE').cle).toBe('raccordement')
    expect(domaineDuMotif('desequilibre_phases').cle).toBe('raccordement')
    expect(domaineDuMotif('TRONCON_NON_CALCULABLE').cle).toBe('troncons')
    expect(domaineDuMotif('TERRE_JUSTIFICATION_MANQUANTE').cle).toBe('terre')
    expect(domaineDuMotif('SIGNE_DU_FUTUR')).toBe(DOMAINE_AUTRE)
    expect(domaineDuMotif(undefined)).toBe(DOMAINE_AUTRE)

    const groupes = grouperMotifs(MOTIFS)
    expect(groupes.map((g) => g.domaine.cle))
      .toEqual(['fiches', 'chaines', 'norme', 'raccordement', 'troncons',
        'terre', 'autre'])
    expect(grouperMotifs(null)).toEqual([])
  })

  it('le bouton du domaine mène à l’onglet responsable, NOMMÉ par le registre',
    async () => {
      servir(REPONSE)

      rendre()

      await screen.findByTestId('calx249-panneau')
      const lien = screen.getByTestId('calx249-aller-raccordement')
      const onglet = ongletParCle('raccordement')
      expect(lien.textContent).toBe(onglet.libelle)
      expect(lien.getAttribute('href'))
        .toBe('/calepinage/12?onglet=raccordement')
      expect(screen.getByTestId('calx249-aller-troncons').getAttribute('href'))
        .toBe('/calepinage/12?onglet=cheminement-cables')
      // La norme est un réglage SOCIÉTÉ : aucun onglet n'en répond, donc
      // aucun bouton — plutôt que d'en proposer un qui mènerait ailleurs.
      expect(screen.getByTestId('calx249-domaine-norme')).toBeTruthy()
      expect(screen.queryByTestId('calx249-aller-norme')).toBeNull()
      expect(screen.queryByTestId('calx249-aller-autre')).toBeNull()
    })

  it('chaque onglet responsable déclaré EXISTE dans le registre', () => {
    for (const domaine of DOMAINES) {
      if (domaine.onglet === null) continue
      expect(ongletParCle(domaine.onglet)).not.toBeNull()
    }
    expect(ongletParCle(CLE_ONGLET)).not.toBeNull()
  })

  it('nomme un statut inconnu plutôt que de le taire', () => {
    expect(libelleStatut('bloquant')).toBe('Bloquant')
    expect(libelleStatut('lunaire')).toBe('statut « lunaire »')
  })

  it('R3-09 — jamais un code brut : intitulé de métier, repli lisible pour un code inconnu', async () => {
    servir(REPONSE)

    rendre()

    await screen.findByTestId('calx249-panneau')
    expect(screen.getByTestId('calx249-code-NORME_NON_APPLICABLE').textContent).toBe(libelleCode('NORME_NON_APPLICABLE'))
    expect(libelleCode('NORME_NON_APPLICABLE')).toBe('Norme électrique non applicable')
    expect(screen.getByTestId('calx249-code-SIGNE_DU_FUTUR').textContent).toBe(LIBELLE_CODE_INCONNU)
    for (const entree of MOTIFS) {
      const rendu = screen.getByTestId(`calx249-code-${entree.code}`).textContent
      expect(rendu, entree.code).not.toBe(entree.code)
      expect(rendu).not.toMatch(/^[A-Za-z_]+$/)
    }
    // chaque intitulé de la table est une vraie phrase, jamais le code recopié.
    for (const [code, intitule] of Object.entries(LIBELLES_CODES)) {
      expect(intitule, code).not.toBe(code)
      expect(intitule, code).toMatch(/\s/)
    }
  })

  it('R3-09 — « Aucune provenance » masqué pour une abstention, gardé pour un motif qui a jugé', async () => {
    servir(REPONSE)

    rendre()

    await screen.findByTestId('calx249-panneau')
    expect(statutAbstention('omis')).toBe(true)
    expect(statutAbstention('non_verifiable')).toBe(true)
    expect(statutAbstention('bloquant')).toBe(false)
    expect(screen.queryByTestId('calx249-sans-source-regime_phases')).toBeNull()
    expect(screen.queryByTestId('calx249-sans-source-TERRE_OMISE')).toBeNull()
    expect(screen.getByTestId('calx249-sans-source-elevation_tension')).toHaveTextContent('Aucune provenance')
  })
})

/* ACAL284 — dérogations : réponse = exemple du contrat calepinage_resultat
   (jamais retapée), augmentée d'une alerte non bloquante et de son fil. */
describe('ACAL284 — dérogations posées et geste « Passer outre »', () => {
  const ALERTE = {
    code: 'ratio_dc_ac', libelle: 'Ratio DC/AC au-dessus du seuil société', conforme: false,
    bloquant: false, source: 'fiche', detail: '', temperature_c: null, temperature_source: null,
    temperature_mention: '',
  }
  const resultatAvec = ({ derogations = [], ecarts = [] } = {}) => {
    const r = exempleContrat('calepinage', 'calepinage_resultat')
    r.electrique = { ...r.electrique, verdicts: [...(r.electrique?.verdicts || []), ALERTE] }
    r.derogations = derogations
    r.ecarts_longueur = ecarts
    return { data: r }
  }
  const DEROGATION = {
    code: 'ratio_dc_ac', libelle: ALERTE.libelle, auteur: 'Utilisateur d’essai',
    horodatage: '2026-10-12T09:30:00+01:00', motif: 'Surdimensionnement voulu (est-ouest).', texte: '',
  }
  const monter = () => {
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { publication: null, manquantes: [] } })
    return render(<MemoryRouter><VerdictElectrique calepinageId={7} /></MemoryRouter>)
  }

  it('affiche la dérogation posée à côté de son alerte, et une orpheline dans « Dérogations enregistrées »', async () => {
    const orpheline = { ...DEROGATION, code: 'code_disparu', libelle: 'Contrôle retiré' }
    calepinageApi.calepinages.resultat.mockResolvedValue(resultatAvec({ derogations: [DEROGATION, orpheline] }))
    monter()
    expect(await screen.findByTestId('acal284-derogation-ratio_dc_ac'))
      .toHaveTextContent('Passée outre par Utilisateur d’essai')
    expect(screen.getByTestId('acal284-derogation-ratio_dc_ac')).toHaveTextContent('Surdimensionnement voulu')
    expect(screen.getByTestId('acal284-derogations-enregistrees')).toHaveTextContent('Contrôle retiré')
  })

  it('le geste Passer outre envoie {code, motif} et refuse un motif vide', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(resultatAvec())
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    monter()
    fireEvent.click(await screen.findByTestId('acal284-passer-outre-ratio_dc_ac'))
    const confirmer = screen.getByTestId('acal284-confirmer-ratio_dc_ac')
    expect(confirmer).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Motif de la dérogation/), { target: { value: 'Voulu.' } })
    expect(confirmer).not.toBeDisabled()
    fireEvent.click(confirmer)
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
      .toHaveBeenCalledWith(7, { derogations: [{ code: 'ratio_dc_ac', motif: 'Voulu.' }] }))
  })

  it('un 400 / 403 serveur est affiché tel quel', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(resultatAvec())
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({ response: { status: 400, data: {
      'derogations.0.motif': ['Le motif d’une dérogation est obligatoire.'],
      error: { code: 'validation_error', message: 'x', fields: {}, request_id: 'r' } } } })
    monter()
    fireEvent.click(await screen.findByTestId('acal284-passer-outre-ratio_dc_ac'))
    fireEvent.change(screen.getByLabelText(/Motif de la dérogation/), { target: { value: ' ok ' } })
    fireEvent.click(screen.getByTestId('acal284-confirmer-ratio_dc_ac'))
    expect(await screen.findByTestId('acal284-refus-ratio_dc_ac'))
      .toHaveTextContent('Le motif d’une dérogation est obligatoire.')
  })

  it('sans calepinage_approuver aucun bouton Passer outre', async () => {
    useHasPermission.mockReturnValue(false)
    calepinageApi.calepinages.resultat.mockResolvedValue(resultatAvec())
    monter()
    expect(await screen.findByText('Dérogation réservée aux approbateurs')).toBeInTheDocument()
    expect(screen.queryByTestId('acal284-passer-outre-ratio_dc_ac')).toBeNull()
    useHasPermission.mockReturnValue(true)
  })
})

/* ACAL712 — la carte « chaîne touchée par l'ombre » (niveau expert). */
describe('ACAL712 — carte chaîne touchée par l’ombre', () => {
  const CLE_EXPERT = 'calepinage.mode_expert.anonyme'
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  const servirCascade = (cascade) => {
    const r = exempleContrat('calepinage', 'calepinage_resultat')
    r.cascade = cascade
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: r })
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { publication: null, manquantes: [] } })
    return render(<MemoryRouter><VerdictElectrique calepinageId={7} /></MemoryRouter>)
  }
  const ombrage = () => structuredClone(
    exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple_ombrage_chaines').cascade)

  it('une carte pour la chaîne 1 du pan P1, aucune pour P2 ; parades sans chiffre ; lien Affectation', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirCascade(ombrage())
    const carte = await screen.findByTestId('acal712-carte-P1-1')
    expect(screen.getAllByTestId(/^acal712-carte-/)).toHaveLength(1)
    expect(screen.queryByTestId('acal712-carte-P2-1')).toBeNull()
    expect(carte).toHaveTextContent('Chaîne 1 touchée par l\'ombre')
    expect(carte).toHaveTextContent('1 module sous le seuil de votre société ; le module le plus ombré reçoit 50 % du soleil ; perte de la chaîne entre 33,3 % et 50 %')
    expect(carte).toHaveTextContent('Hypothèse de lecture, non mesurée')
    const parades = screen.getByTestId('acal712-parades')
    expect(parades).toHaveTextContent('mettre ces modules sur une chaîne à part')
    expect(parades).toHaveTextContent('poser un optimiseur sur ces modules')
    expect(parades).toHaveTextContent('déplacer ou retirer ces modules')
    expect(parades.textContent).not.toMatch(/%|\d/)
    expect(screen.getByTestId('acal712-modifier')).toHaveAttribute('href', '/calepinage/7?onglet=affectation')
  })

  it('ACAL619 — « Tension par temps froid » : une ligne par chaîne, les nombres servis, mots pour l’état', async () => {
    const chaines = exempleContrat('calepinage', 'calepinage_evaluation_electrique').chaines
    servir({ ...REPONSE, chaines })

    rendre()

    const ligne = await screen.findByTestId('acal619-ligne-1')
    expect(ligne).toHaveTextContent('642 V / 1 000 V — dans la limite')
    expect(ligne).toHaveTextContent('432 V / 200 V — dans la limite')
    expect(ligne).toHaveTextContent('-5 °C')
    expect(screen.getByTestId('acal619-ligne-2')).toHaveTextContent('535 V')
  })

  it('ACAL1544 — 4.18 s’écrit « 4,18 °C » et 18.59 « 18,59 A », une fiche par chaîne', async () => {
    const [une] = exempleContrat('calepinage', 'calepinage_evaluation_electrique').chaines
    servir({ ...REPONSE, chaines: [{ ...une, temperature_froide_c: 4.18, isc_a: 18.59 }] })

    rendre()

    const ligne = await screen.findByTestId('acal619-ligne-1')
    expect(ligne).toHaveTextContent('4,18 °C')
    expect(ligne).toHaveTextContent('18,59 A')
    expect(ligne.textContent).not.toMatch(/4\.18|18\.59/)
    expect(ligne.closest('table')).toBeNull()
  })

  it('ACAL619 — une chaîne indéterminée : « tension non calculable », jamais un nombre', async () => {
    const chaines = [{ ...exempleContrat('calepinage', 'calepinage_evaluation_electrique').chaines[0], voc_froid_v: null, vmp_chaud_v: null, indetermine: ['fiche module : Voc absent'] }]
    servir({ ...REPONSE, chaines })

    rendre()

    const ligne = await screen.findByTestId('acal619-ligne-1')
    expect(ligne).toHaveTextContent('tension non calculable : fiche module : Voc absent')
  })

  it('ACAL685 — « Boucles de câblage » : la ligne de l’échantillon, puis limite null, puis surface null', async () => {
    const boucle = exempleContrat('calepinage', 'calepinage_evaluation_electrique').boucles_dc[0]
    servir({ ...REPONSE, boucles_dc: [boucle] })
    rendre()
    const ligne = await screen.findByTestId('acal685-ligne-1')
    expect(ligne).toHaveTextContent('Chaîne 1 : boucle de 4,5 m², limite de 3 m² fixée par la société — au-dessus')
    expect(ligne).not.toHaveTextContent('limite de 4,5')
    cleanup()

    servir({ ...REPONSE, boucles_dc: [{ ...boucle, limite_m2: null, limite_source: null, depasse: null, indetermine: ['limite non saisie : réglage boucle_dc_max_m2'] }] })
    rendre()
    const sansLimite = await screen.findByTestId('acal685-ligne-1')
    expect(sansLimite).toHaveTextContent('boucle de 4,5 m², limite non saisie')
    expect(sansLimite).toHaveTextContent('réglage boucle_dc_max_m2')
    expect(sansLimite).not.toHaveTextContent('au-dessus')
    cleanup()

    servir({ ...REPONSE, boucles_dc: [{ ...boucle, surface_m2: null, depasse: null, indetermine: ['point de collecte non saisi'] }] })
    rendre()
    expect(await screen.findByTestId('acal685-ligne-1')).toHaveTextContent('Chaîne 1 : surface non calculable : point de collecte non saisi')
    cleanup()

    servir({ ...REPONSE, boucles_dc: [] })
    rendre()
    await waitFor(() => expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalled())
    expect(screen.queryByTestId('acal685-boucles')).toBeNull()
  })

  it('rien sans chaîne touchée, sans cascade, ou en guidé', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const sansEcart = ombrage()
    sansEcart.etapes[0].entree.chaines[0].ecart_bornes_pct = 0
    servirCascade(sansEcart)
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    expect(screen.queryByTestId('acal712-cartes')).toBeNull()
    cleanup()
    servirCascade(null)
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    expect(screen.queryByTestId('acal712-cartes')).toBeNull()
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirCascade(ombrage())
    await waitFor(() => expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalled())
    expect(screen.queryByTestId('acal712-cartes')).toBeNull()
  })
})

/* ── ACAL1299 / ACAL1300 — l'étape Électrique de la coque (maquette `Electrique.dc.html`) ──────────── */
describe('EtapeElectrique — étape guidée de la coque (maquette Électrique)', () => {
  const resultat = () => structuredClone(exempleContrat('calepinage', 'calepinage_resultat'))
  const entree = () => structuredClone(exempleContrat('calepinage', 'calepinage_entree_electrique'))
  const configs = () => structuredClone(exempleContrat('calepinage', 'calepinage_configurations_onduleur'))
  const pret = (controles) => {
    const p = structuredClone(exempleContrat('calepinage', 'calepinage_pret_a_envoyer'))
    if (controles) p.controles = controles
    return p
  }
  const servirEtape = ({ r = resultat(), e = entree(), c = configs(), p = pret() } = {}) => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: r })
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: e })
    calepinageApi.calepinages.configurationsOnduleur.mockResolvedValue({ data: c })
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue({ data: p })
    calepinageApi.calepinages.explications.mockResolvedValue({ data: { entrees: [] } })
  }
  function TemoinUrl() {
    return <p data-testid="temoin-url">{useLocation().search}</p>
  }
  const rendreEtape = ({ builderApi = null, id = 7, contexte = undefined } = {}) => {
    const surCarte = document.createElement('div')
    document.body.appendChild(surCarte)
    const coque = { noeuds: { surCarte, panneau: null, pied: null }, prendrePied: () => () => {} }
    const arbre = (api) => (
      <MemoryRouter initialEntries={[`/calepinage/${id}?onglet=verdict-electrique`]}>
        <Routes>
          <Route path="/calepinage/:id" element={(
            <ContexteCoque.Provider value={coque}>
              <EtapeElectrique calepinageId={id} builderApi={api} contexte={contexte} ouvert="verdict-electrique"
                action={{ libelle: 'Voir les résultats', onClick: () => {} }} />
              <TemoinUrl />
            </ContexteCoque.Provider>
          )} />
        </Routes>
      </MemoryRouter>
    )
    const { rerender } = render(arbre(builderApi))
    // Le constructeur de toit peut être prêt APRÈS l'arrivée des lignes : le test le fournit plus tard.
    surCarte.fournirConstructeur = (api) => rerender(arbre(api))
    return surCarte
  }
  afterEach(() => { document.body.innerHTML = '' })

  it('panneau dans l’ordre : onduleur, « Comparer avec N », « Prêt à envoyer ? » court, Schéma — Voir ; aucune clé technique', async () => {
    servirEtape()
    rendreEtape()
    const ecran = screen.getByTestId('cal-etape-electrique-ecran')
    // Le nom désigné et la ligne SERVIE de la configuration retenue (6 kW, 2 entrées) + panneaux du chaînage servi.
    await waitFor(() => expect(screen.getByTestId('cal-elec-onduleur')).toHaveTextContent('Onduleur hybride 10 kW (exemple)'))
    await waitFor(() => expect(screen.getByTestId('cal-elec-onduleur')).toHaveTextContent('6 kW · 2 entrées · proposé pour 12 panneaux'))
    // N = configurations servies autres que la retenue (2 dans l'échantillon).
    expect(screen.getByRole('button', { name: 'Comparer avec 2 autres onduleurs' })).toBeTruthy()
    const liste = await screen.findByTestId('cal-pret-a-envoyer')
    // Filtre « electrique » : les contrôles des autres étapes n'y sont pas.
    expect(await within(liste).findByTestId('cal-pret-ligne-tension_froid')).toHaveTextContent('Tension des chaînes par grand froid')
    expect(within(liste).queryByTestId('cal-pret-ligne-visite_validee')).toBeNull()
    expect(within(liste).queryByTestId('cal-pret-ligne-simulation_fraiche')).toBeNull()
    expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('Prêt à envoyer')
    const blocs = [...ecran.children].map((n) => n.getAttribute('data-testid'))
    // ACAL1830 : la carte « Prêt à envoyer ? » est EN TÊTE du panneau (maquette v2), puis l'onduleur, puis le Schéma.
    expect(blocs.indexOf('cal-pret-a-envoyer')).toBeLessThan(blocs.indexOf('cal-elec-onduleur'))
    expect(blocs.indexOf('cal-elec-onduleur')).toBeLessThan(blocs.indexOf('cal-elec-schema-voir'))
    expect(screen.getByTestId('cal-elec-schema-voir')).toHaveTextContent('Schéma électriqueDessiné tout seul à partir du raccordementVoir')
    // Rien de normatif ni de clé brute à l'écran guidé (mutant : réafficher `ombrage.shading12x24`).
    expect(ecran.textContent).not.toMatch(/shading12x24|NF C 15-100|UTE C 15-712|ombrage\./)
    // Les huit sections d'avant restent, repliées sous « Réglages avancés » — UN lien discret en bas (F3).
    expect(screen.getByTestId('cal-electrique-avances')).toHaveAttribute('data-state', 'closed')
    expect(screen.getByRole('button', { name: 'Réglages avancés' })).toHaveClass('cel-avances-lien')
    expect(ecran.lastElementChild).toHaveClass('cel-avances') // en dernier, après la carte Schéma
  })

  it('ACAL1830 — tous bons ⇒ section « Contrôles · N bons » repliée avec son compte ; carte verte, aucun « Régler »', async () => {
    const p = pret()
    servirEtape({ p })
    rendreEtape()
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('Prêt à envoyer'))
    const nbOk = p.controles.filter((c) => c.etat === 'ok').length
    expect(nbOk).toBeGreaterThan(0)
    const bons = screen.getByTestId('cal-pret-bons')
    expect(bons.open).toBe(false)
    expect(bons.querySelector('summary')).toHaveTextContent(`Contrôles · ${nbOk} ${nbOk > 1 ? 'bons' : 'bon'}`)
    expect(screen.getByTestId('cal-pret-a-envoyer').querySelector('.cel-pret-carte')).toHaveAttribute('data-ton', 'ok')
    expect(screen.queryByRole('button', { name: 'Régler' })).toBeNull()
    // Les contrôles bons restent à l'écran (dans la section), coche verte et « ? » compris.
    expect(within(bons).getByTestId('cal-pret-ligne-tension_froid').querySelector('.cel-pret-coche')).toBeTruthy()
  })

  it('ACAL1830 — le point à régler est DANS la carte en tête avec « Régler » appuyé (bleu nuit, 44 px) ; les bons sont dans la section', async () => {
    const base = pret()
    const ok = base.controles.find((c) => c.code === 'tension_froid')
    const aRegler = { ...ok, code: 'pente_toit', libelle: 'Pente du toit à confirmer', etat: 'a_regler',
      valeur_texte: '22° est une valeur de départ', cible: { etape: 'electrique', onglet: 'cheminement-cables', champ: '' } }
    servirEtape({ p: pret([ok, aRegler]) })
    rendreEtape()
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('1 point à régler'))
    const carte = screen.getByTestId('cal-pret-a-envoyer').querySelector('.cel-pret-carte')
    expect(carte).toHaveAttribute('data-ton', 'a_regler')
    const ligne = within(carte).getByTestId('cal-pret-ligne-pente_toit')
    const regler = within(ligne).getByRole('button', { name: 'Régler' })
    expect(regler).toHaveAttribute('data-recommande', 'oui')
    expect(within(carte).queryByTestId('cal-pret-ligne-tension_froid')).toBeNull()
    expect(within(screen.getByTestId('cal-pret-bons')).getByTestId('cal-pret-ligne-tension_froid')).toBeTruthy()
    expect(screen.getByTestId('cal-pret-bons').querySelector('summary')).toHaveTextContent('Contrôles · 1 bon')
    // La règle de la feuille : cible tactile de 44 px (la feuille réelle est chargée dans le DOM de test).
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/53-etape-electrique.css`, 'utf8')
    document.head.appendChild(style)
    try {
      expect(getComputedStyle(regler).minHeight).toBe('44px')
    } finally {
      style.remove()
    }
  })

  it('ACAL1830 — sous-titre de l’onduleur : « 2 entrées · proposé pour 12 panneaux » servi, jamais « En stock »', async () => {
    servirEtape()
    rendreEtape()
    const carte = screen.getByTestId('cal-elec-onduleur')
    await waitFor(() => expect(carte).toHaveTextContent('2 entrées · proposé pour 12 panneaux'))
    expect(carte).not.toHaveTextContent('En stock')
  })

  it('D-ACAL-71 — le menu de l’onduleur (étape guidée) dit « En stock » sur la ligne servie, rien sur l’autre', async () => {
    const e = entree()
    const servi = { ...e.candidats.onduleurs[0], id: 9101, libelle: 'Onduleur A', fiche_complete: true, champs_manquants: [], en_stock: true }
    e.candidats.onduleurs = [servi, { ...servi, id: 9102, libelle: 'Onduleur B', en_stock: null }]
    servirEtape({ e })
    rendreEtape()
    const menu = await screen.findByLabelText('Onduleur')
    await waitFor(() => expect(within(menu).getByRole('option', { name: /Onduleur A/ })).toHaveTextContent('· En stock'))
    expect(within(menu).getByRole('option', { name: /Onduleur B/ })).not.toHaveTextContent(/stock|rupture/i)
  })

  // T4-X2-004 — « proposé pour 5 panneaux » à côté d'un verdict « Bloquant : 2 » (courant de chaîne au-dessus du maxi).
  it('T4-X2-004 — un contrôle bloquant échoue : la ligne ne dit plus « proposé », elle dit pourquoi l’onduleur ne convient pas', async () => {
    const r = resultat()
    const courant = r.electrique.verdicts.find((v) => v.code === 'courant_par_entree_mppt')
    Object.assign(courant, { conforme: false, bloquant: true, detail: '18,6 A > 18,0 A maxi' })
    servirEtape({ r })
    rendreEtape()
    const carte = screen.getByTestId('cal-elec-onduleur')
    await waitFor(() => expect(carte).toHaveTextContent(`ne convient pas pour 12 panneaux : ${courant.libelle} (18,6 A > 18,0 A maxi)`))
    expect(carte).not.toHaveTextContent('proposé pour')
  })

  // T4-X9-002 — le libellé du contrôle collé à son détail disait « sous … (… au-dessus …) » : la raison COURTE servie
  // (`raison`, une phrase qui dit le fait et son sens) passe devant ; sans elle, le repli d'avant.
  it('T4-X9-002 — la raison courte servie remplace « libellé (détail) » dans la ligne de l’onduleur', async () => {
    const r = resultat()
    const courant = r.electrique.verdicts.find((v) => v.code === 'courant_par_entree_mppt')
    const raison = 'le courant des panneaux (18,6 A) dépasse ce qu’une entrée de cet onduleur accepte (18,0 A)'
    Object.assign(courant, { conforme: false, bloquant: true, detail: '18,6 A au-dessus de la borne de fiche 18,0 A', raison })
    servirEtape({ r })
    rendreEtape()
    const carte = screen.getByTestId('cal-elec-onduleur')
    await waitFor(() => expect(carte).toHaveTextContent(`ne convient pas pour 12 panneaux : ${raison} — comparez`))
    expect(carte).not.toHaveTextContent('borne de fiche')
  })

  it('F3 — lecture en cours : le titre est posé tout de suite, seules les lignes sont grisées, aucun compte inventé', async () => {
    servirEtape()
    calepinageApi.calepinages.pretAEnvoyer.mockReturnValue(new Promise(() => {}))
    rendreEtape({ id: 701 })
    const liste = screen.getByTestId('cal-pret-a-envoyer')
    expect(liste).toHaveAttribute('aria-busy', 'true')
    expect(within(liste).getByRole('heading', { name: 'Prêt à envoyer ?' })).toBeTruthy()
    expect(within(liste).getByTestId('cel-pret-attente')).toBeTruthy()
    expect(screen.queryByTestId('cal-electrique-synthese')).toBeNull()
    // La carte « Schéma électrique — Voir » est déjà à sa place.
    expect(screen.getByTestId('cal-elec-schema-voir')).toBeTruthy()
  })

  it('F3 — en revenant sur l’étape, la dernière liste SERVIE reste affichée pendant la relecture (plus de squelette)', async () => {
    servirEtape()
    rendreEtape({ id: 702 })
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('Prêt à envoyer'))
    cleanup()
    document.body.innerHTML = ''
    calepinageApi.calepinages.pretAEnvoyer.mockReturnValue(new Promise(() => {}))
    rendreEtape({ id: 702 })
    const liste = screen.getByTestId('cal-pret-a-envoyer')
    expect(within(liste).getByTestId('cal-pret-ligne-tension_froid')).toBeTruthy()
    expect(liste).toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByTestId('cel-pret-attente')).toBeNull()
  })

  it('F3 — le « ? » est sur chaque ligne qui a un texte (entrée `controle.*` du registre comprise, ok compris), jamais vide', async () => {
    const base = pret()
    const ok = { ...base.controles.find((c) => c.code === 'tension_froid'), seuil_source: null }
    const muet = { ...ok, code: 'orientation_mppt', libelle: 'Orientations par entrée MPPT', valeur_texte: 'Aucun point relevé' }
    servirEtape({ p: pret([ok, muet]) })
    registre.force = [{
      cle: 'controle.tension_froid', famille: 'controle', valeurs: {}, lexique: null, ecrans: [],
      phrase: 'Vérifie que la tension des chaînes par grand froid reste sous la tension maximale admise par l’onduleur.',
      geste: 'Si ce n’est pas bon : revoyez les chaînes.' }]
    onTestFinished(() => { registre.force = null })
    rendreEtape({ id: 703 })
    const ligne = await screen.findByTestId('cal-pret-ligne-tension_froid')
    const aide = await within(ligne).findByRole('button', { name: 'Pourquoi : Tension des chaînes par grand froid' })
    fireEvent.click(aide)
    expect(await screen.findByText(/reste sous la tension maximale admise/)).toBeTruthy()
    expect(screen.getByText('Si ce n’est pas bon : revoyez les chaînes.')).toBeTruthy()
    // Refermer la bulle (portail) avant le nettoyage du document.
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByText(/reste sous la tension maximale admise/)).toBeNull())
    // Aucun texte (ni registre, ni cause, ni source, ni geste) : aucun « ? » qui n'ouvrirait rien.
    expect(within(screen.getByTestId('cal-pret-ligne-orientation_mppt')).queryByRole('button', { name: /Pourquoi/ })).toBeNull()
  })

  it('F3 — légende de carte rangée par numéro de chaîne, quel que soit l’ordre de la table servie', async () => {
    const r = resultat()
    r.electrique.affectation.reverse()
    servirEtape({ r })
    const carte = rendreEtape({ builderApi: { setAffectationChaines: vi.fn() } })
    const legende = await within(carte).findByRole('group', { name: 'Couleurs des chaînes' })
    expect(legende.textContent).toBe('Chaîne 1 · entrée 1Chaîne 2 · entrée 2')
  })

  it('un point électrique à régler : pastille « 1 point à régler », ligne or pâle et « Régler » qui ouvre sa cible', async () => {
    const base = pret()
    const ok = base.controles.find((c) => c.code === 'tension_froid')
    const aRegler = { ...ok, code: 'chutes_tension', libelle: 'Chutes de tension', etat: 'a_regler',
      valeur_texte: 'Aucun tronçon mesuré', cible: { etape: 'electrique', onglet: 'cheminement-cables', champ: '' } }
    servirEtape({ p: pret([ok, aRegler]) })
    rendreEtape()
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('1 point à régler'))
    const ligne = screen.getByTestId('cal-pret-ligne-chutes_tension')
    expect(ligne).toHaveAttribute('data-etat', 'a_regler')
    fireEvent.click(within(ligne).getByRole('button', { name: 'Régler' }))
    expect(new URLSearchParams(screen.getByTestId('temoin-url').textContent).get('onglet')).toBe('cheminement-cables')
  })

  /* T4-U4-007 — « Régler » sur « Dossier électrique » ne faisait rien : sa cible est l'onglet d'OUVERTURE de l'étape
     (`verdict-electrique`), l'URL ne change pas et la section « Verdict » restait repliée sous « Réglages avancés ». */
  const dossierBloquant = () => {
    const ok = pret().controles.find((c) => c.code === 'tension_froid')
    return [ok, { ...ok, code: 'verdict_electrique', libelle: 'Dossier électrique', etat: 'bloquant',
      valeur_texte: 'Bloquant : 1', cause: '', geste: 'Corriger le dossier électrique',
      cible: { etape: 'electrique', onglet: 'verdict-electrique', champ: '' } }]
  }

  it('T4-U4-007 — « Régler » sur « Dossier électrique » ouvre « Verdict » sous « Réglages avancés » et y met le focus', async () => {
    servirEtape({ p: pret(dossierBloquant()) })
    servir(REPONSE)
    rendreEtape()
    const ligne = await screen.findByTestId('cal-pret-ligne-verdict_electrique')
    fireEvent.click(within(ligne).getByRole('button', { name: 'Régler' }))
    await waitFor(() => expect(screen.getByTestId('cal-electrique-avances')).toHaveAttribute('data-state', 'open'))
    const section = screen.getByTestId('cal-electrique-section-verdict-electrique')
    expect(section).toHaveAttribute('data-state', 'open')
    await waitFor(() => expect(document.activeElement).toBe(within(section).getByRole('button', { name: 'Verdict' })))
    expect(await within(section).findByTestId('calx249-panneau')).toBeTruthy()
  })

  /* ACAL1936 — les TROIS « Régler » de « Prêt à envoyer ? » amènent la section d'arrivée dans la partie visible : après
     son montage (les volets animent leur hauteur), jamais avant. La coque remonte l'écran à chaque changement d'onglet
     (clé `étape:onglet` de CoqueAtelier) : le harnais fait de même, avec la VRAIE étape et le VRAI « Prêt à envoyer ? ». */
  describe('ACAL1936 — « Régler » défile jusqu’à la section ouverte', () => {
    function Coque() {
      const [parametres] = useSearchParams()
      const onglet = parametres.get('onglet') ?? 'verdict-electrique'
      return (
        <EtapeElectrique key={onglet} calepinageId={7} ouvert={onglet}
          action={{ libelle: 'Voir les résultats', onClick: () => {} }} />
      )
    }
    const rendreCoque = () => {
      const surCarte = document.createElement('div')
      document.body.appendChild(surCarte)
      const coque = { noeuds: { surCarte, panneau: null, pied: null }, prendrePied: () => () => {} }
      render(
        <MemoryRouter initialEntries={['/calepinage/7?onglet=verdict-electrique']}>
          <Routes>
            <Route path="/calepinage/:id" element={<ContexteCoque.Provider value={coque}><Coque /><TemoinUrl /></ContexteCoque.Provider>} />
          </Routes>
        </MemoryRouter>,
      )
    }
    const controles = () => {
      const ok = pret().controles.find((c) => c.code === 'tension_froid')
      const ligne = (code, libelle, onglet) => ({ ...ok, code, libelle, etat: 'a_regler', valeur_texte: 'À régler',
        cible: { etape: 'electrique', onglet, champ: '' } })
      return [ok,
        ligne('verdict_electrique', 'Dossier électrique', 'verdict-electrique'),
        ligne('chutes_tension', 'Chutes de tension', 'cheminement-cables'),
        ligne('terre_protections', 'Terre et protections', 'decisions-electriques')]
    }
    let defiles
    beforeEach(() => {
      defiles = []
      HTMLElement.prototype.scrollIntoView = function suivre() {
        const section = this.closest('[data-testid^="cal-electrique-section-"]')
        defiles.push({ testid: section?.getAttribute('data-testid'), etat: section?.getAttribute('data-state') })
      }
    })
    afterEach(() => { delete HTMLElement.prototype.scrollIntoView })

    it.each([
      ['verdict_electrique', 'verdict-electrique'],
      ['chutes_tension', 'cheminement-cables'],
      ['terre_protections', 'decisions-electriques'],
    ])('« Régler » sur %s : la section %s est dépliée PUIS amenée à l’écran', async (code, section) => {
      servirEtape({ p: pret(controles()) })
      servir(REPONSE)
      rendreCoque()
      const ligne = await screen.findByTestId(`cal-pret-ligne-${code}`)
      expect(defiles).toEqual([]) // rien ne défile avant le geste
      fireEvent.click(within(ligne).getByRole('button', { name: 'Régler' }))
      await waitFor(() => expect(defiles.length).toBeGreaterThan(0))
      expect(defiles.at(-1)).toEqual({ testid: `cal-electrique-section-${section}`, etat: 'open' })
    })
  })

  it('T4-U4-007 — le « ? » de « Dossier électrique » nomme le point qui bloque (motif servi par evaluer-electrique)', async () => {
    servirEtape({ p: pret(dossierBloquant()) })
    servir(REPONSE)
    rendreEtape()
    const ligne = await screen.findByTestId('cal-pret-ligne-verdict_electrique')
    fireEvent.click(within(ligne).getByRole('button', { name: 'Pourquoi : Dossier électrique' }))
    const bulle = await screen.findByTestId('cal-pret-points-dossier')
    await waitFor(() => expect(within(bulle).getByRole('listitem')).toHaveTextContent('onduleur : fiche technique absente du stock'))
    expect(bulle).toHaveTextContent('Ce qui bloque :')
    expect(bulle).not.toHaveTextContent('pan « Sud »') // une alerte ne bloque pas : jamais citée comme bloquante
    cleanup() // la bulle vit dans un portail : démontée avant que l'afterEach du bloc ne vide le body
  })

  /* T4-U4-007 (moitié serveur) — « Prêt à envoyer » SERT les points du dossier (`controles[].points[]`, contrat
     `calepinage_pret_a_envoyer.json::exemple_points`) : le « ? » les lit tels quels (clé interne finale retirée) sans
     relire `evaluer-electrique`, et « Régler » suit la `cible` du point servi. */
  const dossierAvecPoints = () => {
    const [ok, dossier] = dossierBloquant()
    const servi = structuredClone(exempleContrat('calepinage', 'calepinage_pret_a_envoyer', 'exemple_points').controle)
    servi.points[0].phrase = 'Continuité de la terre existante à justifier (terre.justification_continuite)'
    servi.cause = servi.points[0].phrase
    return [ok, { ...dossier, ...servi }]
  }

  it('T4-U4-007 — le « ? » de « Dossier électrique » lit les points SERVIS, sans la clé interne finale', async () => {
    servirEtape({ p: pret(dossierAvecPoints()) })
    servir(REPONSE)
    rendreEtape()
    const ligne = await screen.findByTestId('cal-pret-ligne-verdict_electrique')
    const appelsAvant = calepinageApi.calepinages.evaluerElectrique.mock.calls.length
    fireEvent.click(within(ligne).getByRole('button', { name: 'Pourquoi : Dossier électrique' }))
    const bulle = await screen.findByTestId('cal-pret-points-dossier')
    expect(bulle).toHaveAttribute('data-source', 'servi')
    expect(bulle).toHaveTextContent('Ce qui bloque :')
    expect(within(bulle).getByRole('listitem')).toHaveTextContent(
      'Continuité de la terre existante à justifier — Compléter la check-list de terre')
    expect(document.body).not.toHaveTextContent('terre.justification_continuite')
    // la cause (= phrase du premier point) n'est pas dite une seconde fois
    expect(document.body.textContent.split('Continuité de la terre existante à justifier').length - 1).toBe(1)
    expect(calepinageApi.calepinages.evaluerElectrique.mock.calls.length).toBe(appelsAvant)
    cleanup()
  })

  it('T4-U4-007 — « Régler » de « Dossier électrique » suit la cible du point SERVI', async () => {
    servirEtape({ p: pret(dossierAvecPoints()) })
    servir(REPONSE)
    rendreEtape()
    const ligne = await screen.findByTestId('cal-pret-ligne-verdict_electrique')
    fireEvent.click(within(ligne).getByRole('button', { name: 'Régler' }))
    await waitFor(() => expect(new URLSearchParams(screen.getByTestId('temoin-url').textContent).get('onglet'))
      .toBe('decisions-electriques'))
  })

  it('ACAL1268 — lead de pompage : ni onduleur, ni batterie, ni schéma réseau ; un renvoi au devis agricole. Autre marché : inchangé', async () => {
    servirEtape()
    const contexte = (marche, devis = null) => ({ calepinage: { lead: 5 }, chiffrage: { marche }, cible: { devis_agricole: devis } })
    rendreEtape({ contexte: contexte('agricole', { id: 42, reference: 'DEV-AGR-42' }) })
    const ecran = screen.getByTestId('cal-etape-electrique-ecran')
    expect(within(ecran).getByRole('link', { name: 'Ouvrir le devis agricole DEV-AGR-42' })).toHaveAttribute('href', '/ventes/devis?devis=42')
    expect(ecran).toHaveTextContent('ni onduleur ni batterie')
    for (const absent of ['cal-elec-onduleur', 'cal-elec-schema-voir', 'cal-electrique-avances']) {
      expect(screen.queryByTestId(absent)).toBeNull()
    }
    cleanup()
    rendreEtape({ contexte: contexte('residentiel') })
    await waitFor(() => expect(screen.getByTestId('cal-elec-onduleur')).toBeTruthy())
    expect(document.querySelector('[data-zone="pompage-outil-pose"]')).toBeNull()
  })

  it('T4-U4-007 — une étape ouverte sur une section (« Régler » d’un autre point) la déplie et y met le focus', async () => {
    servirEtape()
    const surCarte = document.createElement('div')
    document.body.appendChild(surCarte)
    render(
      <MemoryRouter initialEntries={['/calepinage/7?onglet=cheminement-cables']}>
        <ContexteCoque.Provider value={{ noeuds: { surCarte, panneau: null, pied: null }, prendrePied: () => () => {} }}>
          <EtapeElectrique calepinageId={7} ouvert="cheminement-cables" action={{ libelle: 'Voir les résultats', onClick: () => {} }} />
        </ContexteCoque.Provider>
      </MemoryRouter>,
    )
    const section = screen.getByTestId('cal-electrique-section-cheminement-cables')
    expect(section).toHaveAttribute('data-state', 'open')
    await waitFor(() => expect(document.activeElement).toBe(within(section).getByRole('button', { name: 'Cheminement & câbles' })))
  })

  /* T4-U4-018 — le serveur câble pans, champs au sol et ombrières (`chaines.py::_pans_poses`, test serveur
     `SurfacesDePoseSeules`) : l'étape n'annonce plus rien de faux sur les surfaces. Quand le raccordement ne forme
     aucune chaîne (matériel non désigné), l'écran dit la cause SERVIE (`manquantes` de l'évaluation). */
  const SURFACES = {
    zones: [],
    poseSurfaces: [
      { kind: 'sol', id: 'sol-1', label: 'Champ au sol', moduleWc: 710, engine: { modules: 28 } },
      { kind: 'ombriere', id: 'omb-1', label: 'Ombrière parking', moduleWc: 710, engine: { modules: 16 } },
    ],
  }

  it('T4-U4-018 — champ au sol + ombrière : aucun avis « pas encore raccordés » (le serveur les câble)', async () => {
    servirEtape()
    const carte = rendreEtape({ builderApi: { serializeLayout: () => SURFACES } })
    expect(within(carte).getByRole('button', { name: 'Raccorder automatiquement' })).toBeInTheDocument()
    await waitFor(() => expect(calepinageApi.calepinages.resultat).toHaveBeenCalled())
    expect(document.body).not.toHaveTextContent('pas encore raccordé')
    expect(document.body).not.toHaveTextContent('ne câble aujourd’hui que')
  })

  it('T4-U4-018 — « Raccorder automatiquement » sans chaîne : la cause SERVIE (manquantes), jamais une phrase devinée', async () => {
    servirEtape()
    const manque = 'Onduleur : aucun onduleur désigné.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: { electrique: { affectation: [] } } })
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: {
      ...exempleContrat('calepinage', 'calepinage_evaluation_electrique', 'exemple_a_completer'), manquantes: [manque] } })
    const carte = rendreEtape({ builderApi: { serializeLayout: () => SURFACES } })
    fireEvent.click(within(carte).getByRole('button', { name: 'Raccorder automatiquement' }))
    const alerte = await within(carte).findByRole('alert')
    await waitFor(() => expect(alerte).toHaveTextContent(manque))
    expect(alerte).toHaveTextContent('Aucune chaîne formée :')
    expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalledWith(7, {})
    expect(alerte).not.toHaveTextContent('module de ce toit')
    expect(alerte).not.toHaveTextContent('pas encore')
  })

  /* Item 12 (T4-U4-012, côté écran) — « Raccorder automatiquement » forme des chaînes, mais le serveur les juge hors plage
     (chaîne trop courte : MPPT hors plage par forte chaleur) : l'écran le DIT avec la phrase servie, jamais un succès muet. */
  it('« Raccorder automatiquement » : chaînes formées mais verdict servi non conforme ⇒ la phrase servie est dite', async () => {
    servirEtape()
    const detail = 'Vmp à chaud 180 V < bas de plage MPPT 200 V — chaîne trop courte, MPPT hors plage en été'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: { electrique: {
      affectation: [{ module: 'm1', chaine: 1 }],
      verdicts: [
        { code: 'voc_cold_under_vmax', libelle: 'Voc à froid', conforme: true, bloquant: true, detail: '' },
        { code: 'vmp_hot_over_mppt_min', libelle: 'Vmp à chaud au-dessus du bas de la plage MPPT', conforme: false, bloquant: false, detail },
      ],
    } } })
    const carte = rendreEtape()
    fireEvent.click(within(carte).getByRole('button', { name: 'Raccorder automatiquement' }))
    const alerte = await within(carte).findByRole('alert')
    expect(alerte).toHaveTextContent('Chaînes formées, mais à revoir :')
    expect(alerte).toHaveTextContent(detail)
    expect(alerte).not.toHaveTextContent('Voc à froid')
  })

  it('« Voir » ouvre le sous-écran Schéma (`?onglet=schema`)', async () => {
    servirEtape()
    rendreEtape()
    fireEvent.click(within(screen.getByTestId('cal-elec-schema-voir')).getByRole('button', { name: 'Voir' }))
    expect(new URLSearchParams(screen.getByTestId('temoin-url').textContent).get('onglet')).toBe('schema')
  })

  it('choisir un onduleur fait le geste de l’onglet Matériel : les trois désignations, `onduleur_produit` remplacé', async () => {
    const e = entree()
    e.candidats.onduleurs = [
      { id: 901, libelle: 'Onduleur A', marque: '', favori: false, fiche_complete: true, champs_manquants: [] },
      { id: 902, libelle: 'Onduleur B', marque: 'M', favori: false, fiche_complete: true, champs_manquants: [] },
    ]
    servirEtape({ e })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendreEtape()
    const choix = await screen.findByLabelText('Onduleur')
    await waitFor(() => expect(choix).not.toBeDisabled())
    fireEvent.change(choix, { target: { value: '902' } })
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledWith(7, {
      module_produit: 4112, onduleur_produit: 902, optimiseur_produit: null,
    }))
    // L'écran relit ensuite ce que le serveur a stocké.
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalledTimes(2))
  })

  it('R5C-N2 — un onduleur à fiche incomplète nomme le champ en mots, jamais sa clé (v_max_abs)', async () => {
    const e = entree()
    e.candidats.onduleurs = [
      { id: 903, libelle: 'Onduleur injection 30kW', marque: '', favori: false, fiche_complete: false, champs_manquants: ['v_max_abs'] },
    ]
    servirEtape({ e })
    rendreEtape()
    const choix = await screen.findByLabelText('Onduleur')
    const option = within(choix).getByRole('option', { name: /Onduleur injection 30kW/ })
    expect(option).toHaveTextContent('fiche incomplète : Tension maximale absolue (V)')
    expect(option).not.toHaveTextContent('v_max_abs')
  })

  it('« Comparer avec N autres onduleurs » ouvre la comparaison existante, sans seconde lecture', async () => {
    servirEtape()
    rendreEtape()
    fireEvent.click(await screen.findByRole('button', { name: 'Comparer avec 2 autres onduleurs' }))
    expect(screen.getByTestId('acal617-carte-43')).toBeTruthy()
    expect(screen.queryByTestId('acal617-lien')).toBeNull()
    expect(calepinageApi.calepinages.configurationsOnduleur).toHaveBeenCalledTimes(1)
  })

  it('S3 — le constructeur du toit prêt APRÈS l’arrivée des lignes : la teinte est quand même poussée, une seule fois', async () => {
    servirEtape()
    const carte = rendreEtape({ builderApi: null })
    await within(carte).findByTestId('cal-sur-carte-resume') // les lignes sont arrivées, aucun constructeur
    const builderApi = { setAffectationChaines: vi.fn() }
    carte.fournirConstructeur(builderApi)
    await waitFor(() => expect(builderApi.setAffectationChaines).toHaveBeenCalledTimes(1))
    expect(builderApi.setAffectationChaines).toHaveBeenCalledWith(resultat().electrique.affectation, 'chaine')
    // Un constructeur sans la méthode (ancien build) : rien n'est appelé, aucune erreur.
    carte.fournirConstructeur({})
  })

  it('carte : pastille « Chaînes | Onduleur | Câble côté panneaux » servie, légende des couleurs dessinées, barre d’actions', async () => {
    servirEtape()
    const builderApi = { setAffectationChaines: vi.fn() }
    const carte = rendreEtape({ builderApi })
    const pastille = await within(carte).findByTestId('cal-sur-carte-resume')
    // 2 chaînes de 2 modules, onduleur dimensionné 10 kW, câble DC = 18,4 + 12,0 m mesurés.
    await waitFor(() => expect(pastille).toHaveTextContent('Chaînes2 × 2 panneaux'))
    expect(pastille).toHaveTextContent('Onduleur10 kW')
    expect(pastille).toHaveTextContent('Câble côté panneaux30 m')
    // Les couleurs servies sont poussées au constructeur, et la légende les nomme.
    await waitFor(() => expect(builderApi.setAffectationChaines).toHaveBeenCalledWith(resultat().electrique.affectation, 'chaine'))
    const legende = within(carte).getByRole('group', { name: 'Couleurs des chaînes' })
    expect(legende).toHaveTextContent('Chaîne 1 · entrée 1')
    expect(legende).toHaveTextContent('Chaîne 2 · entrée 2')
    const barre = within(carte).getByTestId('cal-elec-actions-carte')
    expect(within(barre).getByRole('button', { name: 'Raccorder automatiquement' })).toBeTruthy()
    expect(within(barre).getByRole('button', { name: 'Modifier une chaîne' })).toBeTruthy()
    // ACAL1317 : sans couche électrique du constructeur, aucun geste d'onduleur (« Déplacer l'onduleur ») n'est proposé.
    expect(within(barre).queryByText(/Déplacer l/)).toBeNull()
  })

  it('carte : un câble non mesuré est OMIS (jamais une longueur inventée) ; sans constructeur, aucune légende', async () => {
    const r = resultat()
    r.troncons = null
    servirEtape({ r })
    const carte = rendreEtape()
    const pastille = await within(carte).findByTestId('cal-sur-carte-resume')
    await waitFor(() => expect(pastille).toHaveTextContent('Chaînes'))
    expect(pastille).not.toHaveTextContent('Câble côté panneaux')
    expect(within(carte).queryByRole('group', { name: 'Couleurs des chaînes' })).toBeNull()
  })

  it('« Raccorder automatiquement » envoie l’affectation automatique ; un refus du serveur est affiché tel quel', async () => {
    servirEtape()
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValueOnce({
      response: { data: { affectation_manuelle: 'Aucun onduleur désigné : chaînage impossible.' } } })
    const carte = rendreEtape()
    fireEvent.click(await within(carte).findByRole('button', { name: 'Raccorder automatiquement' }))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
      .toHaveBeenCalledWith(7, { affectation_manuelle: [] }))
    expect(await within(carte).findByText('Aucun onduleur désigné : chaînage impossible.')).toBeTruthy()
  })

  it('S3 — « Raccorder automatiquement » lancé depuis l’éditeur d’affectation le rafraîchit (plus d’ancien état jusqu’au rechargement)', async () => {
    const avant = resultat()
    const apres = resultat()
    apres.electrique.affectation.forEach((l) => { if (l.chaine != null) l.chaine = 3 })
    let reclame = false
    servirEtape({ r: avant })
    calepinageApi.calepinages.resultat.mockImplementation(() => Promise.resolve({ data: reclame ? apres : avant }))
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { modules_sous_seuil: [] } })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockImplementation(() => {
      reclame = true
      return Promise.resolve({ data: apres })
    })
    const carte = rendreEtape()
    fireEvent.click(await within(carte).findByRole('button', { name: 'Modifier une chaîne' }))
    const legende = await screen.findByTestId('cal234-legende')
    await waitFor(() => expect(legende).toHaveTextContent('Chaîne 1'))
    fireEvent.click(within(carte).getByRole('button', { name: 'Raccorder automatiquement' }))
    await waitFor(() => expect(screen.getByTestId('cal234-legende')).toHaveTextContent('Chaîne 3'))
    expect(screen.getByTestId('cal234-legende')).not.toHaveTextContent('Chaîne 1')
  })

  describe('D-ACAL-157 — désigner une batterie (sélecteur à côté de celui de l’onduleur)', () => {
    beforeEach(() => { calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} }) })
    const entreeAvec = ({ hybride, batterie = null }) => {
      const e = entree()
      e.materiel.onduleur.hybride = hybride
      e.entree.batterie = batterie
      return e
    }

    it('onduleur réseau, aucune batterie désignée : aucun sélecteur de batterie', async () => {
      servirEtape({ e: entreeAvec({ hybride: false }) })
      rendreEtape()
      await screen.findByTestId('cal-elec-onduleur')
      expect(screen.queryByTestId('cal-elec-batterie')).toBeNull()
      expect(screen.queryByTestId('cal-elec-batterie-inapplicable')).toBeNull()
    })

    it('onduleur hybride : sélecteur « Aucune » par défaut, candidats sans prix ; le choix envoie l’objet batterie COMPLET', async () => {
      servirEtape({ e: entreeAvec({ hybride: true, batterie: { packs: 2, strategie: 'autoconsommation' } }) })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie')
      const choix = within(carte).getByRole('combobox')
      expect(choix).toHaveValue('')
      expect(within(carte).getByRole('option', { name: 'Aucune' })).toBeTruthy()
      expect(carte.textContent).not.toMatch(/MAD|DH|prix/i)
      const lectures = calepinageApi.calepinages.entreeElectrique.mock.calls.length
      fireEvent.change(choix, { target: { value: '905' } })
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledWith(
        7, { batterie: { packs: 2, strategie: 'autoconsommation', produit: 905 } }))
      await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique.mock.calls.length).toBeGreaterThan(lectures))
    })

    it('un refus du serveur (onduleur non hybride) est dit tel quel sous le sélecteur', async () => {
      servirEtape({ e: entreeAvec({ hybride: true }) })
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValueOnce({
        response: { data: { 'batterie.produit': 'L’onduleur désigné n’est pas un onduleur hybride.' } } })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie')
      fireEvent.change(within(carte).getByRole('combobox'), { target: { value: '905' } })
      expect(await within(carte).findByRole('alert')).toHaveTextContent('n’est pas un onduleur hybride')
    })

    it('batterie désignée puis onduleur devenu non hybride : l’écran le dit, propose de la retirer, ne l’efface pas', async () => {
      servirEtape({ e: entreeAvec({ hybride: false, batterie: { produit: 905, packs: 3 } }) })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie-inapplicable')
      expect(carte).toHaveTextContent('la batterie « Batterie 5,1 kWh (exemple) » ne s’applique plus')
      expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()
      fireEvent.click(within(carte).getByRole('button', { name: 'Retirer la batterie' }))
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
        .toHaveBeenCalledWith(7, { batterie: null }))  // plus rien d'autre de saisi : retour à « jamais désignée »
    })

    it('retirer une batterie dont la déclaration porte d’autres saisies garde ces saisies, sans produit ni packs', async () => {
      servirEtape({ e: entreeAvec({ hybride: true, batterie: { produit: 905, packs: 2, strategie: 'autoconsommation' } }) })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie')
      fireEvent.change(within(carte).getByRole('combobox'), { target: { value: '' } })
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
        .toHaveBeenCalledWith(7, { batterie: { strategie: 'autoconsommation', produit: null } }))
    })

    it('première désignation : `packs` part explicitement (1) pour que stocké, écran et dessin comptent pareil', async () => {
      servirEtape({ e: entreeAvec({ hybride: true }) })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie')
      fireEvent.change(within(carte).getByRole('combobox'), { target: { value: '905' } })
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
        .toHaveBeenCalledWith(7, { batterie: { produit: 905, packs: 1 } }))
    })

    it('sans batterie désignée mais avec une ligne batterie au devis : la carte le dit, jamais un « Aucune » muet', async () => {
      const e = entreeAvec({ hybride: true })
      e.candidats.batterie_du_devis = { produit_id: 905, designation: 'Batterie du devis', packs: 3 }
      servirEtape({ e })
      rendreEtape()
      const note = await screen.findByTestId('cal-elec-batterie-du-devis')
      expect(note).toHaveTextContent('le schéma montre la batterie du devis (« Batterie du devis », 3 unités)')
    })

    it('ancienne entrée sans packs : la carte affiche ce que le dessin compte (la quantité du devis), pas 1', async () => {
      const e = entreeAvec({ hybride: true, batterie: { produit: 905 } })
      e.candidats.batterie_du_devis = { produit_id: 905, designation: 'Batterie du devis', packs: 3 }
      servirEtape({ e })
      rendreEtape()
      expect(await screen.findByTestId('cal-elec-batterie-packs')).toHaveTextContent('3 batteries')
    })

    it('une batterie que le juge dit incompatible est grisée avec SES raisons ; « inconnu » reste proposée', async () => {
      const e = entreeAvec({ hybride: true })
      e.candidats.batteries = [
        { id: 905, libelle: 'Batterie 48 V', marque: 'M', favori: false, fiche_complete: true, champs_manquants: [],
          compatibilite: { statut: 'incompatible', raisons: ['tension nominale 48 V hors de la plage 150-500 V'] } },
        { id: 906, libelle: 'Batterie sans tension', marque: 'M', favori: false, fiche_complete: true, champs_manquants: [],
          compatibilite: { statut: 'inconnu', raisons: ['tension nominale inconnue'] } },
      ]
      servirEtape({ e })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie')
      const incompatible = within(carte).getByRole('option', { name: /Batterie 48 V — incompatible : tension nominale 48 V hors de la plage 150-500 V/ })
      expect(incompatible).toBeDisabled()
      expect(within(carte).getByRole('option', { name: 'Batterie sans tension (M)' })).not.toBeDisabled()
    })

    it('batterie désignée : le nombre de batteries se règle par pas, avec l’objet complet', async () => {
      servirEtape({ e: entreeAvec({ hybride: true, batterie: { produit: 905, packs: 2, couplage: 'dc' } }) })
      rendreEtape()
      const carte = await screen.findByTestId('cal-elec-batterie')
      expect(within(carte).getByTestId('cal-elec-batterie-packs')).toHaveTextContent('2 batteries')
      fireEvent.click(within(carte).getByRole('button', { name: 'Une batterie de plus' }))
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
        .toHaveBeenCalledWith(7, { batterie: { produit: 905, packs: 3, couplage: 'dc' } }))
    })
  })

  describe('S3 — « Raccorder automatiquement » depuis l’éditeur : brouillon non enregistré', () => {
    const ouvrirEditeur = async () => {
      servirEtape()
      calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { modules_sous_seuil: [] } })
      calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: resultat() })
      const carte = rendreEtape()
      fireEvent.click(await within(carte).findByRole('button', { name: 'Modifier une chaîne' }))
      await screen.findByTestId('cal234-ecran')
      return carte
    }
    const salirLEditeur = () => {
      fireEvent.pointerDown(screen.getByTestId('cal234-module-z2#3'))
      fireEvent.pointerUp(screen.getByTestId('cal234-module-z2#3'))
      fireEvent.change(screen.getByTestId('cal234-champ-chaine'), { target: { value: '2' } })
      fireEvent.change(screen.getByTestId('cal234-champ-mppt'), { target: { value: '2' } })
      fireEvent.change(screen.getByTestId('cal234-champ-onduleur'), { target: { value: '1' } })
      fireEvent.click(screen.getByTestId('cal234-affecter'))
    }

    it('éditeur propre, aucune ligne manuelle enregistrée : aucune confirmation, l’envoi part (comme avant)', async () => {
      const carte = await ouvrirEditeur()
      fireEvent.click(within(carte).getByRole('button', { name: 'Raccorder automatiquement' }))
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
      expect(within(carte).queryByText(/Confirmez pour continuer/)).toBeNull()
    })

    it('éditeur avec brouillon : la barre demande confirmation, rien n’est envoyé ; confirmer envoie puis relit', async () => {
      const carte = await ouvrirEditeur()
      salirLEditeur()
      expect(await screen.findByTestId('cal234-enregistrer')).not.toBeDisabled()
      const lectures = calepinageApi.calepinages.resultat.mock.calls.length
      fireEvent.click(within(carte).getByRole('button', { name: 'Raccorder automatiquement' }))
      expect(await within(carte).findByText(/modifications non enregistrées seront perdues/)).toBeTruthy()
      expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()
      fireEvent.click(within(carte).getByRole('button', { name: 'Confirmer : perdre mes modifications' }))
      await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
      await waitFor(() => expect(calepinageApi.calepinages.resultat.mock.calls.length).toBeGreaterThan(lectures))
    })
  })

  it('« Modifier une chaîne » ouvre l’écran d’affectation existant dans le panneau, avec un retour', async () => {
    servirEtape()
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { modules_sous_seuil: [] } })
    const carte = rendreEtape()
    fireEvent.click(await within(carte).findByRole('button', { name: 'Modifier une chaîne' }))
    expect(await screen.findByTestId('cal234-ecran')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Raccordement' }))
    expect(await screen.findByTestId('cal-elec-onduleur')).toBeTruthy()
  })

  it('ACAL1317 — après un geste sur l’onduleur, l’ANCIENNE longueur n’est pas montrée tant que l’atelier n’est pas enregistré et relu', async () => {
    servirEtape()
    const origine = [-7.6, 33.5]
    const m = (Math.PI / 180) * 6378137
    const versLngLat = (e, n) => [origine[0] + e / (m * Math.cos((origine[1] * Math.PI) / 180)), origine[1] + n / m]
    const couche = creerCoucheElectrique({
      electrical: null, sceneOrigin: origine, activeAreaId: 'z1',
      areas: [{ id: 'z1', renderPlan: { pack: { origin: origine, azimuthDeg: 180, ringENU: [[0, 0], [20, 0], [20, 12], [0, 12]] },
        grid: { rowWidthM: 2, panels: [3, 5, 7, 9].map((cx) => ({ cx, cy: 6 })) } } }],
    })
    const builderApi = { setAffectationChaines: vi.fn(), electrique: couche }
    const surCarte = document.createElement('div')
    document.body.appendChild(surCarte)
    const coque = { noeuds: { surCarte, panneau: null, pied: null }, prendrePied: () => () => {} }
    const arbre = (enregistreLe) => (
      <MemoryRouter initialEntries={['/calepinage/7']}>
        <Routes>
          <Route path="/calepinage/:id" element={(
            <ContexteCoque.Provider value={coque}>
              <EtapeElectrique calepinageId={7} builderApi={builderApi} enregistreLe={enregistreLe}
                action={{ libelle: 'Voir les résultats', onClick: () => {} }} />
            </ContexteCoque.Provider>
          )} />
        </Routes>
      </MemoryRouter>
    )
    const { rerender } = render(arbre('T0'))
    const pastille = await within(surCarte).findByTestId('cal-sur-carte-resume')
    await waitFor(() => expect(pastille).toHaveTextContent('Câble côté panneaux30 m'))
    fireEvent.click(within(surCarte).getByRole('button', { name: 'Placer l’onduleur' }))
    act(() => { couche.clicCarte(versLngLat(19, 2)) })
    expect(pastille).toHaveTextContent('Câble côté panneauxà mesurer à l’enregistrement')
    expect(pastille).not.toHaveTextContent('30 m')
    expect(within(surCarte).getByTestId('cal-elec-cable-provenance')).toHaveTextContent('tracé proposé le long des rangées (position de l’onduleur)')
    // L'atelier est enregistré : tant que le résultat n'est pas RELU, l'ancien chiffre reste retenu.
    let servir
    calepinageApi.calepinages.resultat.mockReturnValueOnce(new Promise((r) => { servir = r }))
    rerender(arbre('T1'))
    expect(pastille).toHaveTextContent('à mesurer à l’enregistrement')
    const relu = resultat()
    relu.troncons.troncons = relu.troncons.troncons.map((t) => (t.cote === 'dc' ? { ...t, longueur_m: 21 } : t))
    await act(async () => { servir({ data: relu }) })
    await waitFor(() => expect(pastille).toHaveTextContent('Câble côté panneaux42 m'))
  })

  it('liaison DC tracée — la longueur que la simulation compte sous « Câble côté panneaux », retenue après un geste, relue après l’enregistrement', async () => {
    // Le fragment COMMITTÉ du contrat : 28 m = 3 m dans le pan + 19 m de tracé + 6 m de descente saisie.
    const liaison = exempleContrat('calepinage', 'calepinage_resultat', 'liaison_dc_tracee')
    servirEtape({ r: { ...resultat(), simule: true, simulation_perimee: false, longueurs: structuredClone(liaison.longueurs) } })
    const origine = [-7.6, 33.5]
    const m = (Math.PI / 180) * 6378137
    const versLngLat = (e, n) => [origine[0] + e / (m * Math.cos((origine[1] * Math.PI) / 180)), origine[1] + n / m]
    const couche = creerCoucheElectrique({
      electrical: null, sceneOrigin: origine, activeAreaId: 'z1',
      areas: [{ id: 'z1', renderPlan: { pack: { origin: origine, azimuthDeg: 180, ringENU: [[0, 0], [20, 0], [20, 12], [0, 12]] },
        grid: { rowWidthM: 2, panels: [3, 5, 7, 9].map((cx) => ({ cx, cy: 6 })) } } }],
    })
    const builderApi = { setAffectationChaines: vi.fn(), electrique: couche }
    const surCarte = document.createElement('div')
    document.body.appendChild(surCarte)
    const coque = { noeuds: { surCarte, panneau: null, pied: null }, prendrePied: () => () => {} }
    const arbre = (enregistreLe) => (
      <MemoryRouter initialEntries={['/calepinage/7']}>
        <Routes>
          <Route path="/calepinage/:id" element={(
            <ContexteCoque.Provider value={coque}>
              <EtapeElectrique calepinageId={7} builderApi={builderApi} enregistreLe={enregistreLe}
                action={{ libelle: 'Voir les résultats', onClick: () => {} }} />
            </ContexteCoque.Provider>
          )} />
        </Routes>
      </MemoryRouter>
    )
    const { rerender } = render(arbre('T0'))
    const ligne = await within(surCarte).findByTestId('cal-elec-cable-simulation')
    expect(ligne).toHaveTextContent('La simulation compte 28 m (tracé du plan et longueurs saisies — une longueur saisie l’emporte sur le plan)')
    expect(ligne).toHaveTextContent('+ 6 m descente verticale (saisie)')
    // Un geste sur l'onduleur : la longueur comptée décrit l'ANCIEN tracé, elle n'est plus montrée.
    fireEvent.click(within(surCarte).getByRole('button', { name: 'Placer l’onduleur' }))
    act(() => { couche.clicCarte(versLngLat(19, 2)) })
    expect(within(surCarte).getByTestId('cal-sur-carte-resume')).toHaveTextContent('à mesurer à l’enregistrement')
    expect(within(surCarte).queryByTestId('cal-elec-cable-simulation')).toBeNull()
    // Enregistré, pas encore relu : toujours retenue.
    let servir
    calepinageApi.calepinages.resultat.mockReturnValueOnce(new Promise((r) => { servir = r }))
    rerender(arbre('T1'))
    expect(within(surCarte).queryByTestId('cal-elec-cable-simulation')).toBeNull()
    // Relu : le document a changé, la simulation rangée est périmée — la longueur est celle que la PROCHAINE comptera.
    const relu = { ...resultat(), simule: false, simulation_perimee: true, longueurs: structuredClone(liaison.longueurs) }
    relu.longueurs.dc.valeur_m = 33
    await act(async () => { servir({ data: relu }) })
    const relue = await within(surCarte).findByTestId('cal-elec-cable-simulation')
    expect(relue).toHaveTextContent('La simulation comptera 33 m')
  })
})

/* Liaison DC tracée (suite ACAL1317) — la provenance de la longueur que la simulation compte, lue sur le fragment
   COMMITTÉ du contrat (`calepinage_resultat.json` › `liaison_dc_tracee`), jamais sur une charge inventée. */
describe('provenanceLiaisonDc — quelle longueur la simulation compte', () => {
  const servi = () => structuredClone(exempleContrat('calepinage', 'calepinage_resultat', 'liaison_dc_tracee'))

  const parts = ' : 3 m module le plus éloigné → départ du tracé « chA » (plan) + 19 m tracé « chA » jusqu\'à '
    + 'l\'onduleur « eq1 », à plat (plan) + 6 m descente verticale (saisie)'

  it('tracé + descente saisie (le tracé tel que l’atelier l’écrit) : la longueur comptée, ses parts et leur source', () => {
    // 28 m servis = 3 m dans le pan + 19 m de tracé (la pastille) + 6 m de descente : jamais la pastille seule.
    // Sans simulation fraîche servie (le fragment n'en porte pas), c'est la PROCHAINE qui comptera.
    expect(provenanceLiaisonDc(servi())).toBe('La simulation comptera 28 m (tracé du plan et longueurs saisies — une '
      + `longueur saisie l’emporte sur le plan)${parts}`)
    expect(provenanceLiaisonDc({ ...servi(), simule: true, simulation_perimee: false }))
      .toMatch(/^La simulation compte 28 m \(/)
  })

  it('plan seul, longueurs saisies, aucune longueur, ou rien de servi', () => {
    const plan = servi()
    plan.longueurs.source_dc = 'trace'
    expect(provenanceLiaisonDc(plan)).toBe(`La simulation comptera 28 m (relevée sur le plan)${parts}`)
    const saisie = servi()
    saisie.longueurs.source_dc = 'saisie'
    expect(provenanceLiaisonDc(saisie)).toBe(`La simulation comptera 28 m (longueurs saisies)${parts}`)
    const defaut = servi()
    defaut.longueurs = { dc: null, ac: null, source_dc: 'defaut' }
    expect(provenanceLiaisonDc(defaut))
      .toBe('Longueur inconnue de la simulation : la perte de ce câble y est supposée, ou non comptée')
    const inconnue = servi()
    inconnue.longueurs.source_dc = 'toString'
    expect(provenanceLiaisonDc(inconnue)).toBeNull()
    expect(provenanceLiaisonDc({ troncons: servi().troncons })).toBeNull()
    expect(provenanceLiaisonDc(null)).toBeNull()
  })
})
