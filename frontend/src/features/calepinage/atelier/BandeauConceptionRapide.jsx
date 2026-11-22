import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'

/* ACAL1007 — un calepinage `rapide` (ouvert depuis un devis automatique, jamais dessiné : ACAL1006)
   le DIT au-dessus du plan, avec le motif SERVI par le détail (contrat calepinage_detail.json).
   « J'ai vérifié le toit » appelle l'enregistrement EXISTANT de l'atelier ; c'est le serveur qui
   passe l'état à `complet` : le bandeau relit le détail à chaque enregistrement (`rechargerLe`)
   et disparaît quand l'état servi n'est plus `rapide`. Un calepinage `complet` n'affiche rien. */
export default function BandeauConceptionRapide({ calepinageId, onVerifier, rechargerLe }) {
  const [motif, setMotif] = useState(undefined) // undefined = rien à dire
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve().then(() => calepinageApi.calepinages.get(calepinageId)).then((rep) => {
      const d = rep?.data
      if (!annule) setMotif(d?.etat_conception === 'rapide' ? (d.etat_conception_motif || null) : undefined)
    }).catch(() => { if (!annule) setMotif(undefined) })
    return () => { annule = true }
  }, [calepinageId, rechargerLe])

  if (motif === undefined) return null
  const verifier = async () => {
    setEnCours(true)
    try { await onVerifier?.() } finally { setEnCours(false) }
  }
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted p-4"
      role="status" data-testid="cal-conception-rapide">
      <p className="text-sm text-foreground">
        Conception rapide — à vérifier sur place{motif ? ` (${motif})` : ''}
      </p>
      {onVerifier && (
        <button type="button" onClick={verifier} disabled={enCours}
          className="min-h-[44px] rounded-md border border-border px-4 text-sm text-foreground"
          data-testid="cal-conception-rapide-verifier">
          J’ai vérifié le toit
        </button>
      )}
    </div>
  )
}
