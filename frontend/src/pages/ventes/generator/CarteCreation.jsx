// SPL49 — LE BAS DU FORMULAIRE DU GÉNÉRATEUR, déplacé tel quel de
// DevisGenerator.jsx : montage de l'échéancier (Édition complète), notes
// client (QJR627), avertissements non bloquants, raisons de blocage et carte
// « Création du Devis » (QJ28 contacter le supérieur, Réinitialiser, Annuler,
// Enregistrer). Props nommées une par une, jamais de spread.
import CarteEcheancier from './CarteEcheancier'
import { erreursConditions } from '../../../features/ventes/echeancierEdition'
import { Button, Card, CardContent, Textarea } from '../../../ui'
import { GenCardHeader } from './CarteMetrique'
import { FileText, RotateCcw, StickyNote, Sun } from 'lucide-react'
import { formatMoney } from '../../../features/ventes/solar'

export default function CarteCreation({
  embedded, clients, saving, errors, warnings, cancel, editDevis, superieurBusy, superieurMsg,
  contacterSuperieur, note, setNote, echeancierSaisie, termesEffectifs, conditions, setCondition,
  setEcheancierSaisie, modeInstallation, apercuPompage, kpiTotal, handleReset,
  // EDC7/EDC4 (contrat EDC) — l'écran reste ouvert après l'enregistrement.
  onEnregistre = null, onVoirPdf = null,
}) {
  return (
    <>
      {/* ── QJR624 — Échéancier (Édition complète seulement) ── */}
      {editDevis && (
        // EDC9 — ancre de navigation « Échéancier » (jamais repliable).
        <div id="gen-sec-echeancier" data-nav-libelle="Échéancier">
          <CarteEcheancier saisie={echeancierSaisie} setSaisie={setEcheancierSaisie}
                           mode={modeInstallation} effectifs={termesEffectifs}
                           conditions={conditions} setCondition={setCondition}
                           erreursConditions={erreursConditions(conditions)} clients={clients} />
        </div>
      )}
      {errors.conditions && (
        <p role="alert" className="text-xs text-destructive" data-testid="erreur-conditions">{errors.conditions}</p>
      )}

      {/* ── QJR627 (D-QJR5-6) — Notes = texte CLIENT, imprimé (PDF + proposition) ── */}
      <Card id="gen-sec-texte" data-nav-libelle="Texte client">
        <GenCardHeader icon={StickyNote} title="Texte pour le client (imprimé sur le devis)" />
        <CardContent className="pt-4">
          <Textarea rows={3} value={note}
                    onChange={e => setNote(e.target.value)}
                    placeholder="Conditions particulières, précisions pour le client…" />
        </CardContent>
      </Card>

      {/* Avertissements NON bloquants (lead perdu/archivé, chiffres d'étude
          auto) — informatifs, n'empêchent jamais l'enregistrement. */}
      {Object.values(warnings).filter(Boolean).length > 0 && (
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
          {Object.values(warnings).filter(Boolean).map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}
      {/* Toute raison de blocage est VISIBLE à côté du bouton — jamais de
          clic silencieux sans effet. */}
      {(errors.submit || errors.lines || errors.client || errors.conso || errors.factures) && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive" data-testid="erreur-enregistrement">
          {errors.submit || errors.lines || errors.client || errors.conso || errors.factures}
        </div>
      )}

      {/* ── Création ── */}
      <Card id="gen-sec-enregistrer" data-nav-libelle="Enregistrement">
        <GenCardHeader icon={FileText}
                       title={editDevis ? `Modification du devis ${editDevis.reference}` : 'Création du Devis'} />
        <CardContent className="pt-4">
          <p className="text-sm text-muted-foreground">
            {/* EDC7 — en Édition complète embarquée, l'écran RESTE ouvert
                après l'enregistrement : le texte le dit. */}
            {embedded && editDevis && onEnregistre
              ? "Vérifiez puis enregistrez : l'écran reste ouvert après l'enregistrement."
                + (onVoirPdf ? ' « Voir le PDF », en haut, affiche le document.' : '')
              : embedded
              ? "Vérifiez puis enregistrez. Le devis s'affiche ensuite ici même "
                + 'avec son PDF, sans quitter la fiche du lead.'
              : 'Vérifiez les informations ci-dessus puis créez le devis. Le PDF '
                + 'premium 3 pages se génère ensuite depuis la liste des devis (bouton « PDF »).'}
          </p>
          {modeInstallation === 'agricole' && (apercuPompage?.donnees?.prix_a_renseigner || []).length > 0 && (
            <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
                 data-testid="pompage-prix-a-renseigner">
              Attention : seules des pompes <strong>sans prix renseigné</strong> conviennent
              ({apercuPompage.donnees.prix_a_renseigner.join(', ')}). Aucune pompe ne sera chiffrée
              au devis tant que leur prix n'est pas saisi dans Stock.
            </div>
          )}
          {superieurMsg && (
            <div className={`mt-3 rounded-lg border p-3 text-sm ${superieurMsg.ok
              ? 'border-success/30 bg-success/10 text-success'
              : 'border-destructive/30 bg-destructive/10 text-destructive'}`}>
              {superieurMsg.text}
            </div>
          )}
          <div className="gen-actions-sticky mt-3 flex flex-wrap items-center justify-end gap-3">
            {/* VX138(d) — bandeau sticky au scroll (plus seulement mobile) :
                TTC courant condensé, dérivé de `totals`/`kpiTotal` déjà en
                mémoire (même valeur que le rail latéral VX16).
                EDC2 — masqué SEULEMENT quand le rail est visible
                (`gen-ttc-condense`, même container query que le rail) : le
                rail replié, le total reprend sa place ici. */}
            <div className="gen-ttc-condense mr-auto flex items-baseline gap-1.5 text-sm">
              <span className="text-muted-foreground">Total TTC</span>
              <strong className="tabular-nums text-base font-semibold text-foreground">
                {formatMoney(kpiTotal)}
              </strong>
            </div>
            {/* QJ28 — notification manuelle au supérieur (devis déjà enregistré) */}
            {editDevis && (
              <Button type="button" variant="outline" loading={superieurBusy}
                      onClick={contacterSuperieur}
                      title="Envoyer une notification à mon supérieur avec le lien de ce devis">
                Contacter mon supérieur
              </Button>
            )}
            {!embedded && (
              <Button type="button" variant="outline" onClick={handleReset}>
                <RotateCcw /> Réinitialiser
              </Button>
            )}
            <Button type="button" variant="ghost" onClick={cancel}>
              Annuler
            </Button>
            <Button type="submit" loading={saving}>
              {saving
                ? 'Enregistrement...'
                : (editDevis ? <><Sun /> Enregistrer les modifications</> : <><Sun /> Créer le devis</>)}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
