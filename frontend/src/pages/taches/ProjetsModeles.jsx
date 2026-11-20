import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Ellipsis } from 'lucide-react'
import { annulerGeste, lireModele, listerTousLesModeles } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../../ui/DropdownMenu'
import ChargementTardif from '../../features/taches/ui/ChargementTardif'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { naviguerApresFeuille } from '../../features/taches/ui/FeuilleACrans'
import { DialogueRenommerModele, DialogueSupprimerModele, DialogueUtiliser } from '../../features/taches/projets/Dialogues'
import { annoncer, proposerAnnuler } from '../../features/taches/lib/gestes'
import { etapesDuModele } from '../../features/taches/lib/projets'
import { accord, aujourdhuiIso } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH157 — Écran « Modèles » (`/taches/projets/modeles`) : les modèles de projet du compte, « Utiliser ce modèle »
   (nom, date de lancement, APERÇU des dates « {n} tâches, première le {jour} », puis Créer), Renommer, Supprimer.
   Maquettes : projets-modeles.html, projets-modeles-utiliser.html. Textes : reference/textes.md §2.6 « Modèles »
   (vide « Aucun modèle »). Contrats : `modeles_liste.json`, `modele.json`, `modele_instancier.json`, `projet_ecrit.json`.
   Une ligne qui change (renommer, supprimer) se met à jour sur place : la liste n'est jamais relue après un geste.
   Un projet créé depuis un modèle s'ouvre, avec « Projet créé · Annuler » (le geste du serveur le supprime).
   ========================================================================== */

export default function ProjetsModeles() {
  const navigate = useNavigate()
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [modeles, setModeles] = useState(null)
  const [erreur, setErreur] = useState('')
  const [dialogue, setDialogue] = useState(null)

  const lire = useCallback(async () => {
    try {
      setModeles(await listerTousLesModeles())
      setErreur('')
    } catch (err) {
      setModeles((l) => l ?? [])
      setErreur(frenchError(err, 'Les modèles n\'ont pas pu être lus. Réessaie.'))
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { lire() }, [lire])

  // « Utiliser ce modèle » : les étapes et leurs tâches viennent du contenu figé (`GET modeles/{id}/`) ; sans lui, le dialogue s'ouvre quand même.
  const utiliser = async (modele) => {
    let etapes = null
    try {
      const { data } = await lireModele(modele.id)
      etapes = etapesDuModele(data.contenu)
    } catch {
      etapes = null // le dialogue s'ouvre sans la liste des étapes : le nom, la date et l'aperçu suffisent à créer
    }
    setDialogue({ type: 'utiliser', modele, etapes })
  }

  const cree = (reponse) => {
    setDialogue(null)
    const geste = reponse.geste_id
    proposerAnnuler({
      message: 'Projet créé',
      onAnnuler: async () => { if (geste) await annulerGeste(geste); navigate('/taches/projets/modeles') },
    })
    // la feuille « Utiliser ce modèle » se ferme dans le même geste : la navigation remplace son entrée d'historique
    naviguerApresFeuille(navigate, `/taches/projets/${reponse.projet.id}`)
  }
  const renomme = (modele) => {
    setDialogue(null)
    setModeles((l) => l.map((m) => (m.id === modele.id ? { ...m, nom: modele.nom } : m)).sort((a, b) => a.nom.localeCompare(b.nom, 'fr')))
    annoncer(`« ${modele.nom} »`)
  }
  const supprime = (modele) => {
    setDialogue(null)
    setModeles((l) => l.filter((m) => m.id !== modele.id))
    annoncer(`« ${modele.nom} » supprimé`)
  }

  const vide = modeles !== null && modeles.length === 0
  return (
    <CoquilleTaches ecran="projets-modeles" titre="Modèles" retour={{ libelle: 'Projets', vers: '/taches/projets' }}>
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      <ChargementTardif actif={modeles === null && !erreur} />
      {vide && !erreur ? <div className="ep-vide"><p>Aucun modèle</p></div> : null}
      {modeles && modeles.length > 0 ? (
        <section className="section ep-projets" aria-label="Modèles">
          <div className="liste" role="list">
            {modeles.map((m) => (
              <div className="ligne projet" role="listitem" key={m.id} data-modele={m.id}>
                <span className="point-projet" aria-hidden="true" />
                <div className="ligne-corps">
                  <span className="titre">{m.nom}</span>
                  <div className="meta">
                    <button type="button" className="es-action" onClick={() => utiliser(m)}>Utiliser ce modèle</button>
                    <span className="chiffres">{`${accord(m.nb_taches, 'tâche')} · ${accord(m.nb_sections, 'étape')}`}</span>
                  </div>
                </div>
                <div className="ligne-fin">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button type="button" className="ligne-actions" aria-label={`Actions pour « ${m.nom} »`}>
                        <Ellipsis className="i" aria-hidden="true" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => setDialogue({ type: 'renommer', modele: m })}>Renommer</DropdownMenuItem>
                      <DropdownMenuItem destructive onSelect={() => setDialogue({ type: 'supprimer', modele: m })}>Supprimer</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      {dialogue?.type === 'utiliser' ? (
        <DialogueUtiliser source={{ type: 'modele', id: dialogue.modele.id, nom: dialogue.modele.nom }} etapes={dialogue.etapes}
          aujourdhui={aujourdhui} onFait={cree} onFermer={() => setDialogue(null)} />
      ) : null}
      {dialogue?.type === 'renommer' ? (
        <DialogueRenommerModele modele={dialogue.modele} onFait={renomme} onFermer={() => setDialogue(null)} />
      ) : null}
      {dialogue?.type === 'supprimer' ? (
        <DialogueSupprimerModele modele={dialogue.modele} onFait={supprime} onFermer={() => setDialogue(null)} />
      ) : null}
    </CoquilleTaches>
  )
}
