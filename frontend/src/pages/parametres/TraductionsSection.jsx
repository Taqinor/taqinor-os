// N94 — onglet « Traductions » de la page Paramètres.
//
// Permet de RELIRE et AJUSTER les chaînes de l'interface par langue (FR/EN/AR)
// SANS changement de code. S'appuie sur le cadre i18n N93 : la liste des clés
// est dérivée du catalogue FR (source des identifiants), chaque valeur affichée
// est le catalogue statique de la langue, SURCHARGÉ par l'éventuelle valeur
// enregistrée pour la société. Enregistrer écrit des surcharges via l'API ;
// « Réinitialiser » supprime la surcharge (retour au catalogue statique).
//
// Section autonome (comme Statuts/Documents) : elle charge ses propres
// surcharges, gère son état d'édition, s'enregistre via l'endpoint bulk, puis
// rafraîchit les surcharges du provider i18n (effet immédiat, sans rechargement).
import { useEffect, useMemo, useState } from 'react'
import { RotateCcw, Save, CheckCircle2, Search, X } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { CATALOGS, LOCALES, useI18n } from '../../i18n'
import { Card, CardContent, Input, IconButton, Button, Spinner, Badge } from '../../ui'
import { toast } from '../../ui/confirm'

// Libellés des colonnes de langue (ordre d'affichage = ordre du cadre N93).
const LOCALE_LABELS = { fr: 'Français', en: 'English', ar: 'العربية' }

// Toutes les clés i18n connues = clés du catalogue FR (source des identifiants).
// Triées : elles arrivent déjà groupées par espace de noms dans le fichier.
const ALL_KEYS = Object.keys(CATALOGS.fr).sort()

// Espace de noms d'une clé = segment avant le premier point (ex. `nav`,
// `title`, `common`). Sert de titre de groupe.
function namespaceOf(key) {
  const i = key.indexOf('.')
  return i === -1 ? key : key.slice(0, i)
}

// Groupe les clés par espace de noms → [{ ns, keys: [...] }, ...] (ordre stable).
function groupByNamespace(keys) {
  const map = new Map()
  for (const k of keys) {
    const ns = namespaceOf(k)
    if (!map.has(ns)) map.set(ns, [])
    map.get(ns).push(k)
  }
  return [...map.entries()].map(([ns, ks]) => ({ ns, keys: ks }))
}

// Valeur statique du catalogue pour (locale, key), repli FR puis clé — miroir
// exact de la chaîne de repli N93 sans surcharge.
function staticValue(locale, key) {
  const cat = CATALOGS[locale] || CATALOGS.fr
  return cat[key] ?? CATALOGS.fr[key] ?? key
}

export default function TraductionsSection() {
  const { setOverrides } = useI18n()
  // overrides = { locale: { key: value } } enregistrées pour la société.
  const [overrides, setOverridesLocal] = useState(null) // null = chargement
  // drafts = { `${locale}:${key}`: value } édités mais pas encore enregistrés.
  const [drafts, setDrafts] = useState({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => {
    parametresApi.getTranslationOverrides()
      .then(r => setOverridesLocal(r.data?.overrides ?? {}))
      .catch(() => setOverridesLocal({}))
  }, [])

  // Valeur affichée d'une cellule : brouillon > surcharge enregistrée > statique.
  const cellValue = (locale, key) => {
    const dk = `${locale}:${key}`
    if (Object.prototype.hasOwnProperty.call(drafts, dk)) return drafts[dk]
    const ov = overrides?.[locale]
    if (ov && Object.prototype.hasOwnProperty.call(ov, key)) return ov[key]
    return staticValue(locale, key)
  }

  // Une cellule est « personnalisée » si une surcharge est enregistrée pour elle.
  const isOverridden = (locale, key) =>
    !!(overrides?.[locale] && Object.prototype.hasOwnProperty.call(overrides[locale], key))

  const setCell = (locale, key, value) =>
    setDrafts(d => ({ ...d, [`${locale}:${key}`]: value }))

  // Réinitialiser une cellule = supprimer la surcharge (valeur vide au bulk) et
  // reposer le brouillon sur la valeur statique.
  const resetCell = (locale, key) =>
    setDrafts(d => ({ ...d, [`${locale}:${key}`]: '' }))

  // Filtre : clé OU l'une des valeurs (statiques/surcharges) contient la requête.
  const filteredGroups = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const keys = !needle ? ALL_KEYS : ALL_KEYS.filter(k =>
      k.toLowerCase().includes(needle)
      || LOCALES.some(loc => String(cellValue(loc, k)).toLowerCase().includes(needle)))
    return groupByNamespace(keys)
    // cellValue dépend de drafts/overrides ; on recalcule quand ils changent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, drafts, overrides])

  const dirtyCount = Object.keys(drafts).length

  const save = async () => {
    if (dirtyCount === 0) return
    setSaving(true)
    try {
      const items = Object.entries(drafts).map(([dk, value]) => {
        const idx = dk.indexOf(':')
        return { locale: dk.slice(0, idx), key: dk.slice(idx + 1), value }
      })
      const res = await parametresApi.saveTranslationOverrides(items)
      const fresh = res.data?.overrides ?? {}
      setOverridesLocal(fresh)
      setDrafts({})
      // Effet immédiat : le provider i18n adopte les nouvelles surcharges.
      setOverrides(fresh)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-muted/30 px-4 py-3 text-[12.5px] leading-relaxed text-muted-foreground">
        Relisez et ajustez les libellés de l’interface par langue
        (<strong>Français</strong>, <strong>English</strong>,
        {' '}<strong>العربية</strong>) sans changement de code. Une valeur laissée
        vide ou <em>réinitialisée</em> revient au texte livré par défaut.
      </div>

      {/* Recherche (clé ou valeur) */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          type="search" value={q} onChange={e => setQ(e.target.value)}
          placeholder="Rechercher une clé ou un texte (ex. « nav », « Enregistrer »)…"
          aria-label="Rechercher une traduction"
          className="pl-9 pr-9"
        />
        {q && (
          <button type="button" onClick={() => setQ('')}
                  aria-label="Effacer la recherche"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
            <X className="size-4" aria-hidden="true" />
          </button>
        )}
      </div>

      {overrides === null ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </div>
      ) : (
        <>
          {filteredGroups.length === 0 && (
            <p className="px-1 py-4 text-sm text-muted-foreground">
              Aucune clé ne correspond à « {q} ».
            </p>
          )}
          {filteredGroups.map(({ ns, keys }) => (
            <Card key={ns}>
              <CardContent className="pt-4 sm:pt-5">
                <div className="mb-3 flex items-center gap-2">
                  <span className="font-mono text-[12px] font-semibold text-foreground">{ns}.*</span>
                  <Badge tone="neutral">{keys.length}</Badge>
                </div>
                <div className="flex flex-col gap-2.5">
                  {keys.map(key => (
                    <div key={key} className="rounded-lg border border-border p-2.5">
                      <div className="mb-1.5 flex items-center gap-2">
                        <span className="font-mono text-[11px] text-muted-foreground">{key}</span>
                      </div>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                        {LOCALES.map(loc => (
                          <div key={loc}>
                            <div className="mb-0.5 flex items-center justify-between">
                              <span className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                                {LOCALE_LABELS[loc]}
                              </span>
                              {isOverridden(loc, key) && (
                                <span className="flex items-center gap-1">
                                  <Badge tone="info">modifié</Badge>
                                  <IconButton size="sm" variant="ghost"
                                    label={`Réinitialiser ${loc} / ${key}`}
                                    title="Rétablir le texte par défaut"
                                    onClick={() => resetCell(loc, key)}>
                                    <RotateCcw className="size-3.5" aria-hidden="true" />
                                  </IconButton>
                                </span>
                              )}
                            </div>
                            <Input
                              value={cellValue(loc, key)}
                              dir={loc === 'ar' ? 'rtl' : 'ltr'}
                              aria-label={`Traduction ${LOCALE_LABELS[loc]} de ${key}`}
                              onChange={e => setCell(loc, key, e.target.value)}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Barre d'enregistrement (collante en bas de la section) */}
          <div className="sticky bottom-0 z-10 -mx-1 flex items-center gap-3 border-t border-border bg-background/95 px-1 py-3 backdrop-blur">
            <Button type="button" onClick={save} loading={saving}
              disabled={saving || dirtyCount === 0}
              variant={saved ? 'success' : 'default'}>
              {saved
                ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
                : <><Save className="size-4" aria-hidden="true" /> Enregistrer{dirtyCount ? ` (${dirtyCount})` : ''}</>}
            </Button>
            {dirtyCount > 0 && (
              <span className="text-xs text-muted-foreground">
                {dirtyCount} modification{dirtyCount > 1 ? 's' : ''} non enregistrée{dirtyCount > 1 ? 's' : ''}.
              </span>
            )}
          </div>
        </>
      )}
    </>
  )
}
