/* QJ20 — Planifier une visite (inline dans la fiche lead).
   Contrôle minimal, style cohérent avec la fiche existante.
   Un clic sur « Planifier une visite » révèle un mini-formulaire
   (date/heure + notes optionnelles) ; la soumission POST /crm/appointments/
   et affiche les RDV existants du lead. Aucun état global Redux : local only.

   LW36 — sortie de l'inline : les 30 blocs de style en ligne (px bruts,
   radius 6/8/10 — recon 04 §2) migrent vers des classes `.lw-booker*`
   (index.css, tokens) + les primitives du kit compatibles SANS changement de
   comportement (Badge pour la pastille de statut, Button/Input/Label pour
   les contrôles) — aucune logique touchée (LW6 a déjà traité cancel/form). */
import { useState, useEffect, useCallback } from 'react'
import crmApi from '../../../api/crmApi'
import { formatDateTime } from '../../../lib/format'
import { Badge, Button, Input, Label } from '../../../ui'
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
    <div className="lw-booker">
      {/* Liste des RDV existants */}
      {!loading && upcoming.length > 0 && (
        <div className="lw-booker-upcoming">
          <div className="lw-booker-upcoming-label">Visites planifiées</div>
          <div className="lw-booker-list">
            {upcoming.map(a => (
              <div key={a.id} className="lw-booker-row">
                <span className="lw-booker-datetime">
                  {/* VX75 — variante lisible « 18 juin 2026, 14:05 » via
                      formatDateTime(..., { long: true }), une seule source
                      de vérité (lib/format.js) au lieu d'un toLocaleString
                      natif dupliqué. */}
                  {formatDateTime(a.scheduled_at, { long: true })}
                </span>
                {/* LW36 — pastille de statut : ui/Badge (tons tokenisés),
                    remplace le fond/texte conditionnel en inline. */}
                <Badge tone={a.statut === 'confirme' ? 'success' : 'warning'}>
                  {STATUS_LABELS[a.statut] ?? a.statut}
                </Badge>
                {a.notes && (
                  <span className="lw-booker-notes">— {a.notes}</span>
                )}
                {/* VX245(a) — .ics d'événement unique pour CE rendez-vous. */}
                <button
                  type="button"
                  onClick={() => handleDownloadIcs(a.id)}
                  className="lw-booker-link lw-booker-link--muted lw-booker-link--push"
                  title="Télécharger un fichier .ics pour cet unique rendez-vous"
                >
                  📅 Agenda
                </button>
                {/* VX245(b) — aperçu de confirmation WhatsApp (jamais un envoi
                    automatique — le commercial ouvre wa.me lui-même). */}
                <button
                  type="button"
                  onClick={() => handleConfirmWhatsapp(a.id)}
                  className="lw-booker-link lw-booker-link--success"
                  title="Aperçu du message de confirmation WhatsApp"
                >
                  Confirmer par WhatsApp
                </button>
                <button
                  type="button"
                  onClick={() => handleCancel(a.id)}
                  disabled={cancellingId === a.id}
                  className="lw-booker-link lw-booker-link--destructive"
                  title="Annuler ce rendez-vous"
                >
                  {cancellingId === a.id ? 'Annulation…' : 'Annuler'}
                </button>
              </div>
            ))}
          </div>
          {/* VX245(b) — aperçu inline (pas de Dialog ici — composant léger)
              avant ouverture de wa.me. Jamais un envoi automatique. */}
          {waPreview && (
            <div className="lw-booker-wa-preview">
              <div className="lw-booker-wa-preview-title">
                Aperçu du message WhatsApp
              </div>
              <pre className="lw-booker-wa-preview-text">
                {waPreview.message}
              </pre>
              <div className="lw-booker-wa-preview-actions">
                <Button type="button" variant="default" size="sm" disabled={!waPreview.wa_url} onClick={openWhatsapp}>
                  Ouvrir WhatsApp
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => setWaPreview(null)}>
                  Annuler
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Bouton / formulaire — disclosure : aria-expanded reflète l'état
          réel (ce bouton n'existe que quand !open, donc toujours false tant
          qu'il est rendu) ; aria-controls pointe vers le groupe ci-dessous
          (id="appt-booker-form", hook stable — testé en LW6). */}
      {!open ? (
        <Button
          type="button" variant="outline" size="sm" className="lw-booker-toggle"
          aria-expanded={false}
          aria-controls="appt-booker-form"
          onClick={() => setOpen(true)}
        >
          + Planifier une visite
        </Button>
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
          className="lw-booker-form"
        >
          <div className="lw-booker-field lw-booker-field--date">
            <Label htmlFor="appt-scheduled-at" required>Date et heure</Label>
            <Input
              id="appt-scheduled-at"
              type="datetime-local"
              value={scheduledAt}
              onChange={e => setScheduledAt(e.target.value)}
              invalid={!!error}
              aria-describedby={error ? 'appt-error' : undefined}
              required
            />
          </div>
          <div className="lw-booker-field lw-booker-field--notes">
            <Label htmlFor="appt-notes">Notes (optionnel)</Label>
            <Input
              id="appt-notes"
              type="text"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Objet de la visite…"
            />
          </div>
          {error && (
            <div id="appt-error" role="alert" className="lw-booker-error">
              {error}
            </div>
          )}
          <div className="lw-booker-form-actions">
            <Button type="button" variant="default" size="sm" disabled={saving} onClick={handleBook}>
              {saving ? 'Enregistrement…' : 'Confirmer'}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => { setOpen(false); setError(null) }}>
              Annuler
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
