// Gabarit commun des écrans d'équipes de Paramètres (ENF19) : Équipes
// terrain (WIR112) et Équipes commerciales (ZSAL3) partagent le même rendu ;
// seuls les libellés, le champ « responsable » et les actions changent.
import { Plus, Trash2, Archive, ArchiveRestore } from 'lucide-react'
import {
  Card, CardContent, Input, Label, Badge, IconButton, Button, Switch,
} from '../../ui'
import { SectionTitle, Field, ChargementErreur } from './peComponents'

export default function EquipesAdminPanel({
  titre, description, vide, placeholder, chefLabel, chefField, chefIdPrefix,
  testIdPrefix = null, loading, error, equipes, busyId, assignables,
  onRename, onArchive, onDelete, onSetChef, onToggleMembre, onToggleRecoitLeads,
  newNom, setNewNom, onAdd,
}) {
  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label={titre} icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">{description}</p>

        <ChargementErreur loading={loading} error={error} />

        {!loading && equipes.length === 0 && (
          <p className="mb-3 text-xs text-muted-foreground">{vide}</p>
        )}

        {!loading && equipes.map((eq) => (
          <div key={eq.id}
               className={['mb-3 rounded-lg border border-border p-3', eq.actif ? '' : 'opacity-50'].join(' ')}
               data-testid={testIdPrefix ? `${testIdPrefix}-${eq.id}` : undefined}>
            <div className="mb-2 flex items-center gap-1.5">
              <Input key={eq.nom} className="flex-1" defaultValue={eq.nom}
                     onBlur={(e) => onRename(eq, e.target.value)} />
              <Badge tone="neutral">{eq.nb_membres ?? 0} membre(s)</Badge>
              <IconButton size="md" variant="outline"
                          label={eq.actif ? 'Archiver' : 'Réactiver'}
                          disabled={busyId === eq.id}
                          onClick={() => onArchive(eq)}>
                {eq.actif
                  ? <Archive className="size-4" aria-hidden="true" />
                  : <ArchiveRestore className="size-4" aria-hidden="true" />}
              </IconButton>
              <IconButton size="md" variant="outline" label="Supprimer l'équipe"
                          className="text-destructive hover:text-destructive"
                          disabled={busyId === eq.id}
                          onClick={() => onDelete(eq)}>
                <Trash2 className="size-4" aria-hidden="true" />
              </IconButton>
            </div>
            {onToggleRecoitLeads && (
              <label className="mb-2 flex items-center gap-2 text-sm text-foreground">
                <Switch checked={!!eq.recoit_leads}
                        disabled={busyId === eq.id}
                        aria-label={`Reçoit les nouveaux leads — ${eq.nom}`}
                        onCheckedChange={(v) => onToggleRecoitLeads(eq, v)} />
                Reçoit les nouveaux leads
              </label>
            )}
            <Field label={chefLabel} htmlFor={`${chefIdPrefix}-${eq.id}`}>
              <select id={`${chefIdPrefix}-${eq.id}`} className="form-control"
                      value={eq[chefField] ?? ''}
                      disabled={busyId === eq.id}
                      onChange={(e) => onSetChef(eq, e.target.value ? Number(e.target.value) : null)}>
                <option value="">— Aucun —</option>
                {assignables.map((u) => (
                  <option key={u.id} value={u.id}>{u.username}</option>
                ))}
              </select>
            </Field>
            <Label className="mb-1 mt-2 block">Membres</Label>
            <div className="flex flex-wrap gap-1.5">
              {assignables.map((u) => {
                const active = (eq.membres ?? []).includes(u.id)
                return (
                  <button key={u.id} type="button"
                          disabled={busyId === eq.id}
                          onClick={() => onToggleMembre(eq, u.id)}
                          className={[
                            'rounded-full border px-2.5 py-1 text-xs transition-colors',
                            active
                              ? 'border-primary bg-primary/10 text-primary'
                              : 'border-border text-muted-foreground hover:bg-muted/40',
                          ].join(' ')}>
                    {u.username}
                  </button>
                )
              })}
            </div>
          </div>
        ))}

        <div className="mt-1.5 flex gap-1.5">
          <Input className="flex-1" placeholder={placeholder} value={newNom}
                 onChange={(e) => setNewNom(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAdd() } }} />
          <Button type="button" onClick={onAdd}><Plus className="size-4" aria-hidden="true" /></Button>
        </div>
      </CardContent>
    </Card>
  )
}
