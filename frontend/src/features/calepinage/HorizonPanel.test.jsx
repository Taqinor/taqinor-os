import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { espions } from '../../test/fixtures/calepinageApiMock'
import { MESSAGE_ILLISIBLE } from './useDocumentCalepinage'

/* ENF15 — l'onglet « Horizon lointain » (CALX1) est MONTÉ : lecture du document,
   un profil incomplet n'est pas enregistrable, un document illisible le dit. */

vi.mock('../../api/calepinageApi', async () => (await import('../../test/fixtures/calepinageApiMock')).apiDocument({ horizon: true }))

const { default: HorizonPanel } = await import('./HorizonPanel')

const rendre = () => render(<MemoryRouter><HorizonPanel calepinageId={7} /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('HorizonPanel — onglet monté', () => {
  it('3 points relevés : listés, mais « Enregistrer » refusé (tour incomplet)', async () => {
    const points = [0, 120, 240].map((azimuthDeg) => ({ azimuthDeg, heightDeg: 10 }))
    espions.layout.mockResolvedValue({ data: { roof_layout: { pin: { lat: 33.5, lng: -7.6 }, horizonProfile: { source: 'saisie', points } } } })
    rendre()
    const liste = await screen.findByTestId('cal-horizon-points')
    await vi.waitFor(() => expect(liste.querySelectorAll('li')).toHaveLength(3))
    expect(screen.getByRole('button', { name: 'Enregistrer le profil' })).toBeDisabled()
    expect(screen.getByText(/au moins 8 directions \(3 relevée/)).toBeInTheDocument()
  })

  it('ajouter un point à la saisie le met dans la liste', async () => {
    espions.layout.mockResolvedValue({ data: { roof_layout: {} } })
    rendre()
    await screen.findByTestId('cal-horizon')
    fireEvent.change(screen.getByTestId('cal-horizon-champ-azimut').querySelector('input'), { target: { value: '90' } })
    fireEvent.change(screen.getByTestId('cal-horizon-champ-hauteur').querySelector('input'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter le point' }))
    expect(screen.getByTestId('cal-horizon-hauteur-max')).toHaveTextContent('12.0°')
  })

  it('latitude du contexte sans épingle : la course du soleil est tracée (ACAL251)', async () => {
    // Calepinage NEUF : aucun pin dans le document ; le détail sert le repère.
    espions.layout.mockResolvedValue({ data: { roof_layout: {} } })
    espions.get.mockResolvedValue({ data: { contexte_geographique: { pin: { lat: 33.6, lng: -7.6 } } } })
    rendre()
    await screen.findByTestId('cal-horizon')
    await vi.waitFor(() => expect(espions.get).toHaveBeenCalledWith(7))
    await vi.waitFor(() => expect(screen.queryByText(/Latitude du site inconnue/)).toBeNull())
  })

  it('ni épingle ni repère servi : latitude inconnue, dite (jamais devinée)', async () => {
    espions.layout.mockResolvedValue({ data: { roof_layout: {} } })
    espions.get.mockResolvedValue({ data: { contexte_geographique: { pin: null } } })
    rendre()
    await vi.waitFor(() => expect(espions.get).toHaveBeenCalled())
    expect(await screen.findByText(/Latitude du site inconnue/)).toBeInTheDocument()
  })

  it('lecture du document en échec : message d’illisibilité, rien d’enregistrable', async () => {
    espions.layout.mockRejectedValue(new Error('500'))
    rendre()
    expect(await screen.findByText(MESSAGE_ILLISIBLE)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enregistrer le profil' })).toBeDisabled()
  })

  // ACAL1815 — au doigt : le message d'enregistrement passe SOUS « Enregistrer le profil » (pleine largeur, plus
  // sur sa rangée où il l'écrasait en colonne de ~60 px) ; champs et boutons de l'onglet ≥ 44 px de haut.
  it('après « Enregistrer le profil », le message est sous le bouton ; champs et boutons à 44 px', async () => {
    const points = [0, 45, 90, 135, 180, 225, 270, 315].map((azimuthDeg) => ({ azimuthDeg, heightDeg: 5 }))
    espions.layout.mockResolvedValue({ data: { roof_layout: { horizonProfile: { source: 'saisie', points } }, empreinte_document: 'E0' } })
    espions.enregistrerSectionLayout.mockResolvedValue({ data: { empreinte_document: 'E1' } })
    rendre()
    const bouton = await screen.findByRole('button', { name: 'Enregistrer le profil' })
    await vi.waitFor(() => expect(bouton).toBeEnabled())
    fireEvent.click(bouton)
    const message = await screen.findByText(/Profil d’horizon enregistré/)
    const rangee = screen.getByTestId('cal-horizon-enregistrer-rangee')
    expect(rangee).toHaveClass('flex-col')
    expect(message.parentElement).toBe(rangee)
    expect(message).toHaveClass('w-full')
    expect(bouton.compareDocumentPosition(message) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const cibles = [
      bouton,
      screen.getByTestId('cal-horizon-champ-azimut').querySelector('input'),
      screen.getByTestId('cal-horizon-champ-hauteur').querySelector('input'),
      screen.getByTestId('cal-horizon-fichier'),
      ...['Ajouter le point', 'Importer', 'Récupérer depuis PVGIS'].map((name) => screen.getByRole('button', { name })),
    ]
    for (const el of cibles) expect(el).toHaveClass('min-h-11')
  })

  describe('ACAL458 — import de fichier', () => {
    const huit = (az) => az.map((a, i) => `${a};${i + 1}`).join('\n')
    async function choisir(contenu) {
      espions.layout.mockResolvedValue({ data: { roof_layout: {} } })
      rendre()
      await screen.findByTestId('cal-horizon')
      const f = new File([contenu], 'horizon.txt', { type: 'text/plain' })
      fireEvent.change(screen.getByTestId('cal-horizon-fichier'), { target: { files: [f] } })
      await new Promise((r) => setTimeout(r, 60)) // FileReader asynchrone
    }
    const liste = () => [...screen.getByTestId('cal-horizon-points').querySelectorAll('li')].map((li) => li.textContent)

    it('convention non choisie ⇒ bouton inactif ; Sud : −180→0, −90→90, 0→180, +90→270', async () => {
      await choisir(huit([-180, -135, -90, -45, 0, 45, 90, 135]))
      const bouton = screen.getByRole('button', { name: 'Importer' })
      await vi.waitFor(() => expect(bouton).toBeDisabled())
      fireEvent.click(screen.getByLabelText(/0° = Sud/))
      await vi.waitFor(() => expect(bouton).toBeEnabled())
      fireEvent.click(bouton)
      const lignes = liste()
      expect(lignes).toHaveLength(8)
      // azimut de face triés : 0 (−180), 45, 90 (−90), 135, 180 (0), 225, 270 (+90), 315
      expect(lignes.map((t) => t.split('°')[0])).toEqual(['0', '45', '90', '135', '180', '225', '270', '315'])
      expect(lignes[0]).toContain('1.0°')
      expect(screen.getByRole('status')).toHaveTextContent(/horizon\.txt.*0° = Sud/)
    })

    it('convention Nord : azimuts gardés tels quels', async () => {
      await choisir(huit([0, 45, 90, 135, 180, 225, 270, 315]))
      fireEvent.click(screen.getByLabelText(/0° = Nord/))
      fireEvent.click(screen.getByRole('button', { name: 'Importer' }))
      expect(liste().map((t) => t.split('°')[0])).toEqual(['0', '45', '90', '135', '180', '225', '270', '315'])
    })

    it('une colonne (userhorizon) : 8 hauteurs = directions de 45° depuis le Nord, sans convention', async () => {
      await choisir('# userhorizon\n1\n2\n3\n4\n5\n6\n7\n8')
      const bouton = screen.getByRole('button', { name: 'Importer' })
      await vi.waitFor(() => expect(bouton).toBeEnabled())
      fireEvent.click(bouton)
      expect(liste().map((t) => t.split('°')[0])).toEqual(['0', '45', '90', '135', '180', '225', '270', '315'])
      expect(liste()[2]).toContain('3.0°')
    })

    it('ligne illisible nommée ; tour incomplet refusé', async () => {
      await choisir('azimut;hauteur\n0;1\n45;abc\n90;3')
      fireEvent.click(screen.getByLabelText(/0° = Nord/))
      fireEvent.click(screen.getByRole('button', { name: 'Importer' }))
      expect(screen.getByRole('status')).toHaveTextContent(/ligne 3 illisible/)
      expect(screen.queryByTestId('cal-horizon-points').querySelectorAll('li')[0]).toHaveTextContent('Aucun point')
      fireEvent.change(screen.getByTestId('cal-horizon-fichier'), { target: { files: [new File(['0;1\n90;2\n180;3'], 'c.txt')] } })
      await new Promise((r) => setTimeout(r, 60))
      await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Importer' })).toBeEnabled())
      fireEvent.click(screen.getByRole('button', { name: 'Importer' }))
      await vi.waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/tour complet/))
    })
  })
})
