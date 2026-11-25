/* CALX222 — le panneau « Équipements électriques » de l'atelier.

   Ce qui est prouvé ici :
     1. la liste rend UN élément par équipement du document
        (`electrical.equipements[]`, contrat `electrique_equipements.json`
        COMMITTÉ, relu par `node:fs` — jamais recopié à la main) ;
     2. le bouton « Armer la pose » appelle l'API du builder 3D (CALX220) UNE
        SEULE fois, avec le type choisi ;
     3. un document sans équipement (ou sans clé `electrical`) affiche un
        `EmptyState` qui NOMME le geste à faire — jamais une liste vide muette. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const CONTRAT = documentContrat('calepinage', 'electrique_equipements')

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { layout: vi.fn(), evaluerElectrique: vi.fn(), entreeElectrique: vi.fn(), enregistrerEntreeElectrique: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import EquipementsElectriques from './EquipementsElectriques'
import { TYPES_EQUIPEMENT, libelleType, libelleProduit } from './EquipementsElectriques.helpers'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

const servirLayout = (electrical) => {
  calepinageApi.calepinages.layout.mockResolvedValue({
    data: { roof_layout: electrical === undefined ? {} : { electrical }, layout_hash: 'h', schema_version: 2 },
  })
}

const rendre = (props = {}) => render(
  <MemoryRouter>
    <EquipementsElectriques calepinageId={12} {...props} />
  </MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EquipementsElectriques (CALX222)', () => {
  it('rend un élément par équipement de l’exemple COMMITTÉ (les huit types)', async () => {
    servirLayout(CONTRAT.exemple.electrical)

    rendre()

    const liste = await screen.findByTestId('calx222-liste')
    expect(liste).toBeInTheDocument()
    for (const eq of CONTRAT.exemple.electrical.equipements) {
      const item = await screen.findByTestId(`calx222-equipement-${eq.id}`)
      expect(item).toHaveTextContent(eq.label)
    }
    expect(CONTRAT.exemple.electrical.equipements).toHaveLength(8)
  })

  it('un type hors énumération est NOMMÉ, jamais masqué', () => {
    expect(libelleType('onduleur_hybride')).toBe('Type inconnu : onduleur_hybride')
    expect(TYPES_EQUIPEMENT).toHaveLength(8)
  })

  it('la référence produit est brute, jamais une désignation devinée', () => {
    expect(libelleProduit(12)).toBe('Fiche produit #12')
    expect(libelleProduit(null)).toBe('Aucune fiche produit rattachée')
  })

  it('« Armer la pose » appelle l’API du builder UNE SEULE fois, avec le type choisi', async () => {
    servirLayout(CONTRAT.exemple_vide.electrical)
    const armerPose = vi.fn()
    const user = userEvent.setup()

    rendre({ builderApi: { electrique: { armerPose } } })

    await screen.findByTestId('calx222-vide')
    await user.click(screen.getByTestId('calx222-armer'))

    expect(armerPose).toHaveBeenCalledTimes(1)
    expect(armerPose).toHaveBeenCalledWith(TYPES_EQUIPEMENT[0])
    expect(screen.queryByTestId('calx222-armement-motif')).toBeNull()
  })

  it('sans builder prêt : le motif est NOMMÉ, jamais un échec silencieux', async () => {
    servirLayout(CONTRAT.exemple_vide.electrical)
    const user = userEvent.setup()

    rendre()

    await screen.findByTestId('calx222-vide')
    await user.click(screen.getByTestId('calx222-armer'))

    expect(await screen.findByTestId('calx222-armement-motif')).toHaveTextContent(
      'Outil 3D non prêt',
    )
  })

  it('document sans équipement : EmptyState qui NOMME le geste à faire', async () => {
    servirLayout(CONTRAT.exemple_vide.electrical)

    rendre()

    const vide = await screen.findByTestId('calx222-vide')
    expect(vide).toHaveTextContent('Aucun équipement électrique posé')
    expect(vide).toHaveTextContent('Armer la pose')
    expect(screen.queryByTestId('calx222-liste')).toBeNull()
  })

  it('T4-X5-008 — un organe posé puis enregistré (nouvelle empreinte du document) apparaît sans rouvrir l’onglet', async () => {
    servirLayout(CONTRAT.exemple_vide.electrical)
    const vue = rendre({ documentVivant: { empreinte: 'avant' } })
    await screen.findByTestId('calx222-vide')

    const eq = CONTRAT.exemple.electrical.equipements[0]
    servirLayout({ ...CONTRAT.exemple_vide.electrical, equipements: [eq] })
    vue.rerender(
      <MemoryRouter>
        <EquipementsElectriques calepinageId={12} documentVivant={{ empreinte: 'apres' }} />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId(`calx222-equipement-${eq.id}`)).toHaveTextContent(eq.label)
    expect(screen.queryByTestId('calx222-vide')).toBeNull()
  })

  it('T4-X5-008 — « Armer la pose » dit où cliquer et comment garder l’organe', async () => {
    servirLayout(CONTRAT.exemple_vide.electrical)
    const user = userEvent.setup()
    rendre({ builderApi: { electrique: { armerPose: vi.fn() } } })
    await screen.findByTestId('calx222-vide')
    await user.click(screen.getByTestId('calx222-armer'))
    expect(await screen.findByTestId('calx222-armement-consigne')).toHaveTextContent(
      'Cliquez dans l’atelier 3D à l’endroit de l’organe, puis « Enregistrer le calepinage »')
  })

  it('document SANS clé `electrical` : même état vide, jamais une erreur', async () => {
    servirLayout(undefined)

    rendre()

    await waitFor(() => expect(screen.getByTestId('calx222-vide')).toBeInTheDocument())
  })
})

describe('EquipementsElectriques (ACAL634) — « n onduleurs sont nécessaires »', () => {
  const EVAL = exempleContrat('calepinage', 'calepinage_evaluation_electrique', 'exemple_bloque')
  const ENTREE = exempleContrat('calepinage', 'calepinage_entree_electrique')
  const servir = (evaluation, accepte = null) => {
    servirLayout(undefined)
    calepinageApi.calepinages.evaluerElectrique.mockResolvedValue({ data: evaluation })
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { ...ENTREE, entree: { ...ENTREE.entree, nombre_onduleurs: accepte } } })
  }

  it('suggestion de 2 : la carte dit le motif servi ; le clic enregistre le nombre puis relit', async () => {
    servir(EVAL)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })
    rendre()

    expect(await screen.findByTestId('acal634-motif')).toHaveTextContent(EVAL.onduleurs_suggeres.motif)
    expect(calepinageApi.calepinages.enregistrerEntreeElectrique).not.toHaveBeenCalled()
    servir(EVAL, 2)
    await userEvent.click(screen.getByTestId('acal634-prendre'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledWith(12, { nombre_onduleurs: 2 }))
    await waitFor(() => expect(screen.queryByTestId('acal634-carte')).toBeNull())
  })

  it('nombre 1, ou nombre déjà accepté : aucune carte', async () => {
    servir(exempleContrat('calepinage', 'calepinage_evaluation_electrique'))
    rendre()
    await screen.findByTestId('calx222-panneau')
    expect(screen.queryByTestId('acal634-carte')).toBeNull()
    cleanup()
    servir(EVAL, 2)
    rendre()
    await screen.findByTestId('calx222-panneau')
    await waitFor(() => expect(calepinageApi.calepinages.entreeElectrique).toHaveBeenCalled())
    expect(screen.queryByTestId('acal634-carte')).toBeNull()
  })

  it('un refus serveur est affiché tel quel', async () => {
    servir(EVAL)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({ response: { status: 400, data: { nombre_onduleurs: 'Nombre refusé.' } } })
    rendre()
    await userEvent.click(await screen.findByTestId('acal634-prendre'))
    expect(await screen.findByTestId('acal634-refus')).toHaveTextContent('Nombre refusé.')
  })
})

