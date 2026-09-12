import { useEffect, useState } from 'react'
import { Star } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Button, Card, FormField, Input } from '../../../ui'

/* ============================================================================
   NTPRT35 — Widget « Satisfaction » post-interaction (portail client).
   ----------------------------------------------------------------------------
   C'est le DÉCLENCHEUR D'INTERFACE qui manquait à FG238 : l'enquête était bien
   créée à la réception d'un chantier, mais le client n'avait aucun écran pour
   y répondre. Aucune logique de scoring ici — la note part telle quelle au
   serveur, qui applique `repondre_enquete_nps` (FG238) inchangé.

   « Une fois par événement » (critère d'acceptation) ne repose sur AUCUN état
   local : le serveur ne renvoie une enquête que tant qu'elle est sans réponse.
   Une fois répondue, l'endpoint renvoie `enquete: null` — le prompt ne peut
   pas se rejouer à la connexion suivante, même sur un autre appareil.

   FG239 — après une réponse de PROMOTEUR, le serveur peut renvoyer un lien
   d'avis Google (routage, jamais une API payante) : vide, on n'affiche rien.
   ========================================================================== */

const NOTES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

export default function SatisfactionPrompt() {
  const [enquete, setEnquete] = useState(null)
  const [note, setNote] = useState(null)
  const [commentaire, setCommentaire] = useState('')
  const [erreurNote, setErreurNote] = useState(null)
  const [busy, setBusy] = useState(false)
  const [merci, setMerci] = useState(null)

  useEffect(() => {
    let annule = false
    portailApi.satisfaction.enAttente()
      .then((r) => { if (!annule) setEnquete(r.data?.enquete || null) })
      // Un widget d'enquête ne casse jamais un écran : sans réponse, il ne
      // s'affiche simplement pas.
      .catch(() => {})
    return () => { annule = true }
  }, [])

  const envoyer = async () => {
    setErreurNote(null)
    if (note === null) {
      setErreurNote('Choisissez une note entre 0 et 10.')
      return
    }
    setBusy(true)
    try {
      const r = await portailApi.satisfaction.repondre({
        enquete_id: enquete.id,
        score: note,
        commentaire,
      })
      setMerci(r.data)
      setEnquete(null)
    } catch (err) {
      setErreurNote(err?.response?.data?.score
        || "Votre réponse n'a pas pu être enregistrée.")
    } finally {
      setBusy(false)
    }
  }

  if (merci) {
    return (
      <Card className="flex flex-col gap-2 p-4">
        <p className="font-medium">{merci.detail}</p>
        {merci.lien_avis_google ? (
          <p className="text-sm text-muted-foreground">
            Vous pouvez aussi partager votre avis publiquement :{' '}
            <a href={merci.lien_avis_google} target="_blank"
               rel="noopener noreferrer" className="underline">
              laisser un avis
            </a>
          </p>
        ) : null}
      </Card>
    )
  }

  if (!enquete) return null

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <Star className="size-5 text-muted-foreground" aria-hidden="true" />
        <p className="font-medium">
          Recommanderiez-vous nos services à un proche ?
        </p>
      </div>
      <FormField label="Votre note, de 0 à 10" required error={erreurNote}>
        <div className="flex flex-wrap gap-1" role="group"
             aria-label="Note de 0 à 10">
          {NOTES.map((n) => (
            <Button
              key={n}
              type="button"
              size="sm"
              variant={note === n ? 'default' : 'outline'}
              aria-pressed={note === n}
              onClick={() => setNote(n)}
            >
              {n}
            </Button>
          ))}
        </div>
      </FormField>
      <FormField label="Un mot à ajouter ? (facultatif)">
        <Input value={commentaire}
               onChange={(e) => setCommentaire(e.target.value)} />
      </FormField>
      <div>
        <Button size="sm" onClick={envoyer} disabled={busy}>
          Envoyer mon avis
        </Button>
      </div>
    </Card>
  )
}
