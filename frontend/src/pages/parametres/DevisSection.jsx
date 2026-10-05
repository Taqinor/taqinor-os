// Onglet « Devis & Factures » de la page Paramètres (échéancier, validité,
// pompage, numérotation, commission, TVA/Taxes). Restylé sur le système de
// design (@/ui) ; champs, libellés et comportement identiques.
import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import {
  Button, Card, CardContent, Input, Label, Switch,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  toast,
} from '../../ui'
import ventesApi from '../../api/ventesApi'
import { SectionTitle, Field } from './peComponents'
import {
  MODE_LABELS, DOC_TYPES, REGLAGES_POMPAGE, REPERES_ENERGIE, joursDepuisReleve,
} from './peConstants'

/* WIR225/QG9 — Le « % de variation par défaut » des variantes de devis vivait
   sur `CompanyProfile.variante_pct` et n'était réglable NULLE PART : le seul
   moyen de le changer était l'override ponctuel de la modale « Créer des
   variantes », qui repart de la valeur société à chaque ouverture. Il se règle
   ici, via `get/setVarianteConfig` — un endpoint DISTINCT du profil société,
   d'où son état local et son bouton d'enregistrement propres.

   Le serveur réserve l'ÉCRITURE au Directeur et au Commercial responsable
   (403 sinon) ; l'écran reflète la MÊME règle plutôt que de laisser partir une
   requête vouée au refus. La LECTURE reste ouverte à tous. */
const ROLES_VARIANTE_PCT = ['Directeur', 'Commercial responsable']

/* CIQ106 — prestations C&I réglables (CIQ105, `CompanyProfile.forfaits_ci`).
   Chaque ligne : fixe HT, par kWc HT, par panneau HT, source (obligatoire dès
   qu'un montant est saisi), date. Vide = « prix à renseigner » : AUCUNE valeur
   suggérée ni pré-remplie, jamais le barème résidentiel. */
// source-choix: parametres.serializers_company.FORFAITS_CI_PRESTATIONS
const PRESTATIONS_CI = [
  ['etudes_ingenierie', 'Études et ingénierie'],
  ['pose_structure', 'Pose de la structure'],
  ['pose_modules', 'Pose des modules'],
  ['raccordement_ac', 'Raccordement AC'],
  ['mise_en_service', 'Mise en service'],
  ['dossier_raccordement', 'Dossier de raccordement'],
  ['levage_acces', 'Levage et accès'],
  ['transport_ci', 'Transport C&I'],
]
const MONTANTS_FORFAIT_CI = [
  ['fixe_ht', 'Fixe HT'],
  ['par_kwc_ht', 'Par kWc HT'],
  ['par_panneau_ht', 'Par panneau HT'],
]
const MONTANTS_BANDE_CI = [['min_ht', 'Minimum HT / kWc'], ['max_ht', 'Maximum HT / kWc']]

const _rempli = (v) => v !== null && v !== undefined && String(v).trim() !== ''
/** Un montant saisi sans source : l'erreur s'affiche sous le champ Source. */
const sourceManquante = (entree, montants) => !!entree
  && montants.some(([k]) => _rempli(entree[k])) && !_rempli(entree.source)
const MSG_SOURCE = 'Source obligatoire (devis fournisseur, offre écrite…) : jamais un montant sans source.'

export default function DevisSection({
  form, set, setForm, setPT, setPrefix, setNumbering, numberingPreview,
  canManageSensitive = false,
}) {
  const roleNom = useSelector(s => s.auth?.role_nom) || ''
  const peutReglerVariante = canManageSensitive
    || ROLES_VARIANTE_PCT.includes(roleNom)

  // AGR209 — repères énergie {cle: {valeur, source, releve_le}} (vide = '').
  const reperes = form.reperes_energie_agricole || {}
  const setRepere = (cle, cleChamp, valeur) => setForm(p => ({
    ...p,
    reperes_energie_agricole: {
      ...(p.reperes_energie_agricole || {}),
      [cle]: { ...((p.reperes_energie_agricole || {})[cle] || {}), [cleChamp]: valeur },
    },
  }))

  // CIQ106 — forfaits C&I et bande interne prix/kWc (CIQ105). Seul un champ
  // TOUCHÉ modifie le formulaire : enregistrer sans toucher n'envoie rien de neuf.
  const forfaitsCi = form.forfaits_ci || {}
  const bandeCi = form.bande_prix_kwc_ci || {}
  const setForfaitCi = (cle, champ, valeur) => setForm(p => ({
    ...p,
    forfaits_ci: {
      ...(p.forfaits_ci || {}),
      [cle]: { ...((p.forfaits_ci || {})[cle] || {}), [champ]: valeur },
    },
  }))
  const setBandeCi = (champ, valeur) => setForm(p => ({
    ...p,
    bande_prix_kwc_ci: { ...(p.bande_prix_kwc_ci || {}), [champ]: valeur },
  }))

  const [variantePct, setVariantePct] = useState('')
  const [variantePctSaving, setVariantePctSaving] = useState(false)

  useEffect(() => {
    let vivant = true
    ventesApi.getVarianteConfig()
      .then((r) => {
        if (!vivant) return
        const pct = r?.data?.variante_pct
        if (pct == null) return
        // Le serveur renvoie une chaîne décimale (« 20.00 ») — on l'arrondit,
        // comme la modale de création.
        const n = Math.round(parseFloat(pct))
        if (Number.isFinite(n)) setVariantePct(String(n))
      })
      .catch(() => { /* silencieux : le champ reste vide, rien n'est cassé */ })
    return () => { vivant = false }
  }, [])

  const enregistrerVariantePct = async () => {
    setVariantePctSaving(true)
    try {
      await ventesApi.setVarianteConfig(variantePct)
      toast.success('Pourcentage de variation enregistré.')
    } catch (err) {
      // Le serveur nomme la cause (403 de rôle, bornes 0–100) : on l'affiche
      // tel quel plutôt qu'un message maison qui la masquerait.
      toast.error(err?.response?.data?.detail
        ?? 'Enregistrement du pourcentage impossible.')
    } finally {
      setVariantePctSaving(false)
    }
  }

  return (
    <>
      {/* Devis — échéancier, validité, pompage, numérotation */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Devis" icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Conditions de paiement par marché (acompte / matériel / solde, en %).
            Les factures d'acompte suivent ces valeurs.
          </p>
          {Object.keys(MODE_LABELS).map(mode => (
            <div key={mode} className="mb-2.5">
              <div className="mb-1 text-xs font-semibold text-foreground">{MODE_LABELS[mode]}</div>
              <div className="pe-grid-3">
                {['acompte', 'materiel', 'solde'].map(k => (
                  <div key={k} className="flex flex-col gap-1">
                    <Label className="text-[10.5px] font-normal capitalize text-muted-foreground">{k} %</Label>
                    <Input type="number" step="any"
                           value={form.payment_terms?.[mode]?.[k] ?? ''}
                           onChange={e => setPT(mode, k, e.target.value)} />
                  </div>
                ))}
              </div>
            </div>
          ))}
          {/* WIR225/QG9 — % de variation par défaut des variantes de devis. */}
          <div className="pe-grid-2 mt-2.5">
            <Field label="% de variation par défaut des variantes"
                   htmlFor="pe-variante-pct">
              <div className="flex items-center gap-2">
                <Input id="pe-variante-pct" type="number" step="any" min="0" max="100"
                       value={variantePct}
                       readOnly={!peutReglerVariante}
                       aria-readonly={!peutReglerVariante}
                       onChange={e => setVariantePct(e.target.value)} />
                {peutReglerVariante && (
                  <Button type="button" size="sm" variant="outline"
                          loading={variantePctSaving}
                          onClick={enregistrerVariantePct}>
                    Enregistrer
                  </Button>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground">
                Les trois variantes générées sont réduite (−p %), standard et
                augmentée (+p %). La modale de création part de cette valeur.
                {!peutReglerVariante
                  && ' Réservé au Directeur et au Commercial responsable.'}
              </p>
            </Field>
          </div>
          <div className="pe-grid-2 mt-2.5">
            <Field label="Validité du devis (jours)" htmlFor="pe-validity">
              <Input id="pe-validity" type="number" step="any" name="quote_validity_days"
                     value={form.quote_validity_days} onChange={set} />
            </Field>
            <Field label="Heures de repli / jour si l'irradiation du site est indisponible (agricole)"
                   htmlFor="pe-pump-hours">
              <Input id="pe-pump-hours" type="number" step="any" name="agricole_pump_hours"
                     value={form.agricole_pump_hours} onChange={set} />
            </Field>
          </div>
          {/* AGR108 — réglages pompage société SANS défaut (AGR107) : un
              champ vide reste vide et part `null` ; l'indication sourcée est
              affichée À CÔTÉ, jamais pré-remplie. */}
          <div className="pe-grid-2 mt-2.5" data-testid="reglages-pompage">
            {REGLAGES_POMPAGE.map(({ champ, libelle, indication }) => (
              <Field key={champ} label={libelle} htmlFor={`pe-${champ}`}>
                <Input id={`pe-${champ}`} type="number" step="any" name={champ}
                       value={form[champ] ?? ''} onChange={set} />
                <p className="text-[11px] text-muted-foreground">{indication}</p>
              </Field>
            ))}
          </div>
          {/* AGR209 — REPÈRES énergie agricole datés et sourcés (ex-réglages
              « bonbonne » Q4). Une indication montrée À CÔTÉ du champ du
              générateur, seulement si elle a une source ; aucun moteur ne la
              lit comme prix : le prix retenu est celui DÉCLARÉ par le client.
              Aucun défaut, aucun repli numérique ; « relevé il y a N jours »
              sans seuil. */}
          <div className="mt-2.5 flex flex-col gap-2" data-testid="reperes-energie">
            <p className="text-[11px] text-muted-foreground">
              Indication datée montrée à côté du champ du générateur ; le prix
              retenu est celui DÉCLARÉ par le client. Un repère sans source
              n&apos;est pas affiché au générateur.
            </p>
            {REPERES_ENERGIE.map(({ cle, libelle, interne }) => {
              const r = reperes[cle] || {}
              const jours = joursDepuisReleve(r.releve_le)
              return (
                <div key={cle} className="pe-grid-2" data-testid={`repere-${cle}`}>
                  <Field label={libelle} htmlFor={`pe-repere-${cle}-valeur`}>
                    <Input id={`pe-repere-${cle}-valeur`} type="number" step="any"
                           value={r.valeur ?? ''}
                           onChange={e => setRepere(cle, 'valeur', e.target.value)} />
                    {interne && (
                      <p className="text-[11px] text-muted-foreground">
                        Interne, jamais sur un devis.
                      </p>
                    )}
                  </Field>
                  <div className="pe-grid-2">
                    <Field label="Source" htmlFor={`pe-repere-${cle}-source`}>
                      <Input id={`pe-repere-${cle}-source`}
                             value={r.source ?? ''}
                             onChange={e => setRepere(cle, 'source', e.target.value)} />
                    </Field>
                    <Field label="Relevé le" htmlFor={`pe-repere-${cle}-date`}>
                      <Input id={`pe-repere-${cle}-date`} type="date"
                             value={r.releve_le ?? ''}
                             onChange={e => setRepere(cle, 'releve_le', e.target.value)} />
                      {jours !== null && (
                        <p className="text-[11px] text-muted-foreground">
                          relevé il y a {jours} jour{jours > 1 ? 's' : ''}
                        </p>
                      )}
                    </Field>
                  </div>
                </div>
              )
            })}
          </div>
          {/* CIQ106 — « Prestations C&I » : une ligne par prestation (fixe,
              par kWc, par panneau, source, date). Champ vide = « prix à
              renseigner », aucune valeur suggérée ; saisie libre step="any". */}
          <div className="mb-1 mt-4 text-xs font-semibold text-foreground">
            Prestations C&amp;I
          </div>
          <p className="mb-2 text-[11px] text-muted-foreground">
            Forfaits HT des prestations commerciales et industrielles. Une
            prestation sans montant reste « prix à renseigner » sur le devis C&amp;I
            (jamais le barème résidentiel) ; tout montant exige sa source.
          </p>
          <div className="flex flex-col gap-2" data-testid="prestations-ci">
            {PRESTATIONS_CI.map(([cle, libelle]) => {
              const f = forfaitsCi[cle] || {}
              const sansSource = sourceManquante(f, MONTANTS_FORFAIT_CI)
              const vide = !MONTANTS_FORFAIT_CI.some(([k]) => _rempli(f[k]))
              return (
                <div key={cle} data-testid={`prestation-ci-${cle}`}>
                  <div className="mb-1 text-[11px] font-semibold text-muted-foreground">
                    {libelle}
                    {vide && <span className="ml-2 font-normal italic">prix à renseigner</span>}
                  </div>
                  <div className="pe-grid-3">
                    {MONTANTS_FORFAIT_CI.map(([k, lbl]) => (
                      <Field key={k} label={`${libelle} — ${lbl}`} htmlFor={`pe-ci-${cle}-${k}`}>
                        <Input id={`pe-ci-${cle}-${k}`} type="number" step="any"
                               value={f[k] ?? ''}
                               onChange={e => setForfaitCi(cle, k, e.target.value)} />
                      </Field>
                    ))}
                  </div>
                  <div className="pe-grid-2">
                    <Field label={`${libelle} — source`} htmlFor={`pe-ci-${cle}-source`}>
                      <Input id={`pe-ci-${cle}-source`}
                             value={f.source ?? ''}
                             aria-invalid={sansSource}
                             onChange={e => setForfaitCi(cle, 'source', e.target.value)} />
                      {sansSource && (
                        <p role="alert" className="text-[11px] text-destructive">{MSG_SOURCE}</p>
                      )}
                    </Field>
                    <Field label={`${libelle} — date`} htmlFor={`pe-ci-${cle}-date`}>
                      <Input id={`pe-ci-${cle}-date`} type="date"
                             value={f.date ?? ''}
                             onChange={e => setForfaitCi(cle, 'date', e.target.value)} />
                    </Field>
                  </div>
                </div>
              )
            })}
          </div>
          {/* CIQ106 — contrôle INTERNE du prix au kWc (QXG6(b)) : jamais
              imprimé au client, servi au vendeur seulement. */}
          <div className="mb-1 mt-4 text-xs font-semibold text-foreground">
            Contrôle interne du prix au kWc (C&amp;I)
          </div>
          <p className="mb-2 text-[11px] text-muted-foreground">
            Jamais imprimé au client. Bande issue de trois offres réelles ;
            vide = aucun contrôle.
          </p>
          <div className="pe-grid-2" data-testid="bande-prix-kwc-ci">
            {MONTANTS_BANDE_CI.map(([k, lbl]) => (
              <Field key={k} label={lbl} htmlFor={`pe-bande-ci-${k}`}>
                <Input id={`pe-bande-ci-${k}`} type="number" step="any"
                       value={bandeCi[k] ?? ''}
                       onChange={e => setBandeCi(k, e.target.value)} />
              </Field>
            ))}
            <Field label="Bande prix/kWc — source" htmlFor="pe-bande-ci-source">
              <Input id="pe-bande-ci-source" value={bandeCi.source ?? ''}
                     aria-invalid={sourceManquante(bandeCi, MONTANTS_BANDE_CI)}
                     onChange={e => setBandeCi('source', e.target.value)} />
              {sourceManquante(bandeCi, MONTANTS_BANDE_CI) && (
                <p role="alert" className="text-[11px] text-destructive">{MSG_SOURCE}</p>
              )}
            </Field>
            <Field label="Bande prix/kWc — date" htmlFor="pe-bande-ci-date">
              <Input id="pe-bande-ci-date" type="date" value={bandeCi.date ?? ''}
                     onChange={e => setBandeCi('date', e.target.value)} />
            </Field>
          </div>
          {/* Q5 (fondateur, 20/08/2026) — délais commerciaux INDICATIFS.
              Ils étaient codés en dur dans les renderers PDF et rendus dans la
              boîte « Conditions », où ils se lisaient comme contractuels. Ils
              sont désormais édités ici, affichés hors des Conditions et suivis
              de « (indicatif) ». Champ VIDÉ ⇒ le délai n'apparaît sur aucun
              document — jamais un forfait déguisé en donnée société. */}
          <div className="pe-grid-2 mt-2.5">
            <Field label="Délai de visite technique (indicatif ; vide = non affiché)"
                   htmlFor="pe-delai-visite">
              <Input id="pe-delai-visite" name="delai_visite_technique"
                     placeholder="48-72 h"
                     value={form.delai_visite_technique} onChange={set} />
            </Field>
            <Field label="Délai d'installation (indicatif ; vide = non affiché)"
                   htmlFor="pe-delai-installation">
              <Input id="pe-delai-installation" name="delai_installation"
                     placeholder="7-14 jours ouvrés"
                     value={form.delai_installation} onChange={set} />
            </Field>
          </div>
          <div className="mb-1 mt-3 text-xs font-semibold text-foreground">
            Numérotation des pièces
          </div>
          {DOC_TYPES.map(([k, lbl]) => (
            <div key={k} className="mb-2.5">
              <div className="mb-1 text-[11px] font-semibold text-muted-foreground">{lbl}</div>
              <div className="pe-grid-3">
                <div className="flex flex-col gap-1">
                  <Label className="text-[10.5px] font-normal text-muted-foreground">Préfixe</Label>
                  <Input value={form.doc_prefixes?.[k] ?? ''}
                         onChange={e => setPrefix(k, e.target.value)} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-[10.5px] font-normal text-muted-foreground">Largeur (chiffres)</Label>
                  <Input type="number" step="any"
                         value={form.doc_numbering?.[k]?.padding ?? 4}
                         onChange={e => setNumbering(k, 'padding', e.target.value)} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-[10.5px] font-normal text-muted-foreground">Réinitialisation</Label>
                  <Select value={form.doc_numbering?.[k]?.reset ?? 'monthly'}
                          onValueChange={v => setNumbering(k, 'reset', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="monthly">Mensuelle</SelectItem>
                      <SelectItem value="yearly">Annuelle</SelectItem>
                      <SelectItem value="none">Continue</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="mt-0.5 font-mono text-[10.5px] text-muted-foreground">
                Aperçu : {numberingPreview(k)}
              </div>
            </div>
          ))}
          <p className="mt-2.5 text-[11px] text-muted-foreground">
            Les numéros déjà émis ne changent pas ; seuls les nouveaux suivent ces
            réglages. « Mensuelle » repart à 1 chaque mois (comportement actuel),
            « Annuelle » chaque année, « Continue » ne repart jamais. La
            numérotation reste sans trou et sans collision.
          </p>
          <div className="mb-1 mt-4 text-xs font-semibold text-foreground">
            Commission commerciale
          </div>
          <p className="mb-2.5 text-[11.5px] text-muted-foreground">
            Désactivée par défaut. Calculée sur les devis signés, par
            commercial (responsable du lead, sinon créateur). Visible des
            seuls admins dans Rapports → Commissions commerciales.
          </p>
          {/* WR12/N99 — réglage sensible : édition réservée à l'admin. */}
          {!canManageSensitive ? (
            <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-[11.5px] text-muted-foreground">
              Réservé à l'administrateur. Contactez un administrateur pour
              configurer la commission commerciale.
            </p>
          ) : (
          <div className="pe-grid-2">
            <Field label="Mode" htmlFor="pe-commission-mode">
              <Select value={form.commission_mode}
                      onValueChange={v => set({ target: { name: 'commission_mode', value: v } })}>
                <SelectTrigger id="pe-commission-mode"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="off">Désactivée</SelectItem>
                  <SelectItem value="pct_devis">% du HT des devis signés</SelectItem>
                  <SelectItem value="par_kwc">MAD par kWc installé</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label={form.commission_mode === 'par_kwc'
              ? 'Valeur (MAD/kWc)' : 'Valeur (%)'} htmlFor="pe-commission-val">
              <Input id="pe-commission-val" type="number" step="any"
                     name="commission_valeur" value={form.commission_valeur}
                     onChange={set}
                     aria-required={form.commission_mode !== 'off'}
                     aria-invalid={form.commission_mode !== 'off'
                       && (form.commission_valeur === '' || form.commission_valeur == null)}
                     disabled={form.commission_mode === 'off'} />
              {/* L788 — la valeur est obligatoire dès qu'un mode actif est choisi. */}
              {form.commission_mode !== 'off'
                && (form.commission_valeur === '' || form.commission_valeur == null) && (
                <p className="text-[11px] text-destructive">
                  La valeur de commission est obligatoire quand un mode est actif.
                </p>
              )}
            </Field>
          </div>
          )}

          {/* WR12/N105 — interrupteur maître DGI (export UBL local). Sensible :
              édition réservée à l'admin. OFF par défaut → capacité invisible. */}
          {canManageSensitive && (
            <>
              <div className="mb-1 mt-4 text-xs font-semibold text-foreground">
                Export DGI (facturation électronique)
              </div>
              <p className="mb-2 text-[11.5px] text-muted-foreground">
                Interrupteur maître de la capacité DGI locale (export UBL 2.1 +
                validateur de conformité). Désactivé par défaut : tant qu'il
                l'est, la capacité reste totalement invisible et ne change rien.
              </p>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <Switch name="dgi_export_actif"
                        checked={!!form.dgi_export_actif}
                        onCheckedChange={v => setForm(f => ({ ...f, dgi_export_actif: v }))} />
                Activer l'export DGI
              </label>
            </>
          )}
        </CardContent>
      </Card>

      {/* TVA / Taxes (réglage légal/comptable) */}
      <Card className="border-warning/40">
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="TVA / Taxes" icon={<><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-warning">
            ⚠ Réglage légal/comptable. Les valeurs par défaut (10 % panneaux,
            20 % standard) correspondent à la réforme marocaine. À vérifier
            avec votre comptable avant toute modification.
          </p>
          <div className="pe-grid-2">
            <Field label="Taux standard (%)" htmlFor="pe-tva-standard">
              <Input id="pe-tva-standard" type="number" step="any"
                     name="tva_standard" value={form.tva_standard} onChange={set} />
            </Field>
            <Field label="Taux panneaux PV (%)" htmlFor="pe-tva-panneaux">
              <Input id="pe-tva-panneaux" type="number" step="any"
                     name="tva_panneaux" value={form.tva_panneaux} onChange={set} />
            </Field>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
