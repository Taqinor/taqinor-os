import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, CircleAlert, Upload } from 'lucide-react'
import stockApi from '../api/stockApi'
import { cn } from '../lib/cn'
import { Button } from '../ui'

/* NTP2P29 — Wizard d'onboarding fournisseur guidé (sur NTP2P7).

   Trois étapes :
     1. Identité légale — ICE / IF / RC / RIB, déjà portés par le Fournisseur
        (lecture : le wizard VÉRIFIE, il ne re-saisit pas le référentiel) ;
     2. Pièces requises — téléversement UNE PAR UNE, statut par document ;
     3. Récapitulatif + soumission pour validation.

   La barre de progression est calculée par le SERVEUR
   (`progression.progression_pct` = pièces requises reçues et non expirées).
   Le passage à l'étape 3 est BLOQUÉ tant que le dossier est incomplet — la
   même règle est appliquée côté serveur par `valider-dossier` (400), l'écran
   ne fait que l'annoncer plus tôt.

   Contextuelle : rendu dans un onglet de la fiche fournisseur 360, jamais une
   route autonome. */

const LIBELLES = {
  rc: 'Registre du commerce',
  attestation_fiscale: 'Attestation fiscale',
  attestation_cnss: 'Attestation CNSS',
  rib_certifie: 'RIB certifié',
  assurance: 'Assurance',
  autre: 'Autre pièce',
}

const ETAPES = ['Identité légale', 'Pièces requises', 'Récapitulatif']

function frErr(err, fallback) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  return fallback
}

export default function OnboardingFournisseurWizard({ fournisseur }) {
  const fournisseurId = fournisseur?.id
  const [etape, setEtape] = useState(0)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInputs = useRef({})

  const charger = useCallback(() => {
    if (!fournisseurId) return
    stockApi.getOnboardingFournisseur(fournisseurId).then(
      (r) => setData(r.data ?? null),
      (e) => setError(frErr(e, 'Dossier d’onboarding indisponible.')),
    )
  }, [fournisseurId])

  useEffect(() => { charger() }, [charger])

  const dossier = data?.dossier ?? null
  const progression = data?.progression ?? null
  const pct = progression?.progression_pct ?? 0
  const complet = !!progression?.complet
  const requis = progression?.requis ?? []
  const recus = progression?.recus ?? []
  const expires = progression?.expires ?? []

  const ouvrirDossier = async () => {
    setBusy(true)
    setError('')
    try {
      await stockApi.createDossierOnboarding({ fournisseur: fournisseurId })
      charger()
    } catch (e) {
      setError(frErr(e, 'Impossible d’ouvrir le dossier.'))
    } finally {
      setBusy(false)
    }
  }

  const televerser = async (typeDocument, fichier) => {
    if (!fichier || !dossier) return
    setBusy(true)
    setError('')
    try {
      const existant = (dossier.documents ?? []).find(
        (d) => d.type_document === typeDocument)
      let documentId = existant?.id
      if (!documentId) {
        const cree = await stockApi.createDocumentFournisseur({
          dossier: dossier.id, type_document: typeDocument,
        })
        documentId = cree.data?.id
      }
      const formData = new FormData()
      formData.append('file', fichier)
      await stockApi.televerserDocumentFournisseur(documentId, formData)
      charger()
    } catch (e) {
      setError(frErr(e, 'Téléversement impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const soumettre = async () => {
    setBusy(true)
    setError('')
    try {
      await stockApi.validerDossierOnboarding(dossier.id, { valider: true })
      charger()
    } catch (e) {
      setError(frErr(e, 'Validation impossible.'))
    } finally {
      setBusy(false)
    }
  }

  if (error && !data) {
    return (
      <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
        {error}
      </div>
    )
  }
  if (!data) return <p className="py-4 text-sm text-muted-foreground">Chargement…</p>

  if (!dossier) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-muted-foreground">
          Aucun dossier d&apos;entrée en relation n&apos;est ouvert pour ce
          fournisseur.
        </p>
        <Button type="button" onClick={ouvrirDossier} disabled={busy}>
          Ouvrir un dossier d&apos;onboarding
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4" data-testid="onboarding-wizard">
      {/* Barre de progression — pièces requises reçues et non expirées. */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium">
            Étape {etape + 1}/3 — {ETAPES[etape]}
          </span>
          <span data-testid="onboarding-progression" className="tabular-nums text-muted-foreground">
            {pct}% ({recus.length}/{requis.length} pièces)
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full rounded-full transition-all',
              complet ? 'bg-emerald-500' : 'bg-amber-500')}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {etape === 0 && (
        <dl className="grid grid-cols-2 gap-2 text-sm">
          {[
            ['ICE', fournisseur?.ice],
            ['Identifiant fiscal', fournisseur?.identifiant_fiscal],
            ['Registre du commerce', fournisseur?.rc],
            ['RIB', fournisseur?.rib],
          ].map(([label, valeur]) => (
            <div key={label} className="flex flex-col">
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className={valeur ? '' : 'italic text-muted-foreground'}>
                {valeur || 'non renseigné'}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {etape === 1 && (
        <ul className="flex flex-col gap-2">
          {requis.map((type) => {
            const recu = recus.includes(type)
            const expire = expires.includes(type)
            return (
              <li
                key={type}
                data-testid={`onboarding-piece-${type}`}
                className="flex items-center gap-2 rounded-lg border border-border p-2 text-sm"
              >
                {recu
                  ? <Check className="size-4 shrink-0 text-emerald-600" aria-hidden="true" />
                  : <CircleAlert className={cn('size-4 shrink-0', expire ? 'text-destructive' : 'text-muted-foreground')} aria-hidden="true" />}
                <span className="flex-1">{LIBELLES[type] ?? type}</span>
                <span className="text-xs text-muted-foreground">
                  {recu ? 'reçue' : expire ? 'expirée' : 'manquante'}
                </span>
                <input
                  type="file"
                  aria-label={`Téléverser ${LIBELLES[type] ?? type}`}
                  ref={(el) => { fileInputs.current[type] = el }}
                  className="hidden"
                  onChange={(e) => televerser(type, e.target.files?.[0])}
                />
                <Button
                  type="button" variant="outline" size="sm" disabled={busy}
                  onClick={() => fileInputs.current[type]?.click()}
                >
                  <Upload className="mr-1 size-3.5" aria-hidden="true" />
                  {recu ? 'Remplacer' : 'Téléverser'}
                </Button>
              </li>
            )
          })}
        </ul>
      )}

      {etape === 2 && (
        <div className="flex flex-col gap-2 text-sm">
          <p>
            Dossier <strong>{dossier.statut_display}</strong> — {recus.length} pièce·s
            reçue·s sur {requis.length}.
          </p>
          <Button type="button" onClick={soumettre} disabled={busy || !complet}>
            Soumettre pour validation
          </Button>
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <Button
          type="button" variant="outline" size="sm" disabled={etape === 0}
          onClick={() => setEtape((e) => Math.max(0, e - 1))}
        >
          Précédent
        </Button>
        <div className="flex flex-col items-end gap-1">
          <Button
            type="button" size="sm"
            data-testid="onboarding-suivant"
            // Le récapitulatif (étape 3) est BLOQUÉ tant que le dossier est
            // incomplet — même règle que le serveur, annoncée plus tôt.
            disabled={etape === 2 || (etape === 1 && !complet)}
            onClick={() => setEtape((e) => Math.min(2, e + 1))}
          >
            Suivant
          </Button>
          {etape === 1 && !complet && (
            <p className="text-xs text-muted-foreground">
              Récapitulatif accessible une fois toutes les pièces reçues.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
