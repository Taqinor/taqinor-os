import { useId, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import AnneauProgression from '../ui/AnneauProgression'
import { duree } from '../lib/textes'

/* ============================================================================
   TCH77 — La ligne de progression d'Aujourd'hui : « {faites} sur {objectif} · essentiel {ef}/{ep} »,
   « Reprise » le jour d'un retour. R3-020 (M1, C-14) — UNE source par chiffre : tout est lu dans `progression`
   SERVIE (`aujourdhui/`, et la `progression` de chaque réponse d'écriture que la page applique) ; l'écran ne
   recompte rien. « essentiel » = les ★ de la section Essentiel servie (ouvertes, ou faites aujourd'hui).
   Trois modes (textes.md §2.2) : `pousser` « 1 sur 5 · essentiel 0/1 » ; `tenir` « 1 sur 5 · ton
   rythme : 3 à 5 » ; `libre` « 1 faite » (R3-029 : aussi tant que l'objectif est la valeur par défaut). Au toucher :
   « 1 faite sur 5 », la source de l'objectif s'il est par défaut, « Temps : 4 h 30 prévues pour 4 h disponibles ·
   30 min de trop », puis « Mon rythme › ».
   Maquettes : ecran-aujourdhui-matin.html, ecran-aujourdhui-retour.html, ecran-aujourdhui-15h.html.
   ========================================================================== */

/** La seule source d'objectif qui change sa lecture : il n'est pas encore calculé sur la personne. */
const OBJECTIF_PAR_DEFAUT = 'Objectif : valeur par défaut, pas encore calculée sur toi'

/**
 * R3-020 (M6) — le temps du jour en une phrase : « Temps : 4 h 30 prévues pour 4 h disponibles · 30 min de trop »
 * (`minutes_prevues` contre `disponible_minutes`, servis) ; « · 2 sans durée » quand des tâches n'en ont pas ;
 * « Durée totale inconnue… » quand plus de la moitié n'en a pas.
 */
function tempsTexte(progression) {
  const { minutes_prevues: minutes = 0, sans_estimation: sans = 0, prevues = 0, disponible_minutes: dispo = null } = progression
  if (sans > 0 && sans * 2 > prevues) return "Durée totale inconnue : la plupart des tâches n'ont pas de durée."
  if (!minutes && !sans) return ''
  const pour = Number.isFinite(dispo) && dispo > 0 ? ` pour ${duree(dispo)} disponibles` : ''
  const sansDuree = sans ? ` · ${sans} sans durée` : ''
  const trop = Number.isFinite(dispo) && dispo > 0 && minutes > dispo ? ` · ${duree(minutes - dispo)} de trop` : ''
  return `Temps : ${minutes ? duree(minutes) : '0 min'} prévues${pour}${sansDuree}${trop}`
}

/** R3-029 (C-24) — un objectif CHIFFRÉ à lire : ni le mode libre, ni la valeur par défaut d'avant tout usage (« 0 sur 5 »
 *  au premier jour ne dit rien de Reda) ; le chiffre vient au premier objectif calculé ou choisi. */
const objectifChiffre = (objectif) => objectif.mode !== 'libre' && Boolean(objectif.nb) && objectif.source !== 'defaut'

/** Les deux morceaux du texte : le compte (gras) et son détail (doux). */
function textesProgression(objectif, progression) {
  const { faites = 0, essentiel_faites: ef = 0, essentiel_prevues: ep = 0, reprise = false } = progression
  if (reprise) return { compte: 'Reprise', detail: objectifChiffre(objectif) ? ` · objectif ${objectif.nb}` : '' }
  if (!objectifChiffre(objectif)) {
    const compte = `${faites} ${faites >= 2 ? 'faites' : 'faite'}`
    return { compte, detail: '' }
  }
  const compte = `${faites} sur ${objectif.nb}`
  let detail = ''
  if (objectif.mode === 'tenir' && Array.isArray(objectif.zone)) detail = ` · ton rythme : ${objectif.zone[0]} à ${objectif.zone[1]}`
  else if (ep > 0) detail = ` · essentiel ${ef}/${ep}`
  return { compte, detail }
}

/**
 * R3-020 (M1, M6) — UNE phrase pour le compte du jour : « 1 faite sur 5 » (sans objectif chiffré : « 1 faite ») ; plus
 * de « visées » ni de second chiffre « gardées » de la même journée.
 */
function phraseDuJour(objectif, progression) {
  const { faites = 0 } = progression
  const fait = `${faites} ${faites >= 2 ? 'faites' : 'faite'}`
  return objectifChiffre(objectif) ? `${fait} sur ${objectif.nb}` : fait
}

function Faits({ objectif, progression, onRythme }) {
  const lignes = [
    phraseDuJour(objectif, progression),
    objectif.mode !== 'libre' && objectif.nb && objectif.source === 'defaut' ? OBJECTIF_PAR_DEFAUT : '',
    tempsTexte(progression),
  ].filter(Boolean)
  return (
    <div className="progression-faits" role="group" aria-label="Détail de la journée">
      {lignes.map((ligne) => <p key={ligne} className="chiffres">{ligne}</p>)}
      <button type="button" className="bouton lien" onClick={onRythme}>
        Mon rythme<ChevronRight className="i i-16" aria-hidden="true" />
      </button>
    </div>
  )
}

export default function Progression({ donnees, onRythme }) {
  const [ouverte, setOuverte] = useState(false)
  const identifiant = useId()
  const objectif = donnees?.objectif
  const progression = donnees?.progression
  if (!objectif || !progression) return null
  const { compte, detail } = textesProgression(objectif, progression)
  return (
    <>
      <button
        type="button"
        className="progression"
        aria-expanded={ouverte}
        aria-controls={identifiant}
        // axe 4.14 `label-content-name-mismatch` : le nom lu CONTIENT le texte visible, mot pour mot
        aria-label={`${compte}${detail}. Détail de la journée`}
        onClick={() => setOuverte((v) => !v)}
      >
        <AnneauProgression faites={progression.faites} objectif={objectifChiffre(objectif) ? objectif.nb : 0} />
        <span>
          <span className="progression-compte chiffres">{compte}</span>
          {detail ? <span className="progression-detail chiffres">{detail}</span> : null}
        </span>
      </button>
      <div id={identifiant} hidden={!ouverte}>
        {ouverte ? <Faits objectif={objectif} progression={progression} onRythme={onRythme} /> : null}
      </div>
    </>
  )
}
