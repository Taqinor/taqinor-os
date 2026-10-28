// Attribution des leads (fondateur, 27/10/2026) — réglages d'UNE équipe
// commerciale : confirmation par le responsable, délai avant attribution
// automatique, et « Règles de proposition » (ville, type de client, source,
// facture → membre proposé, dans l'ordre ; sinon rotation équilibrée).
import { useCallback, useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import crmApi from '../../api/crmApi'
import useCanaux from '../../features/crm/useCanaux'
import { TYPE_INSTALLATION_LABELS } from '../../features/crm/stages'
import { Button, IconButton, Input, Label, Switch } from '../../ui'
import { apiErrorMessage } from '../../lib/apiError'
import fetchAllPages from '../../utils/fetchAllPages'

const VIDE = {
  villes: '', type_installation: '', source: '', facture_min: '', facture_max: '',
  membre: '', actif: true,
}

// Le serveur attend les montants en CHAÎNE décimale (« 1500.00 »), jamais un flottant.
const num = (v) => (v === '' || v == null ? null : Number(v).toFixed(2))

function LigneRegle({ regle, membres, canaux, typesClient, onSave, onDelete, onMove, busy }) {
  const [r, setR] = useState(regle)
  const maj = (k, v) => setR((cur) => ({ ...cur, [k]: v }))
  const enregistrer = () => onSave({
    ...r, facture_min: num(r.facture_min), facture_max: num(r.facture_max),
    membre: r.membre ? Number(r.membre) : null,
  })
  return (
    <div className="mb-2 grid grid-cols-2 items-end gap-2 rounded-md border border-border p-2 sm:grid-cols-4"
         data-testid="regle-attribution">
      <div>
        <Label>Villes</Label>
        <Input value={r.villes ?? ''} placeholder="Casablanca, Rabat"
               onChange={(e) => maj('villes', e.target.value)} />
      </div>
      <div>
        <Label>Type de client</Label>
        <select className="form-control" value={r.type_installation ?? ''}
                onChange={(e) => maj('type_installation', e.target.value)}>
          <option value="">Tous</option>
          {typesClient.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      <div>
        <Label>Source</Label>
        <select className="form-control" value={r.source ?? ''}
                onChange={(e) => maj('source', e.target.value)}>
          <option value="">Toutes</option>
          {canaux.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
      <div>
        <Label>Membre proposé</Label>
        <select className="form-control" value={r.membre ?? ''}
                onChange={(e) => maj('membre', e.target.value)}>
          <option value="">— Choisir —</option>
          {membres.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
      </div>
      <div>
        <Label>Facture min (DH)</Label>
        <Input type="number" step="any" value={r.facture_min ?? ''}
               onChange={(e) => maj('facture_min', e.target.value)} />
      </div>
      <div>
        <Label>Facture max (DH)</Label>
        <Input type="number" step="any" value={r.facture_max ?? ''}
               onChange={(e) => maj('facture_max', e.target.value)} />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Switch checked={!!r.actif} aria-label="Règle active"
                onCheckedChange={(v) => maj('actif', v)} />
        Active
      </label>
      <div className="flex items-center gap-1">
        <IconButton size="md" variant="outline" label="Monter" disabled={busy || !onMove.haut}
                    onClick={() => onMove.haut()}>
          <ArrowUp className="size-4" aria-hidden="true" />
        </IconButton>
        <IconButton size="md" variant="outline" label="Descendre" disabled={busy || !onMove.bas}
                    onClick={() => onMove.bas()}>
          <ArrowDown className="size-4" aria-hidden="true" />
        </IconButton>
        <Button type="button" size="sm" disabled={busy || !r.membre} onClick={enregistrer}>
          Enregistrer
        </Button>
        <IconButton size="md" variant="outline" label="Supprimer la règle"
                    className="text-destructive hover:text-destructive"
                    disabled={busy} onClick={onDelete}>
          <Trash2 className="size-4" aria-hidden="true" />
        </IconButton>
      </div>
    </div>
  )
}

export default function ReglesAttributionEditor({ equipe, assignables = [], onSaveEquipe, busy }) {
  const { options: canaux } = useCanaux()
  const [regles, setRegles] = useState([])
  const [erreur, setErreur] = useState(null)
  const membres = assignables.filter((u) => (equipe.membres ?? []).includes(u.id))
  const typesClient = Object.entries(TYPE_INSTALLATION_LABELS)

  const charger = useCallback(() =>
    fetchAllPages((page, o) => crmApi.getReglesAttribution(equipe.id, { page, ...o }).then((r) => r?.data))
      .then((data) => {
        const rows = Array.isArray(data) ? data : (data?.results ?? [])
        setRegles([...rows].sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0)))
        setErreur(null)
      })
      .catch((e) => setErreur(apiErrorMessage(e, 'Impossible de charger les règles de proposition.'))),
  [equipe.id])

  useEffect(() => { charger() }, [charger])

  const agir = (promesse, repli) =>
    promesse.then(charger).catch((e) => setErreur(apiErrorMessage(e, repli)))

  const enregistrer = (regle, ordre) => agir(
    crmApi.saveRegleAttribution(regle.id ?? null, { ...regle, equipe: equipe.id, ordre }),
    'L’enregistrement de la règle a échoué.')

  const deplacer = (i, delta) => {
    const j = i + delta
    const liste = [...regles]
    ;[liste[i], liste[j]] = [liste[j], liste[i]]
    return agir(
      Promise.all(liste.map((x, k) => (!x.id || x.ordre === k ? null
        : crmApi.saveRegleAttribution(x.id, { ordre: k })))),
      'Le changement d’ordre a échoué.')
  }

  const ajouter = () => setRegles((l) => [...l, { ...VIDE, equipe: equipe.id, ordre: l.length, _nouvelle: Math.random() }])

  return (
    <div className="mt-3 border-t border-border pt-3" data-testid={`attribution-equipe-${equipe.id}`}>
      <Label className="mb-1 block">Attribution des leads</Label>
      <label className="mb-2 flex items-center gap-2 text-sm text-foreground">
        <Switch checked={!!equipe.confirmation_responsable} disabled={busy}
                aria-label={`Le responsable confirme chaque lead — ${equipe.nom}`}
                onCheckedChange={(v) => onSaveEquipe(equipe, { confirmation_responsable: v })} />
        Le responsable confirme chaque lead
      </label>
      {equipe.confirmation_responsable && (
        <>
          <div className="mb-2 max-w-xs">
            <Label htmlFor={`delai-attr-${equipe.id}`}>
              Délai avant attribution automatique (minutes ouvrées)
            </Label>
            <Input id={`delai-attr-${equipe.id}`} type="number" step="any" min="0"
                   key={equipe.delai_attribution_minutes}
                   defaultValue={equipe.delai_attribution_minutes ?? ''}
                   onBlur={(e) => {
                     const v = e.target.value
                     if (v !== '' && Number(v) !== equipe.delai_attribution_minutes) {
                       onSaveEquipe(equipe, { delai_attribution_minutes: Math.round(Number(v)) })
                     }
                   }} />
          </div>
          <Label className="mb-1 block">Règles de proposition</Label>
          <p className="mb-2 text-[11.5px] text-muted-foreground">
            La première règle qui correspond propose son membre ; sinon rotation équilibrée.
          </p>
          {erreur && <p role="alert" className="mb-2 text-xs text-destructive">{erreur}</p>}
          {regles.map((r, i) => (
            <LigneRegle key={r.id ?? r._nouvelle} regle={r} membres={membres}
                        canaux={canaux} typesClient={typesClient} busy={busy}
                        onSave={(x) => enregistrer(x, i)}
                        onDelete={() => (r.id
                          ? agir(crmApi.deleteRegleAttribution(r.id), 'La suppression de la règle a échoué.')
                          : setRegles((l) => l.filter((x) => x !== r)))}
                        onMove={{
                          haut: i > 0 && r.id ? () => deplacer(i, -1) : null,
                          bas: i < regles.length - 1 && r.id ? () => deplacer(i, 1) : null,
                        }} />
          ))}
          <Button type="button" variant="outline" size="sm" onClick={ajouter}>
            <Plus className="size-4" aria-hidden="true" /> Ajouter une règle
          </Button>
        </>
      )}
    </div>
  )
}
