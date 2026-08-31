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
// QJR206 — la garde de péremption s'indexait sur `cleCourante`, le corps NON
// débouncé : `useEtudeHorairePreview` n'envoie au réseau que le corps
// DÉBOUNCÉ (~500 ms, `corpsServi`, exposé au succès SEULEMENT). Pendant la
// fenêtre de debounce d'une requête déjà en vol, `cleCourante` continue de
// bouger à chaque frappe alors qu'AUCUNE requête n'est encore partie pour ce
// nouveau corps — mémoriser `cleCourante` comme « clé en vol » attribue donc
// l'échec d'une requête plus ANCIENNE au corps affiché à l'écran, ce qui
// épingle un refus pour une requête jamais partie et ferme l'attente pour
// de bon. Ce hook n'a pas accès au debounce interne de
// `useEtudeHorairePreview` (Files: de cette tâche ne le touche pas) : on en
// dérive un ÉQUIVALENT localement, même délai, sur le même flux `corps`.
//
// Hook AJOUTÉ TESTÉ (via sa moitié pure), IMPORTÉ PAR PERSONNE (vague M4).
import { useEffect, useRef, useState } from 'react'
import { useEtudeHorairePreview } from '../../etudeHorairePreview'
import { useDebouncedValue } from '../../../../lib/debounce'
import { decisionSizing } from './useSizingMoteurPur'

// QJR206 — PURE (aucun hook) : calcule la clé « en vol » à mémoriser pour ce
// rendu. Tant que le chargement est en cours, on retient la clé DÉBOUNCÉE
// (celle qui correspond à ce que `useEtudeHorairePreview` a réellement — ou
// est sur le point de — envoyer), jamais la clé courante non débouncée.
export function cleEnVolPourChargement(chargement, cleDebouncee, precedente) {
  return chargement ? cleDebouncee : precedente
}

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
  // QJR206 — même délai que `useEtudeHorairePreview` (500 ms) : dérivé
  // localement pour suivre la clé RÉELLEMENT (ou bientôt) envoyée, pas celle
  // affichée à l'écran à l'instant T.
  const cleDebouncee = useDebouncedValue(cleCourante, 500)
  // Clé du corps EN VOL : posée au départ de l'appel, attribuée à l'erreur
  // qui en revient (le hook réseau ne l'expose que pour le succès).
  const cleEnVol = useRef(null)
  const [cleErreur, setCleErreur] = useState(null)

  useEffect(() => {
    cleEnVol.current = cleEnVolPourChargement(chargement, cleDebouncee, cleEnVol.current)
  }, [chargement, cleDebouncee])

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
