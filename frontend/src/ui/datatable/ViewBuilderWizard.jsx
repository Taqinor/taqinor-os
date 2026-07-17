// NTUX25 — Assistant de création de vue avancée (wizard 3 étapes) au-dessus
// de FilterBuilder.jsx (NTUX3) et du système de vues serveur (NTUX1) : pour
// un utilisateur non technique, remplace la construction manuelle de
// `SavedView.configuration` dans un formulaire technique. Étape 1 : colonnes
// visibles + ordre (boutons monter/descendre — plus accessible et testable
// que le glisser-déposer déjà utilisé sur les en-têtes de <DataTable>, même
// résultat final : un ordre de colonnes). Étape 2 : filtres visuels
// (FilterBuilder, NTUX3/4). Étape 3 : nom + visibilité (personnelle/équipe,
// seulement si l'appelant indique que le rôle courant a le droit de
// partager — reflète le 403 serveur de `SavedViewViewSet`).
//
// Composant GÉNÉRIQUE et autonome (aucun état serveur, aucun import
// crm/ventes) : l'écran appelant fournit `columns` + `ecran` +
// `onCreate({ecran, nom, visibilite, configuration})` — voir
// `useServerSavedViews().createView` pour un `onCreate` prêt à l'emploi.
import { useState } from 'react'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Check } from 'lucide-react'
import { Button, Checkbox, Input, Segmented } from '..'
import FilterBuilder from './FilterBuilder'
import { emptyGroup } from './filterLogic'

const STEPS = ['Colonnes', 'Filtres', 'Nom et visibilité']

export default function ViewBuilderWizard({
  columns = [], ecran, canShareTeam = false, onCreate, onCancel,
}) {
  const [step, setStep] = useState(0)
  const [order, setOrder] = useState(() => columns.map((c) => c.id))
  const [hidden, setHidden] = useState(() => new Set())
  const [filters, setFilters] = useState(() => emptyGroup('AND'))
  const [nom, setNom] = useState('')
  const [visibilite, setVisibilite] = useState('PERSONNELLE')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const visibleColumns = order.filter((id) => !hidden.has(id))

  const toggleColumn = (id) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const move = (id, dir) => {
    setOrder((prev) => {
      const idx = prev.indexOf(id)
      const target = idx + dir
      if (target < 0 || target >= prev.length) return prev
      const next = prev.slice()
      const tmp = next[idx]
      next[idx] = next[target]
      next[target] = tmp
      return next
    })
  }

  const canLeaveStep1 = visibleColumns.length > 0
  const canSubmit = nom.trim().length > 0 && !submitting

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      await onCreate({
        ecran,
        nom: nom.trim(),
        visibilite,
        configuration: { colonnes_visibles: visibleColumns, filtres: filters },
      })
    } catch {
      setError('Création de la vue impossible.')
      setSubmitting(false)
    }
  }

  return (
    <div data-testid="view-builder-wizard" className="flex flex-col gap-4">
      <ol className="flex items-center gap-3 text-xs font-medium text-muted-foreground" aria-label="Étapes de l'assistant">
        {STEPS.map((label, i) => (
          <li key={label} aria-current={i === step ? 'step' : undefined}
            className={i === step ? 'text-foreground' : undefined}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div data-testid="vbw-step-columns" className="flex flex-col gap-2">
          {order.map((id) => {
            const col = columns.find((c) => c.id === id)
            const visible = !hidden.has(id)
            return (
              <div key={id} className="flex items-center gap-2">
                <Checkbox
                  id={`vbw-col-${id}`}
                  checked={visible}
                  onCheckedChange={() => toggleColumn(id)}
                />
                <label htmlFor={`vbw-col-${id}`} className="flex-1 text-sm">
                  {col?.header ?? id}
                </label>
                {visible && (
                  <>
                    <Button
                      type="button" variant="ghost" size="icon" className="size-7"
                      aria-label={`Monter ${col?.header ?? id}`}
                      onClick={() => move(id, -1)}
                    >
                      <ArrowUp />
                    </Button>
                    <Button
                      type="button" variant="ghost" size="icon" className="size-7"
                      aria-label={`Descendre ${col?.header ?? id}`}
                      onClick={() => move(id, 1)}
                    >
                      <ArrowDown />
                    </Button>
                  </>
                )}
              </div>
            )
          })}
        </div>
      )}

      {step === 1 && (
        <div data-testid="vbw-step-filters">
          <FilterBuilder columns={columns} value={filters} onChange={setFilters} />
        </div>
      )}

      {step === 2 && (
        <div data-testid="vbw-step-name" className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Nom de la vue
            <Input
              value={nom} onChange={(e) => setNom(e.target.value)}
              placeholder="Mes devis en retard ce mois" autoFocus
            />
          </label>
          {canShareTeam && (
            <div className="flex flex-col gap-1 text-sm">
              Visibilité
              <Segmented
                value={visibilite}
                onChange={setVisibilite}
                options={[
                  { value: 'PERSONNELLE', label: 'Personnelle' },
                  { value: 'EQUIPE', label: "Partagée à l'équipe" },
                ]}
              />
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
      )}

      <div className="flex items-center justify-between border-t border-border pt-3">
        <Button type="button" variant="ghost" onClick={onCancel}>Annuler</Button>
        <div className="flex items-center gap-2">
          {step > 0 && (
            <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>
              <ArrowLeft /> Précédent
            </Button>
          )}
          {step < 2 && (
            <Button
              type="button" onClick={() => setStep((s) => s + 1)}
              disabled={step === 0 && !canLeaveStep1}
            >
              Suivant <ArrowRight />
            </Button>
          )}
          {step === 2 && (
            <Button type="button" onClick={submit} disabled={!canSubmit} loading={submitting}>
              <Check /> Créer la vue
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
