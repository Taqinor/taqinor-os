import { Plus, Trash2 } from 'lucide-react'
import {
  Button, Input, Checkbox, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem,
} from '../../ui'
import { champVisible, champsFormulaireManquants } from './workflow'

/* ============================================================================
   NTWFL12 -- Rendu GENERIQUE d'un formulaire dynamique (FormulaireDefinition,
   backend) : affiche avant qu'un utilisateur puisse approuver une etape qui
   en exige un (voir core.workflow._formulaire_incomplet, meme regle de
   visibilite/completude que ce composant).
   ----------------------------------------------------------------------------
   `schema` : liste ordonnee de champs {nom, type, requis, options?, repetable?}
   (type='section' + repetable=true => N occurrences, une LISTE de sous-objets
   sous `valeurs[section.nom]`).
   `champsConditionnels` : {nom: {visible_si: <condition core.rules>}}.
   `valeurs` : reponses actuelles ({champ: valeur}). `onChange(nom, valeur)`.
   ========================================================================== */

function ChampSimple({ champ, valeur, onChange }) {
  const commun = {
    value: valeur ?? (champ.type === 'booleen' ? false : ''),
    'data-testid': `df-champ-${champ.nom}`,
  }

  if (champ.type === 'booleen') {
    return (
      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={!!valeur}
          onCheckedChange={(v) => onChange(champ.nom, !!v)}
          data-testid={`df-champ-${champ.nom}`}
        />
        {champ.nom}
        {champ.requis && <span className="text-destructive"> *</span>}
      </label>
    )
  }

  if (champ.type === 'choix') {
    return (
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {champ.nom}{champ.requis && <span className="text-destructive"> *</span>}
        </label>
        <Select value={valeur || ''} onValueChange={(v) => onChange(champ.nom, v)}>
          <SelectTrigger data-testid={`df-champ-${champ.nom}`}><SelectValue /></SelectTrigger>
          <SelectContent>
            {(champ.options || []).map((opt) => (
              <SelectItem key={opt} value={opt}>{opt}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    )
  }

  const type = champ.type === 'nombre' ? 'number' : (champ.type === 'date' ? 'date' : 'text')
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted-foreground">
        {champ.nom}{champ.requis && <span className="text-destructive"> *</span>}
      </label>
      <Input
        {...commun}
        type={type}
        onChange={(e) => onChange(champ.nom, e.target.value)}
      />
    </div>
  )
}

function SectionRepetable({ champ, occurrences, onChange }) {
  const lignes = Array.isArray(occurrences) ? occurrences : []

  function majLigne(index, patch) {
    const next = lignes.map((l, i) => (i === index ? { ...l, ...patch } : l))
    onChange(champ.nom, next)
  }

  function ajouterLigne() {
    onChange(champ.nom, [...lignes, {}])
  }

  function retirerLigne(index) {
    onChange(champ.nom, lignes.filter((_, i) => i !== index))
  }

  return (
    <div className="rounded-md border p-2" data-testid={`df-section-${champ.nom}`}>
      <p className="mb-2 text-xs font-medium text-muted-foreground">{champ.nom}</p>
      {lignes.map((ligne, index) => (
        // Pas d'id stable avant sauvegarde ; les lignes ne sont jamais
        // réordonnées entre elles (seulement ajoutées/retirées en fin de
        // liste) — l'index reste un identifiant React stable ici.
        <div
          key={index}
          className="mb-2 flex items-center gap-2"
          data-testid={`df-section-${champ.nom}-ligne-${index}`}
        >
          <Input
            value={ligne.valeur || ''}
            onChange={(e) => majLigne(index, { valeur: e.target.value })}
            data-testid={`df-section-${champ.nom}-valeur-${index}`}
          />
          <Button variant="ghost" size="sm" onClick={() => retirerLigne(index)}>
            <Trash2 />
          </Button>
        </div>
      ))}
      <Button variant="secondary" size="sm" onClick={ajouterLigne} data-testid={`df-section-${champ.nom}-ajouter`}>
        <Plus /> Ajouter une ligne
      </Button>
    </div>
  )
}

export default function DynamicForm({ schema, champsConditionnels, valeurs, onChange }) {
  const champs = Array.isArray(schema) ? schema : []
  const v = valeurs || {}
  const manquants = champsFormulaireManquants(champs, champsConditionnels, v)

  return (
    <div className="flex flex-col gap-3" data-testid="dynamic-form">
      {champs.map((champ) => {
        if (!champVisible(champ.nom, champsConditionnels, v)) return null
        if (champ.type === 'section' && champ.repetable) {
          return (
            <SectionRepetable
              key={champ.nom}
              champ={champ}
              occurrences={v[champ.nom]}
              onChange={onChange}
            />
          )
        }
        return (
          <ChampSimple
            key={champ.nom}
            champ={champ}
            valeur={v[champ.nom]}
            onChange={onChange}
          />
        )
      })}
      {manquants.length > 0 && (
        <p className="text-xs text-destructive" data-testid="df-champs-manquants">
          Champs requis manquants : {manquants.join(', ')}
        </p>
      )}
    </div>
  )
}
