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
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { evaluerElectrique: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import { ongletParCle } from '../atelier/onglets'
import VerdictElectrique, {
  CLE_ONGLET, DOMAINE_AUTRE, DOMAINES, domaineDuMotif, grouperMotifs,
  libelleStatut, motifsRefusants, statutRefuse, tonStatut,
} from './VerdictElectrique'

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
})
