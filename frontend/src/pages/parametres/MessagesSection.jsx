// Onglet « Messages & relances » de la page Paramètres (niveaux de relance,
// modèles WhatsApp FR/Darija). Restylé sur le système de design (@/ui) ;
// champs, libellés et comportement identiques.
import { Check } from 'lucide-react'
import { Card, CardContent, Input, Textarea, Button } from '../../ui'
import { SectionTitle, Field } from './peComponents'

export default function MessagesSection({
  niveaux, setNiveau, saveNiveaux, niveauxSaved,
  messages, setMsgField, saveMessage, msgSavedCle,
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
          </p>
          {niveaux.map(n => (
            <div key={n.id} className="pe-grid-relance mb-2.5">
              <Field label={`Niveau ${n.ordre}`} htmlFor={`pe-niv-nom-${n.id}`}>
                <Input id={`pe-niv-nom-${n.id}`} value={n.nom}
                       onChange={e => setNiveau(n.id, 'nom', e.target.value)} />
              </Field>
              <Field label="Jours (J+)" htmlFor={`pe-niv-jours-${n.id}`}>
                <Input id={`pe-niv-jours-${n.id}`} type="number" min="0" value={n.delai_jours}
                       onChange={e => setNiveau(n.id, 'delai_jours', e.target.value)} />
              </Field>
            </div>
          ))}
          {niveaux.length === 0 && (
            <p className="text-xs text-muted-foreground">Aucun niveau configuré.</p>
          )}
          <Button type="button" className="mt-1" variant={niveauxSaved ? 'success' : 'destructive'}
                  onClick={saveNiveaux}>
            {niveauxSaved ? (
              <><Check className="size-4" aria-hidden="true" /> Niveaux enregistrés</>
            ) : 'Enregistrer les niveaux'}
          </Button>
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
              <Button type="button" size="sm" className="mt-0.5"
                      variant={msgSavedCle === m.cle ? 'success' : 'default'}
                      onClick={() => saveMessage(m)}>
                {msgSavedCle === m.cle ? (
                  <><Check className="size-3.5" aria-hidden="true" /> Enregistré</>
                ) : 'Enregistrer'}
              </Button>
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
