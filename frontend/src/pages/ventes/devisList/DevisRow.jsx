import { Fragment } from 'react'
import { useSelector } from 'react-redux'
import {
  Plus, FileText, FileDown, Check, ArrowRight, HardHat, FileStack,
  Copy, Send, X, Eye, AlertTriangle, Box, ExternalLink,
  Link2, MoreHorizontal, Bell, Share2,
} from 'lucide-react'
import { fetchDevis } from '../../../features/ventes/store/ventesSlice.js'
import ventesApi from '../../../api/ventesApi.js'
import {
  Button, Badge, StatusPill, Checkbox, Textarea,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel,
  // APX17 — les signaux secondaires du statut passent dans un Popover.
  Popover, PopoverTrigger, PopoverContent,
} from '../../../ui/index.js'
import { formatMAD, formatDateTime } from '../../../lib/format.js'
// NTI18N12 — calendrier hégirien EN PLUS de la date grégorienne (jamais en
// remplacement, jamais stocké), uniquement quand locale=ar ET la préférence
// utilisateur est active.
import { formatWithHijri, shouldShowHijri } from '../../../lib/hijriDate.js'
import { useI18n } from '../../../i18n/index.js'
import { useRotatingLabel } from '../../../hooks/useRotatingLabel.js'
import RoofViewer from '../RoofViewer'
// ANALYT1 — panneau « Lecture par le client » (visites par section + friction).
import DevisSuiviPartagePanel from '../DevisSuiviPartagePanel'
// PV43 — panneau « Conception électrique » (chaînes/conformité/schéma/surcharges).
import ConceptionElectrique from '../../../features/ventes/ConceptionElectrique'
// PV76 — carte « Étude bancable » (P50/P90/PR/cascade/payback/VAN/TRI).
import EtudeBancable from '../../../features/ventes/EtudeBancable'
import DocumentStageTrack from '../../../ui/DocumentStageTrack'
// APX13 — la piste devis→BC→facture, définie UNE fois pour les 3 écrans.
import { DOC_STATUT_TRACK } from '../../../features/ventes/documentChain.js'
import { peutEditerDevis, chantierEnCours } from '../../../features/ventes/devisStatuts.js'
import { reviserEtOuvrir } from '../../../features/ventes/reviserDevis.js'
import { STATUT_DISPLAY } from './devisListConstants.js'

// VX132 — chargement long CONSCIENT : la génération du devis PDF premium est
// la latence connue la plus longue de l'app (schémas, produits, chiffrage) ;
// un spinner MUET pendant tout ce temps ne dit rien d'utile. Libellés
// honnêtes qui tournent pendant l'attente — ne touche QUE ce bouton côté
// client, jamais le moteur `apps/ventes/quote_engine/` (règle #4).
const PDF_GENERATION_LABELS = [
  'Génération du PDF…',
  'Mise en page des schémas…',
  'Calcul du système…',
  'Finalisation du document…',
]

// XSAL16 — libellés FR des sections suivies sur la proposition web (miroir de
// `_ENGAGEMENT_SECTIONS` côté serveur, apps/ventes/public_views.py).
// source-choix: ventes.public_views._ENGAGEMENT_SECTIONS
const ENGAGEMENT_LABELS = {
  hero: 'accueil', prix: 'prix', etude: 'étude', garanties: 'garanties', signature: 'signature',
}

// Résume l'engagement par section en une phrase courte (« 2 min sur le prix,
// 30 s sur l'étude ») — null sans aucune section suivie (comportement QJ1
// inchangé, aucun badge affiché).
function engagementSummary(engagement) {
  const entries = Object.entries(engagement || {}).filter(([, v]) => v?.seconds > 0)
  if (entries.length === 0) return null
  entries.sort((a, b) => b[1].seconds - a[1].seconds)
  return entries.map(([section, v]) => {
    const label = ENGAGEMENT_LABELS[section] ?? section
    const mins = Math.round(v.seconds / 60)
    const duree = mins >= 1 ? `${mins} min` : `${v.seconds} s`
    return `${duree} sur ${label}`
  }).join(' · ')
}

// ── ARC49 — Ligne de la liste des devis (« lignes divisées »). Extraite VERBATIM
// du corps de `filteredDevis.map(...)` : mêmes `<tr>`, mêmes `data-label`, mêmes
// boutons d'action VISIBLES (états `loading` individuels), mêmes deux panneaux
// dépliables (versions / design 3D), mêmes appels API. Tout l'état et les
// handlers viennent du parent via `ctx` — aucune logique n'est déplacée ni
// modifiée. Le tableau reste `table.data-table` (contrat de test + carte mobile).
export default function DevisRow({ d, ctx }) {
  const {
    selectedIds, toggleSelected,
    versionsOpenId, roofOpenId, setRoofOpenId,
    // WIR225 - comparaison des variantes servie par le serveur.
    variantesEtat, basculerVersions,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    // WIR274 - composeur de note manuelle sur le panneau Historique.
    peutNoter, noteBrouillon, ecrireNote, publierNote, noteBusyId,
    suiviOpenId, toggleSuiviPartage,
    lectureClientCache, canSeeLectureClient,
    conceptionOpenId, setConceptionOpenId,
    etudeOpenId, setEtudeOpenId,
    navigate, dispatch,
    role, canDelete, canValiderVente, canSeePublicite, highlightId,
    deletingId, statutActionId, superieurBusyId, superieurStatus, shareBusyId, previewingId,
    pdfGenerating, pdfDownloading, pdfSlowPoll, convertingId, chantierBusy, factureGenId,
    openEdit, openVarianteModal, openGammeModal, handleDelete, handleEnvoyer, handleRelancer,
    handleContacterSuperieur,
    openEmailModal, handleCopierLienProposition, handleCopierApercuInterne, copierLienInterne, handlePreview, openPdfModal,
    handleTelechargerPdf, handlePartagerPdf, openAcceptModal, openRefusModal, handleConvertBC,
    handleProformaPdf, handleBonCommandePdf,
    handleChantier, handleGenererFacture,
  } = ctx
  // NTI18N12 — calendrier hégirien EN PLUS de la date grégorienne (jamais en
  // remplacement, jamais stocké) : uniquement quand locale=ar ET la
  // préférence utilisateur `calendrier_hegirien` est active.
  const { locale } = useI18n()
  const calendrierHegirien = useSelector((s) => s.auth.user?.calendrier_hegirien)
  const afficherHegirien = shouldShowHijri({ locale, calendrierHegirien })
  // Expiration calculée à la volée (T7) : un devis en attente dont la
  // date de validité est dépassée s'affiche « Expiré » sans changer
  // son statut stocké ni l'étape du lead.
  const effStatut = d.is_expired ? 'expire' : d.statut
  // VX141 — parcours DOCUMENT (règle #4) affiché par <DocumentStageTrack> à
  // côté du StatusPill : brouillon/envoyé sont pilotés par `d.statut` ; passé
  // l'acceptation, `d.statut` reste figé à 'accepte' (règle #4 — les statuts
  // Devis/BC/Facture sont préservés 1:1) donc la piste avance via la présence
  // du BC / d'une facture liée / d'un chantier, jamais via `d.statut` lui-même.
  // refuse/expire = statuts terminaux NÉGATIFS : la piste s'arrête au dernier
  // jalon positif (envoyé) sans jamais franchir « Accepté ».
  const docTrackCurrent = (d.statut === 'refuse' || d.statut === 'expire' || d.is_expired)
    ? 'envoye'
    : d.statut === 'brouillon' ? 'brouillon'
      : d.statut === 'envoye' ? 'envoye'
        : chantierEnCours(d.chantier) ? 'chantier'
          : (d.factures_liees?.length > 0) ? 'facture'
            : d.bon_commande_etat?.exists ? 'bc'
              : 'accepte'
  const docTrackBlocked = d.bon_commande_etat?.mismatch ? ['bc'] : []

  // APX17 — les signaux SECONDAIRES du statut, rassemblés au lieu d'être
  // empilés dans la cellule (hauteur de ligne stable + scroll juste au-delà
  // de ~100 devis). Aucun signal n'est perdu : ils sont tous dans le Popover
  // « Détails », et l'anomalie de BC reste visible sur la ligne elle-même.
  const statutDetails = [
    d.statut === 'accepte' && d.option_acceptee ? (
      <span className="text-success">
        Option : {d.option_acceptee === 'avec_batterie' ? 'Avec batterie' : 'Sans batterie'}
      </span>
    ) : null,
    /* QJ22 — « Proposition signée » : un DevisSignature (loi 53-05) existe. */
    d.est_signe ? (
      <span className="inline-flex items-center gap-1 font-medium text-success">
        <Check className="size-3" aria-hidden="true" />
        Proposition signée
        {d.signature_info?.signataire_nom ? ` — ${d.signature_info.signataire_nom}` : ''}
        {d.signature_info?.signed_at ? ` le ${formatDateTime(d.signature_info.signed_at)}` : ''}
      </span>
    ) : null,
    /* U8 — état du bon de commande lié (lecture seule, OneToOne existant). */
    d.bon_commande_etat?.exists ? (
      <span className="text-muted-foreground">BC : {d.bon_commande_etat.statut_display}</span>
    ) : null,
    d.bon_commande_etat?.mismatch ? (
      <span className="inline-flex items-start gap-1 font-medium text-warning">
        <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
        {d.bon_commande_etat.exists
          ? 'Devis accepté mais BC annulé'
          : 'Devis accepté sans bon de commande'}
      </span>
    ) : null,
    /* VX215 — boucle « pris en charge » après « Contacter mon supérieur ». */
    superieurStatus[d.id]?.requested ? (
      <span
        data-testid={`superieur-status-${d.id}`}
        className={`inline-flex items-center gap-1 font-medium ${
          superieurStatus[d.id].seen ? 'text-success' : 'text-muted-foreground'
        }`}
      >
        {superieurStatus[d.id].seen ? <Check className="size-3 shrink-0" aria-hidden="true" /> : null}
        {superieurStatus[d.id].seen
          ? `Pris en charge${superieurStatus[d.id].seen_by?.[0] ? ' par ' + superieurStatus[d.id].seen_by[0] : ''}`
          : 'Avis demandé — en attente'}
      </span>
    ) : null,
  ].filter(Boolean)

  const isGenerating = pdfGenerating[d.id]
  // VX132 — chargement long conscient : libellés honnêtes qui tournent
  // pendant la génération du PDF premium (jamais de fausse barre de progression).
  const pdfLabel = useRotatingLabel(PDF_GENERATION_LABELS, { active: !!isGenerating })
  const isDownloading = pdfDownloading[d.id]
  // QX21 — passé 30 s, on n'abandonne plus le suivi : ce badge reste visible
  // tant que le polling se poursuit (aucun second job n'est jamais relancé
  // en dessous).
  const isSlowPolling = !!pdfSlowPoll[d.id]
  return (
    <Fragment key={d.id}>
    {/* QX12 — deep-link ?devis=<pk> : la ligne ciblée porte un id ancrable et
        un surlignage temporaire (l'effet de page scrolle jusqu'à cet id). */}
    <tr id={`devis-row-${d.id}`}
        style={highlightId === d.id
          ? { outline: '2px solid var(--color-primary, #2563eb)', outlineOffset: '-2px' }
          : undefined}>
      <td>
        <Checkbox
          checked={selectedIds.includes(d.id)}
          onCheckedChange={() => toggleSelected(d.id)}
          aria-label={`Sélectionner ${d.reference}`}
        />
      </td>
      <td data-testid={`ref-cell-${d.id}`}>
        {/* VX140 — cellule Référence à 2 niveaux : ligne 1 = référence + badges
            de version en gras ; ligne 2 = métadonnées compactes (versions,
            consultation, engagement) séparées par « · », muted, text-xs ;
            chips de documents liés en dessous (rendues, pas title-only, pour
            ne pas casser les tests U5 qui vérifient leur texte visible). */}
        <div className="text-sm font-semibold">
          {d.reference}
          {d.version > 1 && (
            <Badge tone="primary" className="ml-1.5">v{d.version}</Badge>
          )}
          {/* U7 — une révision remplacée (is_active=False) porte un
              badge « Remplacé » explicite ; le lien ouvre l'historique
              des versions (qui pointe vers la version courante). */}
          {d.is_active === false && (
            <Badge tone="neutral" className="ml-1.5">Remplacé</Badge>
          )}
        </div>
        {/* WIR225 — `a_variantes` entre AUSSI dans la garde de la zone de
            métadonnées : sans lui, la racine d'un groupe de variantes n'avait
            même pas de 2e ligne, donc pas d'entrée « Voir les versions ». */}
        {(d.superseded_by_ref
          || d.version > 1 || d.version_parent_ref || d.a_variantes
          || d.deja_consulte || engagementSummary(d.engagement)) && (
          <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
            {d.superseded_by_ref && (
              <span className="text-warning">
                remplacé par{' '}
                <button
                  type="button"
                  className="font-medium underline hover:no-underline"
                  onClick={() => basculerVersions(d.id)}
                  title="Voir la version qui remplace ce devis"
                >
                  {d.superseded_by_ref}
                </button>
              </span>
            )}
            {d.superseded_by_ref
              && (d.version > 1 || d.version_parent_ref || d.deja_consulte
                || engagementSummary(d.engagement)) && <span aria-hidden="true">·</span>}
            {/* WIR225 — `a_variantes` (serveur) décrit le côté RACINE : les
                trois autres champs ne parlent que du côté ENFANT, si bien que
                la racine d'un groupe perdait son entrée « Voir les versions »
                au premier rechargement — la comparaison n'était atteignable
                que juste après la création. */}
            {(d.version > 1 || d.superseded_by_ref || d.version_parent_ref
              || d.a_variantes) && (
              <button
                type="button"
                className="text-primary hover:underline"
                onClick={() => basculerVersions(d.id)}
              >
                {versionsOpenId === d.id ? 'Masquer les versions' : 'Voir les versions'}
              </button>
            )}
            {(d.version > 1 || d.version_parent_ref)
              && (d.deja_consulte || engagementSummary(d.engagement)) && <span aria-hidden="true">·</span>}
            {/* QJ1 — Badge de consultation : affiché quand le lien public
                a été ouvert au moins une fois. Nombre de vues + date. */}
            {d.deja_consulte && (
              <span
                className="inline-flex items-center gap-1 font-medium text-primary"
                title={d.derniere_consultation
                  ? `Dernière ouverture : ${formatDateTime(d.derniere_consultation)}`
                  : 'Document consulté'}
              >
                <Eye className="size-3" aria-hidden="true" />
                Consulté ×{d.nombre_vues ?? 1}
              </span>
            )}
            {d.deja_consulte && engagementSummary(d.engagement) && <span aria-hidden="true">·</span>}
            {/* XSAL16 — résumé d'engagement par section de la proposition
                web (« a passé 2 min sur le prix, n'a pas ouvert l'étude »).
                Vide sans beacon (déjà serialisé, comportement QJ1 inchangé). */}
            {engagementSummary(d.engagement) && (
              <span title="Temps passé par section sur la proposition en ligne">
                {engagementSummary(d.engagement)}
              </span>
            )}
          </div>
        )}
        {/* U5 — Documents générés depuis ce devis : factures (chips
            cliquables → liste Factures) + bon de commande (→ BC).
            Lecture seule, données du serializer. */}
        {(d.factures_liees?.length > 0 || d.bon_commande_etat?.exists) && (
          <div
            className="mt-1 flex flex-wrap gap-1"
            title="Documents liés à ce devis"
          >
            {d.bon_commande_etat?.exists && (
              <button
                type="button"
                onClick={() => navigate('/ventes/bons-commande')}
                title={`Bon de commande ${d.bon_commande_etat.reference} — ${d.bon_commande_etat.statut_display}`}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2 py-0.5 text-xs font-medium hover:bg-muted"
              >
                <FileStack className="size-3" aria-hidden="true" />
                {d.bon_commande_etat.reference}
              </button>
            )}
            {(d.factures_liees ?? []).map(f => (
              <button
                key={f.id}
                type="button"
                onClick={() => navigate('/ventes/factures')}
                title={`Facture ${f.reference} — ${f.statut_display}`}
                className="inline-flex items-center gap-1 rounded-full border border-success/40 bg-success/10 px-2 py-0.5 text-xs font-medium text-success hover:bg-success/20"
              >
                <FileText className="size-3" aria-hidden="true" />
                {f.reference} · {f.statut_display}
              </button>
            ))}
          </div>
        )}
        {/* VX216(a) — rend le seam devis↔chantier VISIBLE côté vendeur (avant,
            seul InstallationDetail.jsx le détectait). Un chantier en cours a
            sa nomenclature (bom) GELÉE : éditer ce devis maintenant crée un
            écart que l'installateur découvrira seul sur le terrain. */}
        {chantierEnCours(d.chantier) && (
          <div
            className="mt-1 inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning"
            title="La nomenclature de ce chantier est gelée — éditer ce devis peut créer un écart devis↔chantier"
          >
            <AlertTriangle className="size-3" aria-hidden="true" />
            Chantier en cours (compo gelée)
          </div>
        )}
      </td>
      <td data-label="Client">
        {/* VX7 — calm color : le nom client est une donnée PRIMAIRE (contraste
            plein + poids medium), il ressort du chrome désaturé environnant. */}
        <span className="inline-flex items-center gap-1.5">
          <span className="font-medium text-foreground">{d.client_nom ?? '—'}</span>
        </span>
        {d.lead && (
          <div className="mt-1">
            <button
              type="button"
              title={[
                'Ouvrir le lead lié',
                d.lead_type_installation
                  ? `Type : ${d.lead_type_installation}` : null,
                d.lead_facture_hiver != null
                  ? `Facture hiver : ${formatMAD(d.lead_facture_hiver)}` : null,
              ].filter(Boolean).join('\n')}
              onClick={() => navigate(`/crm/leads?lead=${d.lead}`)}
              className="inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning hover:bg-warning/20"
            >
              ↗ {d.lead_nom ?? 'Lead'}
            </button>
            {/* PUB53 — traçabilité retour : ce devis vient (via son lead) d'une
                ad Meta → lien direct vers sa fiche « histoire complète »
                (PUB44). Gaté aux rôles qui voient /publicite. */}
            {d.lead_meta_ad_id && canSeePublicite && (
              <a
                href={`/publicite/ad/${encodeURIComponent(d.lead_meta_ad_id)}`}
                target="_blank"
                rel="noopener noreferrer"
                title="Ouvrir la fiche de l'annonce Meta à l'origine de ce lead"
                className="ml-1 inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary hover:bg-primary/20"
              >
                📣 Vient de la pub
              </a>
            )}
          </div>
        )}
      </td>
      {/* VX7 — calm color : les dates sont des métadonnées secondaires → mutées
          (le contraste plein est réservé au client, au total TTC et au statut). */}
      <td data-label="Créé le" className="text-muted-foreground">
        {afficherHegirien
          ? (formatWithHijri(d.date_creation) || new Date(d.date_creation).toLocaleDateString('fr-FR'))
          : new Date(d.date_creation).toLocaleDateString('fr-FR')}
      </td>
      <td className="m-hide text-muted-foreground">
        {d.date_validite
          ? new Date(d.date_validite).toLocaleDateString('fr-FR')
          : '—'}
      </td>
      <td className="ta-right tabular-nums" data-label="Total TTC">
        {/* PVAB (fondateur 20/08) — devis à deux options : les DEUX totaux,
            « sans / avec » batterie, jamais un montant qui n'existe dans aucun
            document. Repli : total_affiche (option 1), puis total stocké. */}
        {d.nb_options === 2
         && d.comparaison_options?.sans?.ttc != null
         && d.comparaison_options?.avec?.ttc != null
          ? (
            // QA-FIGURES — `data-figure` (clés : apps/ventes/quote_engine/
            // figures.py) : parité liste / PDF / page publique / API.
            <>
              <span data-figure="total_ttc" data-figure-option="sans">{formatMAD(d.comparaison_options.sans.ttc)}</span>
              {' / '}
              <span data-figure="total_ttc" data-figure-option="avec">{formatMAD(d.comparaison_options.avec.ttc)}</span>
            </>
          )
          : ((d.total_affiche ?? d.total_ttc) != null
              ? <span data-figure="total_affiche">{formatMAD(d.total_affiche ?? d.total_ttc)}</span>
              : '—')}
        {d.nb_options === 2 && (
          <Badge tone="warning" className="ml-1.5"
                 title="Devis à deux options — sans batterie / avec batterie, remise incluse">
            2 options
          </Badge>
        )}
        {d.solde && (
          <div className="mt-1 text-xs text-muted-foreground">
            Facturé {d.solde.facture} / Payé {d.solde.paye} / Restant {d.solde.restant} MAD
          </div>
        )}
      </td>
      {/* APX17 — la cellule Statut empilait jusqu'à SIX blocs (pastille,
          piste, option acceptée, proposition signée, état du BC, incohérence
          BC, boucle « pris en charge ») : la hauteur de ligne variait du
          simple au triple. Comme la liste tourne sur le moteur `ui/datatable`,
          qui ESTIME une hauteur constante au-delà de ~100 lignes, cette
          variabilité décalait aussi le scroll. La cellule est désormais
          PLAFONNÉE à StatusPill + piste documentaire ; tout le reste vit dans
          un Popover « Détails » — aucun CSS `<td>` artisanal, le contenu est
          simplement borné. */}
      <td data-label="Statut">
        <StatusPill status={effStatut} label={STATUT_DISPLAY[effStatut] ?? STATUT_DISPLAY.brouillon} />
        {/* VX141 — le StatusPill est un fait isolé ; la piste ci-dessous
            visualise la CHAÎNE complète (un devis accepté sans BC actif est
            maintenant signalé visuellement, pas seulement en texte L563+). */}
        <DocumentStageTrack
          className="mt-1"
          stages={DOC_STATUT_TRACK}
          current={docTrackCurrent}
          blocked={docTrackBlocked}
        />
        {statutDetails.length > 0 && (
          <Popover>
            <PopoverTrigger
              className="mt-1 inline-flex cursor-pointer items-center gap-1 rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground"
              aria-label={`Détails du statut — ${statutDetails.length} information(s)`}
            >
              Détails ({statutDetails.length})
              {/* L'anomalie ne se cache JAMAIS : elle reste signalée sur la
                  ligne, même repliée. */}
              {d.bon_commande_etat?.mismatch && (
                <AlertTriangle className="size-3 text-warning" aria-hidden="true" />
              )}
            </PopoverTrigger>
            <PopoverContent className="max-w-xs space-y-1.5 text-xs">
              {statutDetails.map((node, i) => <div key={i}>{node}</div>)}
            </PopoverContent>
          </Popover>
        )}
      </td>
      <td>
        <div className="flex flex-wrap items-center gap-2">
          {/* VX20 — « soupe d'actions » réduite : 2-3 actions primaires
              contextuelles restent des boutons directs (PDF, Envoyer/
              Accepter/Refuser selon statut, Générer facture) ; tout le reste
              (Éditer, Lien interne, Variante, Supprimer, Copier le lien,
              Design 3D, Aperçu, Télécharger, BC, Chantier, Créer projet, +
              l'ancien menu « Autres actions ») vit dans UN SEUL menu « ⋯ ».
              Anatomie de rangée Linear/Attio — actions révélées, jamais
              empilées. Hauteur de ligne stable, aucun bouton perdu. */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => openPdfModal(d)}
            loading={isGenerating}
            title="Générer le PDF (choix du format)"
          >
            <FileText /> {isGenerating ? pdfLabel : 'PDF'}
          </Button>
          {/* QX21 — passé 30 s, on n'abandonne plus le suivi : ce badge reste
              visible tant que le polling se poursuit (aucun second job
              n'est jamais relancé en dessous). */}
          {isSlowPolling && (
            <Badge tone="warning" title="Le PDF est toujours en cours de génération côté serveur — la page continue de vérifier automatiquement.">
              PDF toujours en cours…
            </Badge>
          )}

          {d.statut === 'brouillon' && (
            <Button
              size="sm"
              variant="outline"
              loading={statutActionId === d.id}
              onClick={() => handleEnvoyer(d)}
              title="Envoyer par WhatsApp (message + lien de proposition) — le devis passe « Envoyé » quand vous ouvrez WhatsApp"
            >
              <Send /> Envoyer
            </Button>
          )}
          {/* VX222 — « Relancer » : pendant devis de la relance facture. Rouvre
              le flux WhatsApp EXISTANT en mode rappel (aperçu-puis-clic, jamais
              d'envoi auto) + consigne la relance au chatter. N'apparaît que sur
              un devis « Envoyé ». */}
          {d.statut === 'envoye' && (
            <Button
              size="sm"
              variant="outline"
              loading={statutActionId === d.id}
              onClick={() => handleRelancer(d)}
              title="Relancer ce devis par WhatsApp (message de rappel + note au chatter)"
            >
              <Bell /> Relancer
            </Button>
          )}
          {d.statut === 'envoye' && canValiderVente && (
            <Button
              size="sm"
              title="Marquer accepté (date + nom + option) — déclenche la création du chantier"
              onClick={() => openAcceptModal(d)}
            >
              <Check /> Accepter
            </Button>
          )}
          {d.statut === 'envoye' && canValiderVente && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => openRefusModal(d)}
              className="border-destructive/40 text-destructive hover:bg-destructive/10"
              title="Marquer ce devis comme refusé (motif obligatoire)"
            >
              <X /> Refuser
            </Button>
          )}

          {/* « Générer facture » TOUJOURS visible, pour montrer que
              c'est ici qu'un devis devient des factures. Désactivé
              tant que le devis n'est pas « Accepté », avec un indice
              VISIBLE (pas seulement au survol → lisible sur mobile). */}
          {d.statut !== 'accepte' ? (
            <div className="flex flex-col gap-0.5">
              <Button size="sm" variant="outline" disabled>
                Générer facture
              </Button>
              <span className="max-w-[190px] text-xs leading-tight text-muted-foreground">
                Passez le devis en « Accepté » pour générer les factures.
              </span>
            </div>
          ) : d.solde && d.solde.tranches_facturees >= d.solde.tranches_total ? (
            <Button size="sm" variant="outline" disabled
                    title="Toutes les tranches ont été facturées">
              Échéancier complet
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => handleGenererFacture(d)}
              loading={factureGenId === d.id}
              title="Générer la prochaine tranche de facture"
            >
              Générer facture
            </Button>
          )}

          {/* VX20 — menu « Plus » unique : regroupe TOUTES les actions
              secondaires (précédemment jusqu'à 10 boutons par ligne). */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="ghost" aria-label={`Plus d'actions — ${d.reference}`}>
                <MoreHorizontal className="size-4" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Plus d'actions</DropdownMenuLabel>
              <DropdownMenuItem
                disabled={!peutEditerDevis(d)}
                onSelect={() => openEdit(d)}
              >
                Éditer
              </DropdownMenuItem>
              {/* VX79 — « Copier le lien interne » : URL de l'ERP partageable
                  (/ventes/devis?devis=<pk>) à envoyer à un collègue. Distinct
                  du lien PUBLIC de proposition (règle #4) plus bas — celui-ci
                  ouvre le devis DANS l'ERP, toujours disponible quel que soit
                  le statut. */}
              <DropdownMenuItem onSelect={() => copierLienInterne(d)}>
                <Link2 className="size-3.5" aria-hidden="true" />
                Lien interne
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={previewingId === d.id}
                onSelect={() => handlePreview(d)}
              >
                <Eye className="size-3.5" aria-hidden="true" />
                {previewingId === d.id ? 'Aperçu du PDF…' : 'Aperçu du PDF'}
              </DropdownMenuItem>
              {d.fichier_pdf && (
                <DropdownMenuItem
                  disabled={isDownloading}
                  onSelect={() => handleTelechargerPdf(d)}
                >
                  <FileDown className="size-3.5" aria-hidden="true" />
                  {isDownloading ? 'Téléchargement…' : 'Télécharger le dernier PDF'}
                </DropdownMenuItem>
              )}
              {/* VX44 — partage natif du PDF (feuille de partage iOS/Android →
                  WhatsApp/e-mail), repli téléchargement. */}
              {d.fichier_pdf && (
                <DropdownMenuItem
                  disabled={isDownloading}
                  onSelect={() => handlePartagerPdf(d)}
                >
                  <Share2 className="size-3.5" aria-hidden="true" />
                  Partager le PDF
                </DropdownMenuItem>
              )}
              {/* WR2/QJR531 — Copier le lien de proposition (share_link) :
                  copier le lien CLIENT vaut envoi (D-QJR5-3). */}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem
                  disabled={shareBusyId === d.id}
                  onSelect={() => handleCopierLienProposition(d)}
                >
                  <Link2 className="size-3.5" aria-hidden="true" />
                  Copier le lien de la proposition{shareBusyId === d.id ? '…' : ''}
                </DropdownMenuItem>
              )}
              {/* L-INTPREV/QJ1bis — même page, jeton INTERNE : vérifier la
                  proposition sans déclencher la notification d'ouverture
                  ni aucune trace. Jamais à envoyer au client. */}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem
                  disabled={shareBusyId === d.id}
                  onSelect={() => handleCopierApercuInterne(d)}
                >
                  <Link2 className="size-3.5" aria-hidden="true" />
                  Copier l&rsquo;aperçu interne (sans notification){shareBusyId === d.id ? '…' : ''}
                </DropdownMenuItem>
              )}
              {/* QG10/QJ15 — « Variante » : ouvre une modale pour
                  confirmer/éditer le pourcentage (défaut = config société),
                  créer les 3 variantes puis router vers la comparaison
                  côte-à-côte. */}
              {d.statut === 'brouillon' && (
                <DropdownMenuItem onSelect={() => openVarianteModal(d)}>
                  <Copy className="size-3.5" aria-hidden="true" />
                  Variante
                </DropdownMenuItem>
              )}
              {/* GAMMES — « Créer une variante de gamme » : crée le devis
                  FRÈRE d'une seconde gamme (composition et prix propres, à
                  retoucher ensuite). Le libellé est libre — aucune marque
                  codée en dur ; défauts proposés : Essentielle / Premium. */}
              {d.statut === 'brouillon' && (
                <DropdownMenuItem onSelect={() => openGammeModal(d)}>
                  <Copy className="size-3.5" aria-hidden="true" />
                  Créer une variante de gamme
                </DropdownMenuItem>
              )}
              {/* PV23 — porte d'entrée du CALEPINAGE depuis la liste. Un devis
                  encore ouvert (brouillon / envoyé) se CONÇOIT — l'écran de
                  conception resynchronise ses lignes (PV21). Un devis figé ne
                  se conçoit plus : il se CONSULTE, et seulement s'il porte
                  réellement un plan (`roof_layout`, exposé par le serializer —
                  aucun champ backend ajouté pour cette entrée). */}
              {(effStatut === 'brouillon' || effStatut === 'envoye') && (
                <DropdownMenuItem
                  onSelect={() => navigate(`/ventes/devis/${d.id}/design`)}
                  aria-label={`Concevoir la toiture 3D de ${d.reference}`}
                >
                  <Box className="size-3.5" aria-hidden="true" />
                  Concevoir en 3D
                </DropdownMenuItem>
              )}
              {effStatut !== 'brouillon' && effStatut !== 'envoye' && d.roof_layout && (
                <DropdownMenuItem
                  onSelect={() => navigate(`/ventes/devis/${d.id}/3d`)}
                  aria-label={`Voir le design 3D de ${d.reference}`}
                >
                  <Box className="size-3.5" aria-hidden="true" />
                  Voir le design 3D
                </DropdownMenuItem>
              )}
              {/* QG11/QG12 — « Voir le design 3D » : ouvre le plan de toiture
                  (roof_layout) en lecture seule dans le détail, ou dans une
                  fenêtre séparée. N'apparaît que si un plan existe. */}
              {d.roof_layout && (
                <DropdownMenuItem onSelect={() => setRoofOpenId(
                  roofOpenId === d.id ? null : d.id)}>
                  <Box className="size-3.5" aria-hidden="true" />
                  Design 3D
                </DropdownMenuItem>
              )}
              {d.roof_layout && (
                <DropdownMenuItem
                  onSelect={() => window.open(`/ventes/devis/${d.id}/3d`, '_blank', 'noopener')}
                  aria-label={`Ouvrir le design 3D de ${d.reference} dans une fenêtre`}
                >
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                  Design 3D — nouvelle fenêtre
                </DropdownMenuItem>
              )}
              {d.statut === 'accepte' && (
                <DropdownMenuItem
                  disabled={convertingId === d.id}
                  onSelect={() => handleConvertBC(d)}
                >
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                  Convertir en bon de commande
                </DropdownMenuItem>
              )}
              {d.statut === 'accepte' && (
                <DropdownMenuItem
                  disabled={chantierBusy === d.id}
                  onSelect={() => handleChantier(d)}
                >
                  <HardHat className="size-3.5" aria-hidden="true" />
                  {d.chantier ? `Voir le chantier ${d.chantier.reference}` : 'Créer le chantier'}
                </DropdownMenuItem>
              )}
              {/* VX97 — journal des changements (qui/quand/ancien→nouveau),
                  section repliable ; distinct de la chaîne de versions. */}
              <DropdownMenuItem onSelect={() => toggleHistorique(d.id)}>
                {histoOpenId === d.id ? "Masquer l'historique" : "Historique des modifications"}
              </DropdownMenuItem>
              {/* WIR103/XFAC10 — proforma PDF (aucun impact comptable). */}
              <DropdownMenuItem onSelect={() => handleProformaPdf(d)}>
                Proforma (PDF)
              </DropdownMenuItem>
              {/* ZSAL8 — PDF du bon de commande lié (client `getBonCommandePdf`
                  déjà présent dans ventesApi.js, jamais appelé). Endpoint BC
                  distinct, ne touche pas au rendu /proposal du devis (règle #4). */}
              {d.bon_commande_etat?.exists && (
                <DropdownMenuItem onSelect={() => handleBonCommandePdf(d)}>
                  Bon de commande (PDF)
                </DropdownMenuItem>
              )}
              {/* ANALYT1 — lecture par le client (visites par section de la
                  proposition web + alerte de friction). */}
              <DropdownMenuItem onSelect={() => toggleSuiviPartage(d.id)}>
                {suiviOpenId === d.id ? 'Masquer la lecture par le client' : 'Lecture par le client'}
              </DropdownMenuItem>
              {/* PV43 — étude électrique agrégée (chaînes/conformité/schéma
                  unifilaire/surcharges DC-AC-phases), calculée depuis les
                  lignes + le calepinage du devis. */}
              <DropdownMenuItem onSelect={() => setConceptionOpenId(
                conceptionOpenId === d.id ? null : d.id)}>
                {conceptionOpenId === d.id
                  ? 'Masquer la conception électrique' : 'Conception électrique'}
              </DropdownMenuItem>
              {/* PV76 — carte « Étude bancable » (P50/P90/PR/cascade des
                  pertes/payback/VAN/TRI), lecture de `etude_params.simulation`. */}
              <DropdownMenuItem onSelect={() => setEtudeOpenId(
                etudeOpenId === d.id ? null : d.id)}>
                {etudeOpenId === d.id ? "Masquer l'étude bancable" : 'Étude bancable'}
              </DropdownMenuItem>
              {/* QX27 — actions historiquement dans « Autres actions » :
                  Réviser, Approuver remise, Contacter mon supérieur, Email. */}
              {d.is_active && d.statut !== 'brouillon' && (
                <DropdownMenuItem onSelect={() => {
                  // QJR533 — UN seul geste (features/ventes/reviserDevis) :
                  // avertit si chantier en cours (VX216(a)), dit le résultat,
                  // ouvre la V2 en Édition complète.
                  reviserEtOuvrir({
                    devis: d, navigate, onApres: () => dispatch(fetchDevis()),
                  })
                }}>
                  Réviser (nouvelle version)
                </DropdownMenuItem>
              )}
              {role === 'admin' && d.statut === 'brouillon'
                && parseFloat(d.remise_globale) > 0 && !d.remise_approuvee && (
                <DropdownMenuItem onSelect={() => {
                  ventesApi.approuverRemise(d.id)
                    .then(() => dispatch(fetchDevis())).catch(() => {})
                }}>
                  Approuver la remise
                </DropdownMenuItem>
              )}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem
                  disabled={superieurBusyId === d.id}
                  onSelect={() => handleContacterSuperieur(d)}
                >
                  Contacter mon supérieur
                </DropdownMenuItem>
              )}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem onSelect={() => openEmailModal(d)}>
                  Envoyer par email
                </DropdownMenuItem>
              )}
              {/* QJR639/QJR661 — seul un brouillon se supprime ; tout autre
                  statut s'archive (409 serveur « archivez-le »). */}
              {canDelete && d.statut === 'brouillon' && (
                <DropdownMenuItem
                  destructive
                  disabled={deletingId === d.id}
                  onSelect={(e) => { e.preventDefault(); handleDelete(d) }}
                >
                  Supprimer
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </td>
    </tr>
    {versionsOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          {/* WIR225 — comparaison des variantes, servie par le SERVEUR
              (`getVariantes`) : la chaîne reconstruite localement ignorait
              toute variante absente de la page courante. */}
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Comparaison des variantes
            </p>
            {variantesEtat.loading ? (
              <p className="text-xs text-muted-foreground">Chargement…</p>
            ) : variantesEtat.error ? (
              <p className="text-xs text-muted-foreground">
                Comparaison indisponible pour le moment.
              </p>
            ) : variantesEtat.rows.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Ce devis n’appartient à aucun groupe de variantes.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm"
                       aria-label={`Comparaison des variantes de ${d.reference}`}>
                  <thead>
                    <tr className="border-b border-border">
                      <th scope="col" className="px-2 py-1 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">Référence</th>
                      <th scope="col" className="px-2 py-1 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">Libellé</th>
                      <th scope="col" className="px-2 py-1 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total HT</th>
                      <th scope="col" className="px-2 py-1 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total TTC</th>
                    </tr>
                  </thead>
                  <tbody>
                    {variantesEtat.rows.map(v => (
                      <tr key={v.id}
                          data-source={v.id === d.id ? 'true' : undefined}
                          className="border-b border-border/60 last:border-b-0">
                        <td className="px-2 py-1">
                          <strong>{v.reference}</strong>
                          {v.id === d.id && (
                            <span className="ml-2 text-xs text-primary">(source)</span>
                          )}
                        </td>
                        <td className="px-2 py-1 text-muted-foreground">
                          {/* Aucun libellé n'est INVENTÉ : le nom de gamme s'il
                              existe, sinon le rang de version servi par le
                              serveur. */}
                          {v.etude_params?.gamme?.nom || `v${v.version || 1}`}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {v.total_ht != null ? formatMAD(v.total_ht) : '—'}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {(v.total_affiche ?? v.total_ttc) != null
                            ? formatMAD(v.total_affiche ?? v.total_ttc)
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </td>
      </tr>
    )}
    {/* VX97 — Panneau « Historique » : journal des changements du devis
        (DevisActivity). Qui / quand / ancien→nouveau. `prix_achat` jamais
        rendu (le journal ne le porte pas). */}
    {histoOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Historique des modifications — {d.reference}
            </p>
            {histoLoadingId === d.id ? (
              <p className="text-xs text-muted-foreground">Chargement…</p>
            ) : (histoCache[d.id]?.length ?? 0) === 0 ? (
              <p className="text-xs text-muted-foreground">
                Aucune modification consignée.
              </p>
            ) : (
              <ul className="space-y-1 text-sm">
                {histoCache[d.id].map(a => (
                  <li key={a.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="text-xs text-muted-foreground">
                      {a.created_at ? formatDateTime(a.created_at) : '—'}
                      {a.user_nom ? ` · ${a.user_nom}` : ''}
                    </span>
                    <span>
                      {a.body
                        ? a.body
                        : (
                          <>
                            <strong>{a.field_label || a.field}</strong>
                            {' : '}
                            <span className="text-muted-foreground">{a.old_value || '—'}</span>
                            {' → '}
                            <span>{a.new_value || '—'}</span>
                          </>
                        )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {/* ── WIR274 — Composeur de note manuelle ──────────────────────
                `noterDevis` n'était appelé que par l'auto-note de relance
                WhatsApp (VX222, intacte) : personne ne pouvait écrire une
                note à la main. Le fil est RECHARGÉ DU SERVEUR après l'envoi —
                jamais un ajout optimiste local. */}
            {peutNoter && (
              <div className="mt-2 flex flex-col gap-1.5">
                <label htmlFor={`note-devis-${d.id}`} className="sr-only">
                  Ajouter une note — {d.reference}
                </label>
                <Textarea
                  id={`note-devis-${d.id}`}
                  rows={2}
                  placeholder="Ajouter une note au fil du devis…"
                  value={noteBrouillon[d.id] ?? ''}
                  onChange={(e) => ecrireNote(d.id, e.target.value)}
                />
                <div className="flex justify-end">
                  <Button
                    type="button" size="sm"
                    loading={noteBusyId === d.id}
                    disabled={!(noteBrouillon[d.id] || '').trim()}
                    onClick={() => publierNote(d.id)}
                  >
                    Ajouter la note
                  </Button>
                </div>
              </div>
            )}
          </div>
        </td>
      </tr>
    )}
    {/* ANALYT1 — Panneau « Lecture par le client » (visites par section de
        la proposition web + alerte de friction). */}
    {suiviOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Lecture par le client — {d.reference}
            </p>
            <DevisSuiviPartagePanel
              lectureClient={canSeeLectureClient ? lectureClientCache[d.id] : undefined}
            />
          </div>
        </td>
      </tr>
    )}
    {/* QG11 — Panneau « Voir le design 3D » : rendu LECTURE
        SEULE du plan de toiture stocké (roof_layout). */}
    {roofOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-muted-foreground">
                Design 3D de la toiture — {d.reference}
              </p>
              <div className="flex items-center gap-2">
                {/* PV23 — depuis l'aperçu, reprendre le calepinage (devis
                    encore ouvert seulement : au-delà, le document est figé). */}
                {(effStatut === 'brouillon' || effStatut === 'envoye') && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate(`/ventes/devis/${d.id}/design`)}
                    title="Reprendre le calepinage de cette toiture"
                  >
                    Concevoir en 3D
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => window.open(`/ventes/devis/${d.id}/3d`, '_blank', 'noopener')}
                  title="Ouvrir dans une nouvelle fenêtre"
                >
                  <ExternalLink className="size-3.5 mr-1" aria-hidden="true" />
                  Ouvrir dans une fenêtre
                </Button>
              </div>
            </div>
            <div className="max-w-2xl">
              <RoofViewer
                layout={d.roof_layout}
                clientNom={d.client_nom}
                leadNom={d.lead_nom}
                lignes={d.lignes}
              />
            </div>
          </div>
        </td>
      </tr>
    )}
    {/* PV43 — Panneau « Conception électrique » : chaînes par MPPT,
        conformité, aperçu du schéma unifilaire, surcharges DC/AC/phases. */}
    {conceptionOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Conception électrique — {d.reference}
            </p>
            <ConceptionElectrique devisId={d.id} />
          </div>
        </td>
      </tr>
    )}
    {/* PV76 — Carte « Étude bancable » : lecture de
        `etude_params.simulation`, recalcul asynchrone (PV74). */}
    {etudeOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Étude bancable — {d.reference}
            </p>
            <EtudeBancable devis={d} onRefresh={() => dispatch(fetchDevis())} />
          </div>
        </td>
      </tr>
    )}
    </Fragment>
  )
}
