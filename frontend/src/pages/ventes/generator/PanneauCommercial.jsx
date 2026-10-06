// QJR101 — PANNEAU DE MARCHÉ : COMMERCIAL.
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. Le commercial ajoute au socle industriel la
// CATÉGORIE (hôtel, bureau…) et ses questions par archétype (CIQ125/CIQ131 :
// elles partent au moteur serveur C&I) ; il n'a pas de pompage.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale ; l'ex-module de stratégie `quote/marches/commercial.js`,
// devenu du code mort — aucun autre export que `cle` n'avait de consommateur
// de production — a été supprimé) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend, à la place exacte qu'occupait la carte d'origine.
//
// CIQ125/CIQ126 — UNE seule saisie de consommation : la carte C&I partagée
// (`CarteProfilCi` : profil déclaré + résultat du moteur serveur) ; ce panneau
// y ajoute sa catégorie commerciale en `children`. Les factures hiver/été et
// la facture réelle résidentielles ne sont plus montées ici.
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props, tout le calcul
// reste dans l'écran porteur (et au serveur). Chaque `<input type="number">`
// garde `step="any"` (règle fondateur : aucun champ ne snappe jamais) et le
// `noValidate` est resté sur le formulaire porteur.
import {
  Input, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import {
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS,
} from '../../../features/ventes/solar'
// CIQ125 — la carte C&I partagée (profil déclaré + résultat du moteur serveur).
import { CarteProfilCi } from './BlocEtudeReseau'

// QJR241 — clé de marché de ce panneau (ex-`cle` de quote/marches/
// commercial.js, module supprimé faute de consommateur de production).
const CLE = 'commercial'

// QJR575 — catégorie « Non précisée » : la valeur par défaut de l'écran (Radix
// refuse value=''), persistée `null` (jamais « hôtel » par défaut) : le moteur
// serveur C&I ne reçoit alors aucune catégorie.
export const CATEGORIE_NON_PRECISEE = 'non_precisee'

// CIQ131 — les HEURES qu'une réponse demande (le moteur serveur les lit dans
// `rythme.reponses_categorie`, `moteur_ci/categories.py`) : saisies à côté
// de la réponse, jamais supposées. `[[début, fin]]` en heures civiles.
const HEURES_PAR_REPONSE = {
  horaires: { cle: 'heures', libelle: "Heures d'ouverture" },
  cuisson_nocturne: { cle: 'heures_cuisson', libelle: 'Heures de cuisson' },
  garde_nuit: { cle: 'heures_garde', libelle: 'Heures de garde' },
}

function HeuresDeLaReponse({ cle, reponses, setReponse }) {
  if (cle === 'fermeture_estivale') {
    if (!reponses.fermeture_estivale) return null
    return (
      <div className="flex gap-2" data-testid="ci-fermeture-estivale">
        <Input type="date" aria-label="Fermeture estivale du" value={reponses.fermeture_du ?? ''}
               onChange={e => setReponse('fermeture_du', e.target.value)} />
        <Input type="date" aria-label="Fermeture estivale au" value={reponses.fermeture_au ?? ''}
               onChange={e => setReponse('fermeture_au', e.target.value)} />
      </div>
    )
  }
  const h = HEURES_PAR_REPONSE[cle]
  if (!h || !reponses[cle]) return null
  const plage = (Array.isArray(reponses[h.cle]) && reponses[h.cle][0]) || ['', '']
  const poser = (i, v) => {
    const suivante = [...plage]
    suivante[i] = v
    setReponse(h.cle, [suivante])
  }
  return (
    <div className="flex items-center gap-2 text-xs" data-testid={`ci-${h.cle}`}>
      <span>{h.libelle}</span>
      <Input type="number" min="0" step="any" aria-label={`${h.libelle} début`}
             value={plage[0] ?? ''} onChange={e => poser(0, e.target.value)} />
      <Input type="number" min="0" step="any" aria-label={`${h.libelle} fin`}
             value={plage[1] ?? ''} onChange={e => poser(1, e.target.value)} />
    </div>
  )
}

// CIQ131 — l'archétype retenu par le moteur (avec sa source, « estimation »
// quand aucun horaire n'est déclaré) et les réponses SANS effet sur le calcul.
function ArchetypeEtSansEffet({ profil }) {
  if (!profil) return null
  const a = profil.archetype
  const sansEffet = profil.reponses_non_consommees || []
  return (
    <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
      {a && (
        <p data-testid="ci-archetype">
          Archétype retenu : <strong>{a.cle}</strong>
          {a.source ? ` — source : ${a.source}` : ''}
          {profil.methode === 'archetype' ? ' (estimation : aucun horaire déclaré)' : ''}
        </p>
      )}
      {sansEffet.length > 0 && (
        <p data-testid="ci-sans-effet">
          Sans effet sur le calcul : {sansEffet.join(', ')}.
        </p>
      )}
    </div>
  )
}

export default function PanneauCommercial({
  marche, errors,
  // ── CIQ125 — profil déclaré C&I + résultat du moteur serveur ──
  profilCi, setChampCi, apercuCi,
  // ── Catégorie commerciale et ses questions (QX44) ──
  categorieCommerciale, setCategorieCommerciale,
  commercialAnswers, setCommercialAnswer,
}) {
  if (marche !== CLE) return null
  return (
    <CarteProfilCi profilCi={profilCi} setChampCi={setChampCi} apercuCi={apercuCi} errors={errors}>
      {/* QX44 — étude commerciale par catégorie */}
      <div className="mt-3.5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Catégorie commerciale</Label>
            <Select value={categorieCommerciale} onValueChange={setCategorieCommerciale}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={CATEGORIE_NON_PRECISEE}>Non précisée</SelectItem>
                {COMMERCIAL_CATEGORIES.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        {(COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || []).length > 0 && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {(COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || []).map(q => (
              <div className="grid gap-1.5" key={q.key}>
                <Label htmlFor={`gen-com-${q.key}`}>{q.label}</Label>
                {q.type === 'number' && (
                  <Input id={`gen-com-${q.key}`} type="number" min="0" step="any"
                         value={commercialAnswers[q.key] ?? ''}
                         onChange={e => setCommercialAnswer(q.key, e.target.value)} />
                )}
                {q.type === 'select' && (
                  <Select value={commercialAnswers[q.key] ?? ''}
                          onValueChange={v => setCommercialAnswer(q.key, v)}>
                    <SelectTrigger id={`gen-com-${q.key}`}><SelectValue placeholder="—" /></SelectTrigger>
                    <SelectContent>
                      {q.options.map(o => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {q.type === 'bool' && (
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input id={`gen-com-${q.key}`} type="checkbox"
                           checked={!!commercialAnswers[q.key]}
                           onChange={e => setCommercialAnswer(q.key, e.target.checked)} />
                    Oui
                  </label>
                )}
                <HeuresDeLaReponse cle={q.key} reponses={commercialAnswers}
                                   setReponse={setCommercialAnswer} />
              </div>
            ))}
          </div>
        )}
        <ArchetypeEtSansEffet profil={apercuCi?.donnees?.profil_charge} />
      </div>
    </CarteProfilCi>
  )
}
