import { useEffect, useMemo, useState } from 'react'
import { Building2, Target, Users } from 'lucide-react'
import {
  Card, EmptyState, Input, Label, Spinner, Stat, toast,
} from '../../ui'
import rhApi from '../../api/rhApi'

/* ============================================================================
   NTHCM9 — Tableau de bord OKR (mes OKR / mon équipe / entreprise).
   ----------------------------------------------------------------------------
   Consomme `GET /rh/okr-individuels/tableau-de-bord/`
   (selectors.tableau_okr_employe).

   TROIS PORTÉES DISTINCTES, JAMAIS MÉLANGÉES — c'est tout le propos de
   l'écran : mes OKR, ceux de mon équipe (subordonnés DIRECTS, NTHCM1), et le
   rollup d'entreprise. Le dossier est résolu SERVEUR depuis le compte
   appelant : aucun identifiant d'employé ne transite par l'URL, sinon
   n'importe qui lirait les OKR d'un autre.

   `progression_okr_pct` à `null` n'est PAS 0 % : « aucun contributeur » et
   « tout le monde à zéro » sont deux situations opposées, l'écran les
   distingue explicitement au lieu d'afficher une barre vide dans les deux cas.
   ========================================================================== */

function Progression({ valeur }) {
  const connue = valeur !== null && valeur !== undefined && valeur !== ''
  const pourcentage = connue ? Math.max(0, Math.min(100, Number(valeur))) : 0
  return (
    <span className="flex items-center gap-2">
      <span className="h-2 w-24 overflow-hidden rounded bg-muted">
        {connue && (
          <span
            className="block h-full rounded bg-primary"
            style={{ width: `${pourcentage}%` }}
          />
        )}
      </span>
      <span className="w-20 shrink-0 text-xs tabular-nums text-muted-foreground">
        {connue ? `${valeur} %` : 'non mesuré'}
      </span>
    </span>
  )
}

function ListeOkr({ okrs, vide }) {
  if (!okrs.length) {
    return <p className="text-sm text-muted-foreground">{vide}</p>
  }
  return (
    <ul className="flex flex-col gap-2">
      {okrs.map((okr) => (
        <li
          key={okr.id}
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2"
        >
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {okr.titre}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {okr.employe}
              {okr.periode ? ` — ${okr.periode}` : ''}
            </span>
          </span>
          <Progression valeur={okr.progression_pct} />
        </li>
      ))}
    </ul>
  )
}

export default function OkrDashboard() {
  const [periode, setPeriode] = useState('')
  const [etat, setEtat] = useState({ data: null, loading: true, error: null })
  const { data, loading, error } = etat

  useEffect(() => {
    let vivant = true
    rhApi.getTableauBordOkr(periode ? { periode } : undefined)
      .then((res) => {
        if (vivant) setEtat({ data: res.data, loading: false, error: null })
      })
      .catch(() => {
        if (!vivant) return
        setEtat({
          data: null,
          loading: false,
          error: 'Impossible de charger le tableau de bord OKR.',
        })
        toast.error('Impossible de charger le tableau de bord OKR.')
      })
    return () => { vivant = false }
  }, [periode])

  const entreprise = useMemo(() => data?.entreprise ?? [], [data])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Mes OKR</h2>
      </div>

      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <div className="flex flex-col gap-1.5 sm:w-64">
          <Label htmlFor="okr-periode">Période</Label>
          <Input
            id="okr-periode"
            value={periode}
            onChange={(e) => setPeriode(e.target.value)}
            placeholder="Ex. T1-2027 (vide = toutes)"
          />
        </div>
        <div className="sm:ml-auto flex items-end gap-3">
          <Stat
            label="Mes OKR"
            value={data ? String(data.mes_okr.length) : '—'}
            icon={Target}
          />
          <Stat
            label="OKR de l’équipe"
            value={data ? String(data.equipe.length) : '—'}
            hint={data?.est_manager ? 'Rapports directs' : 'Aucune équipe'}
            icon={Users}
          />
        </div>
      </Card>

      {loading && (
        <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement des OKR…
        </Card>
      )}
      {!loading && error && (
        <Card className="p-4 text-sm text-destructive">{error}</Card>
      )}

      {!loading && !error && data && (
        <>
          <Card className="flex flex-col gap-3 p-4">
            <h3 className="text-sm font-medium">Mes OKR</h3>
            <ListeOkr
              okrs={data.mes_okr}
              vide="Aucun OKR ne vous est rattaché sur cette période."
            />
          </Card>

          <Card className="flex flex-col gap-3 p-4">
            <h3 className="text-sm font-medium">OKR de mon équipe</h3>
            <ListeOkr
              okrs={data.equipe}
              vide="Aucun rapport direct ne porte d’OKR sur cette période."
            />
          </Card>

          <Card className="flex flex-col gap-3 p-4">
            <h3 className="text-sm font-medium">
              Objectifs d’entreprise (rollup)
            </h3>
            {entreprise.length === 0 ? (
              <EmptyState
                icon={Building2}
                title="Aucun objectif d’entreprise"
                description="Aucun objectif n’est défini sur cette période."
              />
            ) : (
              <ul className="flex flex-col gap-2">
                {entreprise.map((objectif) => (
                  <li
                    key={objectif.objectif_id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {objectif.titre}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {objectif.nombre_contributeurs} contributeur
                        {objectif.nombre_contributeurs > 1 ? 's' : ''}
                        {' · '}
                        {objectif.nombre_okr_rattaches} OKR rattaché
                        {objectif.nombre_okr_rattaches > 1 ? 's' : ''}
                      </span>
                    </span>
                    <Progression valeur={objectif.progression_okr_pct} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
