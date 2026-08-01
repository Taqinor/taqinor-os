import { useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, Banknote, FileText, Paperclip, Phone, UserRound } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { Badge, Button, Card, Checkbox, EmptyState, Skeleton, toast } from '../../../ui'
import { formatDate, formatMAD } from '../../../lib/format'
import { StatutPiece } from '../statusAo'

/* ============================================================================
   AOF182 — Écran administratif : cautions, pièces datées, vérifications.
   ----------------------------------------------------------------------------
   AOF16 complète `CautionSoumission` et AOF136/AOF137 livrent la checklist et
   les pièces datées. Sans écran, la caution bancaire et les attestations
   restent suivies par téléphone — c'est-à-dire exactement l'état d'avant, où
   l'on découvre la veille du dépôt qu'une attestation expire l'avant-veille.

   **LA DATE DE RÉFÉRENCE EST L'OUVERTURE DES PLIS, pas aujourd'hui.** Une
   attestation « encore valable » aujourd'hui mais expirée le jour de la remise
   est un dossier rejeté : toute validité est confrontée à la date de remise
   des plis, et l'écart s'affiche EN ROUGE AVEC SA DATE (jamais un simple
   « expiré » sans le jour).

   **Une case obligatoire ouverte bloque VISIBLEMENT le dépôt** : le bandeau
   nomme la vérification manquante et le bouton de dépôt porte son motif ÉCRIT
   (même règle produit qu'AOF176 — jamais un bouton grisé sans explication).

   **Chaque ligne trace son responsable.** Une ligne sans responsable désigné
   n'est pas neutre : elle est signalée, parce qu'une vérification téléphonique
   sans nom n'est faite par personne.

   Aucune ressource n'est inventée : la lecture passe par `aoApi.affaires.get`
   (AOF11, `api/aoApi.js` n'est jamais retouché ici) et les écritures sont
   INJECTÉES (`onCocherVerification`) — sans injection, la case est en lecture
   seule plutôt que branchée sur un endpoint imaginaire.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

// Libellés de repli des vérifications téléphoniques réellement faites avant un
// dépôt — jamais une liste FERMÉE : un code inconnu s'affiche tel quel.
export const VERIFICATIONS_LABELS = {
  prorogation_ecrite: 'Prorogation écrite obtenue',
  attestation_visite: 'Attestation de visite de site',
  plis_separes: 'Plis séparés ou pli unique — confirmé par téléphone',
}

export const TYPES_CAUTION = [
  ['provisoire', 'Caution provisoire (soumission)'],
  ['definitive', 'Caution définitive'],
]

/** `true` si `dateValidite` s'achève AVANT `dateReference` (ouverture des
    plis). Comparaison de JOURS calendaires, jamais d'heures. `false` dès
    qu'une des deux dates manque : on ne signale pas ce qu'on ne sait pas. */
export function expireAvant(dateValidite, dateReference) {
  if (!dateValidite || !dateReference) return false
  const a = new Date(dateValidite)
  const b = new Date(dateReference)
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return false
  const jour = (d) => Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())
  return jour(a) < jour(b)
}

/** Les vérifications OBLIGATOIRES encore ouvertes. */
export function verificationsOuvertes(verifications) {
  return (verifications || []).filter((v) => v.obligatoire && !v.fait)
}

/** Motif AFFICHABLE du blocage du dépôt, `null` si rien ne bloque. */
export function motifBlocageDepot(verifications) {
  const premiere = verificationsOuvertes(verifications)[0]
  if (!premiere) return null
  return premiere.libelle || VERIFICATIONS_LABELS[premiere.code] || premiere.code || 'vérification obligatoire'
}

/** Cautions ET pièces dont la validité s'achève avant l'ouverture des plis. */
export function elementsExpires({ cautions = [], pieces = [], dateOuverture }) {
  return [
    ...cautions
      .filter((c) => expireAvant(c.date_validite, dateOuverture))
      .map((c) => ({
        cle: `caution-${c.id}`,
        libelle: c.libelle || TYPES_CAUTION.find(([t]) => t === c.type)?.[1] || c.type,
        date: c.date_validite,
      })),
    ...pieces
      .filter((p) => expireAvant(p.valide_jusqu_au, dateOuverture))
      .map((p) => ({
        cle: `piece-${p.id}`,
        libelle: p.libelle || p.code,
        date: p.valide_jusqu_au,
      })),
  ]
}

function Responsable({ nom }) {
  if (!nom) {
    return (
      <Badge tone="warning">
        <UserRound className="size-3" aria-hidden="true" />
        Responsable non désigné
      </Badge>
    )
  }
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <UserRound className="size-3" aria-hidden="true" />
      {nom}
    </span>
  )
}

function DateValidite({ date, dateOuverture, prefixe }) {
  if (!date) return <span className="text-xs text-muted-foreground">{prefixe} —</span>
  const expiree = expireAvant(date, dateOuverture)
  return (
    <span className={`text-xs ${expiree ? 'font-medium text-destructive' : 'text-muted-foreground'}`}>
      {prefixe} {formatDate(date)}
      {expiree && ' — expire AVANT l’ouverture des plis'}
    </span>
  )
}

function CautionCard({ type, libelle, caution, dateOuverture, onOuvrirPiece }) {
  if (!caution) {
    return (
      <Card className="flex flex-col gap-1 border-warning/50 bg-warning/5 p-3">
        <p className="text-sm font-medium">{libelle}</p>
        <p className="text-xs text-warning">Non constituée — aucune caution enregistrée à ce jour.</p>
      </Card>
    )
  }
  const expiree = expireAvant(caution.date_validite, dateOuverture)
  return (
    <Card
      data-ao-piece={`caution-${type}`}
      className={`flex flex-col gap-1.5 p-3 ${expiree ? 'border-destructive/60 bg-destructive/5' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Banknote className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-medium">{caution.libelle || libelle}</span>
        {caution.statut && <StatutPiece status={caution.statut} data-ao-etat={caution.statut} />}
      </div>
      <p className="text-sm tabular-nums">
        {caution.montant != null ? formatMAD(caution.montant) : '—'}
        {caution.banque ? ` · ${caution.banque}` : ''}
        {caution.reference ? ` · réf. ${caution.reference}` : ''}
      </p>
      <DateValidite date={caution.date_validite} dateOuverture={dateOuverture} prefixe="Valable jusqu’au" />
      <div className="flex flex-wrap items-center gap-2">
        {caution.piece_jointe ? (
          onOuvrirPiece ? (
            <Button size="sm" variant="link" className="h-auto p-0" onClick={() => onOuvrirPiece(caution.piece_jointe)}>
              <Paperclip className="size-3.5" aria-hidden="true" />
              {caution.piece_jointe.nom || 'Pièce jointe'}
            </Button>
          ) : (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Paperclip className="size-3" aria-hidden="true" />
              {caution.piece_jointe.nom || 'Pièce jointe'}
            </span>
          )
        ) : (
          <Badge tone="warning">Aucune pièce jointe</Badge>
        )}
        <Responsable nom={caution.responsable} />
      </div>
    </Card>
  )
}

function PiecesTable({ pieces, dateOuverture }) {
  if (!pieces.length) {
    return (
      <EmptyState
        icon={FileText}
        title="Aucune pièce administrative"
        description="Attestations fiscale, CNSS, RC, assurance… aucune n’est encore suivie sur cette affaire."
      />
    )
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] text-left">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b border-border">
            <th scope="col" className="px-2 py-2 font-medium">Pièce</th>
            <th scope="col" className="px-2 py-2 font-medium">Délivrée le</th>
            <th scope="col" className="px-2 py-2 font-medium">Valable jusqu’au</th>
            <th scope="col" className="px-2 py-2 font-medium">Responsable</th>
            <th scope="col" className="px-2 py-2 font-medium">État</th>
          </tr>
        </thead>
        <tbody>
          {pieces.map((p) => {
            const expiree = expireAvant(p.valide_jusqu_au, dateOuverture)
            return (
              <tr
                key={p.id ?? p.code}
                data-ao-piece={p.code || String(p.id)}
                className={`border-b border-border last:border-b-0 ${expiree ? 'bg-destructive/5' : ''}`}
              >
                <td className="px-2 py-2 text-sm font-medium">
                  {p.libelle || p.code}
                  {p.obligatoire && <Badge tone="danger" className="ml-2">Obligatoire</Badge>}
                </td>
                <td className="px-2 py-2 text-xs text-muted-foreground">
                  {p.date_delivrance ? formatDate(p.date_delivrance) : '—'}
                </td>
                <td className={`px-2 py-2 text-xs ${expiree ? 'font-medium text-destructive' : 'text-muted-foreground'}`}>
                  {p.valide_jusqu_au ? formatDate(p.valide_jusqu_au) : '—'}
                  {expiree && ' — expire AVANT l’ouverture des plis'}
                </td>
                <td className="px-2 py-2"><Responsable nom={p.responsable} /></td>
                <td className="px-2 py-2">
                  {p.statut
                    ? <StatutPiece status={p.statut} data-ao-etat={p.statut} />
                    : <Badge tone="neutral">—</Badge>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Verifications({ verifications, onCocher, occupe }) {
  if (!verifications.length) {
    return (
      <EmptyState
        icon={Phone}
        title="Aucune vérification listée"
        description="Prorogation écrite, attestation de visite, plis séparés ou pli unique… rien n’est encore suivi."
      />
    )
  }
  return (
    <ul className="flex flex-col gap-2">
      {verifications.map((v) => {
        const libelle = v.libelle || VERIFICATIONS_LABELS[v.code] || v.code
        const ouverte = v.obligatoire && !v.fait
        return (
          <li
            key={v.id ?? v.code}
            className={`flex flex-wrap items-center gap-2 rounded-lg border p-2.5 ${
              ouverte ? 'border-destructive/50 bg-destructive/5' : 'border-border'
            }`}
          >
            <Checkbox
              checked={Boolean(v.fait)}
              disabled={!onCocher || occupe}
              aria-label={libelle}
              onCheckedChange={(val) => onCocher?.(v, val === true)}
            />
            <span className={`text-sm ${ouverte ? 'font-medium text-destructive' : ''}`}>{libelle}</span>
            {v.obligatoire && <Badge tone={v.fait ? 'success' : 'danger'}>Obligatoire</Badge>}
            <span className="ml-auto"><Responsable nom={v.responsable} /></span>
          </li>
        )
      })}
    </ul>
  )
}

export default function AdministratifPage({
  affaireId,
  onCocherVerification,
  onOuvrirPiece,
  onDeposer,
}) {
  const routeParams = useParams()
  const id = affaireId ?? routeParams.id
  const [occupe, setOccupe] = useState(false)

  const { data: affaire, loading, error, refetch } = useResource(
    () => aoApi.affaires.get(id), id,
    { errorMessage: 'Impossible de charger le volet administratif.' },
  )

  const dateOuverture = affaire?.date_ouverture_plis || affaire?.date_remise_plis || null
  const cautions = useMemo(() => affaire?.cautions ?? [], [affaire])
  const pieces = useMemo(() => affaire?.pieces_administratives ?? [], [affaire])
  const verifications = useMemo(() => affaire?.verifications_avant_depot ?? [], [affaire])

  const motif = useMemo(() => motifBlocageDepot(verifications), [verifications])
  const expires = useMemo(
    () => elementsExpires({ cautions, pieces, dateOuverture }),
    [cautions, pieces, dateOuverture],
  )

  const cocher = useCallback(async (verification, fait) => {
    if (!onCocherVerification) return
    setOccupe(true)
    try {
      await onCocherVerification(verification, fait)
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Vérification non enregistrée.'))
    } finally {
      setOccupe(false)
    }
  }, [onCocherVerification, refetch])

  if (loading && !affaire) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-56 w-full" /></div>
  }
  if (error || !affaire) {
    return (
      <EmptyState
        icon={FileText}
        title="Volet administratif indisponible"
        description={error || "Cette affaire n'est pas accessible."}
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">Administratif</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Cautions, pièces datées et vérifications avant dépôt — validité appréciée
          {dateOuverture ? ` à l’ouverture des plis du ${formatDate(dateOuverture)}` : ' à la date de remise des plis'}.
        </p>
      </div>

      {expires.length > 0 && (
        <Card className="flex items-start gap-2 border-destructive/60 bg-destructive/5 p-3" role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
          <div>
            <p className="text-sm font-medium text-destructive">
              Validité insuffisante à l’ouverture des plis
            </p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {expires.map((e) => (
                <li key={e.cle} className="text-xs text-destructive">
                  {e.libelle} — expire le {formatDate(e.date)}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {TYPES_CAUTION.map(([type, libelle]) => (
          <CautionCard
            key={type}
            type={type}
            libelle={libelle}
            caution={cautions.find((c) => c.type === type) ?? null}
            dateOuverture={dateOuverture}
            onOuvrirPiece={onOuvrirPiece}
          />
        ))}
      </div>

      <Card className="p-0">
        <h2 className="px-3 py-2 font-display text-base font-semibold">Pièces administratives</h2>
        <PiecesTable pieces={pieces} dateOuverture={dateOuverture} />
      </Card>

      <Card className="flex flex-col gap-2 p-4">
        <div>
          <h2 className="font-display text-base font-semibold">Vérifications avant dépôt</h2>
          <p className="text-xs text-muted-foreground">
            Les points qui se règlent au téléphone et qui font perdre un dossier quand personne
            ne les porte.
          </p>
        </div>
        <Verifications verifications={verifications} onCocher={cocher} occupe={occupe} />
        {!onCocherVerification && verifications.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Consultation seule — la saisie se fait depuis le dossier de soumission.
          </p>
        )}
      </Card>

      {/* La porte de dépôt. Le blocage est visible MÊME quand aucune action de
          dépôt n'est branchée sur cet écran — c'est le point de la tâche. */}
      {motif && (
        <Card className="flex items-start gap-2 border-destructive/60 bg-destructive/5 p-3" role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
          <p className="text-sm font-medium text-destructive">Dépôt bloqué — {motif}</p>
        </Card>
      )}
      {onDeposer && (
        <Button
          className="self-start"
          disabled={Boolean(motif)}
          title={motif || undefined}
          onClick={onDeposer}
        >
          {motif ? `Dépôt bloqué — ${motif}` : 'Déposer le pli'}
        </Button>
      )}
    </div>
  )
}
