// Onglet « Avancé » de la page Paramètres (hypothèses ROI, logique de devis,
// types d'intervention, checklist d'exécution, champs personnalisés). Restylé
// sur le système de design (@/ui) ; champs, libellés et comportement identiques.
import { Plus, Trash2 } from 'lucide-react'
import {
  Card, CardContent, Input, Button, IconButton, Badge,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle, Field } from './peComponents'

export default function AvanceSection({
  form, set,
  typesItv, newType, setNewType, addType, renameType, delType,
  checklistEtapes, newEtape, setNewEtape, addEtape, renameEtape, toggleEtapeActif, delEtape,
  cfModule, setCfModule, cfDefs, newCf, setNewCf, addCf, delCf, loadCfDefs,
}) {
  return (
    <>
      {/* ROI — hypothèses (tarif ONEE, productible) */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Hypothèses ROI" icon={<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Constantes utilisées pour les estimations d'économies/rentabilité.
            Les valeurs par défaut reprennent l'historique du simulateur — rien
            ne change tant que vous ne les modifiez pas.
          </p>
          <div className="pe-grid-2">
            <Field label="Tarif ONEE moyen (MAD/kWh)" htmlFor="pe-onee">
              <Input id="pe-onee" type="number" min="0" step="0.001"
                     name="onee_tarif_kwh" value={form.onee_tarif_kwh} onChange={set} />
            </Field>
            <Field label="Productible (kWh/kWc/an)" htmlFor="pe-productible">
              <Input id="pe-productible" type="number" min="0" step="1"
                     name="productible_kwh_kwc" value={form.productible_kwh_kwc} onChange={set} />
            </Field>
            <Field label="Seuil d'approbation de remise (%)" htmlFor="pe-discount-thr">
              <Input id="pe-discount-thr" type="number" min="0" max="100" step="0.01"
                     name="discount_approval_threshold" placeholder="vide = désactivé"
                     value={form.discount_approval_threshold} onChange={set} />
            </Field>
            <Field label="Seuil régime « Déclaration » (kWc)" htmlFor="pe-seuil-decl">
              <Input id="pe-seuil-decl" type="number" min="0" step="0.01"
                     name="seuil_regime_declaration_kwc"
                     value={form.seuil_regime_declaration_kwc} onChange={set} />
            </Field>
            <Field label="Seuil régime « Autorisation ANRE » (kWc)" htmlFor="pe-seuil-anre">
              <Input id="pe-seuil-anre" type="number" min="0" step="0.01"
                     name="seuil_regime_anre_kwc"
                     value={form.seuil_regime_anre_kwc} onChange={set} />
            </Field>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Seuils loi 82-21 proposés à la création d'un chantier (régime
            suggéré, modifiable) : sous le 1er seuil = Déclaration, entre les
            deux = Accord de raccordement, au-dessus du 2nd = Autorisation ANRE.
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Au-delà de ce seuil de remise, un devis exige l'approbation d'un
            administrateur avant l'envoi. Vide = désactivé (défaut).
          </p>
        </CardContent>
      </Card>

      {/* Logique de devis (avancé) — paramètres implicites du simulateur (D5) */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Logique de devis (avancé)" icon={<><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Paramètres implicites du générateur de devis, rendus modifiables.
            Les valeurs par défaut reprennent EXACTEMENT les constantes du
            simulateur — le devis reste identique tant que vous ne les
            modifiez pas. Chaque changement est tracé (journal d'audit).
          </p>
          <div className="pe-grid-2">
            <Field label="Rendement global (0–1)" htmlFor="pe-rendement">
              <Input id="pe-rendement" type="number" min="0" max="1" step="0.01"
                     name="rendement_global" value={form.rendement_global} onChange={set} />
            </Field>
            <Field label="Panneaux par tranche de 900 MAD (auto-remplir)" htmlFor="pe-panneaux900">
              <Input id="pe-panneaux900" type="number" min="1" step="1"
                     name="panneaux_par_900mad" value={form.panneaux_par_900mad} onChange={set} />
            </Field>
            <Field label="Prix cible /kWc par défaut (MAD)" htmlFor="pe-prix-cible">
              <Input id="pe-prix-cible" type="number" min="0" step="any"
                     name="prix_cible_kwc_defaut" placeholder="vide = aucun"
                     value={form.prix_cible_kwc_defaut} onChange={set} />
            </Field>
            <Field label="Limite de remise conseillée (%)" htmlFor="pe-remise-max">
              <Input id="pe-remise-max" type="number" min="0" max="100" step="0.01"
                     name="remise_max_pct" placeholder="vide = aucune"
                     value={form.remise_max_pct} onChange={set} />
            </Field>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Le rendement et le tarif ONEE (ci-dessus) pilotent les économies
            estimées ; le ratio de dimensionnement pilote la suggestion de
            panneaux du devis auto ; le prix cible pré-remplit le générateur ;
            la limite de remise affiche un repère (sans bloquer la saisie).
            Les tables tarifaires ONEE par tranche et les facteurs de
            production par région restent un raffinement futur (modèle de
            calcul à valider avec le founder).
          </p>
        </CardContent>
      </Card>

      {/* Chantiers — Types d'intervention */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Chantiers — Types d'intervention" icon={<><path d="M14.7 6.3a4 4 0 0 0-5.6 5.6l-6 6 2 2 6-6a4 4 0 0 0 5.6-5.6l-2.5 2.5-2-2 2.5-2.5z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Types d'intervention proposés sur les chantiers. Les types système
            sont protégés ; un type déjà utilisé ne peut pas être supprimé.
          </p>
          {typesItv.map(t => (
            <div key={t.id} className="mb-1.5 flex items-center gap-1.5">
              <Input className="flex-1" defaultValue={t.libelle}
                     onBlur={e => renameType(t, e.target.value)} />
              {t.protege
                ? <Badge tone="info">système</Badge>
                : (
                  <IconButton size="md" variant="outline" label="Supprimer le type"
                              className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                              disabled={t.en_usage > 0}
                              onClick={() => delType(t)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
            </div>
          ))}
          <div className="flex gap-1.5">
            <Input className="flex-1" placeholder="Nouveau type" value={newType}
                   onChange={e => setNewType(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addType() } }} />
            <Button type="button" onClick={addType}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>

      {/* Chantiers — Checklist d'exécution */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Chantiers — Checklist d'exécution" icon={<><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Étapes proposées sur la checklist des chantiers. Désactivez une
            étape pour la retirer des nouveaux chantiers sans toucher aux
            chantiers existants ; les étapes système sont protégées.
          </p>
          {checklistEtapes.map(et => (
            <div key={et.id} className="mb-1.5 flex items-center gap-1.5">
              <Input className={['flex-1', et.actif ? '' : 'opacity-50'].join(' ')} defaultValue={et.libelle}
                     onBlur={e => renameEtape(et, e.target.value)} />
              {et.capture_serie && <Badge tone="info" title="Saisie de n° de série">série</Badge>}
              <Button type="button" size="sm"
                      variant={et.actif ? 'success' : 'secondary'}
                      title={et.actif ? 'Désactiver' : 'Activer'}
                      onClick={() => toggleEtapeActif(et)}>
                {et.actif ? 'Actif' : 'Inactif'}
              </Button>
              {et.protege
                ? <Badge tone="info">système</Badge>
                : (
                  <IconButton size="md" variant="outline" label="Supprimer l'étape"
                              className="text-destructive hover:text-destructive"
                              onClick={() => delEtape(et)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
            </div>
          ))}
          <div className="flex gap-1.5">
            <Input className="flex-1" placeholder="Nouvelle étape" value={newEtape}
                   onChange={e => setNewEtape(e.target.value)}
                   onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEtape() } }} />
            <Button type="button" onClick={addEtape}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>

      {/* Champs personnalisés */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Champs personnalisés" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Ajoutez vos propres champs aux fiches (leads, clients, produits).
            Ils apparaissent dans le formulaire ; rien n'est perdu si vous en
            retirez un.
          </p>
          <div className="mb-2 flex gap-1.5">
            <div className="w-[140px]">
              <Select value={cfModule}
                      onValueChange={v => { setCfModule(v); loadCfDefs(v) }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="lead">Leads</SelectItem>
                  <SelectItem value="client">Clients</SelectItem>
                  <SelectItem value="produit">Produits</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {cfDefs.map(d => (
            <div key={d.id} className="mb-1.5 flex items-center gap-1.5">
              <span className="flex-1 text-sm text-foreground">{d.libelle}</span>
              <span className="text-[11px] text-muted-foreground">{d.type}</span>
              <IconButton size="md" variant="outline" label="Supprimer le champ"
                          className="text-destructive hover:text-destructive"
                          onClick={() => delCf(d)}>
                <Trash2 className="size-4" aria-hidden="true" />
              </IconButton>
            </div>
          ))}
          <div className="flex flex-wrap gap-1.5">
            <Input className="min-w-[140px] flex-[1_1_140px]" placeholder="Libellé du champ"
                   value={newCf.libelle} onChange={e => setNewCf(c => ({ ...c, libelle: e.target.value }))} />
            <div className="w-[120px]">
              <Select value={newCf.type}
                      onValueChange={v => setNewCf(c => ({ ...c, type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Texte</SelectItem>
                  <SelectItem value="number">Nombre</SelectItem>
                  <SelectItem value="date">Date</SelectItem>
                  <SelectItem value="choice">Choix</SelectItem>
                  <SelectItem value="boolean">Oui/Non</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {newCf.type === 'choice' && (
              <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Options (a, b, c)"
                     value={newCf.options} onChange={e => setNewCf(c => ({ ...c, options: e.target.value }))} />
            )}
            <Button type="button" onClick={addCf}><Plus className="size-4" aria-hidden="true" /></Button>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
