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
   Une SÉRIE = un envoi daté de questions au maître d'ouvrage.

   RÉPARATION 03/08/2026. Cet écran appelait `/ao/series-qr/`, une route jamais
   enregistrée (le routeur publie `series-questions`), et lisait six champs que
   `SerieQuestionsSerializer` n'a jamais produits : `date`, `objet`,
   `questions_count`, `reponses_count`, `impact_constate_modules`, `echanges`.
   Le test le laissait passer parce qu'il mockait la forme SUPPOSÉE par
   l'écran.

   Ce que le serveur envoie RÉELLEMENT, et donc ce que cet écran affiche :
   `numero`, `date_envoi`, `canal`/`canal_display`, `destinataire`, la liste
   `questions` (imbriquée, `QuestionAOSerializer`) et `impact_total_modules`
   — une FOURCHETTE PRÉVISIONNELLE `{min, max}` calculée par le serveur.

   Deux conséquences honnêtes, à ne pas maquiller :
   * l'impact affiché est PRÉVISIONNEL (somme des impacts chiffrés des
     questions), pas « constaté » — aucune mesure d'après-réponse n'existe
     côté serveur ; l'annoncer « constaté » serait un chiffre inventé ;
   * la timeline des échanges n'existe nulle part côté serveur. Le dépliant
     montre donc les QUESTIONS de la série (données réelles), pas un fil
     reconstitué côté front.

   Le front n'agrège rien qu'il n'ait reçu : les deux compteurs sont la
   longueur de la liste que le serveur a envoyée et le nombre de ses éléments
   déjà répondus — jamais une estimation.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const signe = (v) => (v > 0 ? `+${formatNumber(v, { decimals: 0 })}` : formatNumber(v, { decimals: 0 }))

/* Miroir de `SerieQuestions.Canal` (`apps/ao/models.py`) — verrouillé par un
   test qui relit les `TextChoices` du modèle. */
// eslint-disable-next-line react-refresh/only-export-components -- constante pure co-localisée (testable contre le modèle), même motif que SensibilitesPanel.lignePlancher
export const CANAUX = [
  { value: 'email', label: 'Courriel' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'courrier', label: 'Courrier' },
  { value: 'reunion', label: 'Réunion' },
  { value: 'autre', label: 'Autre' },
]

const repondues = (questions) =>
  (questions ?? []).filter((q) => (q.reponse ?? '').trim() !== '').length

function ImpactPrevisionnel({ serie }) {
  const questions = serie.questions ?? []
  if (!questions.length) return <span className="text-muted-foreground">aucune question</span>
  const { min = 0, max = 0 } = serie.impact_total_modules ?? {}
  if (min === max) return <>{`${signe(min)} module(s)`}</>
  return <>{`${signe(min)} à ${signe(max)} module(s)`}</>
}

function Questions({ questions }) {
  if (!questions?.length) {
    return <p className="text-sm text-muted-foreground">Aucune question dans cette série.</p>
  }
  return (
    <ol className="flex flex-col gap-2 border-l border-border pl-4">
      {questions.map((q) => (
        <li key={q.id} className="text-sm">
          <span className="font-medium">{q.repere ? `Repère ${q.repere}` : `Question ${q.id}`}</span>
          <span className="ml-2 text-xs uppercase tracking-wide text-muted-foreground">
            {q.statut_display}
          </span>
          <p>{q.texte}</p>
          {q.reponse ? (
            <p className="text-muted-foreground">{`Réponse : ${q.reponse}`}</p>
          ) : (
            <p className="text-muted-foreground">Sans réponse à ce jour.</p>
          )}
        </li>
      ))}
    </ol>
  )
}

export function SeriesPage({ affaireId }) {
  const [ouverte, setOuverte] = useState(null) // id de la série dépliée
  const [creation, setCreation] = useState(false)
  const [destinataire, setDestinataire] = useState('')
  const [canal, setCanal] = useState(CANAUX[0].value)
  const [enCours, setEnCours] = useState(false)

  // Le filtre serveur s'appelle `appel_offre` (`SerieQuestionsViewSet`) —
  // `affaire` est un mot d'écran, il était ignoré en silence.
  const params = useMemo(() => ({ appel_offre: affaireId }), [affaireId])
  const { data: series, loading, error, refetch } = useResource(
    () => aoApi.seriesQR.list(params), params,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les séries de questions.' },
  )

  const creer = useCallback(async () => {
    if (!destinataire.trim()) return
    setEnCours(true)
    try {
      // `numero` est attribué CÔTÉ SERVEUR (plus haut utilisé + 1) : l'écran
      // ne propose jamais un numéro, ce serait un `count()+1` déguisé.
      await aoApi.seriesQR.create({
        appel_offre: affaireId, canal, destinataire: destinataire.trim(),
      })
      toast.success('Série de questions créée.')
      setDestinataire('')
      setCreation(false)
      await refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Création impossible.'))
    } finally {
      setEnCours(false)
    }
  }, [affaireId, canal, destinataire, refetch])

  if (loading) {
    return <Card className="p-4"><Skeleton className="h-5 w-1/3" /><Skeleton className="mt-3 h-24 w-full" /></Card>
  }
  if (error) {
    return <EmptyState icon={AlertTriangle} title="Impossible de charger les séries" description={error} />
  }

  const serieOuverte = series.find((s) => s.id === ouverte)

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
          <table className="w-full min-w-[44rem] border-collapse text-sm">
            <caption className="sr-only">
              Séries de questions : numéro, date d’envoi, canal, destinataire, questions posées,
              réponses obtenues, impact prévisionnel.
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-2 pr-3 font-medium">N°</th>
                <th scope="col" className="py-2 pr-3 font-medium">Envoyée le</th>
                <th scope="col" className="py-2 pr-3 font-medium">Canal</th>
                <th scope="col" className="py-2 pr-3 font-medium">Destinataire</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Questions</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Réponses</th>
                <th scope="col" className="py-2 pr-3 text-right font-medium">Impact prévisionnel</th>
                <th scope="col" className="py-2 font-medium">Détail</th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => (
                <tr key={s.id} className="border-b border-border/60 align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    {`Série ${formatNumber(s.numero, { decimals: 0 })}`}
                  </th>
                  <td className="py-2 pr-3 whitespace-nowrap">
                    {s.date_envoi ? formatDate(s.date_envoi) : 'non envoyée'}
                  </td>
                  <td className="py-2 pr-3">{s.canal_display}</td>
                  <td className="py-2 pr-3">{s.destinataire || '—'}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {formatNumber((s.questions ?? []).length, { decimals: 0 })}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {formatNumber(repondues(s.questions), { decimals: 0 })}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    <ImpactPrevisionnel serie={s} />
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

      {serieOuverte && (
        <Card className="flex flex-col gap-2 p-4">
          <h2 className="font-medium">
            {`Questions — série ${formatNumber(serieOuverte.numero, { decimals: 0 })}`}
          </h2>
          <Questions questions={serieOuverte.questions} />
        </Card>
      )}

      <Dialog open={creation} onOpenChange={setCreation}>
        <DialogContent>
          <DialogHeader><DialogTitle>Nouvelle série de questions</DialogTitle></DialogHeader>
          <label className="flex flex-col gap-1 text-sm" htmlFor="serie-canal">
            Canal
            <select
              id="serie-canal"
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
              value={canal}
              onChange={(e) => setCanal(e.target.value)}
            >
              {CANAUX.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </label>
          <Input
            value={destinataire}
            onChange={(e) => setDestinataire(e.target.value)}
            placeholder="Destinataire (ex. maîtrise d’œuvre)"
            aria-label="Destinataire de la série"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreation(false)}>Annuler</Button>
            <Button disabled={!destinataire.trim() || enCours} onClick={creer}>Créer la série</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default SeriesPage
