import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR212 — Écran admin « Périodes & bulletins » (NTEDU17). Le backend
   (PeriodeScolaireViewSet, BulletinViewSet.publier, eleves.bulletinPdf)
   était complet mais SEUL l'admin Django pouvait créer une période ou
   publier un bulletin. Vérifie : création de période, appréciation
   (create la première fois, update ensuite), publication (jamais un PATCH
   direct), et téléchargement du PDF — le tout sans admin Django. */

const {
  anneesScolaires, periodes, classes, eleves, bulletins,
} = vi.hoisted(() => ({
  anneesScolaires: { list: vi.fn() },
  periodes: { list: vi.fn(), create: vi.fn() },
  classes: { list: vi.fn() },
  eleves: { list: vi.fn(), bulletinPdf: vi.fn() },
  bulletins: { list: vi.fn(), create: vi.fn(), update: vi.fn(), publier: vi.fn() },
}))

vi.mock('../../api/educationApi', () => ({
  default: { anneesScolaires, periodes, classes, eleves, bulletins },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import { toast } from '../../ui'
import BulletinsPage from './BulletinsPage'

const PERIODE = { id: 20, libelle: 'Trimestre 1', ordre: 1 }
const CLASSE = { id: 5, nom: 'CE1-A' }
const ELEVE_SANS_BULLETIN = { id: 8, nom: 'Alami', prenom: 'Yassine', classe: 5 }
const ELEVE_AVEC_BULLETIN = { id: 9, nom: 'Bennani', prenom: 'Salma', classe: 5 }
const BULLETIN_EXISTANT = {
  id: 100, eleve: 9, periode: 20, appreciation_generale: 'Bon trimestre.',
  publie: false, date_publication: null,
}

function afficher() {
  return render(<ThemeProvider><BulletinsPage /></ThemeProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  anneesScolaires.list.mockResolvedValue({ data: [{ id: 3, libelle: '2026-2027' }] })
  periodes.list.mockResolvedValue({ data: [PERIODE] })
  classes.list.mockResolvedValue({ data: [CLASSE] })
  eleves.list.mockResolvedValue({ data: [ELEVE_SANS_BULLETIN, ELEVE_AVEC_BULLETIN] })
  bulletins.list.mockResolvedValue({ data: [BULLETIN_EXISTANT] })
  periodes.create.mockResolvedValue({ data: { id: 21 } })
  bulletins.create.mockResolvedValue({ data: { id: 101 } })
  bulletins.update.mockResolvedValue({ data: {} })
  bulletins.publier.mockResolvedValue({ data: {} })
  eleves.bulletinPdf.mockResolvedValue({ data: new Blob(['%PDF'], { type: 'application/pdf' }) })
  // jsdom ne fournit pas createObjectURL/revokeObjectURL (même garde que
  // NumeriserPage.test.jsx) — utilisés pour déclencher le téléchargement.
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:fake')
  globalThis.URL.revokeObjectURL = vi.fn()
})

describe('BulletinsPage (WIR212)', () => {
  it('rend l’écran sans planter et liste les périodes existantes', async () => {
    afficher()
    expect(await screen.findByText('Périodes & bulletins')).toBeInTheDocument()
    await waitFor(() => expect(periodes.list).toHaveBeenCalled())
    // « Trimestre 1 » apparaît à la fois dans la liste des périodes et comme
    // option du sélecteur « Période » : au moins une occurrence suffit ici.
    expect((await screen.findAllByText('Trimestre 1')).length).toBeGreaterThan(0)
  })

  it('crée une nouvelle période', async () => {
    afficher()
    await waitFor(() => expect(anneesScolaires.list).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Année scolaire'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Libellé de la période'), { target: { value: 'Trimestre 2' } })
    fireEvent.change(screen.getByLabelText('Date de début de la période'), { target: { value: '2027-01-05' } })
    fireEvent.change(screen.getByLabelText('Date de fin de la période'), { target: { value: '2027-04-01' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer/i }))

    await waitFor(() => expect(periodes.create).toHaveBeenCalledWith({
      annee_scolaire: 3, libelle: 'Trimestre 2', ordre: 1,
      date_debut: '2027-01-05', date_fin: '2027-04-01',
    }))
  })

  it('sélectionne une période et une classe puis affiche le roster avec les bulletins existants', async () => {
    afficher()
    await waitFor(() => expect(classes.list).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText('Période'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } })

    await waitFor(() => expect(bulletins.list).toHaveBeenCalledWith({ periode: '20' }))
    expect(await screen.findByText('Alami Yassine')).toBeInTheDocument()
    expect(screen.getByText('Bennani Salma')).toBeInTheDocument()
    // L'appréciation déjà saisie est PRÉ-REMPLIE (jamais un champ vide qui écraserait l'existant).
    expect(screen.getByLabelText('Appréciation de Bennani Salma')).toHaveValue('Bon trimestre.')
    expect(screen.getByLabelText('Appréciation de Alami Yassine')).toHaveValue('')
  })

  it('enregistre l’appréciation d’un élève SANS bulletin — appelle create()', async () => {
    afficher()
    fireEvent.change(await screen.findByLabelText('Période'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } })
    await screen.findByText('Alami Yassine')

    const row = screen.getByText('Alami Yassine').closest('tr')
    fireEvent.change(within(row).getByLabelText('Appréciation de Alami Yassine'), {
      target: { value: 'Excellent trimestre.' },
    })
    fireEvent.click(within(row).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(bulletins.create).toHaveBeenCalledWith({
      eleve: 8, periode: 20, appreciation_generale: 'Excellent trimestre.',
    }))
    expect(bulletins.update).not.toHaveBeenCalled()
  })

  it('enregistre l’appréciation d’un élève AVEC bulletin — appelle update(), jamais create()', async () => {
    afficher()
    fireEvent.change(await screen.findByLabelText('Période'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } })
    await screen.findByText('Bennani Salma')

    const row = screen.getByText('Bennani Salma').closest('tr')
    fireEvent.change(within(row).getByLabelText('Appréciation de Bennani Salma'), {
      target: { value: 'Bon trimestre, en progrès.' },
    })
    fireEvent.click(within(row).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(bulletins.update).toHaveBeenCalledWith(100, {
      appreciation_generale: 'Bon trimestre, en progrès.',
    }))
    expect(bulletins.create).not.toHaveBeenCalled()
  })

  it('publie le bulletin d’un élève qui en a déjà un, jamais un PATCH direct', async () => {
    afficher()
    fireEvent.change(await screen.findByLabelText('Période'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } })
    await screen.findByText('Bennani Salma')

    const row = screen.getByText('Bennani Salma').closest('tr')
    // « Brouillon » avant publication, jamais recalculé côté client.
    expect(within(row).getByText('Brouillon')).toBeInTheDocument()
    fireEvent.click(within(row).getByRole('button', { name: /Publier/i }))

    await waitFor(() => expect(bulletins.publier).toHaveBeenCalledWith(100))
    expect(bulletins.update).not.toHaveBeenCalled()
    expect(toast.success).toHaveBeenCalledWith('Bulletin publié.')
  })

  it('désactive « Publier » tant qu’aucun bulletin n’existe pour l’élève', async () => {
    afficher()
    fireEvent.change(await screen.findByLabelText('Période'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } })
    await screen.findByText('Alami Yassine')

    const row = screen.getByText('Alami Yassine').closest('tr')
    expect(within(row).getByRole('button', { name: /Publier/i })).toBeDisabled()
  })

  it('télécharge le PDF du bulletin pour la période choisie', async () => {
    afficher()
    fireEvent.change(await screen.findByLabelText('Période'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Classe'), { target: { value: '5' } })
    await screen.findByText('Alami Yassine')

    const row = screen.getByText('Alami Yassine').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /PDF/i }))

    await waitFor(() => expect(eleves.bulletinPdf).toHaveBeenCalledWith(8, '20'))
  })
})
