/* QJ20 — Planifier une visite (inline dans la fiche lead).
   Contrôle minimal, style cohérent avec la fiche existante.
   Un clic sur « Planifier une visite » révèle un mini-formulaire
   (date/heure + notes optionnelles) ; la soumission POST /crm/appointments/
   et affiche les RDV existants du lead. Aucun état global Redux : local only. */
import { useState, useEffect, useCallback } from 'react'
import crmApi from '../../../api/crmApi'
import { formatDateTime } from '../../../lib/format'
// LW6 — toast d'erreur explicite quand l'annulation échoue (import direct,
// même convention que PlaybookChecklistPanel.jsx/KanbanView.jsx dans ce
// même dossier — ce fichier est un composant JSX, jamais exécuté sous
// `node --test`, donc aucune contrainte d'import paresseux ici).
import { toast } from '../../../ui/confirm'

const STATUS_LABELS = {
  planifie: 'Planifié',
  confirme: 'Confirmé',
  effectue: 'Effectué',
  annule: 'Annulé',
}

// VX245(a)/(b) — helper de téléchargement blob (jamais un `<a href>` brut :
// l'endpoint est authentifié JWT, il faut passer par axios).
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function AppointmentBooker({ leadId }) {
  const [open, setOpen] = useState(false)
  const [scheduledAt, setScheduledAt] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  // LW6 — id du RDV en cours d'annulation (bouton désactivé pendant la
  // requête, jamais un échec silencieux qui laisse croire au commercial que
  // le RDV a bien été annulé alors qu'il tient toujours — double-booking).
  const [cancellingId, setCancellingId] = useState(null)
  // VX245(b) — aperçu du message de confirmation WhatsApp avant ouverture de
  // wa.me : { apptId, message, wa_url } | null.
  const [waPreview, setWaPreview] = useState(null)

  const load = useCallback(() => {
    if (!leadId) return
    crmApi.getAppointments(leadId)
      .then(r => setAppointments(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [leadId])

  useEffect(() => { load() }, [load])

  // LW6 — plus de balise `form` (soumission au clic ET à Entrée, gérée
  // localement ci-dessous) : `e` peut désormais être un KeyboardEvent, un
  // MouseEvent, ou absent — `preventDefault` optionnel, jamais requis
  // (aucune soumission de formulaire natif à bloquer).
  async function handleBook(e) {
    e?.preventDefault?.()
    if (!scheduledAt) { setError('La date et heure sont requises.'); return }
    setSaving(true)
    setError(null)
    try {
      await crmApi.createAppointment({ lead: leadId, scheduled_at: scheduledAt, notes })
      setOpen(false)
      setScheduledAt('')
      setNotes('')
      load()
    } catch (err) {
      setError(
        err?.response?.data?.detail
        || err?.response?.data?.scheduled_at?.[0]
        || 'Erreur lors de la création du rendez-vous.'
      )
    } finally {
      setSaving(false)
    }
  }

  // LW6 — l'échec était avalé en silence (`catch {}`) : le commercial
  // croyait le RDV annulé alors qu'il tenait toujours (double-booking client
  // réel, recon 05 P2#11). Toast d'erreur explicite + bouton désactivé
  // pendant la requête ; en échec, `load()` n'est PAS rappelé — la liste
  // reste honnête, le RDV toujours affiché puisqu'il n'a pas été annulé.
  async function handleCancel(apptId) {
    setCancellingId(apptId)
    try {
      await crmApi.updateAppointment(apptId, { statut: 'annule' })
      load()
    } catch {
      toast.error('Annulation du rendez-vous impossible — réessayez.')
    } finally {
      setCancellingId(null)
    }
  }

  // VX245(a) — « Ajouter à mon agenda (.ics) » : télécharge un .ics
  // d'événement UNIQUE pour ce rendez-vous (jamais le flux d'abonnement
  // complet — distinct, réservé à Mes préférences).
  async function handleDownloadIcs(apptId) {
    try {
      const res = await crmApi.getAppointmentIcs(apptId)
      downloadBlob(res.data, `rdv-${apptId}.ics`)
    } catch {
      setError("Téléchargement de l'agenda impossible.")
    }
  }

  // VX245(b) — « Confirmer par WhatsApp » : construit l'aperçu côté serveur
  // (date/heure + lien .ics), puis n'ouvre wa.me qu'après confirmation
  // explicite — jamais un envoi automatique.
  async function handleConfirmWhatsapp(apptId) {
    try {
      const res = await crmApi.confirmerAppointmentWhatsapp(apptId)
      setWaPreview({
        apptId, message: res.data?.message ?? '', wa_url: res.data?.wa_url ?? '',
      })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Aperçu WhatsApp impossible.')
    }
  }

  function openWhatsapp() {
    if (waPreview?.wa_url) window.open(waPreview.wa_url, '_blank', 'noopener')
    setWaPreview(null)
  }

  const upcoming = appointments.filter(a => a.statut !== 'annule' && a.statut !== 'effectue')

  return (
    <div style={{ marginTop: 12 }}>
      {/* Liste des RDV existants */}
      {/* VX193 — les variables `--color-*` référencées ici n'existent nulle
          part dans tokens.css (aucun fallback appliqué en dark mode, où le
          navigateur retombe sur `unset`) ; migrées vers les vrais tokens
          (`--muted-foreground`, `--muted`, `--success`, `--warning`,
          `--destructive`). */}
      {!loading && upcoming.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12, color: 'var(--muted-foreground)', marginBottom: 4 }}>
            Visites planifiées
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {upcoming.map(a => (
              <div key={a.id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 10px',
                background: 'var(--muted)',
                borderRadius: 6, fontSize: 13,
              }}>
                <span style={{ fontWeight: 500 }}>
                  {/* VX75 — variante lisible « 18 juin 2026, 14:05 » via
                      formatDateTime(..., { long: true }), une seule source
                      de vérité (lib/format.js) au lieu d'un toLocaleString
                      natif dupliqué. */}
                  {formatDateTime(a.scheduled_at, { long: true })}
                </span>
                <span style={{
                  fontSize: 11, padding: '2px 6px', borderRadius: 10,
                  background: a.statut === 'confirme'
                    ? 'color-mix(in oklch, var(--success) 18%, transparent)'
                    : 'color-mix(in oklch, var(--warning) 18%, transparent)',
                  color: a.statut === 'confirme'
                    ? 'var(--success)'
                    : 'var(--warning)',
                }}>
                  {STATUS_LABELS[a.statut] ?? a.statut}
                </span>
                {a.notes && (
                  <span style={{ color: 'var(--muted-foreground)', fontSize: 12, flex: 1 }}>
                    — {a.notes}
                  </span>
                )}
                {/* VX245(a) — .ics d'événement unique pour CE rendez-vous. */}
                <button
                  type="button"
                  onClick={() => handleDownloadIcs(a.id)}
                  style={{
                    fontSize: 11, color: 'var(--muted-foreground)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    padding: '0 4px', marginLeft: 'auto',
                  }}
                  title="Télécharger un fichier .ics pour cet unique rendez-vous"
                >
                  📅 Agenda
                </button>
                {/* VX245(b) — aperçu de confirmation WhatsApp (jamais un envoi
                    automatique — le commercial ouvre wa.me lui-même). */}
                <button
                  type="button"
                  onClick={() => handleConfirmWhatsapp(a.id)}
                  style={{
                    fontSize: 11, color: 'var(--success)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    padding: '0 4px',
                  }}
                  title="Aperçu du message de confirmation WhatsApp"
                >
                  Confirmer par WhatsApp
                </button>
                <button
                  type="button"
                  onClick={() => handleCancel(a.id)}
                  disabled={cancellingId === a.id}
                  style={{
                    fontSize: 11, color: 'var(--destructive)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    padding: '0 4px',
                  }}
                  title="Annuler ce rendez-vous"
                >
                  {cancellingId === a.id ? 'Annulation…' : 'Annuler'}
                </button>
              </div>
            ))}
          </div>
          {/* VX245(b) — aperçu inline (pas de Dialog ici — composant léger,
              styles inline cohérents avec le reste du fichier) avant
              ouverture de wa.me. Jamais un envoi automatique. */}
          {waPreview && (
            <div style={{
              marginTop: 6, padding: '8px 10px',
              background: 'var(--muted)',
              border: '1px solid var(--border)',
              borderRadius: 8, fontSize: 12,
            }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                Aperçu du message WhatsApp
              </div>
              <pre style={{
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
                fontFamily: 'inherit',
              }}>
                {waPreview.message}
              </pre>
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ fontSize: 12, padding: '3px 10px' }}
                  disabled={!waPreview.wa_url}
                  onClick={openWhatsapp}
                >
                  Ouvrir WhatsApp
                </button>
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  style={{ fontSize: 12, padding: '3px 10px' }}
                  onClick={() => setWaPreview(null)}
                >
                  Annuler
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Bouton / formulaire — VX193 : disclosure sans aria-expanded/
          aria-controls, labels nus (pas de htmlFor/id), erreur non annoncée. */}
      {!open ? (
        <button
          type="button"
          className="btn btn-outline-secondary"
          style={{ fontSize: 13, padding: '4px 12px' }}
          aria-expanded={false}
          aria-controls="appt-booker-form"
          onClick={() => setOpen(true)}
        >
          + Planifier une visite
        </button>
      ) : (
        // LW6 — une balise `form` ici imbriquait un formulaire DANS le
        // formulaire de LeadForm (HTML invalide, propriété du Enter
        // fragile, recon 05 P2#10). `div role="group"` = équivalent
        // sémantique pour un groupe de contrôles ; la soumission au clic
        // (bouton Confirmer) et à Entrée (onKeyDown ci-dessous, réservé aux
        // champs texte — comme un formulaire natif, jamais sur les boutons
        // qui gèrent déjà Entrée eux-mêmes) est gérée localement.
        <div
          id="appt-booker-form"
          role="group"
          aria-label="Planifier une visite"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && e.target.tagName === 'INPUT' && !saving) {
              e.preventDefault()
              handleBook(e)
            }
          }}
          style={{
            display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end',
            padding: '10px', background: 'var(--muted)',
            borderRadius: 8, border: '1px solid var(--border)',
          }}
        >
          <div className="form-group" style={{ flex: '1 1 180px', margin: 0 }}>
            <label className="form-label" htmlFor="appt-scheduled-at" style={{ fontSize: 12 }}>
              Date et heure <span style={{ color: 'var(--destructive)' }}>*</span>
            </label>
            <input
              id="appt-scheduled-at"
              type="datetime-local"
              className="form-control"
              style={{ fontSize: 13 }}
              value={scheduledAt}
              onChange={e => setScheduledAt(e.target.value)}
              aria-invalid={!!error}
              aria-describedby={error ? 'appt-error' : undefined}
              required
            />
          </div>
          <div className="form-group" style={{ flex: '2 1 200px', margin: 0 }}>
            <label className="form-label" htmlFor="appt-notes" style={{ fontSize: 12 }}>Notes (optionnel)</label>
            <input
              id="appt-notes"
              type="text"
              className="form-control"
              style={{ fontSize: 13 }}
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Objet de la visite…"
            />
          </div>
          {error && (
            <div id="appt-error" role="alert" style={{ width: '100%', color: 'var(--destructive)', fontSize: 12 }}>
              {error}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              className="btn btn-primary"
              style={{ fontSize: 13, padding: '4px 14px' }}
              disabled={saving}
              onClick={handleBook}
            >
              {saving ? 'Enregistrement…' : 'Confirmer'}
            </button>
            <button
              type="button"
              className="btn btn-outline-secondary"
              style={{ fontSize: 13, padding: '4px 12px' }}
              onClick={() => { setOpen(false); setError(null) }}
            >
              Annuler
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
