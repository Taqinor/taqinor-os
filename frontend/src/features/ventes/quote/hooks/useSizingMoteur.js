// QJR90 — `useSizingMoteur` : le hook qui enrobe `useEtudeHorairePreview` et
// possède LA GARDE DE RÉPONSE PÉRIMÉE **SUR LES DEUX CHEMINS**.
//
// Patron maison (`etudeHorairePreview.js`) : la décision vit dans le module
// PUR à côté (`useSizingMoteurPur.js`, testable sous `node --test`) ; ce
// fichier ne fait qu'enchaîner le hook réseau et rendre la décision. Aucune
// règle métier n'est écrite ici.
//
// Une branche d'ÉCHEC sans clé épinglerait un refus obsolète (rien ne dirait
// QUEL corps a échoué) : `useEtudeHorairePreview` sert `corpsServi` pour le
// succès et `corpsEchoue` pour l'échec, et ce hook les compare au corps
// affiché.
//
// QJR206 / QJR644 — la garde de péremption s'indexe sur la clé RÉELLEMENT
// envoyée (débouncée), jamais sur `cleCourante`. Depuis QJR644 elle vient du
// hook d'aperçu lui-même (`corpsEchoue`, la clé dont la requête a échoué) :
// UNE seule temporisation de 500 ms, plus de second debounce local.
//
// Hook testé via sa moitié pure ; importé par `DevisGenerator.jsx`.
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
  const {
    donnees, chargement, erreur, corpsServi, corpsEchoue,
  } = useEtudeHorairePreview(corps)
  const cleCourante = corps ? JSON.stringify(corps) : null
  // QJR644 — la clé du corps ÉCHOUÉ est servie par le hook d'aperçu.
  const cleErreur = erreur ? (corpsEchoue ?? null) : null

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
