// NTMOB25 — Accueil mobile rôle « Technicien responsable » :
// `/mobile/equipe-terrain`, distinct de « Ma journée » (F22, individuelle).
// Vue d'ÉQUIPE compacte : les interventions du jour de TOUS ses subordonnés
// directs (`CustomUser.supervisor`, déjà existant), les conflits d'affectation
// du jour (`installations/interventions/conflits-affectation/`, FG300 déjà
// construit) et la réaffectation d'une intervention à un collègue disponible.
// LECTURE + RÉAFFECTATION seulement : aucune nouvelle règle métier de planning,
// aucun nouvel endpoint, aucun nouveau modèle.
import { useCallback, useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { AlertTriangle, HardHat, Users } from 'lucide-react'
import installationsApi from '../../../api/installationsApi'
// L'annuaire de la société est DÉJÀ exposé par `coreApi.utilisateurs.list`
// (PACT120, `GET /users/`) — aucun nouvel endpoint.
import coreApi from '../../../api/coreApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import OnboardingTerrain from '../OnboardingTerrain'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function EquipeTerrainHome() {
  const isMobile = useIsMobile()
  const navigate = useNavigate()
  const moi = useSelector((s) => s.auth?.user?.id)
  const [equipe, setEquipe] = useState(null)
  const [interventions, setInterventions] = useState(null)
  const [conflits, setConflits] = useState([])
  const [busyId, setBusyId] = useState(null)

  const charger = useCallback(() => {
    const jour = todayIso()
    coreApi.utilisateurs.list()
      .then((r) => {
        const list = r.data?.results ?? r.data ?? []
        // Subordonnés DIRECTS uniquement (le sous-arbre complet est une autre
        // notion, portée par la visibilité des enregistrements — pas ici).
        setEquipe(list.filter((u) => u.supervisor === moi))
      })
      .catch(() => setEquipe([]))
    installationsApi.getInterventions({ date_prevue: jour })
      .then((r) => setInterventions(r.data?.results ?? r.data ?? []))
      .catch(() => setInterventions([]))
    installationsApi.getConflitsAffectation({ debut: jour, fin: jour })
      .then((r) => setConflits(r.data?.conflits ?? r.data?.results ?? []))
      .catch(() => setConflits([]))
  }, [moi])

  useEffect(() => {
    if (!isMobile || !moi) return
    charger()
  }, [isMobile, moi, charger])

  if (!isMobile) return <Navigate to="/dashboard" replace />

  const membreIds = new Set((equipe ?? []).map((u) => u.id))
  const duJour = (interventions ?? []).filter((iv) => membreIds.has(iv.technicien))
  const nomMembre = (id) => (equipe ?? []).find((u) => u.id === id)?.username || '—'

  const reaffecter = async (intervention, technicienId) => {
    setBusyId(intervention.id)
    try {
      await installationsApi.updateIntervention(
        intervention.id, { technicien: Number(technicienId) })
      charger()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="flex flex-col gap-3 p-3 pb-24">
      {/* NTMOB33 — aide contextuelle premiere utilisation terrain. */}
      <OnboardingTerrain userId={moi} />

      {conflits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-warning" aria-hidden="true" />
              Conflits d'affectation
            </CardTitle>
            <CardDescription>Double-réservation détectée aujourd'hui</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col divide-y divide-border text-sm">
              {conflits.map((c, i) => (
                <li key={c.id ?? `conflit-${i}`} className="py-2">
                  {c.libelle || c.message
                    || `${nomMembre(c.technicien)} — ${c.date || todayIso()}`}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-4 text-muted-foreground" aria-hidden="true" />
                Interventions de mon équipe
              </CardTitle>
              <CardDescription>Aujourd'hui, tous techniciens</CardDescription>
            </div>
            {duJour.length > 0 && <Badge tone="neutral">{duJour.length}</Badge>}
          </div>
        </CardHeader>
        <CardContent>
          {equipe === null || interventions === null
            ? <Spinner />
            : duJour.length === 0
              ? (
                <EmptyState
                  icon={HardHat}
                  title="Aucune intervention d'équipe aujourd'hui" />
              )
              : (
                <ul className="flex flex-col divide-y divide-border">
                  {duJour.map((iv) => (
                    <li key={iv.id} className="flex flex-col gap-1.5 py-2">
                      {/* Il n'existe pas de route de DÉTAIL d'intervention :
                          la liste `/interventions` est l'écran source. */}
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => navigate('/interventions')}
                      >
                        <span className="block truncate font-medium">
                          {iv.client_nom || iv.installation_reference || `Intervention #${iv.id}`}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {nomMembre(iv.technicien)}
                          {iv.site_ville ? ` — ${iv.site_ville}` : ''}
                        </span>
                      </button>
                      <Select
                        value={String(iv.technicien ?? '')}
                        disabled={busyId === iv.id}
                        onValueChange={(v) => reaffecter(iv, v)}
                      >
                        <SelectTrigger
                          className="h-9"
                          aria-label={`Réaffecter l'intervention ${iv.id}`}
                        >
                          <SelectValue placeholder="Réaffecter à…" />
                        </SelectTrigger>
                        <SelectContent>
                          {(equipe ?? []).map((u) => (
                            <SelectItem key={u.id} value={String(u.id)}>
                              {u.username}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </li>
                  ))}
                </ul>
              )}
        </CardContent>
      </Card>
    </div>
  )
}
