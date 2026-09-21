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
   6. la teinte est EXACTEMENT celle de CAL126 (`scene3d.ts`) — lue dans le
      source TypeScript, jamais recopiée de tête.

   La charge utile du `resultat` vient du contrat COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_resultat.json` (PACT10/13). */
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { fichierContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(),
      evaluerElectrique: vi.fn(),
      enregistrerEntreeElectrique: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import AffectationChaines, {
  AFFECTATION_PALETTE, AFFECTATION_UNASSIGNED, couleurParModule,
} from './AffectationChaines'

const contratResultat = () => reponseContrat('calepinage', 'calepinage_resultat', 'exemple')

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

    glisserSur(['PAN-B#1', 'PAN-B#2', 'PAN-B#3'])

    expect(screen.getByTestId('cal234-selection'))
      .toHaveTextContent('3 module(s) sélectionné(s).')
    expect(screen.getByTestId('cal234-module-PAN-B#2'))
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

describe('AffectationChaines (CAL234) — le verdict SERVEUR', () => {
  it('la proposition part sur l’endpoint qui ne persiste rien', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur(['PAN-B#1', 'PAN-B#2'])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    await waitFor(() => {
      expect(calepinageApi.calepinages.evaluerElectrique).toHaveBeenCalled()
    })
    const [idAppele, corps] = calepinageApi.calepinages.evaluerElectrique.mock.calls.at(-1)
    expect(idAppele).toBe(1)
    expect(corps.entree_electrique.affectation_manuelle).toEqual([
      { module: 'PAN-B#1', chaine: 2, mppt: 2, onduleur: 1 },
      { module: 'PAN-B#2', chaine: 2, mppt: 2, onduleur: 1 },
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

    glisserSur(['PAN-B#1', 'PAN-B#2'])
    saisir('chaine', '2')
    saisir('mppt', '2')
    saisir('onduleur', '1')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    expect(await screen.findByTestId('cal234-bloquant')).toHaveTextContent(motif)
    expect(screen.getByTestId('cal234-enregistrer')).toBeDisabled()
  })

  it('un numéro invalide est refusé SOUS le champ fautif, sans appel serveur', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur(['PAN-B#1'])
    saisir('chaine', '0')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    expect(screen.getByTestId('cal234-erreur-chaine'))
      .toHaveTextContent('entier strictement positif')
    expect(calepinageApi.calepinages.evaluerElectrique).not.toHaveBeenCalled()
  })

  it('aucun module sélectionné : l’erreur le dit, rien ne part', async () => {
    rendre()
    await screen.findByTestId('cal234-ecran')

    saisir('chaine', '2')
    fireEvent.click(screen.getByTestId('cal234-affecter'))

    expect(screen.getByTestId('cal234-erreur-selection'))
      .toHaveTextContent('Aucun module sélectionné')
    expect(calepinageApi.calepinages.evaluerElectrique).not.toHaveBeenCalled()
  })
})

describe('AffectationChaines (CAL234) — enregistrer et revenir à l’auto', () => {
  it('valider persiste par entree-electrique et la ligne est relue « affectation manuelle »', async () => {
    calepinageApi.calepinages.enregistrerEntreeElectrique
      .mockResolvedValue(resultatAvecManuelle(['PAN-B#1'], { chaine: 2, mppt: 2, onduleur: 1 }))
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur(['PAN-B#1'])
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
      affectation_manuelle: [{ module: 'PAN-B#1', chaine: 2, mppt: 2, onduleur: 1 }],
    })
    expect(screen.getByTestId('cal234-module-PAN-B#1'))
      .toHaveAttribute('data-source', 'affectation manuelle')
  })

  it('relancer l’auto n’écrase rien sans confirmation explicite', async () => {
    calepinageApi.calepinages.resultat
      .mockResolvedValue(resultatAvecManuelle(['PAN-B#1'], { chaine: 2, mppt: 2, onduleur: 1 }))
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
      response: { data: { affectation_manuelle: 'Le module « PAN-B#1 » est affecté deux fois.' } },
    })
    rendre()
    await screen.findByTestId('cal234-ecran')

    glisserSur(['PAN-B#1'])
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

describe('AffectationChaines (CAL234) — la teinte est celle de CAL126', () => {
  /** Les couleurs 0-1 déclarées dans `scene3d.ts`, lues dans le SOURCE. */
  const paletteScene3d = () => {
    // La racine du dépôt est déduite du chemin d'un contrat committé : le
    // helper partagé n'a pas à être modifié pour ce seul test.
    const racine = resolve(
      dirname(fichierContrat('calepinage', 'calepinage_resultat')),
      '..', '..', '..', '..', '..',
    )
    const source = readFileSync(
      join(racine, 'apps', 'web', 'src', 'scripts', 'roofPro11', 'scene3d.ts'),
      'utf8',
    )
    const bloc = source.split('AFFECTATION_PALETTE: readonly Rgb01[] = [')[1].split('];')[0]
    const palette = [...bloc.matchAll(/r:\s*([\d.]+),\s*g:\s*([\d.]+),\s*b:\s*([\d.]+)/g)]
      .map((m) => m.slice(1, 4).map(Number))
    const gris = source
      .split('AFFECTATION_UNASSIGNED: Rgb01 = {')[1].split('}')[0]
      .match(/r:\s*([\d.]+),\s*g:\s*([\d.]+),\s*b:\s*([\d.]+)/)
      .slice(1, 4).map(Number)
    return { palette, gris }
  }

  const enRgb = ([r, g, b]) => `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`

  it('la palette de cet écran est EXACTEMENT celle de la 3D', () => {
    const { palette, gris } = paletteScene3d()
    expect(palette.length).toBe(AFFECTATION_PALETTE.length)
    expect(palette.map(enRgb)).toEqual([...AFFECTATION_PALETTE])
    expect(enRgb(gris)).toBe(AFFECTATION_UNASSIGNED)
  })

  it('un module non affecté est GRIS et compté dans la légende', () => {
    const lignes = contratResultat().data.electrique.affectation
    const { couleurs, legende } = couleurParModule(lignes, 'chaine')
    expect(couleurs.get('PAN-B#3')).toBe(AFFECTATION_UNASSIGNED)
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
    expect(screen.getByTestId('cal234-module-PAN-A#1')).toBeInTheDocument()
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
    expect(screen.getByTestId('cal234-module-PAN-A#1'))
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
    expect(screen.getByTestId('cal234-module-PAN-B#1'))
      .toHaveAttribute('data-chaine-faible', 'non')
  })
})
