import { useId, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import AnneauProgression from '../ui/AnneauProgression'
import { duree } from '../lib/textes'

/* ============================================================================
   TCH77 — La ligne de progression d'Aujourd'hui : « {faites} sur {objectif} · essentiel {ef}/{ep} »
   (« faites » et l'objectif lus dans `aujourdhui.json` ; « essentiel » compté sur la section affichée, R2-019),
   « Reprise » le jour d'un retour.
   Trois modes (textes.md §2.2) : `pousser` « 1 sur 5 · essentiel 0/1 » ; `tenir` « 1 sur 5 · ton
   rythme : 3 à 5 » ; `libre` « 1 faite ». Au toucher : « 1 faite sur 5 visées · 6 tâches gardées » (R2-035),
   la source de l'objectif s'il est par défaut, le temps, le temps libre, puis « Mon rythme › ».
   Maquettes : ecran-aujourdhui-matin.html, ecran-aujourdhui-retour.html, ecran-aujourdhui-15h.html.
   ========================================================================== */

/** La seule source d'objectif qui change sa lecture : il n'est pas encore calculé sur la personne. */
const OBJECTIF_PAR_DEFAUT = 'Objectif : valeur par défaut, pas encore calculée sur toi'

/** « 1 h 15 prévues + 2 sans durée » ; « Durée totale inconnue… » quand plus de la moitié n'a pas de durée. */
function chargeTexte(progression) {
  const { minutes_prevues: minutes = 0, sans_estimation: sans = 0, prevues = 0 } = progression
  if (sans > 0 && sans * 2 > prevues) return "Durée totale inconnue : la plupart des tâches n'ont pas de durée."
  if (!minutes && !sans) return ''
  const prevu = minutes ? `${duree(minutes)} prévues` : ''
  const sansDuree = sans ? `${sans} sans durée` : ''
  return [prevu, sansDuree].filter(Boolean).join(' + ')
}

function tempsLibreTexte(progression) {
  const { capacite_minutes: cap, rendez_vous_minutes: rdv = 0, disponible_minutes: dispo } = progression
  if (!cap) return ''
  return rdv > 0
    ? `Temps libre : ${duree(dispo)} (${duree(cap)} moins ${duree(rdv)} de rendez-vous)`
    : `Temps libre : ${duree(cap)}`
}

/** Une ligne encore prévue AUJOURD'HUI à l'écran : pas reportée à un autre jour (estampille « → ven. 20 »). */
const resteAujourdhui = (item, jour) => !(item.jour_prevu && jour && item.jour_prevu > jour)

/**
 * R2-019 — « essentiel f/p » et les gardées se comptent sur ce que l'écran MONTRE : une ★ reportée à demain ne compte
 * plus (le serveur, lui, garde la mesure du plan du matin, `progression.essentiel_*` / `plan_*`, pour le bilan et le
 * rythme). Une essentielle faite est servie deux fois (Essentiel et Faites) : chaque ligne ne compte qu'une fois.
 */
function comptesAffiches(donnees) {
  const jour = donnees.jour
  const essentielles = (donnees.essentiel ?? []).filter((it) => resteAujourdhui(it, jour))
  const vues = new Set()
  const gardees = ['essentiel', 'journee', 'ce_soir', 'faites']
    .flatMap((cle) => donnees[cle] ?? [])
    .filter((it) => it.prevue_au_plan && resteAujourdhui(it, jour))
    .filter((it) => (vues.has(`${it.type}:${it.id}`) ? false : vues.add(`${it.type}:${it.id}`)))
  return {
    essentiel_faites: essentielles.filter((it) => it.statut === 'fait').length,
    essentiel_prevues: essentielles.length,
    gardees: gardees.length,
  }
}

/** Les deux morceaux du texte : le compte (gras) et son détail (doux). */
function textesProgression(objectif, progression) {
  const { faites = 0, essentiel_faites: ef = 0, essentiel_prevues: ep = 0, reprise = false } = progression
  if (reprise) return { compte: 'Reprise', detail: objectif.nb ? ` · objectif ${objectif.nb}` : '', parole: 'Reprise' }
  if (objectif.mode === 'libre' || !objectif.nb) {
    const compte = `${faites} ${faites >= 2 ? 'faites' : 'faite'}`
    return { compte, detail: '', parole: compte }
  }
  const compte = `${faites} sur ${objectif.nb}`
  let detail = ''
  if (objectif.mode === 'tenir' && Array.isArray(objectif.zone)) detail = ` · ton rythme : ${objectif.zone[0]} à ${objectif.zone[1]}`
  else if (ep > 0) detail = ` · essentiel ${ef}/${ep}`
  const parole = `${compte} faites${ep > 0 && objectif.mode !== 'tenir' ? `, essentiel ${ef} sur ${ep}` : ''}`
  return { compte, detail, parole }
}

/**
 * R2-035 — UNE phrase pour le compte du jour : « 1 faite sur 5 visées · 6 tâches gardées » (sans objectif : « 1 faite ·
 * 6 tâches gardées ») ; la source de l'objectif n'est dite que quand elle change sa lecture (valeur par défaut).
 */
function phraseDuJour(objectif, progression, gardees) {
  const { faites = 0 } = progression
  const fait = `${faites} ${faites >= 2 ? 'faites' : 'faite'}`
  const vise = objectif.mode !== 'libre' && objectif.nb ? ` sur ${objectif.nb} ${objectif.nb >= 2 ? 'visées' : 'visée'}` : ''
  const garde = gardees > 0 ? ` · ${gardees} ${gardees >= 2 ? 'tâches gardées' : 'tâche gardée'}` : ''
  return `${fait}${vise}${garde}`
}

function Faits({ objectif, progression, gardees, onRythme }) {
  const lignes = [
    phraseDuJour(objectif, progression, gardees),
    objectif.mode !== 'libre' && objectif.nb && objectif.source === 'defaut' ? OBJECTIF_PAR_DEFAUT : '',
    chargeTexte(progression) ? `Temps : ${chargeTexte(progression)}` : '',
    tempsLibreTexte(progression),
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
  const { gardees, ...essentiel } = comptesAffiches(donnees)
  const { compte, detail, parole } = textesProgression(objectif, { ...progression, ...essentiel })
  return (
    <>
      <button
        type="button"
        className="progression"
        aria-expanded={ouverte}
        aria-controls={identifiant}
        aria-label={`${parole}. Détail de la journée`}
        onClick={() => setOuverte((v) => !v)}
      >
        <AnneauProgression faites={progression.faites} objectif={objectif.mode === 'libre' ? 0 : objectif.nb} />
        <span>
          <span className="progression-compte chiffres">{compte}</span>
          {detail ? <span className="progression-detail chiffres">{detail}</span> : null}
        </span>
      </button>
      <div id={identifiant} hidden={!ouverte}>
        {ouverte ? <Faits objectif={objectif} progression={progression} gardees={gardees} onRythme={onRythme} /> : null}
      </div>
    </>
  )
}
