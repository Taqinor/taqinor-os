// ALEA71 (D-ACAL-97, contrôle C4-E7) — la carte « Conception » de la fiche du
// lead LIT le moteur unique (`GET ventes/conception/<lead>/`) et n'en calcule
// rien. Les réponses mockées sont celles du contrat committé
// `conception_lead.json` (PACT10), jamais écrites à la main.
// Nouveau fichier car : composant neuf.
//
// Run : npx vitest run --pool=threads --maxWorkers=1 src/features/crm/workspace/CarteConception.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: { getConceptionLead: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import CarteConception from './CarteConception'

const CONCEPTION = exempleContrat('ventes', 'conception_lead')
const clone = (o) => JSON.parse(JSON.stringify(o))
const introuvable = () => Object.assign(new Error('404'), { response: { status: 404 } })
const rendre = (props = {}) => render(
  <CarteConception leadId={1} delaiRelectureMs={5} maxRelectures={3} {...props} />,
)
const texte = () => screen.getByTestId('carte-conception').textContent
const sansEspaces = (s) => s.replace(/\s/g, '')
const fr = (n) => sansEspaces(new Intl.NumberFormat('fr-FR').format(n))

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
})

describe('ALEA71 — carte « Conception » de la fiche du lead', () => {
  it('lit les valeurs de la route : taille, production, économies, retour, source du prix', async () => {
    rendre()
    await screen.findByTestId('carte-conception')
    expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(1)
    // Les deux options du contrat, chacune avec SES valeurs servies.
    for (const [option, v] of Object.entries(CONCEPTION.valeurs)) {
      const colonne = screen.getByTestId(`carte-conception-option-${option}`).textContent
      expect(colonne).toContain(`${v.nb_panneaux.valeur} panneaux`)
      expect(sansEspaces(colonne)).toContain(`${String(v.puissance_kwc.valeur).replace('.', ',')}kWc`)
      expect(sansEspaces(colonne)).toContain(fr(v.production_annuelle.valeur))
      expect(sansEspaces(colonne)).toContain(fr(v.economies_annuelles.valeur))
      expect(colonne).toContain(`${v.payback.valeur} ans`)
    }
    expect(texte()).toContain(`d'après le devis ${CONCEPTION.payback_devis.devis_ref}`)
  })

  it('dit chaque supposition avec son champ, et l\'historique « Recalculé le … »', async () => {
    rendre()
    await screen.findByTestId('carte-conception')
    for (const s of CONCEPTION.suppositions) {
      expect(texte()).toContain(s.message)
      expect(screen.getByTestId(`carte-conception-supposition-${s.champ}`)).toBeTruthy()
    }
    expect(screen.getByTestId('carte-conception-historique').textContent)
      .toContain(CONCEPTION.declencheur.raison)
  })

  it('« Recalcul en cours » quand la version est périmée, avec les valeurs gardées', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: { ...clone(CONCEPTION), perimee: true } })
    rendre({ maxRelectures: 0 })
    await screen.findByTestId('carte-conception')
    expect(texte()).toContain('Recalcul en cours')
    expect(texte()).toContain(`${CONCEPTION.valeurs.sans.nb_panneaux.valeur} panneaux`)
  })

  it('lead sans conception rangée (404) : « Conception en cours de calcul… », relue puis affichée', async () => {
    ventesApi.getConceptionLead
      .mockRejectedValueOnce(introuvable())
      .mockRejectedValueOnce(introuvable())
      .mockResolvedValue({ data: CONCEPTION })
    rendre()
    expect((await screen.findByTestId('carte-conception-attente')).textContent)
      .toContain('Conception en cours de calcul…')
    await waitFor(() => expect(screen.getByTestId('carte-conception-option-avec')).toBeTruthy())
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(3)
    expect(screen.queryByTestId('carte-conception-attente')).toBeNull()
  })

  it('la relecture est BORNÉE : jamais d\'appel sans fin', async () => {
    ventesApi.getConceptionLead.mockRejectedValue(introuvable())
    rendre({ maxRelectures: 2 })
    await waitFor(() => expect(screen.getByTestId('carte-conception-sans-conception')).toBeTruthy())
    await new Promise((r) => setTimeout(r, 60))
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(3) // 1 lecture + 2 relectures
  })

  it('un refus nomme le champ à remplir, jamais des zéros', async () => {
    const refus = exempleContrat('ventes', 'conception_lead', 'exemple_refus')
    ventesApi.getConceptionLead.mockResolvedValue({ data: refus })
    rendre()
    const carte = await screen.findByTestId('carte-conception')
    expect(carte.textContent).toContain(refus.refus.message)
    expect(screen.getByTestId('carte-conception-refus').textContent).toContain(refus.refus.champ)
    expect(screen.queryByTestId('carte-conception-option-sans')).toBeNull()
    expect(carte.textContent).not.toMatch(/\b0 (panneaux|kWc|ans)/)
  })

  it('payback nul : la phrase du serveur, puis « d\'après le devis DEV-… » une fois un devis rangé', async () => {
    const sansDevis = clone(CONCEPTION)
    for (const o of Object.values(sansDevis.valeurs)) o.payback = { valeur: null, unite: 'ans', source: 'devis' }
    sansDevis.payback_devis = { devis_ref: null, motif: 'retour sur investissement : après un premier devis' }
    ventesApi.getConceptionLead.mockResolvedValue({ data: sansDevis })
    const { unmount } = rendre()
    await screen.findByTestId('carte-conception')
    expect(texte()).toContain('retour sur investissement : après un premier devis')
    expect(texte()).not.toContain("d'après le devis")
    unmount()
    ventesApi.getConceptionLead.mockResolvedValue({ data: CONCEPTION })
    rendre()
    await screen.findByTestId('carte-conception')
    expect(texte()).toContain(`d'après le devis ${CONCEPTION.payback_devis.devis_ref}`)
  })

  it('fiche technique incomplète : la phrase `non_calcule` est une supposition à corriger, pas une erreur', async () => {
    const phrase = 'Fiche technique de l’onduleur incomplète : renseigner la tension MPPT maximale.'
    const incomplet = clone(CONCEPTION)
    incomplet.valeurs.sans.verdicts.valeur.non_calcule = phrase
    ventesApi.getConceptionLead.mockResolvedValue({ data: incomplet })
    rendre()
    await screen.findByTestId('carte-conception')
    const ligne = screen.getByTestId('carte-conception-non-calcule')
    expect(ligne.textContent).toContain(phrase)
    expect(ligne.closest('[role="alert"]')).toBeNull()
  })

  it('une seule option servie : pas de seconde colonne vide', async () => {
    const industriel = exempleContrat('ventes', 'conception_lead', 'exemple_industriel')
    ventesApi.getConceptionLead.mockResolvedValue({ data: industriel })
    rendre()
    await screen.findByTestId('carte-conception')
    expect(screen.getByTestId('carte-conception-option-sans')).toBeTruthy()
    expect(screen.queryByTestId('carte-conception-option-avec')).toBeNull()
    expect(document.querySelectorAll('[data-testid^="carte-conception-option-"]').length).toBe(1)
  })

  it('erreur autre que 404 : la carte le dit sans casser la fiche', async () => {
    ventesApi.getConceptionLead.mockRejectedValue(
      Object.assign(new Error('x'), { response: { status: 500 } }))
    rendre()
    expect((await screen.findByTestId('carte-conception-indisponible')).textContent)
      .toContain('indisponible')
  })
})
