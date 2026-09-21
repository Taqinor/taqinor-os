import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import ChatterTimeline from '../../../components/ChatterTimeline'
import { Button, Card, Spinner, Textarea } from '../../../ui'

/* ============================================================================
   CALX31 — LE FIL D'ACTIVITÉ DU CALEPINAGE.
   ----------------------------------------------------------------------------
   Constat : `CalepinageViewSet` hérite `ChatterViewSetMixin`
   (`views/calepinages.py:158-161`), donc `chatter/historique/` et
   `chatter/noter/` sont DÉJÀ servis et alimentés par `services/journal.py` à
   chaque écriture — aucun consommateur n'existait dans le module.

   RÉUTILISE le composant maison `ChatterTimeline` (VX23, `components/
   ChatterTimeline.jsx`), déjà consommé par `PlanComptePage.jsx` sur le MÊME
   contrat (`records.serializers.ChatterActivitySerializer`) : jamais un
   second rendu de fil d'activité. L'auteur ET l'horodatage viennent
   TOUJOURS du serveur (`user_username`, `created_at`) — la note elle-même
   ne porte ni l'un ni l'autre, écrits côté vue.

   AUCUN RECHARGEMENT COMPLET après l'ajout d'une note : l'entrée renvoyée
   par `chatter/noter/` rejoint la liste en mémoire, et `ChatterTimeline`
   la replace en tête (tri décroissant sur `created_at`).
   ========================================================================== */

export default function PanneauActivite({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [entrees, setEntrees] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [note, setNote] = useState('')
  const [envoiEnCours, setEnvoiEnCours] = useState(false)

  useEffect(() => {
    if (!calepinageId) return undefined
    let annule = false
    Promise.resolve(calepinageApi.calepinages.chatterHistorique(calepinageId))
      .then((res) => {
        if (annule) return
        const liste = Array.isArray(res?.data) ? res.data : []
        setEntrees(liste.map((e) => ({ ...e, user_nom: e.user_username })))
        setErreur(null)
      })
      .catch(() => { if (!annule) setErreur('L’historique n’a pas pu être chargé.') })
    return () => { annule = true }
  }, [calepinageId])

  const ajouterNote = () => {
    const texte = note.trim()
    if (!texte) return
    setEnvoiEnCours(true)
    setErreur(null)
    Promise.resolve(calepinageApi.calepinages.chatterNoter(calepinageId, texte))
      .then((res) => {
        const cree = res?.data
        if (cree) {
          setEntrees((liste) => [...(liste ?? []), { ...cree, user_nom: cree.user_username }])
        }
        setNote('')
      })
      .catch(() => setErreur('La note n’a pas pu être enregistrée.'))
      .finally(() => setEnvoiEnCours(false))
  }

  return (
    <div className="mt-6" data-testid="cal-activite">
      <p className="tech-label rule-brass text-brass-300">Activité</p>

      <Card className="mt-3 space-y-2 p-4">
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ajouter une note…"
          data-testid="cal-activite-note-texte"
          rows={3}
        />
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={ajouterNote}
            disabled={!note.trim() || envoiEnCours}
            data-testid="cal-activite-note-ajouter"
          >
            {envoiEnCours ? 'Enregistrement…' : 'Ajouter la note'}
          </Button>
        </div>
      </Card>

      {erreur && (
        <p role="alert" className="mt-3 text-sm text-destructive" data-testid="cal-activite-erreur">
          {erreur}
        </p>
      )}

      <div className="mt-4">
        {entrees === null ? (
          <div className="flex items-center gap-2 text-sm text-lune-faint">
            <Spinner />
            Chargement de l’activité…
          </div>
        ) : (
          <ChatterTimeline entries={entrees} emptyLabel="Aucune activité pour le moment." />
        )}
      </div>
    </div>
  )
}
