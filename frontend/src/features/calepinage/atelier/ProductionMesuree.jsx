import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Button, Card } from '../../../ui'
import Pourquoi from '../commun/Pourquoi'
import CelluleEcart from '../commun/CelluleEcart'
import { refusServeur } from '../commun/refusServeur'
import { MOIS, nombre, valeurSaisie } from '../commun/mesuresMensuelles'

/* ============================================================================
   ACAL888 — L'ONGLET « LIVRÉ ET PRÉVU » (étape Résultats, niveau expert).
   ----------------------------------------------------------------------------
   Douze valeurs MESURÉES (kWh par mois, collées d'une colonne de compteur ou
   tapées), rangées par `PUT production-mesuree/` (ACAL887, contrat
   `calepinage_production_mesuree.json`) puis comparées au P50 mensuel SERVI.
   RIEN n'est calculé ici : prévu, écart du mois et écart annuel sont RECOPIÉS
   du serveur. Un mois sans mesure s'écrit « — », jamais 0. Un refus nomme son
   champ (`annee`, `mesures[i].kwh_mesure`) et se rend sous le champ du mois.
   ========================================================================== */

/** Les saisies (douze textes) relues d'une réponse du serveur : `kwh_mesure` par mois. */
function saisiesDe(donnees) {
  const saisies = Array(12).fill('')
  for (const m of donnees?.mesures || []) {
    if (m?.mois >= 1 && m.mois <= 12 && m.kwh_mesure !== null && m.kwh_mesure !== undefined) {
      saisies[m.mois - 1] = String(m.kwh_mesure).replace('.', ',')
    }
  }
  return saisies
}

/** « le réel est X % au-dessus / en dessous de la prévision » — X est la valeur servie. */
function phraseAnnuelle(ecart) {
  if (ecart === null || ecart === undefined) return null
  if (ecart === 0) return 'Le réel est égal à la prévision.'
  const sens = ecart > 0 ? 'au-dessus' : 'en dessous'
  return `Le réel est ${nombre(Math.abs(ecart))} % ${sens} de la prévision.`
}

export default function ProductionMesuree({ calepinageId: idPropose = null }) {
  const { id: idUrl } = useParams()
  const id = idPropose ?? idUrl ?? null
  const peutGerer = useHasPermission('calepinage_gerer')
  const [etat, setEtat] = useState(null)
  const [annee, setAnnee] = useState('')
  const [saisies, setSaisies] = useState(() => Array(12).fill(''))
  const [erreurs, setErreurs] = useState({})
  const [erreurLecture, setErreurLecture] = useState(null)
  const [envoi, setEnvoi] = useState(false)

  const appliquer = (donnees) => {
    setEtat(donnees)
    setAnnee(donnees?.annee === null || donnees?.annee === undefined ? '' : String(donnees.annee))
    setSaisies(saisiesDe(donnees))
  }

  useEffect(() => {
    if (!id) return undefined
    let vivant = true
    Promise.resolve(calepinageApi.calepinages.productionMesuree(id))
      .then((res) => { if (vivant) appliquer(res?.data) })
      .catch(() => { if (vivant) setErreurLecture('La production mesurée de ce calepinage n’a pas pu être lue.') })
    return () => { vivant = false }
  }, [id])

  // Une colonne collée (retours à la ligne, tabulations, points-virgules) remplit les mois à partir du champ visé.
  const coller = (debut) => (e) => {
    const morceaux = e.clipboardData.getData('text').split(/[\n\r\t;]+/).map((m) => m.trim()).filter((m) => m !== '')
    if (morceaux.length < 2) return
    e.preventDefault()
    setSaisies((avant) => avant.map((v, j) => (j >= debut && j - debut < morceaux.length ? morceaux[j - debut] : v)))
  }

  const enregistrer = () => {
    setErreurs({})
    const mesures = saisies
      .map((texte, i) => ({ mois: i + 1, kwh_mesure: valeurSaisie(texte) }))
      .filter((m) => m.kwh_mesure !== null)
    setEnvoi(true)
    calepinageApi.calepinages.enregistrerProductionMesuree(id, { annee: valeurSaisie(annee), mesures })
      .then((res) => appliquer(res.data))
      .catch((err) => {
        const { message, champs } = refusServeur(err)
        const parMois = {}
        for (const [champ, motif] of Object.entries(champs)) {
          const rang = /^mesures\[(\d+)\]/.exec(champ)?.[1]
          if (rang !== undefined && mesures[Number(rang)]) parMois[mesures[Number(rang)].mois] = motif
        }
        setErreurs({
          ...(champs.annee ? { annee: champs.annee } : {}),
          mois: parMois,
          ...(!champs.annee && !Object.keys(parMois).length
            ? { general: message || 'Enregistrement refusé par le serveur.' } : {}),
        })
      })
      .finally(() => setEnvoi(false))
  }

  const ecarts = Array.isArray(etat?.ecarts) ? etat.ecarts : []
  const phrase = phraseAnnuelle(etat?.ecart_annuel_pct)
  const parMois = erreurs.mois || {}

  return (
    <Card className="flex flex-col gap-4 p-4" data-testid="acal888-ecran">
      <header className="flex flex-col gap-1">
        <h2 className="flex items-center gap-1 text-base font-semibold">
          Livré et prévu
          <Pourquoi cle="mesure.ecart" />
        </h2>
        <p className="text-sm text-muted-foreground">
          Collez ou tapez la production mesurée de chaque mois (kWh) ; le serveur la compare à la prévision.
        </p>
      </header>

      {erreurLecture ? <p role="alert" className="text-sm text-destructive" data-testid="acal888-erreur-lecture">{erreurLecture}</p> : null}

      <div className="flex flex-col gap-1">
        <label className="text-sm text-muted-foreground" htmlFor="acal888-annee">Année des mesures</label>
        <input
          id="acal888-annee"
          data-testid="acal888-annee"
          value={annee}
          inputMode="numeric"
          aria-invalid={erreurs.annee ? 'true' : undefined}
          onChange={(e) => setAnnee(e.target.value)}
          className="min-h-11 w-32 rounded border border-border bg-background px-2 text-sm"
        />
        {erreurs.annee ? <p className="text-sm text-destructive" data-testid="acal888-erreur-annee">{erreurs.annee}</p> : null}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {MOIS.map((mois, i) => (
          <div key={mois} className="flex flex-col gap-1">
            <label className="text-sm text-muted-foreground" htmlFor={`acal888-${i + 1}`}>{mois} (kWh)</label>
            <input
              id={`acal888-${i + 1}`}
              data-testid={`acal888-champ-${i + 1}`}
              value={saisies[i]}
              inputMode="decimal"
              aria-invalid={parMois[i + 1] ? 'true' : undefined}
              onPaste={coller(i)}
              onChange={(e) => setSaisies((avant) => avant.map((v, j) => (j === i ? e.target.value : v)))}
              className="min-h-11 rounded border border-border bg-background px-2 text-sm"
            />
            {parMois[i + 1]
              ? <p className="text-sm text-destructive" data-testid={`acal888-erreur-${i + 1}`}>{parMois[i + 1]}</p>
              : null}
            {/* ACAL1251 (D-ACAL-63) — mesure gardée mais plus de 10 fois le P50 du mois : le serveur le dit. */}
            {ecarts.find((ligne) => ligne.mois === i + 1)?.avertissement
              ? (
                <p role="status" className="text-sm text-warning" data-testid={`acal1251-avertissement-${i + 1}`}>
                  {ecarts.find((ligne) => ligne.mois === i + 1).avertissement}
                </p>
              )
              : null}
          </div>
        ))}
      </div>
      {erreurs.general ? <p role="alert" className="text-sm text-destructive" data-testid="acal888-erreur">{erreurs.general}</p> : null}

      {peutGerer
        ? (
          <div>
            <Button type="button" className="min-h-11" onClick={enregistrer} disabled={envoi} data-testid="acal888-enregistrer">
              Enregistrer et comparer
            </Button>
          </div>
        )
        : <p className="text-sm text-muted-foreground" data-testid="acal888-sans-droit">Lecture seule : vous ne pouvez pas enregistrer de mesures.</p>}

      {phrase ? <p className="text-sm font-medium" data-testid="acal888-annuel">Écart annuel : {nombre(etat.ecart_annuel_pct, true)} %. {phrase}</p> : null}
      {etat?.motif ? <p className="text-sm text-muted-foreground" data-testid="acal888-motif">{etat.motif}</p> : null}

      {ecarts.length > 0
        ? (
          <table className="w-full text-sm" data-testid="acal888-tableau">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="py-1">Mois</th>
                <th scope="col">Prévu (P50)</th>
                <th scope="col">Mesuré</th>
                <th scope="col">Écart</th>
              </tr>
            </thead>
            <tbody>
              {ecarts.map((ligne) => (
                <tr key={ligne.mois} data-testid={`acal888-ligne-${ligne.mois}`}>
                  <th scope="row" className="py-1 text-left font-normal">{MOIS[ligne.mois - 1] ?? ligne.mois}</th>
                  <td>{nombre(ligne.p50_kwh)}</td>
                  <td data-testid={`acal888-mesure-${ligne.mois}`}>{nombre(ligne.kwh_mesure)}</td>
                  <CelluleEcart ecart={ligne.ecart_pct} testId={`acal888-ecart-${ligne.mois}`} />
                </tr>
              ))}
            </tbody>
          </table>
        )
        : null}
    </Card>
  )
}
