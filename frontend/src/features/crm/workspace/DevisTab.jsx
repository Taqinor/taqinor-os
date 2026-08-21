import { useState } from 'react'
import {
  Zap, FileText, Link2, Check, ExternalLink, MessageCircle, Eye,
} from 'lucide-react'
import {
  Button, Checkbox, Input, StatusPill,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import DocumentStageTrack from '../../../ui/DocumentStageTrack'
import crmApi from '../../../api/crmApi'
import ventesApi from '../../../api/ventesApi'
import installationsApi from '../../../api/installationsApi'
import { formatMAD, formatDate, normalizeMaPhone } from '../../../lib/format'
import { toastError, errorMessageFrom } from '../../../lib/toast'
// L5 (fondateur 21/08/2026) — lien PAGE CLIENT + message WhatsApp, MÊME
// FORMAT que l'outil 3D (ToitureDesign.jsx). Fonctions pures, testées à part.
import { clientProposalUrl, proposalWhatsappText, buildWaUrl } from '../../ventes/clientProposalLink'
// ROUND 5 — LE saut canonique (déplie toujours la section cible), partagé avec
// le centre : le même clic donne désormais le même résultat des deux côtés.
import { jumpToField } from './jumpToField'
import { missingFieldTarget } from './missingFields'
// NTCRM19 — badge de consultation de la salle de vente digitale (NTCRM17/18).
import SalleVenteAnalyticsBadge from '../../../pages/crm/leads/SalleVenteAnalyticsBadge'

// LW21/LW22 — Onglet Devis : la chaîne document en cartes (StatusPill statut
// devis — JAMAIS le funnel lead, règle #2) + le CTA « Devis automatique » qui
// dit ce qui manque + la barre d'envoi WhatsApp multi-devis FR/Darija, portée
// à l'identique (LeadForm.jsx:383-411, 1737-1801) mais avec `wa.selected/
// langue/preview` vivant sur le MOTEUR (via ContextRail) — la sélection ne
// peut plus structurellement survivre à un changement de lead (P1#2).
//
// L5 (fondateur 21/08/2026) — chaque carte devis expose en plus 3 actions
// TOUJOURS visibles (jamais réservées à l'outil 3D) : « Page client » (copie/
// ouvre le lien de la page devis web publique), « WhatsApp » (même format de
// message que ToitureDesign.jsx, sur CE lien), « Aperçu interne (sans
// notification) » — qui rouvre le panneau PDF déjà en service (`view-devis` →
// LeadDevisPanel → GET /ventes/devis/<id>/proposal/, le chemin canonique
// AUTHENTIFIÉ de la règle #4). Ce dernier ne touche JAMAIS le ShareLink
// public (ni `first_viewed_at`/`view_count`, ni la note chatter « devis
// ouvert », ni la notification au responsable posées par
// `apps/ventes/public_views.py::_stamp_view`/`_notify_first_open`) : il ne
// résout même pas de token, donc rien de ce mécanisme ne peut s'y déclencher
// — sûr par CONSTRUCTION, pas par un indicateur qu'on pourrait oublier de
// vérifier.

// L5 — site public (page client), même résolution que ToitureDesign.jsx.
const PUBLIC_SITE_URL = import.meta.env.VITE_PUBLIC_SITE_URL || 'https://taqinor.ma'

// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que DEVIS_MINI_TRACK
export const STATUT_DEVIS = {
  brouillon: 'Brouillon', envoye: 'Envoyé', accepte: 'Accepté',
  refuse: 'Refusé', expire: 'Expiré',
}

// Mini-piste DOCUMENT (règle #4) devis→facture→chantier — JAMAIS les stages
// STAGES.py du funnel lead (règle #2). N'est rendue QUE sur une carte devis
// ACCEPTÉE. `Lead.devis[]` (serializers.get_devis) n'expose ni BC ni facture
// liée (contrairement à la requête dédiée de DevisList.jsx) — seul `chantier`
// est disponible : la piste avance donc directement de « Accepté » à
// « Chantier » quand un chantier existe, sans distinguer un état
// intermédiaire « Facturé » (limitation de donnée documentée, pas un choix
// arbitraire — voir le rapport de fin de lane).
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que ChatterTimeline.OUTCOME_LABELS
export const DEVIS_MINI_TRACK = [
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'envoye', label: 'Envoyé' },
  { key: 'accepte', label: 'Accepté' },
  { key: 'facture', label: 'Facturé' },
  { key: 'chantier', label: 'Chantier' },
]

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function devisTrackCurrent(d) {
  return d?.chantier ? 'chantier' : 'accepte'
}

// LW21 — mapping libellés backend (apps/crm/devis_auto.py `champs_manquants`,
// texte FR fixe — source unique règle serveur/UI) → id DOM du champ dans
// SectionsPane (ids `lf-*`).
// ROUND 5 — la carte a DÉMÉNAGÉ dans `missingFields.js` : le bandeau « À
// compléter » du centre doit pointer EXACTEMENT les mêmes champs que cet
// onglet, et deux cartes divergentes seraient pires que pas de carte. On la
// réexporte ici pour que rien de ce qui l'importait de `./DevisTab` ne bouge.
// eslint-disable-next-line react-refresh/only-export-components -- réexport de logique pure (testable), même motif que ChatterTimeline.OUTCOME_LABELS
export { DEVIS_AUTO_FIELD_IDS, missingFieldTarget } from './missingFields'

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function waArmed(phone, selectedCount) {
  return !!normalizeMaPhone(phone) && selectedCount > 0
}

// EZ5 — intention d'ouverture du panneau devis. Sans puissance cible saisie on
// renvoie la CHAÎNE de mode historique (aucun appelant existant ne bouge :
// IdentityRail, palette de commandes, tests) ; avec une cible on renvoie
// l'objet { mode, targetKwc } que LeadWorkspace sait aussi lire. La cible ne
// concerne que les modes qui DIMENSIONNENT (auto/remise/onepage/premium) —
// « edit » ouvre le générateur, qui a son propre champ kWc (EZ5, 1ʳᵉ moitié).
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function devisIntent(mode, kwcCible) {
  const cible = String(kwcCible ?? '').trim()
  if (!cible || mode === 'edit') return mode
  return { mode, targetKwc: cible }
}

// ROUND 5 — plus de saut maison : `jumpToField` DÉPLIE toujours la section
// cible avant de scroller et de focaliser. Avant, ce chemin ne dépliait pas —
// un champ dans une section repliée n'est pas dans le DOM, on retombait donc
// sur l'en-tête de section et le même clic donnait deux résultats différents
// selon l'état de repli. Un seul chemin, partagé avec le centre.
function jumpToMissingField(label) {
  const target = missingFieldTarget(label)
  if (!target) return
  jumpToField(target)
}

export default function DevisTab({
  state, onAction, wa, onWaToggle, onWaLangue, onWaPreview, onWaReset,
}) {
  const devisList = state.server?.devis ?? []
  const devisAuto = state.server?.devis_auto ?? { pret: false, manquants: [] }
  const leadPhone = (state.server?.whatsapp || state.server?.telephone || '').trim()
  const leadPhoneOk = !!normalizeMaPhone(leadPhone)

  const [busyAction, setBusyAction] = useState(null) // `f-<id>` | `c-<id>` | null
  const [actionMsg, setActionMsg] = useState(null)
  // EZ5 — puissance cible (kWc) FACULTATIVE du devis automatique : le client
  // dit « je veux 3 kWc », pas « je veux 4 panneaux ». Vide = dimensionnement
  // historique (taille souhaitée du lead, sinon facture d'hiver) : le trajet
  // à 1 clic du commercial est INCHANGÉ.
  const [kwcCible, setKwcCible] = useState('')
  const [waBusy, setWaBusy] = useState(false)

  // L5 — les 3 actions « Page client / WhatsApp / Aperçu interne » ci-dessous.
  // Busy PAR devis + PAR action (préfixes `l-`/`o-`/`w-`), distinct de
  // `busyAction` (facture/chantier) : deux familles d'actions indépendantes,
  // jamais de collision de clé.
  const [linkBusy, setLinkBusy] = useState(null)
  const [copiedId, setCopiedId] = useState(null)

  // Mint (ou réutilise — idempotent côté serveur) le ShareLink du devis et
  // renvoie l'URL ABSOLUE de la page client (chemin_proposition backend),
  // MÊME lien que celui déjà envoyé par email/WhatsApp/l'outil 3D.
  const mintProposalUrl = async (d) => {
    const res = await ventesApi.shareLinkDevis(d.id)
    return clientProposalUrl(res.data?.path, PUBLIC_SITE_URL)
  }

  const copierPageClient = async (d) => {
    setLinkBusy(`l-${d.id}`)
    setActionMsg(null)
    try {
      const url = await mintProposalUrl(d)
      try {
        await navigator.clipboard?.writeText(url)
        setCopiedId(d.id)
        window.setTimeout(() => setCopiedId((cur) => (cur === d.id ? null : cur)), 2000)
      } catch { /* presse-papier indisponible — le lien reste ouvrable */ }
    } catch (err) {
      setActionMsg(errorMessageFrom(err, 'Lien de la page client indisponible.'))
    } finally {
      setLinkBusy(null)
    }
  }

  const ouvrirPageClient = async (d) => {
    setLinkBusy(`o-${d.id}`)
    setActionMsg(null)
    try {
      const url = await mintProposalUrl(d)
      window.open(url, '_blank', 'noopener')
    } catch (err) {
      setActionMsg(errorMessageFrom(err, 'Lien de la page client indisponible.'))
    } finally {
      setLinkBusy(null)
    }
  }

  // WhatsApp PAR devis (distinct de la barre multi-devis LW22 ci-dessous :
  // celle-ci lie le PDF direct `/api/django/public/document/<token>/` ; ici on
  // partage la PAGE CLIENT web, MÊME message que ToitureDesign.jsx).
  const envoyerWhatsAppUnique = async (d) => {
    if (!leadPhoneOk) return
    setLinkBusy(`w-${d.id}`)
    setActionMsg(null)
    try {
      const url = await mintProposalUrl(d)
      const nom = `${state.server?.nom ?? ''} ${state.server?.prenom ?? ''}`.trim()
      const waUrl = buildWaUrl(normalizeMaPhone(leadPhone), proposalWhatsappText(nom, url))
      if (waUrl) window.open(waUrl, '_blank', 'noopener')
    } catch (err) {
      setActionMsg(errorMessageFrom(err, 'Lien WhatsApp indisponible.'))
    } finally {
      setLinkBusy(null)
    }
  }

  const genererFacture = (d) => {
    setBusyAction(`f-${d.id}`)
    setActionMsg(null)
    ventesApi.genererFacture(d.id)
      .then((res) => {
        const f = res.data
        setActionMsg(`${f.type_facture_display ?? 'Facture'} ${f.reference} créée.`)
        onAction?.('refresh')
      })
      .catch((err) => setActionMsg(errorMessageFrom(err, 'Génération de facture impossible.')))
      .finally(() => setBusyAction(null))
  }

  const creerChantier = (d) => {
    setBusyAction(`c-${d.id}`)
    setActionMsg(null)
    installationsApi.createFromDevis(d.id)
      .then((res) => {
        setActionMsg(`Chantier ${res.data.reference} prêt.`)
        onAction?.('refresh')
      })
      .catch((err) => setActionMsg(errorMessageFrom(err, 'Création du chantier impossible.')))
      .finally(() => setBusyAction(null))
  }

  const envoyerWhatsApp = () => {
    if (!waArmed(leadPhone, wa.selected.length) || !state.leadId) return
    setWaBusy(true)
    crmApi.whatsappDevis(state.leadId, { devis_ids: wa.selected, langue: wa.langue })
      .then((res) => {
        onWaPreview({
          message: res.data?.message ?? '',
          links: res.data?.links ?? [],
          wa_url: res.data?.wa_url ?? '',
        })
      })
      .catch((err) => toastError(errorMessageFrom(err, 'Envoi WhatsApp impossible.')))
      .finally(() => setWaBusy(false))
  }

  const ouvrirWhatsApp = () => {
    if (wa.preview?.wa_url) window.open(wa.preview.wa_url, '_blank', 'noopener')
    onWaReset()
  }

  return (
    <div className="lw-context-devis">
      <SalleVenteAnalyticsBadge leadId={state.leadId} />
      {devisAuto.pret ? (
        <div className="lw-context-devis-cta">
          <Button
            type="button"
            variant="default"
            onClick={() => onAction?.('open-devis', devisIntent('auto', kwcCible))}
          >
            <Zap size={14} aria-hidden="true" /> Devis automatique
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="outline" size="sm">
                <FileText size={14} aria-hidden="true" /> Devis modifiable ▾
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', devisIntent('remise', kwcCible))}>Remise %…</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', devisIntent('onepage', kwcCible))}>Devis 1 page</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', devisIntent('premium', kwcCible))}>Devis premium</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', 'edit')}>Édition complète…</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {/* EZ5 — cible kWc facultative. `step="any"` + aucune validation
              bloquante : ce champ ne rejette ni n'arrondit jamais une saisie
              (même garde que le générateur). */}
          <div className="lw-devis-kwc">
            <label htmlFor="lw-devis-kwc" className="lw-devis-kwc-label">
              Puissance cible (kWc)
            </label>
            <Input
              id="lw-devis-kwc"
              data-testid="lw-devis-kwc"
              type="number"
              min="0"
              step="any"
              inputMode="decimal"
              placeholder="auto"
              className="lw-devis-kwc-input"
              value={kwcCible}
              onChange={(e) => setKwcCible(e.target.value)}
            />
          </div>
        </div>
      ) : (
        <div className="lw-context-devis-missing">
          <p className="gen-hint">Devis automatique — champs manquants :</p>
          <ul className="lw-context-missing-list">
            {(devisAuto.manquants ?? []).map((label) => (
              <li key={label}>
                <button
                  type="button"
                  className="lw-context-missing-link"
                  onClick={() => jumpToMissingField(label)}
                >
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="lw-context-devis-list">
        {devisList.length === 0 ? (
          <p className="gen-hint">Aucun devis pour ce lead.</p>
        ) : (
          devisList.map((d) => (
            <div key={d.id} className="lw-context-devis-card">
              <div className="lw-context-devis-card-head">
                <Checkbox
                  checked={wa.selected.includes(d.id)}
                  onCheckedChange={() => onWaToggle(d.id)}
                  aria-label={`Sélectionner ${d.reference} pour WhatsApp`}
                />
                <button
                  type="button"
                  className="lw-context-devis-ref"
                  title="Voir / télécharger le PDF dans la fiche"
                  onClick={() => onAction?.('view-devis', d.id)}
                >
                  {d.reference}
                </button>
                <StatusPill status={d.statut} label={STATUT_DEVIS[d.statut] ?? d.statut} />
              </div>
              <div className="lw-context-devis-card-body">
                <span className="num">{formatMAD(d.total_ttc, { decimals: 0 })}</span>
                <span className="lw-context-devis-date">{formatDate(d.date_creation)}</span>
              </div>
              {/* L5 — TOUJOURS visibles (jamais réservées à l'outil 3D) : le
                  lien de la page client, son bouton WhatsApp, et l'aperçu
                  interne qui n'enclenche aucune notification. */}
              <div className="lw-context-devis-links">
                <Button
                  type="button" size="sm" variant="outline"
                  disabled={linkBusy === `l-${d.id}`}
                  title="Copier le lien de la page client (page devis web publique)"
                  onClick={() => copierPageClient(d)}
                >
                  {copiedId === d.id
                    ? <Check size={14} aria-hidden="true" />
                    : <Link2 size={14} aria-hidden="true" />}
                  {copiedId === d.id ? 'Copié' : 'Page client'}
                </Button>
                <Button
                  type="button" size="sm" variant="ghost"
                  disabled={linkBusy === `o-${d.id}`}
                  aria-label={`Ouvrir la page client de ${d.reference} dans un nouvel onglet`}
                  title="Ouvrir la VRAIE page client (compte comme une lecture côté suivi — pour regarder sans notifier, utilisez l'aperçu interne)"
                  onClick={() => ouvrirPageClient(d)}
                >
                  <ExternalLink size={14} aria-hidden="true" />
                </Button>
                <Button
                  type="button" size="sm" variant="outline"
                  disabled={!leadPhoneOk || linkBusy === `w-${d.id}`}
                  title={leadPhoneOk
                    ? 'Envoyer le lien de la page client par WhatsApp'
                    : 'Aucun numéro de téléphone exploitable'}
                  onClick={() => envoyerWhatsAppUnique(d)}
                >
                  <MessageCircle size={14} aria-hidden="true" /> WhatsApp
                </Button>
                <Button
                  type="button" size="sm" variant="outline"
                  title="Ouvre le PDF client sans notifier le lead ni marquer le devis consulté (chemin interne /proposal — ne touche jamais le ShareLink public)"
                  onClick={() => onAction?.('view-devis', d.id)}
                >
                  <Eye size={14} aria-hidden="true" /> Aperçu interne (sans notification)
                </Button>
              </div>
              {d.statut === 'accepte' && (
                <>
                  <DocumentStageTrack
                    className="lw-context-devis-track"
                    stages={DEVIS_MINI_TRACK}
                    current={devisTrackCurrent(d)}
                  />
                  <div className="lw-context-devis-actions">
                    <Button
                      type="button" size="sm" variant="outline"
                      disabled={busyAction === `f-${d.id}`}
                      onClick={() => genererFacture(d)}
                    >
                      {busyAction === `f-${d.id}` ? '…' : '🧾 Générer la facture'}
                    </Button>
                    {d.chantier ? (
                      <span className="gen-hint" title="Chantier déjà créé">🏗 {d.chantier.reference}</span>
                    ) : (
                      <Button
                        type="button" size="sm" variant="outline"
                        disabled={busyAction === `c-${d.id}`}
                        onClick={() => creerChantier(d)}
                      >
                        {busyAction === `c-${d.id}` ? '…' : '🏗 Créer le chantier'}
                      </Button>
                    )}
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>
      {actionMsg && <p className="gen-hint" role="status">{actionMsg}</p>}

      {devisList.length > 0 && (
        <div className="lw-context-wa-bar">
          <Button
            type="button" variant="success" loading={waBusy}
            disabled={!waArmed(leadPhone, wa.selected.length) || waBusy}
            title={!leadPhone
              ? 'Aucun numéro de téléphone'
              : !leadPhoneOk
                ? 'Numéro invalide'
                : 'Préparer le message WhatsApp pour le(s) devis sélectionné(s)'}
            onClick={envoyerWhatsApp}
          >
            {waBusy ? 'Préparation…' : '🟢'} Envoyer par WhatsApp{wa.selected.length > 0 ? ` (${wa.selected.length})` : ''}
          </Button>
          <div role="group" aria-label="Langue du message WhatsApp" className="lw-context-wa-langue">
            {[['fr', 'FR'], ['darija', 'Darija']].map(([val, label]) => (
              <Button
                key={val} type="button" size="sm"
                variant={wa.langue === val ? 'default' : 'outline'}
                aria-pressed={wa.langue === val}
                onClick={() => onWaLangue(val)}
              >
                {label}
              </Button>
            ))}
          </div>
          {!leadPhone && <span className="gen-hint">Aucun numéro de téléphone</span>}
          {leadPhone && !leadPhoneOk && <span className="gen-hint">Numéro invalide</span>}
        </div>
      )}

      <Dialog open={!!wa.preview} onOpenChange={(o) => { if (!o) onWaPreview(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aperçu du message WhatsApp</DialogTitle>
            <DialogDescription>
              {wa.langue === 'darija' ? 'Variante Darija' : 'Variante Français'}
              {' '}— vérifiez le texte et le(s) lien(s), puis ouvrez WhatsApp.
            </DialogDescription>
          </DialogHeader>
          <pre className="lw-context-wa-preview">{wa.preview?.message}</pre>
          {(wa.preview?.links?.length ?? 0) > 0 && (
            <ul className="gen-hint lw-context-wa-links">
              {wa.preview.links.map((l) => (
                <li key={l.devis_id ?? l.url}>{l.reference} : {l.url}</li>
              ))}
            </ul>
          )}
          <div className="lw-context-wa-dialog-actions">
            <Button type="button" variant="ghost" onClick={() => onWaPreview(null)}>Annuler</Button>
            <Button type="button" variant="success" disabled={!wa.preview?.wa_url} onClick={ouvrirWhatsApp}>
              🟢 Ouvrir WhatsApp
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
