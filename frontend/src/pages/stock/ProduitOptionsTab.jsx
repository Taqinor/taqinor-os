import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import api from '../../api/axios'
import { Button, Badge, Input, Checkbox, toast } from '../../ui'

/* ============================================================================
   PACT128 — Options de configuration d'un produit.
   ----------------------------------------------------------------------------
   NTCPQ1 (`apps/cpq`) livrait déjà ``OptionProduit`` (groupes d'options
   « Onduleur »/« Batterie », obligatoires ou non, endpoint
   `/cpq/options-produit/`) SANS AUCUN écran. La fiche produit a déjà un
   système d'onglets (`ProduitDetail.jsx`) : cet onglet s'y ajoute, comme
   demandé — pas un écran séparé. `OptionProduitViewSet` ne déclare aucun
   filtre serveur par produit (même patron que `cpqApi.js::getPrixContractuels`,
   PACT129) : le filtrage par produit se fait CÔTÉ CLIENT sur la réponse,
   jamais un `?produit=` inventé que le serveur ignorerait.
   ========================================================================== */

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

export default function ProduitOptionsTab({ produitId }) {
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [groupeOption, setGroupeOption] = useState('')
  const [obligatoire, setObligatoire] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    api.get('/cpq/options-produit/')
      .then((res) => {
        const toutes = listOf(res.data)
        setOptions(toutes.filter((o) => o.produit === produitId))
      })
      .catch(() => setError('Impossible de charger les options de ce produit.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount pour ce produit
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [produitId])

  const ajouterGroupe = async (e) => {
    e.preventDefault()
    if (!groupeOption.trim()) return
    setSaving(true)
    try {
      await api.post('/cpq/options-produit/', {
        produit: produitId, groupe_option: groupeOption.trim(), obligatoire,
      })
      toast.success('Groupe d’options ajouté.')
      setGroupeOption('')
      setObligatoire(false)
      load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Impossible d’ajouter ce groupe d’options.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={ajouterGroupe} className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="popt-groupe" className="text-xs text-muted-foreground">Groupe d’options</label>
          <Input
            id="popt-groupe" value={groupeOption}
            onChange={(e) => setGroupeOption(e.target.value)}
            placeholder="ex. Onduleur, Batterie…"
          />
        </div>
        <label className="mb-2 flex items-center gap-2 text-sm">
          <Checkbox
            checked={obligatoire}
            onCheckedChange={(v) => setObligatoire(Boolean(v))}
          />
          Obligatoire
        </label>
        <Button type="submit" size="sm" disabled={saving || !groupeOption.trim()}>
          <Plus className="size-4" aria-hidden="true" /> Ajouter
        </Button>
      </form>

      {loading && <p className="py-2 text-sm text-muted-foreground">Chargement…</p>}
      {error && <p className="py-2 text-sm text-destructive" role="alert">{error}</p>}
      {!loading && !error && options.length === 0 && (
        <p className="py-2 text-sm text-muted-foreground">Aucun groupe d’options pour ce produit.</p>
      )}
      {!loading && !error && options.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Groupe</th>
                <th className="px-3 py-2 text-left font-semibold">Caractère</th>
              </tr>
            </thead>
            <tbody>
              {options.map((o) => (
                <tr key={o.id} className="border-t border-border">
                  <td className="px-3 py-2 font-medium">{o.groupe_option}</td>
                  <td className="px-3 py-2">
                    <Badge tone={o.obligatoire ? 'warning' : 'neutral'}>
                      {o.obligatoire ? 'Obligatoire' : 'Optionnel'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
