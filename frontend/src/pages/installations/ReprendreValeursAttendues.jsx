// ACAL668 — « Reprendre les valeurs du calepinage » dans le relevé I-V de la
// recette : Voc, Isc et Pmax ATTENDUS de la chaîne choisie, servis par
// `recettes-commissioning/<id>/valeurs-attendues/` (ACAL667, contrat
// `installations/recette_valeurs_attendues.json`). Rien n'est écrit ici : le
// relevé part toujours par « Ajouter le relevé I-V ». Les mesures restent à
// taper ; les valeurs reprises sont recopiées telles que servies (jamais
// arrondies) et restent corrigeables.
import { useCallback, useEffect, useState } from 'react'
import { Button, Label } from '../../ui'
import installationsApi from '../../api/installationsApi'

const libelleChaine = (c) => `Chaîne ${String(c.chaine).replace(/^CH/, '')} — ${c.modules} modules`

export default function ReprendreValeursAttendues({ ficheId, onReprendre }) {
  const [chaines, setChaines] = useState(null)
  const [choix, setChoix] = useState('')
  const [erreur, setErreur] = useState(null)
  const [repris, setRepris] = useState(false)

  // Une lecture : la liste servie, ou `null` en échec (message posé).
  const lire = useCallback(() => Promise.resolve()
    .then(() => installationsApi.valeursAttendues(ficheId))
    .then((r) => {
      const liste = r?.data?.chaines ?? []
      setErreur(null)
      setChaines(liste)
      setChoix((c) => c || liste[0]?.chaine || '')
      return liste
    }, () => {
      setErreur('Les valeurs du calepinage n’ont pas pu être lues — réessayez ou tapez-les.')
      return null
    }), [ficheId])

  useEffect(() => {
    if (ficheId) lire()
  }, [ficheId, lire])

  const reprendre = async () => {
    const liste = chaines ?? await lire()
    const chaine = liste?.find((c) => c.chaine === choix) ?? liste?.[0]
    if (!chaine) return
    onReprendre({
      voc_attendu_v: chaine.voc_attendu_v == null ? '' : String(chaine.voc_attendu_v),
      isc_attendu_a: chaine.isc_attendu_a == null ? '' : String(chaine.isc_attendu_a),
      pmax_attendu_w: chaine.pmax_attendu_w == null ? '' : String(chaine.pmax_attendu_w),
    })
    setRepris(true)
  }

  // Chantier sans calepinage retenu (liste vide) : rien à proposer.
  if (!erreur && (chaines == null || chaines.length === 0)) return null
  return (
    <div className="flex flex-col gap-1.5" data-testid="recette-reprise-calepinage">
      {chaines?.length > 0 && (
        <>
          <Label htmlFor="iv-chaine-calepinage">Chaîne du calepinage</Label>
          <select id="iv-chaine-calepinage" className="form-control min-h-11" value={choix}
                  onChange={(e) => { setChoix(e.target.value); setRepris(false) }}>
            {chaines.map((c) => <option key={c.chaine} value={c.chaine}>{libelleChaine(c)}</option>)}
          </select>
        </>
      )}
      <div>
        <Button type="button" size="sm" variant="outline" onClick={reprendre}>
          Reprendre les valeurs du calepinage
        </Button>
      </div>
      {erreur && <p className="form-error" role="alert">{erreur}</p>}
      {repris && (
        <p className="text-sm text-muted-foreground" data-testid="recette-reprise-note">
          Valeurs attendues d’après le calepinage, à confirmer.
        </p>
      )}
    </div>
  )
}
