import { useState } from 'react'
import { frenchError } from '../../../lib/frenchError'
import { aujourdhuiIso, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH107 — « Mes jours » de Mon rythme (replié par défaut) : jours travaillés, jours courts
   (un de moins), congés (« Du … au … »), temps disponible par jour. Chaque réglage est une
   PRÉFÉRENCE dite (`POST preferences/`, clés `jours_travailles`, `jours_courts`, `conges`,
   `capacite_jour_min` — donnees.md §2.11) : l'écran envoie `onPoser(cle, valeur)` (une promesse)
   et le parent remplace son RYTHME par la réponse. Une erreur s'affiche SOUS le champ fautif,
   avec le message du serveur ; la saisie reste là. Textes : textes.md §2.11 « Mes jours ».
   Maquette : docs/taches/maquettes/rythme.html (ligne repliée « Mes jours »).
   ========================================================================== */

const JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
const TOUS_LES_JOURS = '1111111'
const UN_JOUR_AU_MOINS = 'Garde au moins un jour travaillé.'
const FIN_AVANT_DEBUT = 'La date de fin précède la date de début.'
const ENTRE_30_ET_720 = 'Entre 30 et 720 minutes.'
const CAPACITE_MIN = 30
const CAPACITE_MAX = 720

const valeurDe = (preferences, cle) => (preferences ?? []).find((p) => p.cle === cle)?.valeur

/** Le message du serveur sous `valeur` (ou sous le champ nommé), sinon une phrase lisible. */
function messageDe(err) {
  const brut = err?.response?.data
  const champ = brut?.valeur ?? brut?.cle
  if (Array.isArray(champ) && champ.length > 0) return String(champ[0])
  return frenchError(err, 'Réessaie dans un instant.')
}

function ErreurChamp({ id, texte }) {
  return texte ? <p id={id} className="es-erreur" role="alert">{texte}</p> : null
}

function Pastilles({ nom, actives, onBasculer, desactives = new Set() }) {
  return (
    <div className="ep-jours" role="group" aria-label={nom}>
      {JOURS.map((jour, rang) => (
        <button
          key={jour}
          type="button"
          className="puce ep-jour-puce"
          aria-pressed={actives.has(rang)}
          disabled={desactives.has(rang)}
          onClick={() => onBasculer(rang)}
        >
          {jour}
        </button>
      ))}
    </div>
  )
}

/** « Mes jours » allume les jours RÉELLEMENT travaillés (`joursTravailles`, servi par `rythme/` : les jours dits ∩
 *  le calendrier de la société, R2-123). Un jour dit travaillé mais éteint par la société n'est pas modifiable ici :
 *  il est grisé et nommé. Sans la valeur servie (réponse d'une autre route), les jours dits. */
function JoursTravailles({ preferences, joursTravailles, onPoser }) {
  const [erreur, setErreur] = useState('')
  const dit = valeurDe(preferences, 'jours_travailles') ?? TOUS_LES_JOURS
  const effectif = joursTravailles ?? dit
  const actifs = new Set([...effectif].flatMap((c, i) => (c === '1' ? [i] : [])))
  const societe = new Set(JOURS.flatMap((_, i) => (dit[i] === '1' && effectif[i] !== '1' ? [i] : [])))

  const basculer = async (rang) => {
    const suite = JOURS.map((_, i) => ((i === rang ? !actifs.has(i) : dit[i] === '1') ? '1' : '0')).join('')
    if (!JOURS.some((_, i) => (i === rang ? !actifs.has(i) : actifs.has(i)))) { setErreur(UN_JOUR_AU_MOINS); return }
    setErreur('')
    try { await onPoser('jours_travailles', suite) } catch (err) { setErreur(messageDe(err)) }
  }

  return (
    <div className="ep-groupe">
      <h3 className="ep-groupe-titre">Jours travaillés</h3>
      <Pastilles nom="Jours travaillés" actives={actifs} onBasculer={basculer} desactives={societe} />
      {societe.size > 0 ? (
        <p className="ep-source">{`${[...societe].map((i) => JOURS[i]).join(', ')} : non travaillé${societe.size > 1 ? 's' : ''} dans ta société.`}</p>
      ) : null}
      <ErreurChamp id="err-jours-travailles" texte={erreur} />
    </div>
  )
}

function JoursCourts({ preferences, onPoser }) {
  const [erreur, setErreur] = useState('')
  const courts = new Set(valeurDe(preferences, 'jours_courts') ?? [])

  const basculer = async (rang) => {
    const suite = JOURS.flatMap((_, i) => ((i === rang ? !courts.has(i) : courts.has(i)) ? [i] : []))
    setErreur('')
    try { await onPoser('jours_courts', suite) } catch (err) { setErreur(messageDe(err)) }
  }

  return (
    <div className="ep-groupe">
      <h3 className="ep-groupe-titre">Jours courts (un de moins)</h3>
      <Pastilles nom="Jours courts" actives={courts} onBasculer={basculer} />
      <ErreurChamp id="err-jours-courts" texte={erreur} />
    </div>
  )
}

function Conges({ preferences, onPoser, aujourdhui }) {
  const [erreur, setErreur] = useState('')
  const [du, setDu] = useState('')
  const [au, setAu] = useState('')
  const conges = valeurDe(preferences, 'conges') ?? []

  const envoyer = async (suite, apres) => {
    setErreur('')
    try { await onPoser('conges', suite); apres?.() } catch (err) { setErreur(messageDe(err)) }
  }
  const ajouter = () => {
    if (!du || !au) { setErreur('Requis.'); return }
    if (au < du) { setErreur(FIN_AVANT_DEBUT); return }
    envoyer([...conges, { du, au }], () => { setDu(''); setAu('') })
  }

  return (
    <div className="ep-groupe">
      <h3 className="ep-groupe-titre">Congés</h3>
      <ul className="ep-conges">
        {conges.map((periode) => (
          <li key={`${periode.du}-${periode.au}`}>
            <span>{`Du ${jourNomme(periode.du, aujourdhui)} au ${jourNomme(periode.au, aujourdhui)}`}</span>
            <button
              type="button"
              className="bouton lien"
              aria-label={`Retirer le congé du ${periode.du} au ${periode.au}`}
              onClick={() => envoyer(conges.filter((c) => c !== periode))}
            >
              Retirer
            </button>
          </li>
        ))}
      </ul>
      <div className="ep-champs">
        <label>Du <input type="date" value={du} onChange={(e) => setDu(e.target.value)} aria-describedby="err-conges" /></label>
        <label>Au <input type="date" value={au} onChange={(e) => setAu(e.target.value)} aria-describedby="err-conges" /></label>
        <button type="button" className="bouton second" onClick={ajouter}>Ajouter</button>
      </div>
      <ErreurChamp id="err-conges" texte={erreur} />
    </div>
  )
}

function TempsDisponible({ preferences, onPoser }) {
  const enregistre = valeurDe(preferences, 'capacite_jour_min')
  const [saisie, setSaisie] = useState(enregistre == null ? '' : String(enregistre))
  const [erreur, setErreur] = useState('')

  const enregistrer = async () => {
    const minutes = Number(saisie.trim().replace(',', '.'))
    if (!saisie.trim() || !Number.isFinite(minutes) || minutes < CAPACITE_MIN || minutes > CAPACITE_MAX) {
      setErreur(ENTRE_30_ET_720)
      return
    }
    setErreur('')
    try { await onPoser('capacite_jour_min', Math.round(minutes)) } catch (err) { setErreur(messageDe(err)) }
  }

  return (
    <div className="ep-groupe">
      <h3 className="ep-groupe-titre"><label htmlFor="capacite-jour">Temps disponible par jour</label></h3>
      <div className="ep-champs">
        <input
          id="capacite-jour"
          className="es-champ"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={saisie}
          onChange={(e) => setSaisie(e.target.value)}
          aria-invalid={Boolean(erreur) || undefined}
          aria-describedby="err-capacite"
        />
        <span aria-hidden="true">min</span>
        <button type="button" className="bouton second" onClick={enregistrer}>Enregistrer</button>
      </div>
      <ErreurChamp id="err-capacite" texte={erreur} />
    </div>
  )
}

/** Les quatre réglages de « Mes jours » ; `preferences` = le tableau du RYTHME. */
export default function MesJours({ preferences, joursTravailles, onPoser, aujourdhui = aujourdhuiIso() }) {
  return (
    <div className="ep-mes-jours">
      <JoursTravailles preferences={preferences} joursTravailles={joursTravailles} onPoser={onPoser} />
      <JoursCourts preferences={preferences} onPoser={onPoser} />
      <Conges preferences={preferences} onPoser={onPoser} aujourdhui={aujourdhui} />
      <TempsDisponible key={String(valeurDe(preferences, 'capacite_jour_min') ?? '')} preferences={preferences} onPoser={onPoser} />
    </div>
  )
}
