# Registre des constats — format machine (go-deep L4 / L5)

Le registre REMPLACE les rapports en prose comme source de vérité : l'orchestrateur ne relit que lui (et des messages
de 15 lignes) et ne RECOPIE jamais une sortie d'agent dans le registre — chaque agent écrit la sienne. JSON Lines (une
ligne = un objet) : un modèle écrase moins volontiers un fichier JSON qu'un Markdown, et on ne modifie jamais une ligne
écrite — on AJOUTE un événement. Dossier : `<dossier de travail>/registre/`, sur la branche de notes, poussé à chaque
point de contrôle.

## 1. Fichiers — UN écrivain par fichier, jamais deux agents sur le même
| Fichier | Écrivain | Quand |
|---|---|---|
| `constats/T<n>-<relecteur>.jsonl` | le relecteur | au fil de l'eau, un constat dès qu'il est prouvé |
| `evenements/T<n>-<relecteur>-cv.jsonl` | le relecteur (tour ≥ 2) | un verdict de contre-vérification par correction |
| `evenements/T<n>-consolidation.jsonl` | l'agent de consolidation | un verdict par constat |
| `evenements/T<n>-tests-<lane>.jsonl` | le rédacteur des tests premiers de la lane | un `ecrit` par test |
| `evenements/T<n>-lane-<lane>.jsonl` | la lane de correction (seule écriture permise hors de son worktree, chemin absolu donné par son brief) | une sortie par correction, une `demande-croisee` par besoin d'une autre lane |
| `evenements/T<n>-couture.jsonl` | la lane de couture | capture « après » regardée, identifiant partagé vérifié, réponse aux demandes croisées |
| `evenements/T<n>-orchestrateur.jsonl` | l'orchestrateur, pour SES gestes seulement | rejeu, disjoncteur |
| `classes.jsonl` | l'agent de consolidation | une ligne par classe (renvoie à sa fiche d'invariant) |

## 2. Gravité — l'échelle S1-S4 de `docs/audits/METHODE.md` (§B.2), une seule échelle dans toute la maison
| Gravité | METHODE | Lecture pour l'écran (fonction · simplicité · beauté) |
|---|---|---|
| S1 | argent faux, perte, fuite, chiffre client faux | idem |
| S2 | saisie effacée, geste cassé sans contournement | geste courant cassé ou impossible ; défaut qui saute aux yeux dès la première heure |
| S3 | contournement | gêne ou laideur au quotidien |
| S4 | cosmétique (optionnel) | finition |
Correspondance avec l'ancien projet : A = S1-S2, B = S3, C = S4. La priorité P0-P3 est posée par l'orchestrateur.

## 3. Champs d'un constat
| champ | valeurs |
|---|---|
| `id` | `T<n>-<relecteur>-<nnn>` (jamais renuméroté) |
| `tour`, `relecteur` | entier ; code du relecteur (`F1`, `S1`, `B1`…) |
| `axe` | `F` fonction · `S` simplicité · `Be` beauté · `A11y` · `D` données |
| `vue` | `iphone-clair` · `iphone-sombre` · `bureau-clair` · `bureau-sombre` · `serveur` |
| `gravite` | `S1` · `S2` · `S3` · `S4` |
| `ecran`, `gestes`, `capture`, `attendu` | texte ; chemin de capture ; texte |
| `critere` | `K<n>` du contrat de sortie, ou `hors-contrat` (alors OPTIONNEL, jamais bloquant) |
| `classe` | `null` ou id de classe proposé par le relecteur (la consolidation tranche) |
| `avant_merge` | dernier tour seulement : `true` / `false` ; sinon `null` |

## 4. Événements — listes FERMÉES de verdicts (un autre mot = ligne refusée par le script)
| `etape` | `verdict` | champs en plus |
|---|---|---|
| `consolidation` | `retenu` · `doublon` · `ecarte-artefact` (dû à l'instrument) · `ecarte-hors-perimetre` · `ecarte-faux` · `a-reproduire` | `cause` (`fichier::symbole`), `cause_statut` (`lue` · `probable` · `a-reproduire`), `correction`, `lane`, `tache` (id du plan), `classe`, `doublon_de` |
| `test-premier` | `ecrit` | `test` (`chemin::nom`), `branche`, `commit` |
| `correction` | `corrige` · `conteste` · `impossible` | `commit`, `test`, `gestes_apres` (à rejouer par la couture), `raison` (obligatoire hors `corrige`) |
| `capture-apres` | `vue-ok` · `vue-ko` | `par` (couture), `capture`, `correction` |
| `contre-verification` | `ok` · `partiel` · `non-fait` · `faux` · `regression` · `deja-present` (mots de `vérifie`, METHODE §C.4) | `par` (relecteur NEUF, jamais l'auteur), `capture`, `reste` |
| `demande-croisee` | `ouverte` · `faite` · `refusee` | `de` (lane), `vers` (lane ou couture), `fichier`, `changement` ; `faite` / `refusee` écrits par le destinataire |
| `disjoncteur` | `parque-avec-decision` · `plus-petit-changement` | `decision`, `cout_si_faux` |
| `rejeu` | `confirme` · `infirme` | `par` (orchestrateur ou neuf) — obligatoire avant correction pour tout S1, chiffre faux, perte de données |

Les « restes » du fichier d'état sont les `demande-croisee` encore `ouverte` et les contre-vérifications `partiel` /
`non-fait` sans correction suivante : aucun autre état n'existe.

## 5. Exemple (module Tâches, 19-20/11 — trois lignes)
`constats/T1-F1.jsonl` :
```json
{"id":"T1-F1-007","tour":1,"relecteur":"F1","axe":"F","vue":"iphone-clair","gravite":"S2","ecran":"<écran>","gestes":"taper « abc », Entrée, taper « def » sans attendre","capture":"<scratchpad>/T1-F1/007.png","attendu":"« def » entier","critere":"K1","classe":"frappe-perdue","avant_merge":null}
```
`evenements/T1-consolidation.jsonl` puis `evenements/T2-F3-cv.jsonl` :
```json
{"id":"T1-F1-007","tour":1,"etape":"consolidation","verdict":"retenu","cause":"frontend/src/<chemin>.jsx::<fonction>","cause_statut":"lue","correction":"C1-012","lane":"L3","tache":"<PLAN>-101","classe":"K-FRAPPE"}
{"id":"T1-F1-007","tour":2,"etape":"contre-verification","verdict":"partiel","par":"F3","capture":"<scratchpad>/T2-F3/r007.png","reste":"hors ligne, la 1re lettre est encore avalée"}
```

## 6. En tirer la courbe par relecteur, le taux d'écartés et les restes
Depuis le dossier `registre/` (Python 3, sans dépendance) :
```sh
python - <<'EOF'
import json, glob, collections as C
lire = lambda motif: [json.loads(l) for f in sorted(glob.glob(motif)) for l in open(f, encoding='utf-8') if l.strip()]
cs, ev = lire('constats/*.jsonl'), lire('evenements/*.jsonl')
V = {'consolidation': {'retenu','doublon','ecarte-artefact','ecarte-hors-perimetre','ecarte-faux','a-reproduire'}, 'test-premier': {'ecrit'}, 'correction': {'corrige','conteste','impossible'}, 'capture-apres': {'vue-ok','vue-ko'}, 'contre-verification': {'ok','partiel','non-fait','faux','regression','deja-present'}, 'demande-croisee': {'ouverte','faite','refusee'}, 'disjoncteur': {'parque-avec-decision','plus-petit-changement'}, 'rejeu': {'confirme','infirme'}}
bad = [e for e in ev if e.get('verdict') not in V.get(e.get('etape'), ())]
if bad: raise SystemExit(f'{len(bad)} lignes refusees, ex. {bad[0]}')
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
dem = {}
for e in ev:
    if e['etape'] == 'demande-croisee':
        k = (e['de'], e['fichier'], e['changement'])
        if e['verdict'] != 'ouverte' or k not in dem: dem[k] = e['verdict']
print('demandes croisees ouvertes', [k for k, v in dem.items() if v == 'ouverte'])
EOF
```
Lecture : la courbe de découverte se lit PAR RELECTEUR (retenus / relecteur / tour), jamais en total brut (152 → 78 →
27 cachait 6, 5 puis 4 relecteurs, et le 27 ne comptait que les corrections « avant le merge »). Le taux d'écartés par relecteur
et par axe dit si un axe produit surtout du bruit. La ligne `non-fait+partiel %` décide de la contre-vérification :
toutes les corrections tant qu'elle dépasse 10 %, puis tous les S1-S2 + 25 % des autres (10 % : valeur de départ, non
calibrée ; 25 % : METHODE §C.4.2).
