import { useState } from 'react'
import { Zap, FileText } from 'lucide-react'
import {
  Button, StatusPill,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../ui'
import DocumentStageTrack from '../../../ui/DocumentStageTrack'
import ventesApi from '../../../api/ventesApi'
import installationsApi from '../../../api/installationsApi'
import { formatMAD, formatDate } from '../../../lib/format'
import { errorMessageFrom } from '../../../lib/toast'

// LW21 — Onglet Devis : la chaîne document en cartes (StatusPill statut
// devis — JAMAIS le funnel lead, règle #2) + le CTA « Devis automatique » qui
// dit ce qui manque. LW22 ajoutera la barre d'envoi WhatsApp multi-devis
// FR/Darija (état `wa` porté par le moteur via ContextRail).

const STATUT_DEVIS = {
  brouillon: 'Brouillon', envoye: 'Envoyé', accepte: 'Accepté',
  refuse: 'Refusé', expire: 'Expiré',
}

// Mini-piste DOCUMENT (règle #4) devis→facture→chantier — JAMAIS les stages
// STAGES.py du funnel lead (règle #2). N'est rendue QUE sur une carte devis
// ACCEPTÉE. `Lead.devis[]` (serializers.get_devis) n'expose ni BC ni facture
// liée (contrairement à la requête dédiée de DevisList.jsx) — seul `chantier`
// est disponible : la piste avance donc directement de « Accepté » à
// « Chantier » quand un chantier existe, sans distinguer un état
// intermédiaire « Facturé » (limitation de donnée documentée, pas un choix
// arbitraire — voir le rapport de fin de lane).
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que ChatterTimeline.OUTCOME_LABELS
export const DEVIS_MINI_TRACK = [
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'envoye', label: 'Envoyé' },
  { key: 'accepte', label: 'Accepté' },
  { key: 'facture', label: 'Facturé' },
  { key: 'chantier', label: 'Chantier' },
]

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function devisTrackCurrent(d) {
  return d?.chantier ? 'chantier' : 'accepte'
}

// LW21 — mapping labels backend (apps/crm/devis_auto.py `champs_manquants`,
// texte FR fixe — source unique règle serveur/UI) → id DOM du champ dans
// SectionsPane (sections/SectionEnergie.jsx, ids `lf-*`). Logique pure
// co-localisée, testable sans DOM.
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que ChatterTimeline.OUTCOME_LABELS
export const DEVIS_AUTO_FIELD_IDS = {
  'facture hiver': { field: 'lf-facture-hiver', section: 'energie' },
  'facture été': { field: 'lf-facture-ete', section: 'energie' },
  'consommation mensuelle (kWh)': { field: 'lf-conso-mensuelle', section: 'energie' },
  'pompe (CV)': { field: 'lf-pompe-cv', section: 'pompage' },
  HMT: { field: 'lf-pompe-hmt', section: 'pompage' },
  'débit souhaité': { field: 'lf-pompe-debit', section: 'pompage' },
}

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function missingFieldTarget(label) {
  return DEVIS_AUTO_FIELD_IDS[label] ?? null
}

// Saute au champ manquant dans le centre et le focus ; si la section est
// repliée (le champ n'est alors pas dans le DOM — SectionsPane.jsx est hors
// périmètre de cette lane, aucun canal de dépli-à-distance n'existe encore),
// on retombe sur un scroll jusqu'à l'en-tête de la section (voir le rapport
// de fin de lane : câblage `SectionsPane` documenté, pas implémenté ici).
function jumpToMissingField(label) {
  const target = missingFieldTarget(label)
  if (!target) return
  const el = document.getElementById(target.field)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus()
    return
  }
  document.querySelector(`[data-nav-id="${target.section}"]`)
    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export default function DevisTab({ state, onAction }) {
  const devisList = state.server?.devis ?? []
  const devisAuto = state.server?.devis_auto ?? { pret: false, manquants: [] }

  const [busyAction, setBusyAction] = useState(null) // `f-<id>` | `c-<id>` | null
  const [actionMsg, setActionMsg] = useState(null)

  const genererFacture = (d) => {
    setBusyAction(`f-${d.id}`)
    setActionMsg(null)
    ventesApi.genererFacture(d.id)
      .then((res) => {
        const f = res.data
        setActionMsg(`${f.type_facture_display ?? 'Facture'} ${f.reference} créée.`)
        onAction?.('refresh')
      })
      .catch((err) => setActionMsg(errorMessageFrom(err, 'Génération de facture impossible.')))
      .finally(() => setBusyAction(null))
  }

  const creerChantier = (d) => {
    setBusyAction(`c-${d.id}`)
    setActionMsg(null)
    installationsApi.createFromDevis(d.id)
      .then((res) => {
        setActionMsg(`Chantier ${res.data.reference} prêt.`)
        onAction?.('refresh')
      })
      .catch((err) => setActionMsg(errorMessageFrom(err, 'Création du chantier impossible.')))
      .finally(() => setBusyAction(null))
  }

  return (
    <div className="lw-context-devis">
      {devisAuto.pret ? (
        <div className="lw-context-devis-cta">
          <Button type="button" variant="default" onClick={() => onAction?.('open-devis', 'auto')}>
            <Zap size={14} aria-hidden="true" /> Devis automatique
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="outline" size="sm">
                <FileText size={14} aria-hidden="true" /> Devis modifiable ▾
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', 'remise')}>Remise %…</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', 'onepage')}>Devis 1 page</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', 'premium')}>Devis premium</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction?.('open-devis', 'edit')}>Édition complète…</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ) : (
        <div className="lw-context-devis-missing">
          <p className="gen-hint">Devis automatique — champs manquants :</p>
          <ul className="lw-context-missing-list">
            {(devisAuto.manquants ?? []).map((label) => (
              <li key={label}>
                <button
                  type="button"
                  className="lw-context-missing-link"
                  onClick={() => jumpToMissingField(label)}
                >
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="lw-context-devis-list">
        {devisList.length === 0 ? (
          <p className="gen-hint">Aucun devis pour ce lead.</p>
        ) : (
          devisList.map((d) => (
            <div key={d.id} className="lw-context-devis-card">
              <div className="lw-context-devis-card-head">
                <button
                  type="button"
                  className="lw-context-devis-ref"
                  title="Voir / télécharger le PDF dans la fiche"
                  onClick={() => onAction?.('view-devis', d.id)}
                >
                  {d.reference}
                </button>
                <StatusPill status={d.statut} label={STATUT_DEVIS[d.statut] ?? d.statut} />
              </div>
              <div className="lw-context-devis-card-body">
                <span className="num">{formatMAD(d.total_ttc, { decimals: 0 })}</span>
                <span className="lw-context-devis-date">{formatDate(d.date_creation)}</span>
              </div>
              {d.statut === 'accepte' && (
                <>
                  <DocumentStageTrack
                    className="lw-context-devis-track"
                    stages={DEVIS_MINI_TRACK}
                    current={devisTrackCurrent(d)}
                  />
                  <div className="lw-context-devis-actions">
                    <Button
                      type="button" size="sm" variant="outline"
                      disabled={busyAction === `f-${d.id}`}
                      onClick={() => genererFacture(d)}
                    >
                      {busyAction === `f-${d.id}` ? '…' : '🧾 Générer la facture'}
                    </Button>
                    {d.chantier ? (
                      <span className="gen-hint" title="Chantier déjà créé">🏗 {d.chantier.reference}</span>
                    ) : (
                      <Button
                        type="button" size="sm" variant="outline"
                        disabled={busyAction === `c-${d.id}`}
                        onClick={() => creerChantier(d)}
                      >
                        {busyAction === `c-${d.id}` ? '…' : '🏗 Créer le chantier'}
                      </Button>
                    )}
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>
      {actionMsg && <p className="gen-hint" role="status">{actionMsg}</p>}
    </div>
  )
}
