# Registre des constats — format machine (go-deep L4 / L5)

Le registre REMPLACE les rapports en prose comme source de vérité : l'orchestrateur ne relit que lui (et des messages
de 15 lignes). JSON Lines (une ligne = un objet) : un modèle écrase moins volontiers un fichier JSON qu'un Markdown,
et on ne modifie jamais une ligne écrite — on AJOUTE un événement. Dossier : `<dossier de travail>/registre/`.

## 1. Fichiers (un seul écrivain par fichier : jamais deux agents sur le même fichier)
- `constats/T<n>-<relecteur>.jsonl` — écrit par le relecteur, au fil de l'eau (un constat dès qu'il est prouvé).
- `evenements.jsonl` — écrit par l'orchestrateur SEUL, à chaque étape (il recopie les sorties de la consolidation,
  des lanes et des contre-vérifications) ; ajout seulement.
- `classes.jsonl` — une ligne par classe de défaut (renvoie à sa fiche d'invariant).

## 2. Champs d'un constat
| champ | valeurs |
|---|---|
| `id` | `T<n>-<relecteur>-<nnn>` (jamais renuméroté) |
| `tour`, `relecteur` | entier ; code du relecteur (`F1`, `S1`, `B1`…) |
| `axe` | `F` fonction · `S` simplicité · `Be` beauté · `A11y` · `D` données |
| `vue` | `iphone-clair` · `iphone-sombre` · `bureau-clair` · `bureau-sombre` · `serveur` |
| `gravite` | `A` (casse ou bloque un geste courant, ou saute aux yeux) · `B` (gêne ou laideur au quotidien) · `C` (finition) |
| `ecran`, `gestes`, `capture`, `attendu` | texte ; chemin de capture ; texte |
| `critere` | `K<n>` du contrat de sortie, ou `hors-contrat` (alors OPTIONNEL, jamais bloquant) |
| `classe` | `null` ou id de classe proposé par le relecteur (la consolidation tranche) |
| `avant_merge` | dernier tour seulement : `true` / `false` ; sinon `null` |

## 3. Événements — listes FERMÉES de verdicts (un autre mot = ligne refusée)
| `etape` | `verdict` | champs en plus |
|---|---|---|
| `consolidation` | `retenu` · `doublon` · `ecarte-artefact` (dû à l'instrument) · `ecarte-hors-perimetre` · `ecarte-faux` · `a-reproduire` | `cause` (`fichier::symbole`), `cause_statut` (`lue` · `probable` · `a-reproduire`), `correction`, `lane`, `tache` (id du plan), `classe`, `doublon_de` |
| `test-premier` | `ecrit` | `test` (`chemin::nom`), `branche`, `commit` |
| `correction` | `corrige` · `conteste` · `impossible` | `commit`, `test`, `capture_apres`, `raison` (obligatoire hors `corrige`) |
| `contre-verification` | `ok` · `partiel` · `non-fait` · `faux` · `regression` · `deja-present` (mots de `vérifie`, METHODE §C.4) | `par` (relecteur NEUF, jamais l'auteur), `capture`, `reste` |
| `disjoncteur` | `parque-avec-decision` · `plus-petit-changement` | `decision`, `cout_si_faux` |
| `rejeu` | `confirme` · `infirme` | `par` (orchestrateur ou neuf) — obligatoire avant correction pour tout A, chiffre faux, perte de données |

## 4. Exemple (trois lignes)
`constats/T1-F1.jsonl` :
```json
{"id":"T1-F1-007","tour":1,"relecteur":"F1","axe":"F","vue":"iphone-clair","gravite":"A","ecran":"<écran>","gestes":"taper « abc », Entrée, taper « def » sans attendre","capture":"<scratchpad>/T1-F1/007.png","attendu":"« def » entier","critere":"K1","classe":"frappe-perdue","avant_merge":null}
```
`evenements.jsonl` :
```json
{"id":"T1-F1-007","tour":1,"etape":"consolidation","verdict":"retenu","cause":"frontend/src/<chemin>.jsx::<fonction>","cause_statut":"lue","correction":"C1-012","lane":"L3","tache":"<PLAN>-101","classe":"K-FRAPPE"}
{"id":"T1-F1-007","tour":2,"etape":"contre-verification","verdict":"partiel","par":"F3","capture":"<scratchpad>/T2-F3/r007.png","reste":"hors ligne, la 1re lettre est encore avalée"}
```

## 5. En tirer la courbe par relecteur et le taux d'écartés
Depuis le dossier `registre/` (Python 3, sans dépendance) :
```sh
python - <<'EOF'
import json, glob, collections as C
cs = [json.loads(l) for f in glob.glob('constats/*.jsonl') for l in open(f, encoding='utf-8') if l.strip()]
ev = [json.loads(l) for l in open('evenements.jsonl', encoding='utf-8') if l.strip()]
cons = {e['id']: e['verdict'] for e in ev if e['etape'] == 'consolidation'}
tot, ret = C.Counter(), C.Counter()
for c in cs:
    k = (c['tour'], c['relecteur'], c['axe']); tot[k] += 1
    ret[k] += cons.get(c['id']) == 'retenu'
print('tour relecteur axe  vus retenus ecartes%')
for k in sorted(tot):
    print(*k, tot[k], ret[k], round(100 * (1 - ret[k] / tot[k])))
cv = C.Counter(e['verdict'] for e in ev if e['etape'] == 'contre-verification')
n = sum(cv.values()) or 1
print('contre-verification', dict(cv), 'non-fait+partiel %', round(100 * (cv['non-fait'] + cv['partiel']) / n))
EOF
```
Lecture : la courbe de découverte se lit PAR RELECTEUR (retenus / relecteur / tour), jamais en total brut (152 → 78 →
~30 cachait 6, 5 puis 4 relecteurs). Le taux d'écartés par relecteur et par axe dit si un axe produit surtout du
bruit. La ligne `non-fait+partiel %` décide de la contre-vérification : toutes les corrections tant qu'elle dépasse
10 %, puis tous les A + 25 % des autres.
