import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CALX19 — le panneau « Documents » lit l'inventaire des sorties, RIEN
   D'AUTRE.
   ----------------------------------------------------------------------------
   PACT10/PACT13 — AUCUNE CHARGE UTILE RETAPÉE ICI : les payloads viennent du
   document committé `backend/django_core/apps/calepinage/contract_samples/
   calepinage_sorties.json`, le MÊME que le test backend
   `apps/calepinage/tests/test_cal175_sorties.py` affirme. Un mock écrit à la
   main serait une DEUXIÈME source de vérité (l'incident « AO — Tableau de
   bord » du 03/08/2026, exactement ce que ces helpers empêchent).
   ========================================================================== */

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      sorties: vi.fn(),
      telechargerSortie: vi.fn(),
    },
  },
}))
vi.mock('../../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(),
  // Reprend la RÈGLE du vrai helper (lire `Content-Disposition`, jamais un
  // nom inventé) — assez fidèle pour prouver que le nom AFFICHÉ est bien
  // celui posé par le serveur, jamais un nom écrit en dur côté écran.
  filenameFromResponse: vi.fn((res, repli) => {
    const cd = res?.headers?.['content-disposition'] || ''
    return /filename="([^"]+)"/.exec(cd)?.[1] || `${repli}.bin`
  }),
}))

import calepinageApi from '../../../api/calepinageApi'
import { downloadBlob, filenameFromResponse } from '../../../utils/downloadBlob'
import PanneauDocuments from './PanneauDocuments'

const APP = 'calepinage'
const NOM = 'calepinage_sorties'

const sortie = (variante, code) =>
  exempleContrat(APP, NOM, variante).sorties.find((s) => s.code === code)

const servirInventaire = (variante = 'exemple') => {
  calepinageApi.calepinages.sorties.mockResolvedValue(reponseContrat(APP, NOM, variante))
}

const rendre = (calepinageId = 41) => render(
  <MemoryRouter><PanneauDocuments calepinageId={calepinageId} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PanneauDocuments (CALX19)', () => {
  it('le contrat committé porte bien les deux sorties branchées ici', () => {
    expect(sortie('exemple', 'planche_pdf').endpoint)
      .toBe('/api/django/calepinage/calepinages/41/planche.pdf/')
    expect(sortie('exemple', 'planche_svg').endpoint)
      .toBe('/api/django/calepinage/calepinages/41/planche.svg/')
  })

  it('sans conception (exemple_vide) : aucun bouton n’est actif, chaque motif est lisible', async () => {
    servirInventaire('exemple_vide')

    rendre()

    const boutonPdf = await screen.findByTestId('cal-doc-bouton-planche_pdf')
    const boutonSvg = await screen.findByTestId('cal-doc-bouton-planche_svg')
    expect(boutonPdf).toBeDisabled()
    expect(boutonSvg).toBeDisabled()

    expect(screen.getByTestId('cal-doc-motif-planche_pdf'))
      .toHaveTextContent(sortie('exemple_vide', 'planche_pdf').motif_indisponible)
    expect(screen.getByTestId('cal-doc-motif-planche_svg'))
      .toHaveTextContent(sortie('exemple_vide', 'planche_svg').motif_indisponible)
  })

  it('avec conception : les DEUX boutons branchés sont actifs et rien d’autre n’apparaît', async () => {
    servirInventaire('exemple')

    rendre()

    await screen.findByTestId('cal-doc-bouton-planche_pdf')
    expect(screen.getByTestId('cal-doc-bouton-planche_pdf')).toBeEnabled()
    expect(screen.getByTestId('cal-doc-bouton-planche_svg')).toBeEnabled()
    // `planche_png` (conversion NAVIGATEUR du SVG frère) et `image_3d` (pas
    // un fichier — son URL voyage dans l'agrégat de détail) ne sont JAMAIS
    // des téléchargements génériques de ce panneau (voir le commentaire de
    // `CODES_GERES`) : un bouton qui ne ferait rien au clic n'est jamais rendu.
    expect(screen.queryByTestId('cal-doc-sortie-planche_png')).toBeNull()
    expect(screen.queryByTestId('cal-doc-sortie-image_3d')).toBeNull()
  })

  it('clic sur « Télécharger » (planche PDF) : télécharge via l’endpoint du serveur', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({
      data: new Blob(['%PDF-1.4']),
      headers: { 'content-disposition': 'attachment; filename="planche.pdf"' },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-planche_pdf'))

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1))
    expect(calepinageApi.calepinages.telechargerSortie)
      .toHaveBeenCalledWith(sortie('exemple', 'planche_pdf').endpoint, undefined)
    expect(filenameFromResponse).toHaveBeenCalled()
  })

  it('refus serveur au téléchargement : le motif s’affiche SOUS la carte concernée', async () => {
    servirInventaire('exemple')
    const corpsErreur = { roof_layout: 'Aucune conception enregistrée.' }
    calepinageApi.calepinages.telechargerSortie.mockRejectedValue({
      response: {
        status: 400,
        data: new Blob([JSON.stringify(corpsErreur)], { type: 'application/json' }),
      },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-planche_svg'))

    const carte = await screen.findByTestId('cal-doc-sortie-planche_svg')
    await waitFor(() => {
      expect(carte.querySelector('[data-testid="cal-doc-erreurs"]'))
        .toHaveTextContent('Aucune conception enregistrée.')
    })
    // Le refus reste SOUS sa carte : l'autre sortie n'affiche rien.
    expect(screen.queryByTestId('cal-doc-sortie-planche_pdf')
      ?.querySelector('[data-testid="cal-doc-erreurs"]')).toBeNull()
    expect(downloadBlob).not.toHaveBeenCalled()
  })
})

describe('PanneauDocuments — les trois plans (CALX20)', () => {
  it('les trois boutons apparaissent', async () => {
    servirInventaire('exemple')

    rendre()

    expect(await screen.findByTestId('cal-doc-sortie-plan_pose_pdf')).toBeTruthy()
    expect(screen.getByTestId('cal-doc-sortie-plan_toiture_pdf')).toBeTruthy()
    expect(screen.getByTestId('cal-doc-sortie-plan_masse_pdf')).toBeTruthy()
  })

  it('le plan de masse est inactif sans parcelle et son motif nomme le champ', async () => {
    servirInventaire('exemple') // le contrat committé : plan_masse_pdf indisponible ici

    rendre()

    const bouton = await screen.findByTestId('cal-doc-bouton-plan_masse_pdf')
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('cal-doc-motif-plan_masse_pdf'))
      .toHaveTextContent(/parcelle/)
    // Les deux autres plans, eux, sont actifs — seul celui qui manque de
    // parcelle tombe.
    expect(screen.getByTestId('cal-doc-bouton-plan_pose_pdf')).toBeEnabled()
    expect(screen.getByTestId('cal-doc-bouton-plan_toiture_pdf')).toBeEnabled()
  })

  it('un téléchargement pose le nom de fichier RENDU PAR LE SERVEUR', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({
      data: new Blob(['%PDF-1.4']),
      headers: { 'content-disposition': 'attachment; filename="plan-pose-calepinage-41.pdf"' },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-plan_pose_pdf'))

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1))
    // Le nom livré à `downloadBlob` est CELUI DU SERVEUR, jamais un nom
    // écrit en dur côté écran (`filenameFromResponse` lit `Content-Disposition`).
    expect(downloadBlob.mock.calls[0][1]).toBe('plan-pose-calepinage-41.pdf')
  })
})

describe('PanneauDocuments — la note de calcul (CALX21)', () => {
  it('sans simulation (exemple_vide) : le bouton est inactif, le motif est lisible', async () => {
    servirInventaire('exemple_vide')

    rendre()

    const bouton = await screen.findByTestId('cal-doc-bouton-note_calcul_pdf')
    expect(bouton).toBeDisabled()
    expect(screen.getByTestId('cal-doc-motif-note_calcul_pdf'))
      .toHaveTextContent(sortie('exemple_vide', 'note_calcul_pdf').motif_indisponible)
  })

  it('résultat partiel refusé : la liste NOMMÉE des valeurs manquantes s’affiche sous le bouton, aucun montant', async () => {
    servirInventaire('exemple') // note_calcul_pdf disponible ici (résultat présent)
    calepinageApi.calepinages.telechargerSortie.mockRejectedValue({
      response: {
        status: 400,
        data: new Blob([JSON.stringify({
          'production.total.p50_kwh':
            'Note de calcul : la grandeur « production annuelle P50 (kWh) » '
            + '(production.total.p50_kwh) est absente du résultat du moteur.',
        })], { type: 'application/json' }),
      },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-note_calcul_pdf'))

    const carte = await screen.findByTestId('cal-doc-sortie-note_calcul_pdf')
    await waitFor(() => {
      const erreurs = carte.querySelector('[data-testid="cal-doc-erreurs"]')
      expect(erreurs).toHaveTextContent('production.total.p50_kwh')
      expect(erreurs).toHaveTextContent('production annuelle P50')
      // Pièce technique : aucun montant ne doit apparaître dans ce texte.
      expect(erreurs.textContent).not.toMatch(/\bMAD\b|€|\bDH\b/)
    })
  })

  it('après simulation (résultat complet) : le téléchargement part', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({
      data: new Blob(['%PDF-1.4']),
      headers: { 'content-disposition': 'attachment; filename="note-calcul-41.pdf"' },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-note_calcul_pdf'))

    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1))
    expect(downloadBlob.mock.calls[0][1]).toBe('note-calcul-41.pdf')
  })
})

describe('PanneauDocuments — export DXF et export XLSX (CALX22)', () => {
  it('les deux boutons apparaissent, chacun avec sa description', async () => {
    servirInventaire('exemple')

    rendre()

    expect(await screen.findByTestId('cal-doc-sortie-dxf')).toBeTruthy()
    expect(screen.getByTestId('cal-doc-description-dxf'))
      .toHaveTextContent('TOITURE, OBSTACLES, MODULES, COTES')
    expect(screen.getByTestId('cal-doc-sortie-tableur_xlsx')).toBeTruthy()
    expect(screen.getByTestId('cal-doc-description-tableur_xlsx'))
      .toHaveTextContent('Modules, Chaînes, Nomenclature')
  })

  it('un refus serveur sur le DXF s’affiche SOUS son bouton, jamais en tête de panneau', async () => {
    servirInventaire('exemple')
    calepinageApi.calepinages.telechargerSortie.mockRejectedValue({
      response: {
        status: 400,
        data: new Blob([JSON.stringify({
          roof_layout: 'Aucune conception enregistrée : la géométrie exportée serait vide.',
        })], { type: 'application/json' }),
      },
    })
    const utilisateur = userEvent.setup()

    rendre()
    await utilisateur.click(await screen.findByTestId('cal-doc-bouton-dxf'))

    const carteDxf = await screen.findByTestId('cal-doc-sortie-dxf')
    await waitFor(() => {
      expect(carteDxf.querySelector('[data-testid="cal-doc-erreurs"]'))
        .toHaveTextContent('géométrie exportée serait vide')
    })
    // La carte XLSX voisine, elle, ne porte AUCUNE erreur : le refus reste
    // localisé à sa propre carte.
    expect(screen.getByTestId('cal-doc-sortie-tableur_xlsx')
      .querySelector('[data-testid="cal-doc-erreurs"]')).toBeNull()
    expect(screen.queryByTestId('cal-doc-erreur')).toBeNull() // pas de bandeau de tête
  })
})
