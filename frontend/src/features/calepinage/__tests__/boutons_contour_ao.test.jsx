import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'

/* ============================================================================
   CAL242 — les DEUX boutons de l'import de contour, des deux côtés.
   ----------------------------------------------------------------------------
   Ce que ce fichier prouve :
     * chaque bouton appelle SON endpoint (CAL240 côté calepinage, CAL241 côté
       AO) — sans bouton, les deux endpoints restent morts ;
     * chacun RAFRAÎCHIT après succès : l'écran relit la géométrie, il ne la
       devine pas ;
     * un refus 409/400 s'affiche SOUS le bouton avec le message du SERVEUR,
       mot pour mot — aucun texte fabriqué côté client ;
     * les deux rappellent que seule la géométrie de contour voyage.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ importerContourAo: vi.fn(), reprendreContour3d: vi.fn() }))

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { importerContourAo: mocks.importerContourAo } },
}))

vi.mock('../../../api/aoApi', () => ({
  default: { toitures: { reprendreContour3d: mocks.reprendreContour3d } },
}))

import { BoutonReprendreContourAffaire, BoutonReprendreTrace3D } from '../BoutonsContourAO'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.importerContourAo.mockResolvedValue({ data: {} })
  mocks.reprendreContour3d.mockResolvedValue({ data: {} })
})

describe('CAL242 — sens AO → calepinage (« Reprendre le contour de l’affaire »)', () => {
  it('appelle CAL240 avec la source AO, puis rafraîchit', async () => {
    const rafraichir = vi.fn().mockResolvedValue(undefined)
    render(
      <BoutonReprendreContourAffaire
        calepinageId={1}
        toitureId={5}
        affaireId={9}
        onImporte={rafraichir}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le contour de l’affaire/ }))
    await waitFor(() => expect(mocks.importerContourAo)
      .toHaveBeenCalledWith(1, { toiture: 5, appel_offre: 9 }))
    await waitFor(() => expect(rafraichir).toHaveBeenCalled())
  })

  it('n’invente aucune source : sans toiture ni affaire, le corps est vide', async () => {
    render(<BoutonReprendreContourAffaire calepinageId={1} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le contour de l’affaire/ }))
    await waitFor(() => expect(mocks.importerContourAo).toHaveBeenCalledWith(1, {}))
  })

  it('rappelle que SEULE la géométrie de contour voyage', () => {
    render(<BoutonReprendreContourAffaire calepinageId={1} />)
    expect(screen.getByText(/Seule la géométrie de contour est reprise/)).toBeInTheDocument()
    expect(screen.getByText(/obstacles, cotes, zones et variante retenue ne sont pas touchés/))
      .toBeInTheDocument()
  })

  it('un refus 400 s’affiche SOUS le bouton, avec le message du serveur', async () => {
    mocks.importerContourAo.mockRejectedValue({
      response: {
        status: 400,
        data: { detail: 'Cette toiture AO n’a pas d’origine géographique.' },
      },
    })
    render(<BoutonReprendreContourAffaire calepinageId={1} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le contour de l’affaire/ }))
    const bloc = await screen.findByTestId('cal-bouton-contour-affaire-refus')
    expect(bloc).toHaveTextContent('Cette toiture AO n’a pas d’origine géographique.')
    expect(within(screen.getByTestId('cal-bouton-contour-affaire')).getByRole('alert'))
      .toBe(bloc)
  })

  it('un refus nommant un CHAMP nomme ce champ, sans réécrire le message', async () => {
    mocks.importerContourAo.mockRejectedValue({
      response: { status: 400, data: { origine_geographique: ['Champ manquant.'] } },
    })
    render(<BoutonReprendreContourAffaire calepinageId={1} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le contour de l’affaire/ }))
    expect(await screen.findByTestId('cal-bouton-contour-affaire-refus'))
      .toHaveTextContent('origine_geographique : Champ manquant.')
  })

  it('un refus n’entraîne AUCUN rafraîchissement', async () => {
    const rafraichir = vi.fn()
    mocks.importerContourAo.mockRejectedValue({ response: { status: 409, data: { detail: 'Non.' } } })
    render(<BoutonReprendreContourAffaire calepinageId={1} onImporte={rafraichir} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le contour de l’affaire/ }))
    await screen.findByTestId('cal-bouton-contour-affaire-refus')
    expect(rafraichir).not.toHaveBeenCalled()
  })
})

describe('CAL242 — sens calepinage → AO (« Reprendre le tracé 3D »)', () => {
  it('appelle CAL241 sur la toiture AO, puis rafraîchit', async () => {
    const rafraichir = vi.fn().mockResolvedValue(undefined)
    render(<BoutonReprendreTrace3D toitureId={5} calepinageId={1} onImporte={rafraichir} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le tracé 3D/ }))
    await waitFor(() => expect(mocks.reprendreContour3d)
      .toHaveBeenCalledWith(5, { calepinage: 1 }))
    await waitFor(() => expect(rafraichir).toHaveBeenCalled())
  })

  it('sans calepinage connu, l’écran n’en invente pas un : le serveur résout', async () => {
    render(<BoutonReprendreTrace3D toitureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le tracé 3D/ }))
    await waitFor(() => expect(mocks.reprendreContour3d).toHaveBeenCalledWith(5, {}))
  })

  it('le refus 409 « affaire déposée/close » s’affiche TEL QUEL, sans adoucissement', async () => {
    const message = 'Conception figée : l’affaire est déposée.'
    mocks.reprendreContour3d.mockRejectedValue({ response: { status: 409, data: { detail: message } } })
    render(<BoutonReprendreTrace3D toitureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le tracé 3D/ }))
    expect(await screen.findByTestId('ao-bouton-trace-3d-refus')).toHaveTextContent(message)
  })

  it('un réseau muet le DIT — c’est le seul texte que le client écrive', async () => {
    mocks.reprendreContour3d.mockRejectedValue(new Error('network'))
    render(<BoutonReprendreTrace3D toitureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Reprendre le tracé 3D/ }))
    expect(await screen.findByTestId('ao-bouton-trace-3d-refus'))
      .toHaveTextContent(/Le serveur n’a pas répondu/)
  })

  it('rappelle lui aussi que seule la géométrie de contour voyage', () => {
    render(<BoutonReprendreTrace3D toitureId={5} />)
    expect(screen.getByText(/Seule la géométrie de contour est reprise/)).toBeInTheDocument()
  })

  it('un second clic est bloqué pendant l’appel (aucun double import)', async () => {
    let debloquer
    mocks.reprendreContour3d.mockReturnValue(new Promise((r) => { debloquer = r }))
    render(<BoutonReprendreTrace3D toitureId={5} />)
    const bouton = screen.getByRole('button', { name: /Reprendre le tracé 3D/ })
    fireEvent.click(bouton)
    await waitFor(() => expect(bouton).toBeDisabled())
    fireEvent.click(bouton)
    expect(mocks.reprendreContour3d).toHaveBeenCalledTimes(1)
    debloquer({ data: {} })
  })
})
