import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { initState } from './draftCore'
import { exempleContrat, documentContrat } from '../../../test/fixtures/contractSamples'
import { toast } from '../../../ui'
import DevisTab from './DevisTab'
import ventesApi from '../../../api/ventesApi'
import { openPdfBlob } from '../../../utils/pdfBlob'
import {
  devisTrackCurrent, devisIntent, waArmed,
  SECTIONS_ENVOI, sectionsDepuisServeur,
  TAILLES_ENVOI, taillesDepuisServeur, optionsCountFromTailles, taillesFromOptionsCount,
  lectureClientLabel,
} from './devisTabLogique'
import { missingFieldTarget } from './missingFields'
import { resolveCss } from '../../../test/readCss.mjs'

/* LW21/LW22 — `DevisTab` : cartes devis (StatusPill statut devis, total TTC
   `.num`, actions facture/chantier busy-par-id), CTA « Devis automatique »
   (prêt → bouton + menu ; pas prêt → champs manquants cliquables), barre
   WhatsApp multi-devis FR/Darija (état `wa` fourni par le parent — ici des
   props contrôlées, comme le fera réellement ContextRail). */

const {
  apercuFacturerVente, createFromDevis, whatsappDevis, whatsappDevisApercu, shareLinkDevis, getOffresTaillesDevis,
  getProduits, CATALOGUE_SUBSTITUTIONS, reviserDevis,
} = vi.hoisted(() => {
  // LANE E — SUBSTITUTIONS (29/08/2026) — catalogue minimal servant les tests
  // du chargement paresseux ci-dessous (MÊME forme que DevisOffresTailles.
  // test.jsx : id/nom/marque/prix_vente > 0, seul filtre appliqué côté écran).
  const CATALOGUE_SUBSTITUTIONS = [
    { id: 41, nom: 'Panneau Longi 610W', marque: 'Longi', prix_vente: 1400, prix_achat: 1000 },
  ]
  return {
    // VNT75 — « Facturer… » du panneau ouvre FacturerVenteDialog, qui lit
    // l'aperçu serveur (réponse fournie par le test depuis devis_facturer.json).
    apercuFacturerVente: vi.fn(),
    createFromDevis: vi.fn(() => Promise.resolve({ data: { reference: 'CHT-1' } })),
    whatsappDevis: vi.fn(() => Promise.resolve({ data: {} })),
    // QJR538 — l'aperçu sans effet : réponse fournie par le test depuis
    // l'exemple COMMITTÉ whatsapp_devis_apercu.json (jamais un mock inventé).
    whatsappDevisApercu: vi.fn(),
    // L5/L-NIV-UI/L-INTPREV — mint/réutilisation du ShareLink pour « Page
    // client »/WhatsApp/aperçu interne (format identique à ce que renvoie POST
    // .../share-link/ : {token, path, token_interne, path_interne, niveau,
    // otp_lecture} — contrat L-NIV + L-INTPREV, apps/ventes/views/devis.py).
    shareLinkDevis: vi.fn(() => Promise.resolve({
      data: {
        token: 'tok-abc', path: '/proposition/karim/tok-abc',
        token_interne: 'tok-int-xyz', path_interne: '/proposition/karim/tok-int-xyz',
        niveau: 'standard', otp_lecture: false,
      },
    })),
    // LANE E (spec_3_options.md) — DevisOffresTailles.jsx (composant RÉUTILISÉ
    // tel quel par « Modifier les options ») appelle ce même module ventesApi
    // au montage : un stub minimal (« pas encore disponible ») suffit ici, ce
    // composant a déjà ses propres tests dédiés (DevisOffresTailles.test.jsx).
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    // LANE E — SUBSTITUTIONS — catalogue société DRF (une page suffit ici :
    // `fetchAllPages` s'arrête dès que `next` est nul).
    getProduits: vi.fn(() => Promise.resolve({
      data: { results: CATALOGUE_SUBSTITUTIONS, count: CATALOGUE_SUBSTITUTIONS.length, next: null },
    })),
    CATALOGUE_SUBSTITUTIONS,
    // QJR534 — « Réviser » depuis la carte (reviserEtOuvrir → ventesApi).
    reviserDevis: vi.fn(() => Promise.resolve({ data: { id: 99, reference: 'DEV-V2' } })),
  }
})
vi.mock('../../../api/ventesApi', async () => ({
  default: {
    apercuFacturerVente, shareLinkDevis, getOffresTaillesDevis, reviserDevis,
    ...(await import('../../../test/mocksVentesEcrans.js')).gestesFactureVente(),
  },
}))
vi.mock('../../../utils/pdfBlob', async (orig) => (await import('../../../test/mocksVentesEcrans.js')).pdfBlobSansOuverture(await orig()))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis } }))
vi.mock('../../../api/stockApi', () => ({ default: { getProduits } }))
// NTCRM19 — badge de consultation salle de vente : résolu en no-op (aucune
// salle) pour ne pas polluer ces tests, déjà couverts par son propre test.
vi.mock('../../../api/crmApi', () => ({
  default: {
    whatsappDevis,
    whatsappDevisApercu,
    getLeadSalleVenteAnalytics: () => Promise.resolve({ data: null }),
  },
}))

beforeAll(() => {
  if (!window.HTMLElement.prototype.scrollIntoView) window.HTMLElement.prototype.scrollIntoView = () => {}
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const leadState = (leadOverrides = {}) => initState({
  lead: {
    id: 7, nom: 'Karim', telephone: '0612345678', whatsapp: '',
    devis: [], devis_auto: { pret: true, manquants: [], message: null },
    ...leadOverrides,
  },
  mode: 'edit',
})

const waState = (overrides = {}) => ({ selected: [], langue: 'fr', preview: null, ...overrides })

function renderTab(props = {}) {
  const onAction = vi.fn()
  const onWaToggle = vi.fn()
  const onWaLangue = vi.fn()
  const onWaPreview = vi.fn()
  const onWaReset = vi.fn()
  const utils = render(
    // CHT21(b) — la référence du chantier déjà créé est désormais un vrai
    // lien (`Link` vers `/chantiers?id=`) : exige un contexte Router.
    <MemoryRouter>
      <DevisTab
        state={leadState()}
        onAction={onAction}
        wa={waState()}
        onWaToggle={onWaToggle}
        onWaLangue={onWaLangue}
        onWaPreview={onWaPreview}
        onWaReset={onWaReset}
        {...props}
      />
    </MemoryRouter>,
  )
  return { ...utils, onAction, onWaToggle, onWaLangue, onWaPreview, onWaReset }
}

describe('LW21 — logique pure (co-localisée, testable sans DOM)', () => {
  it('devisTrackCurrent : accepté sans chantier → "accepte" ; avec chantier → "chantier"', () => {
    expect(devisTrackCurrent({ chantier: null })).toBe('accepte')
    expect(devisTrackCurrent({ chantier: { id: 1, reference: 'CHT-1' } })).toBe('chantier')
  })

  it('missingFieldTarget mappe le NOM DU CHAMP servi (manquants_detail) vers les id lf-* (QJR601)', () => {
    expect(missingFieldTarget('facture_hiver')).toEqual({ field: 'lf-facture-hiver', section: 'energie' })
    expect(missingFieldTarget('pompe_hmt_m')).toEqual({ field: 'lf-pompe-hmt', section: 'pompage' })
    expect(missingFieldTarget('inconnu')).toBeNull()
  })

  it('waArmed : numéro invalide ou sélection vide → jamais armé', () => {
    expect(waArmed('0612345678', 1)).toBe(true)
    expect(waArmed('0612345678', 0)).toBe(false)
    expect(waArmed('123', 1)).toBe(false)
    expect(waArmed('', 1)).toBe(false)
  })

  // EZ5 — contrat « chaîne OU objet » du payload open-devis : sans cible kWc
  // rien ne change pour les appelants existants (IdentityRail, palette…).
  it('devisIntent : sans cible → la chaîne de mode ; avec cible → { mode, targetKwc }', () => {
    expect(devisIntent('auto', '')).toBe('auto')
    expect(devisIntent('auto', '   ')).toBe('auto')
    expect(devisIntent('auto', null)).toBe('auto')
    expect(devisIntent('auto', undefined)).toBe('auto')
    expect(devisIntent('auto', '3')).toEqual({ mode: 'auto', targetKwc: '3' })
    expect(devisIntent('premium', ' 6.5 ')).toEqual({ mode: 'premium', targetKwc: '6.5' })
    // « edit » ouvre le générateur, qui a son PROPRE champ kWc : jamais deux
    // cibles rivales pour le même devis.
    expect(devisIntent('edit', '3')).toBe('edit')
  })
})

describe('LW21 — CTA devis automatique', () => {
  it('devis_auto.pret → bouton primaire + menu remise/onepage/premium/édition', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis_auto: { pret: true, manquants: [] } }) })
    await user.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'auto')

    await user.click(screen.getByRole('button', { name: /Devis modifiable/ }))
    await user.click(screen.getByText('Remise %…'))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'remise')
  })

  // EZ5 — « je veux 3 kWc », pas « je veux 4 panneaux ».
  it('une puissance cible saisie voyage avec l’intention de devis', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab()
    await user.type(screen.getByLabelText(/Puissance cible/), '3')
    await user.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', { mode: 'auto', targetKwc: '3' })
  })

  // AGNR39 — au pompage, aucune cible kWc : ni champ, ni cible envoyée ; le
  // C&I garde le champ et sa cible.
  it('lead agricole : pas de champ « puissance cible », intention sans cible', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ type_installation: 'agricole' }) })
    expect(document.getElementById('lw-devis-kwc')).toBeNull()
    await user.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'auto')
  })

  it('lead industriel : le champ « puissance cible » reste et sa cible voyage', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ type_installation: 'industriel' }) })
    await user.type(screen.getByLabelText(/Puissance cible/), '40')
    await user.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', { mode: 'auto', targetKwc: '40' })
  })

  it('QJR599 — devis_auto pas prêt → « Nouveau devis (édition complète) » reste proposé', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({
      state: leadState({ devis_auto: { pret: false, manquants: ['facture hiver'] } }),
    })
    expect(screen.queryByRole('button', { name: /Devis automatique/ })).toBeNull()
    await user.click(screen.getByRole('button', { name: /Nouveau devis \(édition complète\)/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'edit')
  })

  it('QJR599 — devis_auto prêt → le bouton d’édition complète est là aussi, une seule fois', () => {
    renderTab({ state: leadState({ devis_auto: { pret: true, manquants: [] } }) })
    expect(screen.getAllByRole('button', { name: /Nouveau devis \(édition complète\)/ })).toHaveLength(1)
  })

  it('devis_auto pas prêt → liste des champs manquants cliquables (saute au champ du centre)', async () => {
    const user = userEvent.setup()
    const input = document.createElement('input')
    input.id = 'lf-facture-hiver'
    document.body.appendChild(input)
    const focusSpy = vi.spyOn(input, 'focus')
    try {
      renderTab({
        state: leadState({
          devis_auto: {
            pret: false, manquants: ['facture hiver'], message: 'Manque : facture hiver',
            manquants_detail: [{ champ: 'facture_hiver', label: 'facture hiver' }],
            requis: [['facture_hiver']],
          },
        }),
      })
      expect(screen.queryByRole('button', { name: /Devis automatique/ })).toBeNull()
      await user.click(screen.getByText('facture hiver'))
      // ROUND 5 — le saut canonique DÉPLIE d'abord la section cible, puis
      // scrolle/focalise au frame SUIVANT (le champ n'existe pas encore au
      // moment du clic quand la section était repliée). D'où l'attente.
      await waitFor(() => expect(focusSpy).toHaveBeenCalled())
    } finally {
      input.remove()
    }
  })
})

describe('LW21 — cartes devis + actions facture/chantier', () => {
  const devisAccepte = {
    id: 1, reference: 'DEV-2026-001', statut: 'accepte', total_ttc: '15000',
    date_creation: '2026-01-05', option_acceptee: 'A', chantier: null,
  }

  it('carte rend référence, statut, total .num et « Créer le chantier » ; sans `vente` aucun « Facturer »', () => {
    renderTab({ state: leadState({ devis: [devisAccepte] }) })
    expect(screen.getByText('DEV-2026-001')).toBeInTheDocument()
    expect(screen.getByText('Accepté')).toBeInTheDocument()
    expect(document.querySelector('.num')).toHaveTextContent('15 000')
    expect(screen.queryByRole('button', { name: /Facturer|Générer la facture/ })).toBeNull()
    expect(screen.getByRole('button', { name: /Créer le chantier/ })).toBeInTheDocument()
  })

  // VNT75 — les boutons suivent `vente.peut` du contrat `vente_etat.json`
  // (exemples COMMITTÉS, jamais un mock inventé) ; plus de repli `'libre'`.
  const avecVente = (variante) => ({
    ...devisAccepte,
    vente: exempleContrat('ventes', 'vente_etat', variante).vente,
  })

  it('« Facturer l’acompte » ouvre « Facturer la vente » (aperçu serveur)', async () => {
    apercuFacturerVente.mockResolvedValue({ data: documentContrat('ventes', 'devis_facturer').apercu_get.reponse_200 })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [avecVente('exemple')] }) })
    await user.click(screen.getByRole('button', { name: /Facturer l.acompte/ }))
    await waitFor(() => expect(apercuFacturerVente).toHaveBeenCalledWith(1))
    expect(await screen.findByText(/Facturer — DEV-2026-001/)).toBeInTheDocument()
  })

  it('porte aucune (tout facturé) : aucun bouton « Facturer »', () => {
    renderTab({ state: leadState({ devis: [avecVente('exemple_tout_facture')] }) })
    expect(screen.queryByRole('button', { name: /Facturer/ })).toBeNull()
  })

  it('acompte payé : seul le geste suivant (`peut.facturer_solde`)', () => {
    renderTab({ state: leadState({ devis: [avecVente('exemple_acompte_paye_solde_a_faire')] }) })
    expect(screen.getByRole('button', { name: /Facturer (le solde|la tranche suivante)/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Facturer l.acompte/ })).toBeNull()
  })

  it('vente neuve : seul « Facturer l’acompte » (`peut.facturer_acompte`)', () => {
    renderTab({ state: leadState({ devis: [avecVente('exemple')] }) })
    expect(screen.getByRole('button', { name: /Facturer l.acompte/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Facturer/ })).toHaveLength(1)
  })

  it('version remplacée / révision en cours : jamais de « Facturer »', () => {
    renderTab({
      state: leadState({
        devis: [
          avecVente('exemple_version_remplacee'),
          { ...avecVente('exemple_revision_en_cours'), id: 2, reference: 'DEV-2' },
        ],
      }),
    })
    expect(screen.queryByRole('button', { name: /Facturer/ })).toBeNull()
  })

  it('« Créer le chantier » appelle installationsApi puis onAction(\'refresh\')', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis: [devisAccepte] }) })
    await user.click(screen.getByRole('button', { name: /Créer le chantier/ }))
    await waitFor(() => expect(createFromDevis).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
  })

  it('chantier déjà créé → référence affichée au lieu du bouton', () => {
    renderTab({ state: leadState({ devis: [{ ...devisAccepte, chantier: { id: 5, reference: 'CHT-2026-005' } }] }) })
    expect(screen.getByText(/CHT-2026-005/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
  })

  it('CHT21(b) — la référence du chantier est un lien réel vers /chantiers?id=', () => {
    renderTab({ state: leadState({ devis: [{ ...devisAccepte, chantier: { id: 5, reference: 'CHT-2026-005' } }] }) })
    const lien = screen.getByRole('link', { name: /CHT-2026-005/ })
    expect(lien).toHaveAttribute('href', '/chantiers?id=5')
  })

  it('devis brouillon : aucune action facture/chantier ni piste document', () => {
    renderTab({ state: leadState({ devis: [{ ...devisAccepte, statut: 'brouillon' }] }) })
    expect(screen.queryByRole('button', { name: /Générer la facture|Facturer/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
  })
})

// VNT74 — le panneau de vente lit `d.vente` (exemples COMMITTÉS de
// vente_etat.json) ; absent ⇒ rien ; une réponse sans la clé garde l'état.
describe('VNT74 — panneau de vente (lecture seule)', () => {
  const carteVente = (variante, extra = {}) => {
    const ex = exempleContrat('ventes', 'vente_etat', variante)
    return {
      id: ex.id, reference: ex.reference, statut: 'accepte', total_ttc: '49000.00',
      date_creation: '2026-10-10', chantier: null, is_active: ex.vente.est_tete,
      vente: ex.vente, ...extra,
    }
  }

  it('acompte en brouillon : pastille « Brouillon », bilan lu du serveur', () => {
    renderTab({ state: leadState({ devis: [carteVente('exemple_acompte_brouillon')] }) })
    const panneau = screen.getByTestId('panneau-vente')
    const ligne = within(panneau).getByTestId('facture-vente-117')
    expect(within(ligne).getByText('BROUILLON-117')).toBeInTheDocument()
    expect(within(ligne).getByText('Brouillon')).toBeInTheDocument()
    expect(within(ligne).queryByText('Émise')).toBeNull()
    expect(within(panneau).getByText('Prix convenu')).toBeInTheDocument()
    expect(within(panneau).getByText("L'acompte est en brouillon : émettez-le.")).toBeInTheDocument()
  })

  it('facture émise : pastille « Émise » et payé', () => {
    renderTab({ state: leadState({ devis: [carteVente('exemple_acompte_paye_solde_a_faire')] }) })
    const ligne = screen.getByTestId('facture-vente-118')
    expect(within(ligne).getByText('Émise')).toBeInTheDocument()
    expect(within(ligne).getByText(/Payé/)).toBeInTheDocument()
  })

  it('version remplacée : « Remplacé par » la tête, aucun bouton dans le panneau', () => {
    renderTab({ state: leadState({ devis: [carteVente('exemple_version_remplacee')] }) })
    const panneau = screen.getByTestId('panneau-vente')
    expect(within(panneau).getByText(/Remplacé par DEV-202610-0021/)).toBeInTheDocument()
    expect(within(panneau).queryAllByRole('button')).toHaveLength(0)
  })

  it('sans `vente` ⇒ rien', () => {
    renderTab({ state: leadState({ devis: [carteVente('exemple', { vente: null })] }) })
    expect(screen.queryByTestId('panneau-vente')).toBeNull()
  })

  it('une réponse sans la clé `vente` (PATCH / refresh) garde l’état du dernier GET détail', () => {
    const avec = carteVente('exemple_acompte_brouillon')
    const { rerender, onAction } = renderTab({ state: leadState({ devis: [avec] }) })
    expect(screen.getByTestId('panneau-vente')).toBeInTheDocument()
    const sansCle = { ...avec }
    delete sansCle.vente
    rerender(
      <MemoryRouter>
        <DevisTab
          state={leadState({ devis: [sansCle] })} onAction={onAction} wa={waState()}
          onWaToggle={vi.fn()} onWaLangue={vi.fn()} onWaPreview={vi.fn()} onWaReset={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(within(screen.getByTestId('panneau-vente')).getByText('BROUILLON-117')).toBeInTheDocument()
  })
})

// VNT76 — les gestes PAR facture du panneau suivent `facture.peut` ; un refus
// serveur s'affiche sous CETTE facture (role=alert), jamais en toast.
describe('VNT76 — panneau : Émettre, PDF, Envoyer, Encaisser, Reçu par paiement', () => {
  const carte = (variante) => {
    const ex = exempleContrat('ventes', 'vente_etat', variante)
    return {
      id: ex.id, reference: ex.reference, statut: 'accepte', total_ttc: '49000.00',
      date_creation: '2026-10-10', chantier: null, is_active: true, vente: ex.vente,
    }
  }

  it('brouillon : Émettre + PDF seulement ; Émettre → POST emettre puis rafraîchit le lead', async () => {
    ventesApi.emettreFacture.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis: [carte('exemple_acompte_brouillon')] }) })
    const ligne = screen.getByTestId('facture-vente-117')
    expect(within(ligne).queryByRole('button', { name: 'Encaisser' })).toBeNull()
    expect(within(ligne).queryByRole('button', { name: 'WhatsApp' })).toBeNull()
    expect(within(ligne).getByRole('button', { name: 'PDF' })).toBeInTheDocument()
    await user.click(within(ligne).getByRole('button', { name: 'Émettre' }))
    await waitFor(() => expect(ventesApi.emettreFacture).toHaveBeenCalledWith(117))
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
  })

  it('refus serveur : message sous CETTE facture avec sa référence, aucun toast', async () => {
    const refus = documentContrat('ventes', 'devis_facturer').erreurs_403.credit_hold
    ventesApi.emettreFacture.mockRejectedValue({ response: { status: 403, data: refus } })
    const toastErreur = vi.spyOn(toast, 'error')
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [carte('exemple_acompte_brouillon')] }) })
    const ligne = screen.getByTestId('facture-vente-117')
    await user.click(within(ligne).getByRole('button', { name: 'Émettre' }))
    expect(await within(ligne).findByRole('alert')).toHaveTextContent(`BROUILLON-117 : ${refus.detail}`)
    expect(toastErreur).not.toHaveBeenCalled()
  })

  it('émise payée : Envoyer (WhatsApp / e-mail) et Reçu PAR paiement encaissé', async () => {
    ventesApi.whatsappFacture.mockResolvedValue({ data: {} })
    ventesApi.recuPdfPaiement.mockResolvedValue({ data: new Blob(['%PDF']), headers: {} })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [carte('exemple_acompte_paye_solde_a_faire')] }) })
    const ligne = screen.getByTestId('facture-vente-118')
    expect(within(ligne).queryByRole('button', { name: 'Émettre' })).toBeNull()
    await user.click(within(ligne).getByRole('button', { name: 'WhatsApp' }))
    await waitFor(() => expect(ventesApi.whatsappFacture).toHaveBeenCalledWith(118, { modele: 'facture', langue: 'fr' }))
    await user.click(within(ligne).getByRole('button', { name: /Reçu du paiement/ }))
    await waitFor(() => expect(ventesApi.recuPdfPaiement).toHaveBeenCalledWith(301))
    await waitFor(() => expect(openPdfBlob).toHaveBeenCalledWith(expect.any(Blob), 'Quittance_301.pdf'))
  })
})

// VNT77 — Annuler / Supprimer / Modifier le montant suivent `facture.peut`
// (palier serveur) ; variantes dérivées des exemples COMMITTÉS de vente_etat.
describe('VNT77 — panneau : Annuler, Supprimer, Modifier le montant', () => {
  const carteAvec = (variante, retouche) => {
    const ex = exempleContrat('ventes', 'vente_etat', variante)
    const factures = ex.vente.factures.map((f) => ({ ...f, ...retouche(f) }))
    return {
      id: ex.id, reference: ex.reference, statut: 'accepte', total_ttc: '49000.00',
      date_creation: '2026-10-10', chantier: null, is_active: true,
      vente: { ...ex.vente, factures },
    }
  }

  it('Commercial (peut fermé par le serveur) : aucun des trois', () => {
    const ferme = (f) => ({ peut: { ...f.peut, annuler: false, supprimer: false, modifier_montant: false } })
    renderTab({ state: leadState({ devis: [carteAvec('exemple_acompte_brouillon', ferme)] }) })
    const ligne = screen.getByTestId('facture-vente-117')
    expect(within(ligne).queryByRole('button', { name: /Annuler|Supprimer|Modifier le montant/ })).toBeNull()
  })

  it('Responsable : brouillon 14 700 → 15 000 ⇒ montant-tranche puis rafraîchit', async () => {
    ventesApi.montantTrancheFacture.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    const { onAction } = renderTab({
      state: leadState({ devis: [carteAvec('exemple_acompte_brouillon', () => ({ total_ttc: '14700.00' }))] }),
    })
    const ligne = screen.getByTestId('facture-vente-117')
    await user.click(within(ligne).getByRole('button', { name: 'Modifier le montant' }))
    const champ = within(ligne).getByLabelText(/Montant TTC de BROUILLON-117/)
    await user.clear(champ)
    await user.type(champ, '15 000')
    await user.click(within(ligne).getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(ventesApi.montantTrancheFacture).toHaveBeenCalledWith(117, '15000'))
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
  })

  it('brouillon : Supprimer (BROUILLON-<id>) confirme puis DELETE', async () => {
    ventesApi.supprimerFacture.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [carteAvec('exemple_acompte_brouillon', () => ({}))] }) })
    await user.click(within(screen.getByTestId('facture-vente-117')).getByRole('button', { name: 'Supprimer' }))
    await user.click(await screen.findByTestId('supprimer-brouillon-confirmer'))
    await waitFor(() => expect(ventesApi.supprimerFacture).toHaveBeenCalledWith(117))
  })

  it('émise sans argent : confirmation nommant l’avoir, puis annulation', async () => {
    ventesApi.annulerFacture.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    renderTab({
      state: leadState({ devis: [carteAvec('exemple_acompte_paye_solde_a_faire', () => ({ montant_paye: '0.00', paiements: [] }))] }),
    })
    await user.click(within(screen.getByTestId('facture-vente-118')).getByRole('button', { name: 'Annuler' }))
    expect(await screen.findByTestId('annulation-avoir')).toHaveTextContent(/avoir de contre-passation/)
    await user.click(screen.getByRole('button', { name: 'Annuler la facture' }))
    await waitFor(() => expect(ventesApi.annulerFacture).toHaveBeenCalledWith(118, undefined))
  })

  it('émise avec argent : la directive est obligatoire avant l’annulation', async () => {
    ventesApi.annulerFacture.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [carteAvec('exemple_acompte_paye_solde_a_faire', () => ({}))] }) })
    await user.click(within(screen.getByTestId('facture-vente-118')).getByRole('button', { name: 'Annuler' }))
    const confirmer = await screen.findByRole('button', { name: 'Annuler la facture' })
    expect(confirmer).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: 'Rembourser' }))
    await user.click(confirmer)
    await waitFor(() => expect(ventesApi.annulerFacture).toHaveBeenCalledWith(118, { acompte: { action: 'rembourser' } }))
  })
})

describe('LW22 — WhatsApp multi-devis', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('case à cocher appelle onWaToggle(id)', async () => {
    const user = userEvent.setup()
    const { onWaToggle } = renderTab({ state: leadState({ devis: [devis1] }) })
    await user.click(screen.getByRole('checkbox', { name: /Sélectionner DEV-1/ }))
    expect(onWaToggle).toHaveBeenCalledWith(1)
  })

  it('numéro invalide → bouton désactivé avec hint « Numéro invalide »', () => {
    renderTab({
      state: leadState({ telephone: '123', devis: [devis1] }),
      wa: waState({ selected: [1] }),
    })
    expect(screen.getByRole('button', { name: /Envoyer par WhatsApp/ })).toBeDisabled()
    expect(screen.getByText('Numéro invalide')).toBeInTheDocument()
  })

  it('aucun numéro → hint dédié, bouton désactivé', () => {
    renderTab({ state: leadState({ telephone: '', whatsapp: '', devis: [devis1] }) })
    expect(screen.getByRole('button', { name: /Envoyer par WhatsApp/ })).toBeDisabled()
    expect(screen.getByText('Aucun numéro de téléphone')).toBeInTheDocument()
  })

  it('numéro valide + sélection non vide → armé, envoi ouvre l\'aperçu (onWaPreview) avant wa.me', async () => {
    const user = userEvent.setup()
    const { onWaPreview } = renderTab({
      state: leadState({ telephone: '0612345678', devis: [devis1] }),
      wa: waState({ selected: [1] }),
    })
    const apercu = exempleContrat('crm', 'whatsapp_devis_apercu')
    whatsappDevisApercu.mockResolvedValue({ data: apercu })
    const btn = screen.getByRole('button', { name: /Envoyer par WhatsApp/ })
    expect(btn).toBeEnabled()
    await user.click(btn)
    // QJR538 — l'aperçu passe par l'action SANS EFFET ; le commit n'est pas appelé.
    await waitFor(() => expect(whatsappDevisApercu).toHaveBeenCalledWith(7, { devis_ids: [1], langue: 'fr' }))
    await waitFor(() => expect(onWaPreview).toHaveBeenCalledWith({
      message: apercu.message,
      links: apercu.links,
      wa_url: apercu.wa_url,
    }))
    expect(whatsappDevis).not.toHaveBeenCalled()
  })

  it('QJR538 — aperçu affiché → « Annuler » n’appelle jamais le commit', async () => {
    const user = userEvent.setup()
    const { onWaPreview } = renderTab({
      state: leadState({ telephone: '0612345678', devis: [devis1] }),
      wa: waState({ selected: [1], preview: { message: 'Bonjour', links: [], wa_url: 'https://wa.me/212600000000?text=x' } }),
    })
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(onWaPreview).toHaveBeenCalledWith(null)
    expect(whatsappDevis).toHaveBeenCalledTimes(0)
  })

  it('aperçu affiché → « Ouvrir WhatsApp » ouvre wa.me puis réinitialise la sélection', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    const { onWaReset, onAction } = renderTab({
      state: leadState({ telephone: '0612345678', devis: [devis1] }),
      wa: waState({ selected: [1], preview: { message: 'Bonjour', links: [], wa_url: 'https://wa.me/212600000000?text=x' } }),
    })
    expect(screen.getByText('Aperçu du message WhatsApp')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(window.open).toHaveBeenCalledWith('https://wa.me/212600000000?text=x', '_blank', 'noopener')
    // QJR538 — seul « Ouvrir WhatsApp » marque les devis envoyés (commit).
    expect(whatsappDevis).toHaveBeenCalledWith(7, { devis_ids: [1], langue: 'fr' })
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
    expect(onWaReset).toHaveBeenCalled()
  })

  it('langue FR/Darija appelle onWaLangue', async () => {
    const user = userEvent.setup()
    const { onWaLangue } = renderTab({ state: leadState({ devis: [devis1] }) })
    await user.click(screen.getByRole('button', { name: 'Darija' }))
    expect(onWaLangue).toHaveBeenCalledWith('darija')
  })
})

/* L-SECT (fondateur 24/08/2026) — l'envoi passe désormais par UN dialogue
   « Envoyer au client » : niveau + OTP + les 7 cases de sections y vivent, avec
   les boutons copier/ouvrir/WhatsApp. Les tests L5/L-NIV ci-dessous ouvrent
   donc le dialogue avant d'agir, et le corps posté à share-link porte en plus
   `sections` (les 7 clés, toutes à true par défaut). */
// LANE E (spec_3_options.md) — `getSections` fusionne désormais les 7 clés
// de sections ET les 2 clés de tailles (`taille_eco`/`taille_max`) dans le
// MÊME objet posté au serveur (défaut = 3 options, donc les deux à `true`) ;
// tous les tests ci-dessous qui postent « toutes les sections par défaut »
// portent donc aussi ces deux clés (`TOUTES_SECTIONS`). `sectionsDepuisServeur`
// reste une fonction pure qui ne connaît QUE les 7 clés historiques
// (`SECTIONS_SEULES`) — les tailles ont leur propre fonction pure/tests plus
// bas dans ce fichier.
const SECTIONS_SEULES = {
  roof3d: true, sld: true, pdf: true, bankable: true,
  economies: true, jour_type: true, gammes: true,
}
const TOUTES_SECTIONS = { ...SECTIONS_SEULES, taille_eco: true, taille_max: true }
const ouvrirEnvoi = (user) => user.click(
  screen.getByRole('button', { name: /Envoyer au client/ }),
)

describe('L5 — Page client / WhatsApp / Aperçu interne (par devis, via le dialogue d’envoi)', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('« Page client » mint le ShareLink (share-link) et copie l’URL absolue', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn(() => Promise.resolve())
    // navigator.clipboard peut être un getter en lecture seule selon la
    // version de jsdom → defineProperty (configurable), même motif que
    // DevisList.test.jsx (WR2 — copier le lien de proposition).
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText }, configurable: true, writable: true,
    })
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    // QJ-FUNNEL (09/09/2026) — copier le lien = l'ENVOYER : le POST porte
    // `envoi: true` (backend : devis « envoyé » + funnel « Devis envoyé »).
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, {
        niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS,
        envoi: true,
      },
    ))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      'https://taqinor.ma/proposition/karim/tok-abc',
    ))
    expect(await screen.findByText('Copié')).toBeInTheDocument()
  })

  it('« Ouvrir dans un nouvel onglet » mint le même lien et l’ouvre', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', {
      name: /Ouvrir la page client de DEV-1 dans un nouvel onglet/,
    }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
    await waitFor(() => expect(window.open).toHaveBeenCalledWith(
      'https://taqinor.ma/proposition/karim/tok-abc', '_blank', 'noopener',
    ))
  })

  it('« WhatsApp » par devis : mint le lien puis ouvre wa.me, MÊME format de message que l’outil 3D', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    renderTab({ state: leadState({ telephone: '0612345678', devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: 'WhatsApp' }))
    // QJ-FUNNEL (09/09/2026) — WhatsApp = ENVOI : `envoi: true` au backend.
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, {
        niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS,
        envoi: true,
      },
    ))
    await waitFor(() => expect(window.open).toHaveBeenCalledWith(
      'https://wa.me/212612345678?text='
      + encodeURIComponent(
        "Bonjour Karim, voici votre proposition d'installation solaire Taqinor : "
        + 'https://taqinor.ma/proposition/karim/tok-abc '
        + "N'hésitez pas à me poser vos questions.",
      ),
      '_blank', 'noopener',
    ))
  })

  it('« WhatsApp » par devis désactivé sans numéro exploitable', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ telephone: '', whatsapp: '', devis: [devis1] }) })
    await ouvrirEnvoi(user)
    expect(screen.getByRole('button', { name: 'WhatsApp' })).toBeDisabled()
  })

  it('« Aperçu interne (sans notification) » appelle onAction(\'view-devis\', id) sans jamais toucher le ShareLink public', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis: [devis1] }) })
    await user.click(screen.getByRole('button', { name: /Aperçu interne \(sans notification\)/ }))
    expect(onAction).toHaveBeenCalledWith('view-devis', 1)
    // L'aperçu interne passe par LeadDevisPanel → GET /proposal (authentifié,
    // ne résout aucun token) — il ne mint JAMAIS de ShareLink.
    expect(shareLinkDevis).not.toHaveBeenCalled()
  })
})

/* L-INTPREV (fondateur 25/08/2026) — « le lien de devis doit aussi avoir un
   lien interne secondaire que le commercial peut visiter sans déclencher la
   notification ». Ligne discrète sous les boutons Page client/WhatsApp, dans
   le MÊME dialogue d'envoi : mint le MÊME ShareLink, mais copie/ouvre
   `path_interne` (jeton interne) — jamais `path` (public). Distincte du
   bouton « Aperçu interne (sans notification) » de la carte (celui-là ouvre
   le panneau PDF authentifié /proposal, ne mint jamais de ShareLink — test
   L5 ci-dessus) : l'accessible name ne doit donc PAS collisionner avec lui. */
describe('L-INTPREV — aperçu interne de la page client (sans notification)', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('la ligne discrète ne collisionne pas avec le bouton « Aperçu interne » de la carte', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    // Bouton de la CARTE (mécanisme /proposal existant, hors dialogue).
    expect(screen.getByRole('button', { name: /^Aperçu interne \(sans notification\)$/ })).toBeInTheDocument()
    await ouvrirEnvoi(user)
    // Ligne du DIALOGUE (ce test) : nom distinct, les deux coexistent.
    expect(screen.getByRole('button', { name: /Aperçu interne de la page client \(sans notification\)/ })).toBeInTheDocument()
  })

  it('copie l’URL ABSOLUE du jeton INTERNE (path_interne), jamais le jeton public', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText }, configurable: true, writable: true,
    })
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Aperçu interne de la page client \(sans notification\)/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      'https://taqinor.ma/proposition/karim/tok-int-xyz',
    ))
    expect(writeText).not.toHaveBeenCalledWith('https://taqinor.ma/proposition/karim/tok-abc')
    expect(await screen.findByText('Copié')).toBeInTheDocument()
  })

  it('le bouton « ouvrir » ouvre aussi l’URL du jeton interne dans un nouvel onglet', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', {
      name: /Ouvrir l'aperçu interne de la page client de DEV-1/,
    }))
    await waitFor(() => expect(window.open).toHaveBeenCalledWith(
      'https://taqinor.ma/proposition/karim/tok-int-xyz', '_blank', 'noopener',
    ))
  })

  it('« Page client » / « Ouvrir » / « WhatsApp » n’utilisent JAMAIS l’URL interne', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    const writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText }, configurable: true, writable: true,
    })
    renderTab({ state: leadState({ telephone: '0612345678', devis: [devis1] }) })
    await ouvrirEnvoi(user)

    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('https://taqinor.ma/proposition/karim/tok-abc'))

    await user.click(screen.getByRole('button', {
      name: /Ouvrir la page client de DEV-1 dans un nouvel onglet/,
    }))
    await waitFor(() => expect(window.open).toHaveBeenCalledWith(
      'https://taqinor.ma/proposition/karim/tok-abc', '_blank', 'noopener',
    ))

    await user.click(screen.getByRole('button', { name: 'WhatsApp' }))
    await waitFor(() => expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent('https://taqinor.ma/proposition/karim/tok-abc')),
      '_blank', 'noopener',
    ))

    // Ni le presse-papier ni window.open n'ont jamais reçu le jeton interne.
    expect(writeText).not.toHaveBeenCalledWith(expect.stringContaining('tok-int-xyz'))
    for (const call of window.open.mock.calls) {
      expect(String(call[0])).not.toContain('tok-int-xyz')
    }
  })
})

describe('L-NIV-UI — niveau de la page client (standard/confiance) + OTP', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('« Page client » poste le niveau choisi (confiance) au lieu du défaut standard', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.selectOptions(
      screen.getByRole('combobox', { name: /Niveau de la page client de DEV-1/ }),
      'confiance',
    )
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { envoi: true, niveau: 'confiance', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
  })

  it('la case OTP est postée avec le niveau', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('checkbox', { name: /Exiger un code de lecture pour la page client de DEV-1/ }))
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { envoi: true, niveau: 'standard', otp_lecture: true, sections: TOUTES_SECTIONS },
    ))
  })

  // L-NIV-VU (24/08/2026) — le commercial basculait le niveau sans voir de
  // différence sur la page client. Une des causes : le texte du dialogue
  // promettait vaguement « masque le dimensionnement détaillé » sans dire QUOI,
  // ni prévenir que sur un devis sans lignes de pose ni étude électrique il n'y
  // a RIEN à masquer. Ce test épingle les trois dégradations RÉELLES
  // (public_views : kit agrégé, calibres retirés, filigrane PDF) et la règle
  // fondateur « les marques restent visibles ».
  it('le texte du dialogue décrit les dégradations RÉELLES du niveau standard', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    const hint = document.querySelector('.lw-context-devis-niveau-hint')
    expect(hint.textContent).toMatch(/kit/i)
    expect(hint.textContent).toMatch(/calibres/i)
    expect(hint.textContent).toMatch(/filigrane/i)
    expect(hint.textContent).toMatch(/marques/i)
    // …et il prévient du cas « aucune différence visible ».
    expect(hint.textContent).toMatch(/rien à masquer/i)
  })

  it('niveau confiance : le texte annonce le dossier technique complet', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.selectOptions(
      screen.getByRole('combobox', { name: /Niveau de la page client de DEV-1/ }),
      'confiance',
    )
    const hint = document.querySelector('.lw-context-devis-niveau-hint')
    expect(hint.textContent).toMatch(/complet/i)
    expect(hint.textContent).toMatch(/filigrane/i)
  })

  it('le badge de niveau se rend depuis la réponse serveur après un premier mint', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    expect(screen.queryByTitle(/Le lien reste le même/)).not.toBeInTheDocument()
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    expect(await screen.findByTitle(/Le lien reste le même/)).toHaveTextContent('Standard')
  })

  it('changer de niveau APRÈS un premier mint re-poste sans régénérer le token (même lien)', async () => {
    const user = userEvent.setup()
    shareLinkDevis
      .mockResolvedValueOnce({
        data: {
          token: 'tok-abc', path: '/proposition/karim/tok-abc', niveau: 'standard', otp_lecture: false,
        },
      })
      .mockResolvedValueOnce({
        data: {
          token: 'tok-abc', path: '/proposition/karim/tok-abc', niveau: 'confiance', otp_lecture: false,
        },
      })
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await screen.findByTitle(/Le lien reste le même/)

    await user.selectOptions(
      screen.getByRole('combobox', { name: /Niveau de la page client de DEV-1/ }),
      'confiance',
    )
    // Re-poste immédiatement (lien déjà minté) avec le NOUVEAU niveau, sur le
    // MÊME devis — le backend renvoie le MÊME token (aucun second devis, aucune
    // régénération) ; on le vérifie via les 2 appels reçus, identiques hors niveau.
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledTimes(2))
    expect(shareLinkDevis).toHaveBeenNthCalledWith(
      1, 1, { envoi: true, niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS })
    expect(shareLinkDevis).toHaveBeenNthCalledWith(
      2, 1, { niveau: 'confiance', otp_lecture: false, sections: TOUTES_SECTIONS })
    const badge = await screen.findByTitle(/Le lien reste le même/)
    expect(badge).toHaveTextContent('Confiance')
  })

  // BUGFIX (24/08/2026) — après rechargement de la fiche, le serveur connaît
  // déjà le niveau du ShareLink (`apps.crm.serializers.get_devis` pose
  // `share_link: { niveau, otp_lecture }` via `apps.ventes.selectors
  // .share_link_niveau_map`, lecture seule, jamais de mint) mais l'écran
  // n'affichait le badge qu'après un premier clic. Le badge doit apparaître
  // DÈS le montage, sans aucune interaction ni appel réseau supplémentaire.
  it('le badge de niveau s\'affiche AU CHARGEMENT depuis `share_link` du serveur, sans interaction', async () => {
    const user = userEvent.setup()
    const devisConfianceDejaMinte = {
      ...devis1,
      share_link: { niveau: 'confiance', otp_lecture: true },
    }
    renderTab({ state: leadState({ devis: [devisConfianceDejaMinte] }) })

    // Le badge est sur la CARTE : lisible sans ouvrir le dialogue d'envoi.
    const badge = screen.getByTitle(/Le lien reste le même/)
    expect(badge).toHaveTextContent('Confiance')
    expect(badge).toHaveTextContent('OTP')
    // Le sélecteur/la case reflètent aussi l'état serveur, pas le défaut.
    await ouvrirEnvoi(user)
    expect(screen.getByRole('combobox', { name: /Niveau de la page client de DEV-1/ })).toHaveValue('confiance')
    expect(screen.getByRole('checkbox', { name: /Exiger un code de lecture pour la page client de DEV-1/ })).toBeChecked()
    // Rien n'a été minté/re-posté au montage : lecture serveur uniquement.
    expect(shareLinkDevis).not.toHaveBeenCalled()
  })

  it('changer de niveau après rechargement (aucun mint local) re-poste quand même, sur l\'état déjà connu du serveur', async () => {
    const user = userEvent.setup()
    const devisStandardDejaMinte = {
      ...devis1,
      share_link: { niveau: 'standard', otp_lecture: false },
    }
    renderTab({ state: leadState({ devis: [devisStandardDejaMinte] }) })

    await ouvrirEnvoi(user)
    await user.selectOptions(
      screen.getByRole('combobox', { name: /Niveau de la page client de DEV-1/ }),
      'confiance',
    )
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { niveau: 'confiance', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
  })
})

/* ══════════════════════════════════════════════════════════════════════════
   L-SECT (fondateur 24/08/2026) — « le commercial choisit ce que le client
   reçoit avant d'envoyer la page devis ». Les 7 cases du dialogue « Envoyer au
   client », leurs défauts, et le corps réellement posté à share-link.
   ══════════════════════════════════════════════════════════════════════════ */
describe('L-SECT — dialogue « Envoyer au client » : les sections servies', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  it('les 7 cases sont présentes et TOUTES cochées par défaut', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    for (const { key, label } of SECTIONS_ENVOI) {
      const box = screen.getByRole('checkbox', { name: new RegExp(`^${label} — page client de DEV-1`) })
      expect(box, key).toBeChecked()
    }
  })

  it('décocher « Calepinage 3D » poste sections.roof3d = false', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('checkbox', { name: /^Calepinage 3D — page client de DEV-1/ }))
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(1, {
      envoi: true, niveau: 'standard', otp_lecture: false,
      sections: { ...TOUTES_SECTIONS, roof3d: false },
    }))
  })

  it('décocher « PDF téléchargeable » et « Étude bancable » poste les deux à false', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('checkbox', { name: /^PDF téléchargeable — page client de DEV-1/ }))
    await user.click(screen.getByRole('checkbox', { name: /^Étude bancable — page client de DEV-1/ }))
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(1, {
      envoi: true, niveau: 'standard', otp_lecture: false,
      sections: { ...TOUTES_SECTIONS, pdf: false, bankable: false },
    }))
  })

  it('re-cocher une case revient au corps par défaut (toutes servies)', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    const box = screen.getByRole('checkbox', { name: /^Schéma unifilaire — page client de DEV-1/ })
    await user.click(box)
    await user.click(box)
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { envoi: true, niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
  })

  it('un lien DÉJÀ envoyé rouvre sur ses sections réelles, pas sur les défauts', async () => {
    const user = userEvent.setup()
    const devisDejaEnvoye = {
      ...devis1,
      share_link: {
        niveau: 'confiance', otp_lecture: false,
        sections: { sld: false, gammes: false },
      },
    }
    renderTab({ state: leadState({ devis: [devisDejaEnvoye] }) })
    await ouvrirEnvoi(user)
    expect(screen.getByRole('checkbox', { name: /^Schéma unifilaire — page client de DEV-1/ })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: /^Comparatif de gammes — page client de DEV-1/ })).not.toBeChecked()
    // Clé absente du serveur → servie (sémantique à trois états côté modèle).
    expect(screen.getByRole('checkbox', { name: /^Calepinage 3D — page client de DEV-1/ })).toBeChecked()
  })

  it('changer le niveau re-poste AUSSI les sections déjà choisies', async () => {
    const user = userEvent.setup()
    const devisDejaMinte = {
      ...devis1,
      share_link: { niveau: 'standard', otp_lecture: false, sections: { pdf: false } },
    }
    renderTab({ state: leadState({ devis: [devisDejaMinte] }) })
    await ouvrirEnvoi(user)
    await user.selectOptions(
      screen.getByRole('combobox', { name: /Niveau de la page client de DEV-1/ }),
      'confiance',
    )
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(1, {
      niveau: 'confiance', otp_lecture: false,
      sections: { ...TOUTES_SECTIONS, pdf: false },
    }))
  })

  it('sectionsDepuisServeur — trois états : absente = servie, false = retirée, true = servie', () => {
    expect(sectionsDepuisServeur(undefined)).toEqual(SECTIONS_SEULES)
    expect(sectionsDepuisServeur({})).toEqual(SECTIONS_SEULES)
    expect(sectionsDepuisServeur({ pdf: false, roof3d: true }))
      .toEqual({ ...SECTIONS_SEULES, pdf: false })
  })

  it('les libellés des cases couvrent exactement la whitelist serveur', () => {
    expect(SECTIONS_ENVOI.map((s) => s.key)).toEqual([
      'roof3d', 'sld', 'pdf', 'bankable', 'economies', 'jour_type', 'gammes',
    ])
  })
})

/* ══════════════════════════════════════════════════════════════════════════
   LANE E (spec_3_options.md, fondateur 28/08/2026) — dialogue « Envoyer au
   client » : combien de tailles (Éco/Recommandé/Max) le client voit. Backend
   contract (ShareLink.SECTIONS_CLES étendu, LANE B, déjà mergé sur la branche
   d'accumulation) : `taille_eco`/`taille_max`, MÊME sémantique trois-états
   que les 7 clés ci-dessus ; `recommande` n'a pas de clé (toujours servie).
   ══════════════════════════════════════════════════════════════════════════ */
describe('LANE E — curseur 1/2/3 options + cases Éco/Recommandé/Max', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  const optionsRadiogroup = () => screen.getByRole(
    'radiogroup', { name: /Nombre d'options présentées — page client de DEV-1/ },
  )
  const radio = (label) => within(optionsRadiogroup()).getByRole('radio', { name: label })
  const eco = () => screen.getByRole('checkbox', { name: /^Taille Éco — page client de DEV-1/ })
  const max = () => screen.getByRole('checkbox', { name: /^Taille Max — page client de DEV-1/ })
  const recommande = () => screen.getByRole(
    'checkbox', { name: /^Taille Recommandé — toujours servie — page client de DEV-1/ },
  )

  it('défaut = 3 options : curseur sur 3, Éco et Max cochées, Recommandé verrouillée cochée', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    expect(radio('3')).toHaveAttribute('aria-checked', 'true')
    expect(eco()).toBeChecked()
    expect(max()).toBeChecked()
    expect(recommande()).toBeChecked()
    expect(recommande()).toBeDisabled()
  })

  it('Recommandé ne peut jamais être décochée (case désactivée)', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(recommande())
    expect(recommande()).toBeChecked()
  })

  it('curseur → cases : 1 décoche Éco ET Max, 2 ne garde que Max, 3 recoche les deux', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(radio('1'))
    expect(eco()).not.toBeChecked()
    expect(max()).not.toBeChecked()

    await user.click(radio('2'))
    expect(eco()).not.toBeChecked()
    expect(max()).toBeChecked()

    await user.click(radio('3'))
    expect(eco()).toBeChecked()
    expect(max()).toBeChecked()
  })

  it('cases → curseur : décocher Max depuis 3 ramène le curseur sur 2 ; décocher Éco ensuite le ramène sur 1', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(max())
    expect(radio('2')).toHaveAttribute('aria-checked', 'true')
    expect(eco()).toBeChecked()

    await user.click(eco())
    expect(radio('1')).toHaveAttribute('aria-checked', 'true')

    await user.click(eco())
    expect(radio('2')).toHaveAttribute('aria-checked', 'true')
    expect(eco()).toBeChecked()
    expect(max()).not.toBeChecked()
  })

  it('POST porte sections.taille_eco/taille_max = false/false quand seule Recommandé est servie (1 option)', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(radio('1'))
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(1, {
      envoi: true, niveau: 'standard', otp_lecture: false,
      sections: { ...TOUTES_SECTIONS, taille_eco: false, taille_max: false },
    }))
  })

  it('POST porte sections.taille_eco = false quand 2 options servies (Recommandé + Max)', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(radio('2'))
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(1, {
      envoi: true, niveau: 'standard', otp_lecture: false,
      sections: { ...TOUTES_SECTIONS, taille_eco: false },
    }))
  })

  it('POST porte les 2 tailles à true par défaut (3 options, aucune interaction)', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { envoi: true, niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
  })

  it('réouverture relit l’état RÉEL du dernier lien (2 options, Éco retirée) plutôt que le défaut', async () => {
    const user = userEvent.setup()
    const devisDejaEnvoye = {
      ...devis1,
      share_link: { niveau: 'standard', otp_lecture: false, sections: { taille_eco: false } },
    }
    renderTab({ state: leadState({ devis: [devisDejaEnvoye] }) })
    await ouvrirEnvoi(user)
    expect(radio('2')).toHaveAttribute('aria-checked', 'true')
    expect(eco()).not.toBeChecked()
    expect(max()).toBeChecked()
  })

  it('« Modifier les options… » ouvre l’écran vendeur existant DevisOffresTailles pour ce devis', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Modifier les options…/ }))
    expect(screen.getByText(/Modifier les options — DEV-1/)).toBeInTheDocument()
    await waitFor(() => expect(getOffresTaillesDevis).toHaveBeenCalledWith(1))
  })

  // LA BOÎTE DOIT ÊTRE LARGE, ET LA CLASSE SEULE NE LE PROUVE PAS.
  // `lw-context-devis-edit-tailles` était POSÉE ici et DÉFINIE NULLE PART : la
  // boîte retombait sur le `max-w-lg` du composant de base et écrasait ses trois
  // cartes (incident fondateur, 29/08/2026, DEV-202608-0042). Un test qui ne
  // vérifierait que l'attribut `class` serait passé au vert pendant tout le bug —
  // c'est la DÉFINITION CSS qui manquait, donc c'est elle qu'on épingle.
  it('la boîte « Modifier les options » porte une classe de largeur RÉELLEMENT définie', async () => {
    const { join } = await import('node:path')
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Modifier les options…/ }))

    const boite = screen.getByText(/Modifier les options — DEV-1/).closest('[role="dialog"]')
    expect(boite).not.toBeNull()
    expect(boite.className).toMatch(/lw-context-devis-edit-tailles/)

    // `process.cwd()` est la racine `frontend/` sous vitest (`root` du config).
    const css = resolveCss(join(globalThis.process.cwd(), 'src', 'index.css'))
    const regle = css.match(/\.lw-context-devis-edit-tailles\s*\{[^}]*\}/)
    expect(regle, '.lw-context-devis-edit-tailles doit être DÉFINIE dans index.css').not.toBeNull()
    expect(regle[0]).toMatch(/max-width/)
  })
})

// LANE E — SUBSTITUTIONS (fondateur 29/08/2026) — « Modifier les options »
// (DevisOffresTailles.jsx) ne propose de remplacer un équipement que si on lui
// passe `produits` (sans lui, `produitsParRole([])` renvoie des listes vides
// et aucun select de rôle ne rend — DevisOffresTailles.jsx:187-189). DevisTab
// montait ce composant SANS `produits` : ce bloc verrouille le chargement
// paresseux (à l'OUVERTURE du dialogue, pas au montage de l'onglet) + le cache
// par session (aucun second aller-retour réseau à la réouverture) + le repli
// gracieux sur échec (l'éditeur reste utilisable, juste sans substitutions).
describe('LANE E — SUBSTITUTIONS : catalogue chargé paresseusement pour « Modifier les options »', () => {
  const devis1 = {
    id: 1, reference: 'DEV-1', statut: 'envoye', total_ttc: '5000',
    date_creation: '2026-01-01', chantier: null,
  }

  // Un devis « éditable » avec un rôle 'panneau' substituable, de la forme
  // du contrat offres_tailles.json (comme dans DevisOffresTailles.test.jsx).
  const blocEditable = {
    editable: true,
    offres_tailles: {
      avec_servable: false,
      module_batterie_kwh: 5.0,
      offres: [{
        cle: 'recommande', titre: 'Recommandé', recommande: true, est_le_devis: true,
        config: { nb_panneaux: 22, batterie_nb_modules: 0, batterie_module_kwh: 5.0 },
        sans: {
          nb_panneaux: 22, puissance_kwc: 12.1, prix_ttc: 108900.0,
          economie_annuelle_mad: 13260.0, payback_annees: 8.21, couverture_pct: 61.0,
          production_annuelle_kwh: 19140.0,
          materiel: [{ role: 'panneau', famille: 'panneau', marque: 'Longi', modele: 'Panneau 550 W' }],
          toit_ok: true,
        },
        avec: null,
      }],
    },
  }

  const ouvrirModifierOptions = async (user) => {
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('button', { name: /Modifier les options…/ }))
  }

  it('ouvrir le dialogue charge le catalogue une fois et le sert à l’éditeur (un select de substitution rend)', async () => {
    getOffresTaillesDevis.mockResolvedValueOnce({ data: blocEditable })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirModifierOptions(user)

    const select = await screen.findByTestId('offre-taille-recommande-equip-panneau')
    expect(within(select).getByRole('option', { name: /Longi — Panneau Longi 610W/ })).toBeInTheDocument()
    await waitFor(() => expect(getProduits).toHaveBeenCalledTimes(1))
  })

  it('fermer puis rouvrir le dialogue ne relance pas le chargement du catalogue', async () => {
    getOffresTaillesDevis.mockResolvedValue({ data: blocEditable })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirModifierOptions(user)
    await screen.findByTestId('offre-taille-recommande-equip-panneau')
    await waitFor(() => expect(getProduits).toHaveBeenCalledTimes(1))

    // Ciblé DANS la boîte « Modifier les options » : le dialogue « Envoyer au
    // client » reste ouvert derrière (dialogues imbriqués), donc un second
    // bouton « Fermer » existe aussi sur celui-là — `screen.getByRole` seul
    // trouverait les deux et échouerait sur une correspondance ambiguë.
    const boiteOptions = screen.getByText(/Modifier les options — DEV-1/).closest('[role="dialog"]')
    await user.click(within(boiteOptions).getByRole('button', { name: 'Fermer' }))
    await waitFor(() => expect(screen.queryByText(/Modifier les options — DEV-1/)).not.toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Modifier les options…/ }))
    await screen.findByTestId('offre-taille-recommande-equip-panneau')
    expect(getProduits).toHaveBeenCalledTimes(1)
  })

  it('échec réseau du catalogue dégrade sans casser le dialogue — l’éditeur reste utilisable', async () => {
    getProduits.mockRejectedValueOnce(new Error('réseau indisponible'))
    getOffresTaillesDevis.mockResolvedValueOnce({ data: blocEditable })
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirModifierOptions(user)

    // Le dialogue et l'écran vendeur restent affichés (rien ne casse) ; sans
    // catalogue, `produitsParRole([])` ne rend AUCUN select de rôle — c'est le
    // comportement d'AVANT ce correctif, le repli attendu sur échec réseau.
    expect(await screen.findByText(/Modifier les options — DEV-1/)).toBeInTheDocument()
    await waitFor(() => expect(getProduits).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('offre-taille-recommande-equip-panneau')).not.toBeInTheDocument()
  })
})

/* Fonctions pures — testables sans rendu (même patron que sectionsDepuisServeur). */
describe('LANE E — logique pure du curseur 1/2/3 (co-localisée, testable sans DOM)', () => {
  it('taillesDepuisServeur — trois états : absente = servie, false = retirée, true = servie', () => {
    expect(taillesDepuisServeur(undefined)).toEqual({ taille_eco: true, taille_max: true })
    expect(taillesDepuisServeur({})).toEqual({ taille_eco: true, taille_max: true })
    expect(taillesDepuisServeur({ taille_eco: false })).toEqual({ taille_eco: false, taille_max: true })
    expect(taillesDepuisServeur({ taille_eco: true, taille_max: false }))
      .toEqual({ taille_eco: true, taille_max: false })
  })

  it('optionsCountFromTailles : Recommandé compte toujours + les tailles cochées', () => {
    expect(optionsCountFromTailles({ taille_eco: false, taille_max: false })).toBe(1)
    expect(optionsCountFromTailles({ taille_eco: true, taille_max: false })).toBe(2)
    expect(optionsCountFromTailles({ taille_eco: false, taille_max: true })).toBe(2)
    expect(optionsCountFromTailles({ taille_eco: true, taille_max: true })).toBe(3)
  })

  it('taillesFromOptionsCount : 1 décoche tout, 3 coche tout, 2 préserve un choix unique sinon défaut Max', () => {
    expect(taillesFromOptionsCount(1, { taille_eco: true, taille_max: true }))
      .toEqual({ taille_eco: false, taille_max: false })
    expect(taillesFromOptionsCount(3, { taille_eco: false, taille_max: false }))
      .toEqual({ taille_eco: true, taille_max: true })
    // Depuis 1 (aucune cochée) → 2 : défaut Max (règle explicite du spec).
    expect(taillesFromOptionsCount(2, { taille_eco: false, taille_max: false }))
      .toEqual({ taille_eco: false, taille_max: true })
    // Depuis 3 (les deux cochées) → 2 : même défaut Max.
    expect(taillesFromOptionsCount(2, { taille_eco: true, taille_max: true }))
      .toEqual({ taille_eco: false, taille_max: true })
    // Un seul déjà coché → préservé tel quel.
    expect(taillesFromOptionsCount(2, { taille_eco: true, taille_max: false }))
      .toEqual({ taille_eco: true, taille_max: false })
  })

  it('les libellés des cases de tailles couvrent exactement les 2 clés serveur ajoutées', () => {
    expect(TAILLES_ENVOI.map((t) => t.key)).toEqual(['taille_eco', 'taille_max'])
  })
})

describe('QJ-VUES — compteur de lectures client sur chaque carte devis', () => {
  const devisBase = {
    id: 1, reference: 'DEV-2026-001', statut: 'envoye', total_ttc: '15000',
    date_creation: '2026-01-05', chantier: null,
  }

  it('lectureClientLabel : jamais envoyé / envoyé jamais ouvert / ouvert N fois', () => {
    expect(lectureClientLabel(null)).toBe('Pas encore envoyé au client')
    expect(lectureClientLabel(undefined)).toBe('Pas encore envoyé au client')
    expect(lectureClientLabel({ nombre_vues: 0, derniere_consultation: null }))
      .toBe('Jamais ouvert par le client')
    const label = lectureClientLabel({
      nombre_vues: 3, derniere_consultation: '2026-09-09T10:30:00+00:00',
    })
    expect(label).toMatch(/^Ouvert 3 fois par le client · dernière lecture /)
    // Sans horodatage (théorique) : jamais de date inventée.
    expect(lectureClientLabel({ nombre_vues: 2, derniere_consultation: null }))
      .toBe('Ouvert 2 fois par le client')
  })

  it('carte devis : le compteur est TOUJOURS visible — ouvert 3 fois', () => {
    renderTab({
      state: leadState({
        devis: [{
          ...devisBase,
          lecture: { nombre_vues: 3, derniere_consultation: '2026-09-08T18:00:00+00:00' },
        }],
      }),
    })
    expect(screen.getByText(/Ouvert 3 fois par le client/)).toBeInTheDocument()
  })

  it('carte devis sans lien : « Pas encore envoyé au client »', () => {
    renderTab({ state: leadState({ devis: [{ ...devisBase, lecture: null }] }) })
    expect(screen.getByText('Pas encore envoyé au client')).toBeInTheDocument()
  })

  it('carte devis lien envoyé jamais ouvert : « Jamais ouvert par le client »', () => {
    renderTab({
      state: leadState({
        devis: [{ ...devisBase, lecture: { nombre_vues: 0, derniere_consultation: null } }],
      }),
    })
    expect(screen.getByText('Jamais ouvert par le client')).toBeInTheDocument()
  })
})

// QJR534 (D-QJR5-1/2) — « Modifier » (brouillon/envoyé) ou « Réviser » sur la
// carte, droits LUS du contrat serveur `devis_modifiabilite` (exemples committés).
describe('QJR534 — cartes devis : Modifier / Réviser', () => {
  const carte = (variante, extra = {}) => ({
    ...exempleContrat('ventes', 'devis_modifiabilite', variante),
    total_ttc: '15000', date_creation: '2026-01-05', chantier: null, ...extra,
  })

  it('brouillon et envoyé → « Modifier » qui émet edit-devis <id>', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({
      state: leadState({ devis: [carte('exemple_envoye')] }),
    })
    await user.click(screen.getByRole('button', { name: /^Modifier$/ }))
    expect(onAction).toHaveBeenCalledWith('edit-devis', 413)
  })

  it('brouillon : « Modifier » mais pas « Réviser »', () => {
    renderTab({ state: leadState({ devis: [carte('exemple_brouillon')] }) })
    expect(screen.getByRole('button', { name: /^Modifier$/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Réviser/ })).toBeNull()
  })

  it('accepté actif → « Réviser », pas « Modifier » ; le clic appelle le serveur', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [carte('exemple_accepte')] }) })
    expect(screen.queryByRole('button', { name: /^Modifier$/ })).toBeNull()
    await user.click(screen.getByRole('button', { name: /Réviser/ }))
    await waitFor(() => expect(reviserDevis).toHaveBeenCalledWith(414))
  })

  it('chantier en cours → avertissement AVANT l\'appel serveur', async () => {
    const user = userEvent.setup()
    const ordre = []
    const warn = vi.spyOn(toast, 'warning').mockImplementation(() => { ordre.push('warning') })
    reviserDevis.mockImplementationOnce(() => {
      ordre.push('appel')
      return Promise.resolve({ data: { id: 99, reference: 'DEV-V2' } })
    })
    renderTab({
      state: leadState({
        devis: [carte('exemple_accepte', {
          chantier: { id: 5, reference: 'CHT-5', statut: 'en_cours' },
        })],
      }),
    })
    await user.click(screen.getByRole('button', { name: /Réviser/ }))
    await waitFor(() => expect(ordre).toEqual(['warning', 'appel']))
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('CHT-5'))
  })

  it('QJR566 — lu AVANT la correction après envoi → « avant la correction du … »', () => {
    const [corrigee] = exempleContrat('crm', 'lead_devis_ligne').devis
    const avant = { nombre_vues: 2, derniere_consultation: '2026-09-28T09:00:00+00:00' }
    renderTab({ state: leadState({ devis: [{ ...corrigee, lecture: avant }] }) })
    expect(screen.getByText(/avant la correction du/)).toBeInTheDocument()
    // Lu APRÈS la correction : aucune mention.
    const apres = { nombre_vues: 2, derniere_consultation: '2026-09-30T09:00:00+00:00' }
    expect(lectureClientLabel(apres, corrigee.corrige_le)).not.toMatch(/avant la correction/)
    // Jamais corrigé (corrige_le null) : aucune mention.
    expect(lectureClientLabel(avant, null)).not.toMatch(/avant la correction/)
  })

  it('QJR535 — carte remplacée : badge « Remplacé par … », plus d\'« Envoyer au client »', () => {
    const lignes = exempleContrat('crm', 'lead_devis_ligne').devis
    const [courante, remplacee] = lignes
    renderTab({ state: leadState({ devis: [courante, remplacee] }) })
    expect(screen.getByTestId(`devis-remplace-${remplacee.id}`).textContent)
      .toBe(`Remplacé par ${courante.reference}`)
    expect(screen.queryByTestId(`devis-remplace-${courante.id}`)).toBeNull()
    // une seule carte vivante → un seul « Envoyer au client »
    expect(screen.getAllByRole('button', { name: /Envoyer au client/ })).toHaveLength(1)
  })

  it('devis remplacé → ni Modifier ni Réviser', () => {
    renderTab({ state: leadState({ devis: [carte('exemple_remplace')] }) })
    expect(screen.queryByRole('button', { name: /^Modifier$/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Réviser/ })).toBeNull()
  })
})
