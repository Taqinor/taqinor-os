// QJR90 — `useSizingMoteur` : le hook qui enrobe `useEtudeHorairePreview` et
// possède LA GARDE DE RÉPONSE PÉRIMÉE **SUR LES DEUX CHEMINS**.
//
// Patron maison (`etudeHorairePreview.js`) : la décision vit dans le module
// PUR à côté (`useSizingMoteurPur.js`, testable sous `node --test`) ; ce
// fichier ne fait qu'enchaîner le hook réseau, suivre la clé du corps EN VOL
// et rendre la décision. Aucune règle métier n'est écrite ici.
//
// La branche d'ÉCHEC de `DevisGenerator.jsx:1076` ferme aujourd'hui le drapeau
// d'attente et épingle un refus obsolète parce que rien ne dit QUEL corps a
// échoué : `useEtudeHorairePreview` n'expose `corpsServi` que pour le succès.
// Ce hook comble le trou en mémorisant la clé du corps au lancement de
// l'appel, puis en l'attribuant à l'erreur qui en revient.
//
// Hook AJOUTÉ TESTÉ (via sa moitié pure), IMPORTÉ PAR PERSONNE (vague M4).
import { useEffect, useRef, useState } from 'react'
import { useEtudeHorairePreview } from '../../etudeHorairePreview'
import { decisionSizing } from './useSizingMoteurPur'

export { decisionSizing, motifRefus, REFUS_GENERIQUE } from './useSizingMoteurPur'

/**
 * @param corps  corps de l'aperçu moteur horaire (`construireCorpsPreview`),
 *               ou `null` quand il n'y a rien à demander.
 * @param etat   `{ attente, toucheNbPanneaux }` — l'état du reducer QJR87.
 * @returns `{ decision, donnees, chargement, erreur }` — `decision` est la
 *          sortie de `decisionSizing`, à traduire en dispatch par l'appelant
 *          (`MOTEUR_A_REPONDU` / `MOTEUR_A_REFUSE`) : le hook ne mute rien.
 */
export function useSizingMoteur(corps, { attente = false, toucheNbPanneaux = false } = {}) {
  const { donnees, chargement, erreur, corpsServi } = useEtudeHorairePreview(corps)
  const cleCourante = corps ? JSON.stringify(corps) : null
  // Clé du corps EN VOL : posée au départ de l'appel, attribuée à l'erreur
  // qui en revient (le hook réseau ne l'expose que pour le succès).
  const cleEnVol = useRef(null)
  const [cleErreur, setCleErreur] = useState(null)

  useEffect(() => {
    if (chargement) cleEnVol.current = cleCourante
  }, [chargement, cleCourante])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- attribue l'échec au corps qui l'a produit
    setCleErreur(erreur ? cleEnVol.current : null)
  }, [erreur])

  return {
    decision: decisionSizing({
      attente,
      toucheNbPanneaux,
      chargement,
      donnees,
      erreur,
      cleServie: corpsServi,
      cleErreur,
      cleCourante,
    }),
    donnees,
    chargement,
    erreur,
  }
}
