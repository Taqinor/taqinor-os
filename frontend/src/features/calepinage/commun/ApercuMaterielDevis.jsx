/* Lane E9 (constat T4-X5-010) — AVANT « Générer le devis » : ce que le devis PORTERA.
   Le serveur rejoue À BLANC la composition que la génération écrirait (`GET apercu-devis/`, rien n'est écrit) :
   par option, le module et l'onduleur du devis, puis une phrase par produit désigné à l'étape Électrique que le
   devis ne portera pas, avec sa raison — phrases servies, jamais réécrites ici. Rien n'est affirmé tant que la
   lecture n'a pas répondu ; un échec se tait (le bouton reste le geste, son refus éventuel parlera).
   Forme lue : contrat `calepinage_apercu_devis.json` (`options[{libelle, module, onduleur}]`, `ecarts[{message}]`, `refus`). */
import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'

/* Lane E9b — `surfaces` : les clés cochées que « Générer » enverra (`surfaces_chiffrees`), `null` quand tout part ;
   le serveur suit alors la MÊME sélection, et dit s'il ouvrirait un brouillon existant (`source`, `reference`). */
export default function ApercuMaterielDevis({ calepinageId, signature = '', surfaces = null }) {
  const [apercu, setApercu] = useState({ cle: null, donnees: null })
  const choix = Array.isArray(surfaces) ? surfaces.join(',') : null
  const cle = `${calepinageId}|${signature}|${choix ?? '*'}`
  useEffect(() => {
    if (calepinageId == null) return undefined
    let vivant = true
    const config = choix == null ? undefined : { params: { surfaces: choix } }
    Promise.resolve().then(() => calepinageApi.calepinages.apercuDevis(calepinageId, config)).then(
      (res) => { if (vivant) setApercu({ cle, donnees: res?.data ?? null }) },
      () => { if (vivant) setApercu({ cle, donnees: null }) },
    )
    return () => { vivant = false }
  }, [calepinageId, cle, choix])
  const donnees = apercu.cle === cle ? apercu.donnees : null
  const options = (donnees?.options ?? []).filter((o) => o.module || o.onduleur)
  if (!options.length) return null
  return (
    <div className="text-xs text-foreground" data-zone="apercu-materiel-devis">
      {donnees.source === 'brouillon_existant' && donnees.reference && (
        <p data-zone="apercu-brouillon-existant">{`Un devis brouillon existe déjà (${donnees.reference}) : le bouton l’ouvre.`}</p>
      )}
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
