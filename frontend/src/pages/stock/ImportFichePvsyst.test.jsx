import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { documentContrat, reponseContrat, fichierContrat } from '../../test/fixtures/contractSamples'

/* CALX357 — dépôt d'un fichier PVsyst depuis le formulaire produit.
   Les réponses viennent UNIQUEMENT du contrat partagé
   apps/stock/contract_samples/fiche_import_pan_ond.json (PACT13) ; les fichiers
   déposés sont les deux VRAIS fichiers pvlib committés à côté (CALX339). */

vi.mock('../../api/stockApi', () => ({
  default: { deposerFichierPvsyst: vi.fn() },
}))

import stockApi from '../../api/stockApi'
import ImportFichePvsyst from './ImportFichePvsyst.jsx'
import { LIBELLES_FICHE } from './pvondFicheTechnique'

const libelleChamp = (champ) => LIBELLES_FICHE[champ]

const DOSSIER = join(fichierContrat('stock', 'fiche_import_pan_ond'), '..', 'pvsyst')
const CONTRAT = documentContrat('stock', 'fiche_import_pan_ond')

function fichierReel(nom) {
  const octets = readFileSync(join(DOSSIER, nom))
  return new File([octets], nom, { type: 'application/octet-stream' })
}
const OND = 'CPS_SCH275KTL-DO-US-800-250kW_275kVA_1.OND'
const PAN = 'ET-M772BH550GL.PAN'

function deposer(container, file) {
  const input = container.querySelector('input[type="file"]')
  fireEvent.change(input, { target: { files: [file] } })
}

beforeEach(() => {
  stockApi.deposerFichierPvsyst.mockReset()
})

describe('ImportFichePvsyst (CALX357)', () => {
  it('le fichier .OND réel donne un aperçu à trois listes, sans rien écrire', async () => {
    stockApi.deposerFichierPvsyst.mockResolvedValue(reponseContrat('stock', 'fiche_import_pan_ond'))
    const onApplique = vi.fn()
    const { container } = render(<ImportFichePvsyst produitId={12} onApplique={onApplique} />)
    const fichier = fichierReel(OND)
    expect(fichier.size).toBe(3284)
    deposer(container, fichier)

    await screen.findByTestId('pvsyst-apercu')
    // Aperçu seul : appelé une fois, SANS confirmer.
    expect(stockApi.deposerFichierPvsyst).toHaveBeenCalledTimes(1)
    expect(stockApi.deposerFichierPvsyst).toHaveBeenCalledWith(12, fichier)
    expect(onApplique).not.toHaveBeenCalled()

    const repris = screen.getByTestId('pvsyst-repris')
    expect(within(repris).getByText(/Champs repris \(9\)/)).toBeTruthy()
    expect(within(repris).getByText(`${libelleChamp('ond_ac_kw')} : 250.00`)).toBeTruthy()
    const nonUtilises = screen.getByTestId('pvsyst-non-utilises')
    expect(within(nonUtilises).getByText('IMaxDC')).toBeTruthy()
    const absents = screen.getByTestId('pvsyst-absents')
    expect(within(absents).getByText(libelleChamp('ond_i_max_mppt_a'))).toBeTruthy()
  })

  it('les trois listes restent affichées, même vides, avec leur libellé', async () => {
    stockApi.deposerFichierPvsyst.mockResolvedValue(
      reponseContrat('stock', 'fiche_import_pan_ond', 'exemple_module'))
    const { container } = render(<ImportFichePvsyst produitId={3} />)
    deposer(container, fichierReel(PAN))
    const absents = await screen.findByTestId('pvsyst-absents')
    expect(CONTRAT.exemple_module.champs_attendus_absents).toEqual([])
    expect(within(absents).getByText(/Champs attendus absents \(0\)/)).toBeTruthy()
    expect(within(absents).getByText('Aucun')).toBeTruthy()
    expect(screen.getByTestId('pvsyst-repris')).toBeTruthy()
    expect(screen.getByTestId('pvsyst-non-utilises')).toBeTruthy()
  })

  it('un champ déjà saisi est annoncé conservé', async () => {
    stockApi.deposerFichierPvsyst.mockResolvedValue(
      reponseContrat('stock', 'fiche_import_pan_ond', 'exemple_module_pmax_deja_saisi'))
    const { container } = render(<ImportFichePvsyst produitId={3} />)
    deposer(container, fichierReel(PAN))
    const note = await screen.findByTestId('pvsyst-deja-saisis')
    expect(note.textContent).toContain(libelleChamp('pmax_wc'))
  })

  it("n'écrit qu'après « Appliquer à la fiche » (confirmer=true)", async () => {
    stockApi.deposerFichierPvsyst
      .mockResolvedValueOnce(reponseContrat('stock', 'fiche_import_pan_ond'))
      .mockResolvedValueOnce(reponseContrat('stock', 'fiche_import_pan_ond', 'exemple_confirme'))
    const onApplique = vi.fn()
    const { container } = render(<ImportFichePvsyst produitId={12} onApplique={onApplique} />)
    const fichier = fichierReel(OND)
    deposer(container, fichier)
    fireEvent.click(await screen.findByRole('button', { name: 'Appliquer à la fiche' }))

    await screen.findByTestId('pvsyst-resultat')
    expect(stockApi.deposerFichierPvsyst).toHaveBeenLastCalledWith(12, fichier, true)
    expect(onApplique).toHaveBeenCalledWith(CONTRAT.exemple_confirme.fiche)
    expect(screen.getByTestId('pvsyst-resultat').textContent)
      .toContain(`${CONTRAT.exemple_confirme.ecrits.length} champ(s)`)
  })

  it('un refus serveur s’affiche sous le dépôt et le bandeau le nomme', async () => {
    const refus = CONTRAT.exemple_refus
    stockApi.deposerFichierPvsyst.mockRejectedValue({ response: { status: 400, data: refus } })
    const { container } = render(<ImportFichePvsyst produitId={12} />)
    deposer(container, new File(['rien de PVsyst ici'], 'faux.pan'))

    const erreur = await screen.findByTestId('pvsyst-erreur')
    expect(erreur.textContent).toContain('Ligne 1')
    expect(screen.getByTestId('pvsyst-bandeau').textContent).toContain('faux.pan')
    expect(screen.queryByTestId('pvsyst-apercu')).toBeNull()
  })

  it('un fichier qui n’est ni .PAN ni .OND est refusé sans appel serveur', async () => {
    const { container } = render(<ImportFichePvsyst produitId={12} />)
    deposer(container, new File(['x'], 'fiche.pdf', { type: 'application/pdf' }))
    await waitFor(() => expect(screen.getByTestId('pvsyst-bandeau').textContent).toContain('fiche.pdf'))
    expect(stockApi.deposerFichierPvsyst).not.toHaveBeenCalled()
  })
})
