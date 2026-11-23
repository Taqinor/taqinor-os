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
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(),
      evaluerElectrique: vi.fn(),
      enregistrerEntreeElectrique: vi.fn(),
      importerAffectation: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import AffectationChaines from './AffectationChaines'
import { couleurParModule, marquerModules } from './AffectationChaines.helpers'

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
