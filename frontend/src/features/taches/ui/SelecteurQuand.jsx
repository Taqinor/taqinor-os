import { useEffect, useId, useRef, useState } from 'react'
import { aujourdhuiIso, jourNomme } from '../lib/textes'

/* ============================================================================
   TCH82 — Sélecteur « Quand » (textes.md §2.4 ; R3-067 : Aujourd'hui · Demain · Ce soir · Reporter à
   {jour} (seulement s'il n'est pas demain) · Calendrier… · Plus tard · Sans jour) + l'heure. Un seul composant,
   posé dans la feuille de saisie, la fiche (TCH84) et À trier (« Choisir un jour »).

   La valeur est celle que `planifier/` et `saisie-rapide/` lisent :
     { jour_prevu: 'AAAA-MM-JJ' | null, moment: '' | 'soir', heure_debut: 'HH:MM' | null, quelque_jour: bool }
   Rien n'est corrigé d'office : une date passée ou un jour non travaillé se pose tel quel, c'est
   le serveur qui avertit. Pas de jour = pas d'heure (« Une heure demande un jour prévu. »).
   Maquettes : composants-5.html, composants-6.html.
   ========================================================================== */

// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export const QUAND_VIDE = { jour_prevu: null, moment: '', heure_debut: null, quelque_jour: false }

/** `iso` + `n` jours, en ISO (calcul en UTC : jamais décalé par l'heure d'été). */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export function ajouterJours(iso, n) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  if (!m) return null
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + n))
  return d.toISOString().split('T')[0]
}

/** R2-041/R2-042 — vrai pour une date ENTIÈRE (`AAAA-MM-JJ`, année ≥ 1900) : pendant la frappe au clavier le champ
 *  date rend déjà « 0002-11-27 » au premier chiffre de l'année, qui partait au serveur (400). */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé (D-ENF22)
export function dateComplete(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso ?? ''))
  return Boolean(m) && Number(m[1]) >= 1900
}

/** Valeur tapée dans un champ, gardée LOCALEMENT tant qu'on n'en sort pas ; elle cède la place à la valeur reçue
 *  dès que celle-ci change (réponse du serveur). `{ pour, valeur }` : la valeur reçue au moment de la frappe.
 *  R3-060 — la frappe vit aussi dans une ref (lue au DÉMONTAGE, où l'état du dernier rendu n'est plus sûr) ; « déjà
 *  écrite » y est noté tout de suite : la sortie du champ puis le démontage n'écrivent jamais deux fois. */
function useFrappe(recue) {
  const [frappe, setFrappe] = useState(null)
  const derniere = useRef(null)
  const affichee = frappe && frappe.pour === recue ? frappe.valeur : recue
  const taper = (valeur) => {
    derniere.current = { pour: recue, valeur, envoyee: false }
    setFrappe(derniere.current)
  }
  /** La valeur à écrire (une seule fois), ou `undefined` s'il n'y a rien de neuf. */
  const aEcrire = () => {
    const vivante = derniere.current
    if (!vivante || vivante.envoyee || vivante.pour !== recue || vivante.valeur === recue) return undefined
    derniere.current = { ...vivante, envoyee: true }
    setFrappe(derniere.current)
    return vivante.valeur
  }
  return [affichee, taper, aEcrire]
}

function tuileCourante(valeur, { aujourdhui, demain, reporterA }) {
  if (valeur.quelque_jour) return 'reserve'
  if (!valeur.jour_prevu) return 'sans'
  if (valeur.jour_prevu === aujourdhui) return valeur.moment === 'soir' ? 'soir' : 'aujourdhui'
  if (valeur.jour_prevu === demain) return 'demain'
  if (reporterA && valeur.jour_prevu === reporterA) return 'reporter'
  return 'choisir'
}

export default function SelecteurQuand({
  valeur = QUAND_VIDE,
  onChoisir,
  aujourdhui = aujourdhuiIso(),
  reporterA = null,
}) {
  const idAide = useId()
  const [dateOuverte, setDateOuverte] = useState(false)
  const demain = ajouterJours(aujourdhui, 1)
  const courante = tuileCourante({ ...QUAND_VIDE, ...valeur }, { aujourdhui, demain, reporterA })
  const choisir = (suite) => onChoisir?.({ ...QUAND_VIDE, ...suite })
  // R2-041 — l'heure et le jour tapés restent ici tant qu'on est dans le champ : écrire à chaque frappe valide
  // enregistrait « 11:04 » pour « 1145 » (la fiche redessinait et le 4e chiffre se perdait)
  const [heureAffichee, taperHeure, heureAEcrire] = useFrappe(valeur.heure_debut ?? '')
  const [jourAffiche, taperJour, jourAEcrire] = useFrappe(valeur.jour_prevu ?? '')
  const gardeHeure = (jour) => (jour ? heureAffichee || null : null)

  const tuiles = [
    { cle: 'aujourdhui', titre: "Aujourd'hui", detail: jourNomme(aujourdhui, aujourdhui) || '', pose: () => choisir({ jour_prevu: aujourdhui, heure_debut: gardeHeure(aujourdhui) }) },
    { cle: 'demain', titre: 'Demain', detail: jourNomme(demain, aujourdhui), pose: () => choisir({ jour_prevu: demain, heure_debut: gardeHeure(demain) }) },
    { cle: 'soir', titre: 'Ce soir', detail: '', pose: () => choisir({ jour_prevu: aujourdhui, moment: 'soir', heure_debut: gardeHeure(aujourdhui) }) },
  ]
  // R3-067 (choix C-22) — « Reporter à ven. 20 » qui tombe DEMAIN disait deux fois le même jour à côté de « Demain
  // ven. 20 » : une seule tuile, « Demain » (prévue aujourd'hui, la poser demain EST le report : même écriture)
  if (reporterA && reporterA !== demain) {
    tuiles.push({
      cle: 'reporter',
      titre: `Reporter à ${jourNomme(reporterA, aujourdhui)}`,
      detail: '',
      pose: () => choisir({ jour_prevu: reporterA, heure_debut: gardeHeure(reporterA) }),
    })
  }
  tuiles.push(
    { cle: 'choisir', titre: 'Calendrier…', detail: courante === 'choisir' ? jourNomme(valeur.jour_prevu, aujourdhui) : '', pose: () => setDateOuverte(true) },
    { cle: 'reserve', titre: 'Plus tard', detail: '', pose: () => { setDateOuverte(false); choisir({ quelque_jour: true }) } },
    { cle: 'sans', titre: 'Sans jour', detail: '', pose: () => { setDateOuverte(false); choisir({}) } },
  )

  const surTuile = (tuile) => () => {
    if (tuile.cle !== 'choisir') setDateOuverte(false)
    tuile.pose()
  }
  // à la sortie du champ (sur l'iPhone, la roue se referme : c'est aussi une sortie) ou à Entrée
  const ecrireJour = () => {
    const jour = jourAEcrire()
    if (jour !== undefined && dateComplete(jour)) choisir({ jour_prevu: jour, heure_debut: heureAffichee || null })
  }
  const ecrireHeure = () => {
    const h = heureAEcrire()
    if (h === undefined || !valeur.jour_prevu) return
    choisir({ jour_prevu: valeur.jour_prevu, moment: valeur.moment ?? '', heure_debut: h || null })
  }
  const surEntree = (ecrire) => (e) => { if (e.key === 'Enter') { e.preventDefault(); ecrire() } }

  // R3-060 — démonté avec une frappe pas encore écrite (retour arrière, fiche changée, éditeur replié d'un toucher qui
  // n'a pas quitté le champ) : elle part quand même, en UNE écriture (jour entier + heure), jamais en silence perdue
  const auDemontage = useRef(null)
  useEffect(() => {
    auDemontage.current = () => {
      const jour = jourAEcrire()
      const h = heureAEcrire()
      if (jour !== undefined && dateComplete(jour)) {
        choisir({ jour_prevu: jour, heure_debut: h !== undefined ? h || null : heureAffichee || null })
      } else if (h !== undefined && valeur.jour_prevu) {
        choisir({ jour_prevu: valeur.jour_prevu, moment: valeur.moment ?? '', heure_debut: h || null })
      }
    }
  })
  useEffect(() => () => auDemontage.current?.(), [])

  const montrerDate = dateOuverte || courante === 'choisir'
  return (
    <div className="selecteur-quand">
      <div className="quand-tuiles" role="radiogroup" aria-label="Quand je la fais">
        {tuiles.map((tuile) => (
          <button
            key={tuile.cle}
            type="button"
            role="radio"
            aria-checked={courante === tuile.cle || (tuile.cle === 'choisir' && dateOuverte)}
            className="quand-tuile"
            onClick={surTuile(tuile)}
          >
            <b>{tuile.titre}</b>
            {tuile.detail ? <span className="chiffres">{tuile.detail}</span> : null}
          </button>
        ))}
      </div>
      {montrerDate ? (
        <label className="champ-etiquette">
          <span>Jour</span>
          <input
            type="date"
            className="champ"
            aria-label="Choisir un jour"
            value={jourAffiche}
            onChange={(e) => taperJour(e.target.value)}
            onBlur={ecrireJour}
            onKeyDown={surEntree(ecrireJour)}
          />
        </label>
      ) : null}
      <label className="champ-etiquette">
        <span>Heure</span>
        <input
          type="time"
          className="champ chiffres"
          aria-label="Heure"
          aria-describedby={valeur.jour_prevu ? undefined : idAide}
          disabled={!valeur.jour_prevu}
          value={heureAffichee}
          onChange={(e) => taperHeure(e.target.value)}
          onBlur={ecrireHeure}
          onKeyDown={surEntree(ecrireHeure)}
        />
      </label>
      {valeur.jour_prevu ? null : <p id={idAide} className="aide-champ">Une heure demande un jour prévu.</p>}
    </div>
  )
}
