import { useId, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import AnneauProgression from '../ui/AnneauProgression'
import { duree } from '../lib/textes'

/* ============================================================================
   TCH77 — La ligne de progression d'Aujourd'hui : « {faites} sur {objectif} · essentiel {ef}/{ep} »
   (valeurs lues dans `aujourdhui.json`, jamais recalculées), « Reprise » le jour d'un retour.
   Trois modes (textes.md §2.2) : `pousser` « 1 sur 5 · essentiel 0/1 » ; `tenir` « 1 sur 5 · ton
   rythme : 3 à 5 » ; `libre` « 1 faite ». Au toucher : les faits qui expliquent le chiffre
   (objectif et sa source, gardées faites, temps, temps libre) puis « Mon rythme › ».
   Maquettes : ecran-aujourdhui-matin.html, ecran-aujourdhui-retour.html, ecran-aujourdhui-15h.html.
   ========================================================================== */

const SOURCES = {
  defaut: 'valeur par défaut, pas encore calculée sur toi',
  calcule: 'ta journée type',
  accepte: 'accepté',
  dit: 'ton choix',
}

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

function Faits({ objectif, progression, onRythme }) {
  const { plan_tenues: pt = 0, plan_lignes: pl = 0 } = progression
  const source = objectif.mode === 'tenir' && objectif.source === 'calcule' ? 'ton rythme' : SOURCES[objectif.source]
  const lignes = [
    objectif.nb && source ? `Objectif du jour : ${objectif.nb} (${source})` : '',
    pl > 0 ? `${pt} des ${pl} gardées` : '',
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
  const { compte, detail, parole } = textesProgression(objectif, progression)
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
        {ouverte ? <Faits objectif={objectif} progression={progression} onRythme={onRythme} /> : null}
      </div>
    </>
  )
}
