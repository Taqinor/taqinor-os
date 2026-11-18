import { useCallback, useEffect, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import * as client from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { annoncer, proposerAnnuler } from '../lib/gestes'

/* ============================================================================
   TCH81 — Ce que l'ERP ajoute à Aujourd'hui, au-delà des lignes déjà rendues par LigneTache
   (badge « Activité ERP », case seulement si `peut_cloturer` → `records/activities/{id}/done/` sans
   Annuler, « Toute la journée », « Suivi des relances : n » : Sections.jsx) :
     · « Ailleurs dans l'ERP » (replié) : les compteurs de `aujourdhui/ailleurs/`, lus à la première
       ouverture seulement (route paresseuse), chacun menant à l'ERP ; une famille illisible n'empêche
       pas les autres : « Certaines informations de l'ERP n'ont pas pu être lues. » ;
     · appui long sur une activité → « Lier une tâche » : crée une tâche liée (`taches/lier-activite/`)
       et LAISSE l'activité ouverte ; déjà liée : 409 `deja_lie`, dit tel quel.
   Maquettes : composants-4.html (activité ERP), ecran-aujourdhui-matin-bas.html.
   Textes : reference/textes.md §2.2 (« Activité ERP », « Ailleurs dans l'ERP ») ; spec-6a-erp.md « Écrans ».
   ========================================================================== */

/** Les compteurs d'`ailleurs.json`, dans l'ordre de spec-6a §3 (« Chantiers, tickets, DA à commander… »). */
const FAMILLES = [
  ['chantiers', 'Chantiers'],
  ['tickets', 'Tickets'],
  ['da_a_commander', "Demandes d'achat à commander"], // « DA » = sigle interne : en clair (textes.md §0, sans jargon)
  ['leads_chauds', 'Leads chauds'],
  ['rappels', 'Rappels'],
  ['devis_expirant', 'Devis expirant'],
  ['relances', 'Relances'],
  ['approbations', 'Approbations'],
  ['mentions', 'Mentions'],
]

export const PHRASE_ERP_ILLISIBLE = "Certaines informations de l'ERP n'ont pas pu être lues."

/** Le corps du repli « Ailleurs dans l'ERP » : lu une seule fois, à l'ouverture. */
export function Ailleurs() {
  const navigate = useNavigate()
  const [etat, setEtat] = useState({ chargement: true, erreur: false, donnees: null })
  const lire = useCallback(async () => {
    try {
      const { data } = await client.lireAilleurs()
      setEtat({ chargement: false, erreur: false, donnees: data })
    } catch {
      setEtat({ chargement: false, erreur: true, donnees: null })
    }
  }, [])
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture paresseuse à l'ouverture du repli : l'état n'est posé qu'après la réponse (D-ENF22)
    lire()
  }, [lire])

  if (etat.chargement) return <div className="squelette" role="status" aria-label="Chargement" />
  if (etat.erreur) {
    return (
      <div className="pas-a-jour" role="status">
        <span>{PHRASE_ERP_ILLISIBLE}</span>
        <button type="button" className="bouton lien" onClick={lire}>Réessayer</button>
      </div>
    )
  }
  // Raccord F2 — une famille ABSENTE de la réponse, ou servie à 0 faute de porte publique (approbations, mentions),
  // n'a pas de ligne : jamais un compteur inventé ; seules les familles servies et non nulles s'affichent.
  const lignes = FAMILLES.filter(([cle]) => Number.isFinite(etat.donnees?.[cle]) && etat.donnees[cle] > 0)
  if (lignes.length === 0) return <p className="section-sous">Rien à signaler.</p>
  return (
    <div className="liste" role="list">
      {lignes.map(([cle, libelle]) => (
        <button
          key={cle}
          type="button"
          className="ligne ligne-repli"
          role="listitem"
          aria-label={`${libelle} : ${etat.donnees[cle]}. Ouvrir`}
          onClick={() => navigate(etat.donnees.lien || '/activites')}
        >
          <span className="case vide" />
          <span className="ligne-corps"><span className="titre">{libelle}</span></span>
          <span className="ligne-fin chiffres">{etat.donnees[cle]}<ChevronRight className="i i-16" aria-hidden="true" /></span>
        </button>
      ))}
    </div>
  )
}

/**
 * Corps de la feuille « Lier une tâche » : le titre de la tâche (celui de l'activité d'emblée). `onLier(titre)` rend
 * '' (réussi : la page ferme la feuille) ou le message du refus, affiché SOUS le champ (textes.md §2.16, ex. 409
 * `deja_lie` « Cette activité a déjà sa tâche. ») — la feuille reste ouverte, rien n'est perdu.
 */
export function FeuilleLier({ item, onLier }) {
  const [titre, setTitre] = useState(item.titre)
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const lier = async () => {
    setEnvoi(true)
    setErreur('')
    const refus = await onLier(titre.trim())
    setEnvoi(false)
    if (refus) setErreur(refus)
  }
  return (
    <div className="choisir-jour">
      <label className="fiche-label" htmlFor="tch-lier-titre">Titre de la tâche</label>
      <input id="tch-lier-titre" type="text" className="champ-date" value={titre} maxLength={280}
        aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'tch-lier-erreur' : undefined}
        onChange={(e) => { setTitre(e.target.value); setErreur('') }} />
      {erreur ? <p id="tch-lier-erreur" className="erreur-champ" role="alert">{erreur}</p> : null}
      <button type="button" className="bouton plein large" disabled={!titre.trim() || envoi} onClick={lier}>
        Lier une tâche
      </button>
    </div>
  )
}

/** « Lier une tâche » : crée la tâche, la montre dans Prévu si elle est du jour, propose Annuler. Rend '' si la
 *  tâche est liée, sinon le message du refus (la feuille l'affiche sous son champ). */
// eslint-disable-next-line react-refresh/only-export-components -- hook du geste, lu par la page (D-ENF22)
export function useLierActivite({ donnees, setDonnees, garde, charger }) {
  return useCallback(async (item, titre) => {
    try { garde() } catch (err) { return err.message }
    try {
      const { data } = await client.lierActivite({ activite_id: item.id, titre, jour_prevu: null })
      if (data.tache?.jour_prevu === donnees.jour) {
        setDonnees((d) => ({ ...d, journee: [...(d.journee ?? []), data.tache] }))
      }
      // Raccord F2 — `lier-activite/` rend la `progression` du jour : elle suit sans relire la journée
      if (data.progression && typeof data.progression.faites === 'number') setDonnees((d) => ({ ...d, progression: data.progression }))
      proposerAnnuler({
        message: "Tâche liée à l'activité",
        onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
      })
      return ''
    } catch (err) {
      const message = frenchError(err)
      annoncer(message)
      return message
    }
  }, [donnees, setDonnees, garde, charger])
}
