// WIR114 (ZFSM3) — Modèles de fiche d'intervention : champs de compte-rendu
// personnalisés par type d'intervention.
//
// Un modèle (`FicheInterventionTemplate`) cible un `type_intervention` et porte
// une liste ordonnée de champs (`FicheInterventionChamp` : case / texte /
// nombre / mesure, `obligatoire` gate la clôture). Le modèle actif du type
// s'applique aux nouvelles interventions de ce type. CRUD minimal (Paramètres),
// gabarit Card comme les autres sections. Les modèles protégés (système) ne se
// suppriment pas.
import { useEffect, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import {
  Card, CardContent, Input, Badge, IconButton, Button, Spinner, Checkbox,
} from '../../ui'
import { SectionTitle, Field } from './peComponents'
import installationsApi from '../../api/installationsApi'

const TYPE_CHAMPS = [
  ['case', 'Case à cocher'], ['texte', 'Texte court'],
  ['nombre', 'Nombre'], ['mesure', 'Mesure (avec unité)'],
]

export default function FicheInterventionModelesSection() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [newNom, setNewNom] = useState('')
  const [newType, setNewType] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    installationsApi.getFicheTemplates()
      .then((r) => setTemplates(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les modèles de fiche.'))
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const addTemplate = async () => {
    if (!newNom.trim() || !newType.trim()) {
      setError('Nom et type d\'intervention sont requis.')
      return
    }
    try {
      await installationsApi.saveFicheTemplate(null, {
        nom: newNom.trim(), type_intervention: newType.trim(), actif: true,
      })
      setNewNom(''); setNewType(''); setError(null)
      load()
    } catch (e) {
      setError(e?.response?.data?.detail || 'La création du modèle a échoué.')
    }
  }

  const delTemplate = async (tpl) => {
    if (!window.confirm(`Supprimer le modèle « ${tpl.nom} » ?`)) return
    setBusyId(tpl.id)
    try {
      await installationsApi.deleteFicheTemplate(tpl.id)
      load()
    } catch (e) {
      setError(e?.response?.data?.detail || 'Suppression impossible.')
    } finally { setBusyId(null) }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Modèles de fiche d'intervention" icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="15" x2="15" y2="15"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Champs de compte-rendu personnalisés par type d'intervention. Le
          modèle actif d'un type s'applique aux nouvelles interventions de ce
          type ; un champ obligatoire non renseigné bloque la clôture.
        </p>

        {loading && (
          <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
            <Spinner className="size-3.5 text-primary" /> Chargement…
          </div>
        )}
        {error && <p className="form-error mb-2" role="alert">{error}</p>}

        {!loading && templates.length === 0 && (
          <p className="mb-3 text-xs text-muted-foreground">Aucun modèle de fiche configuré.</p>
        )}

        {!loading && templates.map((tpl) => (
          <TemplateBlock key={tpl.id} template={tpl} busy={busyId === tpl.id}
            onDelete={() => delTemplate(tpl)} onChanged={load} />
        ))}

        <div className="mt-2 flex flex-wrap gap-1.5">
          <Input className="flex-[2_1_160px]" placeholder="Nom du modèle" value={newNom}
            onChange={(e) => setNewNom(e.target.value)} />
          <Input className="flex-1" placeholder="Type d'intervention" value={newType}
            onChange={(e) => setNewType(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTemplate() } }} />
          <Button type="button" onClick={addTemplate}><Plus className="size-4" aria-hidden="true" /></Button>
        </div>
      </CardContent>
    </Card>
  )
}

function TemplateBlock({ template, busy, onDelete, onChanged }) {
  const [cle, setCle] = useState('')
  const [libelle, setLibelle] = useState('')
  const [typeChamp, setTypeChamp] = useState('texte')
  const [unite, setUnite] = useState('')
  /* WIR266 — `obligatoire` (le gate de clôture ZFSM1 : un champ obligatoire non
     renseigné BLOQUE la clôture de l'intervention) était rendu en badge sur les
     champs existants… et n'était réglable NULLE PART. Le formulaire d'ajout ne
     l'envoyait pas (donc tout champ naissait facultatif) et aucune bascule
     n'existait ensuite : la gate ZFSM1 était en pratique inutilisable depuis
     l'ERP. Aucun changement backend — `saveFicheChamp` accepte déjà le champ. */
  const [obligatoire, setObligatoire] = useState(false)
  const [error, setError] = useState(null)
  const [bascule, setBascule] = useState(null) // id du champ en cours de bascule
  const champs = template.champs ?? []

  const addChamp = async () => {
    if (!cle.trim() || !libelle.trim()) { setError('Clé et libellé requis.'); return }
    try {
      await installationsApi.saveFicheChamp(null, {
        template: template.id, cle: cle.trim(), libelle: libelle.trim(),
        type_champ: typeChamp, unite: typeChamp === 'mesure' ? (unite || '') : '',
        ordre: champs.length,
        obligatoire,
      })
      setCle(''); setLibelle(''); setUnite(''); setObligatoire(false); setError(null)
      onChanged?.()
    } catch (e) {
      setError(e?.response?.data?.detail || "Ajout du champ impossible.")
    }
  }

  // WIR266 — bascule d'un champ EXISTANT (PATCH partiel : rien d'autre n'est
  // renvoyé, donc aucun risque d'écraser libellé/type/unité au passage).
  const basculerObligatoire = async (champ) => {
    setBascule(champ.id)
    try {
      await installationsApi.saveFicheChamp(champ.id, { obligatoire: !champ.obligatoire })
      setError(null)
      onChanged?.()
    } catch (e) {
      setError(e?.response?.data?.detail || "Modification du champ impossible.")
    } finally {
      setBascule(null)
    }
  }

  const delChamp = async (champ) => {
    await installationsApi.deleteFicheChamp(champ.id).catch(() => {})
    onChanged?.()
  }

  return (
    <div className={['mb-3 rounded-lg border border-border p-3', template.actif ? '' : 'opacity-60'].join(' ')}
      data-testid={`fiche-template-${template.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <span className="font-medium text-sm">{template.nom}</span>
        <Badge tone="neutral">{template.type_intervention}</Badge>
        {template.protege
          ? <Badge tone="info">système</Badge>
          : (
            <IconButton size="md" variant="outline" label="Supprimer le modèle"
              className="ml-auto text-destructive hover:text-destructive"
              disabled={busy} onClick={onDelete}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          )}
      </div>

      {champs.length > 0 && (
        <ul className="mb-2 flex flex-col gap-1">
          {champs.map((c) => (
            <li key={c.id} className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{c.libelle}</span>
              <Badge tone="neutral">{c.type_champ}{c.unite ? ` (${c.unite})` : ''}</Badge>
              {c.obligatoire && <Badge tone="warning">obligatoire</Badge>}
              {/* WIR266 — la bascule qui manquait : le gate de clôture ZFSM1
                  devient réglable après coup, sans recréer le champ. */}
              <label className="flex items-center gap-1">
                <Checkbox
                  data-testid={`champ-obligatoire-${c.id}`}
                  checked={!!c.obligatoire}
                  disabled={bascule === c.id}
                  onCheckedChange={() => basculerObligatoire(c)}
                  aria-label={`Rendre « ${c.libelle} » obligatoire (bloque la clôture)`}
                />
                <span>Obligatoire</span>
              </label>
              <IconButton size="sm" variant="ghost" label="Retirer le champ"
                className="ml-auto text-destructive hover:text-destructive"
                onClick={() => delChamp(c)}>
                <Trash2 className="size-3.5" aria-hidden="true" />
              </IconButton>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-1.5">
        <div className="flex-1">
          <Field label="Clé" htmlFor={`ch-cle-${template.id}`}>
            <Input id={`ch-cle-${template.id}`} value={cle} onChange={(e) => setCle(e.target.value)} placeholder="ex. tension_v" />
          </Field>
        </div>
        <div className="flex-[2_1_140px]">
          <Field label="Libellé" htmlFor={`ch-lib-${template.id}`}>
            <Input id={`ch-lib-${template.id}`} value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="ex. Tension mesurée" />
          </Field>
        </div>
        <Field label="Type" htmlFor={`ch-type-${template.id}`}>
          <select id={`ch-type-${template.id}`} className="form-control" value={typeChamp} onChange={(e) => setTypeChamp(e.target.value)}>
            {TYPE_CHAMPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        {typeChamp === 'mesure' && (
          <Field label="Unité" htmlFor={`ch-unite-${template.id}`}>
            <Input id={`ch-unite-${template.id}`} value={unite} onChange={(e) => setUnite(e.target.value)} placeholder="V, A, °C…" />
          </Field>
        )}
        {/* WIR266 — le formulaire d'ajout n'envoyait PAS `obligatoire` : tout
            champ naissait facultatif, gate ZFSM1 comprise. */}
        <label className="flex items-center gap-1.5 pb-1 text-sm">
          <Checkbox
            data-testid={`nouveau-champ-obligatoire-${template.id}`}
            checked={obligatoire}
            onCheckedChange={(v) => setObligatoire(!!v)}
            aria-label="Obligatoire (bloque la clôture)"
          />
          <span>Obligatoire (bloque la clôture)</span>
        </label>
        <Button type="button" size="sm" onClick={addChamp}>
          <Plus className="size-4" aria-hidden="true" /> Champ
        </Button>
      </div>
      {error && <p className="form-error mt-1" role="alert">{error}</p>}
    </div>
  )
}
