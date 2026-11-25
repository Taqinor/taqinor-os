// AGEN11 (D-ACAL-97, contrôle C4-E7) — l'aperçu de l'écran devis (production,
// économies, payback) vient du MOTEUR UNIQUE : la conception rangée du lead
// (`GET conception/<lead>/`) puis l'aperçu sans écriture de ce qui est tapé
// (`POST conception/apercu/`, ADEV152), « Calcul en cours… » pendant l'appel ;
// le payback affiché est celui SERVI (devis de référence, comme le PDF), jamais
// un cashflow refait dans le navigateur. La saisie reste libre : le nombre
// tapé part tel quel, jamais arrondi.
//
// L'écran RÉEL est rendu en édition (`?edit=`) ; la valeur lue est l'ancre
// QA-FIGURES `data-figure` — aucune lecture de source. Les réponses mockées
// sont celles du contrat committé `conception_lead.json` (PACT10).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorPaybackMoteur.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { act, fireEvent, render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { exempleContrat, documentContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock({
    getLead: vi.fn(() => Promise.reject(new Error('sans lead'))),
}))
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    getPrixApplicable: vi.fn(),
    // Le jumeau horaire ne répond jamais : seules les routes du moteur unique servent.
    postEtudeHorairePreview: vi.fn(() => new Promise(() => {})),
    getConceptionLead: vi.fn(),
    apercuConception: vi.fn(),
}))
// AGEN13 — le calcul local (`calc/roi.js`) n'existe plus : sa disparition est
// épinglée par `features/ventes/solar.test.mjs` (cas AGEN13).

import ventesApi from '../../api/ventesApi'
import stockApi from '../../api/stockApi'
import DevisGenerator from './DevisGenerator'
import {
  ONDULEUR, PANNEAU, declarerBeforeEachDevis, ligneProduit, lignesResidentielles, makeDevisStore,
} from './devisGenerator.testHelpers.jsx'
import { reunirOptions } from './generator/hooks/useConceptionEcran'

const RANGEE = exempleContrat('ventes', 'conception_lead')
const APERCU = documentContrat('ventes', 'conception_lead').apercu.reponse
//: Un retour en années au format de l'écran (dixième, virgule française).
const ans = (v) => v.toFixed(1).replace('.', ',')
// L'aperçu sur l'investissement des lignes de l'écran : son payback diffère de la version rangée.
const APERCU_SUR_LES_LIGNES = { ...APERCU, valeurs: { sans: { ...APERCU.valeurs.sans,
  payback: { valeur: 4.2, unite: 'ans', source: 'devis' } } } }
// Sans investissement dans le corps, le serveur ne sert aucun payback.
const APERCU_SANS_PRIX = { ...APERCU, valeurs: { sans: { ...APERCU.valeurs.sans,
  payback: { valeur: null, unite: 'ans', source: 'moteur' } } } }

function devisRouvert(lead) {
  return {
    data: {
      id: 336, reference: 'DEV-202609-0201', statut: 'brouillon', modifiable: true, raison_non_modifiable: '',
      revision_possible: false, is_active: true, lead, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: lignesResidentielles(PANNEAU, ONDULEUR),
    },
  }
}

// E7d — un onduleur hybride et une batterie du catalogue (option « avec » des lignes).
const HYBRIDE = { id: 103, nom: 'Onduleur hybride Deye 5kW Monophasé', prix_vente: 14000, tva: 20, is_archived: false }
const BATTERIE = { id: 104, nom: 'Batterie Dyness 5 kWh', prix_vente: 16000, tva: 20, is_archived: false }

declarerBeforeEachDevis({ stockApi, ventesApi, produits: [PANNEAU, ONDULEUR, HYBRIDE, BATTERIE], devis: () => devisRouvert(RANGEE.lead), localStorage: true })

function renderEdition() {
  return render(
    <Provider store={makeDevisStore('normal', 'Commercial')}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=336']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

const figure = (container, nom) => container
  .querySelector(`[data-figure="${nom}"][data-figure-option="sans"], [data-figure="${nom}"]:not([data-figure-option])`)
  ?.getAttribute('data-figure-value') ?? null

describe('AGEN11 — l’aperçu de l’écran devis vient du moteur unique', () => {
  it('avec lead : la conception rangée, puis l’aperçu de la saisie ; payback de l’aperçu ; saisie non arrondie', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockImplementation((corps) => Promise.resolve({
      data: corps?.investissement ? APERCU_SUR_LES_LIGNES : APERCU }))
    const { container } = renderEdition()

    await waitFor(() => expect(ventesApi.getConceptionLead).toHaveBeenCalledWith(String(RANGEE.lead)), { timeout: 5000 })
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    const hiver = container.querySelector('#gen-hiver')
    await act(async () => { fireEvent.change(hiver, { target: { value: '1400.5' } }) })
    expect(hiver.value).toBe('1400.5')  // jamais arrondi ni refusé
    await waitFor(() => {
      const corps = ventesApi.apercuConception.mock.calls.at(-1)?.[0]
      expect(corps?.lead).toBe(RANGEE.lead)
      expect(corps?.entrees?.facture_hiver).toBe('1400.5')  // tel que tapé
    }, { timeout: 5000 })
    const production = APERCU.valeurs.sans.production_annuelle.valeur
    // La production affichée est celle de l'APERÇU (12 000), plus celle rangée (10 000).
    await waitFor(() => expect((figure(container, 'production_annuelle_kwh') || '').replace(/\D/g, ''))
      .toBe(String(production)), { timeout: 5000 })
    // E7d (M1) — le payback est celui de l'APERÇU, calculé sur le TTC des lignes de
    // l'écran (envoyé avec le corps), jamais celui du devis de référence de la version rangée.
    const corps = ventesApi.apercuConception.mock.calls.at(-1)[0]
    expect(String(Math.round(corps.investissement.sans))).toBe((figure(container, 'total_ttc') || '').replace(/\D/g, ''))
    // Revue de l'écran (25/11) — une règle d'arrondi : au dixième, virgule française.
    expect(figure(container, 'payback_ans')).toBe(`${ans(APERCU_SUR_LES_LIGNES.valeurs.sans.payback.valeur)} ans`)
    expect(figure(container, 'payback_ans')).not.toBe(`${ans(RANGEE.valeurs.sans.payback.valeur)} ans`)
  }, 20000)

  it('lignes sans prix : le payback dit « après enregistrement », aucun investissement envoyé', async () => {
    const devis = devisRouvert(RANGEE.lead)
    devis.data.lignes = devis.data.lignes.map((l) => ({ ...l, prix_unitaire: '0.00' }))
    ventesApi.getDevisById.mockResolvedValue(devis)
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockResolvedValue({ data: APERCU_SANS_PRIX })
    const { container } = renderEdition()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    await waitFor(() => expect(ventesApi.apercuConception).toHaveBeenCalled(), { timeout: 5000 })
    expect(ventesApi.apercuConception.mock.calls.every(([c]) => !('investissement' in c))).toBe(true)
    const roi = container.querySelector('[data-figure="payback_ans"]')
    expect(roi?.textContent || container.textContent).toContain('après enregistrement')
  }, 20000)

  it('sans lead : rien avant la saisie, « Calcul en cours… » pendant l’appel, puis les chiffres servis', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert(null))
    let repondre
    ventesApi.apercuConception.mockImplementation(() => new Promise((r) => { repondre = r }))
    const { container } = renderEdition()
    await waitFor(() => expect(container.querySelector('#gen-hiver')).not.toBeNull(), { timeout: 5000 })
    expect(ventesApi.getConceptionLead).not.toHaveBeenCalled()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain('Calcul en cours'), { timeout: 5000 })
    await waitFor(() => expect(ventesApi.apercuConception).toHaveBeenCalled(), { timeout: 5000 })
    const corps = ventesApi.apercuConception.mock.calls.at(-1)[0]
    expect(corps).toMatchObject({ lead: null, calepinage: null, entrees: { facture_hiver: '1400', type_installation: 'residentiel' } })
    await act(async () => { repondre({ data: APERCU }) })
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    expect((figure(container, 'economie_annuelle') || '').replace(/\D/g, ''))
      .toBe(String(APERCU.valeurs.sans.economies_annuelles.valeur))
    // E7d (M1) — sans lead ni devis de référence, le payback est celui de l'aperçu sur les
    // lignes chiffrées de l'écran (plus « N/A » pour un brouillon aux lignes chiffrées).
    expect(corps.investissement.sans).toBeGreaterThan(0)
    expect(figure(container, 'payback_ans')).toBe(`${ans(APERCU.valeurs.sans.payback.valeur)} ans`)
  }, 20000)

  // E7d (CI e2e figures-parite, 25/11) — un devis « Les deux » aux champs PV
  // divergents (8 panneaux sans, 10 avec), rouvert sans rien taper et SANS
  // version rangée : l'aperçu est demandé sur les valeurs du lead (aucun nombre
  // de panneaux imposé — l'imposition ne sert qu'UNE option) ; sa conception
  // porte les mêmes comptes que les lignes ⇒ la production de CHAQUE option.
  it('« Les deux » divergent sans version rangée : la production de chaque option', async () => {
    const devis = devisRouvert(RANGEE.lead)
    devis.data.etude_params = { scenario: 'Les deux' }
    const [panneau, onduleur] = devis.data.lignes
    devis.data.lignes = [{ ...panneau, variante: 'sans' }, { ...panneau, id: 3, quantite: '10', variante: 'avec', ordre: 2 },
      onduleur]
    ventesApi.getDevisById.mockResolvedValue(devis)
    ventesApi.getConceptionLead.mockRejectedValue({ response: { status: 404 } })
    const option = (nb, production) => ({ ...APERCU.valeurs.sans,
      nb_panneaux: { valeur: nb, unite: 'panneaux', source: 'moteur' },
      module_produit: { valeur: PANNEAU.id, unite: null, source: 'moteur' },
      onduleur_produit: { valeur: ONDULEUR.id, unite: null, source: 'moteur' },
      production_annuelle: { valeur: production, unite: 'kWh/an', source: 'moteur' } })
    const deuxOptions = { ...APERCU, option_retenue: 'avec', valeurs: { sans: option(8, 9000), avec: option(10, 11250) } }
    const uneOption = { ...APERCU, valeurs: { sans: option(8, 9000) } }
    ventesApi.apercuConception.mockImplementation((corps) => Promise.resolve({
      data: corps?.imposes?.nb_panneaux ? uneOption : deuxOptions }))
    const { container } = renderEdition()
    const prod = (opt) => container.querySelector(`[data-figure="production_annuelle_kwh"][data-figure-option="${opt}"]`)
      ?.getAttribute('data-figure-value')?.replace(/\D/g, '')
    await waitFor(() => expect([prod('sans'), prod('avec')]).toEqual(['9000', '11250']), { timeout: 8000 })
    expect(ventesApi.apercuConception.mock.calls.every(([c]) => !c?.imposes?.nb_panneaux)).toBe(true)
  }, 20000)

  // E7d (revue de l'écran, 25/11, BLOQUANT) — « Les deux » 4 / 8 panneaux, 12 factures
  // tapées : la conception sur les valeurs du lead re-dimensionne (3 panneaux) ; l'écran
  // impose alors SA composition — les produits de SES lignes (panneau, onduleur réseau
  // pour « sans » ; onduleur hybride + batterie pour « avec »), un aperçu par option — et
  // les cartes des DEUX options se remplissent ; jamais un panneau absent des lignes.
  it('« Les deux » 4 / 8, factures tapées : composition des lignes imposée par option', async () => {
    const devis = devisRouvert(RANGEE.lead)
    devis.data.etude_params = { scenario: 'Les deux' }
    const [panneau, onduleur] = devis.data.lignes
    devis.data.lignes = [
      { ...panneau, quantite: '4', variante: 'sans' },
      { ...panneau, id: 3, quantite: '8', variante: 'avec', ordre: 1 },
      { ...onduleur, variante: 'sans' },
      ligneProduit({ id: 4, produit: HYBRIDE, quantite: '1', prix_unitaire: '14000.00', taux_tva: '20.00', ordre: 3 }),
      ligneProduit({ id: 5, produit: BATTERIE, quantite: '1', prix_unitaire: '16000.00', taux_tva: '20.00', ordre: 4 }),
    ].map((l, i) => (i >= 3 ? { ...l, variante: 'avec' } : l))
    ventesApi.getDevisById.mockResolvedValue(devis)
    ventesApi.getConceptionLead.mockRejectedValue({ response: { status: 404 } })
    const une = (opt, production) => ({ ...APERCU, option_retenue: opt, valeurs: { [opt]: { ...APERCU.valeurs.sans,
      nb_panneaux: { valeur: 3, unite: 'panneaux', source: 'moteur' },
      production_annuelle: { valeur: production, unite: 'kWh/an', source: 'moteur' } } } })
    ventesApi.apercuConception.mockImplementation((corps) => Promise.resolve({ data:
      !corps?.imposes?.nb_panneaux ? une('sans', 2600) : corps.imposes.batterie_produit_id ? une('avec', 7037)
        : une('sans', 3518) }))
    const { container } = renderEdition()
    for (const c of [...container.querySelectorAll('.gen-monthly-grid input')]) {
      await act(async () => { fireEvent.change(c, { target: { value: '800' } }) })
    }
    const prod = (opt) => container.querySelector(`[data-figure="production_annuelle_kwh"][data-figure-option="${opt}"]`)
      ?.getAttribute('data-figure-value')?.replace(/\D/g, '')
    const imposesFaits = () => ventesApi.apercuConception.mock.calls.map(([c]) => c.imposes).filter((i) => i.nb_panneaux)
    // Les deux DERNIERS aperçus imposés portent les 12 factures tapées (la frappe est finie).
    await waitFor(() => expect(imposesFaits().slice(-2).map((i) => i.consommation?.source))
      .toEqual(['factures', 'factures']), { timeout: 10000 })
    await waitFor(() => expect([prod('sans'), prod('avec')]).toEqual(['3518', '7037']), { timeout: 10000 })
    const imposes = imposesFaits()
    expect(imposes).toContainEqual(expect.objectContaining({ nb_panneaux: 4, panneau_produit_id: PANNEAU.id,
      onduleur_produit_id: ONDULEUR.id }))
    expect(imposes).toContainEqual(expect.objectContaining({ nb_panneaux: 8, panneau_produit_id: PANNEAU.id,
      onduleur_produit_id: HYBRIDE.id, batterie_produit_id: BATTERIE.id }))
  }, 30000)

  // Revue de l'écran (25/11) — trois paybacks « avec batterie » sur un même onglet : la
  // carte (ce devis, ses lignes), le tableau et la falaise (taille, batterie et prix du
  // MOTEUR). Chacun dit pour quoi il est calculé ; un seul arrondi (dixième, virgule).
  it('paybacks du tableau et de la falaise : étiquetés « du moteur », au dixième', async () => {
    const ligne = { panneaux: 8, kwc: 4.4, onduleur: 'Onduleur hybride', ratio_onduleur_kwc: 1.1,
      regle_80_pct_respectee: true, taux_autoconso_sans: 0.5, couverture_sans: 0.4, economie_sans_mad: 5000,
      economie_avec_mad: 8614, batterie_disponible: true, payback_sans_annees: 6.89, payback_avec_annees: 8.72,
      taille_du_devis: ['avec'] }
    const motif = '4.6 kWh refusé : capacité utile 4.60 kWh au-dessus du plafond de remplissage 0.00 kWh '
      + '(le surplus quotidien du mois 2, le plus faible de l\'année).'
    const petite = { ...ligne, panneaux: 4, kwc: 2.2, batterie_disponible: false, taille_du_devis: undefined,
      stockage_refuse: { motif_refus: motif, capacite_kwh: 4.6, remplissage: { pire_mois: { mois: 2, ratio: 0 } } } }
    const brute = 'meilleur payback (6.9 ans, 2 tailles à égalité à moins de 0.25 an près) — critère « meilleur_payback »'
    const dimensionnement = { tableau: [petite, ligne], critere: 'meilleur_payback', motivation: brute,
      recommandation: { panneaux: 8, kwc: 4.4, payback_sans_annees: 6.89, couverture_sans: 0.43 },
      falaise: { cible_kwh_mois: 300 }, meilleure_falaise: { panneaux: 8, kwc: 4.4, batterie_kwh: 4.6,
        payback_annees: 7.66 } }
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockResolvedValue({ data: { ...APERCU_SUR_LES_LIGNES,
      blocs: { ...APERCU.blocs, dimensionnement } } })
    const { container } = renderEdition()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="etude-horaire-dimensionnement"]'))
      .not.toBeNull(), { timeout: 5000 })
    const tableau = container.querySelector('[data-testid="etude-horaire-dimensionnement"]').textContent
    expect(tableau).toContain('Payback sans (prix du moteur)')
    expect(tableau).toContain('6,9 ans')
    expect(tableau).not.toContain('6.89')
    // T4-X4-018 — la ligne à la taille de l'option que le devis vend est marquée.
    expect(container.querySelector('[data-testid="etude-horaire-taille-devis"]').textContent)
      .toContain('taille de ce devis (avec batterie)')
    expect(container.querySelector('[data-testid="etude-horaire-meilleure-falaise"]').textContent)
      .toContain('payback 7,7 ans (batterie et prix du moteur)')
    expect(figure(container, 'payback_ans')).toBe('4,2 ans')  // la carte : ce devis
    // Revue de l'écran (25/11) — la cellule « Éco. avec » : UNE phrase en mots simples ;
    // la phrase technique à la demande (infobulle), jamais dans la cellule.
    const raison = container.querySelector('[data-testid="etude-horaire-raison-batterie"]')
    expect(raison.textContent).toBe('Pas de batterie à cette taille : en février, le surplus solaire d’une '
      + 'journée ne remplirait la batterie de 4,6 kWh qu’à 0 %.')
    expect(raison.getAttribute('title')).toBe(motif)
    // La ligne sous le tableau : nombres français, critère en mots, aucune clé technique.
    const motivation = container.querySelector('[data-testid="etude-horaire-motivation"]')
    expect(motivation.textContent).toContain('critère : le retour sur investissement le plus court')
    expect(motivation.textContent).not.toMatch(/meilleur_payback|\d\.\d/)
    expect(motivation.getAttribute('title')).toBe(brute)
    // Les badges : chacun sur sa ligne sous le chiffre kWc, texte entier.
    const badges = [...container.querySelectorAll('[data-testid="etude-horaire-badges"] > span')]
      .map((b) => b.textContent.trim())
    expect(badges).toEqual(['★ Recommandé (sans)', 'taille de ce devis (avec batterie)'])
  }, 20000)

  // E7d (revue lot 4, M2) — un aperçu en ÉCHEC après une saisie est DIT : la phrase du
  // serveur (400 nommant un champ) ou « Aperçu indisponible — Réessayer » (5xx, réseau) ;
  // les cartes ne retombent JAMAIS sur la version rangée comme si elle était à jour.
  it('aperçu en échec : la phrase du serveur, jamais les chiffres rangés ; Réessayer relance', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    const detail = '« facture_hiver » : valeur illisible.'
    ventesApi.apercuConception.mockRejectedValue({ response: { status: 400, data: { detail, champ: 'facture_hiver' } } })
    const { container } = renderEdition()
    await waitFor(() => expect(container.querySelector('[data-testid="bandeau-modele-conception"]')).not.toBeNull(),
      { timeout: 5000 })
    expect(container.textContent).not.toContain('ceux de la fiche du lead et du document')
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain(detail), { timeout: 5000 })
    expect(figure(container, 'production_annuelle_kwh')).toBeNull()  // jamais la version rangée
    ventesApi.apercuConception.mockRejectedValue(new Error('Network Error'))
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1500' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain('Aperçu indisponible — Réessayer'), { timeout: 5000 })
    const appels = ventesApi.apercuConception.mock.calls.length
    ventesApi.apercuConception.mockResolvedValue({ data: APERCU })
    const bouton = [...container.querySelectorAll('button')].find((b) => b.textContent === 'Réessayer')
    await act(async () => { fireEvent.click(bouton) })
    await waitFor(() => expect(ventesApi.apercuConception.mock.calls.length).toBeGreaterThan(appels), { timeout: 5000 })
    await waitFor(() => expect((figure(container, 'production_annuelle_kwh') || '').replace(/\D/g, ''))
      .toBe(String(APERCU.valeurs.sans.production_annuelle.valeur)), { timeout: 5000 })
  }, 30000)

  // E7d (revue lot 4, M3) — un refus du moteur est TOUJOURS dit (sa phrase, son
  // champ) : jamais remplacé par les chiffres d'un autre calcul ; aucun appel à
  // l'aperçu horaire.
  it('conception refusée : la phrase et le champ du refus, aucun chiffre', async () => {
    const refus = exempleContrat('ventes', 'conception_lead', 'exemple_refus')
    ventesApi.getConceptionLead.mockResolvedValue({ data: RANGEE })
    ventesApi.apercuConception.mockResolvedValue({ data: refus })
    const { container } = renderEdition()
    await act(async () => { fireEvent.change(container.querySelector('#gen-hiver'), { target: { value: '1400' } }) })
    await waitFor(() => expect(container.querySelector('[data-testid="apercu-conception-attente"]')?.textContent)
      .toContain(refus.refus.message), { timeout: 5000 })
    expect(container.querySelector('[data-testid="apercu-conception-attente"]').getAttribute('data-champ'))
      .toBe(refus.refus.champ)
    expect(figure(container, 'production_annuelle_kwh')).toBeNull()
    expect(ventesApi.postEtudeHorairePreview).not.toHaveBeenCalled()
    // Revue de l'écran (25/11) — le refus est dit UNE fois dans le bloc, et les cartes
    // disent ce qui manque au lieu de disparaître en silence.
    const bloc = container.querySelector('#gen-sec-simulation-contenu').textContent
    expect(bloc.split(refus.refus.message).length - 1).toBe(1)
    expect(container.querySelector('[data-testid="apercu-conception-attente"]').textContent)
      .toContain('Production, économies et retour sur investissement ne sont pas calculés')
  }, 20000)
})

// Revue finale du lot (résidentiel « Les deux ») — deux aperçus imposés, UN tableau
// des tailles : les lignes des DEUX aperçus, une taille présente dans les deux
// marquée pour les deux options, triées par taille (`reunirOptions`).
describe('reunirOptions — le tableau des tailles réunit les deux aperçus imposés', () => {
  const apercu = (option, tableau) => ({ ...APERCU, option_retenue: option,
    valeurs: { [option]: APERCU.valeurs.sans },
    blocs: { ...APERCU.blocs, dimensionnement: { ...APERCU.blocs?.dimensionnement, tableau } } })
  it('la ligne de la taille « avec » n’est jamais perdue ; une taille commune porte les deux options', () => {
    const sans = apercu('sans', [{ panneaux: 4, kwc: 2.2, taille_du_devis: ['sans'] }, { panneaux: 6, kwc: 3.3 }])
    const avec = apercu('avec', [{ panneaux: 6, kwc: 3.3 }, { panneaux: 8, kwc: 4.4, taille_du_devis: ['avec'] },
      { panneaux: 4, kwc: 2.2 }])
    const tableau = reunirOptions(sans, avec).blocs.dimensionnement.tableau
    expect(tableau.map((l) => l.panneaux)).toEqual([4, 6, 8])
    expect(tableau.map((l) => l.taille_du_devis)).toEqual([['sans'], undefined, ['avec']])
    const commun = reunirOptions(apercu('sans', [{ panneaux: 6, kwc: 3.3, taille_du_devis: ['sans'] }]),
      apercu('avec', [{ panneaux: 6, kwc: 3.3, taille_du_devis: ['avec'] }])).blocs.dimensionnement.tableau
    expect(commun).toEqual([{ panneaux: 6, kwc: 3.3, taille_du_devis: ['sans', 'avec'] }])
  })
})
