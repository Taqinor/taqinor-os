import { useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { Button, Card } from '../../../ui'
import CelluleEcart from '../commun/CelluleEcart'
import { refusServeur } from '../commun/refusServeur'
import { MOIS, nombre, valeurSaisie } from '../commun/mesuresMensuelles'

/* ============================================================================
   ACAL847 — L'ONGLET « CONSOMMATION MESURÉE » (étape Résultats, niveau expert).
   ----------------------------------------------------------------------------
   12 consommations mensuelles MESURÉES, saisies ici, comparées à la consommation
   simulée du calepinage (`POST ecart-mesures/`, contrat
   `calepinage_asbuilt_mesures.json`, ACAL846). RIEN n'est calculé ni enregistré
   par l'écran : simulé, écart en % et eau sont RECOPIÉS du serveur. Réservé aux
   porteurs de `calepinage_approuver` (porte SAV / gérant) : sans le droit,
   la mention seule et AUCUNE requête. Un refus nomme son champ (`kwh[2]`) et se
   rend sous le champ du mois concerné.
   ========================================================================== */

export default function EcartMesures({ calepinageId: idPropose = null }) {
  const { id: idUrl } = useParams()
  const id = idPropose ?? idUrl ?? null
  const peutApprouver = useHasPermission('calepinage_approuver')
  const [saisies, setSaisies] = useState(() => Array(12).fill(''))
  const [resultat, setResultat] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [envoi, setEnvoi] = useState(false)

  if (!peutApprouver) {
    return (
      <Card className="p-4">
        <p className="text-sm text-muted-foreground" data-testid="acal847-sans-droit">
          Réservé aux porteurs du droit calepinage_approuver.
        </p>
      </Card>
    )
  }

  const comparer = () => {
    setErreurs({})
    setEnvoi(true)
    calepinageApi.calepinages.ecartMesures(id, { kwh: saisies.map(valeurSaisie) })
      .then((r) => setResultat(r.data))
      .catch((err) => {
        const { message, champs } = refusServeur(err)
        setResultat(null)
        setErreurs(Object.keys(champs).length ? champs : { general: message || 'Comparaison refusée par le serveur.' })
      })
      .finally(() => setEnvoi(false))
  }

  const consommation = resultat?.consommation
  const lignes = consommation?.lignes || []
  const eau = resultat?.eau
  const eauMesuree = (eau?.m3_mesures || []).map((m3, i) => [i, m3]).filter(([, m3]) => m3 !== null)

  return (
    <Card className="flex flex-col gap-4 p-4" data-testid="acal847-ecran">
      <header className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Consommation mesurée</h2>
        <p className="text-sm text-muted-foreground">
          Tapez les consommations mesurées (kWh) ; le serveur les compare à la simulation. Les
          saisies ne sont pas enregistrées.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {MOIS.map((mois, i) => (
          <div key={mois} className="flex flex-col gap-1">
            <label className="text-sm text-muted-foreground" htmlFor={`acal847-${i + 1}`}>{mois} (kWh)</label>
            <input
              id={`acal847-${i + 1}`}
              data-testid={`acal847-champ-${i + 1}`}
              value={saisies[i]}
              inputMode="decimal"
              aria-invalid={erreurs[`kwh[${i}]`] ? 'true' : undefined}
              onChange={(e) => setSaisies((avant) => avant.map((v, j) => (j === i ? e.target.value : v)))}
              className="min-h-11 rounded border border-border bg-background px-2 text-sm"
            />
            {erreurs[`kwh[${i}]`]
              ? <p className="text-sm text-destructive" data-testid={`acal847-erreur-${i + 1}`}>{erreurs[`kwh[${i}]`]}</p>
              : null}
          </div>
        ))}
      </div>
      {erreurs.annee ? <p className="text-sm text-destructive" data-testid="acal847-erreur-annee">{erreurs.annee}</p> : null}
      {erreurs.general ? <p className="text-sm text-destructive" data-testid="acal847-erreur">{erreurs.general}</p> : null}

      <div>
        <Button type="button" className="min-h-11" onClick={comparer} disabled={envoi} data-testid="acal847-comparer">
          Comparer
        </Button>
      </div>

      {consommation?.motif && lignes.length === 0
        ? <p className="text-sm text-muted-foreground" data-testid="acal847-motif">{consommation.motif}</p>
        : null}
      {lignes.length > 0
        ? (
          <table className="w-full text-sm" data-testid="acal847-tableau">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="py-1">Mois</th>
                <th scope="col">Simulé (kWh)</th>
                <th scope="col">Mesuré (kWh)</th>
                <th scope="col">Écart</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((ligne) => (
                <tr key={ligne.mois} data-testid={`acal847-ligne-${ligne.mois}`}>
                  <th scope="row" className="py-1 text-left font-normal">{MOIS[ligne.mois - 1] ?? ligne.mois}</th>
                  <td data-testid={`acal847-simule-${ligne.mois}`}>{nombre(ligne.simule_kwh)}</td>
                  <td data-testid={`acal847-mesure-${ligne.mois}`}>{nombre(ligne.mesure_kwh)}</td>
                  <CelluleEcart ecart={ligne.ecart_pct} testId={`acal847-ecart-${ligne.mois}`} />
                </tr>
              ))}
            </tbody>
          </table>
        )
        : null}
      {lignes.length > 0 && consommation.total_ecart_pct !== null && consommation.total_ecart_pct !== undefined
        ? <p className="text-sm" data-testid="acal847-total">Écart sur la période : {nombre(consommation.total_ecart_pct, true)} %</p>
        : null}

      {resultat
        ? (
          <section className="flex flex-col gap-1" data-testid="acal847-eau">
            <h3 className="text-sm font-medium">Eau</h3>
            <p className="text-sm">
              {eauMesuree.length
                ? `Mesurée : ${eauMesuree.map(([i, m3]) => `${MOIS[i]} ${nombre(m3)} m³`).join(', ')}`
                : 'Aucun volume d’eau mesuré.'}
              {' — '}
              {eau?.simule_m3 === null || eau?.simule_m3 === undefined ? 'simulé : non enregistré' : `simulé : ${nombre(eau.simule_m3)} m³`}
            </p>
            {eau?.motif ? <p className="text-sm text-muted-foreground">{eau.motif}</p> : null}
          </section>
        )
        : null}
      {resultat?.mention
        ? <p className="text-sm text-muted-foreground" data-testid="acal847-mention">{resultat.mention}</p>
        : null}
    </Card>
  )
}
