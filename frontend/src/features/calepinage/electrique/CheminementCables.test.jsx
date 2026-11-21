/* CALX229 — le panneau « Cheminement & câbles » de l'atelier.

   Ce qui est prouvé ici :
     1. une ligne par tronçon de l'exemple COMMITTÉ (`calepinage_troncons.json`,
        CALX203, relu par `node:fs` — jamais recopié à la main) ;
     2. une valeur `null` rend un TIRET, jamais un `0` (`ch5`, sans norme
        électrique choisie) ;
     3. les omissions du serveur sont recopiées SANS reformulation ;
     4. un 404 de la porte (calepinage inconnu ou d'une autre société)
        affiche « Calepinage introuvable », jamais une erreur générique. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const CONTRAT = documentContrat('calepinage', 'calepinage_troncons')

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { troncons: vi.fn(), layout: vi.fn(), entreeElectrique: vi.fn(), enregistrerEntreeElectrique: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import CheminementCables from './CheminementCables'
import { celluleLongueur, libelleCote, libelleOrigine } from './CheminementCables.helpers'
import { documentContrat } from '../../../test/fixtures/contractSamples'

const servir = (data) => { calepinageApi.calepinages.troncons.mockResolvedValue({ data }) }
const refuser404 = () => {
  calepinageApi.calepinages.troncons.mockRejectedValue({ response: { status: 404 } })
}

const rendre = () => render(
  <MemoryRouter><CheminementCables calepinageId={12} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CheminementCables (CALX229)', () => {
  it('une ligne par tronçon de l’exemple committé', async () => {
    servir(CONTRAT.exemple)

    rendre()

    for (const t of CONTRAT.exemple.troncons) {
      expect(await screen.findByTestId(`calx229-troncon-${t.id}`)).toBeInTheDocument()
    }
    expect(CONTRAT.exemple.troncons).toHaveLength(5)
  })

  it('ch5 (section/chute non calculables) rend un TIRET, jamais un 0', async () => {
    servir(CONTRAT.exemple)

    rendre()

    expect(await screen.findByTestId('calx229-chute-ch5')).toHaveTextContent('—')
    expect(screen.getByTestId('calx229-section-ch5')).toHaveTextContent('—')
    expect(screen.getByTestId('calx229-chute-ch5')).not.toHaveTextContent('0')
    expect(screen.getByTestId('calx229-section-ch5')).not.toHaveTextContent('0')
  })

  it('celluleLongueur publie TOUJOURS le nombre ET son origine', () => {
    expect(celluleLongueur({ longueur_m: 18.4, longueur_origine: 'plan' }))
      .toBe('18,4 m (tracé sur le plan)')
    expect(celluleLongueur({ longueur_m: 12, longueur_origine: 'saisie' }))
      .toBe('12,0 m (saisie au clavier)')
    expect(celluleLongueur({ longueur_m: null, longueur_origine: 'plan' })).toBe('—')
  })

  it('libelleCote/libelleOrigine NOMMENT un code inconnu, ne le masquent jamais', () => {
    expect(libelleCote('dc')).toBe('DC')
    expect(libelleCote('hydraulique')).toBe('côté « hydraulique »')
    expect(libelleOrigine('mixte')).toBe('tracé + saisie (mixte)')
    expect(libelleOrigine('devinee')).toBe('origine « devinee »')
  })

  it('les omissions du serveur sont recopiées SANS reformulation', async () => {
    servir(CONTRAT.exemple)

    rendre()

    const omission = CONTRAT.exemple.omissions[0]
    expect(await screen.findByTestId('calx229-omission-0')).toHaveTextContent(omission.motif)
  })

  it('métré par section : une ligne par section, section absente NOMMÉE', async () => {
    servir(CONTRAT.exemple)

    rendre()

    const bloc = await screen.findByTestId('calx229-metre-section')
    expect(bloc).toHaveTextContent('Section non déterminée')
    expect(bloc).toHaveTextContent('6,0 mm²')
    expect(bloc).toHaveTextContent('10,0 mm²')
  })

  it('totaux DC/AC recopiés du serveur, jamais recalculés', async () => {
    servir(CONTRAT.exemple)

    rendre()

    expect(await screen.findByTestId('calx229-total-dc')).toHaveTextContent('0,70 %')
    expect(screen.getByTestId('calx229-total-ac')).toHaveTextContent('1,18 %')
  })

  it('aucun tracé : l’exemple_vide du contrat, une omission qui le dit', async () => {
    servir(CONTRAT.exemple_vide)

    rendre()

    expect(await screen.findByTestId('calx229-vide')).toBeInTheDocument()
    expect(await screen.findByTestId('calx229-omission-0')).toHaveTextContent(
      CONTRAT.exemple_vide.omissions[0].motif,
    )
  })

  it('404 : un 404 affiche « Calepinage introuvable », jamais une erreur générique', async () => {
    refuser404()

    rendre()

    expect(await screen.findByTestId('calx229-introuvable')).toBeInTheDocument()
    expect(screen.getByText('Calepinage introuvable')).toBeInTheDocument()
    expect(screen.queryByTestId('calx229-erreur')).toBeNull()
  })

  it('ACAL472 : « Proposer le tracé » appelle l’API du builder avec côté, de, vers ; un refus est NOMMÉ', async () => {
    servir(CONTRAT.exemple)
    const proposerCheminement = vi.fn()
      .mockReturnValueOnce({ ok: true, cheminement: { id: 'ch9', points: [{}, {}, {}] } })
      .mockReturnValueOnce({ ok: false, champ: 'electrical.cheminements.points', message: 'Aucun chemin entre les deux organes.' })
    const builderApi = {
      electrique: {
        proposerCheminement,
        documentElectrique: () => ({ equipements: [{ id: 'eq1', label: 'Onduleur' }, { id: 'eq2', label: 'Coffret' }] }),
      },
    }

    render(<MemoryRouter><CheminementCables calepinageId={12} builderApi={builderApi} /></MemoryRouter>)

    await screen.findByTestId('acal472-proposer')
    fireEvent.change(screen.getByTestId('acal472-cote'), { target: { value: 'ac' } })
    fireEvent.change(screen.getByTestId('acal472-de'), { target: { value: 'eq1' } })
    fireEvent.change(screen.getByTestId('acal472-vers'), { target: { value: 'eq2' } })
    fireEvent.click(screen.getByTestId('acal472-proposer'))

    expect(proposerCheminement).toHaveBeenCalledWith({ cote: 'ac', de: 'eq1', vers: 'eq2' })
    expect(screen.getByTestId('acal472-resultat')).toHaveTextContent('3 points')
    fireEvent.click(screen.getByTestId('acal472-proposer'))
    expect(screen.getByTestId('acal472-resultat')).toHaveTextContent('Aucun chemin entre les deux organes.')
  })

  it('ACAL472 : sans outil 3D prêt, le motif est nommé, rien n’est inventé', async () => {
    servir(CONTRAT.exemple)

    rendre()

    fireEvent.click(await screen.findByTestId('acal472-proposer'))
    expect(screen.getByTestId('acal472-resultat')).toHaveTextContent('Outil 3D non prêt')
  })

  it('ACAL641 : le motif et le point d’un pan partent dans cheminement.pans.<clé> et la longueur est relue', async () => {
    const corpsContrat = documentContrat('calepinage', 'calepinage_entree_electrique').exemple_corps_cheminement_pans
    servir(CONTRAT.exemple)
    calepinageApi.calepinages.layout.mockResolvedValue({ data: {
      roof_layout: { zones: [
        { id: 'z1', label: 'Pan Sud', geometry: { panels: [{ n: 1, cx: 0.5, cy: 0.5 }, { n: 2, cx: 2.4, cy: 1.1 }] } },
        { id: 'z2', label: 'Pan vide', geometry: { panels: [] } },
      ] },
      empreinte_document: 'E0',
    } })
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: { cheminement: { descente_m: 4 } } } })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    const motif = await screen.findByTestId('acal641-motif-z1')
    expect(motif).toHaveValue('') // aucun motif présélectionné
    expect(screen.queryByTestId('acal641-motif-z2')).toBeNull() // pan sans module
    const avant = calepinageApi.calepinages.troncons.mock.calls.length
    fireEvent.change(motif, { target: { value: 'aller_retour' } })
    fireEvent.change(screen.getByTestId('acal641-point-z1'), { target: { value: '1' } })
    fireEvent.click(screen.getByTestId('acal641-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
    const [id, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(id).toBe(12)
    expect(corps).toEqual({ cheminement: { descente_m: 4, ...corpsContrat.cheminement } }) // clé du pan, fusionnée
    await waitFor(() => expect(calepinageApi.calepinages.troncons.mock.calls.length).toBeGreaterThan(avant))
  })

  it('ACAL641 : un refus 400 s’affiche SOUS le champ du pan', async () => {
    const refus = documentContrat('calepinage', 'calepinage_entree_electrique').exemple_refus_motif_parcours
    servir(CONTRAT.exemple)
    calepinageApi.calepinages.layout.mockResolvedValue({ data: {
      roof_layout: { zones: [{ id: 'z1', label: 'Pan Sud', geometry: { panels: [{ n: 1, cx: 0.5, cy: 0.5 }] } }] },
      empreinte_document: 'E0',
    } })
    calepinageApi.calepinages.entreeElectrique.mockResolvedValue({ data: { entree: {} } })
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({ response: { data: refus } })
    rendre()
    fireEvent.change(await screen.findByTestId('acal641-motif-z1'), { target: { value: 'aller_retour' } })
    fireEvent.click(screen.getByTestId('acal641-enregistrer'))
    expect(await screen.findByTestId('acal641-erreur-z1')).toHaveTextContent('motif de parcours inconnu')
  })
})
