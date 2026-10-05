// AGR214 — volet INTERNE de la carte économie : sur l'exemple du contrat
// partagé `economie_pompage.json` (lu dans le fichier, jamais recopié).
import { describe, it, expect, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { render, screen, fireEvent } from '@testing-library/react'

import CarteEconomiePompageInterne from './CarteEconomiePompageInterne'
import {
  ECO_POMPAGE_VIDE, ecoDepuisSaisies, saisiesEconomiePompage,
} from '../../../features/ventes/quote/etudeMarcheBloc'
import { formatNumber } from '../../../lib/format'

const ICI = path.dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(path.resolve(ICI,
  '../../../../../backend/django_core/apps/ventes/contract_samples/economie_pompage.json'),
'utf8'))

const ouvrir = () => fireEvent.click(screen.getByRole('button', { name: /jamais imprimé/ }))

describe('AGR214 — volet interne', () => {
  it('porte la mention « jamais imprimé » et reste replié par défaut', () => {
    render(<CarteEconomiePompageInterne reponse={CONTRAT.exemple} eco={ECO_POMPAGE_VIDE} />)
    expect(screen.getByRole('button').textContent).toContain('jamais imprimé')
    expect(screen.getByRole('button').textContent).toContain('jamais sur un document client')
    expect(screen.queryByTestId('volet-interne-contenu')).toBeNull()
  })

  it('sans taux ⇒ « VAN non calculée : taux d’actualisation non saisi »', () => {
    render(<CarteEconomiePompageInterne reponse={CONTRAT.exemple} eco={ECO_POMPAGE_VIDE} />)
    ouvrir()
    expect(screen.getByTestId('van-interne').textContent)
      .toBe("VAN non calculée : taux d'actualisation non saisi")
  })

  it('taux sans source ⇒ erreur sous le champ source', () => {
    const eco = { ...ECO_POMPAGE_VIDE, interne: { taux_actualisation: { valeur: '8', source: '' }, pret: null } }
    render(<CarteEconomiePompageInterne reponse={CONTRAT.exemple} eco={eco} />)
    ouvrir()
    expect(screen.getByTestId('gen-eco-taux-source-erreur').textContent).toMatch(/Source obligatoire/)
  })

  it('une saisie du taux s’écrit dans les saisies internes', () => {
    const majEco = vi.fn()
    render(<CarteEconomiePompageInterne reponse={CONTRAT.exemple} eco={ECO_POMPAGE_VIDE} majEco={majEco} />)
    ouvrir()
    fireEvent.change(screen.getByLabelText("Taux d'actualisation (%)"), { target: { value: '7.5' } })
    expect(majEco).toHaveBeenCalledWith('interne', expect.objectContaining({
      taux_actualisation: { valeur: '7.5' } }))
  })

  it('aide FDA : quatre termes, base « à confirmer DPA », édition et conditions', () => {
    render(<CarteEconomiePompageInterne reponse={CONTRAT.exemple} eco={ECO_POMPAGE_VIDE} />)
    ouvrir()
    const fda = CONTRAT.exemple.vue_interne.aide_fda_indicative
    const texte = screen.getByTestId('aide-fda').textContent
    expect(texte).toContain(formatNumber(fda.montant_mad))
    expect(texte).toContain('à confirmer DPA')
    expect(texte).toContain(fda.edition)
    for (const valeur of Object.values(fda.termes)) expect(texte).toContain(formatNumber(valeur))
    expect(texte).toContain('à vérifier')
    expect(screen.getByTestId('scenario-butane').textContent)
      .toContain('repère « bouteille non subventionnée » sans source')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = etude_params identique', () => {
    const saisies = {
      ...CONTRAT.saisies_economie_pompage.exemple,
      taux_actualisation: { valeur: 8, source: 'BAM — taux directeur + prime, 2026-09' },
      pret: { principal_mad: 60000, taux_annuel_pct: 6.5, duree_mois: 48,
        differe_mois: 6, type_pret: 'amortissable', source: 'offre écrite Crédit Agricole' },
    }
    const premier = saisiesEconomiePompage(ecoDepuisSaisies(saisies))
    const second = saisiesEconomiePompage(ecoDepuisSaisies(premier))
    expect(second).toEqual(premier)
    expect(premier.taux_actualisation).toEqual(saisies.taux_actualisation)
    expect(premier.pret).toEqual(saisies.pret)
  })

  it('un taux tapé en texte part en nombre ; rien de rempli ⇒ null', () => {
    const eco = { ...ECO_POMPAGE_VIDE, energie: 'butane',
      interne: { taux_actualisation: { valeur: '7,5', source: ' BAM ' }, pret: { source: '' } } }
    const s = saisiesEconomiePompage(eco)
    expect(s.taux_actualisation).toEqual({ valeur: 7.5, source: 'BAM' })
    expect(s.pret).toBeNull()
  })
})
