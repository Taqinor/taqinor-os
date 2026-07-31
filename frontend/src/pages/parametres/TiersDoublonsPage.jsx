import { useEffect, useState } from 'react'
import { Badge } from '../../ui'
import tiersApi from '../../api/tiersApi'

/* ============================================================================
   WIR152 — Écran admin « Doublons tiers » (`/parametres/tiers-doublons`).
   ----------------------------------------------------------------------------
   `TiersViewSet.doublons` (ARC20, `selectors.find_duplicates` — clusters
   même ICE/email sur plusieurs fiches Tiers, admin-only, LECTURE SEULE,
   aucune fusion) n'avait aucun consommateur. Affiche les clusters tels
   quels — aucune action de fusion/écriture ici (le backend ne l'expose pas).
   ========================================================================== */

const ROLE_LABEL = {
  client: 'Client', fournisseur: 'Fournisseur',
  partenaire: 'Partenaire', soustraitant: 'Sous-traitant',
}
const CLE_LABEL = { ice: 'ICE', email: 'Email' }

export default function TiersDoublonsPage() {
  const [clusters, setClusters] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    tiersApi.doublons()
      .then((r) => setClusters(Array.isArray(r?.data?.clusters) ? r.data.clusters : []))
      .catch(() => setError('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="font-display text-xl font-semibold">Doublons tiers</h1>
        <p className="text-sm text-muted-foreground">
          Fiches du répertoire partageant le même ICE ou le même email — lecture seule, aucune fusion automatique.
        </p>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {!loading && !error && clusters.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun doublon détecté pour l’instant.</p>
      )}

      {!loading && !error && clusters.length > 0 && (
        <ul className="flex flex-col gap-3" data-testid="doublons-clusters">
          {clusters.map((c, idx) => (
            <li key={`${c.cle}-${c.valeur}-${idx}`} className="rounded-lg border border-border bg-card p-3">
              <div className="mb-2 flex items-center gap-2 text-sm">
                <Badge tone="warning">{CLE_LABEL[c.cle] || c.cle}</Badge>
                <span className="font-medium">{c.valeur}</span>
              </div>
              <ul className="flex flex-col gap-1">
                {(c.tiers || []).map((t) => (
                  <li key={t.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span>{t.nom}</span>
                    {Object.entries(t.roles || {})
                      .filter(([, v]) => v)
                      .map(([role]) => (
                        <Badge key={role} tone="neutral">{ROLE_LABEL[role] || role}</Badge>
                      ))}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
