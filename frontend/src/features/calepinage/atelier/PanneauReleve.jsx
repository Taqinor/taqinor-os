import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'

/* ============================================================================
   CALX25 — LE RELEVÉ TERRAIN (CHAÎNES DE COTES) SUR UN PANNEAU.
   ----------------------------------------------------------------------------
   CONSTAT. `GET/POST calepinages/<pk>/releve/` (CAL64, `views/releve.py` →
   `services/releve.py` → le solveur pur `core.calepinage.solveur_cotes`,
   modèle `ReleveTerrain` avec azimut boussole et précision) sont servis et
   testés, mais AUCUN écran ne les consomme. Parité Aurora COMPASS — le relevé
   de site est une étape NUMÉROTÉE du parcours de conception :
   https://help.aurorasolar.com/hc/en-us/articles/21240604594963.

   AUCUN CALCUL ICI. Ce panneau saisit les chaînes de cotes et l'azimut, les
   envoie par la porte existante, et affiche EXACTEMENT ce que le solveur
   rend : la géométrie résolue (positions, cote DÉDUITE marquée à confirmer)
   OU, chaîne par chaîne, le POINT DE RUPTURE que le solveur nomme
   (`motif` — jamais un second calcul de fermeture côté écran).

   AUCUNE COTE INVENTÉE EN SILENCE (CAL64). Une chaîne à qui il manque PLUS
   D'UNE cote est refusée AVANT tout envoi réseau (le noyau ne peut déduire
   qu'une seule inconnue) — l'erreur se pose SOUS la chaîne fautive, jamais un
   « non enregistré » générique (règle fondateur du 08/09/2026). Un azimut
   boussole saisi SANS sa précision est refusé de la même façon : la valeur
   nue se lirait comme une mesure exacte.
   ========================================================================== */

const COTE_VIDE = () => ({ nom: '', valeur: '' })
const CHAINE_VIDE = () => ({ nom: '', totalMesure: '', toleranceM: '', cotes: [COTE_VIDE(), COTE_VIDE()] })

function nombreOuNull(brut) {
  if (brut === '' || brut === null || brut === undefined) return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/** Les postes du document envoyé au serveur — `null` = cote MANQUANTE. */
function documentDesChaines(chaines) {
  return chaines.map((chaine) => ({
    nom: chaine.nom || undefined,
    total_mesure: nombreOuNull(chaine.totalMesure),
    tolerance_m: nombreOuNull(chaine.toleranceM),
    cotes: chaine.cotes.map((c) => ({ nom: c.nom, valeur: nombreOuNull(c.valeur) })),
  }))
}

/**
 * Le refus AVANT tout envoi : plus d'une cote manquante par chaîne (le noyau
 * ne peut en déduire qu'une), ou un azimut sans sa précision déclarée. Un
 * poste vide et non problématique n'est JAMAIS refusé — seule une chaîne
 * réellement inconsistante l'est, et l'erreur nomme les cotes manquantes.
 */
function validerAvantEnvoi(chaines, azimutDeg, precisionDeg) {
  const erreurs = {}
  chaines.forEach((chaine, i) => {
    const manquantes = chaine.cotes.filter((c) => c.valeur === '' || c.valeur === null)
    if (manquantes.length > 1) {
      const noms = manquantes.map((c, rang) => c.nom || `cote ${rang + 1}`).join(', ')
      erreurs[`chaines[${i}]`] = `Chaîne « ${chaine.nom || `chaîne ${i + 1}`} » : `
        + `${manquantes.length} cotes sont manquantes (${noms}) — le solveur ne `
        + 'peut en déduire qu’UNE seule par fermeture. Mesurez-en au moins une, '
        + 'ou saisissez le total mesuré pour n’en laisser qu’une manquante.'
    }
  })
  if (azimutDeg !== '' && azimutDeg !== null && (precisionDeg === '' || precisionDeg === null)) {
    erreurs.precision_azimut_deg = 'Un azimut relevé à la boussole doit '
      + 'porter sa précision déclarée (± degrés) : sans elle, il se lirait '
      + 'comme une mesure exacte.'
  }
  return erreurs
}

function ChampTexte({ id, testId, label, valeur, onChange, type = 'text' }) {
  return (
    <label className="block" data-testid={testId}>
      <span className="tech-label text-lune-faint">{label}</span>
      <input
        type={type}
        step={type === 'number' ? 'any' : undefined}
        id={id}
        value={valeur ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
      />
    </label>
  )
}

function BlocCote({ chaineIndex, coteIndex, cote, onChange, onRetirer }) {
  return (
    <div
      className="mt-2 flex flex-wrap items-end gap-2"
      data-testid={`cal-releve-chaine-${chaineIndex}-cote-${coteIndex}`}
    >
      <ChampTexte
        id={`cal-releve-chaine-${chaineIndex}-cote-${coteIndex}-nom`}
        testId={`cal-releve-chaine-${chaineIndex}-cote-${coteIndex}-nom`}
        label="Nom de la cote"
        valeur={cote.nom}
        onChange={(v) => onChange({ ...cote, nom: v })}
      />
      <ChampTexte
        id={`cal-releve-chaine-${chaineIndex}-cote-${coteIndex}-valeur`}
        testId={`cal-releve-chaine-${chaineIndex}-cote-${coteIndex}-valeur`}
        label="Valeur (m) — vide = à déduire"
        type="number"
        valeur={cote.valeur}
        onChange={(v) => onChange({ ...cote, valeur: v })}
      />
      <button
        type="button"
        onClick={onRetirer}
        data-testid={`cal-releve-chaine-${chaineIndex}-cote-${coteIndex}-retirer`}
        className="text-xs text-lune-soft underline"
      >
        Retirer la cote
      </button>
    </div>
  )
}

function BlocChaine({ index, chaine, erreur, onChange, onRetirer }) {
  const majCote = (coteIndex, cote) => {
    const cotes = [...chaine.cotes]
    cotes[coteIndex] = cote
    onChange({ ...chaine, cotes })
  }
  const ajouterCote = () => onChange({ ...chaine, cotes: [...chaine.cotes, COTE_VIDE()] })
  const retirerCote = (coteIndex) => onChange({
    ...chaine, cotes: chaine.cotes.filter((_, i) => i !== coteIndex),
  })

  return (
    <fieldset
      className="mt-4 border-t border-white/10 pt-4"
      data-testid={`cal-releve-chaine-${index}`}
    >
      <legend className="tech-label text-lune-faint">{`Chaîne ${index + 1}`}</legend>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <ChampTexte
          id={`cal-releve-chaine-${index}-nom`}
          testId={`cal-releve-chaine-${index}-nom`}
          label="Nom de la chaîne"
          valeur={chaine.nom}
          onChange={(v) => onChange({ ...chaine, nom: v })}
        />
        <ChampTexte
          id={`cal-releve-chaine-${index}-total_mesure`}
          testId={`cal-releve-chaine-${index}-total_mesure`}
          label="Total mesuré (m)"
          type="number"
          valeur={chaine.totalMesure}
          onChange={(v) => onChange({ ...chaine, totalMesure: v })}
        />
        <ChampTexte
          id={`cal-releve-chaine-${index}-tolerance_m`}
          testId={`cal-releve-chaine-${index}-tolerance_m`}
          label="Tolérance de fermeture (m)"
          type="number"
          valeur={chaine.toleranceM}
          onChange={(v) => onChange({ ...chaine, toleranceM: v })}
        />
      </div>

      <p className="tech-label mt-3 text-lune-faint">Cotes</p>
      {chaine.cotes.map((cote, coteIndex) => (
        <BlocCote
          // Une cote n'a pas d'identifiant stable avant enregistrement ;
          // l'ordre EST la clé.
          key={coteIndex}
          chaineIndex={index}
          coteIndex={coteIndex}
          cote={cote}
          onChange={(c) => majCote(coteIndex, c)}
          onRetirer={() => retirerCote(coteIndex)}
        />
      ))}
      <button
        type="button"
        onClick={ajouterCote}
        data-testid={`cal-releve-chaine-${index}-ajouter-cote`}
        className="mt-2 text-xs text-brass-200 underline"
      >
        + Ajouter une cote
      </button>

      {/* L'ERREUR SOUS LA CHAÎNE FAUTIVE — jamais un refus générique
          (règle fondateur du 08/09/2026). Le message NOMME les cotes. */}
      {erreur && (
        <p
          role="alert"
          data-testid={`cal-releve-erreur-chaine-${index}`}
          className="mt-2 text-xs text-red-300"
        >
          {erreur}
        </p>
      )}

      <button
        type="button"
        onClick={onRetirer}
        data-testid={`cal-releve-chaine-${index}-retirer`}
        className="mt-2 block text-xs text-lune-soft underline"
      >
        Retirer la chaîne
      </button>
    </fieldset>
  )
}

/** UNE chaîne résolue : la géométrie du solveur, OU son point de rupture nommé. */
function ChaineResolue({ index, resolue }) {
  const cotesManquantes = (resolue.cotes || [])
    .filter((c) => c.valeur === null || c.valeur === undefined)
    .map((c) => c.nom)

  return (
    <div className="mt-3 border-t border-white/10 pt-3" data-testid={`cal-releve-resultat-chaine-${index}`}>
      <p className="text-sm font-semibold text-white">{resolue.nom}</p>
      {resolue.ok
        ? (
          <p className="text-sm text-lune-soft" data-testid={`cal-releve-resultat-chaine-${index}-fermee`}>
            {`Chaîne fermée — positions : ${(resolue.positions || []).map((p) => p.toFixed(3)).join(' · ')} m`}
          </p>
        )
        : (
          <p
            role="alert"
            data-testid={`cal-releve-resultat-chaine-${index}-rupture`}
            className="text-sm text-red-300"
          >
            {`Point de rupture (solveur) : ${resolue.motif || 'fermeture non tenue'}`}
          </p>
        )}
      {cotesManquantes.length > 0 && (
        <p className="text-xs text-amber-200" data-testid={`cal-releve-resultat-chaine-${index}-manquante`}>
          {`Cote manquante : ${cotesManquantes.join(', ')}`}
        </p>
      )}
      {(resolue.cotes || []).filter((c) => c.a_confirmer).map((c) => (
        <p
          key={c.nom}
          className="text-xs text-amber-200"
          data-testid={`cal-releve-resultat-chaine-${index}-a-confirmer-${c.nom}`}
        >
          {`Cote « ${c.nom} » déduite par fermeture (${c.valeur} m) — à confirmer à l’exécution.`}
        </p>
      ))}
    </div>
  )
}

export default function PanneauReleve({ calepinageId: idPropose }) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [releveLe, setReleveLe] = useState('')
  const [notes, setNotes] = useState('')
  const [azimutDeg, setAzimutDeg] = useState('')
  const [precisionDeg, setPrecisionDeg] = useState('')
  const [chaines, setChaines] = useState([CHAINE_VIDE()])
  const [erreurs, setErreurs] = useState({})
  const [resultat, setResultat] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null)

  const majChaine = (index, chaine) => setChaines((cs) => cs.map((c, i) => (i === index ? chaine : c)))
  const ajouterChaine = () => setChaines((cs) => [...cs, CHAINE_VIDE()])
  const retirerChaine = (index) => setChaines((cs) => cs.filter((_, i) => i !== index))

  const envoyer = () => {
    const erreursSaisie = validerAvantEnvoi(chaines, azimutDeg, precisionDeg)
    setErreurs(erreursSaisie)
    setMessage(null)
    if (Object.keys(erreursSaisie).length > 0) return
    if (!calepinageId) return

    const corps = {
      releve_le: releveLe || null,
      chaines: documentDesChaines(chaines),
      azimut_boussole_deg: nombreOuNull(azimutDeg),
      precision_azimut_deg: nombreOuNull(precisionDeg),
      notes,
    }
    setEnCours(true)
    Promise.resolve(calepinageApi.calepinages.enregistrerReleve(calepinageId, corps))
      .then((res) => {
        setResultat(res?.data ?? null)
        setMessage('Relevé enregistré.')
      })
      .catch((err) => {
        const corpsRefus = err?.response?.data
        setErreurs(corpsRefus && typeof corpsRefus === 'object'
          ? corpsRefus
          : { detail: 'Le relevé a été refusé par le serveur.' })
        setResultat(null)
      })
      .finally(() => setEnCours(false))
  }

  const champsFautifs = Object.keys(erreurs)
  const geometrieChaines = resultat?.releve?.geometrie?.chaines ?? null

  return (
    <div className="cine-card mt-6 p-6" data-testid="cal-releve-panel">
      <p className="tech-label rule-brass text-brass-300">Relevé terrain</p>

      {champsFautifs.length > 0 && (
        <p
          role="alert"
          data-testid="cal-releve-bandeau"
          className="mt-3 rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-200"
        >
          {`Relevé incomplet — à corriger : ${champsFautifs.join(', ')}`}
        </p>
      )}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ChampTexte
          id="cal-releve-releve_le"
          testId="cal-releve-champ-releve_le"
          label="Relevé le"
          type="date"
          valeur={releveLe}
          onChange={setReleveLe}
        />
        <div />
        <ChampTexte
          id="cal-releve-azimut_boussole_deg"
          testId="cal-releve-champ-azimut_boussole_deg"
          label="Azimut boussole (°)"
          type="number"
          valeur={azimutDeg}
          onChange={setAzimutDeg}
        />
        <div>
          <ChampTexte
            id="cal-releve-precision_azimut_deg"
            testId="cal-releve-champ-precision_azimut_deg"
            label="Précision de l’azimut (± °)"
            type="number"
            valeur={precisionDeg}
            onChange={setPrecisionDeg}
          />
          {erreurs.precision_azimut_deg && (
            <p role="alert" data-testid="cal-releve-erreur-precision_azimut_deg"
              className="mt-1 text-xs text-red-300">
              {erreurs.precision_azimut_deg}
            </p>
          )}
        </div>
      </div>

      <label className="mt-3 block" data-testid="cal-releve-champ-notes">
        <span className="tech-label text-lune-faint">Notes de terrain</span>
        <textarea
          id="cal-releve-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="mt-1 w-full rounded border border-white/15 bg-black/30 px-2 py-1 text-sm text-white"
        />
      </label>

      {chaines.map((chaine, index) => (
        <BlocChaine
          // Même raison que pour les cotes : aucun identifiant stable avant envoi.
          key={index}
          index={index}
          chaine={chaine}
          erreur={erreurs[`chaines[${index}]`]}
          onChange={(c) => majChaine(index, c)}
          onRetirer={() => retirerChaine(index)}
        />
      ))}
      <button
        type="button"
        onClick={ajouterChaine}
        data-testid="cal-releve-ajouter-chaine"
        className="mt-3 text-sm text-brass-200 underline"
      >
        + Ajouter une chaîne
      </button>

      <button
        type="button"
        onClick={envoyer}
        disabled={enCours}
        data-testid="cal-releve-envoyer"
        className="mt-5 block rounded bg-brass-500/20 px-4 py-2 text-sm font-semibold text-brass-200"
      >
        {enCours ? 'Envoi au solveur…' : 'Envoyer au solveur'}
      </button>

      {message && (
        <p role="status" data-testid="cal-releve-message" className="mt-3 text-sm text-lune-soft">
          {message}
        </p>
      )}

      {geometrieChaines && (
        <div className="mt-5 border-t border-white/10 pt-4" data-testid="cal-releve-resultat">
          <p className="tech-label text-lune-faint">Géométrie résolue</p>
          {geometrieChaines.map((resolue, index) => (
            <ChaineResolue key={resolue.nom || index} index={index} resolue={resolue} />
          ))}
        </div>
      )}
    </div>
  )
}
