// VT6 — Formulaire de mesures par catégorie du wizard visite. RÈGLE MAISON
// ABSOLUE : le formulaire n'avale/ne rejette JAMAIS un nombre tapé
// (`noValidate` + `step="any"` sur tout input numérique — jamais de `min`/
// `max` qui bloquerait la saisie). Les erreurs sont CELLES DU SERVEUR
// (`PATCH .../mesures/` → 400 `{erreurs:{champ:message}}`), affichées SOUS le
// champ fautif — jamais une validation client qui pourrait diverger.
//
// CIQ609 — gabarit `ci` (site professionnel) : mesures en LISTE (zones de
// toiture, trajets de câbles…) ajoutables et supprimables, et « non relevé »
// + motif sous chaque mesure qui peut l'être. La complétude vient TOUJOURS du
// serveur : ce formulaire ne décide jamais qu'une mesure est « suffisante ».
import { useState } from 'react'
import { enregistrerMesures } from '../../features/visites/visitesOffline'
import { Button, Card, Input, Label, Checkbox, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../ui'
import { toast } from '../../ui/confirm'
import {
  GABARIT_CI, MOTIFS_NON_RELEVE, schemaMesures, cleNonReleve, formDepuisValeurs,
  payloadDepuisForm, nouvelleLigne, nonRelevesDeCategorie,
} from './visiteHelpers'

// Un champ scalaire (texte, nombre, case, tri-état, liste de choix, date,
// pièce). `id` est unique sur la page ; `erreur` est le message serveur.
function ChampScalaire({ champ, id, valeur, onChange, disabled, erreur }) {
  if (champ.type === 'bool') {
    return (
      <label htmlFor={id} className="flex min-h-11 items-center gap-2 text-sm">
        <Checkbox
          id={id}
          checked={Boolean(valeur)}
          disabled={disabled}
          onCheckedChange={(c) => onChange(c === true)}
        />
        {champ.label}
      </label>
    )
  }
  if (champ.type === 'tribool') {
    return (
      <div>
        <Label htmlFor={id}>{champ.label}</Label>
        <Select value={valeur || undefined} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger id={id}><SelectValue placeholder="— (pas encore relevé)" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="oui">Oui</SelectItem>
            <SelectItem value="non">Non</SelectItem>
          </SelectContent>
        </Select>
        {erreur && <p role="alert" className="mt-1 text-xs text-destructive">{erreur}</p>}
      </div>
    )
  }
  if (champ.type === 'select') {
    return (
      <div>
        <Label htmlFor={id}>{champ.label}</Label>
        <Select value={valeur || undefined} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger id={id}><SelectValue placeholder="—" /></SelectTrigger>
          <SelectContent>
            {champ.options.map((o) => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {erreur && <p role="alert" className="mt-1 text-xs text-destructive">{erreur}</p>}
      </div>
    )
  }
  const nombre = champ.type === 'number'
  return (
    <div>
      <Label htmlFor={id}>
        {champ.label}{champ.unite ? ` (${champ.unite})` : ''}
      </Label>
      <Input
        id={id}
        type={nombre ? 'number' : champ.type === 'date' ? 'date' : 'text'}
        step={nombre ? 'any' : undefined}
        inputMode={nombre ? 'decimal' : undefined}
        value={valeur}
        disabled={disabled}
        aria-invalid={erreur ? 'true' : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {erreur && <p role="alert" className="mt-1 text-xs text-destructive">{erreur}</p>}
    </div>
  )
}

// CIQ601 — « non relevé » + motif sous une mesure. L'erreur du serveur
// (motif manquant ou inconnu) s'affiche sous la case, jamais une validation
// locale.
function NonReleve({ id, motif, onChange, disabled, erreur }) {
  const coche = motif !== undefined
  return (
    <div className="mt-1">
      <label htmlFor={`${id}-nr`} className="flex min-h-9 items-center gap-2 text-xs text-muted-foreground">
        <Checkbox
          id={`${id}-nr`}
          checked={coche}
          disabled={disabled}
          onCheckedChange={(c) => onChange(c === true ? '' : undefined)}
        />
        Non relevé
      </label>
      {coche && (
        <div>
          <Label htmlFor={`${id}-motif`} className="sr-only">Motif — non relevé</Label>
          <Select value={motif || undefined} onValueChange={onChange} disabled={disabled}>
            <SelectTrigger id={`${id}-motif`}><SelectValue placeholder="Motif (obligatoire)" /></SelectTrigger>
            <SelectContent>
              {MOTIFS_NON_RELEVE.map((m) => (
                <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {erreur && <p role="alert" className="mt-1 text-xs text-destructive">{erreur}</p>}
    </div>
  )
}

export default function VisiteMesuresForm({
  visiteId, categorie, libelle, valeurs, onSaved, lectureSeule, gabarit, nonReleves,
}) {
  const schema = schemaMesures(categorie, gabarit)
  const ci = gabarit === GABARIT_CI
  const [form, setForm] = useState(() => formDepuisValeurs(schema, valeurs))
  const [nr, setNr] = useState(() => (ci ? nonRelevesDeCategorie(nonReleves, categorie) : {}))
  const [erreurs, setErreurs] = useState({})
  const [saving, setSaving] = useState(false)

  if (schema.length === 0) return null

  const effacerErreur = (cle) => setErreurs((prev) => (prev[cle] ? { ...prev, [cle]: undefined } : prev))

  const setChamp = (key, v) => {
    setForm((prev) => ({ ...prev, [key]: v }))
    effacerErreur(key)
  }

  // Cocher « non relevé » vide la valeur (une mesure ne peut pas être à la fois
  // relevée et non relevée) ; décocher ne ressaisit rien.
  const setNonReleve = (cle, motif, viderChamp) => {
    setNr((prev) => {
      const suite = { ...prev }
      if (motif === undefined) delete suite[cle]
      else suite[cle] = motif
      return suite
    })
    if (motif !== undefined && viderChamp) viderChamp()
    effacerErreur(`_non_releves.${cle}`)
  }

  const setLigne = (listeKey, index, sousKey, v) => {
    setForm((prev) => {
      const lignes = prev[listeKey].map((l, i) => (i === index ? { ...l, [sousKey]: v } : l))
      return { ...prev, [listeKey]: lignes }
    })
    effacerErreur(listeKey)
  }

  const setSousObjet = (listeKey, index, objetKey, sousKey, v) => {
    setForm((prev) => {
      const lignes = prev[listeKey].map((l, i) => (
        i === index ? { ...l, [objetKey]: { ...l[objetKey], [sousKey]: v } } : l))
      return { ...prev, [listeKey]: lignes }
    })
  }

  const ajouterLigne = (champ) => {
    setForm((prev) => ({ ...prev, [champ.key]: [...prev[champ.key], nouvelleLigne(champ, prev[champ.key])] }))
  }

  const supprimerLigne = (champ, index) => {
    setForm((prev) => ({ ...prev, [champ.key]: prev[champ.key].filter((_, i) => i !== index) }))
  }

  const payload = () => {
    const out = payloadDepuisForm(schema, form)
    if (ci) {
      // Les états « non relevé » partent TELS QUELS (motif vide compris : le
      // serveur répond « Motif requis »).
      out._non_releves = { ...nr }
    }
    return out
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setErreurs({})
    try {
      // VTA10 — même appel, mais via le branchement offline : hors réseau
      // l'op part dans la file de module `visites` et on le DIT.
      const res = await enregistrerMesures(visiteId, categorie, payload())
      if (res.queued) {
        toast.success('Mesures mises en file — elles partiront au retour du réseau.')
      } else {
        onSaved?.(res.data?.data)
        toast.success('Mesures enregistrées.')
      }
    } catch (err) {
      const data = err?.response?.data
      if (data?.erreurs) setErreurs(data.erreurs)
      else toast.error('Enregistrement des mesures impossible.')
    } finally {
      setSaving(false)
    }
  }

  const idDe = (...morceaux) => `visite-mesure-${categorie}-${morceaux.join('-')}`

  const rendreChampTop = (champ) => {
    const id = idDe(champ.key)
    const cle = cleNonReleve(null, null, champ.key)
    const motif = nr[cle]
    return (
      <div key={champ.key}>
        <ChampScalaire
          champ={champ} id={id} valeur={form[champ.key]}
          disabled={lectureSeule || motif !== undefined}
          erreur={erreurs[champ.key]}
          onChange={(v) => setChamp(champ.key, v)}
        />
        {ci && champ.type !== 'bool' && (
          <NonReleve
            id={id} motif={motif} disabled={lectureSeule}
            erreur={erreurs[`_non_releves.${cle}`]}
            onChange={(m) => setNonReleve(cle, m, () => setChamp(champ.key, ''))}
          />
        )}
      </div>
    )
  }

  const rendreListe = (champ) => {
    const lignes = form[champ.key] ?? []
    return (
      <fieldset key={champ.key} className="space-y-2 sm:col-span-2" data-testid={`visite-liste-${champ.key}`}>
        <legend className="text-sm font-medium">{champ.label}</legend>
        {lignes.length === 0 && (
          <p className="text-xs text-muted-foreground">Aucun élément saisi.</p>
        )}
        {lignes.map((ligne, index) => (
          <Card key={ligne.id || index} className="space-y-2 p-3" data-testid={`visite-ligne-${champ.key}-${ligne.id || index}`}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-muted-foreground">{champ.itemLabel} {index + 1}</p>
              {!lectureSeule && (
                <Button
                  type="button" size="sm" variant="ghost"
                  aria-label={`Supprimer ${champ.itemLabel.toLowerCase()} ${index + 1}`}
                  onClick={() => supprimerLigne(champ, index)}
                >
                  Supprimer
                </Button>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {champ.forme.map((sous) => {
                const base = [champ.key, ligne.id || index]
                if (sous.type === 'objet') {
                  return (
                    <fieldset key={sous.key} className="space-y-2 sm:col-span-2">
                      <legend className="text-xs font-medium text-muted-foreground">{sous.label}</legend>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        {sous.forme.map((feuille) => (
                          <ChampScalaire
                            key={feuille.key}
                            champ={{ ...feuille, label: `${sous.label} — ${feuille.label}` }}
                            id={idDe(...base, sous.key, feuille.key)}
                            valeur={ligne[sous.key]?.[feuille.key] ?? ''}
                            disabled={lectureSeule}
                            onChange={(v) => setSousObjet(champ.key, index, sous.key, feuille.key, v)}
                          />
                        ))}
                      </div>
                    </fieldset>
                  )
                }
                const id = idDe(...base, sous.key)
                const cle = cleNonReleve(champ.key, champ.id ? ligne.id : null, sous.key)
                const motif = nr[cle]
                return (
                  <div key={sous.key}>
                    <ChampScalaire
                      champ={sous} id={id} valeur={ligne[sous.key]}
                      disabled={lectureSeule || motif !== undefined}
                      onChange={(v) => setLigne(champ.key, index, sous.key, v)}
                    />
                    {ci && sous.nonReleve && (
                      <NonReleve
                        id={id} motif={motif} disabled={lectureSeule}
                        erreur={erreurs[`_non_releves.${cle}`]}
                        onChange={(m) => setNonReleve(cle, m, () => setLigne(champ.key, index, sous.key, ''))}
                      />
                    )}
                  </div>
                )
              })}
            </div>
          </Card>
        ))}
        {!lectureSeule && (
          <Button type="button" size="sm" variant="outline" onClick={() => ajouterLigne(champ)}>
            {champ.addLabel}
          </Button>
        )}
        {erreurs[champ.key] && (
          <p role="alert" className="mt-1 text-xs text-destructive">{erreurs[champ.key]}</p>
        )}
      </fieldset>
    )
  }

  return (
    <Card className="p-3" data-testid={`visite-mesures-${categorie}`}>
      <form noValidate onSubmit={submit} className="space-y-3">
        <p className="text-sm font-medium">Mesures — {libelle}</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {schema.map((champ) => (champ.type === 'list' ? rendreListe(champ) : rendreChampTop(champ)))}
        </div>
        {!lectureSeule && (
          <Button type="submit" size="sm" disabled={saving}>Enregistrer les mesures</Button>
        )}
      </form>
    </Card>
  )
}
