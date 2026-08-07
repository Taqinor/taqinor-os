import { useCallback, useMemo, useRef, useState } from 'react'
import { MessageSquare, AlertTriangle, Plus } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Card, Button, Input, EmptyState, Skeleton, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatDate, formatNumber } from '../../../lib/format'
import { svgVersPng } from '../studio/svgToPng'
import Annotateur from './Annotateur'
import QuestionFiche from './QuestionFiche'
import ExportQR from './ExportQR'

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

   ── PACT170 — LE FLUX RÉEL : REPÈRE → FICHE → EXPORT ─────────────────────
   `Annotateur` (AOF106, qui porte `RepereMarker`), `QuestionFiche` (AOF107
   1/3) et `ExportQR` (AOF107 2/3) étaient livrés, testés, et importés par
   PERSONNE : cet écran n'affichait que le tableau des séries. Le flux écrit
   dans leurs en-têtes est désormais monté ICI, de bout en bout :

     1. on charge une photo dans l'annotateur et on pose des repères (un clic
        = un repère, ou la voie clavier) ;
     2. « Ouvrir la fiche du repère X » ouvre la QUESTION de ce repère — celle
        que le serveur a déjà, sinon un brouillon rattaché à la série ;
     3. « Enregistrer » écrit VRAIMENT (`aoApi.questions`, la ressource que le
        routeur publiait depuis toujours et que le client n'exposait pas). Le
        refus produit est tenu des deux côtés : sans impact chiffré, la
        question n'est pas créée, et le motif est celui de la règle ;
     4. « Préparer l'image annotée » rasterise le SVG de l'annotateur
        (`svgToPng`, AOF75) et le donne à `ExportQR`, qui aplatit l'image ET
        la liste numérotée en un seul bitmap « prêt à coller ».

   Ce qui n'est PAS fait, et qui est dit à l'écran : le RECALCUL après réponse
   appartient à l'atelier de calepinage, pas à cet écran.
   ========================================================================== */

/* Le motif du SERVEUR, tel quel. DRF renvoie soit `{detail}`, soit un objet
   `{champ: [messages]}` : ne lire que `detail` transformait le refus NOMMÉ du
   sérialiseur de questions (« chiffrez son impact prévisionnel ») en un
   générique « Création impossible ». */
const errMsg = (e, fallback) => {
  const donnees = e?.response?.data
  if (typeof donnees === 'string') return donnees
  if (donnees?.detail) return donnees.detail
  if (donnees && typeof donnees === 'object') {
    const [champ, valeur] = Object.entries(donnees)[0] || []
    if (champ) return `${champ} : ${[].concat(valeur).join(' ')}`
  }
  return fallback
}

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

  // ── PACT170 — annotateur, fiche question, export ────────────────────────
  const svgAnnotateur = useRef(null)
  const [reperes, setReperes] = useState([])
  const [repereOuvert, setRepereOuvert] = useState(null) // { id, lettre }
  const [imageAnnotee, setImageAnnotee] = useState(null)
  const [preparation, setPreparation] = useState(false)
  const [enregistrementQuestion, setEnregistrementQuestion] = useState(false)
  // Ce que cet écran REFUSE de faire, avec son motif — jamais un bouton muet.
  const [noteQuestion, setNoteQuestion] = useState(null)

  /* L'export « prêt à coller » a besoin de l'image ANNOTÉE (photo + repères),
     pas de la photo nue : on rasterise le SVG de l'annotateur avec la brique
     partagée `svgToPng`. Un clic explicite, jamais une rasterisation à chaque
     repère posé (coûteuse, et elle transformerait un geste en attente). */
  const preparerImageAnnotee = useCallback(async () => {
    const svg = svgAnnotateur.current
    if (!svg) return
    setPreparation(true)
    try {
      const { dataUrl } = await svgVersPng(svg, { largeur: 1000 })
      setImageAnnotee(dataUrl)
    } catch {
      toast.error('Image annotée non préparée — réessayez.')
    } finally {
      setPreparation(false)
    }
  }, [])

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

  /* La question du repère ouvert : celle que le SERVEUR a déjà pour ce repère
     dans cette série, sinon un BROUILLON local rattaché à la série. Jamais un
     repli sur la question d'un autre repère — ce serait éditer la mauvaise. */
  const questionCourante = (() => {
    if (!repereOuvert || !serieOuverte) return null
    const existante = (serieOuverte.questions ?? [])
      .find((q) => (q.repere ?? '') === repereOuvert.lettre)
    return existante ?? {
      id: null,
      repere: repereOuvert.lettre,
      texte: '',
      impact_min_modules: null,
      impact_max_modules: null,
      reponse: '',
      decision: '',
      date_decision: null,
      statut: 'posee',
    }
  })()

  /* Écriture RÉELLE. Le sérialiseur refuse une question sans impact chiffré :
     on tient le MÊME refus à la création, avec le même motif, plutôt que de
     laisser partir un 400 que l'écran traduirait en « erreur ». */
  const enregistrerQuestion = async (patch) => {
    if (!serieOuverte || !questionCourante) return
    const sansImpact = patch.impact_min_modules == null && patch.impact_max_modules == null
    if (!questionCourante.id && sansImpact) {
      setNoteQuestion(
        'Question non créée : chiffrez d’abord son impact prévisionnel en modules. '
        + 'On ne pose une question que si sa réponse change le compte.',
      )
      return
    }
    setEnregistrementQuestion(true)
    try {
      if (questionCourante.id) {
        await aoApi.questions.update(questionCourante.id, patch)
      } else {
        await aoApi.questions.create({
          serie: serieOuverte.id,
          repere: questionCourante.repere,
          texte: patch.texte ?? '',
          ...patch,
        })
      }
      setNoteQuestion(null)
      toast.success('Question enregistrée.')
      await refetch()
    } catch (e) {
      const motif = errMsg(e, 'Enregistrement de la question impossible.')
      setNoteQuestion(motif)
      toast.error(motif)
    } finally {
      setEnregistrementQuestion(false)
    }
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

      {/* PACT170 — le flux réel : poser un repère → ouvrir sa fiche → exporter
          l'image annotée et sa liste numérotée. */}
      {serieOuverte && (
        <Card className="flex flex-col gap-4 p-4" data-ao-annotation-serie={serieOuverte.id}>
          <div>
            <h2 className="font-medium">Annoter une image</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Le client répond SUR l’image : posez un repère, ouvrez sa fiche et
              chiffrez l’impact de la réponse. Une question sans impact chiffré
              n’est pas créée.
            </p>
          </div>

          <Annotateur
            refSvg={svgAnnotateur}
            onChange={setReperes}
            onOuvrirFiche={(id, lettre) => {
              setNoteQuestion(null)
              setRepereOuvert({ id, lettre })
            }}
          />

          {questionCourante && (
            <div className="flex flex-col gap-2 border-t border-border pt-3">
              <QuestionFiche
                question={questionCourante}
                onChange={enregistrerQuestion}
                recalculEnCours={enregistrementQuestion}
                onRecalculer={() => setNoteQuestion(
                  'Le recalcul appartient à l’atelier de calepinage (onglet « Calepinages ») : '
                  + 'rien n’est recalculé depuis les questions. La décision, elle, est enregistrée.',
                )}
              />
              {noteQuestion && (
                <p role="status" className="text-sm text-muted-foreground" data-ao-note-question="">
                  {noteQuestion}
                </p>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
            <Button
              size="sm"
              variant="outline"
              loading={preparation}
              disabled={reperes.length === 0 || preparation}
              onClick={preparerImageAnnotee}
            >
              Préparer l’image annotée
            </Button>
            {reperes.length === 0 && (
              <span className="text-xs text-muted-foreground">
                Posez au moins un repère : l’export porte l’image ET la liste numérotée.
              </span>
            )}
          </div>

          <ExportQR
            imageSrc={imageAnnotee}
            questions={serieOuverte.questions ?? []}
            date={serieOuverte.date_envoi}
          />
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
