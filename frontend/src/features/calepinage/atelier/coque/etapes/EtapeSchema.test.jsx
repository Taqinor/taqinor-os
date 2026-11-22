/* ACAL1301 — le sous-écran « Schéma électrique » de la coque (maquette `Schema.dc.html`).
   Nouveau fichier car : écran neuf (`EtapeSchema.jsx`, refait par la lane L3), aucun module de test voisin.

   Ce qui est prouvé : le schéma SERVI est au centre (zoom ±), le panneau lit « Légende » (signes du
   SVG servi) et « Cartouche » (détail servi), la note bleue est là ; au pied, « Télécharger (PDF) »
   et « DXF » appellent les téléchargements EXISTANTS de l'inventaire `documents/` (même délai, mêmes
   textes d'erreur) ; « ← Raccordement » rouvre l'étape Électrique. Toutes les charges utiles viennent
   des échantillons de contrat. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { exempleContrat } from '../../../../../test/fixtures/contractSamples'

vi.mock('../../../../../api/calepinageApi', () => ({
  default: { calepinages: {
    schemaUnifilaire: vi.fn(), get: vi.fn(), resultat: vi.fn(), documents: vi.fn(),
    telechargerDocument: vi.fn(), sldDxf: vi.fn(),
  } },
}))
const downloadBlob = vi.fn()
vi.mock('../../../../../utils/downloadBlob', () => ({
  downloadBlob: (...args) => downloadBlob(...args),
  filenameFromResponse: (_reponse, repli) => repli,
}))

import calepinageApi from '../../../../../api/calepinageApi'
import { OPTIONS_TELECHARGEMENT } from '../../../documents/telechargement'
import { ContexteCoque } from '../contexteCoque'
import EtapeSchema from './EtapeSchema'

const contrat = (nom, cle) => structuredClone(exempleContrat('calepinage', nom, cle))

function inventaire(disponible) {
  const inv = contrat('calepinage_documents')
  const piece = inv.documents.find((d) => d.code === 'plan_cablage')
  piece.disponible = disponible
  return { inv, piece }
}

// Le dessin servi + une liaison pleine et une liaison de terre en pointillé (les deux traits de
// `core/electrique/schema.py::_trait`), sans tableau de sections : la légende doit nommer les deux, pas « mm² ».
function sld() {
  const s = contrat('calepinage_sld')
  s.svg = s.svg.replace('</svg>', '<line x1="0" y1="0" x2="9" y2="0" stroke="#1f3a5f"/>'
    + '<line x1="0" y1="9" x2="9" y2="9" stroke="#1f3a5f" stroke-dasharray="4 3"/></svg>')
  return s
}

function servir({ disponible = true } = {}) {
  const { inv, piece } = inventaire(disponible)
  calepinageApi.calepinages.schemaUnifilaire.mockResolvedValue({ data: sld() })
  calepinageApi.calepinages.get.mockResolvedValue({ data: contrat('calepinage_detail') })
  calepinageApi.calepinages.resultat.mockResolvedValue({ data: contrat('calepinage_resultat') })
  calepinageApi.calepinages.documents.mockResolvedValue({ data: inv })
  calepinageApi.calepinages.telechargerDocument.mockResolvedValue({ data: new Blob(['%PDF']) })
  return piece
}

function TemoinUrl() {
  return <p data-testid="temoin-url">{useLocation().search}</p>
}

function rendre() {
  const panneau = document.createElement('div')
  const pied = document.createElement('div')
  document.body.append(panneau, pied)
  const coque = { noeuds: { surCarte: null, panneau, pied }, prendrePied: () => () => {} }
  render(
    <MemoryRouter initialEntries={['/calepinage/5?onglet=schema']}>
      <Routes>
        <Route path="/calepinage/:id" element={(
          <ContexteCoque.Provider value={coque}>
            <EtapeSchema calepinageId={5} />
            <TemoinUrl />
          </ContexteCoque.Provider>
        )} />
      </Routes>
    </MemoryRouter>,
  )
  return { panneau, pied }
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); document.body.innerHTML = '' })

describe('EtapeSchema — sous-écran « Schéma électrique » (ACAL1301)', () => {
  it('schéma EN BLOCS au centre avec zoom, légende du dessin et cartouche SERVIS, note bleue, deux téléchargements', async () => {
    servir()
    const { panneau, pied } = rendre()
    // F3 — le dessin de la maquette, composé depuis les données servies (blocs + chaînes + tronçons).
    const blocs = await screen.findByTestId('csch-blocs')
    await waitFor(() => expect(blocs).toHaveTextContent('Chaîne 1 · 2 panneaux'))
    for (const texte of ['Côté panneaux · courant continu', 'Coffret côté panneaux', 'Onduleur', '10 kW',
      'Coffret côté réseau', 'Disjoncteur', 'Côté réseau · courant alternatif', 'entrée 2 · 6 mm²']) {
      expect(blocs).toHaveTextContent(texte)
    }
    expect(screen.getByRole('button', { name: 'Zoomer' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Dézoomer' })).toBeTruthy()
    // Phrase sous le dessin : chaînes et câble DC SERVIS (2 chaînes de 2 modules, 18,4 + 12,0 m mesurés).
    await waitFor(() => expect(screen.getByText(
      'Dessiné tout seul à partir du raccordement : 2 chaînes de 2 panneaux, 30 m de câble côté panneaux au total.',
    )).toBeTruthy())
    // Légende = ce que le dessin en blocs emploie (couleurs de chaîne servies comprises), dans l'ordre de la maquette.
    const legende = within(panneau).getByTestId('cal-schema-legende')
    expect([...legende.querySelectorAll('li')].map((li) => li.textContent)).toEqual([
      'Chaîne 1 · entrée 1', 'Chaîne 2 · entrée 2', 'Côté réseau (courant alternatif)', 'Liaison à la terre',
      'mm²Section du câble, puis sa longueur'])
    expect(legende.querySelector('li span').style.background).toBe('rgb(30, 144, 255)')
    const cartouche = await within(panneau).findByTestId('cal-schema-cartouche')
    for (const libelle of ['Projet', 'Date', 'Version', 'Auteur']) expect(cartouche).toHaveTextContent(libelle)
    expect(cartouche).toHaveTextContent('Toiture — bâtiment principal — Casablanca')
    expect(cartouche).toHaveTextContent("Utilisateur d'essai")
    // Un clic sur un élément ouvre vraiment sa section : la 2e phrase de la maquette est rendue.
    expect(panneau).toHaveTextContent(
      'Le schéma se redessine quand le raccordement change. Cliquez sur un élément pour voir d’où vient sa valeur.')
    expect(within(pied).getByRole('button', { name: 'Télécharger (PDF)' })).toBeTruthy()
    expect(within(pied).getByRole('button', { name: 'DXF' })).toBeTruthy()
  })

  it('« Schéma détaillé » montre le SVG SERVI (celui du PDF / DXF) et sa propre légende ; rien n’est retiré', async () => {
    servir()
    const { panneau } = rendre()
    await screen.findByTestId('csch-blocs')
    fireEvent.click(screen.getByRole('button', { name: 'Schéma détaillé' }))
    expect(screen.getByTestId('csch-svg')).toHaveTextContent('Champ PV')
    expect(screen.queryByTestId('csch-blocs')).toBeNull()
    const legende = within(panneau).getByTestId('cal-schema-legende')
    expect(legende).toHaveTextContent('Liaison entre deux organes')
    expect(legende).toHaveTextContent('Liaison à la terre')
    // Aucun « mm² » dans ce SVG-là : la légende n'en invente pas.
    expect(legende).not.toHaveTextContent('Section du câble')
    expect(panneau).not.toHaveTextContent('Cliquez sur un élément')
    fireEvent.click(screen.getByRole('button', { name: 'Schéma en blocs' }))
    expect(screen.getByTestId('csch-blocs')).toBeTruthy()
  })

  it('un clic sur un bloc ouvre la section de l’étape Électrique où SA valeur se règle', async () => {
    servir()
    rendre()
    await screen.findByTestId('csch-blocs')
    fireEvent.click(await screen.findByTestId('csch-bloc-onduleur'))
    const url = () => new URLSearchParams(screen.getByTestId('temoin-url').textContent)
    expect(url().get('onglet')).toBe('materiel-electrique')
    expect(url().get('champ')).toBeNull()
  })

  it('sans chaîne servie, le schéma détaillé du serveur reste affiché (aucun bloc inventé)', async () => {
    servir()
    const vide = contrat('calepinage_resultat')
    vide.electrique.affectation = []
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: vide })
    rendre()
    await waitFor(() => expect(screen.getByTestId('csch-svg')).toHaveTextContent('Champ PV'))
    expect(screen.queryByTestId('csch-blocs')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Schéma détaillé' })).toBeNull()
  })

  it('« Télécharger (PDF) » et « DXF » : le plan de câblage servi et son autre format, mêmes options', async () => {
    const piece = servir()
    const { pied } = rendre()
    const pdf = within(pied).getByRole('button', { name: 'Télécharger (PDF)' })
    await waitFor(() => expect(pdf).not.toBeDisabled())
    fireEvent.click(pdf)
    await waitFor(() => expect(calepinageApi.calepinages.telechargerDocument)
      .toHaveBeenCalledWith(piece.endpoint, undefined, OPTIONS_TELECHARGEMENT))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'plan_cablage.pdf'))
    fireEvent.click(within(pied).getByRole('button', { name: 'DXF' }))
    await waitFor(() => expect(calepinageApi.calepinages.telechargerDocument)
      .toHaveBeenCalledWith(piece.autres_formats[0].endpoint, undefined, OPTIONS_TELECHARGEMENT))
  })

  it('pièce indisponible : PDF désactivé avec le motif SERVI ; le DXF du schéma reste possible', async () => {
    const piece = servir({ disponible: false })
    calepinageApi.calepinages.sldDxf.mockResolvedValue({ data: new Blob(['0']) })
    const { pied } = rendre()
    await waitFor(() => expect(pied).toHaveTextContent(piece.motif_indisponible))
    expect(within(pied).getByRole('button', { name: 'Télécharger (PDF)' })).toBeDisabled()
    const dxf = within(pied).getByRole('button', { name: 'DXF' })
    await waitFor(() => expect(dxf).not.toBeDisabled())
    fireEvent.click(dxf)
    await waitFor(() => expect(calepinageApi.calepinages.sldDxf).toHaveBeenCalledWith(5, OPTIONS_TELECHARGEMENT))
  })

  it('un délai dépassé dit quoi faire, avec le texte des documents', async () => {
    servir()
    calepinageApi.calepinages.telechargerDocument.mockRejectedValueOnce({ code: 'ECONNABORTED' })
    const { pied } = rendre()
    const pdf = within(pied).getByRole('button', { name: 'Télécharger (PDF)' })
    await waitFor(() => expect(pdf).not.toBeDisabled())
    fireEvent.click(pdf)
    expect(await within(pied).findByText(/n'a pas fini de préparer ce document/)).toBeTruthy()
  })

  it('« Raccordement » rouvre l’étape Électrique', async () => {
    servir()
    rendre()
    fireEvent.click(screen.getByRole('button', { name: 'Raccordement' }))
    expect(new URLSearchParams(screen.getByTestId('temoin-url').textContent).get('onglet')).toBe('verdict-electrique')
  })
})
