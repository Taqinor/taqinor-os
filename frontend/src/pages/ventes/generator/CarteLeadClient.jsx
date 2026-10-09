// SPL50 — LA CARTE « Lead & Client » DU GÉNÉRATEUR, déplacée telle quelle
// de DevisGenerator.jsx : sélecteur de lead (lecture seule en édition,
// QJR580), téléphone, bandeau du client résolu, raccourci conception 3D
// (PV23bis), sélecteur client recherché (QC1) et création rapide (QG3).
// Props nommées une par une, jamais de spread.
import { Button, Card, CardContent, Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../ui'
import { GenCardHeader } from './CarteMetrique'
import { Plus, User } from 'lucide-react'
import { Combobox } from '../../../ui/Combobox'

export default function CarteLeadClient({
  clients, saving, errors, editId, editDevis, leadId, clientId, setClientQuickCreateOpen,
  leadsListe, selectedLead, resolvedClientLabel, applyLead, applyClient, selectedClient,
  onSearchClient, ouvrirConception3D,
}) {
  return (
    <>
      {/* ── Lead / Client (lead prioritaire) ── */}
      <Card id="gen-sec-lead" data-nav-libelle="Lead & Client">
        <GenCardHeader icon={User} title="Lead & Client" />
        <CardContent className="pt-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              {editId ? (
                /* QJR580 — Édition complète : lead / client en LECTURE
                   SEULE. L'enregistrement d'édition ne porte ni lead ni
                   client : un sélecteur actif laissait croire à une
                   réaffectation jetée, tout en ré-semant les factures du
                   nouveau lead (applyLead) sur ce devis. Réaffecter n'est
                   pas une correction (D-QJR5-1). */
                <>
                  <Label>Lead / client du devis</Label>
                  <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm"
                       data-testid="gen-lead-lecture-seule">
                    <strong>{editDevis?.lead_nom || editDevis?.client_nom || '…'}</strong>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Changer de client = créer un nouveau devis.
                    </p>
                  </div>
                </>
              ) : (<>
              <Label htmlFor="gen-lead" required>Lead (point de départ)</Label>
              {/* CI #752 — aucune option n'a la valeur '' : un '' ne vient que
                  du <select> natif caché du Select quand la valeur posée
                  n'est pas ENCORE dans ses options (lead d'un devis rouvert
                  relu après coup, hors première page de `leads`). Il vidait
                  le lead ; il est ignoré. */}
              <Select value={leadId ? String(leadId) : undefined}
                      onValueChange={(v) => { if (v) applyLead(v) }}>
                <SelectTrigger id="gen-lead" invalid={!!errors.client}>
                  <SelectValue placeholder="— Sélectionner un lead —" />
                </SelectTrigger>
                <SelectContent>
                  {leadsListe.map(l => (
                    <SelectItem key={l.id} value={String(l.id)}>
                      {l.nom}{l.prenom ? ` ${l.prenom}` : ''}
                      {l.societe ? ` (${l.societe})` : ''}
                      {l.facture_hiver ? ` — ${Math.round(parseFloat(l.facture_hiver))} MAD/mois` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              </>)}
              {errors.client && <p className="text-xs text-destructive">{errors.client}</p>}
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-tel">Téléphone</Label>
              <Input id="gen-tel" disabled placeholder="—"
                     value={selectedLead?.telephone ?? selectedClient?.telephone ?? ''} />
            </div>
          </div>

          {selectedLead && (
            <div className="mt-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
              ✓ Client du devis : <strong>{resolvedClientLabel}</strong>
              {selectedLead.facture_hiver
                ? ` · factures remplies depuis le lead (${selectedLead.facture_hiver}${selectedLead.ete_differente && selectedLead.facture_ete ? ` hiver / ${selectedLead.facture_ete} été` : ' MAD/mois'})`
                : ' · aucune facture enregistrée sur ce lead'}
            </div>
          )}

          {/* QX28 — raccourci vers la conception 3D. PV23bis (fondateur
              20/08, remplace PV23 ci-dessous) : visible dès qu'un lead OU
              un client est choisi — plus seulement quand le lead porte un
              repère toit (GPS) — parce que le bouton n'ouvre plus jamais un
              lead déconnecté du devis : il enregistre D'ABORD le formulaire
              (création ou édition, `ouvrirConception3D`) puis ouvre
              l'outil SUR ce devis. Le repère GPS du lead, quand il existe,
              reste simplement annoncé dans le libellé. */}
          {(selectedLead || clientId) && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-brass-400/40 bg-brass-400/10 p-3 text-sm">
              {/* L-DESSIN (fondateur 25/08) — le libellé ne testait QUE
                  `roof_point` : un lead dont le client a DESSINÉ son toit
                  (`roof_outline`, la donnée la plus riche, chargée telle
                  quelle dans l'outil) s'annonçait « pas de repère ». Les
                  deux états sont désormais nommés, le tracé d'abord. */}
              <span>
                {Array.isArray(selectedLead?.roof_outline) && selectedLead.roof_outline.length >= 3
                  ? '🛰️ Contour de toit tracé par le client sur ce lead — il est chargé dans l\'outil 3D.'
                  : selectedLead?.roof_point
                    ? '🛰️ Repère toit disponible sur ce lead (GPS).'
                    : '🛰️ Concevez la toiture en 3D — le devis est d\'abord enregistré en brouillon.'}
              </span>
              {/* PV23bis — remplace PV23 : édition COMME création passent
                  désormais par `ouvrirConception3D` (enregistrement
                  d'abord, puis ouverture SUR le devis) — une édition non
                  enregistrée n'est plus perdue en repartant du lead. */}
              <Button type="button" variant="outline" size="sm"
                      disabled={saving} onClick={ouvrirConception3D}>
                Concevoir en 3D
              </Button>
            </div>
          )}

          {!leadId && !editId && (
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="gen-client">…ou choisir un client directement (sans lead)</Label>
                <div className="flex gap-2">
                  <div className="flex-1">
                    {/* QC1 — sélecteur client en Combobox recherché sur les
                        données propres (endpoint /search/, filtré aux clients
                        — un devis a besoin d'un id client réel). Les options
                        déjà chargées servent de repli/affichage immédiat. */}
                    <Combobox
                      id="gen-client"
                      options={clients.map(c => ({
                        value: String(c.id),
                        label: `${c.nom}${c.prenom ? ` ${c.prenom}` : ''}`,
                      }))}
                      value={clientId ? String(clientId) : null}
                      onSearch={onSearchClient}
                      onChange={(v) => applyClient(v)}
                      placeholder="— Sélectionner un client —"
                      searchPlaceholder="Nom ou ICE…"
                      emptyText="Aucun client dans vos données"
                    />
                  </div>
                  {/* QG3 — création rapide, sans quitter le devis */}
                  <Button type="button" variant="outline" onClick={() => setClientQuickCreateOpen(true)}>
                    <Plus /> Nouveau client
                  </Button>
                </div>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="gen-adresse">Adresse</Label>
                <Input id="gen-adresse" value={selectedClient?.adresse ?? ''} disabled placeholder="—" />
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}
