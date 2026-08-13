// NTMOB19 — widget « À faire aujourd'hui », unifié cross-rôle.
// Réutilisable par les accueils mobiles (NTMOB4/NTMOB5/NTMOB25/NTMOB26) et
// « Ma journée » : une seule liste, tous modules confondus, triée par urgence
// et bornée à 10 items cliquables vers leur écran source.
// AUCUN nouveau modèle ni endpoint : quatre appels de lecture déjà existants,
// chacun tolérant l'échec indépendamment (un module en panne n'éteint jamais
// le widget). Tri/normalisation dans `aFaireItems.js` (logique pure).
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ListChecks, ChevronRight } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import reportingApi from '../../../api/reportingApi'
import installationsApi from '../../../api/installationsApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Spinner, EmptyState,
} from '../../../ui'
// NOTE : le module de logique s'appelle `aFaireItems.js` et NON
// `aFaireAujourdhui.js` — sur un système de fichiers insensible à la casse
// (Windows), `./AFaireAujourdhui` résoudrait vers le `.js` avant le `.jsx` et
// le composant deviendrait `undefined` au rendu.
import { aFaireAujourdhui } from './aFaireItems'

// Lecture d'arrière-plan : une source indisponible ne doit jamais faire
// surgir un toast rouge (le widget se contente de ne rien montrer pour elle).
const SILENCIEUX = { suppressErrorToast: true }

const TONE = {
  approbation: 'warning',
  intervention: 'neutral',
  relance: 'warning',
  facture: 'danger',
}

/**
 * @param {string[]} exclure — natures dont l'écran hôte est DÉJÀ la vue
 *   complète (ex. `['intervention']` sur « Ma journée ») : la source
 *   correspondante n'est alors même pas appelée — ni doublon d'affichage, ni
 *   second appel réseau sur le même endpoint.
 */
export default function AFaireAujourdhui({ exclure = [] }) {
  const navigate = useNavigate()
  const [items, setItems] = useState(null)
  const exclureCle = exclure.join(',')

  useEffect(() => {
    let alive = true
    const exclus = exclureCle ? exclureCle.split(',') : []
    const veut = (kind) => !exclus.includes(kind)
    const today = new Date().toISOString().slice(0, 10)
    // Chaque source échoue INDÉPENDAMMENT (réseau, droits, module absent) :
    // le widget se contente alors de ne rien afficher pour elle.
    const safe = (call, pick) => {
      try {
        return Promise.resolve(call()).then((r) => pick(r) ?? []).catch(() => [])
      } catch {
        return Promise.resolve([])
      }
    }
    const rien = () => Promise.resolve([])
    Promise.all([
      veut('relance')
        ? safe(() => crmApi.getRelances({ scope: 'today' }, SILENCIEUX), (r) => r.data?.results)
        : rien(),
      veut('approbation')
        ? safe(() => reportingApi.approbationsEnAttente(undefined, SILENCIEUX), (r) => r.data?.items)
        : rien(),
      veut('intervention')
        ? safe(() => installationsApi.getMaTournee(today, SILENCIEUX), (r) => r.data?.stops)
        : rien(),
      veut('facture')
        ? safe(() => reportingApi.getNotifications(SILENCIEUX), (r) => r.data?.factures)
        : rien(),
    ]).then(([relances, approbations, interventions, factures]) => {
      if (!alive) return
      setItems(aFaireAujourdhui(
        { relances, approbations, interventions, factures }, today,
      ))
    })
    return () => { alive = false }
  }, [exclureCle])

  return (
    <Card data-widget="a-faire-aujourdhui">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ListChecks className="size-4 text-muted-foreground" aria-hidden="true" />
              À faire aujourd'hui
            </CardTitle>
            <CardDescription>Tous modules, par urgence</CardDescription>
          </div>
          {items && items.length > 0 && <Badge tone="warning">{items.length}</Badge>}
        </div>
      </CardHeader>
      <CardContent>
        {items === null
          ? <Spinner />
          : items.length === 0
            ? <EmptyState title="Rien d'urgent aujourd'hui" />
            : (
              <ul className="flex flex-col divide-y divide-border">
                {items.map((it) => (
                  <li key={it.id}>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-2 py-2 text-left"
                      onClick={() => navigate(it.to)}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{it.label}</span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {it.sublabel}
                        </span>
                      </span>
                      <Badge tone={TONE[it.kind] || 'neutral'}>{it.kind}</Badge>
                      <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
      </CardContent>
    </Card>
  )
}
