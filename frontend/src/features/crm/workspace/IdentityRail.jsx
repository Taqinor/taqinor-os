import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Badge, badgeVariants, Button, IconButton, StatusPill,
  Avatar, AvatarFallback, DatePicker, FieldSavedPulse,
  Popover, PopoverTrigger, PopoverContent,
  Dialog, DialogContent, DialogTitle,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator,
} from '../../../ui'
import { initials } from '../../../ui/Avatar'
import { normalizeMaPhone, formatDate, formatNumber } from '../../../lib/format'
import { useConfirmDialog, toast } from '../../../ui/confirm'
import { useDuplicateCheck } from '../../../hooks/useDuplicateCheck'
import { useIsAdminOrResponsable } from '../../../hooks/useHasPermission'
import crmApi from '../../../api/crmApi'
import AssigneePicker from '../../../components/AssigneePicker'
import ScoreBadge from '../ScoreBadge'
import StageControl from './StageControl'
import { STATUT_DEVIS } from './DevisTab'
import { CANAL_LABELS, latestDevisTotal, formatMAD } from '../stages'
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

// LWC2 — « Dernier échange » : les seules touches HUMAINES du chatter (une
// modification de champ ou une création automatique n'est pas un échange).
// Vocabulaire de `kind` identique à `TimelineTab.matchesTimelineFilter`.
const ECHANGE_KINDS = new Set(['note', 'appel', 'email'])

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
    if (!leadId) return undefined
    // LW43 — garde d'identité (patron `cancelled` LeadDetailPage.jsx) : une
    // réponse lente pour le lead A arrivant après la navigation vers B ne
    // peint plus les bannières doublons/client_match du lead B.
    let cancelled = false
    // GET paresseux, silencieux sur 404/vide (jamais de bruit).
    crmApi.getLeadDuplicates(leadId)
      .then((r) => { if (!cancelled) setDups(Array.isArray(r.data) ? r.data : []) })
      .catch(() => { if (!cancelled) setDups([]) })
    crmApi.getLeadClientMatch(leadId)
      .then((r) => { if (!cancelled) setClientMatch(Array.isArray(r.data) ? r.data : []) })
      .catch(() => { if (!cancelled) setClientMatch([]) })
    return () => { cancelled = true }
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

  // PV22 — conception 3D DÉJÀ faite pour ce lead : `{kwc, image_url}` servis par
  // la fiche (PV78, RETRIEVE seulement — aucun appel réseau ajouté ici). NULL-SAFE :
  // sans conception le chip DISPARAÎT — jamais un « 0 kWc », jamais une vignette
  // vide (règle « fait vérifié ou rien »).
  const conception = (server.conception && typeof server.conception === 'object')
    ? server.conception : null
  const conceptionKwcBrut = conception?.kwc
  const conceptionKwc = (conceptionKwcBrut != null && conceptionKwcBrut !== '')
    ? Number(conceptionKwcBrut) : null
  const showConception = Number.isFinite(conceptionKwc) && conceptionKwc > 0
  const conceptionImage = (conception?.image_url || '').trim()

  // ── PUB53 — lien retour vers l'annonce Meta d'origine (pur frontend : le
  // serializer crm expose déjà `meta_ad_id` en '__all__', aucun sélecteur
  // adsengine n'est nécessaire côté lecture). Gaté aux rôles qui voient
  // /publicite (responsable/admin — même liste que module.config.jsx).
  const metaAdId = server.meta_ad_id || null
  const canSeePublicite = useIsAdminOrResponsable()
  const showAdBadge = !!metaAdId && canSeePublicite

  // ── Faits clés (LWC2) — bande d'INFO qui remplace 4 des 6 boutons ──────────
  // ZÉRO nouvel appel réseau : tout sort du payload lead DÉJÀ chargé
  // (`devis[]` et `chatter_recent` sont embarqués par le GET détail, LW30).
  // Jamais `prix_achat` ni marge : le total TTC client, rien d'autre (règle #4).
  const dernierDevis = (Array.isArray(server.devis) ? server.devis : [])[0] ?? null
  const montantEstime = latestDevisTotal(server)
  const canal = getField(state, 'canal')
  const canalLabel = canal ? (CANAL_LABELS[canal] ?? canal) : null
  // `chatter_recent` est trié ÉPINGLÉS D'ABORD (backend LW28) : `[0]` n'est donc
  // pas la plus récente — on prend le max de `created_at`. Aucun fetch : si le
  // payload ne porte pas le chatter, la ligne disparaît, point (les points de
  // contact de l'onglet Historique, eux, coûtent une requête — hors sujet ici).
  const dernierEchange = useMemo(() => {
    const rows = Array.isArray(server.chatter_recent) ? server.chatter_recent : []
    let best = null
    for (const a of rows) {
      if (!a || !ECHANGE_KINDS.has(a.kind)) continue
      const t = Date.parse(a.created_at)
      if (Number.isNaN(t)) continue
      if (best == null || t > best) best = t
    }
    return best
  }, [server.chatter_recent])
  const hasFacts = !!(dernierDevis || canalLabel || dernierEchange != null)

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
            /* APX1 — `/crm/clients/:id` n'a JAMAIS existé côté routeur (404
               vérifié) : la fiche client s'ouvre par le lien profond `?id=`
               que ClientList lit déjà (VX220, `ClientList.jsx:71-75`). */
            href={`/crm?id=${clientMatch[0].id}`}
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

      {/* Chips de préparation QX28 (ui/Badge — tokens uniquement, dark-safe).
          LW45 — état « manquant » discret RÉTABLI : l'ancien en-tête (avant
          le shell LW10) stylait aussi ces chips en négatif quand la donnée
          manquait ; le refactor les avait réduits à une simple absence — plus
          aucun signal hors-survol du CTA « Devis automatique ». Toujours
          rendus désormais (tone="neutral", même famille discrète que les
          Badge neutres ailleurs dans l'app), jamais un doublon visuel du
          patron kanban `LeadCard.jsx` (QX28 y est volontairement l'INVERSE —
          micro-icônes denses, jamais de chip « manquant » — un choix
          délibéré pour cette carte-là, pas une régression à répliquer ici). */}
      <div className="lw-rail-chips">
        <Badge
          tone={roofReady ? 'success' : 'neutral'}
          title={roofReady ? 'Un repère GPS de toiture a été capturé (site ou 3D)' : 'Aucun repère GPS de toiture pour le moment'}
        >
          📍 {roofReady ? 'Toit épinglé' : 'Toit non épinglé'}
        </Badge>
        <Badge
          tone={factureReady ? 'info' : 'neutral'}
          title={factureReady ? "Une facture d'électricité a été saisie" : "Aucune facture d'électricité saisie"}
        >
          🧾 {factureReady ? 'Facture saisie' : 'Facture manquante'}
        </Badge>
        <Badge
          tone={devisReady ? 'success' : 'neutral'}
          title={devisReady ? 'Toutes les données nécessaires sont réunies pour générer un devis' : devisNotReadyMsg}
        >
          ⚡ {devisReady ? 'Prêt à deviser' : 'Devis non prêt'}
        </Badge>
        {/* PV22 — la toiture de ce lead a DÉJÀ été calepinée en 3D : puissance
            conçue + vignette du toit. Absent tant qu'aucune conception
            n'existe (jamais un chip « 0 kWc »). */}
        {showConception && (
          <Badge
            tone="success"
            title="Puissance conçue sur le calepinage 3D de ce lead"
            data-testid="lw-chip-conception"
          >
            {conceptionImage && (
              <img
                src={conceptionImage}
                alt=""
                aria-hidden="true"
                style={{
                  width: 16, height: 16, objectFit: 'cover',
                  marginRight: 4, borderRadius: 2, display: 'inline-block',
                  verticalAlign: 'middle',
                }}
              />
            )}
            🛰️ {formatNumber(conceptionKwc, { decimals: 2 })} kWc conçus
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

      {/* LWC2 — Faits clés : la pile de 6 boutons (260-300 px) rendait de la
          PLACE sans information ; ces 2-3 lignes rendent l'information qu'on
          cherchait en ouvrant la fiche. Aucune donnée nouvelle n'est chargée. */}
      {hasFacts && (
        <dl className="lw-facts">
          {dernierDevis && (
            <div className="lw-facts-line">
              <dt className="lw-facts-label">Montant estimé</dt>
              <dd className="lw-facts-value">
                <span className="lw-facts-amount num">{formatMAD(montantEstime)}</span>
                <StatusPill
                  status={dernierDevis.statut}
                  label={STATUT_DEVIS[dernierDevis.statut] ?? dernierDevis.statut}
                  dot={false}
                />
                {dernierDevis.reference && (
                  <span className="lw-facts-ref" title={`Devis ${dernierDevis.reference}`}>
                    {dernierDevis.reference}
                  </span>
                )}
              </dd>
            </div>
          )}
          {canalLabel && (
            <div className="lw-facts-line">
              <dt className="lw-facts-label">Canal</dt>
              <dd className="lw-facts-value">{canalLabel}</dd>
            </div>
          )}
          {dernierEchange != null && (
            <div className="lw-facts-line">
              <dt className="lw-facts-label">Dernier échange</dt>
              <dd className="lw-facts-value num">{formatDate(dernierEchange)}</dd>
            </div>
          )}
        </dl>
      )}

      {/* LWC2 — 2 actions primaires + un menu « ⋯ » pour le reste. « WhatsApp »
          disparaît sous 768 px : la barre-pouce mobile (LeadWorkspace LW34) la
          porte déjà — c'était un doublon, pas une commodité. Les handlers sont
          EXACTEMENT ceux de l'ancienne pile (archiveBusy compris). */}
      <div className="lw-rail-actions">
        <Button
          type="button"
          variant="success"
          className="lw-rail-actions-wa"
          disabled={!waPhone}
          onClick={openWhatsApp}
          title={waPhone ? 'Ouvrir WhatsApp avec ce contact' : 'Numéro de téléphone invalide'}
        >
          🟢 WhatsApp
        </Button>
        <Button
          type="button"
          disabled={!devisReady}
          onClick={() => onAction('open-devis', 'auto')}
          title={devisReady ? 'Créer le devis automatique (affiché ici)' : devisNotReadyMsg}
          // Nom accessible CANONIQUE — le libellé visuel est raccourci pour le
          // rail de 288px, mais le contrat e2e/lecteur d'écran reste
          // « Devis automatique » (classe de bug #29 : dérive de nom accessible).
          aria-label="Devis automatique"
        >
          ⚡ Devis auto
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <IconButton
              type="button"
              variant="outline"
              label="Plus d'actions"
              className="lw-rail-actions-more"
            >
              <span aria-hidden="true">⋯</span>
            </IconButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="lw-rail-actions-menu">
            <DropdownMenuItem
              disabled={!callPhone}
              onSelect={call}
              title={callPhone ? 'Appeler ce contact' : 'Aucun numéro de téléphone'}
            >
              ☎ Appeler
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => onAction('toiture-3d')}
              title="Ouvrir l'outil de conception 3D avec ce lead déjà chargé"
            >
              Concevoir la toiture (3D){hasGps ? ' 📍' : ''}
            </DropdownMenuItem>
            {!alreadyClient && (
              <DropdownMenuItem
                onSelect={() => onAction('convert')}
                title="Convertir ce lead en client (nouveau, existant, ou aucun)"
              >
                Convertir en client
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              destructive={!archived}
              disabled={archiveBusy}
              onSelect={() => onAction('archive')}
              title={archived ? 'Restaurer ce lead' : 'Archiver ce lead'}
            >
              {archived ? 'Restaurer' : 'Archiver'}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
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
