import { useEffect, useState, useCallback } from 'react'
import { ExternalLink } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   VEIL32 — Mode « Échantillon de mesure » : étiquetage À L'AVEUGLE (D-VEIL-4).
   ----------------------------------------------------------------------------
   Le tirage (`echantillon/`) gèle deux jeux disjoints (étalonnage, test). Ici
   l'humain étiquette chaque annonceur SANS voir aucun verdict machine : l'écran
   n'affiche jamais classe, motif ni historique (et le serveur, en mode
   aveugle, ne les sert pas). L'étiquette part par `etiquette/` et ne touche
   jamais le verdict courant. Le compteur « N / taille » vient du SERVEUR
   (nombre d'annonceurs du jeu, nombre restant sans étiquette) : fermer l'onglet
   puis revenir reprend au bon compteur.
   ========================================================================== */

const JEUX = [
  { cle: 'etalonnage', libelle: 'Étalonnage' },
  { cle: 'test', libelle: 'Test' },
]
const TRI = [
  { cle: 'oui', libelle: 'Oui' },
  { cle: 'non', libelle: 'Non' },
  { cle: 'incertain', libelle: 'Incertain' },
]
const sansJeton = (url) => (url && !/access_token/i.test(url) ? url : null)
const liste = (r) => (Array.isArray(r.data) ? r.data : (r.data?.results || []))
const total = (r) => (Array.isArray(r.data) ? r.data.length : (r.data?.count ?? liste(r).length))

export default function VeilleEtiquetage({ decouverteId = null }) {
  const [jeu, setJeu] = useState('test')
  const [tailleE, setTailleE] = useState('')
  const [tailleT, setTailleT] = useState('')
  const [compteur, setCompteur] = useState(null)
  const [courant, setCourant] = useState(null)
  const [classe, setClasse] = useState('')
  const [dropshipper, setDropshipper] = useState('')
  const [message, setMessage] = useState('')
  const [erreur, setErreur] = useState('')
  const [busy, setBusy] = useState(false)

  const charger = useCallback(async () => {
    if (!decouverteId) return
    setErreur('')
    try {
      const base = { decouverte: decouverteId, jeu, aveugle: '1' }
      const [tous, restants] = await Promise.all([
        adsengineApi.veille.annonceurs({ ...base, page_size: 1 }),
        adsengineApi.veille.annonceurs({ ...base, sans_etiquette: '1', page_size: 1 }),
      ])
      const taille = total(tous)
      const reste = total(restants)
      setCompteur({ fait: taille - reste, taille })
      setCourant(liste(restants)[0] || null)
      setClasse('')
      setDropshipper('')
    } catch {
      setErreur("Échantillon illisible pour le moment.")
    }
  }, [decouverteId, jeu])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { charger() }, [charger])

  const tirer = async () => {
    setErreur(''); setMessage('')
    if (!/^\d+$/.test(tailleE) || !/^\d+$/.test(tailleT) || !Number(tailleE) || !Number(tailleT)) {
      setErreur("Tailles d'étalonnage et de test obligatoires (entiers positifs).")
      return
    }
    setBusy(true)
    try {
      const r = await adsengineApi.veille.echantillon(decouverteId, {
        taille_etalonnage: Number(tailleE), taille_test: Number(tailleT),
      })
      setMessage(r.data.deja_tire
        ? 'Échantillon déjà tiré : le tirage gelé est conservé.'
        : `Échantillon tiré : ${r.data.etalonnage.length} + ${r.data.test.length} annonceurs.`)
      await charger()
    } catch (err) {
      setErreur(err?.response?.data?.detail || 'Tirage impossible pour le moment.')
    } finally {
      setBusy(false)
    }
  }

  const enregistrer = async () => {
    if (!courant || !classe || !dropshipper) return
    setBusy(true); setErreur('')
    try {
      await adsengineApi.veille.etiquette(courant.id, { classe, dropshipper })
      await charger()
    } catch (err) {
      setErreur(err?.response?.data?.detail || 'Étiquette non enregistrée : réessayer.')
    } finally {
      setBusy(false)
    }
  }

  if (!decouverteId) {
    return <p data-testid="ae-veille-etiquetage-vide">Choisir d&apos;abord une découverte.</p>
  }

  const classes = courant?.classes_disponibles || []
  const lien = sansJeton(courant?.lien_bibliotheque)

  return (
    <div data-testid="ae-veille-etiquetage">
      <div className="row g-2 mb-2">
        <div className="col-md-3">
          <label className="form-label" htmlFor="ae-veille-taille-e">Taille étalonnage</label>
          <input
            id="ae-veille-taille-e" className="form-control" inputMode="numeric"
            data-testid="ae-veille-etiquetage-taille-etalonnage" value={tailleE}
            onChange={e => setTailleE(e.target.value)} />
        </div>
        <div className="col-md-3">
          <label className="form-label" htmlFor="ae-veille-taille-t">Taille test</label>
          <input
            id="ae-veille-taille-t" className="form-control" inputMode="numeric"
            data-testid="ae-veille-etiquetage-taille-test" value={tailleT}
            onChange={e => setTailleT(e.target.value)} />
        </div>
        <div className="col-md-3 d-flex align-items-end">
          <button
            type="button" className="btn btn-outline-primary" disabled={busy}
            data-testid="ae-veille-etiquetage-tirer" onClick={tirer}>
            Tirer l&apos;échantillon
          </button>
        </div>
      </div>
      <div className="btn-group mb-2" role="group">
        {JEUX.map(j => (
          <button
            key={j.cle} type="button"
            className={`btn btn-sm ${jeu === j.cle ? 'btn-primary' : 'btn-light'}`}
            data-testid={`ae-veille-etiquetage-jeu-${j.cle}`} onClick={() => setJeu(j.cle)}>
            {j.libelle}
          </button>
        ))}
      </div>
      {compteur && (
        <p data-testid="ae-veille-etiquetage-compteur">
          {compteur.fait} / {compteur.taille}
        </p>
      )}
      {message && <div className="text-success small" data-testid="ae-veille-etiquetage-message">{message}</div>}
      {erreur && <div className="text-danger small" data-testid="ae-veille-etiquetage-erreur">{erreur}</div>}

      {courant ? (
        <section className="border rounded p-2" data-testid="ae-veille-etiquetage-fiche">
          <strong>{courant.page_name || courant.page_id}</strong>
          <ul className="small">
            {(courant.extraits || []).map(x => <li key={x.ad_archive_id}>{x.texte.slice(0, 200)}</li>)}
          </ul>
          {(courant.domaines || []).length > 0 && (
            <p className="small">Domaines : {courant.domaines.map(d => d.domaine).join(', ')}</p>
          )}
          {lien && (
            <a href={lien} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-light mb-2">
              <ExternalLink size={13} aria-hidden="true" /> Voir dans la bibliothèque Meta
            </a>
          )}
          <div className="d-flex flex-wrap gap-2 mb-2">
            {classes.map(c => (
              <button
                key={c.cle} type="button"
                className={`btn btn-sm ${classe === c.cle ? 'btn-dark' : 'btn-outline-dark'}`}
                data-testid={`ae-veille-etiquetage-classe-${c.cle}`} onClick={() => setClasse(c.cle)}>
                {c.libelle_fr}
              </button>
            ))}
          </div>
          <div className="d-flex flex-wrap gap-2 mb-2">
            <span className="small align-self-center">Dropshipper :</span>
            {TRI.map(t => (
              <button
                key={t.cle} type="button"
                className={`btn btn-sm ${dropshipper === t.cle ? 'btn-warning' : 'btn-outline-warning'}`}
                data-testid={`ae-veille-etiquetage-drop-${t.cle}`} onClick={() => setDropshipper(t.cle)}>
                {t.libelle}
              </button>
            ))}
          </div>
          <button
            type="button" className="btn btn-primary btn-sm" disabled={busy || !classe || !dropshipper}
            data-testid="ae-veille-etiquetage-enregistrer" onClick={enregistrer}>
            Enregistrer l&apos;étiquette
          </button>
        </section>
      ) : (
        compteur && <p data-testid="ae-veille-etiquetage-fini">Aucun annonceur à étiqueter dans ce jeu.</p>
      )}
    </div>
  )
}
