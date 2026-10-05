import { useEffect, useState, useCallback } from 'react'
import { Plus, Play, RefreshCw } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { NOMS_PAYS } from './VeilleLibelles'

/* ============================================================================
   VEIL30 — Onglet « Découverte » : mots-clés × pays → lancement → état SERVI.
   ----------------------------------------------------------------------------
   Forme des données = contrat `contract_samples/veille_decouverte.json`.
   Tout l'état affiché vient du SERVEUR (statut, compteurs, journal des
   requêtes) : l'écran ne calcule rien. Une pause de quota affiche l'heure de
   reprise et AUCUN bouton de contournement. Plafonds d'appels et de pages
   OBLIGATOIRES (aucun défaut inventé). Un mot-clé fait au plus 100 caractères
   (limite de l'API) : l'erreur s'affiche sous le champ et rien n'est envoyé.
   ========================================================================== */

const LONGUEUR_MAX_MOT_CLE = 100

const LIBELLES_STATUT = {
  en_file: 'En file',
  en_cours: 'En cours',
  en_pause_quota: 'En pause',
  termine: 'Terminé',
  echec: 'Échec',
  annule: 'Annulé',
}
const LIBELLES_REQUETE = {
  a_faire: 'À faire', en_cours: 'En cours', terminee: 'Terminée',
  vide: 'Vide', plafond: 'Plafond atteint', erreur: 'Erreur',
}
const MODES = [
  { cle: 'KEYWORD_UNORDERED', libelle: 'Mots-clés (ordre libre)' },
  { cle: 'KEYWORD_EXACT_PHRASE', libelle: 'Expression exacte' },
]
const LIGNE_VIDE = { texte: '', pays: [] }

const heure = (iso) => (iso
  ? new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  : '')

function libelleStatut(dec) {
  if (!dec) return ''
  if (dec.statut === 'en_pause_quota') {
    return `En pause — quota atteint, reprise à ${heure(dec.reprise_a)}`
  }
  if (dec.statut === 'echec') {
    const derniere = (dec.erreurs || []).at(-1)
    return `Échec${derniere?.message_fr ? ` — ${derniere.message_fr}` : ''}`
  }
  return LIBELLES_STATUT[dec.statut] || dec.statut
}

function valider(lignes, plafondAppels, plafondPages) {
  const erreurs = { mots: {}, pays: {}, plafonds: '' }
  lignes.forEach((l, i) => {
    const texte = l.texte.trim()
    if (!texte) erreurs.mots[i] = 'Mot-clé obligatoire.'
    else if (texte.length > LONGUEUR_MAX_MOT_CLE) {
      erreurs.mots[i] = `${texte.length} caractères : ${LONGUEUR_MAX_MOT_CLE} au plus (limite de l'API).`
    }
    if (!l.pays.length) erreurs.pays[i] = 'Choisir au moins un pays.'
  })
  const entier = (v) => /^\d+$/.test(String(v).trim()) && Number(v) > 0
  if (!entier(plafondAppels) || !entier(plafondPages)) {
    erreurs.plafonds = "Plafonds d'appels et de pages obligatoires (entiers positifs)."
  }
  const ok = !Object.keys(erreurs.mots).length && !Object.keys(erreurs.pays).length
    && !erreurs.plafonds
  return { ok, erreurs }
}

export default function VeilleDecouverte({ couverture = [], decouverteId = null, onSelection }) {
  const [decouvertes, setDecouvertes] = useState([])
  const [courante, setCourante] = useState(null)
  const [lignes, setLignes] = useState([LIGNE_VIDE])
  const [mode, setMode] = useState('KEYWORD_UNORDERED')
  const [plafondAppels, setPlafondAppels] = useState('')
  const [plafondPages, setPlafondPages] = useState('')
  const [erreurs, setErreurs] = useState({ mots: {}, pays: {}, plafonds: '' })
  const [busy, setBusy] = useState(false)
  const [errServeur, setErrServeur] = useState('')

  const paysDisponibles = couverture.filter(l => l.statut !== 'non_couvert')

  const selectionner = useCallback((dec) => {
    setCourante(dec)
    if (dec && onSelection) onSelection(dec.id)
  }, [onSelection])

  useEffect(() => {
    adsengineApi.veille.decouvertes()
      .then(r => {
        const liste = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        setDecouvertes(liste)
        const choisie = liste.find(d => d.id === decouverteId) || liste[0] || null
        selectionner(choisie)
      })
      .catch(() => setErrServeur('Découvertes illisibles pour le moment.'))
  // eslint-disable-next-line react-hooks/exhaustive-deps -- au montage seulement
  }, [])

  const majLigne = (i, patch) => setLignes(ls => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  const basculerPays = (i, code) => setLignes(ls => ls.map((l, j) => {
    if (j !== i) return l
    const pays = l.pays.includes(code) ? l.pays.filter(p => p !== code) : [...l.pays, code]
    return { ...l, pays }
  }))

  const lancer = async (e) => {
    e.preventDefault()
    setErrServeur('')
    const { ok, erreurs: errs } = valider(lignes, plafondAppels, plafondPages)
    setErreurs(errs)
    if (!ok) return
    setBusy(true)
    try {
      const r = await adsengineApi.veille.lancer({
        mots_cles: lignes.map(l => ({ texte: l.texte.trim(), pays: l.pays })),
        search_type: mode,
        ad_active_status: 'ACTIVE',
        plafond_appels: Number(plafondAppels),
        plafond_pages_par_requete: Number(plafondPages),
      })
      setDecouvertes(ds => [r.data, ...ds.filter(d => d.id !== r.data.id)])
      selectionner(r.data)
    } catch (err) {
      setErrServeur(err?.response?.data?.detail || 'Lancement impossible pour le moment.')
    } finally {
      setBusy(false)
    }
  }

  const agir = async (appel) => {
    if (!courante) return
    setBusy(true); setErrServeur('')
    try {
      const r = await appel(courante.id)
      setDecouvertes(ds => ds.map(d => (d.id === r.data.id ? r.data : d)))
      selectionner(r.data)
    } catch (err) {
      setErrServeur(err?.response?.data?.detail || 'Action impossible pour le moment.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div data-testid="ae-veille-decouverte">
      <form onSubmit={lancer} noValidate data-testid="ae-veille-decouverte-form" className="mb-4">
        {lignes.map((l, i) => (
          <fieldset key={i} className="border rounded p-2 mb-2" data-testid={`ae-veille-decouverte-ligne-${i}`}>
            <label className="form-label" htmlFor={`ae-veille-mot-${i}`}>Mot-clé</label>
            <input
              id={`ae-veille-mot-${i}`} className="form-control"
              data-testid={`ae-veille-decouverte-mot-${i}`} value={l.texte}
              onChange={e => majLigne(i, { texte: e.target.value })} />
            {erreurs.mots[i] && (
              <div className="text-danger small" data-testid={`ae-veille-decouverte-erreur-mot-${i}`}>
                {erreurs.mots[i]}
              </div>
            )}
            <div className="d-flex flex-wrap gap-2 mt-2">
              {paysDisponibles.map(p => (
                <label key={p.pays} className="form-check-label small">
                  <input
                    type="checkbox" className="form-check-input me-1"
                    data-testid={`ae-veille-decouverte-pays-${i}-${p.pays}`}
                    checked={l.pays.includes(p.pays)}
                    onChange={() => basculerPays(i, p.pays)} />
                  {NOMS_PAYS[p.pays] || p.pays}
                  {p.statut === 'a_confirmer' && ' (à confirmer)'}
                </label>
              ))}
            </div>
            {erreurs.pays[i] && (
              <div className="text-danger small" data-testid={`ae-veille-decouverte-erreur-pays-${i}`}>
                {erreurs.pays[i]}
              </div>
            )}
          </fieldset>
        ))}
        <button
          type="button" className="btn btn-sm btn-light mb-2"
          data-testid="ae-veille-decouverte-ajouter-mot"
          onClick={() => setLignes(ls => [...ls, LIGNE_VIDE])}>
          <Plus size={14} aria-hidden="true" /> Ajouter un mot-clé
        </button>
        <div className="row g-2">
          <div className="col-md-4">
            <label className="form-label" htmlFor="ae-veille-mode">Mode de recherche</label>
            <select
              id="ae-veille-mode" className="form-select" value={mode}
              data-testid="ae-veille-decouverte-mode" onChange={e => setMode(e.target.value)}>
              {MODES.map(m => <option key={m.cle} value={m.cle}>{m.libelle}</option>)}
            </select>
          </div>
          <div className="col-md-3">
            <label className="form-label" htmlFor="ae-veille-plafond-appels">Plafond d&apos;appels</label>
            <input
              id="ae-veille-plafond-appels" className="form-control" inputMode="numeric"
              data-testid="ae-veille-decouverte-plafond-appels" value={plafondAppels}
              onChange={e => setPlafondAppels(e.target.value)} />
          </div>
          <div className="col-md-3">
            <label className="form-label" htmlFor="ae-veille-plafond-pages">Plafond de pages par requête</label>
            <input
              id="ae-veille-plafond-pages" className="form-control" inputMode="numeric"
              data-testid="ae-veille-decouverte-plafond-pages" value={plafondPages}
              onChange={e => setPlafondPages(e.target.value)} />
          </div>
        </div>
        {erreurs.plafonds && (
          <div className="text-danger small" data-testid="ae-veille-decouverte-erreur-plafonds">
            {erreurs.plafonds}
          </div>
        )}
        <button
          type="submit" className="btn btn-primary mt-3" disabled={busy}
          data-testid="ae-veille-decouverte-lancer">
          <Play size={15} aria-hidden="true" /> Lancer une découverte
        </button>
        {errServeur && (
          <div className="text-danger small mt-1" data-testid="ae-veille-decouverte-erreur-serveur">
            {errServeur}
          </div>
        )}
      </form>

      {decouvertes.length > 1 && (
        <select
          className="form-select mb-2" data-testid="ae-veille-decouverte-choix"
          value={courante?.id || ''}
          onChange={e => selectionner(decouvertes.find(d => String(d.id) === e.target.value))}>
          {decouvertes.map(d => (
            <option key={d.id} value={d.id}>
              Découverte n° {d.id} — {LIBELLES_STATUT[d.statut] || d.statut}
            </option>
          ))}
        </select>
      )}

      {courante && (
        <section data-testid="ae-veille-decouverte-etat">
          <h2 className="h6">Découverte n° {courante.id}</h2>
          <p data-testid="ae-veille-decouverte-statut" data-statut={courante.statut}>
            {libelleStatut(courante)}
          </p>
          <p className="small" data-testid="ae-veille-decouverte-compteurs">
            Appels : {courante.appels_consommes} / {courante.plafond_appels} ·
            {' '}Pages lues : {courante.pages_lues} · Pubs reçues : {courante.pubs_recues} ·
            {' '}Annonceurs distincts : {courante.annonceurs_distincts}
          </p>
          <div className="d-flex gap-2 mb-2">
            <button
              type="button" className="btn btn-sm btn-light" disabled={busy}
              data-testid="ae-veille-decouverte-actualiser"
              onClick={() => agir(adsengineApi.veille.decouverte)}>
              <RefreshCw size={14} aria-hidden="true" /> Actualiser
            </button>
            {['en_file', 'en_cours', 'en_pause_quota'].includes(courante.statut) && (
              <button
                type="button" className="btn btn-sm btn-outline-danger" disabled={busy}
                data-testid="ae-veille-decouverte-annuler"
                onClick={() => agir(adsengineApi.veille.annuler)}>
                Annuler
              </button>
            )}
            {courante.statut === 'echec' && (
              <button
                type="button" className="btn btn-sm btn-outline-primary" disabled={busy}
                data-testid="ae-veille-decouverte-reprendre"
                onClick={() => agir(adsengineApi.veille.reprendre)}>
                Reprendre
              </button>
            )}
          </div>
          <table className="table table-sm" data-testid="ae-veille-decouverte-journal">
            <thead>
              <tr>
                <th>Mot-clé</th><th>Pays</th><th>Statut</th><th>Pages</th>
                <th>Appels</th><th>Pubs</th><th>Nouveaux annonceurs</th>
              </tr>
            </thead>
            <tbody>
              {(courante.requetes || []).map((r, i) => (
                <tr key={`${r.mot_cle}-${r.pays}`} data-testid={`ae-veille-decouverte-requete-${i}`}>
                  <td>{r.mot_cle}</td>
                  <td>{NOMS_PAYS[r.pays] || r.pays}</td>
                  <td>{LIBELLES_REQUETE[r.statut] || r.statut}</td>
                  <td>{r.pages_lues}</td>
                  <td>{r.appels}</td>
                  <td>{r.pubs}</td>
                  <td>{r.nouveaux_annonceurs}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
