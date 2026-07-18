import { useEffect, useRef, useState } from 'react'
import {
  Badge, Button, Avatar, AvatarFallback, DatePicker, FieldSavedPulse,
} from '../../../ui'
import { initials } from '../../../ui/Avatar'
import { normalizeMaPhone } from '../../../lib/format'
import AssigneePicker from '../../../components/AssigneePicker'
import { getField } from './draftCore'

// LW15 — Date locale « YYYY-MM-DD » depuis l'objet Date du DatePicker (jamais
// via toISOString → pas de décalage UTC, cf. classe de bug LW5).
function toIsoLocal(d) {
  if (!d) return ''
  const dt = d instanceof Date ? d : new Date(d)
  if (Number.isNaN(dt.getTime())) return ''
  const m = String(dt.getMonth() + 1).padStart(2, '0')
  const j = String(dt.getDate()).padStart(2, '0')
  return `${dt.getFullYear()}-${m}-${j}`
}

// LW14 — Rail identité (zone gauche, 288px) : tout ce qu'on regarde AVANT
// d'appeler. Identité + contact cliquable + chips de préparation QX28 +
// pile d'actions. La triade (LW15), l'étape (LW16 StageControl), le score
// (LW17) et les bannières (LW18) se greffent ici dans les tâches suivantes.
//
// Contrat de props (blueprint D4 / lane 1) : { state, onAction, users,
// archiveBusy }. Lecture des champs via getField (brouillon-sur-serveur) ; les
// richesses serveur brutes (devis_auto, roof_point, client…) sur state.server.
// TOUTES les sorties/mutations passent par onAction (routé leaveGuard par le
// shell) — jamais de navigation/patch direct ici. Les liens tel:/wa.me
// n'altèrent pas le lead et n'entrent donc pas dans le garde de sortie.

export default function IdentityRail({ state, onAction, users = [], archiveBusy = false }) {
  const server = state.server || {}

  // ── Triade (LW15) : responsable · prochaine action · relance ────────────────
  // La relance pulse (FieldSavedPulse) au succès de sauvegarde qui suit une
  // édition faite depuis le rail. saveState hoisté (scalaire) pour la dep.
  const saveState = state.saveState
  const [relancePulse, setRelancePulse] = useState(0)
  const relancePendingRef = useRef(false)
  useEffect(() => {
    if (saveState === 'saved' && relancePendingRef.current) {
      relancePendingRef.current = false
      // eslint-disable-next-line react-hooks/set-state-in-effect -- pulse au succès de sauvegarde
      setRelancePulse((n) => n + 1)
    }
  }, [saveState])
  const owner = getField(state, 'owner')
  const relance = getField(state, 'relance_date')
  const nextActivity = server.next_activity
  const onRelanceChange = (d) => {
    relancePendingRef.current = true
    onAction('set-field', { key: 'relance_date', value: toIsoLocal(d) })
  }

  // ── Identité ───────────────────────────────────────────────────────────────
  const prenom = getField(state, 'prenom') || ''
  const nom = `${getField(state, 'nom') || ''} ${prenom}`.trim() || 'Lead'
  const societe = getField(state, 'societe')
  const ville = getField(state, 'ville')
  const sub = [societe, ville].filter(Boolean).join(' · ')
  const archived = !!server.is_archived

  // ── Contact (liens directs — jamais de mutation du lead) ────────────────────
  const telephone = (getField(state, 'telephone') || '').trim()
  const whatsapp = (getField(state, 'whatsapp') || '').trim()
  const email = (getField(state, 'email') || '').trim()
  const gpsLat = getField(state, 'gps_lat')
  const gpsLng = getField(state, 'gps_lng')
  const hasGps = gpsLat != null && gpsLat !== '' && gpsLng != null && gpsLng !== ''
  const callPhone = telephone || whatsapp
  // LW7 — bouton WhatsApp armé UNIQUEMENT sur un numéro normalisable (sinon null).
  const waPhone = normalizeMaPhone(whatsapp || telephone)

  // ── Préparation (chips QX28) ────────────────────────────────────────────────
  const roofReady = !!server.roof_point
  const factureReady = server.facture_hiver != null && server.facture_hiver !== ''
  const devisReady = !!(server.devis_auto && server.devis_auto.pret)
  const devisNotReadyMsg = (server.devis_auto && server.devis_auto.message)
    || 'Renseignez la facture du lead pour activer le devis automatique.'

  // ── Actions ─────────────────────────────────────────────────────────────────
  const alreadyClient = !!server.client
  const openWhatsApp = () => {
    if (waPhone) window.open(`https://wa.me/${waPhone}`, '_blank', 'noopener')
  }
  const call = () => {
    if (callPhone) window.location.href = `tel:${callPhone}`
  }

  return (
    <aside className="lw-zone lw-rail-identity" data-testid="lw-identity-rail">
      {/* Identité */}
      <header className="lw-rail-head">
        <Avatar size="lg" className="lw-rail-avatar">
          <AvatarFallback>{initials(nom)}</AvatarFallback>
        </Avatar>
        <div className="lw-rail-headtext">
          <p className="lw-rail-name">
            {nom}
            {archived && <span className="lw-rail-archived">Archivé</span>}
          </p>
          {sub && <p className="lw-rail-sub">{sub}</p>}
        </div>
      </header>

      {/* Contact cliquable */}
      {(callPhone || email || hasGps) && (
        <div className="lw-rail-contact">
          {callPhone && (
            <a className="lw-rail-contact-link" href={`tel:${callPhone}`}>
              ☎ {callPhone}
            </a>
          )}
          {email && (
            <a className="lw-rail-contact-link" href={`mailto:${email}`}>
              ✉ {email}
            </a>
          )}
          {hasGps && (
            <a
              className="lw-rail-contact-link lw-gps-link"
              href={`https://www.google.com/maps?q=${gpsLat},${gpsLng}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              📍 Voir sur la carte
            </a>
          )}
        </div>
      )}

      {/* Triade obligatoire (LW15) : responsable · prochaine action · relance */}
      <div className="lw-rail-triade">
        <div className="lw-rail-field">
          <span className="lw-rail-label">Responsable</span>
          <AssigneePicker
            users={users}
            value={owner ?? ''}
            onChange={(id) => onAction('set-field', { key: 'owner', value: id ?? '' })}
          />
        </div>
        <div className="lw-rail-field">
          <span className="lw-rail-label">Prochaine action</span>
          {nextActivity ? (
            <span className="lw-rail-nextact" data-state={nextActivity.state}>
              ⏰ {nextActivity.summary} — {nextActivity.due_date}
            </span>
          ) : (
            <button
              type="button"
              className="lw-rail-nextact-empty"
              onClick={() => onAction('plan')}
              title="Aucune activité planifiée — planifier une prochaine action"
            >
              <Badge tone="warning">Sans prochaine action</Badge>
              <span className="lw-rail-nextact-cta">Planifier</span>
            </button>
          )}
        </div>
        <div className="lw-rail-field">
          <span className="lw-rail-label">Relance le</span>
          <FieldSavedPulse pulseKey={relancePulse}>
            <DatePicker
              value={relance ? new Date(`${relance}T00:00:00`) : null}
              onChange={onRelanceChange}
              clearable
            />
          </FieldSavedPulse>
        </div>
      </div>

      {/* Chips de préparation QX28 (ui/Badge — tokens uniquement, dark-safe) */}
      {(roofReady || factureReady || devisReady) && (
        <div className="lw-rail-chips">
          {roofReady && (
            <Badge tone="success" title="Un repère GPS de toiture a été capturé (site ou 3D)">
              📍 Toit épinglé
            </Badge>
          )}
          {factureReady && (
            <Badge tone="info" title="Une facture d'électricité a été saisie">
              🧾 Facture saisie
            </Badge>
          )}
          {devisReady && (
            <Badge tone="success" title="Toutes les données nécessaires sont réunies pour générer un devis">
              ⚡ Prêt à deviser
            </Badge>
          )}
        </div>
      )}

      {/* Pile d'actions — WhatsApp et « Devis auto » sont les 2 CTA premiers. */}
      <div className="lw-rail-actions">
        <Button
          type="button"
          variant="success"
          disabled={!waPhone}
          onClick={openWhatsApp}
          title={waPhone ? 'Ouvrir WhatsApp avec ce contact' : 'Numéro de téléphone invalide'}
        >
          🟢 Envoyer WhatsApp
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!callPhone}
          onClick={call}
          title={callPhone ? 'Appeler ce contact' : 'Aucun numéro de téléphone'}
        >
          ☎ Appeler
        </Button>
        <Button
          type="button"
          disabled={!devisReady}
          onClick={() => onAction('open-devis', 'auto')}
          title={devisReady ? 'Créer le devis automatique (affiché ici)' : devisNotReadyMsg}
        >
          ⚡ Devis automatique
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => onAction('toiture-3d')}
          title="Ouvrir l'outil de conception 3D avec ce lead déjà chargé"
        >
          Concevoir la toiture (3D){hasGps ? ' 📍' : ''}
        </Button>
        {!alreadyClient && (
          <Button
            type="button"
            variant="outline"
            onClick={() => onAction('convert')}
            title="Convertir ce lead en client (nouveau, existant, ou aucun)"
          >
            Convertir en client
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          disabled={archiveBusy}
          onClick={() => onAction('archive')}
          title={archived ? 'Restaurer ce lead' : 'Archiver ce lead'}
        >
          {archived ? 'Restaurer' : 'Archiver'}
        </Button>
      </div>
    </aside>
  )
}
