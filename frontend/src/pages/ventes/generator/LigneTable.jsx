// QJR100 — LA TABLE DES LIGNES DU DEVIS, extraite VERBATIM de
// `DevisGenerator.jsx` (ex-région « Lignes de produits »).
// ---------------------------------------------------------------------------
// Elle ENROBE `DevisLineRow.jsx` (déjà extrait, mémoïsé) et POSSÈDE tout ce qui
// entoure une ligne : l'ajout (produit / section / note), la suppression, le
// réordonnancement, l'enregistrement de l'ordre par défaut (PVORD), le bloc
// multi-propriétés (QJ31) et l'échappatoire « accessoires seuls » (QX20).
//
// RÈGLE FONDATEUR PRÉSERVÉE VERBATIM : aucun champ ne « snappe » jamais — tous
// les `<input type="number">` déplacés ici gardent `step="any"`, et le
// formulaire porteur reste `noValidate` (il est resté dans la coquille). Le
// balisage est repris à l'octet : mêmes classes, mêmes `title`, mêmes
// `aria-label`, même ordre de colonnes — le contrat DOM des tests RTL
// (DevisGeneratorLinesInput, DevisGeneratorOrdreLignes) est inchangé.
//
// AUCUNE règle métier ici : ce composant ne calcule rien, il ne fait que
// rendre et remonter les gestes.
import { Card, CardContent, Button, IconButton, Input, Label, Segmented } from '../../../ui'
import { ShoppingCart, Plus, Trash2 } from 'lucide-react'
import DevisLineRow from '../DevisLineRow'
import { GenCardHeader } from './CarteMetrique'
import { formatMoney } from '../../../features/ventes/solar'

export default function LigneTable({
  // ── Lignes ──
  lines, produits, linesTableRef, canRenameLine, tarifBadges, quoteLogic,
  onSetField, onDesignationBlur, onProduitChange, onProduitCreated,
  onQuantiteChange, onSetGroupe, onRemove, onMoveUp, onMoveDown,
  // ── Ajout / ordre ──
  addLine, addStructureLine, handleSaveOrdreLignes, savingOrdreLignes,
  // ── Multi-propriétés (QJ31) ──
  multiMode, onMultiModeChange, multiAccordionOpen, setMultiAccordionOpen,
  nombreProprietes, setNombreProprietes, multiPreview,
  villaGroups, renameVillaGroup, removeVillaGroup, addVillaGroup,
  // ── Divers ──
  errorLines, accessoiresOnly, setAccessoiresOnly,
  // Le RAIL D'ARGENT (`RailArgent`) vit DANS cette même carte, sous la table :
  // c'est le contrat visuel historique (mêmes `CardContent`, même bordure).
  // Il est passé en `children` pour que le DOM rendu soit inchangé à l'octet.
  children,
}) {
  return (
    <Card>
      <GenCardHeader icon={ShoppingCart} title="Lignes de Produits">
        {/* XSAL14 — section (intertitre) / note (texte) : structurent le
            devis sans prix, exclues de tous les totaux. */}
        <Button type="button" size="sm" variant="ghost"
                onClick={() => addStructureLine('section')}
                title="Ajouter un intertitre de section (sans prix)">
          + Section
        </Button>
        <Button type="button" size="sm" variant="ghost"
                onClick={() => addStructureLine('note')}
                title="Ajouter une note (texte sans prix)">
          + Note
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={addLine}>
          <Plus /> Ajouter ligne
        </Button>
        {/* PVORD (fondateur 19/08/2026) — persiste l'ordre ÉCRAN courant
            comme nouvel ordre par défaut des PROCHAINS devis
            (ParametresGammes.ordre_lignes). Réservé Admin/Responsable
            côté serveur (même garde que Paramètres → Gammes & marques) ;
            un rôle non autorisé reçoit un toast d'erreur, pas un crash. */}
        <Button type="button" size="sm" variant="ghost"
                loading={savingOrdreLignes}
                onClick={handleSaveOrdreLignes}
                title="Enregistre l'ordre actuel des lignes comme ordre par défaut pour les prochains devis">
          Enregistrer cet ordre comme ordre par défaut
        </Button>
      </GenCardHeader>
      <CardContent className="px-0 pt-0">
        {/* ── QJ31 — Multi-propriétés (un seul devis) ──
            VX138(e) — accordéon : repliée PAR DÉFAUT en agricole (non
            pertinent pour ce mode) mais jamais masquée ; l'utilisateur
            peut toujours la rouvrir librement. */}
        <details className="mx-4 mt-4 rounded-lg border border-border bg-muted/30 sm:mx-5"
                  open={multiAccordionOpen}
                  onToggle={e => setMultiAccordionOpen(e.currentTarget.open)}>
          <summary className="cursor-pointer select-none px-3 py-3 font-display text-sm font-semibold tracking-tight sm:px-4">
            Plusieurs propriétés ?
            {multiMode !== 'none' && (
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                ({multiMode === 'multiplier' ? '× N identiques' : '+ Villas différentes'})
              </span>
            )}
          </summary>
          <div className="border-t border-border p-3 sm:p-4">
          <div className="flex flex-wrap items-center gap-3">
            <Segmented
              className="flex-wrap"
              options={[
                { value: 'none', label: 'Une seule' },
                { value: 'multiplier', label: '× N identiques' },
                { value: 'villas', label: '+ Villas différentes' },
              ]}
              value={multiMode}
              onChange={onMultiModeChange}
            />
          </div>

          {multiMode === 'multiplier' && (
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="gen-nbprop">Nombre de propriétés identiques</Label>
                <Input id="gen-nbprop" type="number" min="1" step="any" className="w-40"
                       value={nombreProprietes}
                       onChange={e => setNombreProprietes(e.target.value)} />
              </div>
              {multiPreview?.mode === 'multiplicateur' && (
                <div className="text-sm text-muted-foreground">
                  {multiPreview.nombreProprietes} × {formatMoney(multiPreview.totalUnitaireSans)}
                  {' = '}
                  <strong className="text-foreground">{formatMoney(multiPreview.totalMultiSans)}</strong>
                  {' '}(total pour {multiPreview.nombreProprietes} propriétés)
                </div>
              )}
            </div>
          )}

          {multiMode === 'villas' && (
            <div className="mt-3 flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {villaGroups.map(g => (
                  <div key={g.index} className="flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1">
                    <Input
                      className="h-7 w-32 border-0 bg-transparent px-1 text-sm shadow-none focus-visible:ring-0"
                      value={g.label}
                      onChange={e => renameVillaGroup(g.index, e.target.value)}
                      aria-label={`Nom du groupe ${g.index}`} />
                    {g.index !== 0 && (
                      <IconButton type="button" label="Supprimer la villa" size="sm"
                                  className="size-6 text-destructive hover:bg-destructive/10"
                                  onClick={() => removeVillaGroup(g.index)}>
                        <Trash2 />
                      </IconButton>
                    )}
                  </div>
                ))}
                <Button type="button" size="sm" variant="outline" onClick={addVillaGroup}>
                  <Plus /> Ajouter une villa
                </Button>
              </div>
              {multiPreview?.mode === 'villas' && (
                <div className="rounded-md border border-info/30 bg-info/5 p-2 text-sm">
                  {multiPreview.groupes.map(g => (
                    <div key={g.index} className="flex justify-between gap-4">
                      <span>{g.label}</span>
                      <span className="tabular-nums">{formatMoney(g.totalTtc)}</span>
                    </div>
                  ))}
                  <div className="mt-1 flex justify-between gap-4 border-t border-info/30 pt-1 font-semibold">
                    <span>Total général</span>
                    <span className="tabular-nums">{formatMoney(multiPreview.grandTotalTtc)}</span>
                  </div>
                </div>
              )}
            </div>
          )}
          </div>
        </details>

        {errorLines && <div className="px-4 py-2 text-xs text-destructive">{errorLines}</div>}
        {/* QX20 — échappatoire documentée à la garde d'équipement solaire.
            Relibellée (incident fondateur 01/09 round 2) : ce même état
            EST le mode « Composition libre » — le libellé d'origine
            (« accessoires seuls ») la cachait comme un cas marginal alors
            qu'elle est LA façon de composer un devis à la main, sans
            imposer panneau/onduleur. Même state + même clé de persistance
            (`accessoiresOnly`) pour ne pas casser les brouillons existants ;
            reprise à l'identique en haut de l'écran (voir controls). */}
        <label className="px-4 pb-1 flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          <input type="checkbox" checked={accessoiresOnly}
                 onChange={e => setAccessoiresOnly(e.target.checked)} />
          Composition libre — je choisis les articles moi-même (aucun panneau/onduleur imposé)
        </label>
        <div className="lines-table-wrap">
          <table className="lines-table" ref={linesTableRef}>
            <thead>
              <tr>
                <th style={{ minWidth: 160 }}>Désignation</th>
                <th style={{ minWidth: 170 }}>Produit (stock)</th>
                {multiMode === 'villas' && <th style={{ minWidth: 130 }}>Villa</th>}
                <th className="col-num">Qté</th>
                <th className="col-num">Prix Unit. TTC</th>
                <th className="col-num" style={{ width: 64 }} title="Taux TVA de la ligne (réforme : 10 % panneaux PV, 20 % le reste)">TVA %</th>
                <th className="col-num">Total TTC</th>
                {/* XSAL5 — case « option » : la ligne est un add-on proposé
                    hors total (activable par le client sur la proposition). */}
                <th style={{ width: 56 }} title="Ligne optionnelle (add-on) : proposée au client hors total">Option</th>
                {/* PVORD — monter/descendre : ordre par défaut = ordre du
                    simulateur (autoFillLines), réordonnable ici. */}
                <th className="col-ordre" title="Réordonner la ligne">Ordre</th>
                <th className="col-del"></th>
              </tr>
            </thead>
            <tbody>
              {/* VX188 — ligne extraite en <DevisLineRow> mémoïsé : taper
                  dans Note/farmSurfaceHa/n'importe lequel des autres
                  useState ne re-rend plus les lignes inchangées (callbacks
                  stabilisés ci-dessus, clé en argument). */}
              {lines.map((l, i) => (
                <DevisLineRow
                  key={l._key}
                  line={l}
                  produits={produits}
                  multiMode={multiMode}
                  villaGroups={villaGroups}
                  canRenameLine={canRenameLine}
                  tarifBadge={tarifBadges[l._key]}
                  tvaPanneaux={quoteLogic.tvaPanneaux}
                  tvaStandard={quoteLogic.tvaStandard}
                  onSetField={onSetField}
                  onDesignationBlur={onDesignationBlur}
                  onProduitChange={onProduitChange}
                  onProduitCreated={onProduitCreated}
                  onQuantiteChange={onQuantiteChange}
                  onSetGroupe={onSetGroupe}
                  onRemove={onRemove}
                  canMoveUp={i > 0}
                  canMoveDown={i < lines.length - 1}
                  onMoveUp={onMoveUp}
                  onMoveDown={onMoveDown}
                />
              ))}
            </tbody>
          </table>
        </div>

        {children}
      </CardContent>
    </Card>
  )
}
