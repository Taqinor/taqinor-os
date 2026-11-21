import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { Card } from '../../../ui'
import { PARAM_ONGLET } from '../atelier/onglets'
import { useModeExpert } from '../atelier/modeExpert'
import { PARADES, chainesTouchees, phraseChaine } from './CarteChaineOmbragee.helpers'

/* ACAL712 — « Chaîne N touchée par l'ombre » : une carte par chaîne dont les
   deux bornes d'ombrage (ACAL711) diffèrent. Lecture seule du résultat ; la
   liste de parades est FIXE et ne chiffre aucun gain. Étape omise ou aucune
   chaîne touchée ⇒ rien. Niveau expert, sans saisie. */

export default function CarteChaineOmbragee({ calepinageId }) {
  const [expert] = useModeExpert()
  const [cascade, setCascade] = useState(null)
  useEffect(() => {
    if (!calepinageId || !expert) return undefined
    let actif = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.resultat(calepinageId))
      .then((res) => { if (actif) setCascade(res?.data?.cascade ?? null) })
      .catch(() => {})
    return () => { actif = false }
  }, [calepinageId, expert])
  const { chaines, hypothese } = chainesTouchees(cascade)
  if (!expert || chaines.length === 0) return null
  return (
    <div className="flex flex-col gap-3" data-testid="acal712-cartes">
      {chaines.map((c) => (
        <Card key={`${c.pan}-${c.chaine}`} data-testid={`acal712-carte-${c.pan}-${c.chaine}`}>
          <h3 className="text-sm font-semibold">
            Chaîne {c.chaine} touchée par l'ombre{c.pan ? ` (pan ${c.pan})` : ''}
          </h3>
          <p className="text-sm">{phraseChaine(c)}</p>
          {hypothese && <p className="text-xs text-muted-foreground">{hypothese}</p>}
          <p className="text-sm">Parades possibles :</p>
          <ul className="list-disc pl-5 text-sm" data-testid="acal712-parades">
            {PARADES.map((p) => <li key={p}>{p}</li>)}
          </ul>
          <Link
            to={`/calepinage/${calepinageId}?${PARAM_ONGLET}=affectation`}
            className="inline-flex min-h-11 items-center text-sm font-medium text-primary-text underline"
            data-testid="acal712-modifier">
            Modifier une chaîne
          </Link>
        </Card>
      ))}
    </div>
  )
}
