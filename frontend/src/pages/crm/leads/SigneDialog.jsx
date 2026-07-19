// Dialogue « Signé » (A2) — quand un lead est déplacé dans l'étape Signé
// (glisser-déposer kanban ou édition en place de l'étape), on demande QUEL
// devis du lead a été accepté et QUELLE option (Sans batterie / Avec batterie).
// Confirmer marque ce devis « accepté » (réutilise A1 : POST .../accepter/) ;
// l'acceptation fait avancer le lead en Signé côté serveur. Si le lead n'a
// aucun devis, on l'explique et on NE déplace PAS l'étape — jamais de devis
// inventé, jamais de passage en Signé sans devis (règles #2/#4 : l'étape du
// funnel et le statut du document restent deux couches séparées).
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Eye, FileWarning } from 'lucide-react'
import ventesApi from '../../../api/ventesApi'
import { proposalParams, pdfBlob } from '../../../features/ventes/previewPdf'
import { Button, Spinner } from '../../../ui'
// VX182 — le shell fait-main de SigneDialog est passé à ResponsiveDialog.
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
// VX155 — la carte de victoire (enrichit le Done= de VX40) remplace le
// toast plat + celebrateDealSigned() appelés directement d'ici ; le burst
// CSS-only reste posé, mais DEPUIS <DealSignedCelebration> lui-même.
import DealSignedCelebration from '../../../ui/DealSignedCelebration'
import { formatMAD } from '../../../lib/format'

// Rendu PDF.js (canvas) chargé à la demande — même composant inblocable que le
// panneau devis de la fiche lead. Réutilisé tel quel, jamais dupliqué.
const PdfCanvas = lazy(() => import('../../../features/ventes/PdfCanvas'))

const OPTION_LABELS = {
  sans_batterie: 'Sans batterie',
  avec_batterie: 'Avec batterie',
}

// Une désignation de ligne désigne-t-elle une batterie ? (même mot-clé que le
// moteur PDF / solar.js — accents neutralisés.)
const isBatteryLine = (d) =>
  (d || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
    .includes('batterie')

// TTC d'une ligne : qté × P.U. HT × (1 − remise ligne) × (1 + TVA), au taux de
// la ligne s'il est défini, sinon le taux du devis.
function ligneTtc(l, devisTva) {
  const qte = parseFloat(l.quantite) || 0
  const pu = parseFloat(l.prix_unitaire) || 0
  const rem = parseFloat(l.remise) || 0
  const tva = (l.taux_tva != null && l.taux_tva !== '')
    ? (parseFloat(l.taux_tva) || 0)
    : (parseFloat(devisTva) || 0)
  return qte * pu * (1 - rem / 100) * (1 + tva / 100)
}

// Détail par option d'un devis à deux options : kWc estimé (panneaux × 0,71) et
// total TTC de chacune (remise globale appliquée). « Sans batterie » = lignes
// hors batterie, « Avec batterie » = toutes les lignes. Indicatif, calculé à
// l'écran pour aider le choix — le PDF reste la source canonique.
function optionsDetail(devis) {
  const lignes = devis?.lignes ?? []
  if (!lignes.length) return null
  const tva = devis?.taux_tva
  const remGlobale = parseFloat(devis?.remise_globale) || 0
  const factor = 1 - remGlobale / 100
  const ttcAvec = lignes.reduce((s, l) => s + ligneTtc(l, tva), 0) * factor
  const ttcSans = lignes
    .filter((l) => !isBatteryLine(l.designation))
    .reduce((s, l) => s + ligneTtc(l, tva), 0) * factor
  const nbPanneaux = lignes
    .filter((l) => (l.designation || '').toLowerCase().includes('panneau'))
    .reduce((s, l) => s + (parseFloat(l.quantite) || 0), 0)
  const kwc = nbPanneaux > 0 ? Math.round(nbPanneaux * 0.71 * 100) / 100 : null
  return {
    sans_batterie: { ttc: ttcSans, kwc },
    avec_batterie: { ttc: ttcAvec, kwc },
  }
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
  return formatMAD(value, { decimals: 0 })
}

// LW5 — date du jour civil en LOCAL, jamais en UTC : `toISOString()` restitue
// toujours la date UTC, qui décale d'un jour du côté du fuseau local dès que
// l'heure système passe minuit dans l'un des deux référentiels sans avoir
// encore passé minuit dans l'autre (à UTC+1 — Maroc — c'est le cas entre
// 00h00 et 01h00 locales). Utilisée à la fois pour le défaut du champ date
// (L121) et pour la comparaison « date future » (confirm ci-dessous) : les
// deux doivent parler le même référentiel que le sélecteur de date natif,
// lui-même toujours local. `now` est injectable pour les tests (horloge
// mockée), jamais autrement appelé qu'avec l'horloge réelle en production.
function todayLocalStr(now = new Date()) {
  return now.toLocaleDateString('fr-CA') // « AAAA-MM-JJ », comme <input type="date">
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
  const [date, setDate] = useState(() => todayLocalStr())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Aperçu PDF inline du devis sélectionné (PDF.js canvas, comme le panneau
  // devis). previewId = devis dont on a demandé l'aperçu ; previewBlob = octets.
  const [previewId, setPreviewId] = useState(null)
  const [previewBlob, setPreviewBlob] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState(null)
  // VX155 — carte de victoire affichée après acceptation (null = pas encore
  // signé) ; { reference, montantTtc, kwc } réels, jamais un chiffre inventé.
  const [celebration, setCelebration] = useState(null)

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

  // Changer de devis ferme un aperçu devenu obsolète (il portait sur l'ancien).
  const onDevisChange = (id) => {
    setDevisId(id)
    setPreviewId(null)
    setPreviewBlob(null)
    setPreviewError(null)
  }
  const twoOptions = selected?.nb_options === 2
  const option = optionChoice || selected?.option_acceptee || ''
  // Détail par option (kWc / total TTC) — calculé pour TOUT devis sélectionné
  // (pas seulement à 2 options) : la carte de victoire (VX155) en a besoin
  // même pour un devis à une seule option.
  const detailAll = useMemo(() => optionsDetail(selected), [selected])
  // Rendu du choix d'option — seulement utile quand 2 options.
  const optDetail = twoOptions ? detailAll : null

  // Aperçu inline : récupère le PDF /proposal (chemin canonique) en blob, puis
  // le dessine sur canvas. Toggle : recliquer ferme l'aperçu.
  const togglePreview = async (devis) => {
    if (previewId === devis.id) {
      setPreviewId(null); setPreviewBlob(null); setPreviewError(null)
      return
    }
    setPreviewId(devis.id)
    setPreviewBlob(null)
    setPreviewError(null)
    setPreviewLoading(true)
    try {
      const res = await ventesApi.getProposalPdf(
        devis.id, proposalParams('full', false))
      setPreviewBlob(pdfBlob(res.data))
    } catch {
      setPreviewError('Aperçu indisponible — réessayez ou ouvrez le devis.')
    } finally {
      setPreviewLoading(false)
    }
  }

  const confirm = async () => {
    if (!selected) return
    if (twoOptions && !option) {
      setError("Précisez l'option choisie par le client.")
      return
    }
    // La date d'acceptation se propage en date de signature du chantier : une
    // date dans le futur demande une confirmation explicite avant d'enregistrer.
    const today = todayLocalStr()
    if (date > today
        && !window.confirm('Date d\'acceptation dans le futur — confirmer ?')) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      await ventesApi.accepterDevis(selected.id, { nom, date, option })
      // VX40/VX155 — le SEUL moment célébré de toute l'app : devis envoyé→
      // accepté (rare, lié au revenu). La carte de victoire (montant + kWc
      // réels, CO₂ dérivé) remplace le toast plat ; onConfirmed() n'est
      // appelé qu'à la fermeture de la carte (voir le rendu ci-dessous).
      const chosenKey = twoOptions ? option : 'avec_batterie'
      const chosenDetail = detailAll?.[chosenKey]
      const montantTtc = chosenDetail?.ttc
        ?? (parseFloat(selected.total_affiche ?? selected.total_ttc) || 0)
      setCelebration({
        reference: selected.reference,
        montantTtc,
        kwc: chosenDetail?.kwc ?? null,
      })
    } catch (err) {
      setError(err?.response?.data?.detail
        ?? "L'acceptation n'a pas pu être enregistrée — réessayez.")
      setBusy(false)
    }
  }

  const leadNom = `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() || 'ce lead'

  // VX155 — après acceptation, la carte de victoire remplace le dialogue ;
  // onConfirmed() (qui ferme SigneDialog côté appelant) n'est appelé qu'à la
  // fermeture de la carte — jamais avant que le vendeur l'ait vue.
  if (celebration) {
    return (
      <DealSignedCelebration
        open
        reference={celebration.reference}
        montantTtc={celebration.montantTtc}
        kwc={celebration.kwc}
        onClose={() => { setCelebration(null); onConfirmed?.() }}
      />
    )
  }

  return (
    // VX182 — shell fait-main remplacé par ResponsiveDialog (Escape + focus-
    // trap + bottom-sheet mobile) ; `sd-modal` conservée pour le sélecteur CSS
    // scopé `.sd-modal .form-label` ; en-tête/pied inchangés.
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sd-modal sm:max-w-lg" showClose={false}>
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
              <div className="flex flex-wrap items-center gap-2">
                <select
                  id="sd-devis"
                  className="form-control min-w-0 flex-1"
                  value={devisId}
                  onChange={(e) => onDevisChange(e.target.value)}
                  autoFocus
                >
                  {devisList.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.reference} — {STATUT_LABELS[d.statut] ?? d.statut}
                      {' · '}{fmtMAD(d.total_affiche ?? d.total_ttc)}
                    </option>
                  ))}
                </select>
                {selected && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => togglePreview(selected)}
                  >
                    <Eye /> {previewId === selected.id ? "Masquer l'aperçu" : 'Aperçu'}
                  </Button>
                )}
              </div>

              {/* Aperçu PDF inline du devis sélectionné — lecture sans quitter
                  le dialogue, pour choisir le bon devis sans deviner. */}
              {selected && previewId === selected.id && (
                <div className="mt-2 max-h-[55vh] overflow-y-auto rounded-lg border border-border bg-muted/30 p-2">
                  {previewLoading && (
                    <p className="sd-loading"><Spinner /> Rendu de l'aperçu…</p>
                  )}
                  {previewError && (
                    <p className="form-error" role="alert">{previewError}</p>
                  )}
                  {previewBlob && !previewError && (
                    <Suspense fallback={<p className="sd-loading"><Spinner /> Rendu de l'aperçu…</p>}>
                      <PdfCanvas
                        blob={previewBlob}
                        onError={() => setPreviewError(
                          'Aperçu indisponible — réessayez ou ouvrez le devis.')}
                      />
                    </Suspense>
                  )}
                </div>
              )}

              {twoOptions && (
                <div className="sd-options">
                  <span className="form-label">Option choisie par le client</span>
                  {Object.entries(OPTION_LABELS).map(([value, label]) => {
                    const det = optDetail?.[value]
                    return (
                      <label key={value} className="sd-radio">
                        <input
                          type="radio"
                          name="sd-option"
                          value={value}
                          checked={option === value}
                          onChange={() => setOptionChoice(value)}
                        />
                        <span>{label}</span>
                        {det && (
                          <span className="ml-auto text-sm font-medium tabular-nums text-muted-foreground">
                            {det.kwc != null ? `≈ ${det.kwc} kWc · ` : ''}
                            {fmtMAD(det.ttc)}
                          </span>
                        )}
                      </label>
                    )
                  })}
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
    </ResponsiveDialog>
  )
}
