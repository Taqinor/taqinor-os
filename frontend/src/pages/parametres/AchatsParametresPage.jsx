import { useEffect } from 'react'
import useFormulaireReglages from './useFormulaireReglages'
import { Link } from 'react-router-dom'
import { CalendarCheck2, ShieldCheck } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { Button, Card, CardContent, Input, Label, Switch } from '../../ui'
import { toast } from '../../ui/confirm'
import ReglesApprobationAchatSection from './ReglesApprobationAchatSection'
import { frErrDetail as frErr } from '../../lib/frErr'
import { PageChargement, PageReglages, FormulaireReglages } from './EtatsSection'

/* ============================================================================
   WIR26 — Paramètres → Achats (`stock.AchatsParametres`, singleton par
   société, `AchatsParametres.for_company`). Jusqu'ici sans écran : la RAS-TVA
   (XPUR2, LF 2024) était inactivable sans accès direct à la base, et les
   tolérances du rapprochement 3 voies (XPUR10) tout autant. Le blocage
   paiement sur conformité expirée (XPUR1) est exposé sur le même objet.
   Toute la logique serveur (retenue RAS-TVA au paiement, gate conformité,
   exceptions 3-voies) existe déjà et est testée — cet écran ne fait que
   piloter les interrupteurs.
   ========================================================================== */

const emptyForm = {
  bloquer_paiement_conformite_expiree: false,
  ras_tva_actif: false,
  tolerance_prix_pct: '0',
  tolerance_prix_absolu_mad: '0',
  tolerance_quantite_pct: '0',
  // Procure-to-Pay (NTP2P4 / NTP2P7 / NTP2P37) — tous OFF par défaut :
  // comportement historique strictement inchangé tant qu'ils ne sont pas
  // activés par la société.
  budget_departement_actif: false,
  onboarding_fournisseur_obligatoire: false,
  sod_stricte: false,
  // NTP2P31 — notification immédiate du valideur direction (NTP2P45) sur
  // une note de frais escaladée (NTP2P11). N'affecte jamais le calcul
  // d'escalade lui-même.
  plafond_notes_frais_actif: false,
}

export default function AchatsParametresPage() {
  const {
    id, setId, form, setForm, loading, setLoading, saving, setSaving, setField,
  } = useFormulaireReglages(emptyForm)

  useEffect(() => {
    let active = true
    stockApi.getAchatsParametres()
      .then((r) => {
        if (!active) return
        const data = r.data ?? {}
        setId(data.id ?? null)
        setForm({
          bloquer_paiement_conformite_expiree: !!data.bloquer_paiement_conformite_expiree,
          ras_tva_actif: !!data.ras_tva_actif,
          tolerance_prix_pct: data.tolerance_prix_pct ?? '0',
          tolerance_prix_absolu_mad: data.tolerance_prix_absolu_mad ?? '0',
          tolerance_quantite_pct: data.tolerance_quantite_pct ?? '0',
          budget_departement_actif: !!data.budget_departement_actif,
          onboarding_fournisseur_obligatoire: !!data.onboarding_fournisseur_obligatoire,
          sod_stricte: !!data.sod_stricte,
          plafond_notes_frais_actif: !!data.plafond_notes_frais_actif,
        })
      })
      .catch(() => toast.error('Chargement des paramètres achats impossible.'))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement au montage seulement (setters du hook stables)
  }, [])

  const submit = (e) => {
    e.preventDefault()
    if (!id) return
    setSaving(true)
    stockApi.updateAchatsParametres(id, form)
      .then((r) => {
        const data = r.data ?? {}
        setForm((f) => ({
          ...f,
          ...data,
          tolerance_prix_pct: data.tolerance_prix_pct ?? f.tolerance_prix_pct,
          tolerance_prix_absolu_mad: data.tolerance_prix_absolu_mad ?? f.tolerance_prix_absolu_mad,
          tolerance_quantite_pct: data.tolerance_quantite_pct ?? f.tolerance_quantite_pct,
        }))
        toast.success('Paramètres achats enregistrés.')
      })
      .catch((err) => toast.error(frErr(err, "L'enregistrement a échoué.")))
      .finally(() => setSaving(false))
  }

  if (loading) return <PageChargement />

  return (
    <PageReglages titre="Achats"
      sousTitre={
        <>
          Réglages achats/fournisseurs de la société — conformité, RAS-TVA et
          tolérances de rapprochement.
        </>
      }
      actions={(
        <>
        {/* NTP2P30 — wizard de clôture de fin de mois (agrégateur lecture
            seule : factures en exception, demandes anciennes, documents
            expirés). */}
        <Button asChild variant="outline">
          <Link to="/parametres/achats/cloture">
            <CalendarCheck2 /> Clôture de fin de mois
          </Link>
        </Button>
        </>
      )}>

      <FormulaireReglages onSubmit={submit} saving={saving} disabled={!id}>
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" />
              Conformité fournisseur (XPUR1)
            </h2>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="ap-bloquer-conformite"
                aria-label="Bloquer le paiement si conformité expirée"
                checked={form.bloquer_paiement_conformite_expiree}
                onCheckedChange={(v) => setField('bloquer_paiement_conformite_expiree', v)}
              />
              Bloquer le paiement si un document de conformité obligatoire est
              manquant ou expiré
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" />
              Procure-to-Pay
            </h2>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="ap-budget-departement"
                aria-label="Activer le contrôle budgétaire par département"
                checked={form.budget_departement_actif}
                onCheckedChange={(v) => setField('budget_departement_actif', v)}
              />
              Refuser une demande d&apos;achat qui dépasse le budget restant du
              département (NTP2P4)
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="ap-onboarding-obligatoire"
                aria-label="Exiger un dossier d’onboarding fournisseur validé"
                checked={form.onboarding_fournisseur_obligatoire}
                onCheckedChange={(v) => setField('onboarding_fournisseur_obligatoire', v)}
              />
              Exiger un dossier d&apos;onboarding VALIDÉ avant tout bon de
              commande fournisseur (NTP2P7)
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="ap-sod-stricte"
                aria-label="Activer la séparation des tâches stricte"
                checked={form.sod_stricte}
                onCheckedChange={(v) => setField('sod_stricte', v)}
              />
              Séparation des tâches : interdire au créateur d&apos;approuver sa
              propre demande ou note de frais escaladée (NTP2P37)
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="ap-plafond-notes-frais-actif"
                aria-label="Notifier immédiatement la direction sur une note de frais escaladée"
                checked={form.plafond_notes_frais_actif}
                onCheckedChange={(v) => setField('plafond_notes_frais_actif', v)}
              />
              Notifier immédiatement le valideur direction quand une note de
              frais dépasse le seuil d&apos;escalade (NTP2P11/NTP2P45)
            </label>
            <p className="text-xs text-muted-foreground">
              Les quatre sont désactivés par défaut : tant qu&apos;ils le sont,
              le cycle achats reste exactement celui d&apos;avant.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">RAS-TVA (LF 2024 — XPUR2)</h2>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <Switch
                id="ap-ras-tva-actif"
                aria-label="Activer la RAS-TVA"
                checked={form.ras_tva_actif}
                onCheckedChange={(v) => setField('ras_tva_actif', v)}
              />
              Calculer et retenir la RAS-TVA à chaque paiement fournisseur
            </label>
            <p className="text-xs text-muted-foreground">
              Désactivé par défaut (comportement historique — paiement
              intégral, aucune retenue).
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="text-sm font-semibold">
              Tolérances du rapprochement 3 voies (XPUR10)
            </h2>
            <p className="text-xs text-muted-foreground">
              0 = comportement historique (aucune tolérance, tout écart passe
              la facture en exception).
            </p>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <Label htmlFor="ap-tol-prix-pct">Écart de prix toléré (%)</Label>
                <Input id="ap-tol-prix-pct" type="number" step="any" noValidate
                       value={form.tolerance_prix_pct}
                       onChange={(e) => setField('tolerance_prix_pct', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="ap-tol-prix-abs">Écart de prix toléré (MAD)</Label>
                <Input id="ap-tol-prix-abs" type="number" step="any" noValidate
                       value={form.tolerance_prix_absolu_mad}
                       onChange={(e) => setField('tolerance_prix_absolu_mad', e.target.value)} />
              </div>
              <div>
                <Label htmlFor="ap-tol-qte-pct">Écart de quantité toléré (%)</Label>
                <Input id="ap-tol-qte-pct" type="number" step="any" noValidate
                       value={form.tolerance_quantite_pct}
                       onChange={(e) => setField('tolerance_quantite_pct', e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>

      </FormulaireReglages>

      {/* NTP2P32 — CRUD des règles d'approbation d'achat (seuil/chantier/nb
          approbateurs), écran autonome (ses propres appels API, jamais
          rattaché au formulaire AchatsParametres ci-dessus). */}
      <ReglesApprobationAchatSection />
    </PageReglages>
  )
}
