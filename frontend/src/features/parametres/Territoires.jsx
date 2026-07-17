// NTCRM3 — Écran Paramètres → Territoires.
//
// Liste les territoires (moteur NTCRM1/NTCRM2), un formulaire créer/éditer
// (nom, type, critère simple ville/type_installation/tranche CA), la gestion
// des membres + quotas, et un aperçu « simuler cette adresse/ce type » qui
// appelle `territoires/{id}/resoudre/` sans rien muter. Réservé Administrateur/
// Directeur (le backend applique déjà le RBAC ; ce composant ne le redéfinit
// pas côté client).
import { useCallback, useEffect, useState } from 'react'
import api from '../../api/axios'
import {
  Button, Input, Spinner, EmptyState, Card,
} from '../../ui'
import { toast } from '../../ui/confirm'

const TYPES = [
  { value: 'geo', label: 'Géographique' },
  { value: 'segment', label: 'Segment' },
  { value: 'secteur', label: 'Secteur' },
]

function conditionFromCriteres({ ville, type_installation: typeInstallation, montantMin }) {
  const conditions = []
  if (ville) conditions.push({ field: 'ville', operator: 'eq', value: ville })
  if (typeInstallation) {
    conditions.push({ field: 'type_installation', operator: 'eq', value: typeInstallation })
  }
  if (montantMin) {
    conditions.push({ field: 'montant_estime', operator: 'gte', value: Number(montantMin) })
  }
  if (conditions.length === 0) return null
  if (conditions.length === 1) return conditions[0]
  return { op: 'and', conditions }
}

export default function Territoires() {
  const [territoires, setTerritoires] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({
    nom: '', type_territoire: 'geo', ville: '', type_installation: '', montantMin: '',
  })
  const [saving, setSaving] = useState(false)
  const [simulation, setSimulation] = useState({ territoireId: '', ville: '', type_installation: '' })
  const [simResult, setSimResult] = useState(null)
  const [simLoading, setSimLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api.get('/territoires/territoires/')
      .then((res) => setTerritoires(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error("Impossible de charger les territoires."))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!form.nom.trim()) {
      toast.error('Le nom du territoire est requis.')
      return
    }
    setSaving(true)
    try {
      const territoire = await api.post('/territoires/territoires/', {
        nom: form.nom.trim(),
        type_territoire: form.type_territoire,
      })
      const condition = conditionFromCriteres(form)
      if (condition) {
        await api.post('/territoires/regles/', {
          territoire: territoire.data.id, ordre: 1, condition, actif: true,
        })
      }
      toast.success('Territoire créé.')
      setForm({ nom: '', type_territoire: 'geo', ville: '', type_installation: '', montantMin: '' })
      load()
    } catch {
      toast.error("Échec de la création du territoire.")
    } finally {
      setSaving(false)
    }
  }

  const handleAddMembre = async (territoireId, utilisateurId, quotaPct) => {
    if (!utilisateurId) return
    try {
      await api.post('/territoires/membres/', {
        territoire: territoireId,
        utilisateur: utilisateurId,
        quota_pct: quotaPct || null,
      })
      toast.success('Membre ajouté.')
      load()
    } catch {
      toast.error("Échec de l'ajout du membre.")
    }
  }

  const handleSimuler = async () => {
    if (!simulation.territoireId) {
      toast.error('Choisissez un territoire à simuler.')
      return
    }
    setSimLoading(true)
    setSimResult(null)
    try {
      const res = await api.get(
        `/territoires/territoires/${simulation.territoireId}/resoudre/`,
        { params: { ville: simulation.ville, type_installation: simulation.type_installation } },
      )
      setSimResult(res.data)
    } catch {
      toast.error('Échec de la simulation.')
    } finally {
      setSimLoading(false)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="space-y-6" data-testid="territoires-screen">
      <div>
        <h2 className="text-lg font-semibold">Territoires</h2>
        <p className="text-sm text-muted-foreground">
          Règles d'affectation automatique des leads entrants par zone/segment/secteur.
        </p>
      </div>

      <Card className="p-4 space-y-3">
        <h3 className="font-medium">Nouveau territoire</h3>
        <form onSubmit={handleCreate} className="grid grid-cols-2 gap-3">
          <Input
            placeholder="Nom (ex. Sud — résidentiel)"
            value={form.nom}
            onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
          />
          <select
            className="form-select"
            value={form.type_territoire}
            onChange={(e) => setForm((f) => ({ ...f, type_territoire: e.target.value }))}
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <Input
            placeholder="Ville (critère géo)"
            value={form.ville}
            onChange={(e) => setForm((f) => ({ ...f, ville: e.target.value }))}
          />
          <Input
            placeholder="Type d'installation (résidentiel/…)"
            value={form.type_installation}
            onChange={(e) => setForm((f) => ({ ...f, type_installation: e.target.value }))}
          />
          <Input
            placeholder="Montant estimé minimum (tranche CA)"
            type="number"
            value={form.montantMin}
            onChange={(e) => setForm((f) => ({ ...f, montantMin: e.target.value }))}
          />
          <Button type="submit" disabled={saving}>
            {saving ? 'Création…' : 'Créer le territoire'}
          </Button>
        </form>
      </Card>

      <Card className="p-4 space-y-3">
        <h3 className="font-medium">Aperçu — simuler une adresse/un type</h3>
        <div className="grid grid-cols-4 gap-3">
          <select
            className="form-select"
            data-testid="simulation-territoire-select"
            value={simulation.territoireId}
            onChange={(e) => setSimulation((s) => ({ ...s, territoireId: e.target.value }))}
          >
            <option value="">Territoire…</option>
            {territoires.map((t) => (
              <option key={t.id} value={t.id}>{t.nom}</option>
            ))}
          </select>
          <Input
            placeholder="Ville"
            value={simulation.ville}
            onChange={(e) => setSimulation((s) => ({ ...s, ville: e.target.value }))}
          />
          <Input
            placeholder="Type d'installation"
            value={simulation.type_installation}
            onChange={(e) => setSimulation((s) => ({ ...s, type_installation: e.target.value }))}
          />
          <Button type="button" onClick={handleSimuler} disabled={simLoading}>
            {simLoading ? 'Simulation…' : 'Simuler'}
          </Button>
        </div>
        {simResult && (
          <div className="text-sm" data-testid="simulation-result">
            {simResult.matched ? (
              <span>
                Match : <strong>{simResult.territoire_nom}</strong> → assigné à{' '}
                <strong>{simResult.assigne_nom || 'aucun membre disponible'}</strong>
              </span>
            ) : (
              <span>Aucun match pour ces critères sur ce territoire.</span>
            )}
          </div>
        )}
      </Card>

      {territoires.length === 0 ? (
        <EmptyState title="Aucun territoire" description="Créez le premier territoire ci-dessus." />
      ) : (
        <div className="space-y-4">
          {territoires.map((t) => (
            <Card key={t.id} className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{t.nom}</div>
                  <div className="text-xs text-muted-foreground">{t.type_territoire_display}</div>
                </div>
                <span className="text-xs">{t.actif ? 'Actif' : 'Inactif'}</span>
              </div>
              <div>
                <div className="text-xs font-medium mb-1">Membres</div>
                <ul className="text-sm space-y-1">
                  {(t.membres || []).map((m) => (
                    <li key={m.id} className="flex justify-between">
                      <span>{m.utilisateur_nom}</span>
                      <span className="text-muted-foreground">
                        {m.quota_pct ? `${m.quota_pct}%` : 'sans quota'} ·{' '}
                        {m.nb_assignations} assigné(s)
                      </span>
                    </li>
                  ))}
                  {(t.membres || []).length === 0 && (
                    <li className="text-muted-foreground">Aucun membre.</li>
                  )}
                </ul>
                <AjoutMembre onAdd={(userId, quota) => handleAddMembre(t.id, userId, quota)} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function AjoutMembre({ onAdd }) {
  const [userId, setUserId] = useState('')
  const [quota, setQuota] = useState('')
  return (
    <div className="flex gap-2 mt-2">
      <Input
        placeholder="ID utilisateur"
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
        className="w-32"
      />
      <Input
        placeholder="Quota % (optionnel)"
        type="number"
        value={quota}
        onChange={(e) => setQuota(e.target.value)}
        className="w-40"
      />
      <Button
        type="button"
        variant="outline"
        onClick={() => { onAdd(userId, quota); setUserId(''); setQuota('') }}
      >
        Ajouter
      </Button>
    </div>
  )
}
