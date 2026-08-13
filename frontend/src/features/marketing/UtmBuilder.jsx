/* eslint-disable react-refresh/only-export-components --
   L'écran exporte AUSSI sa logique pure (`construireUrlUtm`), testée sans DOM
   comme `segmentRules.js`/`journeyGraph.js`. */
import { useState } from 'react'

/* ============================================================================
   NTMKT25 — Générateur d'URL de campagne (tags UTM personnalisés).
   ----------------------------------------------------------------------------
   Pour un usage HORS campagne ERP (post organique LinkedIn, signature email,
   flyer) : on compose une URL taguée sans créer de `Campagne` ni de lien
   tracké XMKT9. Aucun appel backend — l'URL générée reste attribuable par le
   web existant (`utm_campaign` alimente déjà `PointContact`/FG34).
   ========================================================================== */

export const CHAMPS_UTM = [
  { cle: 'utm_source', label: 'Source (utm_source)', exemple: 'linkedin' },
  { cle: 'utm_medium', label: 'Support (utm_medium)', exemple: 'organique' },
  { cle: 'utm_campaign', label: 'Campagne (utm_campaign)', exemple: 'campagne-2026' },
  { cle: 'utm_content', label: 'Contenu (utm_content)', exemple: 'post-carrousel' },
  { cle: 'utm_term', label: 'Mot-clé (utm_term)', exemple: 'pompe solaire' },
]

/**
 * Compose l'URL taguée. Les paramètres vides sont OMIS (jamais de
 * `utm_term=` vide qui pollue l'attribution) ; les UTM déjà présents dans
 * l'URL de base sont ÉCRASÉS par les valeurs saisies ; le fragment (#ancre)
 * est préservé après la query. Renvoie '' si l'URL de base est invalide.
 */
export function construireUrlUtm(urlBase, valeurs) {
  const brut = (urlBase || '').trim()
  if (!brut) return ''
  let url
  try {
    url = new URL(brut.includes('://') ? brut : `https://${brut}`)
  } catch {
    return ''
  }
  CHAMPS_UTM.forEach(({ cle }) => {
    const valeur = ((valeurs || {})[cle] || '').trim()
    if (valeur) url.searchParams.set(cle, valeur)
    else url.searchParams.delete(cle)
  })
  return url.toString()
}

export default function UtmBuilder() {
  const [urlBase, setUrlBase] = useState('')
  const [valeurs, setValeurs] = useState({})
  const [copie, setCopie] = useState(false)

  const url = construireUrlUtm(urlBase, valeurs)
  const setChamp = (cle) => (e) => {
    setCopie(false)
    setValeurs(v => ({ ...v, [cle]: e.target.value }))
  }

  const copier = async () => {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopie(true)
    } catch {
      setCopie(false)
    }
  }

  return (
    <div className="page utm-builder">
      <h2>Générateur d'URL de campagne</h2>
      <p style={{ color: '#475569' }}>
        Pour un usage hors campagne ERP (post organique, signature email,
        flyer). Aucune campagne n'est créée ; l'URL reste attribuable au bon
        <code> utm_campaign</code> dans les rapports existants.
      </p>

      <label>
        URL de destination
        <input className="form-input" data-testid="utm-url-base"
          placeholder="https://exemple.ma/offre"
          value={urlBase} onChange={e => { setCopie(false); setUrlBase(e.target.value) }} />
      </label>

      {CHAMPS_UTM.map(({ cle, label, exemple }) => (
        <label key={cle}>
          {label}
          <input className="form-input" data-testid={`utm-${cle}`}
            placeholder={exemple}
            value={valeurs[cle] || ''} onChange={setChamp(cle)} />
        </label>
      ))}

      <p data-testid="utm-resultat">
        {url || 'Renseignez une URL de destination valide.'}
      </p>
      <button type="button" className="btn btn-primary"
        data-testid="utm-copier" onClick={copier} disabled={!url}>
        {copie ? 'Copiée !' : "Copier l'URL"}
      </button>
    </div>
  )
}
