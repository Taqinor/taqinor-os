/* AOF81 — Import DXF : mapping des calques, avec ÉTAT DÉGRADÉ garanti.
   ----------------------------------------------------------------------------
   Cet écran est livrable AVANT l'endpoint de parsing (AOF72) : l'analyseur est
   une PROP injectée (`analyserDxf`), jamais un import dur d'un client d'API qui
   n'existe pas encore. Trois conséquences, toutes testées :
     • analyseur absent  → message FR explicite + repli « tracer à la main » ;
     • analyseur en erreur (404, 500, réseau) → message FR explicite, même repli ;
     • jamais de page blanche, dans aucun de ces cas.

   Quand l'analyseur répond, on affiche les CALQUES avec leur nombre d'entités,
   on fait choisir le calque d'enveloppe et les calques d'obstacles, l'unité du
   fichier, et l'aperçu se recentre tout seul sur l'enveloppe choisie. */
import { useCallback, useMemo, useState } from 'react'

const UNITES = [
  { cle: 'm', libelle: 'mètre', facteur: 1 },
  { cle: 'cm', libelle: 'centimètre', facteur: 0.01 },
  { cle: 'mm', libelle: 'millimètre', facteur: 0.001 },
  { cle: 'pouce', libelle: 'pouce', facteur: 0.0254 },
  { cle: 'pied', libelle: 'pied', facteur: 0.3048 },
]

const MSG_INDISPONIBLE =
  "L'analyse des fichiers DXF n'est pas encore disponible sur ce serveur. " +
  'Vous pouvez importer le plan en PDF ou en image, ou tracer la toiture à la main : ' +
  'le DXF pourra être rattaché plus tard, la toiture n’est pas perdue.'

function messageErreur(err) {
  const statut = err?.response?.status ?? err?.statut
  if (statut === 404) return MSG_INDISPONIBLE
  if (statut === 413) return 'Ce DXF est trop volumineux pour être analysé. Simplifiez-le puis réessayez.'
  if (statut === 415 || statut === 400)
    return "Ce fichier n'a pas pu être lu comme un DXF. Vérifiez qu'il s'agit bien d'un export DXF (et non DWG)."
  if (statut >= 500)
    return `Le serveur n'a pas pu analyser ce DXF (erreur ${statut}). Réessayez, ou tracez la toiture à la main.`
  return (
    "L'analyse du DXF a échoué (connexion ou fichier illisible). " +
    'Vous pouvez réessayer, ou tracer la toiture à la main.'
  )
}

/* Boîte englobante d'une liste de sommets [[x, y], …] → viewBox SVG recentrée.
   Une enveloppe sans sommets rend une viewBox neutre plutôt qu'un NaN. */
function viewBoxDe(sommets) {
  if (!Array.isArray(sommets) || sommets.length === 0) return '0 0 100 100'
  const xs = sommets.map((s) => Number(s[0])).filter(Number.isFinite)
  const ys = sommets.map((s) => Number(s[1])).filter(Number.isFinite)
  if (xs.length === 0 || ys.length === 0) return '0 0 100 100'
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const largeur = Math.max(...xs) - minX || 1
  const hauteur = Math.max(...ys) - minY || 1
  // `bordure` : respiration du viewBox (8 % du plus grand côté). Ce n'est PAS
  // une marge métier — la nommer autrement garde la garde AOF94 lisible.
  const bordure = Math.max(largeur, hauteur) * 0.08
  return `${minX - bordure} ${minY - bordure} ${largeur + bordure * 2} ${hauteur + bordure * 2}`
}

export default function ImportDxf({ analyserDxf, onImporter, onTracerAlaMain }) {
  const [etat, setEtat] = useState('attente') // attente | analyse | pret | degrade
  const [message, setMessage] = useState('')
  const [calques, setCalques] = useState([])
  const [enveloppe, setEnveloppe] = useState('')
  const [obstacles, setObstacles] = useState([])
  const [unite, setUnite] = useState('m')

  const choisirFichier = useCallback(
    async (fichier) => {
      if (!fichier) return
      if (typeof analyserDxf !== 'function') {
        setEtat('degrade')
        setMessage(MSG_INDISPONIBLE)
        return
      }
      setEtat('analyse')
      setMessage('')
      try {
        const resultat = await analyserDxf(fichier)
        const liste = Array.isArray(resultat?.calques) ? resultat.calques : []
        if (liste.length === 0) {
          setEtat('degrade')
          setMessage(
            "Ce DXF ne contient aucun calque exploitable. Vérifiez l'export, " +
              'ou tracez la toiture à la main.',
          )
          return
        }
        setCalques(liste)
        // Par défaut : le calque le plus fourni en sommets fait l'enveloppe.
        const avecSommets = liste.filter((c) => Array.isArray(c.sommets) && c.sommets.length >= 3)
        setEnveloppe((avecSommets[0] || liste[0]).nom)
        setObstacles([])
        if (resultat?.unite && UNITES.some((u) => u.cle === resultat.unite)) setUnite(resultat.unite)
        setEtat('pret')
      } catch (err) {
        setEtat('degrade')
        setMessage(messageErreur(err))
      }
    },
    [analyserDxf],
  )

  const calqueEnveloppe = useMemo(
    () => calques.find((c) => c.nom === enveloppe) || null,
    [calques, enveloppe],
  )

  const sommetsApercu = useMemo(() => calqueEnveloppe?.sommets ?? [], [calqueEnveloppe])

  const basculerObstacle = useCallback((nom) => {
    setObstacles((prec) => (prec.includes(nom) ? prec.filter((n) => n !== nom) : [...prec, nom]))
  }, [])

  const importer = useCallback(() => {
    const facteur = UNITES.find((u) => u.cle === unite)?.facteur ?? 1
    onImporter?.({
      calqueEnveloppe: enveloppe,
      calquesObstacles: [...obstacles],
      unite,
      facteurVersMetres: facteur,
      sommets: sommetsApercu.map(([x, y]) => [Number(x) * facteur, Number(y) * facteur]),
    })
  }, [enveloppe, obstacles, unite, sommetsApercu, onImporter])

  return (
    <section className="ao-dxf" data-ao-import-dxf>
      <h3>Importer un DXF</h3>

      <label className="ao-champ" htmlFor="ao-dxf-fichier">
        <span>Fichier DXF</span>
        <input
          id="ao-dxf-fichier"
          type="file"
          accept=".dxf,application/dxf,image/vnd.dxf"
          onChange={(e) => choisirFichier(e.target.files?.[0])}
        />
      </label>

      {etat === 'analyse' && <p className="ao-hint">⏳ Analyse des calques…</p>}

      {etat === 'degrade' && (
        <div className="ao-dxf-degrade" role="alert" data-ao-dxf-degrade>
          <p>{message}</p>
          <button type="button" onClick={() => onTracerAlaMain?.()} data-ao-dxf-repli>
            Tracer la toiture à la main
          </button>
        </div>
      )}

      {etat === 'pret' && (
        <>
          <table className="data-table ao-dxf-calques" data-ao-dxf-calques>
            <caption>Calques du fichier</caption>
            <thead>
              <tr>
                <th scope="col">Calque</th>
                <th scope="col">Entités</th>
                <th scope="col">Enveloppe</th>
                <th scope="col">Obstacles</th>
              </tr>
            </thead>
            <tbody>
              {calques.map((c) => (
                <tr key={c.nom}>
                  <th scope="row">{c.nom}</th>
                  <td>{Number(c.entites) || 0}</td>
                  <td>
                    <input
                      type="radio"
                      name="ao-dxf-enveloppe"
                      value={c.nom}
                      checked={enveloppe === c.nom}
                      onChange={() => setEnveloppe(c.nom)}
                      aria-label={`Calque d'enveloppe : ${c.nom}`}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={obstacles.includes(c.nom)}
                      onChange={() => basculerObstacle(c.nom)}
                      aria-label={`Calque d'obstacles : ${c.nom}`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <label className="ao-champ" htmlFor="ao-dxf-unite">
            <span>Unité du fichier</span>
            <select
              id="ao-dxf-unite"
              className="form-select"
              value={unite}
              onChange={(e) => setUnite(e.target.value)}
            >
              {UNITES.map((u) => (
                <option key={u.cle} value={u.cle}>
                  {u.libelle}
                </option>
              ))}
            </select>
          </label>

          <figure className="ao-dxf-apercu">
            <figcaption>Aperçu — recentré sur le calque d&apos;enveloppe</figcaption>
            <svg
              viewBox={viewBoxDe(sommetsApercu)}
              role="img"
              aria-label={`Aperçu du calque ${enveloppe}`}
              data-ao-dxf-apercu
              data-viewbox={viewBoxDe(sommetsApercu)}
            >
              {sommetsApercu.length >= 3 && (
                <polygon
                  points={sommetsApercu.map(([x, y]) => `${x},${y}`).join(' ')}
                  className="ao-dxf-enveloppe"
                />
              )}
            </svg>
          </figure>

          <button type="button" onClick={importer} data-ao-dxf-importer>
            Importer ce mapping
          </button>
        </>
      )}
    </section>
  )
}
