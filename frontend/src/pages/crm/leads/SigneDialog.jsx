// Dialogue « Signé » (A2) — quand un lead est déplacé dans l'étape Signé
// (glisser-déposer kanban ou édition en place de l'étape), on demande QUEL
// devis du lead a été accepté et QUELLE option (Sans batterie / Avec batterie).
// Confirmer marque ce devis « accepté » (réutilise A1 : POST .../accepter/) ;
// l'acceptation fait avancer le lead en Signé côté serveur. Si le lead n'a
// aucun devis, on l'explique et on NE déplace PAS l'étape — jamais de devis
// inventé, jamais de passage en Signé sans devis (règles #2/#4 : l'étape du
// funnel et le statut du document restent deux couches séparées).
import { useEffect, useMemo, useState } from 'react'
import { FileWarning } from 'lucide-react'
import ventesApi from '../../../api/ventesApi'
import { Button, Spinner } from '../../../ui'

const OPTION_LABELS = {
  sans_batterie: 'Sans batterie',
  avec_batterie: 'Avec batterie',
}

const STATUT_LABELS = {
  brouillon: 'Brouillon',
  envoye: 'Envoyé',
  accepte: 'Accepté',
  refuse: 'Refusé',
  expire: 'Expiré',
}

// Devis « actionnables » : version courante (is_active) et non refusés.
function selectableDevis(list) {
  return (list ?? []).filter(
    (d) => d.is_active !== false && d.statut !== 'refuse',
  )
}

// Devis le plus PERTINENT à présélectionner : le plus récent ENVOYÉ ; à défaut
// d'un envoyé, celui au total le plus élevé. Ne mute pas la liste.
function preselectDevis(list) {
  if (!list || !list.length) return null
  const total = (d) => {
    const n = parseFloat(d.total_affiche ?? d.total_ttc)
    return Number.isFinite(n) ? n : 0
  }
  const envoyes = list.filter((d) => d.statut === 'envoye')
  if (envoyes.length) {
    return [...envoyes].sort(
      (a, b) => new Date(b.date_creation ?? 0) - new Date(a.date_creation ?? 0),
    )[0]
  }
  return [...list].sort((a, b) => total(b) - total(a))[0]
}

function fmtMAD(value) {
  const n = parseFloat(value)
  return Number.isFinite(n)
    ? `${Math.round(n).toLocaleString('fr-FR')} MAD` : '—'
}

export default function SigneDialog({ lead, onClose, onConfirmed }) {
  const [loading, setLoading] = useState(true)
  const [devisList, setDevisList] = useState([])
  // Nombre TOTAL de devis du lead (avant filtrage) : distingue « aucun devis »
  // de « aucun devis sélectionnable » (que des refusés/inactifs).
  const [totalDevisCount, setTotalDevisCount] = useState(0)
  const [devisId, setDevisId] = useState('')
  // Choix explicite de l'option par l'utilisateur ('' = pas encore choisi) ;
  // l'option effective est dérivée (choix explicite, sinon celle déjà retenue
  // sur le devis) — pas d'état dérivé synchronisé via un effet.
  const [optionChoice, setOptionChoice] = useState('')
  const [nom, setNom] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Le dialogue est monté à neuf par lead (clé signeLead) → un seul fetch.
  useEffect(() => {
    let alive = true
    ventesApi.getDevis({ lead: lead.id })
      .then((r) => {
        if (!alive) return
        const all = r.data.results ?? r.data
        setTotalDevisCount((all ?? []).length)
        const list = selectableDevis(all)
        setDevisList(list)
        // Présélection du devis le plus pertinent (envoyé récent, sinon total
        // le plus élevé) au lieu du premier renvoyé par l'API.
        const best = preselectDevis(list)
        if (best) setDevisId(String(best.id))
      })
      .catch(() => {
        if (alive) setError('Impossible de charger les devis de ce lead.')
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [lead.id])

  const selected = useMemo(
    () => devisList.find((d) => String(d.id) === String(devisId)) ?? null,
    [devisList, devisId],
  )
  const twoOptions = selected?.nb_options === 2
  const option = optionChoice || selected?.option_acceptee || ''

  const confirm = async () => {
    if (!selected) return
    if (twoOptions && !option) {
      setError("Précisez l'option choisie par le client.")
      return
    }
    // La date d'acceptation se propage en date de signature du chantier : une
    // date dans le futur demande une confirmation explicite avant d'enregistrer.
    const today = new Date().toISOString().slice(0, 10)
    if (date > today
        && !window.confirm('Date d\'acceptation dans le futur — confirmer ?')) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      await ventesApi.accepterDevis(selected.id, { nom, date, option })
      onConfirmed?.()
    } catch (err) {
      setError(err?.response?.data?.detail
        ?? "L'acceptation n'a pas pu être enregistrée — réessayez.")
      setBusy(false)
    }
  }

  const leadNom = `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() || 'ce lead'

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal sd-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Passer en « Signé »</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {loading && (
            <p className="sd-loading"><Spinner /> Chargement des devis…</p>
          )}

          {!loading && devisList.length === 0 && (
            <div className="sd-empty" role="alert">
              {totalDevisCount === 0 ? (
                <>
                  <p className="sd-empty-head">
                    <FileWarning className="size-4 shrink-0" aria-hidden="true" />
                    <strong>{leadNom}</strong> n'a aucun devis.
                  </p>
                  <p>
                    Créez ou sélectionnez d'abord un devis avant de passer ce
                    lead en « Signé ». L'étape ne sera pas modifiée.
                  </p>
                </>
              ) : (
                <>
                  <p className="sd-empty-head">
                    <FileWarning className="size-4 shrink-0" aria-hidden="true" />
                    Tous les devis sont refusés.
                  </p>
                  <p>
                    <strong>{leadNom}</strong> n'a que des devis refusés —
                    créez ou rouvrez un devis avant de passer en « Signé ».
                    L'étape ne sera pas modifiée.
                  </p>
                </>
              )}
            </div>
          )}

          {!loading && devisList.length > 0 && (
            <>
              <p className="sd-intro">
                Quel devis de <strong>{leadNom}</strong> a été accepté ?
              </p>

              <label className="form-label" htmlFor="sd-devis">Devis accepté</label>
              <select
                id="sd-devis"
                className="form-control"
                value={devisId}
                onChange={(e) => setDevisId(e.target.value)}
              >
                {devisList.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.reference} — {STATUT_LABELS[d.statut] ?? d.statut}
                    {' · '}{fmtMAD(d.total_affiche ?? d.total_ttc)}
                  </option>
                ))}
              </select>

              {twoOptions && (
                <div className="sd-options">
                  <span className="form-label">Option choisie par le client</span>
                  {Object.entries(OPTION_LABELS).map(([value, label]) => (
                    <label key={value} className="sd-radio">
                      <input
                        type="radio"
                        name="sd-option"
                        value={value}
                        checked={option === value}
                        onChange={() => setOptionChoice(value)}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              )}

              <label className="form-label" htmlFor="sd-nom">
                Nom de la personne qui accepte (optionnel)
              </label>
              <input
                id="sd-nom"
                className="form-control"
                value={nom}
                onChange={(e) => setNom(e.target.value)}
                placeholder="ex. M. Bennani"
              />

              <label className="form-label" htmlFor="sd-date">Date d'acceptation</label>
              <input
                id="sd-date"
                type="date"
                className="form-control"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </>
          )}

          {error && <p className="form-error" role="alert">{error}</p>}
        </div>

        <div className="modal-footer">
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          {!loading && devisList.length > 0 && (
            <Button
              type="button"
              variant="success"
              onClick={confirm}
              loading={busy}
              disabled={busy || !selected}
            >
              {busy ? 'Enregistrement…' : 'Confirmer l’acceptation'}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
