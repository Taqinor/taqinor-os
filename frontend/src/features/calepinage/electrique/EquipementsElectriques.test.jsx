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
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const ICI = dirname(fileURLToPath(import.meta.url))

function racineDepot() {
  let dossier = resolve(ICI)
  for (let i = 0; i < 10; i += 1) {
    try {
      readFileSync(join(dossier, 'backend', 'django_core', 'manage.py'))
      return dossier
    } catch { dossier = dirname(dossier) }
  }
  throw new Error(`Racine du depot introuvable depuis ${ICI}`)
}

const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
  'contract_samples', 'electrique_equipements.json'), 'utf8'))

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { layout: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import EquipementsElectriques, {
  TYPES_EQUIPEMENT, libelleType, libelleProduit,
} from './EquipementsElectriques'

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

  it('document SANS clé `electrical` : même état vide, jamais une erreur', async () => {
    servirLayout(undefined)

    rendre()

    await waitFor(() => expect(screen.getByTestId('calx222-vide')).toBeInTheDocument())
  })
})
