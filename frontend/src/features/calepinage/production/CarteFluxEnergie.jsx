import { useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import { formatNumber } from '../../../lib/format'

/* ACAL762 — « Où va l'énergie » (niveau expert, repliée d'office) : le schéma
   dessiné par le serveur (ACAL761, SVG en <img>) et la liste des flux en kWh
   lus tels que servis (`cascade.postes_lisibles`, `autoconsommation.energie`,
   `batterie.total`). Aucune somme : un flux `null` ou un poste « non compté »
   dit « non calculé » et son motif, jamais 0. Un refus du schéma montre son
   motif et garde la liste. */

const kwh = (v) => `${formatNumber(v, { decimals: 0 })} kWh`
const nombre = (v) => typeof v === 'number' && Number.isFinite(v)

function fluxServis(data) {
  const lisibles = data?.cascade?.postes_lisibles
  const energie = data?.autoconsommation?.energie
  const plafond = data?.autoconsommation?.plafond
  const batterie = data?.batterie?.total
  const motifAbsence = data?.autoconsommation?.motif_absence || ''
  const liste = [{ code: 'soleil', nom: 'Soleil reçu', valeur: lisibles?.depart_kwh }]
  for (const p of lisibles?.postes ?? []) {
    const compte = p.statut !== 'non_compte'
    const motif = (p.etapes ?? []).map((e) => e.motif_omission).filter(Boolean).join(' ')
    liste.push({ code: p.poste, nom: p.libelle, valeur: compte ? p.perte_kwh : null, motif })
  }
  liste.push({ code: 'produite', nom: 'Électricité produite', valeur: lisibles?.arrivee_kwh })
  const ligne = (code, nom, valeur) => ({ code, nom, valeur: energie ? valeur : null, motif: motifAbsence })
  liste.push(
    ligne('production_brute', 'Production brute', energie?.production_brute_kwh),
    ligne('sur_place', 'Consommée sur place', energie?.autoconsomme_kwh),
    ligne('injectee', 'Injectée au réseau', energie?.export_reseau_kwh),
  )
  if (plafond?.applique) liste.push(ligne('ecretee', 'Écrêtée', plafond.energie_ecretee_kwh))
  liste.push(
    ligne('importee', 'Importée du réseau', energie?.import_reseau_kwh),
    ligne('consommation', 'Consommation', energie?.consommation_kwh),
  )
  if (energie?.apres_batterie && batterie) {
    liste.push(
      { code: 'batterie', nom: 'Dont par la batterie', valeur: batterie.energie_restituee_kwh },
      { code: 'pertes_batterie', nom: 'Pertes de la batterie', valeur: batterie.energie?.pertes_batterie_kwh },
    )
  }
  return liste
}

async function motifDuRefus(erreur) {
  let corps = erreur?.response?.data
  try {
    if (corps && typeof corps.text === 'function') corps = JSON.parse(await corps.text())
    const premier = corps && typeof corps === 'object' ? Object.values(corps)[0] : null
    const motif = Array.isArray(premier) ? premier[0] : premier
    if (typeof motif === 'string' && motif.trim()) return motif
  } catch {
    return "Le schéma n'a pas pu être chargé."  // corps illisible : le motif par défaut
  }
  return "Le schéma n'a pas pu être chargé."
}

export default function CarteFluxEnergie({ calepinageId, data }) {
  const [ouvert, setOuvert] = useState(false)
  const [image, setImage] = useState(null)
  const [refus, setRefus] = useState('')

  useEffect(() => {
    if (!ouvert) return undefined
    let url = null
    let annule = false
    Promise.resolve(calepinageApi.calepinages.diagrammeEnergie(calepinageId))
      .then((res) => {
        if (annule || typeof URL.createObjectURL !== 'function') return
        url = URL.createObjectURL(res.data)
        setImage(url)
      })
      .catch(async (e) => { const m = await motifDuRefus(e); if (!annule) setRefus(m) })
    return () => {
      annule = true
      if (url && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
    }
  }, [ouvert, calepinageId])

  return (
    <section className="rounded-md border border-border/60 p-3" data-testid="acal762-carte">
      <button
        type="button"
        className="min-h-11 text-sm font-medium underline"
        aria-expanded={ouvert}
        onClick={() => setOuvert((o) => !o)}
        data-testid="acal762-bascule"
      >
        Où va l&apos;énergie
      </button>
      {ouvert && (
        <div className="mt-2 flex flex-col gap-3" data-testid="acal762-contenu">
          {image && (
            <img src={image} className="w-full" data-testid="acal762-schema"
              alt="Schéma des flux d'énergie, du soleil aux usages" />
          )}
          {refus && <p role="alert" className="text-sm text-destructive" data-testid="acal762-refus">{refus}</p>}
          <ul className="divide-y divide-border">
            {fluxServis(data).map((f) => (
              <li key={f.code} className="flex flex-wrap justify-between gap-2 py-1 text-sm"
                data-testid={`acal762-flux-${f.code}`}>
                <span>{f.nom}</span>
                <span className="tabular-nums">
                  {nombre(f.valeur) ? kwh(f.valeur) : `non calculé${f.motif ? ` — ${f.motif}` : ''}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
