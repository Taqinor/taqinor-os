// AGR213 — carte « Économie déclarée » : la réponse simulée EST l'exemple du
// contrat partagé `economie_pompage.json` (lu dans le fichier, jamais recopié).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { render, screen, waitFor } from '@testing-library/react'

const ICI = path.dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(path.resolve(ICI,
  '../../../../../backend/django_core/apps/ventes/contract_samples/economie_pompage.json'),
'utf8'))

vi.mock('../../../api/ventesApi', () => ({
  default: { economiePompagePreview: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import CarteEconomiePompage, { CarteEconomiePompageVue } from './CarteEconomiePompage'
import { construireCorpsEconomiePompage, vueCarteEconomie } from '../../../features/ventes/economiePompagePreviewPur'
import { formatNumber } from '../../../lib/format'

const ECO_BUTANE = {
  energie: 'butane', quantite: '4', unite: 'bouteille_12kg', periode: 'jour_irrigation',
  joursSemaine: '6', prix: '50', dateDeclaration: '2026-09-12', mois: [4, 5, 6, 7, 8, 9],
  entretien: '1500',
}

beforeEach(() => { vi.clearAllMocks() })

describe('AGR213 — vue client de la carte', () => {
  it('exemple « butane déclaré » : chiffres du contrat affichés tels quels', () => {
    const ex = CONTRAT.exemple
    render(<CarteEconomiePompageVue reponse={ex} />)
    expect(screen.getByTestId('depense-actuelle').textContent)
      .toContain(formatNumber(ex.depense_actuelle.annuelle_mad))
    const an1 = ex.economie.flux.find((f) => f.annee === 1)
    expect(screen.getByTestId('economie-nette').textContent).toContain(formatNumber(an1.flux_mad))
    expect(screen.getByTestId('retour-ans').textContent).toContain(`${ex.economie.retour_ans} ans`)
    expect(screen.getByTestId('cout-m3').textContent).toContain(formatNumber(ex.mad_par_m3.actuel))
    expect(screen.getByTestId('detail-declare').textContent).toContain('déclaré le 12/09')
    expect(screen.getByTestId('seuil-rentabilite').textContent)
      .toContain(formatNumber(ex.seuil_rentabilite_carburant.valeur_unitaire_mad))
    expect(screen.getAllByText(/estimation — calculée sur les chiffres déclarés/).length).toBe(1)
    expect(screen.getByTestId('remplacements').textContent)
      .toContain('garantie constructeur non renseignée')
  })

  it('exemple « rien déclaré » : motifs, aucun zéro', () => {
    render(<CarteEconomiePompageVue reponse={CONTRAT.exemple_rien_declare} />)
    expect(screen.getByTestId('depense-actuelle').textContent).toContain('non calculé')
    expect(screen.getByTestId('economie-nette').textContent).toContain('non calculé')
    expect(screen.getByTestId('motifs-non-publiable').textContent)
      .toContain('énergie actuelle non déclarée')
    expect(screen.getByTestId('omissions').textContent).toContain('prix payé non déclaré')
    expect(screen.getByTestId('carte-economie-vue').textContent).not.toMatch(/\b0 MAD/)
  })

  it('aucune clé de vue_interne affichée dans la carte', () => {
    const vue = vueCarteEconomie(CONTRAT.exemple)
    expect(JSON.stringify(vue)).not.toContain('aide_fda')
    render(<CarteEconomiePompageVue reponse={CONTRAT.exemple} />)
    const texte = screen.getByTestId('carte-economie-vue').textContent
    expect(texte).not.toContain(formatNumber(
      CONTRAT.exemple.vue_interne.aide_fda_indicative.montant_mad))
    expect(texte).not.toMatch(/FDA/)
  })

  it('corps : null tant que rien n’est servi, sinon les trois clés du contrat', () => {
    expect(construireCorpsEconomiePompage({ saisies: null, sortieEtude: {} })).toBeNull()
    expect(construireCorpsEconomiePompage({ saisies: {}, sortieEtude: null })).toBeNull()
    const corps = construireCorpsEconomiePompage({
      saisies: CONTRAT.saisies_economie_pompage.exemple, sortieEtude: { hmt: {} },
      lignes: [{ produit: 3, quantite: 1, prix_unitaire: 100, remise: 0, taux_tva: 20 }, {}],
    })
    expect(Object.keys(corps).sort()).toEqual(['lignes', 'saisies', 'sortie_etude_pompage'])
    expect(corps.lignes).toHaveLength(1)
  })

  it('la carte montée appelle le serveur et rend sa réponse', async () => {
    ventesApi.economiePompagePreview.mockResolvedValue({ data: CONTRAT.exemple })
    render(<CarteEconomiePompage eco={ECO_BUTANE} moisCalendrier={[]}
                                 sortieEtude={{ hmt: {} }} lignes={[]} />)
    await waitFor(() => expect(screen.getByTestId('carte-economie-vue')).toBeTruthy(),
      { timeout: 2000 })
    expect(ventesApi.economiePompagePreview).toHaveBeenCalledTimes(1)
    const corps = ventesApi.economiePompagePreview.mock.calls[0][0]
    expect(corps.saisies.energie_actuelle.valeur).toBe('butane')
  })
})
