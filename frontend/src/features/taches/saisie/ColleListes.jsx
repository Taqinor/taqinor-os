import { useMemo, useState } from 'react'

import { accord } from '../lib/textes'
import ApercuListe from '../ui/ApercuListe'

/* ============================================================================
   TCH83 — « Coller mes listes » : le corps de la feuille de saisie quand on colle plus d'une ligne
   (ou plusieurs listes). Reçoit l'aperçu du serveur (`saisie_apercu.json`) et tient ce que la
   personne change AVANT de créer : cases, titres, « En faire une tâche » (le projet de tête
   devient une tâche), « En faire des sous-tâches », priorité des nouveaux projets. Rien n'est
   écrit tant que « Créer N tâches » n'est pas touché ; la création = UN envoi `saisie-rapide/`
   (`apercu:false`) fait par la feuille, qui reçoit les LIGNES prêtes.
   Boutons (textes.md §2.3) : Créer {n} tâches · Coller encore.
   ========================================================================== */

const MODIFS_VIDES = { cochees: {}, titres: {}, enTache: {}, sousTaches: {} }

/** Les champs d'une ligne lue qui disent QUAND la faire : la phrase en a dit un, le jour de l'écran s'efface. */
const CHAMPS_QUAND = ['jour_prevu', 'moment', 'heure_debut', 'quelque_jour']

/**
 * La ligne à créer : les champs lus, puis ce que la personne a posé à la main (Quand, priorité du projet).
 * R2-002 — `quandDefaut` est le jour de l'ÉCRAN (Aujourd'hui, case de l'Agenda) : il ne vaut que si la phrase n'a lu
 * aucun jour (« demain » l'emporte) ; `quand`, choisi à la main dans « Quand », l'emporte sur la phrase.
 */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, partagé avec FeuilleSaisie et testé directement (D-ENF22)
export function construireLigne(ligne, { cid, quand, quandDefaut, priorites }) {
  const champs = { ...(ligne.champs ?? {}) }
  if (champs.nouveau_projet) {
    const nom = champs.nouveau_projet.nom
    champs.nouveau_projet = { ...champs.nouveau_projet, priorite: priorites?.[nom] ?? champs.nouveau_projet.priorite }
  }
  const phraseDitQuand = CHAMPS_QUAND.some((cle) => Boolean(champs[cle]))
  return {
    index: ligne.index,
    collage: ligne.collage,
    client_id: `${cid}:${ligne.index}`,
    titre: ligne.titre,
    ...(quandDefaut && !phraseDitQuand ? quandDefaut : {}),
    ...champs,
    ...(quand ?? {}),
  }
}

const estCochee = (ligne, modifs) => modifs.cochees[ligne.index] ?? ligne.cochee !== false

/** Les lignes à envoyer, dans l'ordre de la liste : cochées seulement, points repliés dans la check-list. */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, testé directement (D-ENF22)
export function lignesACreer(apercu, modifs, { cid, priorites }) {
  const lignes = apercu?.lignes ?? []
  const sorties = []
  const enTete = (apercu?.projets_communs ?? []).filter((c) => modifs.enTache[c.collage] && modifs.cochees[`p${c.collage}`] !== false)
  enTete.forEach((c) => {
    sorties.push({
      index: 10000 + c.collage, collage: c.collage, client_id: `${cid}:p${c.collage}`, titre: modifs.titres[`p${c.collage}`] ?? c.nom,
    })
  })
  lignes.forEach((ligne) => {
    const point = ligne.etape_de != null && !modifs.sousTaches[ligne.etape_de]
    if (point || !estCochee(ligne, modifs)) return
    const base = construireLigne({ ...ligne, titre: modifs.titres[ligne.index] ?? ligne.titre }, { cid, priorites })
    if (modifs.enTache[ligne.collage]) { delete base.nouveau_projet; delete base.projet_id }
    const points = lignes.filter((l) => l.etape_de === ligne.index)
    if (points.length > 0 && !modifs.sousTaches[ligne.index]) {
      base.checklist = points.map((p) => modifs.titres[p.index] ?? p.titre)
    }
    sorties.push(base)
  })
  return sorties
}

function compterProjets(apercu, modifs) {
  const noms = new Set((apercu?.projets_nouveaux ?? []).map((p) => p.nom))
  ;(apercu?.projets_communs ?? []).forEach((c) => { if (!modifs.enTache[c.collage]) noms.add(c.nom) })
  return noms.size
}

export default function ColleListes({
  apercu, cid, priorites = {}, onPriorite, onCreer, onCollerEncore, envoi = false, erreur = '',
}) {
  const [modifs, setModifs] = useState(MODIFS_VIDES)
  const maj = (cle, index, valeur) => setModifs((m) => ({ ...m, [cle]: { ...m[cle], [index]: valeur } }))

  const aEnvoyer = useMemo(() => lignesACreer(apercu, modifs, { cid, priorites }), [apercu, modifs, cid, priorites])
  const nbProjets = compterProjets(apercu, modifs)
  const vide = aEnvoyer.length === 0

  return (
    <div className="colle-listes">
      <ApercuListe
        apercu={apercu}
        modifs={modifs}
        priorites={priorites}
        nbCreer={aEnvoyer.length}
        nbProjets={nbProjets}
        onCocher={(index, valeur) => maj('cochees', index, valeur)}
        onTitre={(index, valeur) => maj('titres', index, valeur)}
        onEnTache={(collage) => maj('enTache', collage, !modifs.enTache[collage])}
        onSousTaches={(index) => maj('sousTaches', index, !modifs.sousTaches[index])}
        onPriorite={onPriorite}
      />
      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}
      <div className="feuille-pied">
        <button type="button" className="bouton second" onClick={onCollerEncore}>Coller encore</button>
        <button
          type="button"
          className="bouton plein large"
          aria-disabled={vide || envoi || undefined}
          onClick={() => { if (!vide && !envoi) onCreer?.(aEnvoyer) }}
        >
          {`Créer ${accord(aEnvoyer.length, 'tâche')}`}
        </button>
      </div>
    </div>
  )
}
