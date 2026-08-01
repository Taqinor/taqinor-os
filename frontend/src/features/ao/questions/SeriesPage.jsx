import { useCallback, useMemo, useState } from 'react'
import { MessageSquare, AlertTriangle, Plus } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Card, Button, Input, EmptyState, Skeleton, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatDate, formatNumber } from '../../../lib/format'

/* ============================================================================
   AOF106 (1/2) — Écran « Questions terrain » : les séries datées.
   ----------------------------------------------------------------------------
   Une SÉRIE = un envoi daté de questions au maître d'ouvrage, avec son objet,
   son nombre de questions, le nombre de réponses obtenues et son IMPACT CUMULÉ
   CONSTATÉ (pas prévisionnel — le prévu vit sur la fiche question, AOF107 ; ici
   on affiche ce que les réponses ont RÉELLEMENT changé, tel que le serveur l'a
   mesuré). Le front n'agrège rien : `impact_constate_modules` est une lecture.

   La timeline des échanges d'une série est fournie par le serveur
   (`echanges`) : date + sens (envoyé / reçu) + résumé. Aucun fil local n'est
   reconstitué côté front.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const signe = (v) => (v > 0 ? `+${formatNumber(v, { decimals: 0 })}` : formatNumber(v, { decimals: 0 }))

function Timeline({ echanges }) {
  if (!echanges?.length) {
    return <p className="text-sm text-muted-foreground">Aucun échange enregistré sur cette série.</p>
  }
  return (
    <ol className="flex flex-col gap-2 border-l border-border pl-4">
      {echanges.map((e) => (
        <li key={e.id} className="text-sm">
          <span className="font-medium">{formatDate(e.date)}</span>
          <span className="ml-2 text-xs uppercase tracking-wide text-muted-foreground">
            {e.sens === 'recu' ? 'Reçu' : 'Envoyé'}
          </span>
          <p className="text-muted-foreground">{e.resume}</p>
        </li>
      ))}
    </ol>
  )
}

export function SeriesPage({ affaireId }) {
  const [ouverte, setOuverte] = useState(null) // id de la série dépliée
  const [creation, setCreation] = useState(false)
  const [objet, setObjet] = useState('')
  const [enCours, setEnCours] = useState(false)

  const params = useMemo(() => ({ affaire: affaireId }), [affaireId])
  const { data: series, loading, error, refetch } = useResource(
    () => aoApi.seriesQR.list(params), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les séries de questions.' },
  )

  const creer = useCallback(async () => {
    if (!objet.trim()) return
    setEnCours(true)
    try {
      await aoApi.seriesQR.create({ affaire: affaireId, objet: objet.trim() })
      toast.success('Série de questions créée.')
      setObjet('')
      setCreation(false)
      await refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Création impossible.'))
    } finally {
      setEnCours(false)
    }
  }, [affaireId, objet, refetch])

  if (loading) {
    return <Card className="p-4"><Skeleton className="h-5 w-1/3" /><Skeleton className="mt-3 h-24 w-full" /></Card>
  }
  if (error) {
    return <EmptyState icon={AlertTriangle} title="Impossible de charger les séries" description={error} />
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Questions terrain</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Une série = un envoi daté. Le client répond sur l’image, pas sur du texte abstrait.
          </p>
        </div>
        <Button size="sm" onClick={() => setCreation(true)}>
          <Plus size={14} aria-hidden="true" /> Nouvelle série
        </Button>
      </div>

      {series.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="Aucune série de questions"
          description="Créez une série pour regrouper les questions d’un même envoi au maître d’ouvrage."
        />
      ) : (
        <div className="-mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[40rem] border-collapse text-sm">
            <caption className="sr-only">
              Séries de questions : date, objet, questions posées, réponses obtenues, impact constaté.
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-2 pr-3 font-medium">Date</th>
                <th scope="col" className="py-2 pr-3 font-medium">Objet</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Questions</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Réponses</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Impact constaté</th>
                <th scope="col" className="py-2 font-medium">Échanges</th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => (
                <tr key={s.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">{formatDate(s.date)}</td>
                  <th scope="row" className="py-2 pr-3 text-left font-normal">{s.objet}</th>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {formatNumber(s.questions_count, { decimals: 0 })}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {formatNumber(s.reponses_count, { decimals: 0 })}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {s.impact_constate_modules != null
                      ? `${signe(s.impact_constate_modules)} module(s)`
                      : 'en attente'}
                  </td>
                  <td className="py-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-expanded={ouverte === s.id}
                      onClick={() => setOuverte((prev) => (prev === s.id ? null : s.id))}
                    >
                      {ouverte === s.id ? 'Masquer' : 'Voir'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {ouverte != null && (
        <Card className="flex flex-col gap-2 p-4">
          <h2 className="font-medium">
            {`Échanges — ${series.find((s) => s.id === ouverte)?.objet ?? ''}`}
          </h2>
          <Timeline echanges={series.find((s) => s.id === ouverte)?.echanges} />
        </Card>
      )}

      <Dialog open={creation} onOpenChange={setCreation}>
        <DialogContent>
          <DialogHeader><DialogTitle>Nouvelle série de questions</DialogTitle></DialogHeader>
          <Input
            value={objet}
            onChange={(e) => setObjet(e.target.value)}
            placeholder="Objet de la série (ex. relevé du bâtiment C)"
            aria-label="Objet de la série"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreation(false)}>Annuler</Button>
            <Button disabled={!objet.trim() || enCours} onClick={creer}>Créer la série</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default SeriesPage
