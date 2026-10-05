/* CALX360 — l'onglet « Fixation » de l'atelier.

   Tout ce qui est affirmé ici l'est sur les échantillons COMMITTÉS
   `calepinage_fixation_bom.json` (contrat CALX335) et `calepinage_sorties.json`
   (CALX19, pour le téléchargement du classeur) — jamais une charge utile
   écrite à la main.

   Ce qui est prouvé :
   1. le système appliqué et ses lignes sont recopiés du serveur ;
   2. une ligne non calculable affiche le `manquant` SERVEUR, jamais un tiret
      muet ni un zéro ;
   3. un catalogue vide affiche l'état vide nommant le réglage à remplir ;
   4. ACAL82 — « Appliquer » PERSISTE le choix (`POST fixation/`) puis relit
      `bom-fixation/` SANS paramètre ; le champ reprend le système que le
      serveur dit persisté (`systeme_source: 'calepinage'`) ;
   5. le téléchargement du classeur utilise l'`endpoint` de l'inventaire des
      sorties TEL QUEL, jamais un chemin reconstruit. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      bomFixation: vi.fn(), sorties: vi.fn(), telechargerSortie: vi.fn(), appliquerFixation: vi.fn(),
    },
  },
}))
vi.mock('../../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(),
  filenameFromResponse: vi.fn((res, repli) => repli),
}))

import calepinageApi from '../../../api/calepinageApi'
import { downloadBlob } from '../../../utils/downloadBlob'
import Fixation from './Fixation'

const echantillon = (variante) => reponseContrat('calepinage', 'calepinage_fixation_bom', variante).data
const sortiesEchantillon = (variante) => reponseContrat('calepinage', 'calepinage_sorties', variante).data

const servir = (variante) => {
  calepinageApi.calepinages.bomFixation
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_fixation_bom', variante))
}
const servirSorties = (variante) => {
  calepinageApi.calepinages.sorties
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_sorties', variante))
}

const rendre = () => render(
  <MemoryRouter><Fixation calepinageId={41} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('Fixation (CALX360) — système et lignes', () => {
  it('affiche le système appliqué et chaque ligne, sans invention', async () => {
    servir('exemple')
    servirSorties('exemple')
    rendre()
    await screen.findByTestId('calx360-panneau')

    const exemple = echantillon('exemple')
    expect(screen.getByTestId('calx360-systeme-applique'))
      .toHaveTextContent(exemple.systeme.code)
    exemple.lignes.forEach((ligne) => {
      const row = screen.getByTestId(`calx360-ligne-${ligne.role}`)
      expect(row).toHaveTextContent(ligne.composant)
    })
  })

  it('une ligne non calculable affiche le « manquant » SERVEUR, jamais un tiret muet', async () => {
    servir('exemple')
    servirSorties('exemple')
    rendre()
    await screen.findByTestId('calx360-panneau')

    const exemple = echantillon('exemple')
    const ligneManquante = exemple.lignes.find((l) => l.quantite === null)
    expect(ligneManquante).toBeTruthy()
    const cellule = screen.getByTestId(`calx360-quantite-${ligneManquante.role}`)
    expect(cellule).toHaveTextContent(ligneManquante.manquant)
    expect(cellule.textContent).not.toBe('—')
  })
})

describe('Fixation (CALX360) — catalogue vide', () => {
  it('affiche l’état vide nommant le réglage à remplir', async () => {
    servir('exemple_vide')
    servirSorties('exemple_vide')
    rendre()
    await screen.findByTestId('calx360-panneau')

    const vide = echantillon('exemple_vide')
    expect(screen.getByTestId('calx360-systeme-absent')).toBeInTheDocument()
    expect(screen.getByTestId('calx360-vide')).toHaveTextContent(vide.refus[0].message)
    expect(screen.getByTestId('calx360-refus-0')).toHaveTextContent(vide.refus[0].message)
  })
})

describe('Fixation (ACAL82) — choix du système persisté', () => {
  it('« Appliquer » → POST fixation/ ; remonté avec systeme_source calepinage → S2 sélectionné', async () => {
    const parametre = reponseContrat('calepinage', 'calepinage_fixation_bom', 'exemple_parametre')
    const persiste = reponseContrat('calepinage', 'calepinage_fixation_bom', 'exemple')
    const post = exempleContrat('calepinage', 'calepinage_fixation_bom', 'fixation_post')
    calepinageApi.calepinages.bomFixation
      .mockResolvedValueOnce(parametre)
      .mockResolvedValue(persiste)
    calepinageApi.calepinages.appliquerFixation.mockResolvedValue({ data: post.exemple })
    servirSorties('exemple')
    rendre()
    await screen.findByTestId('calx360-panneau')

    // Lecture sans paramètre : le serveur décide (jamais `?systeme=`).
    expect(calepinageApi.calepinages.bomFixation).toHaveBeenCalledWith(41)
    // Source « parametre » : rien n'est persisté, le champ est vide.
    expect(screen.getByTestId('acal82-champ-systeme')).toHaveValue('')

    const choisi = String(post.corps.systeme_id)
    fireEvent.change(screen.getByTestId('acal82-champ-systeme'), { target: { value: choisi } })
    fireEvent.click(screen.getByTestId('calx360-appliquer-systeme'))

    await waitFor(() => expect(calepinageApi.calepinages.appliquerFixation)
      .toHaveBeenCalledWith(41, { systeme_id: choisi }))
    await waitFor(() => expect(calepinageApi.calepinages.bomFixation).toHaveBeenCalledTimes(2))
    calepinageApi.calepinages.bomFixation.mock.calls.forEach((appel) => {
      expect(appel).toEqual([41])
    })
    const champ = await screen.findByTestId('acal82-champ-systeme')
    expect(champ).toHaveValue(String(persiste.data.systeme.id))
  })

  it('au rechargement, le champ montre le système PERSISTÉ lu du serveur', async () => {
    servir('exemple')
    servirSorties('exemple')
    rendre()
    await screen.findByTestId('calx360-panneau')

    const exemple = echantillon('exemple')
    expect(exemple.systeme_source).toBe('calepinage')
    expect(screen.getByTestId('acal82-champ-systeme')).toHaveValue(String(exemple.systeme.id))
  })

  it('un refus 400 du serveur est affiché en nommant son motif', async () => {
    servir('exemple_parametre')
    servirSorties('exemple')
    calepinageApi.calepinages.appliquerFixation.mockRejectedValue({
      response: { data: { systeme_id: 'Système de fixation introuvable : « 999 ».' } },
    })
    rendre()
    await screen.findByTestId('calx360-panneau')
    fireEvent.change(screen.getByTestId('acal82-champ-systeme'), { target: { value: '999' } })
    fireEvent.click(screen.getByTestId('calx360-appliquer-systeme'))

    expect(await screen.findByTestId('acal82-erreur-application'))
      .toHaveTextContent('introuvable')
  })
})

describe('Fixation (CALX360) — téléchargement du classeur', () => {
  it('télécharge l’endpoint de l’inventaire des sorties TEL QUEL', async () => {
    servir('exemple')
    servirSorties('exemple')
    const sorties = sortiesEchantillon('exemple')
    const entreeClasseur = sorties.sorties.find((s) => s.code === 'tableur_xlsx')
    const blob = new Blob(['x'])
    calepinageApi.calepinages.telechargerSortie.mockResolvedValue({ data: blob, headers: {} })

    rendre()
    await screen.findByTestId('calx360-telecharger')

    fireEvent.click(screen.getByTestId('calx360-telecharger'))

    await waitFor(() => expect(calepinageApi.calepinages.telechargerSortie)
      .toHaveBeenCalledWith(entreeClasseur.endpoint))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalledTimes(1))
    expect(downloadBlob.mock.calls[0][0]).toBe(blob)
  })

  it('un classeur indisponible affiche le motif SERVEUR, aucun bouton', async () => {
    servir('exemple')
    servirSorties('exemple_vide')
    rendre()
    await screen.findByTestId('calx360-panneau')

    const sorties = sortiesEchantillon('exemple_vide')
    const entreeClasseur = sorties.sorties.find((s) => s.code === 'tableur_xlsx')
    expect(screen.queryByTestId('calx360-telecharger')).toBeNull()
    expect(screen.getByTestId('calx360-telechargement-indisponible'))
      .toHaveTextContent(entreeClasseur.motif_indisponible)
  })
})
