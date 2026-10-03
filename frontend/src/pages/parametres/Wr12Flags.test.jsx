import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WR12 — exposition des flags backend-only en Paramètres :
   - DevisSection : commission (N99) + export DGI (N105) réservés à l'admin ;
   - LeadsSection : délai SLA de premier contact (FG28), éditable. */

// WIR225 — DevisSection lit le « % de variation par défaut » des variantes au
// montage (`get/setVarianteConfig`, endpoint DISTINCT du profil société) et
// consulte le rôle fin pour savoir s'il peut l'écrire : sans ce mock ni ce
// Provider, les deux tests DevisSection ci-dessous casseraient.
vi.mock('../../api/ventesApi', () => ({
  default: {
    getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '20.00' } })),
    setVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '15.00' } })),
  },
}))

import ventesApi from '../../api/ventesApi'
import DevisSection from './DevisSection'
import LeadsSection from './LeadsSection'
import { documentContrat } from '../../test/fixtures/contractSamples'
import {
  REPERES_ENERGIE, formReperes, payloadReperes, joursDepuisReleve,
} from './peConstants'

/* AGR209 — la forme des repères vient du contrat partagé (jamais un mock
   inventé) : `reglages_lus['CompanyProfile.reperes_energie_agricole']`. */
const REPERES_CONTRAT = documentContrat('ventes', 'economie_pompage')
  .reglages_lus['CompanyProfile.reperes_energie_agricole'].exemple

afterEach(() => cleanup())

function withStore(ui, { role_nom = null } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role: 'admin', role_nom }) => s },
  })
  return <Provider store={store}>{ui}</Provider>
}

const baseForm = {
  payment_terms: {}, doc_prefixes: {}, doc_numbering: {},
  quote_validity_days: 30, agricole_pump_hours: 7,
  // AGR209 — repères énergie datés et sourcés (ex-« bonbonne » 50 / 128),
  // forme du contrat partagé `ventes/contract_samples/economie_pompage.json`.
  reperes_energie_agricole: formReperes({
    reperes_energie_agricole: REPERES_CONTRAT,
  }),
  // Q5 — délais commerciaux indicatifs (texte libre ; vide = non affiché).
  delai_visite_technique: '48-72 h', delai_installation: '7-14 jours ouvrés',
  commission_mode: 'off', commission_valeur: '',
  dgi_export_actif: false, tva_standard: 20, tva_panneaux: 10,
  referral_enabled: false, referral_reward: '', lead_sla_hours: 24,
  responsable_defaut_leads: '', default_installer: '',
  // MRY28/MRY8 — fenêtres de contact (defaults du Guide de Meryem, scindées
  // le 07/09/2026 : message 08:30, appel 09:00).
  message_heure_debut: '08:30',
  appel_heure_debut: '09:00', appel_heure_fin: '20:00',
  vendredi_pause_debut: '11:30', vendredi_pause_fin: '15:00',
  ramadan_debut: '', ramadan_fin: '',
  ramadan_appel_debut: '10:00', ramadan_appel_fin: '14:00',
  premier_contact_objectif_min: 5,
}

const devisProps = {
  form: baseForm, set: vi.fn(), setForm: vi.fn(), setPT: vi.fn(),
  setPrefix: vi.fn(), setNumbering: vi.fn(), numberingPreview: () => 'DEV-1',
}

describe('WR12 — DevisSection (commission N99 + DGI N105, admin only)', () => {
  it('cache les réglages sensibles pour un non-admin', () => {
    render(withStore(<DevisSection {...devisProps} canManageSensitive={false} />))
    // Commission verrouillée : message + pas de sélecteur de mode.
    expect(screen.getByText(/Réservé à l'administrateur/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Mode')).not.toBeInTheDocument()
    // DGI non affiché.
    expect(screen.queryByText("Activer l'export DGI")).not.toBeInTheDocument()
  })

  it('expose commission + DGI pour un admin', () => {
    render(withStore(<DevisSection {...devisProps} canManageSensitive />))
    expect(screen.queryByText(/Réservé à l'administrateur/)).not.toBeInTheDocument()
    expect(screen.getByText('Export DGI (facturation électronique)')).toBeInTheDocument()
    expect(screen.getByText("Activer l'export DGI")).toBeInTheDocument()
  })
})

/* WIR225/QG9 — le « % de variation par défaut » des variantes vivait sur
   `CompanyProfile.variante_pct` et n'était réglable NULLE PART : seul
   l'override ponctuel de la modale de création existait, et il repart de la
   valeur société à chaque ouverture. Le serveur réserve l'ÉCRITURE au
   Directeur et au Commercial responsable ; l'écran reflète la MÊME règle. */
describe('WIR225 — DevisSection (% de variation des variantes)', () => {
  const champ = () => screen.getByLabelText(/% de variation par défaut/)

  it('lit la valeur société au montage', async () => {
    render(withStore(<DevisSection {...devisProps} canManageSensitive />))
    expect(ventesApi.getVarianteConfig).toHaveBeenCalled()
    expect(await screen.findByDisplayValue('20')).toBeInTheDocument()
  })

  it('un Commercial responsable peut l’enregistrer', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    render(withStore(
      <DevisSection {...devisProps} canManageSensitive={false} />,
      { role_nom: 'Commercial responsable' },
    ))
    await screen.findByDisplayValue('20')
    await user.clear(champ())
    await user.type(champ(), '15')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(ventesApi.setVarianteConfig).toHaveBeenCalledWith('15')
  })

  it('un rôle non autorisé voit le champ en lecture seule, sans bouton', async () => {
    render(withStore(
      <DevisSection {...devisProps} canManageSensitive={false} />,
      { role_nom: 'Commercial' },
    ))
    await screen.findByDisplayValue('20')
    expect(champ()).toHaveAttribute('readonly')
    expect(screen.queryByRole('button', { name: 'Enregistrer' })).toBeNull()
    expect(screen.getByText(/Réservé au Directeur et au Commercial responsable/))
      .toBeInTheDocument()
  })
})

const leadsProps = {
  form: baseForm, set: vi.fn(), setForm: vi.fn(),
  assignables: [], tags: [], motifs: [], canaux: [],
  newTag: '', setNewTag: vi.fn(), addTag: vi.fn(), renameTag: vi.fn(),
  delTag: vi.fn(), archiveTag: vi.fn(), setTagColor: vi.fn(),
  newMotif: '', setNewMotif: vi.fn(), addMotif: vi.fn(), renameMotif: vi.fn(),
  delMotif: vi.fn(), archiveMotif: vi.fn(),
  newCanal: '', setNewCanal: vi.fn(), addCanal: vi.fn(), renameCanal: vi.fn(),
  delCanal: vi.fn(), archiveCanal: vi.fn(), refLoading: {},
}

describe('WR12 — LeadsSection (SLA premier contact FG28)', () => {
  it('affiche le champ SLA lié à lead_sla_hours', () => {
    render(<LeadsSection {...leadsProps} />)
    const input = screen.getByLabelText('Délai SLA de premier contact (heures)')
    expect(input).toBeInTheDocument()
    expect(input).toHaveValue(24)
    expect(input).toHaveAttribute('name', 'lead_sla_hours')
  })
})

/* Décision fondateur du 07/09/2026 — les messages partent dès 08:30, les
   appels jamais avant 09:00. L'écran doit donc porter DEUX ouvertures : une
   seule aurait laissé Meryem régler « 09:00 » et retarder aussi le message
   d'identité (ou régler « 08:30 » et faire sonner le téléphone à 08:33). */
describe('MRY8 — LeadsSection (deux ouvertures : messages ≠ appels)', () => {
  it('expose « Début des messages » lié à message_heure_debut', () => {
    render(<LeadsSection {...leadsProps} />)
    const input = screen.getByLabelText('Début des messages')
    expect(input).toHaveAttribute('name', 'message_heure_debut')
    expect(input).toHaveAttribute('type', 'time')
    expect(input).toHaveValue('08:30')
  })

  it('garde « Début des appels » distinct, à 09:00', () => {
    render(<LeadsSection {...leadsProps} />)
    const appels = screen.getByLabelText('Début des appels')
    expect(appels).toHaveAttribute('name', 'appel_heure_debut')
    expect(appels).toHaveValue('09:00')
    expect(appels).not.toBe(screen.getByLabelText('Début des messages'))
  })

  it('remonte la saisie au formulaire parent via `set`', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    const set = vi.fn()
    render(<LeadsSection {...leadsProps} set={set} />)
    await user.type(screen.getByLabelText('Début des messages'), '09:15')
    expect(set).toHaveBeenCalled()
    const evenement = set.mock.calls.at(-1)[0]
    expect(evenement.target.name).toBe('message_heure_debut')
  })
})

/* AGR209 — Paramètres › Devis : les anciens « Prix bonbonne » / « Coût réel »
   (écrasés en silence par `|| 50` / `|| 128`) deviennent trois REPÈRES datés
   et sourcés. Vider un repère l'envoie VIDE, jamais 50 ; enregistrer →
   rouvrir → enregistrer sans toucher = profil serveur identique. */
describe('AGR209 — DevisSection (repères énergie datés et sourcés)', () => {
  it('affiche les trois repères, le « non subventionné » marqué interne', () => {
    render(withStore(<DevisSection {...devisProps} canManageSensitive />))
    for (const { libelle } of REPERES_ENERGIE) {
      expect(screen.getByLabelText(libelle)).toHaveAttribute('step', 'any')
    }
    expect(screen.getByText('Interne, jamais sur un devis.')).toBeInTheDocument()
    expect(screen.queryByText(/Prix bonbonne/)).toBeNull()
    expect(screen.getByText(/le prix\s+retenu est celui DÉCLARÉ par le client/))
      .toBeInTheDocument()
  })

  it('vider un repère ⇒ envoyé vide, jamais 50', () => {
    const vide = payloadReperes({
      ...formReperes({ reperes_energie_agricole: REPERES_CONTRAT }),
      butane_12kg_detail: { valeur: '', source: '', releve_le: '' },
    })
    expect(vide.butane_12kg_detail).toEqual(
      { valeur: null, source: '', releve_le: null })
    expect(payloadReperes(formReperes({})).butane_12kg_detail.valeur).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = profil serveur identique', () => {
    const rouvert = formReperes({ reperes_energie_agricole: REPERES_CONTRAT })
    expect(payloadReperes(rouvert)).toEqual(REPERES_CONTRAT)
    expect(payloadReperes(formReperes({
      reperes_energie_agricole: payloadReperes(rouvert),
    }))).toEqual(REPERES_CONTRAT)
  })

  it('« relevé il y a N jours » sans seuil', () => {
    expect(joursDepuisReleve('2026-08-20', new Date(2026, 9, 2))).toBe(43)
    expect(joursDepuisReleve('', new Date())).toBeNull()
  })

  it('saisir une source remonte au formulaire via setForm', () => {
    const setForm = vi.fn()
    render(withStore(
      <DevisSection {...devisProps} setForm={setForm} canManageSensitive />))
    fireEvent.change(document.getElementById('pe-repere-gasoil_litre-source'),
      { target: { value: 'Relevé station' } })
    expect(setForm).toHaveBeenCalled()
    const suivant = setForm.mock.calls.at(-1)[0]({
      reperes_energie_agricole: formReperes({}),
    })
    expect(suivant.reperes_energie_agricole.gasoil_litre.source)
      .toBe('Relevé station')
  })
})
