import { useCallback, useEffect, useState } from 'react'
import calepinageApi from '../../../api/calepinageApi'
import useDocumentCalepinage from '../useDocumentCalepinage'
import { zonesDuDocument } from '../SaisiePente.helpers'
import { copieEntree, refusParChamp } from './entreeElectrique'

/* ACAL641 — « Parcours du câble » par pan : le motif (le long de la rangée / aller-retour) et le
   point de collecte, que le serveur lit (`cheminement.pans.<clé du pan>`, services/cables.py) mais
   qu'aucun écran n'écrivait. Aucun motif n'est présélectionné ni envoyé d'office : tant que rien
   n'est choisi, l'écran montre le détail publié de la longueur (`longueur_detail`). Le point de
   collecte est le CENTRE d'un module posé du pan (`geometry.panels[]`) ; le serveur fait foi. */

const MOTIFS = [
  ['le_long_de_la_rangee', 'Le long de la rangée'],
  ['aller_retour', 'Aller-retour'],
]

const estObjet = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

export default function ParcoursDuPan({ calepinageId, troncons = [], lectureSeule = false, onEnregistre = null }) {
  const doc = useDocumentCalepinage(calepinageId)
  const [entree, setEntree] = useState(null)
  const [choix, setChoix] = useState({}) // { [clé du pan]: { motif, module } }
  const [erreurs, setErreurs] = useState({})
  const [message, setMessage] = useState(null)

  const lire = useCallback(() => Promise.resolve()
    .then(() => calepinageApi.calepinages.entreeElectrique(calepinageId))
    .then((res) => setEntree(res?.data?.entree ?? {}))
    .catch(() => setEntree(null)), [calepinageId])
  useEffect(() => { lire() }, [lire])

  const pans = zonesDuDocument(doc.document)
    .filter((z) => Array.isArray(z.geometry?.panels) && z.geometry.panels.length > 0)
  if (doc.etat !== 'ok' || entree === null || pans.length === 0) return null

  const existant = estObjet(entree.cheminement?.pans) ? entree.cheminement.pans : {}
  // ACAL1547 — le point enregistré (`point_collecte` = centre d'un module du pan) est relu : l'index du module
  // de `geometry.panels[]` dont le centre est ce point, ou '' (aucun point, ou point d'un module disparu).
  const moduleEnregistre = (cle, zone) => {
    const point = existant[cle]?.point_collecte
    if (!estObjet(point)) return ''
    const proche = (a, b) => Math.abs(Number(a) - Number(b)) < 1e-6
    const i = zone.geometry.panels.findIndex((p) => proche(p.cx, point.cx) && proche(p.cy, point.cy))
    return i < 0 ? '' : String(i)
  }
  const valeur = (cle, zone) => {
    const saisi = choix[cle] ?? {}
    return { motif: saisi.motif ?? existant[cle]?.motif_parcours ?? '', module: saisi.module ?? moduleEnregistre(cle, zone) }
  }
  const poser = (cle, champ, v) => setChoix((c) => ({ ...c, [cle]: { ...c[cle], [champ]: v } }))

  const enregistrer = () => {
    const nouveaux = copieEntree(existant)
    for (const zone of pans) {
      const cle = String(zone.id)
      const { motif, module } = valeur(cle, zone)
      const panneau = module === '' ? null : zone.geometry.panels[Number(module)]
      if (!motif && !panneau) continue
      nouveaux[cle] = { ...(nouveaux[cle] ?? {}) }
      if (motif) nouveaux[cle].motif_parcours = motif
      if (panneau) nouveaux[cle].point_collecte = { cx: panneau.cx, cy: panneau.cy }
    }
    const base = estObjet(entree.cheminement) ? copieEntree(entree.cheminement) : {}
    setErreurs({})
    setMessage(null)
    calepinageApi.calepinages.enregistrerEntreeElectrique(calepinageId, { cheminement: { ...base, pans: nouveaux } })
      .then(() => { setChoix({}); setMessage('Parcours enregistré : la longueur est relue.'); return lire() })
      .then(() => onEnregistre?.())
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setErreurs(Object.keys(parChamp).length ? parChamp : { parcours: 'Parcours non enregistré : le serveur n’a pas accepté la saisie.' })
      })
  }

  const details = troncons.filter((t) => t.cote === 'dc' && t.longueur_detail)
  return (
    <section className="flex flex-col gap-3" data-testid="acal641-bloc">
      <p className="text-xs font-medium text-muted-foreground">Parcours du câble, par pan</p>
      {pans.map((zone) => {
        const cle = String(zone.id)
        const { motif, module } = valeur(cle, zone)
        const erreurMotif = erreurs[`cheminement.pans.${cle}.motif_parcours`] ?? erreurs[`cheminement.pans.${cle}`]
        return (
          <div key={cle} className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid={`acal641-pan-${cle}`}>
            <label className="flex flex-col gap-1 text-sm text-foreground">
              {`${zone.label || cle} — parcours`}
              <select value={motif} disabled={lectureSeule} data-testid={`acal641-motif-${cle}`}
                onChange={(e) => poser(cle, 'motif', e.target.value)}
                className="h-11 border border-border bg-background px-2 text-sm text-foreground">
                <option value="">— non choisi —</option>
                {MOTIFS.map(([v, libelle]) => <option key={v} value={v}>{libelle}</option>)}
              </select>
              {erreurMotif && <span role="alert" className="text-xs text-destructive" data-testid={`acal641-erreur-${cle}`}>{erreurMotif}</span>}
            </label>
            <label className="flex flex-col gap-1 text-sm text-foreground">
              Point de collecte
              <select value={module} disabled={lectureSeule} data-testid={`acal641-point-${cle}`}
                onChange={(e) => poser(cle, 'module', e.target.value)}
                className="h-11 border border-border bg-background px-2 text-sm text-foreground">
                <option value="">— non choisi —</option>
                {zone.geometry.panels.map((p, i) => <option key={p.n ?? i} value={i}>{`Module n° ${p.n ?? i + 1}`}</option>)}
              </select>
            </label>
          </div>
        )
      })}
      {details.map((t) => <p key={t.id} className="text-xs text-muted-foreground" data-testid={`acal641-detail-${t.id}`}>{t.longueur_detail}</p>)}
      {erreurs.parcours && <p role="alert" className="text-xs text-destructive">{erreurs.parcours}</p>}
      {message && <p role="status" className="text-sm text-foreground">{message}</p>}
      {!lectureSeule && (
        <button type="button" onClick={enregistrer} data-testid="acal641-enregistrer"
          className="min-h-11 self-start rounded bg-brass-500/20 px-4 text-sm font-semibold text-primary-text">
          Enregistrer le parcours
        </button>
      )}
    </section>
  )
}
