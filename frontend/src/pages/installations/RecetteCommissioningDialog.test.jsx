import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

/* WIR202/CH3 — la fiche de recette IEC 62446-1 se CRÉAIT VIDE et rien ne
   permettait de la remplir : `resultat` restait `en_cours` et le gate « Mise
   en service » ne se franchissait jamais. Ce dialog est le formulaire
   manquant.

   Charges utiles alignées sur `CommissioningRecordSerializer` et
   `CommissioningIVReadingSerializer` — jamais une forme inventée. */

// Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
// events) : on le remplace par un <select> natif, le reste de `../../ui`
// restant réel (pattern établi, cf. ListesPrixPage.test.jsx).
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select role="combobox" value={value} onChange={(e) => onValueChange(e.target.value)}>
        {children}
      </select>
    ),
    SelectTrigger: ({ id }) => <span data-select-trigger={id} />,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

vi.mock('../../api/installationsApi', () => ({
  default: {
    getRecetteRecord: vi.fn(),
    updateRecette: vi.fn(),
    ajouterReleveIv: vi.fn(),
  },
}))

import installationsApi from '../../api/installationsApi'
import RecetteCommissioningDialog from './RecetteCommissioningDialog'

const RECORD = {
  id: 4, installation: 9, date_essai: null, technicien: null,
  instrument_id: null, instrument_nom: null, instrument_numero_serie: null,
  instrument_etalonnage_expire: false,
  doc_dossier_ok: null, doc_schema_ok: null, doc_datasheets_ok: null,
  visuel_structure_ok: null, visuel_cablage_ok: null, visuel_terre_ok: null,
  continuite_terre_ok: null, continuite_terre_ohm: null, polarite_ok: null,
  isolement_mohm: null, isolement_ok: null,
  production_test_kw: null, production_attendue_kw: null, performance_ok: null,
  securite_coupure_ok: null, securite_signalisation_ok: null,
  resultat: 'en_cours', resultat_display: 'En cours', passe: false,
  observations: null, ventes_recette_id: null, iv_readings: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  installationsApi.getRecetteRecord.mockResolvedValue({ data: RECORD })
})
afterEach(() => { cleanup() })

const renderDialog = (props = {}) => render(
  <RecetteCommissioningDialog recordId={4} onClose={() => {}} {...props} />,
)

describe('RecetteCommissioningDialog (WIR202)', () => {
  it('charge la fiche et rend les 4 sections du sérialiseur', async () => {
    renderDialog()
    await waitFor(() => expect(installationsApi.getRecetteRecord).toHaveBeenCalledWith(4))

    expect(await screen.findByText('1. Contrôle documentaire')).toBeInTheDocument()
    expect(screen.getByText('2. Contrôle visuel')).toBeInTheDocument()
    expect(screen.getByText('3. Essais électriques')).toBeInTheDocument()
    expect(screen.getByText('4. Sécurité')).toBeInTheDocument()
  })

  it('saisie + resultat=conforme → PATCH 200 et remontée au parent', async () => {
    const enregistre = { ...RECORD, resultat: 'conforme', resultat_display: 'Conforme', passe: true }
    installationsApi.updateRecette.mockResolvedValue({ data: enregistre })
    const onSaved = vi.fn()
    renderDialog({ onSaved })

    await screen.findByText('1. Contrôle documentaire')
    fireEvent.change(screen.getByLabelText(/Continuité de terre mesurée/), { target: { value: '0.4' } })
    // Le <select> du résultat porte l'id rec-resultat via son Label.
    const selects = screen.getAllByRole('combobox')
    const selectResultat = selects[selects.length - 1]
    fireEvent.change(selectResultat, { target: { value: 'conforme' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))

    await waitFor(() => expect(installationsApi.updateRecette).toHaveBeenCalledTimes(1))
    const [id, corps] = installationsApi.updateRecette.mock.calls[0]
    expect(id).toBe(4)
    expect(corps.resultat).toBe('conforme')
    expect(corps.continuite_terre_ohm).toBe('0.4')
    // Les booléens non renseignés partent en null (ternaire serveur), jamais
    // en `false` inventé.
    expect(corps.doc_dossier_ok).toBeNull()
    // Les décimales vides partent en null, jamais en chaîne vide.
    expect(corps.isolement_mohm).toBeNull()

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(enregistre))
    expect(await screen.findByText('Conforme')).toBeInTheDocument()
  })

  it('ajoute un relevé I-V et repart du serveur (écart calculé côté serveur)', async () => {
    installationsApi.ajouterReleveIv.mockResolvedValue({ data: { id: 11 } })
    installationsApi.getRecetteRecord
      .mockResolvedValueOnce({ data: RECORD })
      .mockResolvedValueOnce({
        data: {
          ...RECORD,
          iv_readings: [{
            id: 11, record: 4, string_label: 'S1', n_modules_serie: 20,
            voc_mesure_v: '780.00', isc_mesure_a: '11.20', pmax_mesure_w: '8000.00',
            voc_attendu_v: null, isc_attendu_a: null, pmax_attendu_w: '8200.00',
            ecart_pmax_pct: '-2.44', defaut_detecte: false, observations: '',
          }],
        },
      })
    renderDialog()

    await screen.findByText('Relevés I-V par string')
    fireEvent.change(screen.getByLabelText(/Repère du string/), { target: { value: 'S1' } })
    fireEvent.change(screen.getByLabelText(/Voc mesurée/), { target: { value: '780' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter le relevé' }))

    await waitFor(() => expect(installationsApi.ajouterReleveIv).toHaveBeenCalledTimes(1))
    expect(installationsApi.ajouterReleveIv.mock.calls[0][1])
      .toMatchObject({ string_label: 'S1', voc_mesure_v: '780' })

    // La liste est rendue depuis la réponse serveur rechargée.
    expect(await screen.findByText('S1')).toBeInTheDocument()
    expect(screen.getByText(/écart -2\.44 %/)).toBeInTheDocument()
  })

  it('relevé I-V sans repère : refusé côté écran, aucun appel réseau', async () => {
    renderDialog()
    await screen.findByText('Relevés I-V par string')
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter le relevé' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/repère du string est requis/i)
    expect(installationsApi.ajouterReleveIv).not.toHaveBeenCalled()
  })

  it('400 serveur : message FR, jamais du JSON brut', async () => {
    installationsApi.updateRecette.mockRejectedValue({
      response: { status: 400, data: { continuite_terre_ohm: ['Valeur invalide.'] } },
    })
    renderDialog()

    await screen.findByText('1. Contrôle documentaire')
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))

    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).not.toMatch(/\{"continuite_terre_ohm"/)
  })
})
