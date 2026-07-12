import { Fragment, useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search, Plus, Download, BookText, ListChecks, FileWarning,
  MessageCircle, Code2, Check, FileText, ReceiptText, MoreHorizontal,
  CreditCard, ShieldCheck, X, LayoutList, LayoutGrid, Printer, Zap,
} from 'lucide-react'
import {
  fetchFactures,
  emettreFacture,
  marquerPayeeFacture,
  annulerFacture,
  genererPdfFacture,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import api from '../../api/axios'
import importApi, { downloadXlsx } from '../../api/importApi'
import FactureForm from './FactureForm'
import FactureKanbanBoard from './FactureKanbanBoard'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  Skeleton, SkeletonTableRow,
  Tabs, TabsList, TabsTrigger,
  Input, Checkbox,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  FormField, FormActions,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  Popover, PopoverTrigger, PopoverContent,
  toast,
} from '../../ui'
import { formatMAD, toNumber, normalizeMaPhone, formatDateTime } from '../../lib/format'
import PaiementDialog from './PaiementDialog'
import { errorMessageFrom } from '../../lib/toast'
import { useSavedViews } from '../../hooks/useSavedViews'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import { useRotatingLabel } from '../../hooks/useRotatingLabel'
import useDocumentTitle from '../../hooks/useDocumentTitle'
// VX248 — raccourci d'ACTION sur la facture focalisée (la modale d'édition
// ouverte — seule vue « fiche » qui existe pour une facture, cf. VX220).
import { useFocusedRecordShortcuts } from '../../providers/focusedRecordShortcuts'
import { DataTable } from '../../ui/datatable'
import { openPdfBlob, openPdfInGesture } from '../../utils/pdfBlob'
import { downloadBlobInGesture } from '../../utils/downloadBlob'

// VX21 — squelette de la liste (parité DevisList/DevisTableSkeleton) : reprend
// les 8 colonnes du vrai tableau pour que la mise en page ne saute pas à
// l'arrivée des données. Affiché dans la même carte que le tableau réel, en
// gardant l'en-tête de page visible.
function FactureTableSkeleton() {
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-10" />
              <th>Référence</th>
              <th>Client</th>
              <th>Émission</th>
              <th>Échéance</th>
              <th className="ta-right">Total TTC</th>
              <th>Statut</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }).map((unused, i) => (
              <SkeletonTableRow key={i} columns={8} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

const FL_SAVED_VIEWS_KEY = 'taqinor.ventes.factures.savedViews'

// VX132 — chargement long conscient (voir DevisList.jsx PDF_GENERATION_LABELS) :
// libellés honnêtes côté client uniquement — le PDF facture reste le moteur
// legacy INTOUCHÉ (règle #4). Sans effet visible si la génération est brève
// (le libellé ne tourne qu'après ~2.5 s d'attente réelle).
const FACTURE_PDF_GENERATION_LABELS = [
  'Génération du PDF…',
  'Mise en forme de la facture…',
  'Finalisation du document…',
]

// ── ARC53 — Colonnes du frame `ui/datatable` en mode « ligne custom ».
// L'écran rend chaque ligne via `renderRow` (<FactureRow>) ; ces définitions ne
// décrivent que la grille au moteur (aucun `cell` n'est utilisé, tri/filtre/
// pagination désactivés via seams manuels). Le rendu réel reste 100 % dans
// <FactureRow> (mêmes cellules, boutons à état, menu « Actions », édition inline).
const FACTURE_DT_COLUMNS = [
  { id: 'reference', header: 'Référence', sortable: false, hideable: false, reorderable: false },
  { id: 'client', header: 'Client', sortable: false, hideable: false, reorderable: false },
  { id: 'date_emission', header: 'Émission', sortable: false, hideable: false, reorderable: false },
  { id: 'date_echeance', header: 'Échéance', sortable: false, hideable: false, reorderable: false },
  { id: 'total_ttc', header: 'Total TTC', align: 'right', sortable: false, hideable: false, reorderable: false },
  { id: 'statut', header: 'Statut', sortable: false, hideable: false, reorderable: false },
  { id: 'actions', header: 'Actions', sortable: false, hideable: false, reorderable: false },
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

const TABS = [
  { key: 'toutes',    label: 'Toutes' },
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'emise',     label: 'Émises' },
  { key: 'overdue',   label: 'En retard' },
  { key: 'partielle', label: 'Partiellement payées' },
  { key: 'payee',     label: 'Payées' },
  { key: 'annulee',   label: 'Annulées' },
]

// Filtre par type de facture d'échéancier (champ type_facture du modèle).
const TYPES_FACTURE = [
  { value: '',             label: 'Tous les types' },
  { value: 'complete',     label: 'Complète' },
  { value: 'acompte',      label: 'Acompte' },
  { value: 'intermediaire', label: 'Intermédiaire' },
  { value: 'solde',        label: 'Solde' },
]

// Facture à solde partiel : un acompte encaissé mais reste dû > 0.
const isPartiallyPaid = f =>
  toNumber(f.montant_paye) > 0 && toNumber(f.montant_du) > 0 &&
  f.statut !== 'annulee'

// VX230 — MODES_PAIEMENT + défauts intelligents VX92/VX93 (localStorage) ont
// suivi la modale de paiement dans le composant partagé PaiementDialog.jsx.

const today = new Date().toISOString().slice(0, 10)
const isOverdue = f =>
  f.is_overdue ||
  (f.statut === 'emise' && f.date_echeance && f.date_echeance < today)

// Prochaine action contextuelle (next-best-action) : clé de l'action mise en
// avant selon statut/montant dû/retard. Une brouillon → Émettre ; une émise en
// retard → Relancer ; une émise partiellement payée → Encaisser ; sinon null.
function nextBestAction(f) {
  if (f.statut === 'brouillon') return 'emettre'
  if (f.statut === 'annulee' || f.statut === 'payee') return null
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
function FactureRow({ f, ctx }) {
  const {
    selectedIds, toggleSelect,
    echeanceEditId, echeanceValue, setEcheanceValue, echeanceSaving,
    saveEcheance, setEcheanceEditId, startEditEcheance,
    dgiActif, isAdmin,
    actionId, pdfGenerating, pdfDownloading, waBusy, payLinkBusy, dgiBusy,
    openEdit, doAction, emettreFacture, marquerPayeeFacture, annulerFacture,
    openPayModal, handleLienPaiement, handleTelechargerPdf, handleGenererPdf,
    openAvoirModal, handleWhatsApp, handleUbl, handleDgiExport, handleDgiConformite,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    highlightFactureId,
  } = ctx
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
  const waPhoneOk = !!normalizeMaPhone(f.client_telephone)
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
        {f.devis_reference && f.devis && (
          <div className="mt-0.5 text-xs">
            <Link to={`/ventes/devis?ref=${encodeURIComponent(f.devis_reference)}`}
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
                    title="Action recommandée">
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
                    loading={busy} onClick={() => doAction(emettreFacture, f.id)}>
              Émettre
            </Button>
          )}
          {(f.statut === 'emise' || f.statut === 'en_retard' || overdue) && (
            <Button size="sm" variant="success" loading={busy}
                    onClick={() => doAction(marquerPayeeFacture, f.id, `Marquer la facture ${f.reference} comme payée ?`)}>
              <Check /> Payée
            </Button>
          )}
          {parseFloat(f.montant_du ?? 0) > 0 && f.statut !== 'annulee' && nba !== 'encaisser' && (
            <Button size="sm" variant="outline"
                    onClick={() => openPayModal(f)} title="Enregistrer un paiement">
              Enregistrer paiement
            </Button>
          )}
          {/* FG53/WR2b — lien « Payer en ligne » (copié au presse-papier). */}
          {parseFloat(f.montant_du ?? 0) > 0 && f.statut !== 'annulee' && (
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
                {/* N105/WR2b — export DGI : masqué tant que l'interrupteur société est OFF. */}
                {dgiActif && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
                  <DropdownMenuItem
                    disabled={isDgiBusy}
                    onSelect={(e) => { e.preventDefault(); handleDgiExport(f) }}>
                    <ShieldCheck /> Export DGI
                  </DropdownMenuItem>
                )}
                {f.statut !== 'payee' && f.statut !== 'annulee' && (
                  <DropdownMenuItem
                    onClick={() => doAction(annulerFacture, f.id, `Annuler la facture ${f.reference} ?`)}>
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

export default function FactureList() {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant).
  useDocumentTitle('Factures')
  const dispatch = useDispatch()
  const [searchParams, setSearchParams] = useSearchParams()
  const { factures, loading, error } = useSelector(s => s.ventes)
  const isAdmin = useSelector(s => s.auth.role) === 'admin'
  // VX21 — chargement différé anti-scintillement (parité DevisList) : spinner
  // discret puis squelette, en-tête de page toujours visible.
  const { showSpinner, showSkeleton } = useDelayedLoading(loading)

  // ── Avoir (note de crédit) : modale total OU partiel ──
  const [avoirTarget, setAvoirTarget] = useState(null) // facture ciblée
  const [avoirMotif, setAvoirMotif]   = useState('')
  const [avoirSaving, setAvoirSaving] = useState(false)
  // Quantités à créditer par ligne (clé = id de ligne) ; vide = avoir total.
  const [avoirQtes, setAvoirQtes]     = useState({})

  const openAvoirModal = async (f) => {
    setAvoirMotif('')
    setAvoirQtes({})
    // Charge le détail des lignes pour permettre un avoir partiel.
    try {
      const res = await ventesApi.getFacture(f.id)
      setAvoirTarget(res.data)
    } catch {
      setAvoirTarget(f)
    }
  }

  const handleCreerAvoir = async (mode) => {
    if (!avoirTarget) return
    setAvoirSaving(true)
    try {
      const payload = { motif: avoirMotif }
      if (mode === 'partiel') {
        const lignes = (avoirTarget.lignes || [])
          .map(l => ({ ...l, _qte: parseFloat(avoirQtes[l.id] ?? 0) }))
          .filter(l => l._qte > 0)
          .map(l => ({
            produit: l.produit ?? null,
            designation: l.designation,
            quantite: l._qte,
            prix_unitaire: l.prix_unitaire,
            remise: l.remise ?? 0,
            taux_tva: l.taux_tva,
          }))
        if (lignes.length === 0) {
          toast.error('Saisissez au moins une quantité à créditer.')
          setAvoirSaving(false)
          return
        }
        payload.lignes = lignes
      }
      await ventesApi.creerAvoir(avoirTarget.id, payload)
      setAvoirTarget(null)
      dispatch(fetchFactures())
      toast.success('Avoir créé. Retrouvez-le dans Ventes → Avoirs.')
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? "Création de l'avoir impossible.")
    } finally {
      setAvoirSaving(false)
    }
  }

  const [showForm, setShowForm]       = useState(false)
  const [editFacture, setEditFacture] = useState(null)
  // VX231(a) — deep-link ?facture=<id> (émis par PaiementsPage/Encaissements) :
  // atterrir sur la BONNE facture surlignée. On force l'onglet « toutes » pour
  // qu'elle ne soit jamais masquée par un filtre d'onglet, puis on la surligne
  // + scrolle 3 s (voir l'effet plus bas).
  const [searchParams] = useSearchParams()
  const [highlightFactureId, setHighlightFactureId] = useState(
    () => searchParams.get('facture') || null)
  const [activeTab, setActiveTab]     = useState('toutes')
  // VX250 — deep-link ?q=<texte> pré-règle la recherche (référence/client) au
  // montage — posé par LIST_ROUTE.facture (entityRoutes.js) et RelationCounters
  // (fiches 360°) sans jamais être lu jusqu'ici. Le filtre `search` existant
  // fait déjà exactement référence/client (ci-dessous) — aucune nouvelle
  // logique de filtre.
  const [search, setSearch]           = useState(() => searchParams.get('q') ?? '')
  const [typeFilter, setTypeFilter]   = useState('')
  // ZFAC9 — bascule Liste/Kanban (wiring/données only, réutilise `filtered`).
  const [viewMode, setViewMode]       = useState('liste')
  // Vues enregistrées (FG11).
  const { savedViews: factSavedViews, saveView: saveFactView, deleteView: deleteFactView } = useSavedViews(FL_SAVED_VIEWS_KEY)
  const saveCurrentFactView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    saveFactView(name, { activeTab, typeFilter })
  }
  const applyFactView = (v) => {
    if (v.state?.activeTab !== undefined) setActiveTab(v.state.activeTab)
    if (v.state?.typeFilter !== undefined) setTypeFilter(v.state.typeFilter)
  }
  const [actionId, setActionId]       = useState(null)
  const [pdfGenerating, setPdfGenerating] = useState({})
  const [pdfDownloading, setPdfDownloading] = useState({})
  const [auditBusy, setAuditBusy] = useState(false)
  // VX142(a) — Journal comptable : petit Dialog mois/trimestre à la place du
  // window.prompt() texte libre (regroupé dans le menu « Exporter »).
  const [journalOpen, setJournalOpen] = useState(false)
  const [journalMode, setJournalMode] = useState('mois') // 'mois' | 'trimestre'
  const [journalMois, setJournalMois] = useState(() => new Date().toISOString().slice(0, 7))
  const [journalAnnee, setJournalAnnee] = useState(() => String(new Date().getFullYear()))
  const [journalTrimestre, setJournalTrimestre] = useState('1')
  const [journalBusy, setJournalBusy] = useState(false)
  // VX142(a) — Export comptable : même traitement, deux champs date au lieu
  // de deux window.prompt() successifs.
  const [exportComptableOpen, setExportComptableOpen] = useState(false)
  const [exportStart, setExportStart] = useState(() => new Date().toISOString().slice(0, 8) + '01')
  const [exportEnd, setExportEnd] = useState(() => new Date().toISOString().slice(0, 10))
  const [exportComptableBusy, setExportComptableBusy] = useState(false)
  // VX172 — pending visible sur « Exporter Excel » (VX49 pose déjà le toast
  // d'erreur ; ceci ajoute juste l'état chargement manquant).
  const [xlsxBusy, setXlsxBusy] = useState(false)
  // ── Envoi WhatsApp : busy par facture (L857), langue (L851), aperçu (L852) ──
  const [waBusy, setWaBusy] = useState({})
  const [waLangue, setWaLangue] = useState('fr')
  const [waPreview, setWaPreview] = useState(null) // { reference, message, url, wa_url }

  // WR2b — interrupteur société « export DGI » (lu une fois au montage) :
  // n'affiche le bouton/badge DGI que quand la société l'a activé (défaut OFF,
  // capacité invisible sinon — même garde que côté serveur).
  const [dgiActif, setDgiActif] = useState(false)
  useEffect(() => {
    parametresApi.getProfile()
      .then(res => setDgiActif(!!res.data?.dgi_export_actif))
      .catch(() => setDgiActif(false))
  }, [])
  const [dgiBusy, setDgiBusy] = useState({})
  const [payLinkBusy, setPayLinkBusy] = useState({})

  // WR2b — sélection multiple pour la barre d'actions en masse (FG43).
  const [selectedIds, setSelectedIds] = useState([])
  const toggleSelect = (id) => setSelectedIds(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  const clearSelection = () => setSelectedIds([])
  const [bulkBusy, setBulkBusy] = useState(false)

  // ── Enregistrement de paiement (VX230 — modale extraite en PaiementDialog) ──
  // FactureList ne garde que la facture CIBLÉE ; tout l'état de saisie, l'arrondi
  // ZFAC11 et le chatter vivent désormais dans PaiementDialog (partagé avec
  // RelancesPage). `onSaved` rafraîchit la liste après chaque encaissement.
  const [payTarget, setPayTarget] = useState(null) // facture ciblée
  const openPayModal = (f) => setPayTarget(f)

  // VX97 — Panneau « Historique » repliable dans le détail facture : journal des
  // changements (FactureActivity) — qui/quand/ancien→nouveau — sur le document
  // au plus gros blast-radius financier. Feed existant monté ; migrera vers
  // ChatterTimeline (VX23). `prix_achat` jamais rendu (le journal ne le porte pas).
  const [histoOpenId, setHistoOpenId] = useState(null)
  const [histoCache, setHistoCache] = useState({})   // id → entrées
  const [histoLoadingId, setHistoLoadingId] = useState(null)
  const toggleHistorique = (id) => {
    if (histoOpenId === id) { setHistoOpenId(null); return }
    setHistoOpenId(id)
    if (histoCache[id] === undefined) {
      setHistoLoadingId(id)
      api.get(`/ventes/factures/${id}/historique/`)
        .then(res => setHistoCache(c => ({ ...c, [id]: res.data || [] })))
        .catch(() => setHistoCache(c => ({ ...c, [id]: [] })))
        .finally(() => setHistoLoadingId(l => (l === id ? null : l)))
    }
  }

  // ── Édition inline de la date d'échéance (facture émise) ──
  const [echeanceEditId, setEcheanceEditId] = useState(null)
  const [echeanceValue, setEcheanceValue]   = useState('')
  const [echeanceSaving, setEcheanceSaving] = useState(false)

  const startEditEcheance = (f) => {
    setEcheanceEditId(f.id)
    setEcheanceValue(f.date_echeance ?? '')
  }
  const saveEcheance = async (f) => {
    setEcheanceSaving(true)
    try {
      await ventesApi.patchFacture(f.id, { date_echeance: echeanceValue || null })
      setEcheanceEditId(null)
      dispatch(fetchFactures())
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Mise à jour de l’échéance impossible.')
    } finally {
      setEcheanceSaving(false)
    }
  }

  useEffect(() => { dispatch(fetchFactures()) }, [dispatch])

  // VX231(a) — une fois les factures chargées, si un ?facture=<id> est ciblé,
  // scrolle la ligne au centre et retire la surbrillance après 3 s (le repère
  // visuel a fait son office). Ne se déclenche qu'une fois (la surbrillance se
  // vide elle-même).
  useEffect(() => {
    if (!highlightFactureId || factures.length === 0) return undefined
    const el = document.getElementById(`facture-row-${highlightFactureId}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const t = setTimeout(() => setHighlightFactureId(null), 3000)
    return () => clearTimeout(t)
  }, [highlightFactureId, factures.length])

  const filtered = useMemo(() => {
    let list = factures
    if (activeTab === 'overdue') {
      list = list.filter(isOverdue)
    } else if (activeTab === 'partielle') {
      list = list.filter(isPartiallyPaid)
    } else if (activeTab !== 'toutes') {
      list = list.filter(f => f.statut === activeTab)
    }
    if (typeFilter) {
      list = list.filter(f => f.type_facture === typeFilter)
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(f =>
        f.reference?.toLowerCase().includes(q) ||
        (f.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [factures, activeTab, search, typeFilter])

  // VX230 — total « reste à encaisser » de la SÉLECTION filtrée courante (onglet
  // + type + recherche), dérivé de `filtered` déjà en mémoire (zéro appel
  // réseau). Répond au manque : le cockpit montre « Encaissé ce mois » mais
  // jamais le dû de l'onglet « Partiellement payées » sous les yeux.
  const resteAEncaisserOnglet = useMemo(
    () => filtered.reduce((s, f) => s + (toNumber(f.montant_du) || 0), 0),
    [filtered])

  const counts = useMemo(() => ({
    toutes:    factures.length,
    brouillon: factures.filter(f => f.statut === 'brouillon').length,
    emise:     factures.filter(f => f.statut === 'emise' && !isOverdue(f)).length,
    overdue:   factures.filter(isOverdue).length,
    partielle: factures.filter(isPartiallyPaid).length,
    payee:     factures.filter(f => f.statut === 'payee').length,
    annulee:   factures.filter(f => f.statut === 'annulee').length,
  }), [factures])

  // Total encaissé du mois courant, dérivé on-the-fly des paiements des
  // factures chargées (date_paiement dans le mois en cours).
  const encaisseMois = useMemo(() => {
    const ym = today.slice(0, 7)  // AAAA-MM
    let total = 0
    for (const f of factures) {
      for (const p of (f.paiements || [])) {
        if ((p.date_paiement || '').slice(0, 7) === ym) {
          total += toNumber(p.montant) || 0
        }
      }
    }
    return total
  }, [factures])

  // VX21 — cockpit trésorerie : 3 cartes additionnelles dérivées des factures
  // déjà chargées (aucun appel réseau). Encaissé ce mois (au-dessus) mesure le
  // flux entrant ; Total dû / En retard / À échoir ≤7 j mesurent l'encours.
  const encaisseMoisPrecedent = useMemo(() => {
    const d = new Date()
    d.setMonth(d.getMonth() - 1)
    const ym = d.toISOString().slice(0, 7)
    let total = 0
    for (const f of factures) {
      for (const p of (f.paiements || [])) {
        if ((p.date_paiement || '').slice(0, 7) === ym) {
          total += toNumber(p.montant) || 0
        }
      }
    }
    return total
  }, [factures])

  const totalDu = useMemo(
    () => factures.reduce((s, f) => s + (toNumber(f.montant_du) || 0), 0),
    [factures])

  const totalEnRetard = useMemo(
    () => factures.filter(isOverdue)
      .reduce((s, f) => s + (toNumber(f.montant_du) || 0), 0),
    [factures])
  const countEnRetard = useMemo(() => factures.filter(isOverdue).length, [factures])

  // À échoir dans les 7 prochains jours (émise, pas déjà en retard).
  const in7Days = new Date(today)
  in7Days.setDate(in7Days.getDate() + 7)
  const in7DaysIso = in7Days.toISOString().slice(0, 10)
  const aEcheoirSoon = useMemo(
    () => factures.filter(f =>
      f.statut === 'emise' && !isOverdue(f)
      && f.date_echeance && f.date_echeance >= today && f.date_echeance <= in7DaysIso),
    [factures, in7DaysIso])
  const totalAEcheoirSoon = useMemo(
    () => aEcheoirSoon.reduce((s, f) => s + (toNumber(f.montant_du) || 0), 0),
    [aEcheoirSoon])

  // VX142(a) — Export comptable DGI (groundwork) : factures validées d'une
  // plage, en .xlsx ET .csv (ventilation TVA par ligne + ICE + totaux).
  // Borné société. Plage saisie via le petit Dialog `exportComptableOpen`
  // (deux champs date), plus de window.prompt().
  const handleExportComptable = async () => {
    const start = exportStart
    const end = exportEnd
    if (!start || !end) return
    setExportComptableBusy(true)
    const dl = async (fmt, ext) => {
      const res = await api.get('/ventes/export-comptable/', {
        params: { start, end, fmt }, responseType: 'blob',
      })
      openPdfBlob(res.data, `export-comptable-${start}_${end}.${ext}`)
    }
    try {
      await dl('xlsx', 'xlsx')
      await dl('csv', 'csv')
      setExportComptableOpen(false)
    } catch {
      toast.error('Export comptable impossible.')
    } finally {
      setExportComptableBusy(false)
    }
  }

  // VX142(a) — Journal des ventes + résumé TVA : plus de window.prompt(), la
  // période (mois ou trimestre) vient du Dialog `journalOpen`.
  const handleJournalComptable = async () => {
    const v = journalMode === 'trimestre'
      ? `${journalAnnee}-${journalTrimestre}`
      : journalMois
    const isQuarter = journalMode === 'trimestre'
    const params = isQuarter ? { quarter: v } : { month: v }
    setJournalBusy(true)
    try {
      const r = await ventesApi.journalVentes(params)
      downloadXlsx(r.data, `journal-ventes-${v}.xlsx`)
      setJournalOpen(false)
    } catch {
      toast.error('Journal comptable indisponible.')
    } finally {
      setJournalBusy(false)
    }
  }

  const openNew   = () => { setEditFacture(null); setShowForm(true) }
  const openEdit  = f  => { setEditFacture(f);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);   setEditFacture(null) }
  const onSaved   = () => dispatch(fetchFactures())

  // VX220 — lien profond ?id=<pk> (patron VX79 déjà lu par InstallationsPage.jsx/
  // TicketsPage.jsx) : la palette de commandes (⌘K) ouvre désormais la FACTURE
  // exacte — la modale d'édition est la seule vue « fiche » qui existe pour une
  // facture, donc c'est elle qui joue le rôle du panneau détail. Posé une fois
  // les factures chargées (jamais avant, la recherche échouerait toujours) ;
  // id introuvable → silencieux (jamais un crash). Le paramètre est retiré dans
  // tous les cas pour ne pas rouvrir la modale à chaque re-render.
  useEffect(() => {
    const wantedId = searchParams.get('id')
    if (!wantedId || loading) return
    const match = factures.find(f => String(f.id) === String(wantedId))
    if (match) openEdit(match)
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('id')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, loading, factures])

  const doAction = async (thunk, id, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return
    setActionId(id)
    try {
      await dispatch(thunk(id)).unwrap()
    } catch (err) {
      // VX63 — plus de JSON brut à l'écran : message FR lisible extrait du
      // payload d'erreur (le sweep alert→toast reste la propriété de VX19).
      toast.error(errorMessageFrom({ response: { data: err } }, 'Action impossible.'))
    } finally {
      setActionId(null)
    }
  }

  const handleGenererPdf = async (f) => {
    setPdfGenerating(prev => ({ ...prev, [f.id]: true }))
    try {
      await dispatch(genererPdfFacture(f.id)).unwrap()
      let attempts = 0
      const poll = async () => {
        if (attempts++ > 15) {
          toast.error('La génération PDF prend plus de temps que prévu. Réessayez dans quelques instants.')
          return
        }
        try {
          const res = await ventesApi.getFacture(f.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchFactures())
          } else {
            setTimeout(poll, 2000)
          }
        } catch {
          // ignore poll errors
        }
      }
      setTimeout(poll, 2000)
    } catch (err) {
      toast.error(err?.detail ?? 'Erreur lors de la génération PDF.')
    } finally {
      setPdfGenerating(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // VX248 — « a » génère le PDF de la facture FOCALISÉE (la modale d'édition
  // ouverte via `?id=` (VX220) ou un clic « Modifier » — `editFacture` est la
  // seule notion de « fiche » qui existe pour une facture). Absent quand
  // aucune facture n'est ouverte (liste nue).
  useFocusedRecordShortcuts(
    'factureDetail',
    { a: () => editFacture && handleGenererPdf(editFacture) },
    !!editFacture,
  )

  const handleTelechargerPdf = async (f) => {
    setPdfDownloading(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfFacture(f.id)
      openPdfBlob(res.data, `${f.reference}.pdf`)
    } catch {
      toast.error('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // Envoyer par WhatsApp : construit le message côté serveur (FR/Darija) puis
  // montre un aperçu (message + lien public) avant d'ouvrir wa.me ; le
  // commercial appuie lui-même sur Envoyer. Le POST consigne aussi l'action au
  // chatter de la facture (côté serveur, L856).
  const handleWhatsApp = async (f, modele = 'facture') => {
    setWaBusy(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.whatsappFacture(f.id, { modele, langue: waLangue })
      setWaPreview({
        reference: f.reference,
        message: res.data?.message ?? '',
        url: res.data?.url ?? '',
        wa_url: res.data?.wa_url ?? '',
      })
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // Ouvre wa.me après confirmation de l'aperçu.
  // VX48 — exclu volontairement : ce window.open() n'est précédé d'AUCUN await
  // (il tourne synchrone dans le clic du bouton « Envoyer » de la modale), donc
  // hors du bug Safari iOS (qui ne bloque qu'un window.open post-await). Ce
  // n'est de toute façon pas un PDF (lien wa.me).
  const ouvrirWhatsApp = () => {
    if (waPreview?.wa_url) window.open(waPreview.wa_url, '_blank', 'noopener')
    setWaPreview(null)
  }

  // N38 — télécharge l'aperçu BROUILLON UBL 2.1 (XML) de la facture.
  const handleUbl = async (f) => {
    try {
      const res = await ventesApi.telechargerUbl(f.id)
      openPdfBlob(res.data, `${f.reference}-ubl.xml`)
    } catch {
      toast.error("Génération de l'aperçu UBL impossible.")
    }
  }

  // N31 — audit admin de la numérotation : résumé des trous/doublons.
  const handleAuditNumerotation = async () => {
    setAuditBusy(true)
    try {
      const { data } = await ventesApi.auditNumerotation()
      if (data.conforme) {
        toast.success('Numérotation conforme : aucun trou ni doublon détecté.')
      } else {
        const lignes = []
        const labels = { devis: 'Devis', facture: 'Factures',
          avoir: 'Avoirs', bon_commande: 'Bons de commande' }
        for (const cle of Object.keys(labels)) {
          for (const g of (data[cle] || [])) {
            const parts = []
            if (g.manquants.length) parts.push(`manquants : ${g.manquants.join(', ')}`)
            if (g.doublons.length) parts.push(`doublons : ${g.doublons.join(', ')}`)
            lignes.push(`${labels[cle]} ${g.radical} → ${parts.join(' ; ')}`)
          }
        }
        toast.error(`Anomalies de numérotation détectées :\n\n${lignes.join('\n')}\n\n`
          + `(${data.total_manquants} numéro(s) manquant(s), `
          + `${data.total_doublons} doublon(s)). Aucune renumérotation automatique.`)
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? "Audit de numérotation impossible.")
    } finally {
      setAuditBusy(false)
    }
  }

  // FG53/WR2b — « Payer en ligne » : crée/réutilise le lien de paiement puis le
  // copie au presse-papier (aucun envoi automatique au client).
  // VX48 — le repli window.open (quand le presse-papier est indisponible) suit
  // un await : onglet pré-ouvert SYNCHRONE (pas un PDF, donc `.win.location`
  // direct plutôt que `openPdfInGesture().deliver()` qui attend un Blob).
  const handleLienPaiement = async (f) => {
    setPayLinkBusy(prev => ({ ...prev, [f.id]: true }))
    const pending = openPdfInGesture()
    try {
      const { data } = await ventesApi.lienPaiementFacture(f.id)
      const url = data?.pay_url ?? ''
      if (url && navigator.clipboard?.writeText) {
        pending.win?.close?.()
        await navigator.clipboard.writeText(url)
        toast.success(`Lien de paiement copié — ${formatMAD(data.montant)}.`)
      } else if (url) {
        if (pending.win && !pending.win.closed) {
          pending.win.location = url
        } else {
          toast.error('Ouverture bloquée par le navigateur.', {
            action: { label: 'Ouvrir', onClick: () => window.open(url, '_blank', 'noopener') },
          })
        }
      } else {
        pending.win?.close?.()
        toast.error('Lien de paiement indisponible.')
      }
    } catch (err) {
      pending.win?.close?.()
      toast.error(err?.response?.data?.detail ?? 'Création du lien de paiement impossible.')
    } finally {
      setPayLinkBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // N105/WR2b — export DGI (UBL local) : téléchargement direct, aucune transmission.
  const handleDgiExport = async (f) => {
    setDgiBusy(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.dgiExportFacture(f.id)
      openPdfBlob(res.data, `${f.reference}-dgi.xml`)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Export DGI impossible.')
    } finally {
      setDgiBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // N105/WR2b — contrôle de conformité DGI à la demande (aucun statut modifié).
  const handleDgiConformite = async (f) => {
    setDgiBusy(prev => ({ ...prev, [f.id]: true }))
    try {
      const { data } = await ventesApi.dgiConformiteFacture(f.id)
      if (data.conforme) {
        toast.success('Conforme DGI : aucun problème détecté.')
      } else {
        toast.error(`Non conforme DGI :\n\n- ${(data.problemes || []).join('\n- ')}`)
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Contrôle de conformité DGI impossible.')
    } finally {
      setDgiBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // FG43/WR2b — actions en masse sur la sélection courante.
  const BULK_LABELS = {
    emettre: 'Émettre', relancer: 'Relancer',
    'envoyer-email': 'Envoyer par email', 'generer-pdf': 'Générer le PDF',
  }
  const handleBulkAction = async (action) => {
    if (!selectedIds.length) return
    setBulkBusy(true)
    try {
      const { data } = await ventesApi.bulkFactures(action, selectedIds)
      const entries = Object.values(data || {})
      const ok = entries.filter(r => r.ok).length
      const ko = entries.length - ok
      if (ko === 0) {
        toast.success(`${BULK_LABELS[action] ?? action} : ${ok} facture(s) traitée(s).`)
      } else {
        toast.error(`${BULK_LABELS[action] ?? action} : ${ok} réussie(s), ${ko} échec(s).`)
      }
      dispatch(fetchFactures())
      clearSelection()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Action en masse impossible.')
    } finally {
      setBulkBusy(false)
    }
  }

  // ── ARC53 — Sac de contexte passé à chaque <FactureRow> (« lignes divisées »).
  // Regroupe l'état + les handlers que la ligne utilisait déjà depuis la clôture ;
  // aucune valeur n'est transformée ni aucun flux modifié.
  const rowCtx = {
    selectedIds, toggleSelect,
    echeanceEditId, echeanceValue, setEcheanceValue, echeanceSaving,
    saveEcheance, setEcheanceEditId, startEditEcheance,
    dgiActif, isAdmin,
    actionId, pdfGenerating, pdfDownloading, waBusy, payLinkBusy, dgiBusy,
    openEdit, doAction, emettreFacture, marquerPayeeFacture, annulerFacture,
    openPayModal, handleLienPaiement, handleTelechargerPdf, handleGenererPdf,
    openAvoirModal, handleWhatsApp, handleUbl, handleDgiExport, handleDgiConformite,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    highlightFactureId,
  }

  // VX21 — l'en-tête de page reste TOUJOURS visible (chargement, erreur,
  // données), parité DevisList/J141 : la mise en page ne saute plus au retour
  // des données (plus de spinner plein écran qui remplace toute la page).
  const pageHeader = (
    <div className="page-header">
      <h2>
        Factures
        {factures.length > 0 && (
          <Badge tone="primary" className="ml-2 align-middle">{factures.length}</Badge>
        )}
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="search"
          className="w-full sm:w-56"
          leading={<Search />}
          placeholder="Référence, client…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <Select value={typeFilter || 'all'}
                onValueChange={v => setTypeFilter(v === 'all' ? '' : v)}>
          <SelectTrigger className="w-full sm:w-44" title="Filtrer par type de facture">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TYPES_FACTURE.map(t => (
              <SelectItem key={t.value || 'all'} value={t.value || 'all'}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* VX80 — impression navigateur (feuille print.css : chrome masqué,
            noir-sur-blanc, table complète). Distinct des PDF WeasyPrint. */}
        <Button size="sm" variant="outline" onClick={() => window.print()}>
          <Printer /> Imprimer
        </Button>
        {/* VX142(a) — toolbar à 5 groupes : recherche+filtre, imprimer,
            EXPORTER (menu unique, remplace 4 boutons à plat + le
            window.prompt() du Journal comptable), langue WhatsApp, Nouvelle
            facture. */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline">
              <Download /> Exporter
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem
              disabled={xlsxBusy}
              onSelect={() => {
                const pending = downloadBlobInGesture()
                setXlsxBusy(true)
                importApi.exportList('factures', factures.map(f => f.id))
                  .then(r => pending.deliver(r.data, 'factures.xlsx'))
                  .catch(() => {})
                  .finally(() => setXlsxBusy(false))
              }}>
              {xlsxBusy ? <Spinner className="size-3.5" /> : <Download className="size-3.5" aria-hidden="true" />} Exporter Excel
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setJournalOpen(true)}>
              <BookText className="size-3.5" aria-hidden="true" /> Journal comptable…
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setExportComptableOpen(true)}>
              <Download className="size-3.5" aria-hidden="true" /> Export comptable…
            </DropdownMenuItem>
            {isAdmin && (
              <DropdownMenuItem disabled={auditBusy} onSelect={handleAuditNumerotation}>
                <ListChecks className="size-3.5" aria-hidden="true" /> Audit numérotation
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        {/* L851 — langue des messages WhatsApp (FR par défaut). */}
        <div role="group" aria-label="Langue des messages WhatsApp"
             className="inline-flex items-center gap-1"
             title="Langue du message « Envoyer par WhatsApp »">
          <MessageCircle className="size-4 text-muted-foreground" />
          {[['fr', 'FR'], ['darija', 'Darija']].map(([val, label]) => (
            <Button key={val} size="sm"
                    variant={waLangue === val ? 'default' : 'outline'}
                    aria-pressed={waLangue === val}
                    onClick={() => setWaLangue(val)}>
              {label}
            </Button>
          ))}
        </div>
        <Button onClick={openNew}><Plus /> Nouvelle facture</Button>
      </div>
      {/* VX142(a) — Journal comptable : Dialog mois/trimestre (remplace le
          window.prompt() texte libre). */}
      <Dialog open={journalOpen} onOpenChange={setJournalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Journal comptable</DialogTitle>
            <DialogDescription>
              Journal des ventes + résumé TVA (comptable), par mois ou par trimestre.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div role="group" aria-label="Période" className="inline-flex gap-1">
              {[['mois', 'Mois'], ['trimestre', 'Trimestre']].map(([val, label]) => (
                <Button key={val} type="button" size="sm"
                        variant={journalMode === val ? 'default' : 'outline'}
                        aria-pressed={journalMode === val}
                        onClick={() => setJournalMode(val)}>
                  {label}
                </Button>
              ))}
            </div>
            {journalMode === 'mois' ? (
              <Input type="month" value={journalMois}
                     onChange={e => setJournalMois(e.target.value)}
                     aria-label="Mois du journal" />
            ) : (
              <div className="flex gap-2">
                <Input type="number" className="w-28" value={journalAnnee}
                       onChange={e => setJournalAnnee(e.target.value)}
                       aria-label="Année du trimestre" />
                <Select value={journalTrimestre} onValueChange={setJournalTrimestre}>
                  <SelectTrigger className="w-32" aria-label="Trimestre">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {['1', '2', '3', '4'].map(q => (
                      <SelectItem key={q} value={q}>{`T${q}`}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJournalOpen(false)}>Annuler</Button>
            <Button loading={journalBusy} onClick={handleJournalComptable}>Télécharger</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* VX142(a) — Export comptable : Dialog plage de dates (remplace les
          deux window.prompt() successifs). */}
      <Dialog open={exportComptableOpen} onOpenChange={setExportComptableOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Export comptable</DialogTitle>
            <DialogDescription>
              Factures validées d'une plage de dates, en Excel + CSV (ventilation TVA, ICE, totaux).
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-2">
            <Input type="date" value={exportStart} required
                   onChange={e => setExportStart(e.target.value)}
                   aria-label="Date de début" />
            <Input type="date" value={exportEnd} required
                   onChange={e => setExportEnd(e.target.value)}
                   aria-label="Date de fin" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExportComptableOpen(false)}>Annuler</Button>
            <Button loading={exportComptableBusy} onClick={handleExportComptable}>Télécharger</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )

  if (loading) {
    return (
      <div className="page">
        {pageHeader}
        {showSpinner && (
          <div className="mt-4 flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Spinner /> Chargement des factures…
          </div>
        )}
        {showSkeleton && (
          <>
            {/* Rangée de cartes trésorerie squelette (parité KPI ci-dessous). */}
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((unused, i) => (
                <div key={i} className="rounded-lg border border-border bg-card p-3">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="mt-2 h-6 w-20" />
                  <Skeleton className="mt-1.5 h-3 w-16" />
                </div>
              ))}
            </div>
            <FactureTableSkeleton />
          </>
        )}
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        {pageHeader}
        <EmptyState className="mt-4" icon={FileWarning} title="Erreur de chargement"
                    description="Impossible de charger les factures. Réessayez." />
      </div>
    )
  }

  return (
    <div className="page">
      {pageHeader}

      {showForm && (
        <FactureForm facture={editFacture} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Modale d'enregistrement de paiement (VX230 — composant partagé) ── */}
      <PaiementDialog
        facture={payTarget}
        onOpenChange={(o) => { if (!o) setPayTarget(null) }}
        onSaved={() => dispatch(fetchFactures())}
      />

      {/* ── Modale d'avoir (total ou partiel par ligne) ── */}
      <Dialog open={!!avoirTarget} onOpenChange={(o) => { if (!o) setAvoirTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un avoir — {avoirTarget?.reference}</DialogTitle>
            <DialogDescription>
              Avoir total (toute la facture) ou partiel (quantités à créditer par ligne).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <FormField label="Motif (optionnel)" htmlFor="avoir-motif" fullWidth>
              <Input id="avoir-motif" type="text" value={avoirMotif}
                     onChange={e => setAvoirMotif(e.target.value)} />
            </FormField>
            {(avoirTarget?.lignes?.length ?? 0) > 0 && (
              <div className="overflow-x-auto">
                <table className="data-table text-sm">
                  <thead>
                    <tr>
                      <th>Désignation</th>
                      <th className="ta-right">Qté facturée</th>
                      <th className="ta-right">Qté à créditer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {avoirTarget.lignes.map(l => (
                      <tr key={l.id}>
                        <td data-label="Désignation">{l.designation}</td>
                        <td className="ta-right tabular-nums" data-label="Qté facturée">{l.quantite}</td>
                        <td className="ta-right" data-label="Qté à créditer">
                          <Input
                            type="number" min="0" step="any"
                            className="w-24"
                            value={avoirQtes[l.id] ?? ''}
                            max={l.quantite}
                            onChange={e => setAvoirQtes(q => ({ ...q, [l.id]: e.target.value }))}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setAvoirTarget(null)}>Annuler</Button>
            {(avoirTarget?.lignes?.length ?? 0) > 0 && (
              <Button type="button" variant="outline" loading={avoirSaving}
                      onClick={() => handleCreerAvoir('partiel')}>
                Avoir partiel
              </Button>
            )}
            <Button type="button" loading={avoirSaving}
                    onClick={() => handleCreerAvoir('total')}>
              Avoir total
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* ── L852 — Aperçu du message WhatsApp avant ouverture de wa.me ── */}
      <Dialog open={!!waPreview} onOpenChange={(o) => { if (!o) setWaPreview(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aperçu du message WhatsApp — {waPreview?.reference}</DialogTitle>
            <DialogDescription>
              {waLangue === 'darija' ? 'Variante Darija' : 'Variante Français'}
              {' '}— vérifiez le texte et le lien, puis ouvrez WhatsApp.
            </DialogDescription>
          </DialogHeader>
          <pre className="m-0 whitespace-pre-wrap break-words rounded-lg bg-muted p-3 text-sm"
               style={{ fontFamily: 'inherit' }}>
            {waPreview?.message}
          </pre>
          {waPreview?.url && (
            <p className="mt-2 break-words text-xs text-muted-foreground">
              Lien public : {waPreview.url}
            </p>
          )}
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setWaPreview(null)}>Annuler</Button>
            <Button type="button" variant="success" disabled={!waPreview?.wa_url}
                    onClick={ouvrirWhatsApp}>
              <MessageCircle /> Ouvrir WhatsApp
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* VX21 — cockpit trésorerie : 4 cartes KPI max, détail sous le pli
          (Stripe) — un directeur voit la santé de trésorerie d'un coup d'œil.
          Anatomie complète : valeur + delta (vs mois précédent où pertinent)
          + période. Dérivées des factures déjà chargées, aucun appel réseau. */}
      {factures.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Card className="p-3 text-sm">
            <div className="text-muted-foreground">Encaissé ce mois</div>
            <div className="mt-1 text-lg font-semibold tabular-nums">{formatMAD(encaisseMois)}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {encaisseMoisPrecedent > 0 ? (
                <span className={encaisseMois >= encaisseMoisPrecedent ? 'text-success' : 'text-destructive'}>
                  {encaisseMois >= encaisseMoisPrecedent ? '▲' : '▼'}{' '}
                  {formatMAD(Math.abs(encaisseMois - encaisseMoisPrecedent))} vs mois dernier
                </span>
              ) : 'Mois en cours'}
            </div>
          </Card>
          <Card className="p-3 text-sm">
            <div className="text-muted-foreground">Total dû</div>
            <div className="mt-1 text-lg font-semibold tabular-nums">{formatMAD(totalDu)}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              Toutes factures non soldées
            </div>
          </Card>
          <Card className="p-3 text-sm">
            <div className="text-muted-foreground">En retard</div>
            <div className={`mt-1 text-lg font-semibold tabular-nums ${countEnRetard > 0 ? 'text-destructive' : ''}`}>
              {formatMAD(totalEnRetard)}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {countEnRetard} facture{countEnRetard > 1 ? 's' : ''} échue{countEnRetard > 1 ? 's' : ''}
            </div>
          </Card>
          <Card className="p-3 text-sm">
            <div className="text-muted-foreground">À échoir ≤ 7 j</div>
            <div className="mt-1 text-lg font-semibold tabular-nums">{formatMAD(totalAEcheoirSoon)}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {aEcheoirSoon.length} facture{aEcheoirSoon.length > 1 ? 's' : ''} · 7 prochains jours
            </div>
          </Card>
        </div>
      )}

      {/* ── Tabs + vues enregistrées (FG11) ── */}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="flex-wrap">
            {TABS.map(t => (
              <TabsTrigger key={t.key} value={t.key}
                           className={t.key === 'overdue' && counts.overdue > 0 ? 'text-destructive data-[state=active]:text-destructive' : undefined}>
                {t.label}
                {counts[t.key] > 0 && (
                  <span className="ml-1.5 rounded bg-muted px-1.5 text-xs text-muted-foreground">{counts[t.key]}</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        {/* VX230 — « Reste à encaisser » de l'onglet/filtre courant (dérivé de
            `filtered`). Visible dès qu'un reste dû existe dans la sélection —
            surtout utile sur « Partiellement payées ». */}
        {resteAEncaisserOnglet > 0 && (
          <span
            className="rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground tabular-nums"
            title="Somme des montants encore dus sur les factures affichées (onglet + filtres courants)"
          >
            Reste à encaisser (onglet) :{' '}
            <strong className="text-foreground">{formatMAD(resteAEncaisserOnglet)}</strong>
          </span>
        )}
        <div className="lp-saved-views">
          <Button type="button" variant="link" size="sm" onClick={saveCurrentFactView}>
            ⭐ Enregistrer cette vue
          </Button>
          {factSavedViews.map((v) => (
            <span key={v.name} className="lp-saved-view-chip">
              <button type="button" className="lp-saved-view-apply"
                      onClick={() => applyFactView(v)} title="Appliquer cette vue">
                {v.name}
              </button>
              <button type="button" className="lp-saved-view-del"
                      onClick={() => deleteFactView(v.name)}
                      aria-label={`Supprimer la vue ${v.name}`}>
                ✕
              </button>
            </span>
          ))}
        </div>
        {/* ZFAC9 — bascule Liste/Kanban : réutilise `filtered` déjà chargé,
            aucune donnée/refonte nouvelle. */}
        <div className="ml-auto flex items-center gap-1 rounded-md border border-border p-0.5" role="group" aria-label="Mode d’affichage">
          <Button
            type="button" size="sm"
            variant={viewMode === 'liste' ? 'secondary' : 'ghost'}
            aria-pressed={viewMode === 'liste'}
            onClick={() => setViewMode('liste')}
          >
            <LayoutList className="size-4" aria-hidden="true" /> Liste
          </Button>
          <Button
            type="button" size="sm"
            variant={viewMode === 'kanban' ? 'secondary' : 'ghost'}
            aria-pressed={viewMode === 'kanban'}
            onClick={() => setViewMode('kanban')}
          >
            <LayoutGrid className="size-4" aria-hidden="true" /> Kanban
          </Button>
        </div>
      </div>

      {viewMode === 'kanban' ? (
        <FactureKanbanBoard factures={filtered} today={today} onOpenFacture={openEdit} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={ReceiptText}
          title={
            search ? `Aucun résultat pour « ${search} »`
              : activeTab !== 'toutes' ? 'Aucune facture dans cet onglet'
                : 'Aucune facture'
          }
          description={search || activeTab !== 'toutes' ? undefined : 'Créez votre première facture.'}
          action={!search && activeTab === 'toutes'
            ? <Button onClick={openNew}><Plus /> Nouvelle facture</Button> : undefined}
          className="mt-4"
        />
      ) : (
        <>
          {/* ── FG43/WR2b — barre d'actions en masse (visible dès une sélection) ── */}
          {selectedIds.length > 0 && (
            <div
              role="region"
              aria-label="Actions factures en masse"
              className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-nuit px-4 py-2.5 text-white shadow-ui-md"
            >
              <div className="text-sm">
                <strong className="tabular-nums">{selectedIds.length}</strong> facture{selectedIds.length > 1 ? 's' : ''} sélectionnée{selectedIds.length > 1 ? 's' : ''}
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {Object.entries(BULK_LABELS).map(([action, label]) => (
                  <button
                    key={action}
                    type="button" disabled={bulkBusy}
                    onClick={() => handleBulkAction(action)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-white/10 disabled:opacity-50"
                  >
                    {label}
                  </button>
                ))}
                <button
                  type="button" disabled={bulkBusy} onClick={clearSelection}
                  className="inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium text-white/70 transition-colors hover:text-white disabled:opacity-50"
                >
                  <X className="size-3.5" /> Désélectionner
                </button>
              </div>
            </div>
          )}
        <Card className="mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            {/* ── ARC53 — Tableau sur le frame `ui/datatable` (mode ligne custom).
                L'écran garde 100 % de son DOM : `table.data-table` avec
                `role="table"` (contrat `getByRole('table')`), son en-tête 8
                colonnes + case « tout sélectionner », `<FactureRow>` verbatim
                (boutons à état, menu « Actions », édition inline d'échéance,
                badges DGI), sa sélection propre (`selectedIds`) et sa barre de
                masse `role="region"` (rendue plus haut, hors table). Le PDF
                facture LEGACY est INTOUCHÉ (règle #4). Le moteur ne fait que
                dérouler le pipeline de lignes (seams manuels → ordre serveur,
                aucun tri/pagination/carte/outil intégré). `filtered.length > 0`
                est déjà garanti par la branche parente. ── */}
            <DataTable
              data={filtered}
              columns={FACTURE_DT_COLUMNS}
              getRowId={f => f.id}
              manualSorting
              manualFiltering
              manualPagination
              rowCount={filtered.length}
              pageSize={filtered.length}
              pageSizeOptions={[filtered.length]}
              searchable={false}
              hideToolbar
              hidePagination
              tableClassName="data-table calm-list"
              tableRole="table"
              aria-label="Factures"
              renderHeaderRow={() => (
                <>
                  <th className="w-10">
                    <Checkbox
                      checked={filtered.length > 0 && selectedIds.length === filtered.length}
                      onCheckedChange={(v) => setSelectedIds(v ? filtered.map(f => f.id) : [])}
                      aria-label="Tout sélectionner"
                    />
                  </th>
                  <th>Référence</th>
                  <th>Client</th>
                  <th>Émission</th>
                  <th>Échéance</th>
                  <th className="ta-right">Total TTC</th>
                  <th>Statut</th>
                  <th>Actions</th>
                </>
              )}
              renderRow={f => <FactureRow key={f.id} f={f} ctx={rowCtx} />}
            />
          </div>
        </Card>
        </>
      )}
    </div>
  )
}
