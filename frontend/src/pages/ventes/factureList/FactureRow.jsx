// SPL211 — ligne de la liste des factures : DÉPLACEMENT VERBATIM depuis
// FactureList.jsx (move only, aucun changement de comportement). Les aides
// partagées avec l'écran vivent dans ./factureHelpers.js.
import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Download, FileWarning, MessageCircle, Code2, Check, FileText, ReceiptText, MoreHorizontal, CreditCard, ShieldCheck, Zap, Eye } from 'lucide-react'
import { Button, Badge, StatusPill, Input, Checkbox, DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, Popover, PopoverTrigger, PopoverContent, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, FormActions } from '../../../ui'
import { formatMAD, toNumber, normalizePhoneE164, formatDateTime } from '../../../lib/format'
import DocumentStageTrack from '../../../ui/DocumentStageTrack'
import { DOC_STATUT_TRACK, factureTrack } from '../../../features/ventes/documentChain'
import { useRotatingLabel } from '../../../hooks/useRotatingLabel'
import { isOverdue, isPartiallyPaid } from './factureHelpers.js'

// VX132 — chargement long conscient (voir DevisList.jsx PDF_GENERATION_LABELS) :
// libellés honnêtes côté client uniquement — le PDF facture reste le moteur
// legacy INTOUCHÉ (règle #4). Sans effet visible si la génération est brève
// (le libellé ne tourne qu'après ~2.5 s d'attente réelle).
const FACTURE_PDF_GENERATION_LABELS = [
  'Génération du PDF…',
  'Mise en forme de la facture…',
  'Finalisation du document…',
]

const STATUT_DISPLAY = {
  brouillon: 'Brouillon',
  emise:     'Émise',
  payee:     'Payée',
  en_retard: 'En retard',
  annulee:   'Annulée',
}

// N39 — statut de télédéclaration DGI (purement informatif, lecture seule).
const TELEDECLARATION_DISPLAY = {
  non_soumise: 'DGI : Non soumise',
  soumise:     'DGI : Soumise',
  validee:     'DGI : Validée',
}
const TELEDECLARATION_TONE = {
  non_soumise: 'neutral',
  soumise:     'info',
  validee:     'success',
}

// Prochaine action contextuelle (next-best-action) : clé de l'action mise en
// avant selon statut/montant dû/retard. Une brouillon → Émettre ; une émise en
// retard → Relancer ; une émise partiellement payée → Encaisser ; sinon null.
function nextBestAction(f) {
  if (f.statut === 'brouillon') return 'emettre'
  if (f.statut === 'annulee' || f.statut === 'payee') return null
  // AFAC10 — « Encaisser » n'est jamais recommandé sur une facture que le serveur
  // déclare non encaissable (champ `encaissable`, porte unique AFAC9).
  if (f.encaissable === false) return null
  if (isOverdue(f)) return 'relancer'
  if (toNumber(f.montant_paye) > 0 && toNumber(f.montant_du) > 0) return 'encaisser'
  return null
}

// ── ARC53 — Ligne de la liste des factures (« lignes divisées »). Extraite
// VERBATIM du corps de `filtered.map(...)` : même <tr> (classe échue conservée),
// mêmes boutons d'action VISIBLES + états loading individuels, même menu
// « Actions » (DropdownMenu queryable), même édition inline d'échéance, mêmes
// badges (DGI/mentions/next-best-action), mêmes appels API. Le PDF facture reste
// legacy et INTOUCHÉ (règle #4). Tout l'état/handlers viennent du parent via `ctx`.
export default function FactureRow({ f, ctx }) {
  const {
    selectedIds, toggleSelect,
    echeanceEditId, echeanceValue, setEcheanceValue, echeanceSaving,
    saveEcheance, setEcheanceEditId, startEditEcheance,
    dgiActif, isAdmin,
    actionId, pdfGenerating, pdfDownloading, waBusy, payLinkBusy, dgiBusy,
    openEdit, doAction, emettreFacture, annulerFacture,
    openPayModal, handleLienPaiement, handleTelechargerPdf, handleGenererPdf,
    openAvoirModal, handleWhatsApp, handleUbl, handleDgiExport, handleDgiConformite,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    openNoteDebit,
    // PACT121 - ouvre la demande de paiement carte (prestataire).
    openPaiementEnLigne,
    // APX14 - ouvre l'apercu PDF inline de cette facture.
    openPreview,
    // EZ13 - marquage sec, relegue au menu et explique.
    openMarquerPayee,
    highlightFactureId,
    // WIR183 - les quatre actions de fiche, jusqu'ici sans point d'entree.
    canManage, wir183Busy,
    handleRemettreBrouillon, handleFacturerPenalites,
    openAbandonSolde, openRetourClient,
  } = ctx
  // AFAC13 - annulation avec directive d'argent (dialogue).
  const { demanderAnnulation } = ctx
  const overdue = isOverdue(f)
  const statutKey = overdue && f.statut === 'emise' ? 'en_retard' : f.statut
  const busy = actionId === f.id
  const isGenerating = pdfGenerating[f.id]
  const isDownloading = pdfDownloading[f.id]
  // VX132 — chargement long conscient : libellés honnêtes qui tournent
  // pendant la génération du PDF (jamais de fausse barre de progression).
  const pdfLabel = useRotatingLabel(FACTURE_PDF_GENERATION_LABELS, { active: !!isGenerating })
  const isWaBusy = waBusy[f.id]
  // L853 — téléphone client normalisable (miroir backend).
  const waPhoneOk = !!normalizePhoneE164(f.client_telephone)
  const nba = nextBestAction(f)
  const isPayLinkBusy = payLinkBusy[f.id]
  const isDgiBusy = dgiBusy[f.id]

  const isHighlighted = String(f.id) === String(highlightFactureId)
  return (
    <Fragment key={f.id}>
    {/* VX231(a) — id d'ancrage + surbrillance temporaire pour le deep-link
        ?facture=<id> (scroll + ring depuis PaiementsPage). */}
    <tr id={`facture-row-${f.id}`}
        className={[
          overdue ? 'bg-destructive/5' : '',
          isHighlighted ? 'ring-2 ring-inset ring-primary bg-primary/5' : '',
        ].filter(Boolean).join(' ') || undefined}>
      <td>
        <Checkbox
          checked={selectedIds.includes(f.id)}
          onCheckedChange={() => toggleSelect(f.id)}
          aria-label={`Sélectionner la facture ${f.reference}`}
        />
      </td>
      <td>
        <strong>{f.reference}</strong>
        {(f.type_facture_display || toNumber(f.pourcentage) > 0) && (
          <div className="mt-0.5 text-xs text-muted-foreground">
            {f.type_facture_display}
            {toNumber(f.pourcentage) > 0
              ? ` ${Math.round(toNumber(f.pourcentage))} %` : ''}
          </div>
        )}
        {/* APX13 — l'AMONT du document, cliquable. Le lien pointait sur
            `?ref=` — un paramètre que DevisList ne lit PAS (vérifié) : il
            atterrissait sur la liste nue. Il pointe désormais sur `?devis=<id>`
            (QX12), que la liste lit déjà pour surligner + scroller jusqu'au
            devis d'origine. */}
        {f.devis_reference && f.devis && (
          <div className="mt-0.5 text-xs">
            <Link to={`/ventes/devis?devis=${encodeURIComponent(f.devis)}`}
                  className="text-primary hover:underline">
              Devis {f.devis_reference}
            </Link>
          </div>
        )}
        {/* VX52 — la liste des mentions manquantes (Art. 145) ne vivait que
            dans l'attribut `title` (survol souris) — illisible au tactile.
            Elle devient un Popover tapable qui révèle la liste au clic/tap. */}
        {Array.isArray(f.mentions_manquantes) && f.mentions_manquantes.length > 0 && (
          <Popover>
            <PopoverTrigger
              className="mt-1 inline-flex cursor-pointer items-center gap-1 rounded-md bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning"
              aria-label={`Mentions légales manquantes (Art. 145) : ${f.mentions_manquantes.join(', ')}`}
            >
              <FileWarning className="size-3" aria-hidden="true" />
              {f.mentions_manquantes.length} mention(s) manquante(s)
            </PopoverTrigger>
            <PopoverContent className="max-w-xs text-xs">
              <p className="mb-1 font-medium">Mentions légales manquantes (Art. 145)</p>
              <ul className="list-disc pl-4 text-muted-foreground">
                {f.mentions_manquantes.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </PopoverContent>
          </Popover>
        )}
        {/* VX97 — journal des changements (qui/quand/ancien→nouveau), repliable. */}
        <div className="mt-0.5">
          <button
            type="button"
            className="text-xs text-primary hover:underline"
            onClick={() => toggleHistorique(f.id)}
          >
            {histoOpenId === f.id ? "Masquer l'historique" : 'Historique'}
          </button>
        </div>
      </td>
      {/* VX7 — calm color : nom client = donnée primaire (contraste plein +
          poids medium) ; date d'émission = métadonnée secondaire (mutée). */}
      <td data-label="Client"><span className="font-medium text-foreground">{f.client_nom ?? '—'}</span></td>
      <td data-label="Émission" className="text-muted-foreground">{new Date(f.date_emission).toLocaleDateString('fr-FR')}</td>
      <td data-label="Échéance">
        {echeanceEditId === f.id ? (
          <span className="flex items-center gap-1">
            <Input type="date" className="w-36" value={echeanceValue}
                   onChange={e => setEcheanceValue(e.target.value)} />
            <Button size="sm" loading={echeanceSaving} onClick={() => saveEcheance(f)}>OK</Button>
            <Button size="sm" variant="ghost" onClick={() => setEcheanceEditId(null)}>×</Button>
          </span>
        ) : (
          <>
          {/* VX52 — l'affordance de modification d'échéance ne vivait que dans
              `title` (survol) : au tactile, un vrai bouton à label accessible. */}
          {['emise', 'en_retard'].includes(f.statut) || overdue ? (
            <button
              type="button"
              className={`${overdue ? 'font-semibold text-destructive' : ''} cursor-pointer text-left hover:underline`}
              aria-label={`Modifier l’échéance de la facture ${f.reference}`}
              onClick={() => startEditEcheance(f)}
            >
              {f.date_echeance
                ? new Date(f.date_echeance).toLocaleDateString('fr-FR')
                : 'Définir une échéance'}
            </button>
          ) : (
            <span>
              {f.date_echeance
                ? new Date(f.date_echeance).toLocaleDateString('fr-FR')
                : '—'}
            </span>
          )}
          </>
        )}
      </td>
      <td className="ta-right tabular-nums" data-label="Total TTC">
        {f.total_ttc != null ? formatMAD(f.total_ttc) : '—'}
        {(f.montant_paye != null || f.montant_du != null) && (
          <div className="mt-0.5 text-xs text-muted-foreground">
            Payé {formatMAD(f.montant_paye)} / Dû {formatMAD(f.montant_du)}
          </div>
        )}
        {/* VX250(a) — PendingStepsIndicator : lecture PURE de statuts déjà
            chargés (`isPartiallyPaid`, déjà utilisé par l'onglet « Partielle »
            ci-dessus) — ne change JAMAIS un statut, ZÉRO appel réseau. Plus
            visible que la ligne « Payé/Dû » neutre au-dessus : seul un acompte
            RÉELLEMENT partiel (reste dû > 0, pas annulée) l'affiche. */}
        {isPartiallyPaid(f) && (
          <div role="status" className="mt-0.5 text-xs font-medium text-warning">
            Solde restant : {formatMAD(f.montant_du)}
          </div>
        )}
      </td>
      <td data-label="Statut">
        <StatusPill status={statutKey} label={STATUT_DISPLAY[statutKey] ?? STATUT_DISPLAY.brouillon} />
        {/* APX13 — la chaîne devis→BC→facture, visible à CETTE étape aussi
            (le stepper VX141 n'existait que sur la liste des devis : il
            disparaissait aux deux étapes suivantes du parcours). */}
        <DocumentStageTrack
          className="mt-1"
          stages={DOC_STATUT_TRACK}
          {...factureTrack(f)}
        />
        {/* VX52 — le sens « télédéclaration DGI » ne vivait que dans `title`
            (survol) : sur mobile, un préfixe explicite le rend lisible. */}
        {['emise', 'payee', 'en_retard'].includes(f.statut) && f.statut_teledeclaration && (
          <Badge
            tone={TELEDECLARATION_TONE[f.statut_teledeclaration] ?? 'neutral'}
            className="mt-1 block w-fit"
            aria-label={`Télédéclaration DGI (informatif) : ${TELEDECLARATION_DISPLAY[f.statut_teledeclaration] ?? f.statut_teledeclaration}`}
          >
            Télédéclaration : {TELEDECLARATION_DISPLAY[f.statut_teledeclaration] ?? f.statut_teledeclaration}
          </Badge>
        )}
        {/* WR2b — badge conformité DGI, visible seulement si l'interrupteur société est actif. */}
        {dgiActif && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
          <Badge
            tone="info"
            className="mt-1 block w-fit cursor-pointer"
            title="Vérifier la conformité DGI (aucune transmission)"
            onClick={() => handleDgiConformite(f)}
          >
            <ShieldCheck className="size-3" /> Conformité DGI
          </Badge>
        )}
      </td>
      <td>
        {/* VX52 — « Facture échue » ne vivait que dans `title` (survol) : le
            texte devient explicite dans la carte (lisible au tactile). */}
        {nba === 'relancer' && (
          <Badge tone="warning" className="mb-1 block w-fit"
                 aria-label="Facture échue — à relancer dans Relances / Impayés">
            Facture échue — à relancer
          </Badge>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {/* VX142(b) — l'action recommandée (nextBestAction) occupe TOUJOURS
              le PREMIER slot de la rangée, icône + halo tokenisé (variant
              "default"), ordre stable — plus de position mouvante selon les
              autres boutons présents/absents. Rendue ici UNE seule fois ;
              retirée de sa position historique plus bas pour ne jamais
              apparaître deux fois. */}
          {nba === 'emettre' && (
            <Button size="sm" variant="default" loading={busy}
                    onClick={() => doAction(emettreFacture, f.id)}
                    title={f.motif_non_encaissable || 'Action recommandée'}>
              <Zap className="size-3.5" aria-hidden="true" /> Émettre
            </Button>
          )}
          {nba === 'encaisser' && (
            <Button size="sm" variant="default"
                    onClick={() => openPayModal(f)} title="Action recommandée — enregistrer un paiement">
              <Zap className="size-3.5" aria-hidden="true" /> Encaisser
            </Button>
          )}
          {f.statut === 'brouillon' && (
            <Button size="sm" variant="outline" onClick={() => openEdit(f)}>
              Éditer
            </Button>
          )}
          {f.statut === 'brouillon' && nba !== 'emettre' && (
            <Button size="sm" variant="outline"
                    loading={busy} onClick={() => doAction(emettreFacture, f.id)}
                    title={f.motif_non_encaissable || undefined}>
              Émettre
            </Button>
          )}
          {/* EZ13 — « ✓ Payée » ÉTAIT ICI, en `variant="success"`, juste à
              côté d'« ⚡ Encaisser ». C'est le bouton PAUVRE : marquage sec qui
              DETRUIT mode, date et référence du règlement, alors qu'Encaisser
              capture tout en 3 clics. Sur une liste chargée, le pauvre
              gagnait. Il est désormais relégué au menu ⫰ (ci-dessous), derrière
              un AlertDialog qui EXPLIQUE ce qu'on perd. « Encaisser » devient
              l'unique action rapide — avec, DANS son dialogue, l'option
              « paiement simple (sans détail) » pour qui veut vraiment aller
              vite sans rien détruire. */}
          {f.encaissable !== false && nba !== 'encaisser' && (
            <Button size="sm" variant="default"
                    onClick={() => openPayModal(f)} title="Enregistrer un paiement">
              <Zap className="size-3.5" aria-hidden="true" /> Encaisser
            </Button>
          )}
          {/* FG53/WR2b — lien « Payer en ligne » (copié au presse-papier). */}
          {/* AFAC26 — seulement si quelque chose est exigible (une facture C&I dont
              seule la retenue reste due n'a rien à payer en ligne ; « Encaisser » reste). */}
          {f.encaissable !== false
            && (f.montant_exigible == null || toNumber(f.montant_exigible) > 0) && (
            <Button size="sm" variant="outline" loading={isPayLinkBusy}
                    onClick={() => handleLienPaiement(f)} title="Créer/copier le lien de paiement en ligne">
              <CreditCard /> Payer en ligne
            </Button>
          )}
          {f.fichier_pdf ? (
            <Button size="sm" variant="success" loading={isDownloading}
                    onClick={() => handleTelechargerPdf(f)} title="Télécharger le PDF">
              <Download /> PDF
            </Button>
          ) : (
            <Button size="sm" variant="outline" loading={isGenerating}
                    onClick={() => handleGenererPdf(f)} title="Générer le PDF">
              <FileText /> {isGenerating ? pdfLabel : 'PDF'}
            </Button>
          )}
          {isAdmin && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
            <Button size="sm" variant="outline" onClick={() => openAvoirModal(f)}
                    title="Créer un avoir (note de crédit)">
              Avoir
            </Button>
          )}
          {/* Actions secondaires regroupées : tiennent sans déborder
              sur écran étroit (menu compact « Actions »). */}
          {(['emise', 'payee', 'en_retard'].includes(f.statut)
            || (f.statut !== 'payee' && f.statut !== 'annulee')) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" title="Plus d'actions">
                  <MoreHorizontal /> Actions
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {/* EZ13 — le marquage sec « Payée » vit ICI désormais, jamais
                    plus à côté d'Encaisser. Il DETRUIT mode/date/référence du
                    règlement : la confirmation l'explique au lieu de demander
                    « êtes-vous sûr ? ». */}
                {(f.statut === 'emise' || f.statut === 'en_retard' || overdue) && (
                  <DropdownMenuItem
                    data-testid="marquer-payee"
                    onSelect={(e) => { e.preventDefault(); openMarquerPayee(f) }}>
                    <Check /> Marquer payée (sans détail)
                  </DropdownMenuItem>
                )}
                {/* APX14 — aperçu du PDF SANS quitter l'écran. */}
                {f.fichier_pdf && (
                  <DropdownMenuItem onSelect={(e) => { e.preventDefault(); openPreview(f) }}>
                    <Eye /> Aperçu du PDF
                  </DropdownMenuItem>
                )}
                {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                  <DropdownMenuItem
                    disabled={isWaBusy || !waPhoneOk}
                    title={!waPhoneOk ? 'Numéro invalide' : undefined}
                    onSelect={(e) => {
                      e.preventDefault()
                      // VX245(c) — une facture EN RETARD envoie le gabarit
                      // « relance » (déjà supporté par `whatsappFacture`,
                      // jamais construit ailleurs) plutôt que le gabarit
                      // générique « facture ».
                      handleWhatsApp(f, f.statut === 'en_retard' ? 'relance' : 'facture')
                    }}>
                    <MessageCircle />
                    {isWaBusy ? 'Préparation…'
                      : !waPhoneOk ? 'WhatsApp (numéro invalide)'
                        : f.statut === 'en_retard' ? 'Relancer par WhatsApp'
                          : 'WhatsApp'}
                  </DropdownMenuItem>
                )}
                {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                  <DropdownMenuItem onClick={() => handleUbl(f)}>
                    <Code2 /> Aperçu UBL
                  </DropdownMenuItem>
                )}
                {/* WIR103/ZFAC4 — note de débit (pendant de l'avoir) :
                    création + PDF, jusqu'ici serveur-only sans aucune UI. */}
                {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                  <DropdownMenuItem onSelect={(e) => { e.preventDefault(); openNoteDebit(f) }}>
                    <ReceiptText /> Note de débit
                  </DropdownMenuItem>
                )}
                {/* PACT121 — demande de paiement carte au client (CMI/Payzone).
                    Libellé distinct du bouton « Payer en ligne » (lien FG53)
                    pour qu'aucune action n'ait deux fois le même nom. */}
                {f.encaissable !== false && (
                  <DropdownMenuItem onSelect={(e) => { e.preventDefault(); openPaiementEnLigne(f) }}>
                    <CreditCard /> Demander un paiement carte
                  </DropdownMenuItem>
                )}
                {/* N105/WR2b — export DGI : masqué tant que l'interrupteur société est OFF. */}
                {dgiActif && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
                  <DropdownMenuItem
                    disabled={isDgiBusy}
                    onSelect={(e) => { e.preventDefault(); handleDgiExport(f) }}>
                    <ShieldCheck /> Export DGI
                  </DropdownMenuItem>
                )}
                {/* ── WIR183 — les quatre actions de FICHE, jusqu'ici sans
                    aucun point d'entrée (ZFAC1 / XFAC6 / XFAC13 / XPOS7).
                    Réservées au palier responsable/admin, comme le serveur. ── */}
                {canManage && f.statut === 'emise' && (
                  <DropdownMenuItem
                    data-testid="remettre-brouillon"
                    disabled={wir183Busy}
                    onSelect={(e) => { e.preventDefault(); handleRemettreBrouillon(f) }}>
                    Remettre en brouillon
                  </DropdownMenuItem>
                )}
                {canManage && (f.statut === 'en_retard' || overdue) && (
                  <DropdownMenuItem
                    data-testid="facturer-penalites"
                    disabled={wir183Busy}
                    onSelect={(e) => { e.preventDefault(); handleFacturerPenalites(f) }}>
                    Facturer les pénalités de retard
                  </DropdownMenuItem>
                )}
                {canManage && f.statut !== 'annulee'
                  && parseFloat(f.montant_du ?? 0) > 0 && (
                  <DropdownMenuItem
                    data-testid="abandonner-solde"
                    onSelect={(e) => { e.preventDefault(); openAbandonSolde(f) }}>
                    Abandonner le solde…
                  </DropdownMenuItem>
                )}
                {canManage && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
                  <DropdownMenuItem
                    data-testid="retour-client"
                    onSelect={(e) => { e.preventDefault(); openRetourClient(f) }}>
                    Retour client…
                  </DropdownMenuItem>
                )}
                {f.statut !== 'payee' && f.statut !== 'annulee' && (
                  <DropdownMenuItem
                    onClick={() => (demanderAnnulation
                      ? demanderAnnulation(f)
                      : doAction(annulerFacture, f.id, `Annuler la facture ${f.reference} ?`))}>
                    Annuler la facture
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </td>
    </tr>
    {/* VX97 — Panneau « Historique » : journal des changements de la facture
        (FactureActivity). Qui / quand / ancien→nouveau. `prix_achat` jamais
        rendu (le journal ne le porte pas). */}
    {histoOpenId === f.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Historique des modifications — {f.reference}
            </p>
            {histoLoadingId === f.id ? (
              <p className="text-xs text-muted-foreground">Chargement…</p>
            ) : (histoCache[f.id]?.length ?? 0) === 0 ? (
              <p className="text-xs text-muted-foreground">
                Aucune modification consignée.
              </p>
            ) : (
              <ul className="space-y-1 text-sm">
                {histoCache[f.id].map(a => (
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
          </div>
        </td>
      </tr>
    )}
    </Fragment>
  )
}

// AFAC13 — une facture qui porte de l'argent ne s'annule jamais sans dire où il
// va : l'écran impose le choix « transférer » (autre facture ouverte du même
// client) ou « rembourser », et affiche le refus serveur SOUS le choix. Aucune
// règle d'argent recalculée ici : le dialogue s'ouvre sur `montant_paye > 0`
// servi par le serveur, qui reste seul juge (AFAC12).
export function AnnulationFactureDialog({ facture, factures = [], busy = false, erreur = null, onConfirm, onClose }) {
  const [action, setAction] = useState('transferer')
  const [cible, setCible] = useState('')
  if (!facture) return null
  const cibles = factures.filter(x => x.id !== facture.id
    && String(x.client) === String(facture.client)
    && ['emise', 'en_retard'].includes(x.statut))
  const manque = action === 'transferer' && !cible
  const valider = () => onConfirm(action === 'transferer'
    ? { action, facture_cible: Number(cible) }
    : { action })
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Annuler la facture {facture.reference}</DialogTitle>
          <DialogDescription>
            Cette facture porte {formatMAD(toNumber(facture.montant_paye))} encaissés :
            dites où va cet argent avant de l’annuler.
          </DialogDescription>
        </DialogHeader>
        <fieldset className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="annulation-acompte" value="transferer"
                   checked={action === 'transferer'}
                   onChange={() => setAction('transferer')} />
            Transférer sur une autre facture
          </label>
          {action === 'transferer' && (
            <select aria-label="Facture cible" value={cible}
                    onChange={(e) => setCible(e.target.value)}
                    className="w-full rounded-md border px-2 py-1 text-sm">
              <option value="">Choisir une facture ouverte…</option>
              {cibles.map(x => (
                <option key={x.id} value={x.id}>{x.reference}</option>
              ))}
            </select>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="annulation-acompte" value="rembourser"
                   checked={action === 'rembourser'}
                   onChange={() => setAction('rembourser')} />
            Rembourser
          </label>
          {erreur && (
            <p role="alert" data-testid="annulation-erreur"
               className="text-sm text-destructive">{erreur}</p>
          )}
        </fieldset>
        <FormActions sticky={false}>
          <Button type="button" variant="ghost" onClick={onClose}>Retour</Button>
          <Button type="button" variant="destructive" loading={busy}
                  disabled={manque} onClick={valider}>
            Annuler la facture
          </Button>
        </FormActions>
      </DialogContent>
    </Dialog>
  )
}
