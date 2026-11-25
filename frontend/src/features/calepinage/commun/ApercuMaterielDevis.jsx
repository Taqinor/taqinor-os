/* Lane E9 (constat T4-X5-010) — AVANT « Générer le devis » : ce que le devis PORTERA.
   Le serveur rejoue À BLANC la composition que la génération écrirait (`GET apercu-devis/`, rien n'est écrit) :
   par option, le module et l'onduleur du devis, puis une phrase par produit désigné à l'étape Électrique que le
   devis ne portera pas, avec sa raison — phrases servies, jamais réécrites ici. Rien n'est affirmé tant que la
   lecture n'a pas répondu ; un échec se tait (le bouton reste le geste, son refus éventuel parlera). */
import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'

export default function ApercuMaterielDevis({ calepinageId, signature = '' }) {
  const [apercu, setApercu] = useState({ cle: null, donnees: null })
  const cle = `${calepinageId}|${signature}`
  useEffect(() => {
    if (calepinageId == null) return undefined
    let vivant = true
    Promise.resolve().then(() => calepinageApi.calepinages.apercuDevis(calepinageId)).then(
      (res) => { if (vivant) setApercu({ cle, donnees: res?.data ?? null }) },
      () => { if (vivant) setApercu({ cle, donnees: null }) },
    )
    return () => { vivant = false }
  }, [calepinageId, cle])
  const donnees = apercu.cle === cle ? apercu.donnees : null
  const options = (donnees?.options ?? []).filter((o) => o.module || o.onduleur)
  if (!options.length) return null
  return (
    <div className="text-xs text-foreground" data-zone="apercu-materiel-devis">
      <p className="font-semibold">Le devis portera :</p>
      <ul>
        {options.map((o) => (
          <li key={o.option ?? 'unique'}>
            {(options.length > 1 ? `${o.libelle} : ` : '')
              + [o.module ? `module ${o.module}` : null, o.onduleur ? `onduleur ${o.onduleur}` : null]
                .filter(Boolean).join(' · ')}
          </li>
        ))}
      </ul>
      {(donnees.ecarts ?? []).map((e) => (
        <p key={e.champ} role="status" data-zone="apercu-ecart">{e.message}</p>
      ))}
    </div>
  )
}
