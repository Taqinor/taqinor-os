import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { initState } from './draftCore'
import DevisTab, {
  devisTrackCurrent, devisIntent, missingFieldTarget, waArmed,
  SECTIONS_ENVOI, sectionsDepuisServeur,
} from './DevisTab'

/* LW21/LW22 — `DevisTab` : cartes devis (StatusPill statut devis, total TTC
   `.num`, actions facture/chantier busy-par-id), CTA « Devis automatique »
   (prêt → bouton + menu ; pas prêt → champs manquants cliquables), barre
   WhatsApp multi-devis FR/Darija (état `wa` fourni par le parent — ici des
   props contrôlées, comme le fera réellement ContextRail). */

const { genererFacture, createFromDevis, whatsappDevis, shareLinkDevis } = vi.hoisted(() => ({
  genererFacture: vi.fn(() => Promise.resolve({ data: { reference: 'FAC-1', type_facture_display: 'Facture' } })),
  createFromDevis: vi.fn(() => Promise.resolve({ data: { reference: 'CHT-1' } })),
  whatsappDevis: vi.fn(() => Promise.resolve({
    data: { message: 'Bonjour, voici votre devis', links: [{ devis_id: 1, reference: 'DEV-1', url: 'https://x/1' }], wa_url: 'https://wa.me/212600000000?text=x' },
  })),
  // L5/L-NIV-UI — mint/réutilisation du ShareLink pour « Page client »/
  // WhatsApp (unique, format identique à ce que renvoie POST
  // .../share-link/ : {token, path, niveau, otp_lecture} — contrat L-NIV).
  shareLinkDevis: vi.fn(() => Promise.resolve({
    data: {
      token: 'tok-abc', path: '/proposition/karim/tok-abc', niveau: 'standard', otp_lecture: false,
    },
  })),
}))
vi.mock('../../../api/ventesApi', () => ({ default: { genererFacture, shareLinkDevis } }))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis } }))
// NTCRM19 — badge de consultation salle de vente : résolu en no-op (aucune
// salle) pour ne pas polluer ces tests, déjà couverts par son propre test.
vi.mock('../../../api/crmApi', () => ({
  default: {
    whatsappDevis,
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
    <DevisTab
      state={leadState()}
      onAction={onAction}
      wa={waState()}
      onWaToggle={onWaToggle}
      onWaLangue={onWaLangue}
      onWaPreview={onWaPreview}
      onWaReset={onWaReset}
      {...props}
    />,
  )
  return { ...utils, onAction, onWaToggle, onWaLangue, onWaPreview, onWaReset }
}

describe('LW21 — logique pure (co-localisée, testable sans DOM)', () => {
  it('devisTrackCurrent : accepté sans chantier → "accepte" ; avec chantier → "chantier"', () => {
    expect(devisTrackCurrent({ chantier: null })).toBe('accepte')
    expect(devisTrackCurrent({ chantier: { id: 1, reference: 'CHT-1' } })).toBe('chantier')
  })

  it('missingFieldTarget mappe les libellés backend (devis_auto.py) vers les id lf-*', () => {
    expect(missingFieldTarget('facture hiver')).toEqual({ field: 'lf-facture-hiver', section: 'energie' })
    expect(missingFieldTarget('HMT')).toEqual({ field: 'lf-pompe-hmt', section: 'pompage' })
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

  it('devis_auto pas prêt → liste des champs manquants cliquables (saute au champ du centre)', async () => {
    const user = userEvent.setup()
    const input = document.createElement('input')
    input.id = 'lf-facture-hiver'
    document.body.appendChild(input)
    const focusSpy = vi.spyOn(input, 'focus')
    try {
      renderTab({
        state: leadState({ devis_auto: { pret: false, manquants: ['facture hiver'], message: 'Manque : facture hiver' } }),
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

  it('carte rend référence, statut, total .num et « Générer la facture »/« Créer le chantier »', () => {
    renderTab({ state: leadState({ devis: [devisAccepte] }) })
    expect(screen.getByText('DEV-2026-001')).toBeInTheDocument()
    expect(screen.getByText('Accepté')).toBeInTheDocument()
    expect(document.querySelector('.num')).toHaveTextContent('15 000')
    expect(screen.getByRole('button', { name: /Générer la facture/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Créer le chantier/ })).toBeInTheDocument()
  })

  it('« Générer la facture » appelle ventesApi puis onAction(\'refresh\')', async () => {
    const user = userEvent.setup()
    const { onAction } = renderTab({ state: leadState({ devis: [devisAccepte] }) })
    await user.click(screen.getByRole('button', { name: /Générer la facture/ }))
    await waitFor(() => expect(genererFacture).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onAction).toHaveBeenCalledWith('refresh'))
    expect(await screen.findByText(/FAC-1 créée/)).toBeInTheDocument()
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

  it('devis brouillon : aucune action facture/chantier ni piste document', () => {
    renderTab({ state: leadState({ devis: [{ ...devisAccepte, statut: 'brouillon' }] }) })
    expect(screen.queryByRole('button', { name: /Générer la facture/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
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
    const btn = screen.getByRole('button', { name: /Envoyer par WhatsApp/ })
    expect(btn).toBeEnabled()
    await user.click(btn)
    await waitFor(() => expect(whatsappDevis).toHaveBeenCalledWith(7, { devis_ids: [1], langue: 'fr' }))
    await waitFor(() => expect(onWaPreview).toHaveBeenCalledWith({
      message: 'Bonjour, voici votre devis',
      links: [{ devis_id: 1, reference: 'DEV-1', url: 'https://x/1' }],
      wa_url: 'https://wa.me/212600000000?text=x',
    }))
  })

  it('aperçu affiché → « Ouvrir WhatsApp » ouvre wa.me puis réinitialise la sélection', async () => {
    const user = userEvent.setup()
    window.open = vi.fn(() => ({}))
    const { onWaReset } = renderTab({
      state: leadState({ telephone: '0612345678', devis: [devis1] }),
      wa: waState({ selected: [1], preview: { message: 'Bonjour', links: [], wa_url: 'https://wa.me/212600000000?text=x' } }),
    })
    expect(screen.getByText('Aperçu du message WhatsApp')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    expect(window.open).toHaveBeenCalledWith('https://wa.me/212600000000?text=x', '_blank', 'noopener')
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
const TOUTES_SECTIONS = {
  roof3d: true, sld: true, pdf: true, bankable: true,
  economies: true, jour_type: true, gammes: true,
}
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
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
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
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
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
      1, { niveau: 'confiance', otp_lecture: false, sections: TOUTES_SECTIONS },
    ))
  })

  it('la case OTP est postée avec le niveau', async () => {
    const user = userEvent.setup()
    renderTab({ state: leadState({ devis: [devis1] }) })
    await ouvrirEnvoi(user)
    await user.click(screen.getByRole('checkbox', { name: /Exiger un code de lecture pour la page client de DEV-1/ }))
    await user.click(screen.getByRole('button', { name: /Page client/ }))
    await waitFor(() => expect(shareLinkDevis).toHaveBeenCalledWith(
      1, { niveau: 'standard', otp_lecture: true, sections: TOUTES_SECTIONS },
    ))
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
      1, 1, { niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS })
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
      niveau: 'standard', otp_lecture: false,
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
      niveau: 'standard', otp_lecture: false,
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
      1, { niveau: 'standard', otp_lecture: false, sections: TOUTES_SECTIONS },
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
    expect(sectionsDepuisServeur(undefined)).toEqual(TOUTES_SECTIONS)
    expect(sectionsDepuisServeur({})).toEqual(TOUTES_SECTIONS)
    expect(sectionsDepuisServeur({ pdf: false, roof3d: true }))
      .toEqual({ ...TOUTES_SECTIONS, pdf: false })
  })

  it('les libellés des cases couvrent exactement la whitelist serveur', () => {
    expect(SECTIONS_ENVOI.map((s) => s.key)).toEqual([
      'roof3d', 'sld', 'pdf', 'bankable', 'economies', 'jour_type', 'gammes',
    ])
  })
})
