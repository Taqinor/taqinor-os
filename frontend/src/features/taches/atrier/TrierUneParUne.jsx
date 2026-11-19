import { useState } from 'react'

import SelecteurProjet from '../ui/SelecteurProjet'

/* ============================================================================
   TCH86 — « Trier une par une » (À trier → ⋯) : UNE carte à la fois — le titre, puis
   Aujourd'hui · Demain · Projet… · Plus tard · Supprimer · Suivant ; à la fin « Tout est trié ».
   Le composant ne parle pas au serveur : chaque geste appelle `actions` (les MÊMES que ceux des lignes
   de la liste : un seul chemin d'écriture) puis passe à la tâche suivante ; « Suivant » passe sans rien
   écrire. Rien n'est supprimé sans passer par le bouton nommé « Supprimer » (jamais une touche seule).
   Maquette : docs/taches/maquettes/ecran-a-trier.html.
   ========================================================================== */

export const PHRASE_FIN = 'Tout est trié'

export default function TrierUneParUne({ taches: aTrier, actions, projets, onNouveauProjet, onFin }) {
  // la file est figée à l'ouverture : les gestes retirent les lignes de la liste sans décaler cette carte
  const [taches] = useState(aTrier)
  const [rang, setRang] = useState(0)
  const [projetOuvert, setProjetOuvert] = useState(false)
  const tache = taches[rang] ?? null

  const suivant = () => { setProjetOuvert(false); setRang((r) => r + 1) }
  // le geste part, la carte suivante s'affiche tout de suite (mise à jour optimiste côté page)
  const agir = (geste) => () => { geste(tache); suivant() }

  if (!tache) {
    return (
      <div className="atrier-carte" role="status">
        <p className="vide-phrase">{PHRASE_FIN}</p>
        <button type="button" className="bouton plein" onClick={onFin}>Terminer</button>
      </div>
    )
  }

  return (
    <div className="atrier-carte" role="group" aria-label={`Trier : ${tache.titre}`}>
      <p className="atrier-compteur chiffres">{`${rang + 1} / ${taches.length}`}</p>
      <p className="atrier-carte-titre">{tache.titre}</p>
      <div className="puces">
        <button type="button" className="puce" onClick={agir(actions.aujourdhui)}>Aujourd'hui</button>
        <button type="button" className="puce" onClick={agir(actions.demain)}>Demain</button>
        <button type="button" className="puce" aria-expanded={projetOuvert} onClick={() => setProjetOuvert((o) => !o)}>Projet…</button>
        <button type="button" className="puce" onClick={agir(actions.reserve)}>Plus tard</button>
        <button type="button" className="puce" onClick={agir(actions.supprimer)}>Supprimer</button>
      </div>
      {projetOuvert ? (
        <SelecteurProjet
          projets={projets}
          sansProjet={false}
          onChoisir={(projetId) => { actions.projet(tache, projetId); suivant() }}
          onNouveau={(nom) => { onNouveauProjet(tache, nom); suivant() }}
        />
      ) : null}
      <button type="button" className="bouton second" onClick={suivant}>Suivant</button>
    </div>
  )
}
