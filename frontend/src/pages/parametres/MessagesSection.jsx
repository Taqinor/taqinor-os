// Onglet « Messages & relances » de la page Paramètres (niveaux de relance,
// modèles WhatsApp FR/Darija). Restylé sur le système de design (@/ui) ;
// champs, libellés et comportement identiques.
import { AlertCircle, Check, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { Card, CardContent, Input, Textarea, Button, IconButton } from '../../ui'
import { SectionTitle, Field } from './peComponents'

// L774 — valeurs d'exemple pour l'aperçu rendu d'un modèle WhatsApp.
const SAMPLE = {
  civilite: 'M.', nom: 'Alami', reference: 'DEV-2026-0001',
  lien: 'https://taqinor.ma/p/exemple', n: '2',
}
function renderPreview(corps) {
  return (corps || '').replace(/\{(\w+)\}/g, (m, k) => (k in SAMPLE ? SAMPLE[k] : m))
}

export default function MessagesSection({
  niveaux, setNiveau, saveNiveaux, niveauxSaved, niveauxError, addNiveau, delNiveau, seedNiveaux,
  messages, setMsgField, saveMessage, resetMessage, msgSavedCle,
}) {
  return (
    <>
      {/* Niveaux de relance */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Niveaux de relance" icon={<><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Seuils de retard (en jours) pour relancer les factures impayées.
            Vue / consigne / impression uniquement — aucun envoi automatique.
            Le message est utilisé comme consigne/modèle pour ce niveau.
          </p>
          {niveaux.map(n => (
            <div key={n.id} className="mb-3 rounded-lg border border-border p-3">
              <div className="pe-grid-relance mb-2">
                <Field label={`Niveau ${n.ordre}`} htmlFor={`pe-niv-nom-${n.id}`}>
                  <Input id={`pe-niv-nom-${n.id}`} value={n.nom}
                         onChange={e => setNiveau(n.id, 'nom', e.target.value)} />
                </Field>
                <Field label="Jours (J+)" htmlFor={`pe-niv-jours-${n.id}`}>
                  <Input id={`pe-niv-jours-${n.id}`} type="number" step="any" value={n.delai_jours}
                         onChange={e => setNiveau(n.id, 'delai_jours', e.target.value)} />
                </Field>
              </div>
              {/* L766 — message du niveau en textarea (round-trip à l'enregistrement). */}
              <Field label="Message / consigne" htmlFor={`pe-niv-msg-${n.id}`}>
                <Textarea id={`pe-niv-msg-${n.id}`} className="min-h-[54px] resize-y"
                          value={n.message ?? ''}
                          placeholder="Ex : Rappel amiable, la facture {reference} est échue…"
                          onChange={e => setNiveau(n.id, 'message', e.target.value)} />
              </Field>
              {/* L767 — suppression d'un niveau. */}
              <div className="mt-1 flex justify-end">
                <IconButton size="sm" variant="outline" label="Supprimer ce niveau"
                            className="text-destructive hover:text-destructive"
                            onClick={() => delNiveau(n)}>
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </IconButton>
              </div>
            </div>
          ))}
          {/* L768 — carte vide : proposer la création des niveaux par défaut. */}
          {niveaux.length === 0 && (
            <div className="mb-3 rounded-lg border border-dashed border-border p-4 text-center">
              <p className="mb-2 text-xs text-muted-foreground">Aucun niveau configuré.</p>
              <Button type="button" size="sm" variant="outline" onClick={seedNiveaux}>
                <Plus className="size-3.5" aria-hidden="true" /> Créer les niveaux par défaut (J+7 / J+15 / J+30)
              </Button>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-1.5">
            {/* L767 — ajout d'un niveau. */}
            <Button type="button" size="sm" variant="outline" onClick={addNiveau}>
              <Plus className="size-3.5" aria-hidden="true" /> Ajouter un niveau
            </Button>
            <Button type="button" variant={niveauxSaved ? 'success' : 'destructive'}
                    onClick={saveNiveaux}>
              {niveauxSaved ? (
                <><Check className="size-4" aria-hidden="true" /> Niveaux enregistrés</>
              ) : 'Enregistrer les niveaux'}
            </Button>
          </div>
          {/* ERR63 — échec par-ligne remonté en français (au lieu d'être avalé). */}
          {niveauxError && (
            <div className="mt-2 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
              <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              <span>{niveauxError}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Messages WhatsApp */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Messages WhatsApp" icon={<><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.38 8.38 0 0 1-4-1L3 21l1-5.5a8.38 8.38 0 0 1-1-4A8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Modèles du message « Envoyer par WhatsApp » (devis, facture,
            rappel). Variantes Français et Darija. Placeholders disponibles :
            {' '}<code>{'{civilite}'}</code> <code>{'{nom}'}</code>{' '}
            <code>{'{reference}'}</code> <code>{'{lien}'}</code>{' '}
            <code>{'{n}'}</code>. Le lien envoyé est public, en lecture seule,
            expire après 30 jours et ne montre que le PDF client.
          </p>
          {messages.map(m => (
            <div key={m.cle} className="mt-2.5 border-t border-border pt-2.5">
              <div className="mb-1 text-xs font-semibold text-foreground">
                {m.label}
                {m.placeholders?.length > 0 && (
                  <span className="ml-1.5 font-normal text-muted-foreground">
                    ({m.placeholders.join(' ')})
                  </span>
                )}
              </div>
              <Field label="Français" htmlFor={`pe-msg-fr-${m.cle}`}>
                <Textarea id={`pe-msg-fr-${m.cle}`} className="min-h-[54px] resize-y"
                          value={m.corps_fr}
                          onChange={e => setMsgField(m.cle, 'corps_fr', e.target.value)} />
              </Field>
              <Field label="Darija (laisser vide = utiliser le Français)" htmlFor={`pe-msg-dr-${m.cle}`}>
                <Textarea id={`pe-msg-dr-${m.cle}`} className="min-h-[54px] resize-y"
                          value={m.corps_darija}
                          onChange={e => setMsgField(m.cle, 'corps_darija', e.target.value)} />
              </Field>
              {/* L774 — aperçu rendu avec valeurs d'exemple substituées. */}
              <div className="mt-1 rounded-md border border-dashed border-border bg-muted/40 p-2">
                <div className="mb-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Aperçu (exemple)
                </div>
                <p className="whitespace-pre-wrap text-[11.5px] text-foreground">
                  {renderPreview(m.corps_darija || m.corps_fr)}
                </p>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                <Button type="button" size="sm"
                        variant={msgSavedCle === m.cle ? 'success' : 'default'}
                        onClick={() => saveMessage(m)}>
                  {msgSavedCle === m.cle ? (
                    <><Check className="size-3.5" aria-hidden="true" /> Enregistré</>
                  ) : 'Enregistrer'}
                </Button>
                {/* L776 — réinitialiser ce modèle au texte par défaut. */}
                {resetMessage && (
                  <Button type="button" size="sm" variant="outline"
                          onClick={() => resetMessage(m)}>
                    <RotateCcw className="size-3.5" aria-hidden="true" /> Réinitialiser au modèle par défaut
                  </Button>
                )}
              </div>
            </div>
          ))}
          {messages.length === 0 && (
            <p className="text-xs text-muted-foreground">Chargement…</p>
          )}
        </CardContent>
      </Card>
    </>
  )
}
