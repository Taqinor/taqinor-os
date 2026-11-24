import { useCallback, useEffect, useState } from 'react'
import { Link, useMatch } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'

/* ACAL719 — l'heure LÉGALE à côté de l'heure solaire. L'atelier positionne le soleil en heure solaire vraie
   (midi = soleil au plus haut) : le serveur (`GET soleil-legal/?date=`, ACAL730) sait la convertir ; cet écran ne
   fait qu'ajouter l'écart servi. Un seul appel par date, gardé pour la session ; jamais persisté. */

const INFOBULLE_SOLAIRE = 'heure vraie du lieu : midi = soleil au plus haut'
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

const cache = new Map()
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, testé directement (D-ENF22)
export const viderCacheHeureLegale = () => cache.clear()

function lire(id, date) {
  const cle = `${id}|${date}`
  if (!cache.has(cle)) {
    // T4-U4-015 — la phrase de l'écran dit le refus : aucun toast global « Site.pin : … » en plus.
    const config = { suppressErrorToast: true }
    cache.set(cle, Promise.resolve().then(() => calepinageApi.calepinages.soleilLegal(id, { date }, config)).then(
      (r) => ({ etat: 'ok', ecart: r?.data?.ecart_legal_moins_solaire_min ?? null }),
      (err) => {
        if (err?.response?.status === 409) {
          return { etat: err.response.data?.['site.pin'] ? 'pin' : 'fuseau' }
        }
        cache.delete(cle) // une panne réseau se retente
        return { etat: 'erreur' }
      },
    ))
  }
  return cache.get(cle)
}

/** « 13 h 45 » : l'heure solaire plus l'écart servi par le serveur (minutes), à la minute près. */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, testé directement (D-ENF22)
export function formaterHeureLegale(heureSolaire, ecartMin) {
  const total = Math.round(heureSolaire * 60 + ecartMin)
  const h = ((Math.floor(total / 60) % 24) + 24) % 24
  return `${h} h ${String(((total % 60) + 60) % 60).padStart(2, '0')}`
}

/** Le jour de l'année d'une scène → une date AAAA-MM-JJ de l'année courante (déclarée dans le texte). */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, testé directement (D-ENF22)
export function dateDuJourDeScene(jour, annee = new Date().getFullYear()) {
  let d = new Date(Date.UTC(annee, 0, jour))
  if (d.getUTCFullYear() !== annee) d = new Date(Date.UTC(annee, 0, 365))
  return `${annee}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
}

// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, testé directement (D-ENF22)
export function useHeureLegale(calepinageId, date) {
  const [lu, setLu] = useState({ cle: '', etat: 'chargement', ecart: null })
  const cle = calepinageId && date ? `${calepinageId}|${date}` : ''
  useEffect(() => {
    if (!cle) return undefined
    let vivant = true
    lire(calepinageId, date).then((r) => { if (vivant) setLu({ cle, ...r }) })
    return () => { vivant = false }
  }, [cle, calepinageId, date])
  if (!cle || lu.cle !== cle) return { etat: 'chargement', ecart: null }
  return lu
}

/** La phrase d'indisponibilité, ou `null` quand l'écart est servi. */
export function PhraseHeureIndisponible({ etat }) {
  if (etat === 'fuseau') {
    return (
      <>heure légale non calculée : fuseau du site non renseigné{' '}
        (<Link to="/calepinage/reglages" className="underline">Réglages › site</Link>)</>
    )
  }
  if (etat === 'pin') return <>heure légale non calculée : posez d’abord l’épingle du site sur la carte</>
  if (etat === 'erreur') return <>heure légale indisponible pour le moment</>
  return null
}

export default function HeureLegale({ calepinageId } = {}) {
  const correspondance = useMatch({ path: '/calepinage/:id', end: false })
  const id = calepinageId ?? correspondance?.params?.id
  const [bar, setBar] = useState({ heure: null, md: null })

  const relire = useCallback(() => {
    const h = Number(document.getElementById('rp9-sun-hour')?.value)
    const v = document.getElementById('rp9-sun-date')?.value ?? ''
    const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(v)
    const suivant = { heure: Number.isFinite(h) ? h : null, md: m ? `${m[1]}-${m[2]}` : null }
    setBar((prec) => (prec.heure === suivant.heure && prec.md === suivant.md ? prec : suivant))
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture initiale de la barre du soleil, hors React (D-ENF22)
    relire()
    const apres = () => setTimeout(relire, 0)
    const surEvenement = (e) => {
      if (e.target?.id === 'rp9-sun-hour' || e.target?.id === 'rp9-sun-date') relire()
      else if (e.target?.closest?.('[data-sun-season]')) apres()
    }
    document.addEventListener('input', surEvenement)
    document.addEventListener('change', surEvenement)
    document.addEventListener('click', surEvenement)
    const hote = document.getElementById('rp9-sun-controls')
    const observateur = hote && typeof MutationObserver === 'function' ? new MutationObserver(relire) : null // la date est créée par le script après le montage
    observateur?.observe(hote, { childList: true })
    return () => {
      document.removeEventListener('input', surEvenement)
      document.removeEventListener('change', surEvenement)
      document.removeEventListener('click', surEvenement)
      observateur?.disconnect()
    }
  }, [relire])

  const annee = new Date().getFullYear()
  const date = bar.md ? `${annee}-${bar.md}` : null
  const { etat, ecart } = useHeureLegale(id, date)
  if (!id || bar.heure === null) return null

  const solaire = <>{bar.heure} h <abbr title={INFOBULLE_SOLAIRE}>solaire</abbr></>
  const legale = etat === 'ok' && ecart != null ? `${formaterHeureLegale(bar.heure, ecart)} heure légale` : null
  const jour = bar.md ? `${Number(bar.md.slice(3))} ${MOIS[Number(bar.md.slice(0, 2)) - 1]} ${annee}` : null
  return (
    <p id="rp9-sun-legal" className="min-h-11 text-sm text-muted-foreground" aria-live="polite">
      {solaire}
      {legale ? <> ({legale})</> : null}
      {etat !== 'ok' && etat !== 'chargement' ? <> — <PhraseHeureIndisponible etat={etat} /></> : null}
      {' '}· L’atelier compte en heure solaire vraie{jour ? ` · calculé pour le ${jour} (année en cours)` : ''}.
    </p>
  )
}
