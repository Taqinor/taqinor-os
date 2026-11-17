# Spécification L3 n°4 — Projets et planification (`apps/taches`)

Sources : `recherche-4-projets-planification.md` (« R§n »). Tout projet actif verse ses tâches dans « Ma journée ».

## 1. Parcours (gestes iPhone / bureau, saisie de texte non comptée)

| # | Parcours | iPhone | Bureau |
|---|---|---|---|
| P1 | « + Nouveau projet » → nom → « Créer » (puis bandeau « Planifier (2 min) / Plus tard ») | 3 | 2 |
| P2 | Tâche dans un projet : champ en pied de section → titre → Retour | 2 | 1 |
| P3 | Tâche vers un nouveau projet : dans le choix de projet, taper « Chantier X » → « Nouveau projet « Chantier X » » | 2 | 2 |
| P4 | Planification minimale : objectif → Suivant · chip d'échéance · Suivant · actions → « Terminer » | 4 | 4 |
| P5 | Sauter la planification : « Plus tard » | 1 | 1 |
| P6 | Découpage IA : « Proposer avec l'assistant » → retirer k lignes → « Tout ajouter » | 2 + k | 2 + k |
| P7 | Décaler : ⋯ → « Décaler les dates » → « +1 semaine » → « Appliquer » (toast Annuler) | 4 | 4 |
| P8 | Prérequis : tâche → « Attend… » → choisir la tâche | 3 | 3 |
| P9 | Revue, un projet : Garder / Pause / Terminer / Passer | 1 | 1 |
| P10 | Terminer : ⋯ → « Terminer » → Atteint / Abandonné → « Confirmer » | 4 | 4 |
| P11 | Modèle : ⋯ → « Enregistrer comme modèle » → OK ; instancier : « + Nouveau projet » → « Depuis un modèle » → modèle → date → « Créer » | 3 ; 5 | 3 ; 5 |

## 2. Fonctions classées

| Fonction | Classe | Origine | Pourquoi |
|---|---|---|---|
| Liste, ordre manuel (`rang`) | ESSENTIEL | Things, Todoist | aucun tri qui bouscule |
| « Trier par priorité » (une fois, Annuler) | AVANCÉ | — | jamais de réordonnancement silencieux |
| Épingler / favoris | ÉCARTÉ → « Mettre en haut » | — | doublon de l'ordre manuel |
| Priorité projet 0-3 | ESSENTIEL | socle §3 | pèse sur la journée |
| Statuts actif, terminé / en pause, archivé | ESSENTIEL / AVANCÉ | OmniFocus On Hold, Things Someday | |
| « À planifier » (dérivé, pas un statut) | ESSENTIEL | GTD | aucune tâche cachée par un état |
| Domaine (libellé, regroupe la liste) | AVANCÉ | PARA, Things Areas | utile à partir de beaucoup de projets |
| Couleur d'office + icône ; choix | ESSENTIEL / AVANCÉ | socle | zéro décision à la création |
| Boîte de réception implicite, compteur « n ouvertes », marque de santé | ESSENTIEL | socle, Linear | |
| Planification : objectif, échéance (chips d'appétit), premières actions | ESSENTIEL | GTD, Shape Up | 2 min |
| Planification : étapes, jalons, risque (pre-mortem 1 ligne) | AVANCÉ | GTD, Klein | repliés sous « Plus » |
| Liste collée → sections + tâches, sans IA | ESSENTIEL | — | marche sans clé |
| Découpage proposé par l'IA, validé au doigt | AVANCÉ | socle §2.6 | |
| Décaler toutes les dates | AVANCÉ | Asana (défaut corrigé) | |
| Sections = phases ; dates de phase | ESSENTIEL / AVANCÉ | Things Headings | |
| Jalon = tâche marquée | AVANCÉ | Linear | pas d'objet de plus |
| Un prérequis par tâche | AVANCÉ | OmniFocus, Asana | |
| Plusieurs prérequis, chemin critique | ÉCARTÉ | R§3 | arbitrage d'équipe |
| Vue Liste à sections | ESSENTIEL | Things | nette au téléphone |
| Vue Tableau, colonnes = sections | AVANCÉ | Marvin | |
| Tableau par statut | ÉCARTÉ → filtre de la liste | — | 4 statuts, aucun gain solo |
| Chronologie phases + jalons (lecture) | AVANCÉ | Linear | |
| Gantt glissé à dépendances | ÉCARTÉ → Chronologie | R§À ÉVITER | illisible au téléphone |
| Calendrier du projet | AVANCÉ (lien agenda `?projet=`) | — | L3 agenda |
| Avancement « 12 sur 20 » + barre | ESSENTIEL | Linear | jamais un % seul |
| Burn-up hebdomadaire | AVANCÉ | Linear | montre la dérive de portée |
| Santé calculée (3 signaux) | ESSENTIEL | OmniFocus « stalled » | zéro saisie |
| Statut couleur saisi | ÉCARTÉ → santé calculée | R§À ÉVITER | entretien |
| Projet négligé vs priorité | ESSENTIEL | socle §5 | |
| Plafond de projets actifs | ÉCARTÉ → constat affiché | R§5 | aucun nombre sourcé |
| Projet focus de la semaine | AVANCÉ | design-s2 §7 | |
| Modèles (créer, instancier, aperçu) ; dupliquer | AVANCÉ | Asana, Todoist | |
| Modèles fournis | ÉCARTÉ | — | rien de sourcé sur son métier |
| Revue : une carte par projet actif | ESSENTIEL | GTD | |
| Terminer (issue + bilan + sort des ouvertes) ; supprimer + Annuler | ESSENTIEL | OmniFocus ; socle §2.2 | |
| Archive, rouvrir | AVANCÉ | Todoist | |
| Objectifs trimestriels (OKR) | ÉCARTÉ → « fini quand… » + domaine + focus | R§9 | aucune utilité sourcée en solo |

## 3. Règles exactes

**Définitions.** *Comptée* = tâche du projet, `parent` nul, non supprimée, statut ≠ `annule`. *Ouverte* = comptée, statut `a_faire` ou `en_attente`. *Actionnable* = ouverte, `a_faire`, `quelque_jour` faux, non bloquée. *Jours travaillés* = `jours_ouvres_entre(company, du, au)` (`apps/notifications/calendar_utils.py:164`) moins les congés de `ReglagesRythme` (fonction partagée avec le L3 coach ; à défaut, calendrier société).

**A. Liste.** Ordre : Boîte de réception ; actifs par `rang`, groupés par `domaine` seulement si un actif en a un (groupes par plus petit `rang`, « Sans domaine » en dernier) ; « En pause (n) » replié ; terminés et archivés dans Archive. Nouveau projet de priorité p : `rang` au milieu entre le dernier actif de priorité ≥ p et le suivant (pas 1 024). Couleur d'office : première couleur de la palette absente des actifs, sinon la moins utilisée, égalité → ordre de palette. Changer la priorité ne déplace rien.

**B. Planification.**
- *À planifier* ⇔ `actif` ∧ `planifie_le` nul ∧ 0 ouverte. « Terminer » ou « Plus tard » pose `planifie_le`.
- Étapes : 1 « Ce sera fini quand… » (`objectif`) ; 2 échéance : `date_debut` (sinon aujourd'hui) + 7 / 14 / 30 / 90 jours, ou une date ; 3 étapes → `Section` ; 4 premières actions → tâches, la 1re avec chips Aujourd'hui / Demain / Plus tard ; 5 jalons (ligne + date) ; 6 risque « Si ça échoue, ce sera sans doute parce que… » (280 car., « En faire une tâche »).
- Liste collée : ligne finissant par « : » = section ; lignes suivantes = tâches ; « - » ou « * » sous une tâche = sous-tâche ; « ◆ » ou « jalon: » en tête = jalon ; vides ignorées ; 200 lignes au plus (sinon 400 sur `texte`).
- Rien n'est écrit avant « Terminer » ; une transaction crée tout.
- **Décaler** de Δ jours calendaires (négatif permis) : tâches ouvertes (`jour_prevu`, `echeance`), sections (`date_debut`, `date_fin`), projet (`date_debut`, `echeance`). Date + Δ ; jour non travaillé → `prochain_jour_ouvre` (`calendar_utils.py:186`). Refus si un `jour_prevu` tombe avant aujourd'hui. Faites et annulées intactes. Service de `planifier/` avec `compter_report=False`. Exemple : dim. 22/11/2026 + 7 = dim. 29/11 → lun. 30/11.

**C. Structure.**
- Section supprimée : ses tâches passent « Sans section ».
- Jalon (`Tache.jalon`) fait quand la tâche est faite. Prochain jalon = jalon ouvert de plus petite date (`echeance`, sinon `jour_prevu` ; sans date en dernier).
- T *bloquée* ⇔ `bloquee_par` non nul ∧ prérequis non supprimé ∧ statut du prérequis ∉ {`fait`, `annule`}. Bloquée = exclue des candidats ET de l'affichage de « Ma journée » même si `jour_prevu` ≤ aujourd'hui ; « Ma journée » montre le seul compte `a_trier.bloquees`. Elle revient quand le prérequis est fait, annulé ou supprimé, `jour_prevu` inchangé ; passé, elle rejoint le tri des retards du L3 journée, jamais déplacée seule. Refus : soi-même, autre propriétaire (404), cycle (remontée de `bloquee_par`, 50 maillons ; T rencontré → 400). Prérequis déjà fait : accepté, sans effet. Clore une tâche bloquée : permis.

**E. Avancement et santé** (projets `actif`).
- Avancement « F sur F+O », avec « dernière faite le … ». Exemple : 12 faites, 8 ouvertes, 3 annulées → « 12 sur 20 ». 0 comptée : pas de barre.
- Burn-up par semaine close s (fin dimanche) : total(s) = comptées créées ≤ fin(s) et non annulées ≤ fin(s) ; faites(s) = `fait` ∧ `fait_le` ≤ fin(s). Dès 2 semaines closes, légende « reconstruit depuis les dates actuelles ».
- `sans_prochaine_action` ⇔ 0 actionnable. Si 0 ouverte et F ≥ 1 : « Tout est fait : terminer le projet ? ».
- `a_l_arret` ⇔ ≥ 1 ouverte ∧ jours travaillés dans ]réf, aujourd'hui] ≥ N ; réf = max(dernier `fait_le` du projet, sous-tâches comprises ; `statut_depuis`). N = 10 par défaut, 5-30 (`Preference` `projet_arret_jours`). Exemple : dernière faite mar. 03/11, aujourd'hui mar. 17/11, lun-ven : 04, 05, 06, 09-13, 16, 17 = 10 → à l'arrêt ; 06/11 férié dans le calendrier société → 9 → non.
- `echeance_menacee` ⇔ `echeance` ∧ ≥ 1 ouverte ∧ : (a) `echeance` < aujourd'hui ; (b) k ouvertes datées (`jour_prevu` ou `echeance`) après elle ; (c) une section finit après elle ; (d) si F28 ≥ 5 (faites sur 28 jours calendaires, J28 jours travaillés de la fenêtre) : besoin = ⌈O × J28 / F28⌉ > reste = jours travaillés dans ]aujourd'hui, échéance]. Exemple : F28 = 8, J28 = 20, O = 12 → besoin 30, reste 15 → « Au rythme des 4 dernières semaines (8 faites en 20 jours travaillés), il faudrait 30 jours travaillés ; il en reste 15. »
- Écran : une icône « à surveiller » et une phrase par signal (ordre de la liste) ; aucun signal → rien.

**F. Priorité entre projets.**
- Classement du jour (socle §6) : élément « priorité projet » = `-(projet.priorite)` (Boîte = 0) ; projet focus = −3 sa semaine.
- En pause : tâches absentes de « Ma journée » et des propositions ; la confirmation de pause liste les k tâches datées.
- *Négligé* : d(P) = tâches de P faites sur les 14 derniers jours calendaires (tous niveaux). P actif, ≥ 1 actionnable, `statut_depuis` ≤ aujourd'hui − 14 : négligé ⇔ d(P) = 0 ∧ ∃ Q actif de priorité strictement inférieure avec d(Q) ≥ 1. Aucun seuil. Exemple : A (3), B (2), C (1), d = 0, 4, 1 → A seul ; tous à 0 ou même priorité → aucun. Phrase : « « A » (priorité haute) n'a rien vu avancer en 14 jours ; « C » (basse) a avancé de 1. » Sert la relance unique (socle §5) et la revue.
- Constat : « 7 projets actifs, 3 ont avancé ces 7 jours ».

**G. Modèles.** Enregistrer fige : objectif, sections (décalages), tâches comptées remises `a_faire` (titre, section, priorité, jalon, décalages `jour_prevu`/`echeance`, sous-tâches, liste de contrôle, prérequis par index) ; notes seulement si « Inclure les notes ». Origine = `date_debut`, sinon plus petite date du projet ; aucune date → décalages nuls. Récurrences non copiées. Instancier : `date_lancement` + décalage, même rectification que Décaler ; aperçu obligatoire (`apercu: true` puis `false`) ; Annuler = suppression douce du projet créé. Exemple : lancement lun. 23/11, J+5 → sam. 28/11 → lun. 30/11. Dupliquer = même moteur.

**H. Revue.** Une carte par projet actif (priorité décroissante, puis `rang`) : faites de la semaine (3 titres au plus), bloquées (« attend X »), prochaine action (première actionnable par `rang_projet`, « Changer », sinon champ d'ajout), santé, intention (200 car.), Garder / Pause / Terminer / Passer, case « Projet focus » (un par semaine). Stockée dans `RevueProjet`.

**I. Clôture.** `terminer` : `issue` ∈ {`atteint`, `abandonne`} obligatoire, `bilan` (280) facultatif, `taches_ouvertes` ∈ {`boite` (défaut), `annuler`, `deplacer` + `projet_cible_id`}. Pose `termine`, `termine_le`, `statut_depuis`. Statistiques lues, jamais recopiées. `archive` = rangé sans issue. Archive : recherche par nom, lecture seule, « Rouvrir » (→ actif, `issue` vidée, `bilan` gardé). Supprimer : suppression douce du projet et de ses tâches, « Supprimer le projet et ses n tâches ? », toast Annuler.

## 4. Données (ajouts au plancher, rien de renommé)

- `Projet` : `domaine` Char(40) blank ; `planifie_le` DateTime null ; `risque` Char(280) blank ; `issue` Char(10) ''/`atteint`/`abandonne` ; `bilan` Char(280) blank ; `statut_depuis` DateTime (posé à chaque changement de statut).
- `Tache` : `jalon` Bool False ; `bloquee_par` FK self null SET_NULL `related_name='bloque'` ; `source` += `modele`.
- `ModeleProjet` (TenantModel) : `proprietaire` FK CASCADE (# on_delete: données personnelles), `nom` Char(120), `contenu` JSON `{"v":1,…}`, `cree_depuis` FK Projet null SET_NULL ; contrainte `taches_modele_nom_uniq` (company, proprietaire, nom).
- `RevueProjet` (TenantModel) : `proprietaire`, `projet` FK CASCADE, `semaine` Date (lundi), `intention` Char(200), `prochaine_action` FK Tache null SET_NULL, `decision` ''/`garder`/`pause`/`terminer`/`passe`, `focus` Bool, `faites_semaine` SmallInt ; contraintes `taches_revueprj_uniq` (company, projet, semaine), `taches_revue_focus_uniq` (company, proprietaire, semaine) WHERE focus.
- Index `taches_tache_bloq_idx` (company, proprietaire, bloquee_par) ; `taches_tache_fait_idx` (socle) sert « négligé » et « à l'arrêt ».
- `Preference` : clé `projet_arret_jours`.

## 5. API (`/api/django/taches/` ; tout id reçu vérifié « même propriétaire », sinon 404)

| Route | Corps / réponse |
|---|---|
| `GET projets/?statut=actif\|en_pause\|archive_vue` | `[{"id":3,"nom":"Chantier Ait","domaine":"Chantiers","couleur":"vert","priorite":3,"statut":"actif","rang":2048,"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"…","donnees":{"jours":10,"depuis":"2026-11-03"}}],"lock_version":4}]` + `"constat":{"actifs":7,"avances_7j":3}` |
| `POST projets/` | `{"nom":"Chantier X"}` ; doublon → 400 `{"nom":["Un projet « Chantier X » existe déjà."]}` |
| `PATCH projets/{id}/` | `statut` ∈ actif/en_pause/archive ; `termine` → 400 `{"statut":["Passe par « Terminer »."]}` |
| `GET projets/{id}/vue/?vue=liste\|tableau\|chronologie` | sections + tâches, `avancement`, `sante`, `prochain_jalon`, `burnup` |
| `POST projets/{id}/planification/apercu/` | `{"texte":"…"}` ou `{"lignes":[…]}` → `{"sections":[{"nom":"Études","taches":[{"titre":"Visite","jalon":false,"sous_taches":[]}]}]}` ; n'écrit rien |
| `POST projets/{id}/planification/` (`Idempotency-Key`) | `{"objectif","echeance","risque","sections":[…],"actions":[{"titre","quand":"aujourdhui"}],"lock_version"}` |
| `POST projets/{id}/decaler/` | `{"delta_jours":7,"apercu":true}` → `{"changements":[{"objet":"tache","id":41,"champ":"jour_prevu","avant":"2026-11-20","apres":"2026-11-27"}]}` ; `false` applique + `annulation` ; 400 `{"delta_jours":["2 tâches passeraient avant aujourd'hui."]}` |
| `POST projets/{id}/decaler/annuler/` | `{"annulation":[…]}` ; valeur courante ≠ `apres` → 409 nommant l'objet |
| `POST projets/{id}/terminer/` · `/rouvrir/` · `/dupliquer/` `{"nom","date_debut"}` · `/enregistrer-modele/` `{"nom","inclure_notes"}` | §3.I, §3.G |
| CRUD `modeles/` ; `POST modeles/{id}/instancier/` | `{"nom","date_lancement","apercu":true}` |
| `PATCH taches/{id}/` | `bloquee_par` (400 `{"bloquee_par":["Boucle : « B » attend déjà « T »."]}`), `jalon` |
| `GET revue/projets/?semaine=` ; `PUT revue/projets/{projet_id}/` | `{"semaine","intention","prochaine_action_id","decision","focus"}` ; 2e focus → 400 `{"focus":["Déjà « A » cette semaine."]}` |

`GET aujourdhui/` gagne `a_trier.bloquees`. Contrats d'abord (PACT10) : `projets_liste.json`, `projet_vue.json` (étendu), `planification_apercu.json`, `decalage.json`, `revue_projets.json`, `modele_instancier.json`.

## 6. Écrans

- **Projets** : Boîte de réception, liste, constat, « + Nouveau projet » (bas d'écran iPhone), ⋯ (Trier par priorité, Archive, Modèles). Vide : « Aucun projet. Crée le premier, ou colle tes listes. » Chargement : `Skeleton`. Erreur : la liste reste, bandeau « Actualisation impossible ». Hors ligne : dernier état en lecture, écritures refusées avec message.
- **Projet** : en-tête (nom, objectif, échéance, « 12 sur 20 » via `ui/Progress.jsx`, santé, prochain jalon) ; `SelecteurVue` (`ui/SelecteurVue.jsx:5`) Liste / Tableau / Chronologie ; lien Calendrier.
  - Liste : sections repliables, « Faites (n) » repliées, ajout par section. Seul `@dnd-kit/core` est installé (`frontend/package.json:25`, pas `sortable`) : glisser à la manière de `pages/crm/leads/views/KanbanView.jsx:7`. iPhone : glisser seulement en « mode réorganiser », capteur tactile monté dans ce mode seul, `delay 300 / tolerance 5` (`KanbanView.jsx:262-287`) ; sinon menu « Déplacer vers… ».
  - Tableau : colonnes = sections + « Sans section », `features/kanban/usePanScroll.js:24`, `kanbanA11y.js:28` ; `collapsedColumns.js:10` est lié aux étapes CRM, pas réutilisable tel quel.
  - Chronologie : bureau = barres de phases, losanges de jalons, traits « aujourd'hui » et « échéance » ; iPhone = liste par date ; « Sans dates » à part ; toucher → feuille d'édition.
- **Planification** : `Sheet` plein écran iPhone, `ResponsiveDialog` bureau, « Passer » / « Suivant », dictée (`ui/DictationButton.jsx`).
- **Archive**, **Modèles**, **Revue** (une carte par écran iPhone).

## 7. Assistant (design-s3 : `internal`, carte-écho pour ce qui range)

- `taches.projet.planifier_apercu` → `planification/apercu/` avec `lignes` ; carte `plan_projet` (retirer, changer de section, « Tout ajouter » → `planification/` au doigt). Absente si projet `confidentiel`.
- `taches.projet.lire` → `projets/{id}/vue/` ; carte `projet` : avancement et phrases de santé lus ; aperçus de décalage et de clôture, appliqués au doigt. Aucune action ne termine, décale ou supprime seule.

## 8. Critères d'acceptation

1. Étant donné un projet actif sans tâche, Quand on lit `projets/`, Alors `a_planifier` = true ; après `planification/` avec 1 action, false.
2. Étant donné 12 faites, 8 ouvertes, 3 annulées et 2 sous-tâches, Quand on lit la vue, Alors `avancement` = `{"faites":12,"total":20}`.
3. Étant donné lun-ven sans férié, dernière faite le 03/11/2026, aujourd'hui 17/11/2026, N=10, 1 ouverte, Alors `a_l_arret` présent ; avec un `Holiday` le 06/11, absent.
4. Étant donné F28=8, J28=20, O=12, 15 jours travaillés restants, Alors `echeance_menacee` porte `{"besoin":30,"reste":15}` ; avec F28=4, le signal (d) est absent.
5. Étant donné A(3), B(2), C(1) actifs depuis 20 jours, d = 0, 4, 1, Alors seul A est négligé ; avec d = 0, 0, 0, aucun.
6. Étant donné T `bloquee_par` B ouverte et `jour_prevu` = aujourd'hui, Alors T absente de `aujourdhui/` et `a_trier.bloquees` = 1 ; Quand B est terminée, Alors T présente, `jour_prevu` et `reports` inchangés.
7. Étant donné B `bloquee_par` T, Quand PATCH T `bloquee_par`=B, Alors 400 sur `bloquee_par`.
8. Étant donné une tâche d'un autre utilisateur, Quand elle est citée en `bloquee_par`, `prochaine_action_id`, `projet_cible_id` ou dans `annulation`, Alors 404 et rien ne change (test de balayage).
9. Étant donné une échéance projet au 22/11/2026, Quand `decaler` Δ=7, Alors 30/11/2026, `reports` inchangés ; `decaler/annuler` restaure tout.
10. Étant donné une tâche `jour_prevu` = demain, Quand Δ=−2, Alors 400 sur `delta_jours`, rien ne change.
11. Étant donné un modèle avec une tâche J+5, Quand instancier au 23/11/2026 `apercu:true`, Alors 0 écriture et date 30/11/2026 annoncée ; `apercu:false` crée le projet.
12. Étant donné 3 ouvertes, Quand `terminer` `issue=atteint` sans `taches_ouvertes`, Alors elles vont dans la Boîte de réception ; sans `issue` → 400 sur `issue`.
13. Étant donné P en pause avec une tâche du jour, Alors elle est absente de `aujourdhui/` ; reprise → présente.
14. Étant donné « Études :\nVisite\n- photos\n◆ Mise en service », Quand `planification/apercu/`, Alors 1 section, « Visite » avec sous-tâche « photos », jalon « Mise en service », 0 écriture.
15. Étant donné deux PUT `revue/projets/` avec `focus` la même semaine, Alors le 2e → 400 sur `focus`.

## 9. Risques et gardes

- Fuite entre propriétaires (`bloquee_par`, `prochaine_action`, modèles) : `taches_de(user)` + test de balayage (socle §2.1).
- N+1 de la santé sur la liste : agrégats annotés ; `jours_ouvres_entre` fait deux requêtes quel que soit l'écart (`calendar_utils.py:167-172`).
- Fonctions ≤ 60 lignes : `sante.py`, `decalage.py`, `modeles.py` purs. PACT10/11.
- Autres propriétaires : `apps/agent/registry.py` (`CARTES` + `plan_projet`, `projet`), `apps/agent/contract_samples/assistant_reponse.json`, `frontend/src/features/ia/cartes/cartes.js`, `CartesDuMessage.jsx` — ajouts en fin de liste, après libération de la réservation `agent`. `calendar_utils.py` : lu seulement (déjà importé par `ventes`, `sav`, `stock`).

## 10. Choix par défaut et objections

**Choix par défaut.**
1. « À planifier » dérivé, pas un statut.
2. Domaine = libellé sur le projet, sans modèle.
3. N = 10 jours travaillés (deux semaines ouvrées, cadence de la revue), réglable : aucune source ne fixe N.
4. Projection seulement si F28 ≥ 5 : sinon le signal se tait plutôt que d'inventer un rythme.
5. Ouvertes d'un projet terminé → Boîte de réception : rien perdu, rien annulé en silence.
6. Une seule échéance ; l'appétit la remplit.
7. Aucun modèle fourni ; notes exclues des modèles par défaut.
8. Décalage calendaire ramené au jour travaillé suivant ; Annuler restaure l'avant exact.

**Objections au socle.** Aucune. Précisions : (1) « UN seul chemin déplace le jour prévu » (socle §4) est lu comme UN service : `decaler/` et `instancier/` l'appellent avec `compter_report=False`. (2) design-s2 §1 numérote 1 = haute ; le socle (3 = haute) prime.
