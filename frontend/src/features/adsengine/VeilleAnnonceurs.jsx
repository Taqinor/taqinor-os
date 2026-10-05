import { useEffect, useState, useCallback } from 'react'
import { Download, ExternalLink } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { nomPays } from './VeilleLibelles'

/* ============================================================================
   VEIL31 — Annonceurs découverts, groupés par classe (D-VEIL-1/2).
   ----------------------------------------------------------------------------
   Forme = contrat `contract_samples/veille_annonceur.json`. Classes et libellés
   lus dans `classes_disponibles` servi par le serveur (jamais en dur).
   - Vendeurs d'abord, avec l'étiquette « dropshipper probable » (un ATTRIBUT,
     jamais une classe) et un filtre « dropshippers seulement » ;
   - Places de marché et géants : onglet À PART (jamais supprimés) ;
   - puis chaque classe de bruit, puis les Incertains.
   Corrections humaines par BOUTONS seulement (aucun raccourci clavier) ; le
   lien vers la bibliothèque Meta s'ouvre par un clic humain, jamais un fetch.
   Une erreur réseau s'affiche sous le bouton : la liste n'est jamais vidée en
   silence.
   ========================================================================== */

const DECIDE_PAR = { regle: 'règle', ia: 'IA', humain: 'humain' }
const sansJeton = (url) => (url && !/access_token/i.test(url) ? url : null)

function ordreGroupes(classes) {
  const vendeur = classes.filter(c => c.cle === 'vendeur')
  const bruit = classes.filter(c => c.est_bruit && c.cle !== 'place_de_marche')
  const autres = classes.filter(c => !c.est_bruit && c.cle !== 'vendeur')
  return [...vendeur, ...bruit, ...autres]
}

function CarteAnnonceur({ annonceur, classesBruit, onVerdict, erreur, busy }) {
  const [choixBruit, setChoixBruit] = useState(null)
  const [classeBruit, setClasseBruit] = useState('')
  const v = annonceur.verdict
  const d = annonceur.dropshipper
  const lien = sansJeton(annonceur.lien_bibliotheque)
  const id = annonceur.id
  return (
    <li className="list-group-item" data-testid={`ae-veille-annonceur-${id}`}>
      <div className="d-flex justify-content-between flex-wrap gap-2">
        <strong>{annonceur.page_name || annonceur.page_id}</strong>
        <span className="small text-muted">
          {annonceur.nb_pubs_vues} pub(s) · {(annonceur.pays_vus || []).map(nomPays).join(', ')}
        </span>
      </div>
      {d?.probable === 'oui' && (
        <span className="badge bg-warning text-dark" data-testid={`ae-veille-annonceur-dropshipper-${id}`}>
          Dropshipper probable
        </span>
      )}
      {v && (
        <p className="small mb-1" data-testid={`ae-veille-annonceur-motif-${id}`}>
          {v.motif_fr}{' '}
          <em data-testid={`ae-veille-annonceur-decide-${id}`}>
            (décidé par : {DECIDE_PAR[v.decide_par] || v.decide_par})
          </em>
        </p>
      )}
      {(v?.preuves || []).length > 0 && (
        <ul className="small mb-1" data-testid={`ae-veille-annonceur-preuves-${id}`}>
          {v.preuves.map((p, i) => (
            <li key={i}><code>{p.champ}</code> : {String(p.valeur).slice(0, 200)}</li>
          ))}
        </ul>
      )}
      {(annonceur.extraits || []).length > 0 && (
        <ul className="small mb-1 text-muted">
          {annonceur.extraits.map(e => <li key={e.ad_archive_id}>{e.texte.slice(0, 200)}</li>)}
        </ul>
      )}
      {(annonceur.domaines || []).length > 0 && (
        <p className="small mb-1">
          Domaines : {annonceur.domaines.map(x => `${x.domaine} (${x.nb})`).join(', ')}
        </p>
      )}
      {(annonceur.historique || []).length > 0 && (
        <p className="small mb-1 text-muted" data-testid={`ae-veille-annonceur-historique-${id}`}>
          Avant : {annonceur.historique.map(h => `${h.classe} (${DECIDE_PAR[h.decide_par] || h.decide_par})`).join(' → ')}
        </p>
      )}
      {lien && (
        <a
          href={lien} target="_blank" rel="noopener noreferrer"
          className="btn btn-sm btn-light me-2" data-testid={`ae-veille-annonceur-lien-${id}`}>
          <ExternalLink size={13} aria-hidden="true" /> Voir dans la bibliothèque Meta
        </a>
      )}
      <div className="d-flex flex-wrap gap-2 mt-2">
        <button
          type="button" className="btn btn-sm btn-outline-success" disabled={busy}
          data-testid={`ae-veille-annonceur-vendeur-${id}`}
          onClick={() => onVerdict(annonceur, { classe: 'vendeur' })}>
          C&apos;est bien un vendeur
        </button>
        <button
          type="button" className="btn btn-sm btn-outline-secondary" disabled={busy}
          data-testid={`ae-veille-annonceur-bruit-${id}`}
          onClick={() => setChoixBruit(true)}>
          C&apos;est du bruit
        </button>
        <button
          type="button" className="btn btn-sm btn-outline-warning" disabled={busy}
          data-testid={`ae-veille-annonceur-drop-oui-${id}`}
          onClick={() => onVerdict(annonceur, { classe: annonceur.classe, dropshipper: 'oui' })}>
          Dropshipper : oui
        </button>
        <button
          type="button" className="btn btn-sm btn-outline-warning" disabled={busy}
          data-testid={`ae-veille-annonceur-drop-non-${id}`}
          onClick={() => onVerdict(annonceur, { classe: annonceur.classe, dropshipper: 'non' })}>
          Dropshipper : non
        </button>
      </div>
      {choixBruit && (
        <div className="d-flex gap-2 mt-2">
          <select
            className="form-select form-select-sm" value={classeBruit}
            data-testid={`ae-veille-annonceur-classe-bruit-${id}`}
            onChange={e => setClasseBruit(e.target.value)}>
            <option value="">— Choisir le type de bruit —</option>
            {classesBruit.map(c => <option key={c.cle} value={c.cle}>{c.libelle_fr}</option>)}
          </select>
          <button
            type="button" className="btn btn-sm btn-secondary" disabled={busy || !classeBruit}
            data-testid={`ae-veille-annonceur-confirmer-bruit-${id}`}
            onClick={() => onVerdict(annonceur, { classe: classeBruit })}>
            Confirmer
          </button>
        </div>
      )}
      {erreur && (
        <div className="text-danger small mt-1" data-testid={`ae-veille-annonceur-erreur-${id}`}>
          {erreur}
        </div>
      )}
    </li>
  )
}

export default function VeilleAnnonceurs({ decouverteId = null }) {
  const [annonceurs, setAnnonceurs] = useState([])
  const [vue, setVue] = useState('liste')
  const [dropSeulement, setDropSeulement] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [errListe, setErrListe] = useState('')
  const [busy, setBusy] = useState(false)

  const charger = useCallback(() => {
    setErrListe('')
    const params = { page_size: 200 }
    if (decouverteId) params.decouverte = decouverteId
    adsengineApi.veille.annonceurs(params)
      .then(r => setAnnonceurs(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setErrListe('Annonceurs illisibles pour le moment : la liste affichée reste la dernière reçue.'))
  }, [decouverteId])

  useEffect(() => { charger() }, [charger])

  const classes = annonceurs[0]?.classes_disponibles || []
  const classesBruit = classes.filter(c => c.est_bruit)

  const onVerdict = async (annonceur, corps) => {
    setBusy(true)
    setErreurs(e => ({ ...e, [annonceur.id]: '' }))
    try {
      const r = await adsengineApi.veille.verdict(annonceur.id, corps)
      setAnnonceurs(liste => liste.map(a => (a.id === r.data.id ? r.data : a)))
    } catch (err) {
      setErreurs(e => ({
        ...e,
        [annonceur.id]: err?.response?.data?.detail || 'Correction non enregistrée (erreur réseau) : réessayer.',
      }))
    } finally {
      setBusy(false)
    }
  }

  const exporter = async () => {
    setErrListe('')
    try {
      const r = await adsengineApi.veille.exportCsv(decouverteId ? { decouverte: decouverteId } : {})
      const url = URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'veille-annonceurs.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setErrListe(err?.response?.status === 403
        ? 'Export réservé au gestionnaire d’une société autorisée.'
        : 'Export impossible pour le moment.')
    }
  }

  const carte = (a) => (
    <CarteAnnonceur
      key={a.id} annonceur={a} classesBruit={classesBruit} onVerdict={onVerdict}
      erreur={erreurs[a.id]} busy={busy} />
  )

  const places = annonceurs.filter(a => a.classe === 'place_de_marche')

  return (
    <div data-testid="ae-veille-annonceurs">
      <div className="d-flex flex-wrap gap-2 mb-2">
        <button
          type="button" className={`btn btn-sm ${vue === 'liste' ? 'btn-primary' : 'btn-light'}`}
          data-testid="ae-veille-annonceurs-vue-liste" onClick={() => setVue('liste')}>
          Vendeurs et bruit
        </button>
        <button
          type="button" className={`btn btn-sm ${vue === 'places' ? 'btn-primary' : 'btn-light'}`}
          data-testid="ae-veille-annonceurs-vue-places" onClick={() => setVue('places')}>
          {classes.find(c => c.cle === 'place_de_marche')?.libelle_fr || 'Places de marché'} ({places.length})
        </button>
        <button
          type="button" className="btn btn-sm btn-outline-primary ms-auto"
          data-testid="ae-veille-annonceurs-export" onClick={exporter}>
          <Download size={14} aria-hidden="true" /> Exporter en CSV
        </button>
      </div>
      {errListe && <div className="text-danger small mb-2" data-testid="ae-veille-annonceurs-erreur">{errListe}</div>}

      {vue === 'places' && (
        <ul className="list-group" data-testid="ae-veille-annonceurs-places">{places.map(carte)}</ul>
      )}

      {vue === 'liste' && ordreGroupes(classes).map(c => {
        let membres = annonceurs.filter(a => a.classe === c.cle)
        if (c.cle === 'vendeur' && dropSeulement) {
          membres = membres.filter(a => a.dropshipper?.probable === 'oui')
        }
        return (
          <section key={c.cle} className="mb-3" data-testid={`ae-veille-groupe-${c.cle}`}>
            <h3 className="h6">{c.libelle_fr} ({membres.length})</h3>
            {c.cle === 'vendeur' && (
              <label className="form-check-label small mb-1">
                <input
                  type="checkbox" className="form-check-input me-1"
                  data-testid="ae-veille-filtre-dropshippers"
                  checked={dropSeulement} onChange={e => setDropSeulement(e.target.checked)} />
                Dropshippers seulement
              </label>
            )}
            <ul className="list-group">{membres.map(carte)}</ul>
          </section>
        )
      })}
    </div>
  )
}
