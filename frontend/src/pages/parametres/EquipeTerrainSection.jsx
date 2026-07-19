// WIR112 — Équipes terrain canoniques (DC40) : CRUD depuis Paramètres.
//
// `installations.Equipe` est l'équipe terrain CANONIQUE (référencée par
// `Intervention.equipe_ref`, le roster FG169, le plan de charge FG299 et le
// planning camionnette FG303) mais n'avait aucun écran — contrairement à
// `crm.EquipeCommerciale` (Leads) et `gestion_projet.Equipe` (Projets), trois
// concepts DISJOINTS. Cet écran ajoute le CRUD manquant, à côté des Types
// d'intervention, sur le même gabarit que les Équipes commerciales (ZSAL3) :
// on regroupe des techniciens (utilisateurs), on désigne un chef optionnel, on
// archive sans supprimer. La liste des utilisateurs assignables est passée par
// le parent (déjà chargée pour l'onglet).
import { useEffect, useState } from 'react'
import { Plus, Trash2, Archive, ArchiveRestore } from 'lucide-react'
import {
  Card, CardContent, Input, Label, Badge, IconButton, Button, Spinner,
} from '../../ui'
import { SectionTitle, Field } from './peComponents'
import installationsApi from '../../api/installationsApi'

export default function EquipeTerrainSection({ assignables = [] }) {
  const [equipes, setEquipes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [newNom, setNewNom] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    installationsApi.getEquipesTerrain()
      .then((r) => setEquipes(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les équipes terrain.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const addEquipe = async () => {
    if (!newNom.trim()) return
    try {
      await installationsApi.saveEquipeTerrain(null, { nom: newNom.trim() })
      setNewNom('')
      load()
    } catch {
      setError("La création de l'équipe a échoué.")
    }
  }

  const renameEquipe = async (equipe, nom) => {
    if (!nom.trim() || nom === equipe.nom) return
    await installationsApi.saveEquipeTerrain(equipe.id, { nom: nom.trim() }).catch(() => {})
    load()
  }

  const setChef = async (equipe, chefId) => {
    setBusyId(equipe.id)
    try {
      await installationsApi.saveEquipeTerrain(equipe.id, { chef: chefId || null })
      load()
    } finally {
      setBusyId(null)
    }
  }

  const toggleMembre = async (equipe, userId) => {
    const membres = equipe.membres ?? []
    const next = membres.includes(userId)
      ? membres.filter((id) => id !== userId)
      : [...membres, userId]
    setBusyId(equipe.id)
    try {
      await installationsApi.saveEquipeTerrain(equipe.id, { membres: next })
      load()
    } finally {
      setBusyId(null)
    }
  }

  const archiveEquipe = async (equipe) => {
    await installationsApi.saveEquipeTerrain(equipe.id, { actif: !equipe.actif }).catch(() => {})
    load()
  }

  const delEquipe = async (equipe) => {
    if (!window.confirm(`Supprimer l'équipe terrain « ${equipe.nom} » ?`)) return
    await installationsApi.deleteEquipeTerrain(equipe.id).catch(() => {})
    load()
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Équipes terrain" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Regroupez des techniciens en équipes terrain assignables à une
          intervention. Distinct des équipes commerciales (Leads) et des
          équipes de projet. Archiver conserve l'historique.
        </p>

        {loading && (
          <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
            <Spinner className="size-3.5 text-primary" /> Chargement…
          </div>
        )}
        {error && <p className="form-error mb-2" role="alert">{error}</p>}

        {!loading && equipes.length === 0 && (
          <p className="mb-3 text-xs text-muted-foreground">Aucune équipe terrain configurée.</p>
        )}

        {!loading && equipes.map((eq) => (
          <div key={eq.id}
               className={['mb-3 rounded-lg border border-border p-3', eq.actif ? '' : 'opacity-50'].join(' ')}
               data-testid={`equipe-terrain-${eq.id}`}>
            <div className="mb-2 flex items-center gap-1.5">
              <Input key={eq.nom} className="flex-1" defaultValue={eq.nom}
                     onBlur={(e) => renameEquipe(eq, e.target.value)} />
              <Badge tone="neutral">{eq.nb_membres ?? 0} membre(s)</Badge>
              <IconButton size="md" variant="outline"
                          label={eq.actif ? 'Archiver' : 'Réactiver'}
                          disabled={busyId === eq.id}
                          onClick={() => archiveEquipe(eq)}>
                {eq.actif
                  ? <Archive className="size-4" aria-hidden="true" />
                  : <ArchiveRestore className="size-4" aria-hidden="true" />}
              </IconButton>
              <IconButton size="md" variant="outline" label="Supprimer l'équipe"
                          className="text-destructive hover:text-destructive"
                          disabled={busyId === eq.id}
                          onClick={() => delEquipe(eq)}>
                <Trash2 className="size-4" aria-hidden="true" />
              </IconButton>
            </div>
            <Field label="Chef d'équipe" htmlFor={`et-chef-${eq.id}`}>
              <select id={`et-chef-${eq.id}`} className="form-control"
                      value={eq.chef ?? ''}
                      disabled={busyId === eq.id}
                      onChange={(e) => setChef(eq, e.target.value ? Number(e.target.value) : null)}>
                <option value="">— Aucun —</option>
                {assignables.map((u) => (
                  <option key={u.id} value={u.id}>{u.username}</option>
                ))}
              </select>
            </Field>
            <Label className="mb-1 mt-2 block">Membres</Label>
            <div className="flex flex-wrap gap-1.5">
              {assignables.map((u) => {
                const active = (eq.membres ?? []).includes(u.id)
                return (
                  <button key={u.id} type="button"
                          disabled={busyId === eq.id}
                          onClick={() => toggleMembre(eq, u.id)}
                          className={[
                            'rounded-full border px-2.5 py-1 text-xs transition-colors',
                            active
                              ? 'border-primary bg-primary/10 text-primary'
                              : 'border-border text-muted-foreground hover:bg-muted/40',
                          ].join(' ')}>
                    {u.username}
                  </button>
                )
              })}
            </div>
          </div>
        ))}

        <div className="mt-1.5 flex gap-1.5">
          <Input className="flex-1" placeholder="Nouvelle équipe terrain" value={newNom}
                 onChange={(e) => setNewNom(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addEquipe() } }} />
          <Button type="button" onClick={addEquipe}><Plus className="size-4" aria-hidden="true" /></Button>
        </div>
      </CardContent>
    </Card>
  )
}
