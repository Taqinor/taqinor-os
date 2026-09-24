/* CALX17 — le panneau « Masse & lestage » de l'atelier.

   Tout ce qui est affirmé ici l'est sur l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_masse_lestage.json` (PACT10/13,
   `reponseContrat`) — jamais une charge utile écrite à la main : le test
   backend jumeau affirme le MÊME fichier, les deux moitiés ne peuvent donc pas
   diverger.

   Ce qui est prouvé :
   1. chaque ligne de la feuille est rendue avec sa FORMULE, ses ENTRÉES et la
      PROVENANCE de chaque entrée (la `source` saisie par la société) ;
   2. un paramètre non saisi laisse la ligne OMISE et NOMME le champ manquant ;
   3. sans poids de fiche produit, AUCUNE masse n'est affichée et le champ
      fautif est nommé sous le bloc ;
   4. la charge par point de fixation n'est publiée que si le nombre de points
      par module est servi — il ne l'est pas, la ligne est donc omise en
      nommant ce champ. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { masseLestage: vi.fn(), zonesLestage: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import PanneauMasseLestage, {
  CLE_POINTS_FIXATION,
  chargeParPointDeFixation,
  provenanceEntree,
} from './PanneauMasseLestage'

const echantillon = (variante) => reponseContrat(
  'calepinage', 'calepinage_masse_lestage', variante,
).data

const servir = (variante) => {
  calepinageApi.calepinages.masseLestage
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_masse_lestage', variante))
}

const rendre = () => render(
  <MemoryRouter><PanneauMasseLestage calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PanneauMasseLestage (CALX17) — calepinage renseigné', () => {
  it('rend chaque ligne de la feuille avec sa formule et ses entrées', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx17-panneau')

    const exemple = echantillon('exemple')
    exemple.lestage.lignes.forEach((ligne) => {
      const bloc = screen.getByTestId(`calx17-ligne-${ligne.code}`)
      expect(within(bloc).getByText(ligne.libelle)).toBeInTheDocument()
      expect(screen.getByTestId(`calx17-formule-${ligne.code}`))
        .toHaveTextContent(ligne.formule)
      const entrees = screen.getByTestId(`calx17-entrees-${ligne.code}`)
      expect(within(entrees).getAllByRole('listitem'))
        .toHaveLength(ligne.entrees.length)
      ligne.entrees.forEach((cle) => {
        expect(screen.getByTestId(`calx17-entree-${ligne.code}-${cle}`))
          .toBeInTheDocument()
      })
    })
  })

  it('chaque entrée SAISIE affiche la provenance servie, jamais une devinette', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx17-panneau')

    const exemple = echantillon('exemple')
    const parametres = exemple.lestage.parametres
    const ligne = exemple.lestage.lignes.find((l) => l.code === 'pression_dynamique')
    ligne.entrees.forEach((cle) => {
      const saisi = parametres.find((parametre) => parametre.cle === cle)
      expect(saisi.source).toBeTruthy()
      expect(screen.getByTestId(`calx17-entree-${ligne.code}-${cle}`))
        .toHaveTextContent(saisi.source)
    })
    // La mention imprimable du serveur est recopiée telle quelle.
    expect(screen.getByTestId('calx17-mention'))
      .toHaveTextContent(exemple.lestage.mention)
  })

  it('montre la masse par m² de chaque pan et la provenance du poids', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx17-panneau')

    const masse = echantillon('exemple').masse
    expect(screen.queryByTestId('calx17-masse-absente')).toBeNull()
    masse.pans.forEach((pan) => {
      const ligne = screen.getByTestId(`calx17-pan-${pan.pan}`)
      expect(within(ligne).getByText(pan.pan)).toBeInTheDocument()
      expect(ligne).toHaveTextContent(String(pan.modules))
    })
    expect(screen.getByTestId('calx17-poids-unitaire'))
      .toHaveTextContent(masse.poids_unitaire.module_source)
  })
})

describe('PanneauMasseLestage (CALX17) — rien de saisi, rien d’inventé', () => {
  it('n’affiche aucune masse sans poids de fiche et nomme le champ fautif', async () => {
    servir('exemple_vide')
    rendre()
    await screen.findByTestId('calx17-panneau')

    const masse = echantillon('exemple_vide').masse
    expect(masse.poids_unitaire.module_kg).toBeNull()
    expect(screen.getByTestId('calx17-masse-absente')).toBeInTheDocument()
    expect(screen.queryByTestId('calx17-masse-pans')).toBeNull()

    const poids = masse.manquants.find((manquant) => manquant.quoi === 'poids_module')
    expect(screen.getByTestId('calx17-manquant-poids_module'))
      .toHaveTextContent(poids.message)
  })

  it('laisse chaque ligne OMISE en nommant les champs manquants', async () => {
    servir('exemple_vide')
    rendre()
    await screen.findByTestId('calx17-panneau')

    const lignes = echantillon('exemple_vide').lestage.lignes
    lignes.forEach((ligne) => {
      expect(ligne.valeur).toBeNull()
      expect(screen.getByTestId(`calx17-valeur-${ligne.code}`))
        .toHaveTextContent('ligne omise')
      // Le motif vient du SERVEUR : il nomme les paramètres à saisir.
      expect(screen.getByTestId(`calx17-manque-${ligne.code}`))
        .toHaveTextContent(ligne.mention)
    })
  })
})

describe('chargeParPointDeFixation (CALX17)', () => {
  it('est omise, en nommant le champ, tant que les points ne sont pas saisis', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx17-panneau')

    // Aucun réglage servi ne porte le nombre de points de fixation…
    const parametres = echantillon('exemple').lestage.parametres
    expect(parametres.some((p) => p.cle === CLE_POINTS_FIXATION)).toBe(false)
    // … la ligne est donc OMISE, et l'écran NOMME le champ attendu.
    expect(screen.getByTestId('calx17-fixation-valeur'))
      .toHaveTextContent('ligne omise')
    expect(screen.getByTestId('calx17-fixation-manque'))
      .toHaveTextContent(CLE_POINTS_FIXATION)
  })

  it('divise l’effort servi par le nombre de points DÈS QU’il est saisi', () => {
    // Fonction PURE : on lui passe l'échantillon committé auquel s'ajoute le
    // paramètre qu'aucun réglage ne sert encore (forme identique à celle des
    // autres paramètres servis). Aucune réponse serveur n'est inventée ici :
    // c'est la formule qui est éprouvée, sur les chiffres du contrat.
    const exemple = echantillon('exemple')
    const effort = exemple.lestage.lignes
      .find((ligne) => ligne.code === 'effort_soulevement_module')
    const charge = chargeParPointDeFixation({
      ...exemple,
      lestage: {
        ...exemple.lestage,
        parametres: [
          ...exemple.lestage.parametres,
          {
            cle: CLE_POINTS_FIXATION,
            libelle: 'Points de fixation par module',
            unite: '',
            valeur: 4,
            source: 'saisie société (essai)',
          },
        ],
      },
    })
    expect(charge.valeur).toBe(effort.valeur / 4)
    expect(charge.manquants).toEqual([])
    expect(charge.provenance).toBe('saisie société (essai)')
  })

  it('reste omise quand l’effort lui-même n’est pas calculé', () => {
    const vide = echantillon('exemple_vide')
    const charge = chargeParPointDeFixation(vide)
    expect(charge.valeur).toBeNull()
    expect(charge.manquants).toContain(CLE_POINTS_FIXATION)
  })
})

describe('provenanceEntree (CALX17)', () => {
  it('rend la source SAISIE quand le serveur la publie', () => {
    const parametres = echantillon('exemple').lestage.parametres
    const premier = parametres[0]
    expect(provenanceEntree(premier.cle, parametres)).toMatchObject({
      libelle: premier.libelle,
      valeur: premier.valeur,
      provenance: premier.source,
    })
  })

  it('dit « non saisie » pour une entrée qu’aucune source ne couvre', () => {
    expect(provenanceEntree('cle_inconnue', []).provenance).toBeNull()
  })
})

/* CALX362 — le choix de la zone (CALX361), la colonne « Source » de chaque
   ligne, et le lien vers les réglages quand rien n'est calculable. Tout est
   affirmé sur `calepinage_masse_lestage.json` (variante `exemple_zone`,
   sortie RÉELLE du service backend, CALX361) — le catalogue des zones
   (`zonesLestage`) est une donnée AUXILIAIRE, illustrée ici (pas de contrat
   dédié : la garantie porte sur `masse-lestage`). */
describe('PanneauMasseLestage (CALX362) — équivalence sans zones (D12)', () => {
  it('n’affiche AUCUN bloc « choix de la zone » et ne lit pas le catalogue', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx17-panneau')
    expect(screen.queryByTestId('calx362-zone')).toBeNull()
    expect(calepinageApi.calepinages.zonesLestage).not.toHaveBeenCalled()
  })
})

describe('PanneauMasseLestage (CALX362) — zone retenue', () => {
  it('affiche la zone, son origine, ses sources, et la marque dans le catalogue', async () => {
    servir('exemple_zone')
    calepinageApi.calepinages.zonesLestage.mockResolvedValue({
      data: {
        lestage: {
          zones: [
            { code: 'littoral', libelle: 'Littoral (essai)', commune_ou_region: 'Casablanca-Settat' },
            { code: 'atlas', libelle: 'Moyen Atlas (essai)', commune_ou_region: 'Fès-Meknès' },
          ],
          zone_par_defaut: 'littoral',
        },
      },
    })
    rendre()
    await screen.findByTestId('calx362-zone')

    const zone = echantillon('exemple_zone').lestage.zone
    expect(screen.getByTestId('calx362-zone-retenue')).toHaveTextContent(zone.libelle)
    expect(screen.getByTestId('calx362-zone-retenue')).toHaveTextContent('désignée par ce calepinage')
    expect(screen.getByTestId('calx362-zone-sources')).toHaveTextContent(zone.sources[0])

    const retenue = await screen.findByTestId('calx362-zone-catalogue-atlas')
    expect(retenue).toHaveTextContent('retenue')
    const autre = screen.getByTestId('calx362-zone-catalogue-littoral')
    expect(autre).not.toHaveTextContent('retenue')
  })

  it('affiche la « colonne source » de chaque ligne calculée en mode zone', async () => {
    servir('exemple_zone')
    calepinageApi.calepinages.zonesLestage.mockResolvedValue({ data: { lestage: {} } })
    rendre()
    await screen.findByTestId('calx17-panneau')

    const ligne = echantillon('exemple_zone').lestage.lignes
      .find((l) => l.code === 'pression_dynamique')
    expect(screen.getByTestId(`calx362-source-${ligne.code}`)).toHaveTextContent(ligne.mention)
  })
})

describe('PanneauMasseLestage (CALX362) — rien de calculable', () => {
  it('affiche un lien vers les réglages, jamais un tableau de zéros', async () => {
    servir('exemple_vide')
    rendre()
    await screen.findByTestId('calx17-panneau')

    expect(echantillon('exemple_vide').lestage.calculable).toBe(false)
    const lien = screen.getByTestId('calx362-lien-reglages-vide')
    expect(lien).toHaveAttribute('href', '/calepinage/reglages')
  })

  it('n’affiche PAS le lien quand des résultats sont calculés', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('calx17-panneau')
    expect(screen.queryByTestId('calx362-lien-reglages-vide')).toBeNull()
  })
})
