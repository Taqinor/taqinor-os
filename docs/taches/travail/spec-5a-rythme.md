# Spec 5a — Rythme : POUSSER par paliers, TENIR, journée réussie, profil, sollicitations

Remplace `design-s2-moteur.md` §3, §5, §6. Banc `sim5/` (AVANT réutilise `sim/engine.py`). **Tout chiffre de
simulation est une propriété de la règle sur données synthétiques (30 graines, 120 jours, comportements écrits dans
`sim5/personas.py`), jamais un fait sur des utilisateurs réels.** Sources = brief §2 ; le reste = choix de
conception (CdC). Les nombres des phrases sont des gabarits.

## 1. Parcours (gestes iPhone / bureau)
« Plus » : Réglages › Rythme › Pousser 3/3 (ou dicté + 1 tap). Répondre à un palier (carte du matin) 1/1.
« Ça suffit » 2/2. Congé 5/4. Revue de la semaine 1/1.

## 2. Fonctions classées
ESSENTIEL : paliers proposés, baisse d'un cran proposée, TENIR bas ET haut (socle §6), bilan à quatre faits.
AVANCÉ : LIBRE, objectif dit, jours courts, 8 constats, repère P60 (Adams 2017). ÉCARTÉ : P60 quotidien comme
objectif (miroir, rapport-simulation) ; P60 comme borne (étouffe la montée, §6) ; points, badges, séries (Deci,
Koestner & Ryan 1999 ; Hamari 2014 ; séries brisées [S]) ; heures imposées (chronotype : > 80 % de 65 études sans
effet).

## 3. Règles exactes

### 3.1 Ce qui compte comme fait (`compte_du_jour`)
Par jour local : tâche propre passée à `fait` = 1 ; parent = 1, **sous-tâche = 0** (affichée « 3 étapes ») ;
récurrence quotidienne ou jours ouvrés = **routine = 0** (affichée à part), récurrence plus espacée = 1 ; activité
ERP close par lui = 1 ; **micro-tâche** (estimation ≤ 10 min) : **2 comptées au plus** par jour ; rouverte =
retirée ; annulée = 0. CdC.

### 3.2 Statut du jour (`statut_jour`)
`conge` · `non_ouvre` (non ouvré société, hors `jours_travailles` dits, férié) · `sans_donnees` (ouvré, 0 compté,
aucun plan validé, app non ouverte) · `evalue`. **Seul `evalue` entre dans les règles.** Un samedi travaillé va
dans les totaux, jamais dans un bloc : il ne peut ni pénaliser ni gonfler. Pas de données ≠ mauvaise journée.

### 3.3 Journée réussie (`journee_reussie`)
Compte ≥ objectif ET au moins un essentiel fait (si 1 à 3 choisis). Toujours affichée avec ses quatre faits —
compte, objectif, essentiel, plan tenu (lignes `prevue_au_plan` faites / prévues ; les ajouts comptent dans le
compte, pas au dénominateur) — jamais le mot « ratée ». Les **paliers** lisent seulement « jours à N ou plus » :
exiger aussi l'essentiel créait des baisses à tort (régulier 0,2-0,4 contre 0-0,1) sans freiner le tricheur.

### 3.4 Démarrage à froid (`palier_initial`)
Avant 10 jours évalués : objectif **5, « valeur par défaut, pas encore calculée sur toi »** (Todoist Karma,
preuve faible) ou le nombre dit (carte au 1er jour). Au 10e jour évalué : journée type = arrondi inférieur de
min(médiane, moyenne), plancher 1 (rafales : médiane 9, moyenne 6,2 → 6). Elle devient le palier, annoncée ; s'il a
dit un objectif, on le garde et on propose la journée type.

### 3.5 POUSSER (`evaluer_bloc`, `clore_bloc`)
- **Bloc** = 10 jours évalués au même palier (≈ 2 semaines ouvrées) ; évalué à sa clôture puis remis à zéro ; au
  plus une proposition par bloc.
- **Monter** si jours à N ou plus ≥ **6/10**, N < 12, aucun bloc à sauter, garde de taille passée, et N+1 n'est pas
  un palier quitté sans avoir été tenu depuis moins de 42 j × nombre d'échecs à ce niveau.
- **Baisser d'un cran** (jamais plus, jamais imposé, plancher 1) si jours à N ou plus ≤ **3/10**. Bloc d'essai :
  le 1er bloc après une montée ne propose une baisse que s'il compte 0 ou 1 jour tenu.
- **Refus de montée** : blocs sautés 1, 2, puis 4 ; au 3e refus de suite la carte ajoute « Garder ce rythme »
  (bascule TENIR). Refus de baisse : aucune baisse au bloc suivant. Sans réponse en 7 jours : expirée, ne compte
  pas comme refus. La réponse vaut le jour même si elle précède la validation du plan, sinon le lendemain.
- **Garde de taille** : référence = médiane des estimations des tâches faites pendant les 10 jours initiaux (ou
  le 1er bloc après une bascule). Pas de montée si la médiane du bloc < 70 % de la référence (≥ 10 tâches
  estimées de chaque côté, sinon inapplicable) ; bouton « Mes tâches ont changé » = nouvelle référence.
- **Jours courts dits** : objectif N−1 ce jour-là, évalué contre N−1.
- **Rôle du P60** : repère affiché à la demande, ni objectif ni borne.

### 3.6 TENIR (`reference_tenir`, `derive_tenir`)
R = moyenne non arrondie des 14 derniers jours évalués (≤ 42 j calendaires) ; s'il en manque, R provisoire = palier
courant (ou défaut), fixée après 14 jours évalués. Affiché « ton rythme : environ round(R), zone [R − b ; R + b] »,
b = max(1 ; 0,2 R). Dérive = moyenne des 14 derniers jours évalués **depuis la fixation de R** hors zone → une
carte, puis **28 jours de silence** quelle que soit la réponse : « Garder R » ou « Passer à » la moyenne observée
arrondie. Au-dessus (surchauffe), le plan proposé est plafonné à R + b tâches.

### 3.7 Bascules
POUSSER → TENIR : R ci-dessus (rythme réel, peut différer du dernier palier). TENIR → POUSSER : palier = arrondi
inférieur de R. LIBRE : aucun objectif, aucune proposition ni alerte ; les quatre faits restent affichés. LIBRE →
POUSSER : journée type des 10 derniers jours évalués (≤ 42 j), sinon défaut. Une bascule remet blocs, refus et
essai à zéro ; `meilleur_tenu` et les échecs sont gardés.

### 3.8 Profil — 8 constats au plus
Fenêtre 28 jours sauf mention ; interrupteur « comprendre mon rythme » coupé → rien calculé ni gardé (socle §8).
Faux constats de C1-C3 mesurés sur un utilisateur sans effet réel (`run_profil.py`).

| # | Formule · minimum | Phrase | Action proposée |
|---|---|---|---|
| C1 | plan tenu par créneau (< 12 h, après-midi, ≥ 16 h), écart ≥ 25 pts · 30 lignes par créneau (faux 1,6 %) | « Fini : 82 % du planifié le matin, 48 % après 16 h (34 et 31 lignes). » | essentiel le matin |
| C2 | essentiel fait quand 1er du plan vs ailleurs, écart ≥ 30 pts · 15 jours chacun (faux 3,0 %) | « Essentiel fait 13 fois sur 15 en tête, 6 sur 15 sinon. » | en tête par défaut |
| C3 | moyenne d'un jour ≤ moyenne générale − 1 · 8 jours de ce jour (faux 2,1 %) | « Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours. » | jour court |
| C4 | prévues − faites ≥ 2 sur ≥ 60 % des plans · 10 plans | « Tu prévois 8 tâches, tu en finis 5 (médianes). » | plan à médiane faite + 1 |
| C5 | heures de fin · 30 tâches | « 34 % de tes 61 tâches finies entre 9 h et 11 h. » | aucune (chronotype) |
| C6 | réel/estimé médian hors [0,8 ; 1,25] · 5 par clé (Buehler, Griffin & Ross 1994) | « Tes tâches « Admin » ont pris 1,5 × l'estimation (8). » | budget corrigé |
| C7 | reportées ≥ 3 fois · 1 | « 4 tâches reportées 3 fois ou plus. » | carte « à trancher » |
| C8 | projet priorité haute, 0 fait en 14 j | « Ton projet prioritaire n'a pas avancé depuis 14 jours. » | une de ses tâches au plan de demain |

Refusé : 28 jours de silence. **Ce qu'il a DIT prime** (`Preference`, clés fermées) : `mode_rythme`,
`objectif_dit`, `jours_travailles`, `jours_courts`, `conges`, `heure_matin`, `heure_soir`, `heure_limite`,
`relance_jour`, `revue_semaine`, `titres_notifications`, `essentiel_le_matin`, `comprendre_mon_rythme`,
`capacite_jour_min`, `note_libre` (≤ 200 car., donnée).

### 3.9 Sollicitations (cadre socle §5)
Défauts : matin **08:30** (si aucun plan validé), relance unique **15:00**, soir **18:00** (si plan validé ou ≥ 1
fait), revue le dernier jour travaillé de la semaine à l'heure du soir à la place du bilan, heure limite 20:00.
Hors fenêtre : sautée ; rien en congé ni jour non ouvré. Relance (`choisir_relance`) : 1) échéance du jour non
faite ; 2) dérive — POUSSER : compte à 15 h < objectif/2 et essentiel non fait ; TENIR : compte ≥ haut de zone ;
3) projet prioritaire négligé. Propositions et alertes = cartes dans l'app, jamais une notification de plus.
Ignorée = non ouverte en 3 h ni écran visité ; **pause d'un type après 14 ignorées de suite**, annoncée (« J'ai mis
en pause le rappel du matin. Le réactiver ? ») ; une ouverture remet à zéro. Rotation (Klasnja 2018) :
`date.toordinal() % 3`. Écran verrouillé : des comptes, pas de titre.

### 3.10 Phrases exactes
- Matin : « Ta journée : 7 tâches prévues ou en retard. Objectif 5. » · « Bonjour. 7 tâches t'attendent ; objectif
  du jour : 5. » · « Plan du jour : choisis ton essentiel (objectif 5). »
- Relance : « 1 tâche a son échéance aujourd'hui. » · « Échéance aujourd'hui : 1 tâche encore ouverte. » · « Avant
  ce soir : 1 tâche à échéance. » ; dérive POUSSER « 2 faites sur 5 ; ton essentiel est encore ouvert. » ; TENIR
  « 7 faites, ta zone est 4 à 6 : le reste peut attendre demain. »
- Soir : « Bilan : 4 faites sur 6 prévues. » · « Journée close ? 4 tâches faites. » · « 4 faites, 2 à placer. »
- Bilan : « Aujourd'hui : 6 faites · objectif 5 atteint · essentiel fait · plan tenu 4 sur 5. » (sinon « 3 faites
  (objectif 5) · … »). Détail : « 2 micro-tâches comptées sur 4 ».
- Monter : « Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ? » [Oui, 6] [Pas maintenant].
- Baisser : « Ces 10 jours travaillés, 6 tâches ou plus : 2 fois. Revenir à 5 pour un temps ? » [Oui, 5] [Garder 6].
- Taille : « Tes tâches terminées sont plus courtes qu'au départ (22 min en médiane contre 33) : je ne propose pas
  de monter. » [Mes tâches ont changé].
- Premier palier : « J'ai 10 jours de toi : ta journée type est 3 tâches. Ton objectif passe de 5 (valeur par
  défaut) à 3. »
- TENIR : « Ces 14 jours travaillés : 3,4 tâches par jour, sous ta zone 4 à 6. Garder 5 ou passer à 3 ? »
- Semaine : « Du 16 au 20/11 : 26 tâches en 5 jours (précédente : 23). Journées réussies 3 sur 5 · essentiel 4 sur 5
  · plan tenu 21 sur 27. Samedi : 2. » Retour informatif (Deci, Koestner & Ryan 1999), un constat au plus.

## 4. Données (ajouts au socle §3) et API
`ReglagesRythme` : `mode` (`pousser` défaut/`tenir`/`libre`), `palier` (null = froid), `palier_source`,
`bloc_debut`, `refus_montee`, `blocs_a_sauter`, `baisse_refusee`, `essai_restant`, `meilleur_tenu`, `echec_niveau`,
`echec_le`, `echec_n`, `ref_taille_min`, `tenir_reference` Decimal(4,2), `tenir_fixee_le`, `tenir_silence_jusquau`.
`PlanJour` : `objectif_du_jour`, `statut_jour`, `compte_rythme`, `micro_comptees`, `essentiels_choisis`,
`essentiels_faits`, `plan_prevues`, `plan_faites`, `taille_mediane_min` (bloc = `PlanJour` `evalue` depuis
`bloc_debut`, recalculable). `IncitationCoach` : types `proposition_palier`, `derive_tenir`, `garde_taille`,
`revue_semaine`. Tâche planifiée `taches.calculer_rythme` (03:00).
`GET taches/rythme/` → `{"mode":"pousser","objectif":{"nb":6,"source":"accepte"},"bloc":{"jours":7,"tenus":5,"sur":10},"proposition":{"id":41,"type":"monter","boutons":["oui","pas_maintenant"]}}` ;
`POST taches/rythme/` `{"mode":"tenir"}` (400 `{"mode":["Valeur inconnue."]}`) ;
`POST taches/rythme/propositions/<id>/repondre/` (409 `{"reponse":["Proposition expirée."]}`). Contrat d'abord :
`profil_rythme.json`. Assistant : `taches.rythme.regler` ; réponses par tap de carte.

## 6. Simulation — AVANT (design-s2 §3) / APRÈS, moyennes de 30 graines

Itérations (`run_variantes.py`) : borne P60 → profil qui progresse à 5,0-5,2 tâches faites ; seuil 7/10 → 5,5-5,9 ;
6/10 sans borne → 6,0-6,4, retenu. Garde à 80 % : bloque l'honnête 0,3-0,4 fois → 70 %. Condition de moyenne sur la
baisse : sans effet → retirée. Moyenne rognée pour TENIR : gain marginal → moyenne simple (socle §6).

| Profil | AVANT objectif j30/60/119 · pire saut · changements | APRÈS objectif j30/60/119 · propositions ↑/↓ (acceptées) · fausses baisses | Fait, 20 derniers j (AV → AP) |
|---|---|---|---|
| 1 régulier 5 ± 1,2 | 5/5/6 · −2 · 10,7 | 5,5/6/6 · 2,6/1,1 (1,9/0,9) · 0 | 5,2 → 5,3 |
| 2 progresse +1/2 sem. s'il est poussé | 5/5/6 · −1 · 7,5 | 5/6/7 · 3,4/0,1 · 0 | 5,8 → **6,5** |
| 3 rafales 9-10 puis 1-2 | 3/4/8 · **−7** · 74,7 | 5/5/4 · 0,2/2 · 0,9 | 5,1 → 5,1 |
| 4 tricheur (objectif + 1 en découpant) | 10/15/**25** · 20 | 7/8/9 (max 11) · 3/0, 4 gardes | 23,5 → 9,8 |
| 5 interrompu (congé 10 j, samedis) | 5/5/5 · −2 · 13 | 5/6/6 · 2,3/0,7 · 0 | 5,1 → 5,3 |
| 6 effondrement puis reprise | 5/4/5 · −4 (min 1) | 5,5/4,5/5 · 2,5/1,5 · 0,1 (min 3) | 5,0 → 5,0 |
| 7 froid, vrai niveau 3 | 3/3/3 · −2 | 4/4/4 · 1,9/1,2 · 0 | 3,0 → 3,3 |
| 8 plafond 6, dit oui | 6/6/6 · −1 | 6/6/6 (max 7) · 2,7/1,5 · 0 | 5,6 → 5,6 |
| 9 alterne P→T→L→P | 5/5/6 · −2 | 5,5/5/6 · 2,0/0 · 0 | 5,2 → 5,1 |
| 10 refuse tout (progresse) | 5/5/6 | 5/5/5 · 2,7/0,2 (0/0) | 5,8 → 4,8 |
| 11 oui à tout (régulier) | 5/5/6 · −2 | 6/6/6 · 2,3/1,2 | 5,2 → 5,3 |
| 11b oui à tout (progresse) | 5/5/6 | 5/6/8 · 3,6/0,2 | 5,8 → **7,3** |

APRÈS : sauts ∈ [−1 ; +1] sauf remplacement du défaut (+2, −2) et bascule (+2). AVANT : baisses imposées alors que
l'habitude ≥ objectif 0,9 (1), 2,2 (5), 1,0 (6). Journées réussies 50 → 48 % (1), 62 → 52 % (8) : pousser a un coût.

| TENIR, 120 j | AVANT alertes / fausses / délai | APRÈS |
|---|---|---|
| régulier 5 ± 1,2 | 2,6 / 2,6 | 0,1 / 0,1 |
| régulier 5 ± 2,0 | 6,7 / 6,7 | 0,9 / 0,9 |
| rafales | 12,0 / 12,0 | 0 / 0 |
| froid enthousiaste (8,8,8 puis 3) | 15,7 / 15,7 | 2,4 / 2,4 |
| baisse 5 → 3 au j50 | 7,7 / 1,1 / 9 j | 2,8 / 0 / 10 j |
| surchauffe 5 → 7 au j50 | 9,0 / 1,1 / 7 j | 2,8 / 0 / 10 j |

Samedi toujours travaillé → objectif du lundi −0,39 AVANT, −0,05 APRÈS. Congé de 10 j : objectif plus bas au retour
1/30 → 0/30 ; congé de 4 semaines : retour au défaut 10/30 → palier gardé 30/30. Refus en série : j25, j53, j101.

**Reste imparfait.** Rafales : ~40 % de journées réussies quel que soit N, le palier ne l'aide pas. Tricheur :
gagne encore 4 crans ; sans estimations, garde inapplicable. Plafond qui dit oui : ~2 semaines à 7, impossible.
+1 par bloc au plus freine un profil plus rapide. TENIR démarré sur des jours atypiques : ~1 alerte / 28 j tant
qu'il répond « garder ». Détection TENIR en 10 j (7-9 AVANT). Non re-simulés : sous-tâches, routines, activités ERP,
C4-C8, décroissance. « Il progresse s'il est poussé » reste une hypothèse.

## 7. Fonctions pures (`apps/taches/moteur/rythme.py`) — exemples vérifiés par `python sim5/exemples.py`

| Fonction → sortie | 3 exemples |
|---|---|
| `compte_du_jour(taches, activites)` → (compte, détail) | 4×30 min + 3×5 min → 6 ; 3 sous-tâches + parent → 1 ; routine + tâche + 2 activités → 3 |
| `statut_jour(ouvre, conge, compte, plan, app)` → statut | (oui, non, 0, non, non) → sans_donnees ; samedi 2 faites → non_ouvre ; (oui, non, 0, oui, oui) → evalue |
| `journee_reussie(compte, objectif, k, e)` → bool/None | (6,5,1,1) vrai ; (6,5,2,0) faux ; (4,5,0,0) faux |
| `palier_initial(comptes10, dit)` → (palier, type) | [5,4,6,5,3,7,5,6,4,5] → (5,5) ; [9,10,9,1,2,1,2,9,10,9] → (6,6) ; [3,3,2,4,3,3,2,3,4,3] dit 5 → (5,3) |
| `evaluer_bloc(etat, jour)` → décision | N 5, (5,6,5,4,7,5,3,6,5,4) → monter ; N 6, (5,4,6,5,3,5,6,4,5,4) → baisser ; tailles 20, réf. 40 → taille |
| `clore_bloc(etat, jour, décision, réponse)` → état | refus → 1 bloc sauté ; baisse 7→6 au j60 → échec (7, 60, 1) ; montée vers 7 refusée au j90, permise au j102 |
| `reference_tenir(comptes)` → R/None | 14 jours de somme 70 → 5,0 ; 13 jours → None ; 14 × 7 → 7,0 |
| `bande_tenir(R)` | 5 → (4 ; 6) ; 8 → (6,4 ; 9,6) ; 2 → (1 ; 3) |
| `derive_tenir(R, comptes, jour, silence)` | 5, moyenne 3,2 → sous ; 5, moyenne 6,9 → au_dessus ; silence en cours → None |
| `objectif_affiche(etat)` → (nb, source) | froid → (5, defaut) ; dit 4 → (4, dit) ; LIBRE → (None, libre) |
| `basculer(etat, mode, jour)` | TENIR R 5,6 → palier 6 ; R 5,5 → 5 ; vers TENIR, 14 derniers = 73 → R 5,21 |
| `choisir_relance(candidats)` | {négligé, échéance} → échéance ; {négligé, dérive} → dérive ; ∅ → None |
| `etat_decroissance(ignorees)` | 14 ignorées → pause ; 13 → normal ; 20 puis 1 ouverte → normal |
| `derive_pousser_journee(c15h, N, ess)` | (2,5,non) vrai ; (3,5,non) faux ; (1,5,oui) faux |
| `variante(ordinal)` | 739572 → 0 ; 739573 → 1 ; 739574 → 2 |

## 8. Critères d'acceptation
Les exemples de §7 sont des critères tels quels. En plus :
1. Étant donné palier 5 et un bloc (5,6,5,4,7,5,3,6,5,4), quand il clôt, alors une proposition « 6 » existe et le
   palier reste 5 jusqu'au tap « Oui ».
2. Étant donné palier 6 et 2 jours sur 10 à 6 ou plus hors essai, alors la proposition est 5 ; palier 1 : aucune.
3. Étant donné un samedi à 2 tâches, alors la longueur du bloc ne change pas.
4. Étant donné un congé déclaré de 10 jours, alors aucune sollicitation pendant, et palier au retour = veille.
5. Étant donné un 3e refus de montée de suite, alors la carte porte « Garder ce rythme ».
6. Étant donné TENIR et une alerte au jour J, alors aucune alerte avant J + 28, quelle que soit la réponse.
7. Étant donné LIBRE, alors `objectif.nb` = null et aucune proposition.
8. Étant donné le banc `sim5` (30 graines, 120 j), alors régulier en TENIR ≤ 0,3 alerte ; tricheur « oui »
   objectif final moyen ≤ 10 ; « oui à tout, progresse » fait final ≥ 6,8 ; fausses baisses du régulier = 0 ;
   sauts ∈ [−1 ; +1] hors remplacement du défaut et bascule.
9. Étant donné « comprendre mon rythme » coupé, alors `constats = []` et rien n'est conservé.
10. Chaque nombre d'un texte de §3.10 figure dans `IncitationCoach.donnees`.

## 9. Risques, choix par défaut, objections
Risque : deux comptes (écran, moteur) → un seul `compte_du_jour` ; banc = test de propriété (critère 8).
Choix par défaut : POUSSER par défaut (demande du fondateur, tout est proposé) ; noms `pousser/tenir/libre`
(design-s3) ; propositions au plan du matin ; activités ERP comptées (Q1 de design-s2) ; heure limite 20:00 ;
plafond 12. Objections au socle : aucune.
