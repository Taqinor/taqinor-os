import { useEffect, useId, useRef } from 'react'
import { X } from 'lucide-react'

/* ============================================================================
   TCH82 — Champ de saisie d'une tâche : UNE phrase, jamais corrigée ni refusée (le texte tapé
   reste exactement tel quel ; l'analyse n'écrit que des PUCES dessous). Sous le champ :
     · les puces de jetons lus (`jetons` de `saisie-rapide/` aperçu), chacune avec son « × »
       (« Retirer {libellé} ») : retirer = `onIgnorer({ type, source })`, le mot reste dans le titre ;
     · pour un projet qui n'existe pas, la puce pointillée « Nouveau projet : {nom} » et sa
       priorité Haute · Moyenne · Basse (Moyenne par défaut) ;
     · les alertes lues (`AlerteSaisie`, textes.md §2.3) ;
     · l'erreur du champ, SOUS le champ (textes.md §2.16).
   iPhone : `<textarea>` natif (pas de contenteditable), 16 px mini (pas de zoom à la mise au point),
   `enterKeyHint="send"`. Entrée envoie quand le texte tient sur une ligne ; Maj+Entrée ou le
   collage d'une liste gardent les retours à la ligne.
   Maquettes : ecran-saisie.html, ecran-saisie-nouveau.html, etat-erreur-champ.html.
   ========================================================================== */

export const INDICATION = 'Ajouter une tâche… demain, 10 h, #projet, !!'

// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export const PRIORITES_PROJET = [['Haute', 3], ['Moyenne', 2], ['Basse', 1]]

const TYPES_LUS = {
  jour: 'jour', heure: 'heure', moment: 'moment', echeance: 'échéance', quelque_jour: 'jour',
  projet: 'projet', section: 'étape', priorite: 'priorité', etiquette: 'étiquette', duree: 'durée',
  recurrence: 'répétition', rappel: 'rappel',
}

/** Phrase d'une alerte (textes.md §2.3) ; `alerte` = `{ code, ...variables }` ou le code seul. */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export function phraseAlerte(alerte) {
  const a = typeof alerte === 'string' ? { code: alerte } : (alerte ?? {})
  const nom = a.nom ?? a.projet ?? a.texte ?? ''
  const cite = `« ${nom} »`
  if (a.code?.startsWith('deux_')) {
    const type = TYPES_LUS[a.code.slice(5)] ?? a.code.slice(5)
    return `Deux ${type} lus : le second reste dans le titre.`
  }
  switch (a.code) {
    case 'date_passee': return a.date ? `Date passée : ${a.date}.` : 'Date passée.'
    case 'heure_passee': return a.heure ? `${a.heure} est passée${a.jour ? ` : prévue ${a.jour}` : ''}.` : 'Cette heure est passée.'
    case 'plusieurs_projets': return `Plusieurs projets s'appellent ${cite} : le premier est choisi.`
    case 'projet_archive': return `${nom ? cite : 'Ce projet'} est archivé : la tâche ira dans À trier.`
    case 'date_invalide': return `${nom ? cite : 'Ce texte'} n'est pas une date : laissé dans le titre.`
    case 'duree_hors_bornes': return `Une durée va de 5 min à 16 h : ${nom ? cite : 'le texte'} reste dans le titre.`
    default: return ''
  }
}

function PuceJeton({ jeton, onIgnorer }) {
  const nouveau = jeton.type === 'projet' && jeton.valeur?.nouveau
  const classe = nouveau ? 'puce nouveau' : jeton.type === 'projet' ? 'puce projet-lu' : 'puce lue'
  return (
    <span className={classe} data-jeton={jeton.type}>
      <span className="chiffres">{jeton.libelle}</span>
      <button
        type="button"
        className="retirer"
        aria-label={`Retirer ${jeton.libelle}`}
        onClick={() => onIgnorer?.({ type: jeton.type, source: jeton.source })}
      >
        <X aria-hidden="true" />
      </button>
    </span>
  )
}

function PrioriteProjet({ nom, valeur, onChoisir }) {
  return (
    <div className="segmente" role="radiogroup" aria-label={`Priorité du projet ${nom}`}>
      {PRIORITES_PROJET.map(([libelle, niveau]) => (
        <button
          key={niveau}
          type="button"
          role="radio"
          aria-checked={valeur === niveau}
          onClick={() => onChoisir?.(nom, niveau)}
        >
          {libelle}
        </button>
      ))}
    </div>
  )
}

export default function ChampSaisie({
  valeur,
  onChange,
  jetons = [],
  alertes = [],
  erreur = '',
  nouveauxProjets = [],
  onPrioriteProjet,
  onIgnorer,
  onSoumettre,
  autoFocus = true,
  indication = INDICATION,
}) {
  const idErreur = useId()
  const champ = useRef(null)
  // la feuille qui l'accueille met son focus sur sa poignée à l'ouverture : on reprend la main juste après
  useEffect(() => {
    if (!autoFocus) return undefined
    const id = requestAnimationFrame(() => champ.current?.focus())
    return () => cancelAnimationFrame(id)
  }, [autoFocus])
  const phrases = alertes.map(phraseAlerte).filter(Boolean)
  const surTouche = (e) => {
    if (e.key !== 'Enter' || e.nativeEvent?.isComposing) return
    const seule = !String(valeur ?? '').includes('\n')
    if ((seule && !e.shiftKey) || e.metaKey || e.ctrlKey) {
      e.preventDefault()
      onSoumettre?.()
    }
  }

  return (
    <div className="champ-saisie">
      <textarea
        className="saisie-champ"
        aria-label="Ajouter une tâche"
        aria-invalid={erreur ? true : undefined}
        aria-describedby={erreur ? idErreur : undefined}
        placeholder={indication}
        rows={2}
        enterKeyHint="send"
        autoComplete="off"
        autoCapitalize="sentences"
        spellCheck="true"
        ref={champ}
        value={valeur}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={surTouche}
      />
      {erreur ? <p id={idErreur} className="erreur-champ" role="alert">{erreur}</p> : null}
      {jetons.length > 0 ? (
        <div className="puces saisie" aria-label="Ce que j'ai lu">
          {jetons.map((jeton) => (
            <PuceJeton key={`${jeton.type}:${jeton.debut}:${jeton.source}`} jeton={jeton} onIgnorer={onIgnorer} />
          ))}
        </div>
      ) : null}
      {nouveauxProjets.map((projet) => (
        <PrioriteProjet key={projet.nom} nom={projet.nom} valeur={projet.priorite} onChoisir={onPrioriteProjet} />
      ))}
      {phrases.length > 0 ? (
        <ul className="alertes-saisie" aria-label="À savoir">
          {phrases.map((phrase) => <li key={phrase}>{phrase}</li>)}
        </ul>
      ) : null}
    </div>
  )
}
