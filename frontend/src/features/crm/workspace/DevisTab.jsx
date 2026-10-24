import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Zap, FileText, Eye, Send, Pencil,
} from 'lucide-react'
import {
  Button, Checkbox, Input, StatusPill,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import DocumentStageTrack from '../../../ui/DocumentStageTrack'
import crmApi from '../../../api/crmApi'
import PanneauVente from '../../ventes/vente/PanneauVente'
import installationsApi from '../../../api/installationsApi'
import { formatMAD, formatDate, normalizePhoneE164 } from '../../../lib/format'
import { toastError, errorMessageFrom } from '../../../lib/toast'
// ALEA52 — la boîte « Envoyer au client » (partagée avec l'aperçu du panneau devis).
import EnvoiDevisDialog from './EnvoiDevisDialog'
import { useEnvoiDevis } from './useEnvoiDevis'
// QJR41 (audit L3 29/08/2026) — MÊME formule que la doctrine fondateur du
// 18/08 (`autoQuote.js:146-152`, palier de 5 kWc, jamais retirée) : lue ici en
// PURE LECTURE pour prévenir le commercial, jamais pour arrondir le champ lui-même.
// QJR534 — droits lus du serveur + geste « Réviser » unique (QJR532/QJR533).
import { peutEditerDevis, peutReviserDevis } from '../../ventes/devisStatuts'
import { reviserEtOuvrir } from '../../ventes/reviserDevis'
// ROUND 5 — LE saut canonique (déplie toujours la section cible), partagé avec
// le centre : le même clic donne désormais le même résultat des deux côtés.
import { jumpToField } from './jumpToField'
import { missingFieldTarget, missingChampPourLead } from './missingFields'
import {
  DEVIS_MINI_TRACK, devisTrackCurrent, waArmed, devisIntent, lectureClientLabel,
  catalogueCiBloque, raisonCatalogueCi, noteDemandeCatalogueCi,
} from './devisTabLogique'
import { libelleStatutDevis } from '../../ventes/devisStatuts'
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

// ROUND 5 — plus de saut maison : `jumpToField` DÉPLIE toujours la section
// cible avant de scroller et de focaliser. Avant, ce chemin ne dépliait pas —
// un champ dans une section repliée n'est pas dans le DOM, on retombait donc
// sur l'en-tête de section et le même clic donnait deux résultats différents
// selon l'état de repli. Un seul chemin, partagé avec le centre.
function jumpToMissingField(champ, state) {
  const target = missingFieldTarget(missingChampPourLead(champ, state))
  if (!target) return
  jumpToField(target)
}

// QJR534 — le bouton « Réviser » porte SON `useNavigate` (monté seulement sur
// une carte révisable) : le reste de l'onglet n'exige aucun contexte Router.
// VNT80 — un refus qui nomme un autre devis s'affiche SOUS la carte avec
// « Ouvrir <réf> », qui fait défiler jusqu'à la carte de la tête.
function BoutonReviser({ devis }) {
  const navigate = useNavigate()
  const [conflit, setConflit] = useState(null)
  const ouvrir = (id) => document.getElementById(`devis-carte-${id}`)?.scrollIntoView({ block: 'center' })
  return (
    <>
      <Button
        type="button" size="sm" variant="outline"
        onClick={() => { setConflit(null); reviserEtOuvrir({ devis, navigate, onConflit: setConflit }) }}
      >
        <Pencil size={14} aria-hidden="true" /> Réviser (nouvelle version)
      </Button>
      {conflit && (
        <p className="basis-full text-sm text-destructive" role="alert">
          {conflit.conflit}{' '}
          <Button type="button" size="sm" variant="link" onClick={() => ouvrir(conflit.successeur.id)}>
            Ouvrir {conflit.successeur.reference}
          </Button>
        </p>
      )}
    </>
  )
}

// ALEA50 (D-ACI-6=a) — le devis automatique C&I est BLOQUÉ tant que des postes
// fixes (forfaits société, coffrets, protection AC, comptage) n'ont pas de prix :
// le bouton est désactivé AVEC son motif, les liens mènent où les régler, et
// « Demander au responsable » laisse une note chatter qui NOMME les postes.
function BlocCatalogueCi({ devisAuto, leadId }) {
  const [demande, setDemande] = useState('idle') // idle | envoi | ok | erreur
  const postes = devisAuto.catalogue_ci?.manquants ?? []
  const demander = () => {
    if (!leadId || demande === 'envoi') return
    setDemande('envoi')
    crmApi.noterLead(leadId, noteDemandeCatalogueCi(devisAuto))
      .then(() => setDemande('ok'))
      .catch((err) => {
        setDemande('erreur')
        toastError(errorMessageFrom(err, 'La demande n’a pas pu être enregistrée — réessayez.'))
      })
  }
  return (
    <div className="lw-context-devis-cta lw-context-devis-bloque" data-testid="lw-devis-catalogue-ci">
      <Button
        type="button" variant="default" disabled
        data-testid="lw-devis-auto-bloque"
        title={raisonCatalogueCi(devisAuto)}
      >
        <Zap size={14} aria-hidden="true" /> Devis automatique
      </Button>
      <p className="gen-hint" role="status">{raisonCatalogueCi(devisAuto)}</p>
      <ul className="lw-context-missing-list">
        {postes.map((p) => <li key={p}>{p}</li>)}
      </ul>
      <p className="gen-hint">
        À régler dans <Link to="/parametres">Paramètres</Link> (prestations) ou{' '}
        <Link to="/stock">Produits</Link> (articles).
      </p>
      <Button
        type="button" size="sm" variant="outline"
        data-testid="lw-devis-demander-responsable"
        disabled={demande === 'envoi' || demande === 'ok'}
        onClick={demander}
      >
        {demande === 'ok' ? 'Demande enregistrée dans le fil' : 'Demander au responsable'}
      </Button>
    </div>
  )
}

export default function DevisTab({
  state, onAction, wa, onWaToggle, onWaLangue, onWaPreview, onWaReset,
}) {
  const devisList = state.server?.devis ?? []
  const devisAuto = state.server?.devis_auto ?? { pret: false, manquants: [] }
  const leadPhone = (state.server?.whatsapp || state.server?.telephone || '').trim()
  const leadPhoneOk = !!normalizePhoneE164(leadPhone)

  const [busyAction, setBusyAction] = useState(null) // `f-<id>` | `c-<id>` | null
  const [actionMsg, setActionMsg] = useState(null)
  // EZ5 — puissance cible (kWc) FACULTATIVE du devis automatique : le client
  // dit « je veux 3 kWc », pas « je veux 4 panneaux ». Vide = dimensionnement
  // historique (taille souhaitée du lead, sinon facture d'hiver) : le trajet
  // à 1 clic du commercial est INCHANGÉ.
  const [kwcCible, setKwcCible] = useState('')
  // AGNR39 — au pompage, le champ solaire découle de la pompe : le champ
  // « puissance cible » n'est pas affiché pour un lead agricole, la cible
  // reste donc vide (le serveur la refuserait en la nommant).
  const agricole = state.server?.type_installation === 'agricole'
  // QJR602 (D-QJR5-13) — la cible tapée ici part TELLE QUELLE : le devis
  // automatique n'arrondit plus au palier de 5 kWc, plus aucun avis à montrer.
  const [waBusy, setWaBusy] = useState(false)

  // ALEA52 — la boîte « Envoyer au client » (état + gestes : WhatsApp, e-mail,
  // copier le lien, réglages avancés) est PARTAGÉE avec l'aperçu du panneau devis
  // de la fiche (LeadDevisPanel) : useEnvoiDevis.js / EnvoiDevisDialog.jsx.
  const envoi = useEnvoiDevis({
    leadPhone,
    leadEmail: (state.server?.email || '').trim(),
    leadNom: `${state.server?.nom ?? ''} ${state.server?.prenom ?? ''}`.trim(),
    onRefresh: () => onAction?.('refresh'),
    leadId: state.leadId,
    relanceActuelle: state.server?.relance_date ?? null,
  })
  // Quel devis a sa boîte d'envoi ouverte (id | null).
  const [envoiOuvert, setEnvoiOuvert] = useState(null)

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
    // QJR538 — l'aperçu n'écrit RIEN : « Annuler » laisse les devis tels quels.
    crmApi.whatsappDevisApercu(state.leadId, { devis_ids: wa.selected, langue: wa.langue })
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
    // QJR538 — seul ce geste marque les devis envoyés (commit serveur).
    const payload = { devis_ids: wa.selected, langue: wa.langue }
    if (state.leadId && wa.selected.length) {
      crmApi.whatsappDevis(state.leadId, payload)
        .then(() => onAction?.('refresh'))
        .catch((err) => toastError(errorMessageFrom(err, 'Envoi WhatsApp non enregistré.')))
    }
    onWaReset()
  }

  return (
    <div className="lw-context-devis">
      <SalleVenteAnalyticsBadge leadId={state.leadId} />
      {/* QJR599 — un devis MANUEL se démarre TOUJOURS depuis le cockpit, même
          quand le devis automatique n'est pas prêt (facture inconnue…) : le
          mode 'edit' sans devisId monte simplement le générateur. Ce bouton
          crée un NOUVEAU devis — jamais le chemin de correction d'un envoyé
          (« Modifier » de la carte, QJR534). Auto / remise / 1 page /
          premium restent conditionnés à devis_auto.pret. */}
      <div className="lw-context-devis-nouveau">
        <Button
          type="button"
          variant="outline"
          size="sm"
          data-testid="lw-devis-edition"
          onClick={() => onAction?.('open-devis', 'edit')}
        >
          <FileText size={14} aria-hidden="true" /> Nouveau devis (édition complète)…
        </Button>
      </div>
      {devisAuto.pret && catalogueCiBloque(devisAuto) ? (
        <BlocCatalogueCi devisAuto={devisAuto} leadId={state.leadId} />
      ) : devisAuto.pret ? (
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
              {/* ALEA55 — « Devis 1 page » / « Devis premium » CRÉAIENT un second
                  devis (anti-doublon 120 s) : ce sont des FORMATS du PDF d'un devis
                  existant, au menu « PDF » de chaque carte. */}
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', devisIntent('remise', kwcCible))}>Remise %…</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {/* EZ5 — cible kWc facultative. `step="any"` + aucune validation
              bloquante : ce champ ne rejette ni n'arrondit jamais une saisie
              (même garde que le générateur). */}
          {!agricole && <div className="lw-devis-kwc">
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
          </div>}
        </div>
      ) : (
        <div className="lw-context-devis-missing">
          <p className="gen-hint">Devis automatique — champs manquants :</p>
          <ul className="lw-context-missing-list">
            {/* QJR601 — la cible vient du NOM DU CHAMP servi, jamais du libellé. */}
            {(devisAuto.manquants_detail ?? []).map(({ champ, label }) => (
              <li key={champ}>
                <button
                  type="button"
                  className="lw-context-missing-link"
                  onClick={() => jumpToMissingField(champ, state)}
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
            <div key={d.id} id={`devis-carte-${d.id}`} className="lw-context-devis-card">
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
                <StatusPill status={d.statut} label={libelleStatutDevis(d.statut)} />
                {/* QJR535 — une version remplacée n'est plus vivante : badge
                    « Remplacé par <référence> » (résolue dans la même liste),
                    plus d'« Envoyer au client » (la V1 obsolète ne se renvoie
                    pas). */}
                {d.is_active === false && (
                  <span className="lw-context-devis-niveau-badge" data-testid={`devis-remplace-${d.id}`}>
                    {(() => {
                      const ref = devisList.find((x) => x.id === d.superseded_by)?.reference
                      return ref ? `Remplacé par ${ref}` : 'Version remplacée'
                    })()}
                  </span>
                )}
              </div>
              <div className="lw-context-devis-card-body">
                <span className="num">{formatMAD(d.total_ttc, { decimals: 0 })}</span>
                <span className="lw-context-devis-date">{formatDate(d.date_creation)}</span>
              </div>
              {/* QJ-VUES (fondateur 09/09/2026) — combien de fois le CLIENT a
                  ouvert ce devis, TOUJOURS visible sur la carte (aucun clic,
                  aucun dialogue). Chiffre serveur (`d.lecture`), lectures
                  humaines uniquement : les pré-chargements d'aperçu WhatsApp
                  et les crawlers n'y entrent plus (QJ-ROBOTS), et l'« Aperçu
                  interne » n'y a jamais compté (L-INTPREV). */}
              <div
                className={`lw-context-devis-lectures${(Number(d.lecture?.nombre_vues ?? 0) > 0) ? ' is-lu' : ''}`}
              >
                <Eye size={13} aria-hidden="true" />
                <span>{lectureClientLabel(d.lecture, d.corrige_le)}</span>
              </div>
              {/* L-NIV-UI — badge d'état du lien, TOUJOURS visible sur la carte
                  (le dialogue d'envoi ci-dessous n'a pas à être ouvert pour
                  savoir ce que le client reçoit aujourd'hui). */}
              {envoi.currentLinkMeta(d) && (
                <div className="lw-context-devis-niveau">
                  <span
                    className="lw-context-devis-niveau-badge"
                    title="Le lien reste le même — seul le niveau affiché au client change."
                  >
                    {envoi.currentLinkMeta(d).niveau === 'confiance' ? 'Confiance' : 'Standard'}
                    {envoi.currentLinkMeta(d).otp_lecture ? ' · OTP' : ''}
                  </span>
                </div>
              )}
              {/* L-SECT (fondateur 24/08/2026) — TOUT l'envoi passe par UN
                  dialogue : le commercial choisit le niveau, l'OTP et les
                  sections que le client reçoit, PUIS copie / ouvre / envoie.
                  L'aperçu interne reste hors dialogue : il ne touche jamais le
                  ShareLink public, ce n'est pas un envoi. */}
              <div className="lw-context-devis-links">
                {d.is_active !== false && (
                  <Button
                    type="button" size="sm" variant="default"
                    onClick={() => setEnvoiOuvert(d.id)}
                  >
                    <Send size={14} aria-hidden="true" /> Envoyer au client
                  </Button>
                )}
                <Button
                  type="button" size="sm" variant="outline"
                  title="Ouvre le PDF client sans notifier le lead ni marquer le devis consulté (chemin interne /proposal — ne touche jamais le ShareLink public)"
                  onClick={() => onAction?.('view-devis', d.id)}
                >
                  <Eye size={14} aria-hidden="true" /> Aperçu interne (sans notification)
                </Button>
                {/* ALEA55 — le FORMAT du PDF d'un devis existant (jamais un second devis). */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button" size="sm" variant="outline"
                      aria-label={`Format du PDF de ${d.reference}`}
                    >
                      <FileText size={14} aria-hidden="true" /> PDF ▾
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start">
                    <DropdownMenuItem onSelect={() => onAction?.('view-devis', { id: d.id, pdf: 'full' })}>
                      Premium (PDF complet)
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => onAction?.('view-devis', { id: d.id, pdf: 'onepage' })}>
                      1 page
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                {/* QJR534 (D-QJR5-1/2) — l'UNIQUE porteur de « Modifier » et de
                    « Réviser » sur la carte. Droits LUS du serveur (QJR516) :
                    brouillon/envoyé → Modifier (correction sur place) ;
                    révisable → Réviser, pour tout rôle d'écriture, avec
                    avertissement si un chantier est en cours. */}
                {peutEditerDevis(d) && (
                  <Button
                    type="button" size="sm" variant="outline"
                    onClick={() => onAction?.('edit-devis', d.id)}
                  >
                    <Pencil size={14} aria-hidden="true" /> Modifier
                  </Button>
                )}
                {peutReviserDevis(d) && <BoutonReviser devis={d} />}
              </div>
              <EnvoiDevisDialog
                devis={d}
                envoi={envoi}
                ouvert={envoiOuvert === d.id}
                onOuvertChange={(o) => setEnvoiOuvert(o ? d.id : null)}
                modeDevis={d.mode_installation ?? state.server?.type_installation ?? null}
              />
              {d.statut === 'accepte' && (
                <>
                  <DocumentStageTrack
                    className="lw-context-devis-track"
                    stages={DEVIS_MINI_TRACK}
                    current={devisTrackCurrent(d)}
                  />
                  {/* VNT74/VNT75 — la vente LUE de `d.vente` ; facturer = `vente.peut`. */}
                  <PanneauVente devis={d} onRafraichir={() => onAction?.('refresh')} />
                  <div className="lw-context-devis-actions">
                    {d.chantier ? (
                      // CHT21(b) — span inerte devenu cliquable : deep-link
                      // réel vers la fiche chantier (patron ?id= déjà lu par
                      // InstallationsPage.jsx:343), jamais la liste nue.
                      <Link to={`/chantiers?id=${d.chantier.id}`}
                            className="gen-hint" title="Voir le chantier">
                        🏗 {d.chantier.reference}
                      </Link>
                    ) : d.is_active !== false && (
                      // ACHT5 — seule la tête de chaîne active propose la
                      // création : une version remplacée (is_active=false)
                      // n'a jamais de chantier à elle.
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
