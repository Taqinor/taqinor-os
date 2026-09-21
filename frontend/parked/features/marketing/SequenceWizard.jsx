import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import {
  emptyWizardState, ajouterEtape, retirerEtape, majEtape, calendrierPrevu,
  blocageWhatsapp, peutActiver,
} from './sequenceWizard'

/* ============================================================================
   NTMKT30 — Wizard guidé « Configurer une séquence de relance ».
   ----------------------------------------------------------------------------
   Étapes ajoutées en glisser-empiler (délai + canal + contenu), aperçu du
   calendrier d'envoi type (J+0, J+3, J+7…) avant activation, contrôle
   bloquant si une étape référence WhatsApp non confirmé configuré (XMKT10
   gated). Créer via ce wizard produit les MÊMES `EtapeSequence` qu'une
   création manuelle (`marketing/etapes-sequence/`).
   ========================================================================== */

const CANAUX = [
  { key: 'email', label: 'Email' },
  { key: 'sms', label: 'SMS' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'appel', label: 'Appel' },
]

export default function SequenceWizard({ onCreated, onCancel }) {
  const navigate = useNavigate()
  const [state, setState] = useState(emptyWizardState())
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const confirmer = async () => {
    if (!peutActiver(state)) return
    setSaving(true)
    setErr('')
    try {
      const seqRes = await marketingApi.sequences.create({ nom: state.nom })
      const sequenceId = seqRes.data.id
      for (let i = 0; i < state.etapes.length; i += 1) {
        const e = state.etapes[i]
        await marketingApi.etapesSequence.create({
          sequence: sequenceId, ordre: i + 1, delai_jours: e.delai_jours,
          canal: e.canal, modele_message: e.modele_message,
        })
      }
      if (onCreated) onCreated(seqRes.data)
      else navigate(`/marketing/sequences/${sequenceId}`)
    } catch {
      setErr('Création de la séquence impossible.')
    } finally {
      setSaving(false)
    }
  }

  const bloque = blocageWhatsapp(state)

  return (
    <div className="page" data-testid="sequence-wizard">
      <h3>Configurer une séquence de relance</h3>
      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      <input className="form-input" data-testid="wizard-sequence-nom"
        placeholder="Nom de la séquence" value={state.nom}
        onChange={e => setState(s => ({ ...s, nom: e.target.value }))} />

      <section style={{ marginTop: '1rem' }}>
        <h4>Étapes</h4>
        {state.etapes.map((etape, i) => (
          <div key={i} data-testid={`wizard-etape-${i}`}
            style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <input className="form-input" type="number" style={{ width: 90 }}
              data-testid={`wizard-etape-${i}-delai`} value={etape.delai_jours}
              onChange={e => setState(s => majEtape(
                s, i, { delai_jours: Number(e.target.value) || 0 }))} />
            <select className="form-input" data-testid={`wizard-etape-${i}-canal`}
              value={etape.canal}
              onChange={e => setState(s => majEtape(s, i, { canal: e.target.value }))}>
              {CANAUX.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            <input className="form-input" placeholder="Message"
              data-testid={`wizard-etape-${i}-message`} value={etape.modele_message}
              onChange={e => setState(s => majEtape(s, i, { modele_message: e.target.value }))} />
            <button type="button" className="btn btn-light"
              data-testid={`wizard-etape-${i}-retirer`}
              onClick={() => setState(s => retirerEtape(s, i))}>Retirer</button>
          </div>
        ))}
        <button type="button" className="btn btn-light" data-testid="wizard-ajouter-etape"
          onClick={() => setState(s => ajouterEtape(s))}>+ Ajouter une étape</button>
      </section>

      {bloque && (
        <p style={{ color: '#dc2626' }} data-testid="wizard-blocage-whatsapp">
          Une étape utilise le canal WhatsApp — confirmez que le gabarit BSP
          (XMKT10) est configuré avant d&apos;activer.
        </p>
      )}
      {state.etapes.some(e => e.canal === 'whatsapp') && (
        <label>
          <input type="checkbox" data-testid="wizard-whatsapp-confirme"
            checked={state.whatsappConfigure}
            onChange={e => setState(s => ({ ...s, whatsappConfigure: e.target.checked }))} />
          {' '}Le gabarit WhatsApp (BSP) est configuré
        </label>
      )}

      <section style={{ marginTop: '1rem' }}>
        <h4>Calendrier d&apos;envoi type</h4>
        <ul data-testid="wizard-calendrier">
          {calendrierPrevu(state.etapes).map((c, i) => (
            <li key={i}>{c.jour} — {c.canal}</li>
          ))}
        </ul>
      </section>

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <button className="btn btn-light" data-testid="wizard-annuler"
          onClick={onCancel}>Annuler</button>
        <button className="btn btn-primary" data-testid="wizard-confirmer"
          disabled={saving || !peutActiver(state)} onClick={confirmer}>
          {saving ? 'Création…' : 'Activer la séquence'}
        </button>
      </div>
    </div>
  )
}
