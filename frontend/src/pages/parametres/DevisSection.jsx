// Onglet « Devis & Factures » de la page Paramètres (échéancier, validité,
// pompage, numérotation, commission, TVA/Taxes). Restylé sur le système de
// design (@/ui) ; champs, libellés et comportement identiques.
import {
  Card, CardContent, Input, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle, Field } from './peComponents'
import { MODE_LABELS, DOC_TYPES } from './peConstants'

export default function DevisSection({ form, set, setPT, setPrefix, setNumbering, numberingPreview }) {
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
                    <Input type="number" min="0" max="100"
                           value={form.payment_terms?.[mode]?.[k] ?? ''}
                           onChange={e => setPT(mode, k, e.target.value)} />
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="pe-grid-2 mt-2.5">
            <Field label="Validité du devis (jours)" htmlFor="pe-validity">
              <Input id="pe-validity" type="number" min="1" name="quote_validity_days"
                     value={form.quote_validity_days} onChange={set} />
            </Field>
            <Field label="Heures de pompage / jour (agricole, défaut)" htmlFor="pe-pump-hours">
              <Input id="pe-pump-hours" type="number" min="0" step="0.5" name="agricole_pump_hours"
                     value={form.agricole_pump_hours} onChange={set} />
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
                  <Input type="number" min="1" max="10"
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
              <Input id="pe-commission-val" type="number" min="0" step="any"
                     name="commission_valeur" value={form.commission_valeur}
                     onChange={set}
                     disabled={form.commission_mode === 'off'} />
            </Field>
          </div>
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
              <Input id="pe-tva-standard" type="number" min="0" max="100" step="0.01"
                     name="tva_standard" value={form.tva_standard} onChange={set} />
            </Field>
            <Field label="Taux panneaux PV (%)" htmlFor="pe-tva-panneaux">
              <Input id="pe-tva-panneaux" type="number" min="0" max="100" step="0.01"
                     name="tva_panneaux" value={form.tva_panneaux} onChange={set} />
            </Field>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
