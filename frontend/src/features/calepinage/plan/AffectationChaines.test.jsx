/* CAL234 — affecter les chaînes À LA MAIN, avec le verdict en direct.

   Ce qui est prouvé ici :
   1. le GESTE : glisser sur une suite de modules les sélectionne ;
   2. la proposition part sur `evaluer-electrique/` sous
      `entree_electrique.affectation_manuelle` — l'endpoint qui NE PERSISTE
      RIEN — et le refus affiché est le motif SERVEUR, mot pour mot ;
   3. un verdict bloquant INTERDIT l'enregistrement ;
   4. valider poste sur `entree-electrique/`, et la table relue marque la ligne
      « affectation manuelle » ;
   5. relancer l'automatique DEMANDE une confirmation (aucun appel au premier
      clic) ;
   6. ACAL324 — la teinte est CELLE SERVIE par chaque ligne
      (`couleur_chaine` / `couleur_mppt`) : aucune palette locale, aucune
      lecture de source.

   La charge utile du `resultat` vient du contrat COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_resultat.json` (PACT10/13). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(),
      evaluerElectrique: vi.fn(),
      enregistrerEntreeElectrique: vi.fn(),
      importerAffectation: vi.fn(),
      entreeElectrique: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import AffectationChaines, { BarreRaccordement } from './AffectationChaines'
import { couleurParModule, marquerModules } from './AffectationChaines.helpers'
import { PROVENANCE_TRACE_PROPOSE, provenanceCable, useOnduleurSurCarte } from '../electrique/onduleurSurCarte'

const contratResultat = () => reponseContrat('calepinage', 'calepinage_resultat', 'exemple')

/* ACAL8 — les modules sont nommés « <zone.id>#<n> » par le contrat (jamais
   « <pan>#<n> ») : les identifiants viennent de l'échantillon, rien n'est retapé.
   Ordre de l'échantillon : pan PAN-A (A1), pan PAN-B (B1, B2 affectés ; B3 non). */
const [A1, , B1, B2, B3] = contratResultat().data.electrique.affectation
  .map((ligne) => ligne.module)

/** Le même résultat, mais avec les modules donnés marqués « manuelle ». */
const resultatAvecManuelle = (modules, { chaine, mppt, onduleur }) => {
  const reponse = contratResultat()
  const donnees = JSON.parse(JSON.stringify(reponse.data))
  donnees.electrique.affectation = donnees.electrique.affectation.map((ligne) => (
    modules.includes(ligne.module)
      ? { ...ligne, chaine, mppt, onduleur, source: 'affectation manuelle' }
      : ligne
  ))
  return { data: donnees }
}

const VERDICT_CONFORME = {
  verdict: 'conforme', publiable: true, bloquants: [], alertes: [],
  manquantes: [], regle_mppt: null, regle_chaine: null, temperatures: null,
}

const rendre = () => render(
  <MemoryRouter><AffectationChaines calepinageId={1} /></MemoryRouter>,
)

const glisserSur = (modules) => {
  const cases = modules.map((m) => screen.getByTestId(`cal234-module-${m}`))
  fireEvent.pointerDown(cases[0])
  cases.slice(1).forEach((c) => fireEvent.pointerOver(c))
  fireEvent.pointerUp(cases[cases.length - 1])
}

/* ACAL647 — au montage l'écran lit `modules_sous_seuil` par un appel au corps VIDE : les appels qui
   VERDICTENT une proposition sont ceux qui portent `entree_electrique`. */
const appelsProposition = () => calepinageApi.calepinages.evaluerElectrique.mock.calls
  .filter(([, corps]) => corps?.entree_electrique)

const saisir = (code, valeur) => {
  fireEvent.change(screen.getByTestId(`cal234-champ-${code}`), { target: { value: valeur } })
}

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.resultat.mockResolvedValue(contratResultat())
  calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: VERDICT_CONFORME })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AffectationChaines (CAL234) — le geste', () => {
  it('glisser sur une suite de modules les sélectionne', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1, B2, B3])

    expect(screen.getByTestId('cal234-selection'))
      .toHaveTextContent('3 module(s) sélectionné(s).')
    expect(screen.getByTestId(`cal234-module-${B2}`))
      .toHaveAttribute('data-selectionne', 'oui')
  })

  it('la table affichée vient du serveur : chaque module porte sa source', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    const servi = contratResultat().data.electrique.affectation
    servi.forEach((ligne) => {
      expect(screen.getByTestId(`cal234-module-${ligne.module}`))
        .toHaveAttribute('data-source', ligne.source)
    })
  })
})

describe('AffectationChaines (ACAL619) — la tension des chaînes affectées', () => {
  it('une bulle par chaîne affectée, nombres servis ; la chaîne non touchée n’a pas de bulle', async () => {
    const chaines = exempleContrat('calepinage', 'calepinage_evaluation_electrique').chaines
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: { ...VERDICT_CONFORME, chaines } })
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1, B2])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    const bulle = await screen.findByTestId('acal619-bulle')
    expect(bulle).toHaveTextContent('Chaîne 2 : 10 modules — Voc à froid 535 V / 1 000 V, Vmp à chaud 360 V ≥ démarrage 180 V')
    expect(bulle).toHaveAttribute('role', 'status')
    expect(screen.getAllByTestId('acal619-bulle')).toHaveLength(1)
  })
})

describe('AffectationChaines (ACAL631) — importer un plan de chaînes (CSV)', () => {
  const IMPORT = exempleContrat('calepinage', 'calepinage_import_affectation')
  const REFUS = exempleContrat('calepinage', 'calepinage_import_affectation', 'exemple_refus')
  const deposer = (texte) => {
    const fichier = new File([texte], 'chaines.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByTestId('acal631-fichier'), { target: { files: [fichier] } })
  }

  it('ACAL1541 : l’import CSV porte un bouton en français et le nom du fichier choisi', async () => {
    calepinageApi.calepinages.importerAffectation.mockResolvedValue({ data: REFUS })
    rendre()
    await screen.findByTestId('cal234-ecran')

    expect(screen.getByRole('button', { name: 'Choisir un fichier' })).toBeInTheDocument()
    expect(screen.getByTestId('acal631-fichier')).toHaveClass('hidden')
    expect(screen.getByTestId('acal1541-nom')).toHaveTextContent('Aucun fichier choisi')
    deposer('module;chaine;mppt;onduleur')
    await waitFor(() => expect(screen.getByTestId('acal1541-nom')).toHaveTextContent('chaines.csv'))
  })

  it('CSV valide : la proposition est remplie, le verdict relancé, RIEN n’est enregistré', async () => {
    calepinageApi.calepinages.importerAffectation.mockResolvedValue({
      data: { ...IMPORT, lignes: [{ module: B1, chaine: 2, mppt: 2, onduleur: 1 }, { module: B2, chaine: 2, mppt: 2, onduleur: 1 }] },
    })
    rendre()
    await screen.findByTestId('cal234-ecran')

    deposer('module;chaine;mppt;onduleur')

    await waitFor(() => expect(calepinageApi.calepinages.importerAffectation).toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.importerAffectation.mock.calls[0][0]).toBe(1)
    await waitFor(() => expect(appelsProposition()).not.toHaveLength(0))
    const [, corps] = appelsProposition().at(-1)
    expect(corps.entree_electrique.affectation_manuelle.filter((l) => l.chaine === 2)).toHaveLength(2)
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()
  })

  it('CSV fautif : « Ligne 4 : … » sous le champ fichier, aucune proposition', async () => {
    calepinageApi.calepinages.importerAffectation.mockResolvedValue({ data: REFUS })
    rendre()
    await screen.findByTestId('cal234-ecran')

    deposer('module;chaine;mppt;onduleur')

    expect(await screen.findByTestId('acal631-refus')).toHaveTextContent(`Ligne 4 : ${REFUS.refus[0].message}`)
    expect(screen.getByTestId('acal631-fichier')).toHaveAttribute('aria-invalid', 'true')
    expect(appelsProposition()).toHaveLength(0)
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()
  })
})

describe('AffectationChaines (CAL234) — le verdict SERVEUR', () => {
  it('la proposition part sur l’endpoint qui ne persiste rien', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1, B2])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    await waitFor(() => {
      expect(appelsProposition()).not.toHaveLength(0)
    })
    const [idAppele, corps] = appelsProposition().at(-1)
    expect(idAppele).toBe(1)
    expect(corps.entree_electrique.affectation_manuelle).toEqual([
      { module: B1, chaine: 2, mppt: 2, onduleur: 1 },
      { module: B2, chaine: 2, mppt: 2, onduleur: 1 },
    ])
    // Rien n'est enregistré par ce chemin.
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()
  })

  // R3 (visuel lot 7) — numéros stables ≠ rang (pose dont le compteur a grandi) : l'écran renvoie
  // les clés SERVIES telles quelles, jamais un rang recalculé.
  it('modules servis `<pan>#2236…` : la proposition et l’enregistrement portent ces mêmes clés', async () => {
    const donnees = JSON.parse(JSON.stringify(contratResultat().data))
    donnees.electrique.affectation = donnees.electrique.affectation.map((ligne, i) => (
      { ...ligne, module: `${ligne.module.split('#')[0]}#${2236 + i}` }))
    const [, , m1, m2] = donnees.electrique.affectation.map((ligne) => ligne.module)
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: donnees })
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([m1, m2])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))
    await waitFor(() => {
      expect(appelsProposition()).not.toHaveLength(0)
    })
    const attendu = [
      { module: m1, chaine: 2, mppt: 2, onduleur: 1 },
      { module: m2, chaine: 2, mppt: 2, onduleur: 1 },
    ]
    expect(m1).toMatch(/#2238$/)
    expect(appelsProposition().at(-1)[1].entree_electrique.affectation_manuelle).toEqual(attendu)
    await waitFor(() => {
      expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled()
    })
    fireEvent.click(screen.getByTestId('cal234-enregistrer'))
    await waitFor(() => {
      expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled()
    })
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls.at(-1)[1])
      .toEqual({ affectation_manuelle: attendu })
  })

  it('un refus est affiché AVEC le motif du serveur et bloque l’enregistrement', async () => {
    const motif = 'Chaîne 2 (pan PAN-B) : 2 modules, minimum 6 — en deçà, la chaîne '
      + 'ne démarre pas sur la plage MPPT.'
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({
      data: { ...VERDICT_CONFORME, verdict: 'bloquant', publiable: false, bloquants: [motif] },
    })
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1, B2])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    expect(await screen.findByTestId('cal234-bloquant')).toHaveTextContent(motif)
    expect(screen.getByTestId('cal234-enregistrer')).toBeDisabled()
  })

  it('ACAL935 : le résumé dit « À compléter : N points », jamais « indetermine »', async () => {
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({
      data: {
        ...VERDICT_CONFORME,
        verdict: 'indetermine',
        manquantes: ['Onduleur : non désigné.'],
        etat: 'a_completer',
        points: 16,
      },
    })
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1, B2])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    const etat = await screen.findByTestId('cal234-verdict-etat')
    expect(etat).toHaveTextContent('À compléter : 16 points')
    expect(etat).not.toHaveTextContent(/indetermine|conforme/i)
  })

  it('ACAL1535 : verdict conforme et dossier « À compléter : 10 points » ⇒ le résumé dit « À compléter »', async () => {
    calepinageApi.calepinages.evaluerElectrique.mockImplementation((_id, corps) => Promise.resolve({
      data: corps?.entree_electrique
        ? { ...VERDICT_CONFORME, etat: 'pret', points: 0, publication: null }
        : { ...VERDICT_CONFORME, etat: 'a_completer', points: 10, publication: { etat: 'a_completer', points: 10 } },
    }))
    rendre()
    await screen.findByTestId('cal234-ecran')
    glisserSur([B1, B2])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    const etat = await screen.findByTestId('cal234-verdict-etat')
    await waitFor(() => expect(etat).toHaveTextContent('À compléter : 10 points'))
    expect(etat).not.toHaveTextContent(/Prêt/)
  })

  it('un numéro invalide est refusé SOUS le champ fautif, sans appel serveur', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1])
    saisir('chaine', '0')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    expect(screen.getByTestId('cal234-erreur-chaine'))
      .toHaveTextContent('entier strictement positif')
    expect(appelsProposition()).toHaveLength(0)
  })

  it('aucun module sélectionné : l’erreur le dit, rien ne part', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    saisir('chaine', '2')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    expect(screen.getByTestId('cal234-erreur-selection'))
      .toHaveTextContent('Aucun module sélectionné')
    expect(appelsProposition()).toHaveLength(0)
  })
})

describe('AffectationChaines (CAL234) — enregistrer et revenir à l’auto', () => {
  it('valider persiste par entree-electrique et la ligne est relue « affectation manuelle »', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique
      .mockResolvedValue(resultatAvecManuelle([B1], { chaine: 2, mppt: 2, onduleur: 1 }))
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))
    await waitFor(() => {
      expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled()
    })

    fireEvent.click(screen.getByTestId('cal234-enregistrer'))

    expect(await screen.findByTestId('cal234-enregistre'))
      .toHaveTextContent('Affectation manuelle enregistrée.')
    const [, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls.at(-1)
    expect(corps).toEqual({
      affectation_manuelle: [{ module: B1, chaine: 2, mppt: 2, onduleur: 1 }],
    })
    expect(screen.getByTestId(`cal234-module-${B1}`))
      .toHaveAttribute('data-source', 'affectation manuelle')
  })

  it('relancer l’auto n’écrase rien sans confirmation explicite', async () => {
    calepinageApi.calepinages.resultat
      .mockResolvedValue(resultatAvecManuelle([B1], { chaine: 2, mppt: 2, onduleur: 1 }))
    calepinageApi.calepinages.enregistrerEntreeElectrique
      .mockResolvedValue(contratResultat())
    rendre()
    await screen.findByTestId('cal234-ecran')

    // Premier clic : il ARME, il n'appelle rien.
    fireEvent.click(screen.getByTestId('cal234-relancer-auto'))
    expect(screen.getByTestId('cal234-confirmation-auto')).toBeInTheDocument()
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()

    // Second clic : il exécute, en effaçant l'affectation manuelle.
    fireEvent.click(screen.getByTestId('cal234-relancer-auto'))
    await waitFor(() => {
      expect(calepinageApi.calepinages.enregistrerEntreeElectrique)
        .toHaveBeenCalledWith(1, { affectation_manuelle: [] })
    })
    expect(await screen.findByTestId('cal234-enregistre'))
      .toHaveTextContent('Affectation automatique rétablie.')
  })

  it('un refus 400 du serveur est rendu sous le champ qu’il nomme', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { data: { affectation_manuelle: `Le module « ${B1} » est affecté deux fois.` } },
    })
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur([B1])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))
    await waitFor(() => {
      expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled()
    })
    fireEvent.click(screen.getByTestId('cal234-enregistrer'))

    expect(await screen.findByTestId('cal234-erreur-affectation'))
      .toHaveTextContent('affecté deux fois')
  })

  it('erreur réseau au chargement : message français, aucune grille inventée', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('boum'))
    rendre()

    expect(await screen.findByTestId('cal234-erreur'))
      .toHaveTextContent('Affectation indisponible.')
  })
})

describe('AffectationChaines (ACAL324) — la teinte est celle SERVIE', () => {
  /** La table du contrat, une seule couleur changée sur la seule ligne visée. */
  const tableServie = () => {
    const lignes = JSON.parse(JSON.stringify(
      contratResultat().data.electrique.affectation))
    const premiere = lignes.find((ligne) => ligne.chaine != null)
    for (const ligne of lignes) {
      if (ligne.chaine === premiere.chaine) {
        ligne.couleur_chaine = 'rgb(1, 2, 3)'
        ligne.couleur_mppt = 'rgb(4, 5, 6)'
      }
    }
    return { lignes, premiere }
  }

  it("la pastille d'un groupe prend la couleur servie par sa ligne", () => {
    const { lignes, premiere } = tableServie()
    const chaine = couleurParModule(lignes, 'chaine')
    expect(chaine.couleurs.get(premiere.module)).toBe('rgb(1, 2, 3)')
    expect(chaine.legende[0].couleur).toBe('rgb(1, 2, 3)')
    const mppt = couleurParModule(lignes, 'mppt')
    expect(mppt.couleurs.get(premiere.module)).toBe('rgb(4, 5, 6)')
  })

  it('un module non affecté garde le GRIS servi et est compté en dernier', () => {
    const lignes = contratResultat().data.electrique.affectation
    const libre = lignes.find((ligne) => ligne.chaine == null)
    const { couleurs, legende } = couleurParModule(lignes, 'chaine')
    expect(couleurs.get(libre.module)).toBe(libre.couleur_chaine)
    expect(legende.at(-1)).toMatchObject({ libelle: 'Non affecté', nombre: 1 })
  })
})

/* ── CALX53 — l'avertissement « coefficients non sourcés », À CÔTÉ DES BORNES
   L'échantillon committé sert `avertissements: []` (rien à signaler). On part
   de LUI et on y pose le message que le serveur publie quand la fiche module
   ne donne pas ses coefficients de température : seule cette clé bouge. */
const AVERTISSEMENT_COEFFS = (
  'Coefficients de température NON SOURCÉS sur la fiche de Module d essai '
  + '710 Wc (« temp_coeff_voc_pct_c » — coefficient de la tension à vide '
  + '(β Voc) : -0,270 %/°C, « temp_coeff_pmax_pct_c » — coefficient de la '
  + 'puissance crête (γ Pmax) : -0,350 %/°C). Ces valeurs sont les défauts du '
  + 'noyau, pas des données constructeur : les bornes de tension de chaîne '
  + 'restent calculées, mais elles sont marquées tant que la fiche produit ne '
  + 'publie pas ces coefficients.'
)

const resultatAvecAvertissement = () => {
  const reponse = contratResultat()
  return {
    ...reponse,
    data: { ...reponse.data, avertissements: [AVERTISSEMENT_COEFFS] },
  }
}

describe('AffectationChaines (CALX53) — coefficients non sourcés', () => {
  it('aucun avertissement servi : le panneau n’en invente aucun', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    expect(contratResultat().data.avertissements).toEqual([])
    expect(screen.queryByTestId('calx53-avertissements')).toBeNull()
  })

  it('l’avertissement du serveur est visible, et NOMME les deux coefficients', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(resultatAvecAvertissement())
    rendre()
    await screen.findByTestId('cal234-ecran')

    const avertissement = screen.getByTestId('calx53-avertissement')
    expect(avertissement).toHaveTextContent('temp_coeff_voc_pct_c')
    expect(avertissement).toHaveTextContent('temp_coeff_pmax_pct_c')
    // Il est rendu AVANT la grille des modules (donc au-dessus des bornes).
    const grille = screen.getByTestId('cal234-pan-PAN-A')
    // `compareDocumentPosition` rend un MASQUE de bits : on teste le bit.
    const apres = avertissement.compareDocumentPosition(grille)
      & Node.DOCUMENT_POSITION_FOLLOWING
    expect(apres).toBeTruthy()
    // Les bornes restent servies : rien n'est omis à cause du défaut.
    expect(screen.getByTestId(`cal234-module-${A1}`)).toBeInTheDocument()
  })
})

describe('AffectationChaines (ACAL1662) — l’avertissement « aucune norme » dit une fois', () => {
  it('trois fois le même motif servi : une phrase courte avec son lien, le détail replié, rien en double', async () => {
    const motif = "Aucune norme électrique n'est choisie : les câbles et les protections ne sont pas calculés. "
      + 'Choisissez une norme dans les réglages du calepinage de votre société pour les calculer.'
    const donnees = JSON.parse(JSON.stringify(contratResultat().data))
    donnees.avertissements = [motif, motif, motif, 'Autre phrase servie.']
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    rendre()
    await screen.findByTestId('cal234-ecran')

    expect(screen.getAllByTestId('acal1662-norme')).toHaveLength(1)
    const bloc = screen.getByTestId('acal1662-norme')
    expect(bloc).toHaveTextContent('Choisissez la norme électrique dans les réglages')
    expect(bloc.querySelector('a')).toHaveAttribute('href', '/calepinage/reglages')
    expect(bloc.tagName).toBe('DETAILS')
    expect(bloc.open).toBe(false)
    expect(screen.getAllByTestId('calx53-avertissement')).toHaveLength(2) // le détail replié + l'autre phrase
  })
})

/* ── CALX16 — LA CHAÎNE LA PLUS FAIBLE EN OMBRAGE ──────────────────────────
   Ce qui est prouvé : la chaîne DÉSIGNÉE par le serveur est teintée, sa
   méthode est recopiée, la légende dit que c'est un signal de CÂBLAGE et
   non une perte d'énergie, et — la garantie qui compte autant — un résultat
   SANS la clé (document sans accès solaire par module) ne teinte rien et
   n'affiche rien : l'écran n'invente aucun 100 %. */

const sansChaineFaible = () => {
  const reponse = contratResultat()
  const donnees = JSON.parse(JSON.stringify(reponse.data))
  delete donnees.electrique.chaine_la_plus_faible
  return { data: donnees }
}

describe('AffectationChaines (CALX16) — la chaîne la plus faible', () => {
  it('teinte la chaîne désignée et recopie la méthode du serveur', async () => {
    const designee = contratResultat().data.electrique.chaine_la_plus_faible
    rendre()
    await screen.findByTestId('cal234-ecran')

    expect(screen.getByTestId('calx16-chaine'))
      .toHaveTextContent(`chaîne ${designee.chaine}`)
    expect(screen.getByTestId('calx16-chaine')).toHaveTextContent(designee.pan)
    expect(screen.getByTestId('calx16-module')).toHaveTextContent(designee.module)
    expect(screen.getByTestId('calx16-methode')).toHaveTextContent(designee.methode)
    // Le module de la chaîne désignée porte le repère ; un module d'un autre
    // pan ne le porte pas.
    expect(screen.getByTestId(`cal234-module-${designee.module}`))
      .toHaveAttribute('data-chaine-faible', 'oui')
    expect(screen.getByTestId(`cal234-module-${A1}`))
      .toHaveAttribute('data-chaine-faible', 'non')
  })

  it('la légende dit que c’est un signal de câblage, pas une perte', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    const legende = screen.getByTestId('calx16-legende')
    expect(legende).toHaveTextContent('Signal de câblage')
    expect(legende).toHaveTextContent('pas une perte')
    expect(legende).toHaveTextContent('aucun kWh')
  })

  it('sans la clé servie, rien n’est teinté et rien n’est affiché', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(sansChaineFaible())
    rendre()
    await screen.findByTestId('cal234-ecran')

    expect(screen.queryByTestId('calx16-chaine-faible')).toBeNull()
    expect(screen.getByTestId(`cal234-module-${B1}`))
      .toHaveAttribute('data-chaine-faible', 'non')
  })
})

describe('AffectationChaines (ACAL725) — le drapeau « optimiseur » par module', () => {
  // Contrat ACAL733 : `affectation_manuelle[].optimiseur` vrai, faux, ou absent.
  const contratOptimiseur = () => exempleContrat(
    'calepinage', 'calepinage_entree_electrique', 'exemple_affectation_optimiseur').affectation_manuelle

  const affecter = (modules, choix) => {
    glisserSur(modules)
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.change(screen.getByTestId('cal234-champ-optimiseur'), { target: { value: choix } })
    fireEvent.click(screen.getByTestId('cal234-affecter'))
  }
  const corpsEnregistre = async () => {
    await waitFor(() => expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled())
    fireEvent.click(screen.getByTestId('cal234-enregistrer'))
    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    return calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls.at(-1)[1]
  }

  it('trois modules marqués « oui » : le corps envoyé porte `optimiseur: true` exactement sur eux', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(contratResultat())
    rendre()
    await screen.findByTestId('cal234-ecran')
    affecter([B1, B2, B3], 'oui')
    const corps = await corpsEnregistre()
    expect(corps.affectation_manuelle).toEqual([B1, B2, B3].map((module) => (
      { module, chaine: 2, mppt: 2, onduleur: 1, optimiseur: true })))
  })

  it('« non » envoie `false` ; « inchangé » sur un module sans drapeau n’envoie AUCUNE clé', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(contratResultat())
    rendre()
    await screen.findByTestId('cal234-ecran')
    affecter([B1], 'non')
    affecter([B2], 'inchange')
    const corps = await corpsEnregistre()
    const parModule = Object.fromEntries(corps.affectation_manuelle.map((l) => [l.module, l]))
    expect(parModule[B1].optimiseur).toBe(false)
    expect('optimiseur' in parModule[B2]).toBe(false)
  })

  it('le serveur renvoyant le drapeau : le module s’affiche marqué (liseré, « optimiseur »), et le drapeau repart', async () => {
    const [marque, demarque] = contratOptimiseur()
    const reponse = contratResultat()
    const donnees = JSON.parse(JSON.stringify(reponse.data))
    donnees.electrique.affectation = donnees.electrique.affectation.map((ligne) => (
      [B1, B2].includes(ligne.module)
        ? { ...ligne, chaine: 2, mppt: 2, onduleur: 1, source: 'affectation manuelle',
          optimiseur: ligne.module === B1 ? marque.optimiseur : demarque.optimiseur }
        : ligne))
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: donnees })
    rendre()
    const module = await screen.findByTestId(`cal234-module-${B1}`)
    expect(module).toHaveAttribute('data-optimiseur', 'oui')
    expect(module).toHaveAttribute('aria-label', expect.stringContaining('optimiseur'))
    expect(module.getAttribute('title')).toContain('optimiseur')
    expect(module.className).toContain('border-solid')
    expect(screen.getByTestId(`cal234-module-${B2}`)).toHaveAttribute('data-optimiseur', 'non')

    affecter([B3], 'inchange') // une édition ailleurs : les drapeaux enregistrés repartent tels quels
    const corps = await corpsEnregistre()
    const parModule = Object.fromEntries(corps.affectation_manuelle.map((l) => [l.module, l]))
    expect(parModule[B1].optimiseur).toBe(true)
    expect(parModule[B2].optimiseur).toBe(false)
  })

  it('ACAL1642 : Optimiseur = Oui seul (numéros vides) marque les modules, garde leur chaîne, active l’enregistrement', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(contratResultat())
    rendre()
    await screen.findByTestId('cal234-ecran')
    const avant = Object.fromEntries(contratResultat().data.electrique.affectation.map((l) => [l.module, l]))
    glisserSur([B1, B2, B3])
    fireEvent.change(screen.getByTestId('cal234-champ-optimiseur'), { target: { value: 'oui' } })
    fireEvent.click(screen.getByTestId('cal234-affecter'))
    for (const m of [B1, B2, B3]) {
      expect(screen.getByTestId(`cal234-module-${m}`)).toHaveAttribute('data-optimiseur', 'oui')
    }
    const corps = await corpsEnregistre()
    const parModule = Object.fromEntries(corps.affectation_manuelle.map((l) => [l.module, l]))
    for (const m of [B1, B2, B3]) {
      expect(parModule[m].optimiseur).toBe(true)
      expect(parModule[m].chaine).toBe(avant[m].chaine ?? null)
      expect(parModule[m].mppt).toBe(avant[m].mppt ?? null)
    }
  })

  it('ACAL1642 : le drapeau seul écrit la table COMPLÈTE — un contrôle qui compte par chaîne ne bloque pas', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(contratResultat())
    // Se comporte comme le serveur : la longueur d'une chaîne est comptée sur les lignes IMPOSÉES seules (minimum 2 ici).
    calepinageApi.calepinages.evaluerElectrique.mockImplementation(async (_id, corps) => {
      const imposees = corps?.entree_electrique?.affectation_manuelle
      if (!imposees) return { data: VERDICT_CONFORME }
      const parChaine = {}
      imposees.forEach((l) => { if (l.chaine != null) parChaine[l.chaine] = (parChaine[l.chaine] || 0) + 1 })
      const courtes = Object.entries(parChaine).filter(([, n]) => n < 2)
      return { data: courtes.length
        ? { ...VERDICT_CONFORME, verdict: 'bloquant', publiable: false,
          bloquants: courtes.map(([c, n]) => `Chaîne ${c} : ${n} module, minimum 2.`) }
        : VERDICT_CONFORME }
    })
    rendre()
    await screen.findByTestId('cal234-ecran')
    glisserSur([B1])
    fireEvent.change(screen.getByTestId('cal234-champ-optimiseur'), { target: { value: 'oui' } })
    fireEvent.click(screen.getByTestId('cal234-affecter'))
    await waitFor(() => expect(appelsProposition().length).toBeGreaterThan(0))
    const dernier = appelsProposition().at(-1)[1].entree_electrique.affectation_manuelle
    expect(dernier.length).toBeGreaterThan(1) // la table complète, pas la seule ligne marquée
    await waitFor(() => expect(screen.queryByTestId('cal234-verdict-en-cours')).toBeNull())
    await waitFor(() => expect(screen.getByTestId('cal234-enregistrer')).not.toBeDisabled())
    expect(screen.queryByText(/minimum 2/)).toBeNull()
    const corps = await corpsEnregistre()
    expect(corps.affectation_manuelle.length).toBeGreaterThan(1)
    expect(corps.affectation_manuelle.find((l) => l.module === B1).optimiseur).toBe(true)
  })

  it('ACAL1642 : numéros à moitié saisis — l’erreur nomme le champ vide, rien n’est écrit à null', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')
    glisserSur([B1])
    saisir('chaine', '2')
    fireEvent.click(screen.getByTestId('cal234-affecter'))
    expect(screen.getByTestId('cal234-erreur-mppt')).toHaveTextContent('Renseignez aussi ce numéro')
    expect(screen.getByTestId('cal234-erreur-onduleur')).toBeInTheDocument()
    expect(screen.queryByTestId('cal234-erreur-chaine')).toBeNull()
    expect(screen.getByTestId('cal234-enregistrer')).toBeDisabled() // aucune édition posée
  })

  it('`marquerModules` marque une liste de six modules d’un seul geste', () => {
    const six = ['P#1', 'P#2', 'P#3', 'P#4', 'P#5', 'P#6'].map((module, i) => (
      { module, chaine: 1, mppt: 1, onduleur: 1, cx: i }))
    const marques = marquerModules(six, true)
    expect(marques).toHaveLength(6)
    expect(marques.every((l) => l.optimiseur === true)).toBe(true)
    expect(marques[0]).toEqual({ module: 'P#1', chaine: 1, mppt: 1, onduleur: 1, optimiseur: true })
    expect(marquerModules(six, undefined).some((l) => 'optimiseur' in l)).toBe(false)
  })
})

describe('BarreRaccordement (ACAL1536) — dire pourquoi rien n’est raccordé', () => {
  it('module non désigné ⇒ une phrase de cause au lieu du silence', async () => {
    const vide = contratResultat()
    vide.data.electrique.affectation = []
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(vide)
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({
      data: exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide'),
    })
    render(<BarreRaccordement calepinageId={1} onRaccorde={() => {}} onModifier={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Raccorder automatiquement' }))
    expect(await screen.findByText(/Choisissez d’abord le module de ce toit/)).toBeInTheDocument()
  })

  it('R5C-N3 — chaînes formées mais verdict refusé : la phrase servie (le courant des panneaux), jamais « borne de fiche »', async () => {
    const resultat = contratResultat()
    resultat.data.electrique.verdicts = [{
      code: 'courant_par_entree_mppt', libelle: 'Courant par entrée MPPT sous le courant admissible',
      conforme: false, bloquant: false, detail: '17,6 A au-dessus de la borne de fiche 13,5 A',
      raison: 'le courant des panneaux (17,6 A) dépasse ce qu’une entrée de cet onduleur accepte (13,5 A)',
    }]
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(resultat)
    render(<BarreRaccordement calepinageId={1} onRaccorde={() => {}} onModifier={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Raccorder automatiquement' }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('le courant des panneaux (17,6 A) dépasse ce qu’une entrée de cet onduleur accepte (13,5 A)')
    expect(alerte).not.toHaveTextContent('borne de fiche')
  })

  it('des chaînes apparaissent ⇒ aucune phrase de cause', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(contratResultat())
    const onRaccorde = vi.fn()
    render(<BarreRaccordement calepinageId={1} onRaccorde={onRaccorde} onModifier={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Raccorder automatiquement' }))
    await waitFor(() => expect(onRaccorde).toHaveBeenCalled())
    expect(screen.queryByText(/Choisissez d’abord/)).toBeNull()
    expect(calepinageApi.calepinages.entreeElectrique).not.toHaveBeenCalled()
  })
})

describe('AffectationChaines (ACAL647) — modules ombrés proposés pour un optimiseur', () => {
  const lire = (module) => contratResultat().data.electrique.affectation.find((l) => l.module === module)

  it('sans seuil (liste vide servie) aucune proposition n’apparaît', async () => {
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({
      data: { ...VERDICT_CONFORME, modules_sous_seuil: [] },
    })
    rendre()
    await screen.findByTestId('cal234-ecran')
    await waitFor(() => expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalledWith(1, {}))

    expect(screen.queryByTestId('acal647-proposition')).toBeNull()
  })

  it('seuil saisi : la phrase du nombre servi, puis « Les équiper » marque ces modules et garde leurs numéros', async () => {
    const proposes = [A1, B1, B3]
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({
      data: { ...VERDICT_CONFORME, modules_sous_seuil: proposes },
    })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue(contratResultat())
    rendre()
    await screen.findByTestId('cal234-ecran')

    expect(await screen.findByTestId('acal647-phrase'))
      .toHaveTextContent('3 modules ombrés pourraient recevoir un optimiseur')
    fireEvent.click(screen.getByTestId('acal647-equiper'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
    const [idAppele, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(idAppele).toBe(1)
    const parModule = Object.fromEntries(corps.affectation_manuelle.map((l) => [l.module, l]))
    // ACAL1509 — l'affectation écrite garde TOUS les modules et leurs chaînes ; seuls les proposés sont marqués.
    const tous = contratResultat().data.electrique.affectation
    expect(Object.keys(parModule).sort()).toEqual(tous.map((l) => l.module).sort())
    tous.filter((l) => !proposes.includes(l.module)).forEach((l) => {
      expect(parModule[l.module].chaine).toBe(l.chaine)
      expect(parModule[l.module].optimiseur).not.toBe(true)
    })
    proposes.forEach((module) => {
      const servi = lire(module)
      expect(parModule[module]).toEqual({
        module, chaine: servi.chaine, mppt: servi.mppt, onduleur: servi.onduleur, optimiseur: true,
      })
    })
  })
})

/* ACAL1317 (D-ACAL-70) — placer / déplacer / retirer l'onduleur depuis la barre de l'étape Électrique. La couche
   électrique de la scène (`electrique3d.ts`, prouvée par ses propres tests) est remplacée par une couche d'essai qui
   tient le même document et prévient l'écran comme elle (`ecouter`) ; la barre et le crochet sont les VRAIS. */
function coucheEssai(equipements = []) {
  const doc = { equipements: equipements.map((e) => ({ ...e })), cheminements: [] }
  const ecouteurs = new Set()
  let pose = null
  let vise = null
  const prevenir = () => ecouteurs.forEach((f) => f())
  const couche = {
    pasDeplacementM: 0.25,
    documentElectrique: () => doc,
    typeArme: () => pose,
    deplacementArme: () => vise,
    dernierRefus: () => null,
    armerPose: vi.fn((type) => { pose = type; vise = null; return true }),
    armerDeplacement: vi.fn((id) => { vise = id; pose = null; return true }),
    pousser: vi.fn(() => ({ ok: true, traces: ['ch1'], refusTrace: null })),
    retirerAvecTraces: vi.fn((id) => {
      doc.equipements = doc.equipements.filter((e) => e.id !== id)
      prevenir()
      return { ok: true, tracesGardees: [] }
    }),
    etatTraces: vi.fn(() => ({ proposes: ['ch1'], autres: [], decales: [], pansSansTrace: [] })),
    ecouter: (f) => { ecouteurs.add(f); return () => ecouteurs.delete(f) },
    /** Le toucher de la carte (le constructeur appelle `clicCarte`) : pose ou déplace l'organe armé. */
    toucher: () => {
      if (vise) {
        vise = null
      } else if (pose) {
        doc.equipements.push({ id: `eq${doc.equipements.length + 1}`, type: 'onduleur', label: 'Onduleur', lng: 0, lat: 0 })
        pose = null
      }
      prevenir()
    },
  }
  return couche
}
const ONDULEUR = { id: 'eqA', type: 'onduleur', label: 'Onduleur 1', lng: -7.6, lat: 33.5, source: 'saisie' }
function BarreAvecOnduleur({ couche, lectureSeule = false, nombreAttendu = 1 }) {
  const onduleur = useOnduleurSurCarte({ builderApi: couche ? { electrique: couche } : null, nombreAttendu })
  return <BarreRaccordement calepinageId={1} onRaccorde={() => {}} onModifier={() => {}} lectureSeule={lectureSeule} onduleur={onduleur} />
}
const GESTES_ECRITS = ['armerPose', 'armerDeplacement', 'pousser', 'retirerAvecTraces']

describe('BarreRaccordement (ACAL1317) — l’onduleur se place, se déplace et se retire sur la carte', () => {
  it('sans constructeur, la barre reste celle d’avant (aucun geste d’onduleur proposé)', () => {
    render(<BarreAvecOnduleur couche={null} />)
    expect(screen.queryByTestId('cal-elec-onduleur-placer')).toBeNull()
    expect(screen.getByRole('button', { name: 'Raccorder automatiquement' })).toBeInTheDocument()
  })

  it('aucun onduleur posé : « Placer l’onduleur » arme la pose avec suivi du tracé ; le toucher de la carte le pose', () => {
    const couche = coucheEssai()
    render(<BarreAvecOnduleur couche={couche} />)
    fireEvent.click(screen.getByRole('button', { name: 'Placer l’onduleur' }))
    expect(couche.armerPose).toHaveBeenCalledWith('onduleur', { suivreTrace: true })
    expect(screen.getByTestId('cal-elec-onduleur-message')).toHaveTextContent('Touchez la carte à l’endroit de l’onduleur.')
    act(() => couche.toucher())
    expect(screen.getByTestId('cal-elec-onduleur-message')).toHaveTextContent('Onduleur placé : le tracé du câble a suivi.')
    // Un onduleur attendu : la barre n'en pose pas un second, elle propose de le déplacer ou de le retirer.
    expect(screen.queryByTestId('cal-elec-onduleur-placer')).toBeNull()
    expect(screen.getByRole('button', { name: 'Déplacer l’onduleur' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retirer l’onduleur' })).toBeInTheDocument()
  })

  it('« Déplacer l’onduleur » arme le déplacement ; flèches du clavier et boutons fléchés poussent d’un pas de la couche', () => {
    const couche = coucheEssai([ONDULEUR])
    render(<BarreAvecOnduleur couche={couche} />)
    fireEvent.click(screen.getByRole('button', { name: 'Déplacer l’onduleur' }))
    expect(couche.armerDeplacement).toHaveBeenCalledWith('eqA')
    const fleches = screen.getByTestId('cal-elec-onduleur-fleches')
    expect(screen.getByRole('button', { name: 'Pousser l’onduleur vers le nord' })).toHaveFocus()
    fireEvent.keyDown(fleches, { key: 'ArrowUp' })
    expect(couche.pousser).toHaveBeenLastCalledWith('eqA', 0, 0.25)
    fireEvent.click(screen.getByRole('button', { name: 'Pousser l’onduleur vers l’est' }))
    expect(couche.pousser).toHaveBeenLastCalledWith('eqA', 0.25, 0)
    act(() => couche.toucher())
    expect(screen.getByTestId('cal-elec-onduleur-message')).toHaveTextContent('Onduleur déplacé : le tracé du câble a suivi.')
    expect(screen.queryByTestId('cal-elec-onduleur-fleches')).toBeNull()
  })

  it('« Retirer l’onduleur » le retire avec son tracé proposé, en un geste', () => {
    const couche = coucheEssai([ONDULEUR])
    render(<BarreAvecOnduleur couche={couche} />)
    fireEvent.click(screen.getByRole('button', { name: 'Retirer l’onduleur' }))
    expect(couche.retirerAvecTraces).toHaveBeenCalledWith('eqA')
    expect(screen.getByTestId('cal-elec-onduleur-message')).toHaveTextContent('Onduleur retiré du plan.')
    expect(screen.getByRole('button', { name: 'Placer l’onduleur' })).toBeInTheDocument()
  })

  it('plusieurs onduleurs au document : les gestes visent celui CHOISI', () => {
    const couche = coucheEssai([ONDULEUR, { ...ONDULEUR, id: 'eqB', label: 'Onduleur 2' }])
    render(<BarreAvecOnduleur couche={couche} nombreAttendu={2} />)
    fireEvent.change(screen.getByTestId('cal-elec-onduleur-choix'), { target: { value: 'eqB' } })
    fireEvent.click(screen.getByRole('button', { name: 'Déplacer l’onduleur' }))
    expect(couche.armerDeplacement).toHaveBeenCalledWith('eqB')
    expect(screen.queryByTestId('cal-elec-onduleur-placer')).toBeNull() // deux attendus, deux posés
  })

  it('lecture seule : chaque geste est désactivé avec le motif, et rien n’est écrit', () => {
    const couche = coucheEssai([ONDULEUR])
    render(<BarreAvecOnduleur couche={couche} lectureSeule />)
    for (const nom of ['Déplacer l’onduleur', 'Retirer l’onduleur']) {
      const bouton = screen.getByRole('button', { name: nom })
      expect(bouton).toBeDisabled()
      expect(bouton).toHaveAttribute('title', expect.stringContaining('Conception figée'))
      fireEvent.click(bouton)
    }
    for (const geste of GESTES_ECRITS) expect(couche[geste]).not.toHaveBeenCalled()
  })

  it('sans geste, l’écran n’écrit rien dans le document (il ne fait que le lire)', () => {
    const couche = coucheEssai([ONDULEUR])
    const avant = JSON.stringify(couche.documentElectrique())
    render(<BarreAvecOnduleur couche={couche} />)
    for (const geste of GESTES_ECRITS) expect(couche[geste]).not.toHaveBeenCalled()
    expect(JSON.stringify(couche.documentElectrique())).toBe(avant)
  })
})

describe('provenanceCable (ACAL1317) — d’où vient la longueur sous « Câble côté panneaux »', () => {
  it('tracé proposé seul ⇒ la position de l’onduleur ; à mesurer tant que rien n’est enregistré', () => {
    const etat = { proposes: ['ch1'], autres: [], decales: [], pansSansTrace: [] }
    expect(provenanceCable(etat, false)).toBe(PROVENANCE_TRACE_PROPOSE)
    expect(provenanceCable(etat, true)).toBe(`${PROVENANCE_TRACE_PROPOSE} — longueur mesurée à l’enregistrement`)
  })
  it('tracé non reconnu décalé ⇒ il le dit SANS dire qui l’a tracé ; non reconnu qui aboutit, ou aucun onduleur ⇒ rien', () => {
    expect(provenanceCable({ proposes: [], autres: ['ch1'], decales: ['ch1'], pansSansTrace: [] }, false)).toBe('tracé enregistré — n’aboutit plus à l’onduleur')
    expect(provenanceCable({ proposes: [], autres: ['ch1'], decales: [], pansSansTrace: [] }, false)).toBeNull()
    expect(provenanceCable(null, true)).toBeNull()
  })
  it('un pan à modules sans tracé vers l’onduleur ⇒ « tracé partiel », jamais la provenance complète', () => {
    expect(provenanceCable({ proposes: ['ch1'], autres: [], decales: [], pansSansTrace: ['z2'] }, false)).toBe('tracé partiel : 1 pan sans tracé vers l’onduleur')
  })
})
