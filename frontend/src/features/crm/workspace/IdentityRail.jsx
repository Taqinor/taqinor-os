import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, badgeVariants, Button, Avatar, AvatarFallback, DatePicker, FieldSavedPulse,
  Popover, PopoverTrigger, PopoverContent,
  Dialog, DialogContent, DialogTitle,
} from '../../../ui'
import { initials } from '../../../ui/Avatar'
import { normalizeMaPhone } from '../../../lib/format'
import { useConfirmDialog, toast } from '../../../ui/confirm'
import { useDuplicateCheck } from '../../../hooks/useDuplicateCheck'
import { useIsAdminOrResponsable } from '../../../hooks/useHasPermission'
import crmApi from '../../../api/crmApi'
import AssigneePicker from '../../../components/AssigneePicker'
import ScoreBadge from '../ScoreBadge'
import StageControl from './StageControl'
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

// Rail identité (zone gauche, 288px) : tout ce qu'on regarde AVANT d'appeler.
// Bannières intelligentes (LW18) · identité + contact cliquable (LW14) · étape
// (LW16 StageControl) · score expliqué (LW17) · triade responsable/prochaine
// action/relance (LW15) · chips de préparation QX28 (LW14) · pile d'actions
// (LW14).
//
// Contrat de props (blueprint D4 / lane 1) : { state, onAction, users,
// archiveBusy }. Lecture des champs via getField (brouillon-sur-serveur) ; les
// richesses serveur brutes (devis_auto, roof_point, client, score_reasons,
// next_activity, stage_since_days…) sur state.server. TOUTES les sorties/
// mutations passent par onAction (routé leaveGuard par le shell) — jamais de
// navigation/patch direct ici. Les liens tel:/wa.me et l'ouverture de la fiche
// client (nouvel onglet) n'altèrent pas le lead → hors garde de sortie.
//
// Extensions onAction que le shell doit câbler (au-delà du contrat existant) :
//   'set-field' { key, value } → setField(key, value)  (responsable, relance)
//   'change-stage' key         → draft.changeStage(key) (StageControl)
//   'apply-card'               → applique la carte collée (inerte tant que
//                                state.cardPaste n'est pas exposé par le moteur)

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

  // ── Score + raisons (LW17) ──────────────────────────────────────────────────
  const hasScore = server.score != null || server.score_label != null
  const scoreReasons = Array.isArray(server.score_reasons) ? server.score_reasons : []

  // ── Bannières intelligentes (LW18) : doublons · client_match · carte collée ──
  const leadId = server.id ?? null
  const { confirm } = useConfirmDialog()
  const [dups, setDups] = useState([])
  const [clientMatch, setClientMatch] = useState([])
  const [dupOpen, setDupOpen] = useState(false)
  useEffect(() => {
    if (!leadId) return
    // GET paresseux, silencieux sur 404/vide (jamais de bruit).
    crmApi.getLeadDuplicates(leadId)
      .then((r) => setDups(Array.isArray(r.data) ? r.data : []))
      .catch(() => setDups([]))
    crmApi.getLeadClientMatch(leadId)
      .then((r) => setClientMatch(Array.isArray(r.data) ? r.data : []))
      .catch(() => setClientMatch([]))
  }, [leadId])
  // VX239 — doublons EN DIRECT (téléphone/email tapés), fusionnés aux probables.
  const liveDups = useDuplicateCheck(
    getField(state, 'telephone'), getField(state, 'email'),
    { exclude: leadId ?? undefined },
  )
  const allDups = useMemo(() => {
    const map = new Map()
    for (const d of [...dups, ...liveDups]) {
      if (d && d.id != null && d.id !== leadId) map.set(d.id, d)
    }
    return [...map.values()]
  }, [dups, liveDups, leadId])
  // VX237 — carte de visite collée : état optionnel exposé par le moteur
  // (lane 1) / la section Contact (lane 4). Inerte tant qu'il est absent.
  const cardPaste = state.cardPaste
  const doMerge = async (otherId) => {
    const ok = await confirm({
      title: 'Fusionner ce doublon dans la fiche courante ?',
      description: 'Le doublon sera archivé (jamais supprimé) et ses devis/activités rattachés à cette fiche.',
      confirmLabel: 'Fusionner',
      cancelLabel: 'Annuler',
      destructive: false,
    })
    if (!ok) return
    try {
      await crmApi.mergeLeads(leadId, [otherId])
      setDups((d) => d.filter((x) => x.id !== otherId))
      onAction('refresh')
      setDupOpen(false)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'La fusion a échoué — réessayez.')
    }
  }

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

  // ── PUB53 — lien retour vers l'annonce Meta d'origine (pur frontend : le
  // serializer crm expose déjà `meta_ad_id` en '__all__', aucun sélecteur
  // adsengine n'est nécessaire côté lecture). Gaté aux rôles qui voient
  // /publicite (responsable/admin — même liste que module.config.jsx).
  const metaAdId = server.meta_ad_id || null
  const canSeePublicite = useIsAdminOrResponsable()
  const showAdBadge = !!metaAdId && canSeePublicite

  // ── Actions ─────────────────────────────────────────────────────────────────
  const alreadyClient = !!server.client
  const openWhatsApp = () => {
    if (waPhone) window.open(`https://wa.me/${waPhone}`, '_blank', 'noopener')
  }
  const call = () => {
    if (callPhone) window.location.href = `tel:${callPhone}`
  }

  return (
    <>
    <aside className="lw-zone lw-rail-identity" data-testid="lw-identity-rail">
      {/* Bannières intelligentes (LW18) — en tête, tones sémantiques (jamais
          de hex : dark-mode par tokens). */}
      {allDups.length > 0 && (
        <div className="lw-banner-card lw-banner-card--warning" role="status">
          <span>
            {allDups.length} doublon{allDups.length > 1 ? 's' : ''} probable{allDups.length > 1 ? 's' : ''}
          </span>
          <Button type="button" size="sm" variant="outline" onClick={() => setDupOpen(true)}>
            Examiner
          </Button>
        </div>
      )}
      {clientMatch.length > 0 && (
        <div className="lw-banner-card lw-banner-card--info" role="status">
          <span>Ce contact correspond au client {clientMatch[0].nom}</span>
          <a
            className="lw-banner-link"
            href={`/crm/clients/${clientMatch[0].id}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Ouvrir la fiche
          </a>
        </div>
      )}
      {cardPaste && (
        <div className="lw-banner-card lw-banner-card--info" role="status">
          <span>Carte de visite détectée : {cardPaste.nom}</span>
          <Button type="button" size="sm" variant="outline" onClick={() => onAction('apply-card')}>
            Répartir
          </Button>
        </div>
      )}

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

      {/* Étape + pourrissement (LW16) — le changement passe par le moteur
          (onAction('change-stage')) ; SIGNED ouvre la signature. */}
      <StageControl
        state={state}
        onChangeStage={(key) => onAction('change-stage', key)}
        onSigne={() => onAction('signe')}
      />

      {/* Score expliqué (LW17) : popover des raisons (score_reasons). */}
      {hasScore && (
        <div className="lw-rail-score">
          <span className="lw-rail-label">Score</span>
          <Popover>
            <PopoverTrigger asChild>
              <ScoreBadge lead={server} asTrigger />
            </PopoverTrigger>
            <PopoverContent align="start" className="lw-rail-score-pop">
              <p className="lw-rail-score-title">Score de qualité — <span className="num">{server.score ?? 0}/100</span></p>
              {scoreReasons.length > 0 ? (
                <ul className="lw-rail-score-reasons">
                  {scoreReasons.map((r, i) => (
                    <li key={r.facteur ?? i}>
                      <Badge tone={r.points >= 0 ? 'success' : 'danger'}>
                        {r.points >= 0 ? '+' : ''}{r.points}
                      </Badge>
                      <span>{r.label}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="lw-rail-score-empty">Aucun facteur détaillé pour ce lead.</p>
              )}
              <p className="lw-rail-score-foot">Le score se recalcule à chaque modification.</p>
            </PopoverContent>
          </Popover>
        </div>
      )}

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
              <Badge tone="warning" className="lw-badge-aa">Sans prochaine action</Badge>
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
      {(roofReady || factureReady || devisReady || showAdBadge) && (
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
          {/* PUB53 — traçabilité retour : ce lead vient d'une ad Meta →
              lien direct vers sa fiche « histoire complète » (PUB44). */}
          {showAdBadge && (
            <a
              href={`/publicite/ad/${encodeURIComponent(metaAdId)}`}
              target="_blank"
              rel="noopener noreferrer"
              className={badgeVariants({ tone: 'primary' })}
              title="Ouvrir la fiche de l'annonce Meta à l'origine de ce lead"
            >
              📣 Vient de la pub
            </a>
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

    {/* Dialog de fusion des doublons (LW18) — portalisé hors du rail. */}
    {dupOpen && (
      <Dialog open onOpenChange={(o) => { if (!o) setDupOpen(false) }}>
        <DialogContent className="lw-dup-dialog">
          <DialogTitle>Doublons probables</DialogTitle>
          <table className="lw-dup-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Téléphone</th>
                <th>Ville</th>
                <th aria-label="Action" />
              </tr>
            </thead>
            <tbody>
              {allDups.map((d) => (
                <tr key={d.id}>
                  <td>{`${d.nom ?? ''} ${d.prenom ?? ''}`.trim() || '—'}</td>
                  <td>{d.telephone || '—'}</td>
                  <td>{d.ville || '—'}</td>
                  <td>
                    <Button type="button" size="sm" onClick={() => doMerge(d.id)}>
                      Fusionner ici
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </DialogContent>
      </Dialog>
    )}
    </>
  )
}
