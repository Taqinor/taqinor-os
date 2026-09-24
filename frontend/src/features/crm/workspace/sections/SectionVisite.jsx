// VISCAD5 (fondateur 15/09/2026) — « la visite technique devient une étape du
// suivi commercial » : cette section montre désormais le VRAI module visites
// (apps/visites, via `crmApi.getLeadVisites`) en contenu PRINCIPAL, avec le
// même bouton « Planifier la visite technique » que le panneau de coaching de
// la cadence (`PlanifierVisiteModal`, partagé — un seul appel serveur). Les
// anciens champs manuels (visite_prevue_le/visite_effectuee/visite_notes)
// restent EN PLACE (toujours fonctionnels) mais visuellement SECONDAIRES ;
// `AppointmentBooker` (RDV général, satellite historique) passe sous une
// disclosure repliée — conservé, jamais supprimé.
import { useCallback, useEffect, useState } from 'react'
import { MapPin } from 'lucide-react'
import {
  FormField, Input, Button, Badge, Spinner,
} from '../../../../ui'
import { formatDate } from '../../../../lib/format'
import { getField } from '../draftCore'
import crmApi from '../../../../api/crmApi'
import PlanifierVisiteModal from '../../relances/PlanifierVisiteModal'
import { STATUT_VISITE_TONE } from '../../relances/visiteGuidance'
import AppointmentBooker from '../../../../pages/crm/leads/AppointmentBooker'

export default function SectionVisite({ state, setField, errors = {}, mode, refData = {} }) {
  const v = (k) => getField(state, k) ?? ''
  const visiteEffectuee = !!getField(state, 'visite_effectuee')
  const { leadId } = refData

  const [visites, setVisites] = useState([])
  // CAD123 — textes du SERVEUR (contrat `lead_visites`) : la règle « la
  // visite se propose après le devis » et son rappel juridique (CAD122),
  // deux chaînes vides dès qu'un devis est parti. On AVERTIT, on ne bloque
  // jamais : le bouton « Planifier » reste actif.
  const [avertissement, setAvertissement] = useState({ texte: '', juridique: '' })
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [planifierOuvert, setPlanifierOuvert] = useState(false)

  const charger = useCallback(() => {
    if (!leadId) return
    setLoading(true)
    setErreur(false)
    // Garde défensive — voir `CadenceFrise.jsx` (même raison) : plusieurs
    // suites de tests existantes mockent `crmApi` sans encore connaître
    // `getLeadVisites` ; un appel direct y lèverait une TypeError synchrone
    // au montage de CETTE section, au lieu du même repli « indisponible »
    // qu'un échec réseau.
    const requete = typeof crmApi.getLeadVisites === 'function'
      ? crmApi.getLeadVisites(leadId)
      : Promise.reject(new Error('getLeadVisites indisponible'))
    requete
      .then((r) => {
        setVisites(r.data?.visites ?? [])
        setAvertissement({
          texte: r.data?.avertissement_sans_devis ?? '',
          juridique: r.data?.rappel_juridique ?? '',
        })
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }, [leadId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage, même patron que VisiteTab.jsx
  useEffect(() => { charger() }, [charger])

  return (
    <>
      {mode === 'edit' && leadId != null && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-medium">Visites techniques</h4>
            <Button type="button" size="sm" onClick={() => setPlanifierOuvert(true)}>
              <MapPin className="size-3.5" /> Planifier la visite technique
            </Button>
          </div>
          {avertissement.texte && (
            <div
              role="note"
              data-testid="visite-sans-devis"
              className="rounded-md border border-warning/40 bg-warning/10 p-2 text-xs"
            >
              <p className="font-medium text-warning">{avertissement.texte}</p>
              {avertissement.juridique && (
                <p className="mt-1 text-muted-foreground">{avertissement.juridique}</p>
              )}
            </div>
          )}
          {loading ? (
            <Spinner className="size-3.5" />
          ) : erreur ? (
            <p className="text-xs text-muted-foreground">Visites indisponibles pour le moment.</p>
          ) : visites.length === 0 ? (
            <p className="text-xs text-muted-foreground">Aucune visite technique planifiée pour ce lead.</p>
          ) : (
            <ul className="flex flex-col gap-1.5" data-testid="section-visite-liste">
              {visites.map((visite) => (
                <li
                  key={visite.id}
                  data-testid="section-visite-row"
                  className="flex flex-wrap items-center gap-1.5 rounded-md border border-border p-2 text-sm"
                >
                  <Badge tone={STATUT_VISITE_TONE[visite.statut] ?? 'neutral'}>
                    {visite.statut_libelle ?? visite.statut}
                  </Badge>
                  {visite.date_prevue && (
                    <span className="text-muted-foreground">Prévue le {formatDate(visite.date_prevue)}</span>
                  )}
                  {visite.commercial_nom && (
                    <span className="text-muted-foreground">· {visite.commercial_nom}</span>
                  )}
                  {visite.retour_disponible && visite.notes && (
                    <span className="w-full text-xs text-muted-foreground">— {visite.notes}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
          <PlanifierVisiteModal
            leadId={leadId}
            open={planifierOuvert}
            onOpenChange={setPlanifierOuvert}
            onPlanifie={charger}
          />
        </div>
      )}
      {/* Champs manuels historiques — conservés fonctionnels (édition
          directe possible, ex. reprise d'une visite tenue hors ERP) mais
          visuellement SECONDAIRES : la liste ci-dessus est désormais la
          source principale. Libellés INCHANGÉS (fieldLabels.js les référence
          par leur texte exact — les garder identiques évite toute
          divergence avec le message d'erreur qui les nomme). */}
      <p className="mt-3 text-xs font-medium text-muted-foreground">Champs manuels (repli)</p>
      <div className="form-row">
        <FormField label="Visite prévue le" htmlFor="lf-visite-prevue" error={errors.visite_prevue_le}>
          <Input
            id="lf-visite-prevue" type="date" invalid={!!errors.visite_prevue_le}
            value={v('visite_prevue_le')} onChange={(e) => setField('visite_prevue_le', e.target.value)}
          />
        </FormField>
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input
              type="checkbox" checked={visiteEffectuee}
              onChange={(e) => setField('visite_effectuee', e.target.checked)}
            />
            <span>Visite effectuée</span>
          </label>
        </div>
        <div className="form-group fg-grow">
          <FormField label="Notes de visite" htmlFor="lf-visite-notes" error={errors.visite_notes}>
            <Input
              id="lf-visite-notes" invalid={!!errors.visite_notes}
              value={v('visite_notes')} onChange={(e) => setField('visite_notes', e.target.value)}
            />
          </FormField>
        </div>
      </div>
      {/* QJ20 — RDV général (satellite historique, conservé fonctionnel) :
          replié par défaut, la visite TECHNIQUE se planifie désormais
          ci-dessus via le vrai module visites. */}
      {mode === 'edit' && leadId != null && (
        <details className="mt-3 rounded-lg border border-border">
          <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium">
            Autre rendez-vous (RDV général)
          </summary>
          <div className="border-t border-border p-3">
            <AppointmentBooker leadId={leadId} />
          </div>
        </details>
      )}
    </>
  )
}
