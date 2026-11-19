# Référence des RÈGLES — `apps/taches` (modules de code pur) — révision 3

Fait foi sur tout algorithme. Les NOMS (champs, valeurs, routes, fonctions) sont ceux de `donnees.md` et `api.md`
révision 3 ; les MOTS montrés sont ceux de `textes.md`. Primauté appliquée : socle §0/§8 → A1-A18 → référence
données/API (noms) → spec-7 r3.1 → `critique-finale.md`, `verif-plan-a-blanc.md` et les autres vérifications → specs. Chaque règle est déterministe, sans base, bibliothèque standard seule, fonctions
≤ 60 lignes logiques (`forme_code/fonction_neuve.py`).

## 0. Conventions communes

- **J** = `timezone.localdate()` dans le fuseau de la société (`Africa/Casablanca`) ; **maintenant** = heure murale
  locale. Toute fonction pure reçoit J et maintenant en argument, jamais l'horloge.
- **Jour travaillé** (pour lui) = jour ouvré de la société (`jours_ouvres_entre`, fériés compris) ∩
  `Preference.jours_travailles` − `Preference.conges`. Fourni aux fonctions pures sous forme d'ensemble
  `travailles` (un seul appel `jours_travailles_de` par lecture). Le mot montré est « travaillé », jamais « ouvré ».
- **Repère de test** (sauf mention) : mardi 17/11/2026 10:00 ; jours travaillés lun-ven ; projets du propriétaire
  Polydesign (id 3, actif, priorité 0), Maison (id 5, actif, étape Achats id 8) ; aucun autre. Pour la récurrence,
  fériés injectés 18/11/2026 et 01/01/2027 (annexe B d'origine) ; pour l'analyseur, aucun férié.
- **Arrondi** partout : `arrondir(x) = ceil(x − 0,5)` — « au plus proche, la demie vers le bas » (A2.3). Aucun autre
  arrondi n'existe dans le moteur.
- **Accord** : 0 et 1 au singulier (« 0 tâche », « 1 faite »), au-delà au pluriel.

### 0.1 Types d'entrée des modules purs (verif-plan M9 ; dataclasses `frozen=True`, bibliothèque standard)

Un test construit ces objets à la main ; la vue les construit depuis l'ORM (aucun module pur ne lit l'ORM). Les noms
sont ceux de `donnees.md` §2.

| Type | Champs (type) | Qui le reçoit |
|---|---|---|
| `ItemPur` | `type` (`'tache'`/`'activite'`), `id`, `statut`, `priorite`, `projet_id` (`int \| None`), `projet_priorite` (`int \| None`), `projet_rang` (`int \| None`), `focus` (bool, projet de la semaine), `section_id`, `parent_id`, `rang_projet`, `rang_jour` (`int \| None`), `jour_prevu`, `heure_debut`, `moment`, `echeance`, `echeance_heure` (`date`/`time \| None`), `quelque_jour`, `bloquee_par` (`int \| None` : id du prérequis encore ouvert, nul sinon), `triee_le` (`datetime \| None`), `estimation_minutes`, `duree_reelle_minutes` (`int \| None`), `reports`, `reports_tranches`, `fait_le` (`datetime \| None`, heure locale), `routine`, `recurrente`, `jalon`, `confidentielle` (bool), `created_at` (datetime) | `placer`, `cle_tri`, `proposer_plan`, `classer_priorites`, `capacite`, `compte_du_jour`, `tuile_pure`, `evenements_flux`, `sante.*` |
| `LignePure` | `tache_id`, `activite_id` (`int \| None`), `prevue_au_plan`, `faite`, `reportee`, `essentielle` (bool), `creneau` (`Creneau`), `rang` (`int \| None`) | `placer`, constats C1-C2 |
| `PlanPur` | `jour`, `planifie_le`, `cloture_le`, `allege_le` (`datetime \| None`), `objectif_du_jour` (`int \| None`), `lignes` (`tuple[LignePure]`) | `placer`, `proposer_plan` (`allege_le`), §4.10 |
| `EtatRythme` | `mode`, `comprendre_mon_rythme`, `palier`, `palier_source`, `bloc_debut`, `refus_montee`, `blocs_a_sauter`, `echec_n`, `baisse_refusee`, `essai_restant`, `meilleur_tenu`, `echec_niveau`, `ref_taille_min`, `echec_le`, `tenir_fixee_le`, `tenir_silence_jusquau`, `tenir_reference` (`float \| None`), `pauses_sollicitations` (`tuple[str]`) — mêmes noms que `ReglagesRythme` §2.10 — + `objectif` (`int \| None`, en vigueur) | `rythme.*` (rend un `EtatRythme` neuf par `dataclasses.replace`) |
| `JourCompte` | `jour`, `statut_jour` (`StatutJour`), `compte`, `essentiels_choisis`, `essentiels_faits`, `plan_prevues`, `plan_faites` (`int`) | `evaluer_bloc`, `reference_tenir`, `derive_tenir`, `palier_initial`, `constats`, `semaine_courte`, `retour_absence` (chronologique) |
| `RendezVousPur` | `cle` (str), `agenda_id`, `titre`, `debut`, `fin` (`datetime`, heure locale), `journee_entiere` (bool) | `minutes_rendez_vous`, Prévu, Agenda |
| `Fenetre` | `debut`, `fin` (`time`) | `minutes_rendez_vous`, `due` |
| `Analyse` | `titre`, `jetons` (tuple de `{type, source, debut, fin, valeur, libelle}`), `champs` (dict LIGNE de `api.md` §4), `alertes` (tuple d'`AlerteSaisie`) | `analyser` (sortie), `decouper_collage` |
| `PlanPropose` | `pour_objectif` (tuple de (`ItemPur`, `RaisonPropose`)), `reste_nb`, `suite_par_projet` (tuple de (`projet_id \| None`, tuple d'`ItemPur`)), `charge` (dict), `replie` (bool) | sortie de `proposer_plan` |

`saisie/dates_pures.py` (partagé par l'analyseur et la récurrence) : `prochain_jour_semaine(d, jour_semaine, inclure=False)`
· `ajouter_mois(d, n)` (quantième borné) · `fin_de_mois(d)` · `prochaine_date_sans_annee(jj, mm, J)` · `n_ieme_jour_du_mois(annee,
mois, jour_semaine, rang)` (−1 = dernier) · `semaine_iso(d)`.

## 1. L'analyseur de saisie — `apps/taches/saisie.py`

### 1.1 Normalisation (`normaliser(texte)`) — copie d'analyse, même longueur que l'original

| Étape | Règle | Source |
|---|---|---|
| Apostrophes | `’` U+2019, `‘` U+2018, `ʼ` U+02BC, `′` U+2032 → `'` | verif-specs-2-3 M12 |
| Espaces | U+00A0, U+202F, U+2007, U+2009 → espace ; tabulation → espace APRÈS la mesure du retrait (§1.10) | M12 |
| Traits d'union | U+2010, U+2011 → `-` (« après‑demain ») | IR3 |
| Casse | minuscule caractère par caractère ; un caractère dont la minuscule change de longueur (İ, ẞ) est laissé tel quel | IR3 |
| Accents | lettre accentuée → lettre de base (premier caractère de sa forme NFD), longueur conservée ; `œ`, `æ` intacts | spec-2 §3.1 r2 |

La copie normalisée sert à reconnaître ; le **titre** est découpé dans le texte ORIGINAL aux mêmes positions (il
garde `’`, les accents et la casse), espaces fusionnés en une espace ASCII, bords rognés. `cle_nom(nom)` = normaliser
+ retrait des espaces, `-`, `_` (I2) : sert `#nom`, l'unicité des projets, étapes, étiquettes, et les doublons.

### 1.2 Ce qui n'est jamais lu

1. Tout ce qui est entre `"…"`, `«…»`, `“…”` (masqué avant la recherche ; les guillemets restent dans le titre).
2. Un nombre nu (« Rapport 2026 », « le 5 »), un mois sans quantième (« novembre »), « daily / weekly / monthly »
   seuls, `!` seul (« Karim ! »), `!!!!` (quatre ou plus), `#` ou `%` suivis d'un chiffre (« facture #12 », « 10% »).
3. Un jeton qui n'est pas sur des frontières de mot (`demainx`, `p12`).
4. Une date impossible (« 31/11 », « 30 février ») : elle reste du texte, alerte `date_invalide` (IR4).
5. Une durée hors [5, 960] minutes (« 2 min », « 20h de route ») : reste du texte, alerte `duree_hors_bornes`.
6. Un jeton listé dans `ignorer = [{type, source}]` (effet du × sur sa puce).
7. Les mots d'un titre qui ne sont pas en position de jeton : voir les règles de contexte §1.4 (moments, midi).
8. Porte `capture` : les types interdits par A1 (§1.8) restent du texte.

### 1.3 Grammaire complète (français et anglais lus ensemble, sans détection de langue)

| Type (`jetons[].type`) | Français | Anglais | Valeur → champ |
|---|---|---|---|
| `jour` relatif | aujourd'hui, demain, après-demain | today, tomorrow | J, J+1, J+2 → `jour_prevu` |
| `jour` de semaine | lundi…dimanche [prochain], le lundi | monday…sunday, next monday, on monday | prochaine date de ce jour, **J exclu** (dit un lundi : J+7) |
| `jour` période | semaine prochaine ; ce week-end, ce weekend ; fin de semaine | next week ; this weekend ; end of week | lundi suivant (J exclu) ; J si J est samedi ou dimanche, sinon samedi suivant ; vendredi de la semaine courante (J si J est vendredi), samedi/dimanche → vendredi suivant |
| `jour` décalage | dans N jour(s) / semaine(s) / mois (N ≥ 1) | in N day(s) / week(s) / month(s) | J+N ; J+7N ; même quantième N mois plus tard, borné à la fin du mois |
| `jour` date | [le] JJ/MM[/AAAA], [le] JJ mois [AAAA], [le] 1er mois | DD MMM, MMM DD, AAAA-MM-JJ | **jour d'abord** ; sans année : prochaine date ≥ J ; avec année passée : gardée + alerte `date_passee` |
| `jour` fin de mois | fin de mois | end of month | dernier jour du mois courant (J si c'est aujourd'hui) |
| `heure` | à 15h, 15h, 15 h, 15h30, 15 h 30, 15:30, à 15 heures, à midi | at 3pm, 3pm, 3:30pm, 15:30, at noon | `heure_debut` ; `Nh` nu seulement si 7 ≤ N ≤ 23 ; `NhMM` nu seulement si 5 ≤ N ≤ 23 (IR5) |
| `moment` | ce matin, cet après-midi, ce soir ; matin, après-midi, soir (contexte §1.4) | this morning, this afternoon, this evening, tonight ; morning, afternoon, evening, in the morning… | `moment` ; ce/cet/this/tonight posent J |
| `echeance` | pour / avant / d'ici + date [heure], ou + heure seule | due / by / for / deadline + date [heure], ou + heure | `echeance`, `echeance_heure` ; `jour_prevu` intact |
| `quelque_jour` | « un jour » ou « en réserve » en fin de ligne | someday (partout) | `quelque_jour = true` (montré « En réserve ») |
| `projet` | `#mot` (lettre après `#`, `_` = espace, tiret permis) | idem | §1.9 |
| `section` | `/mot` après un `#projet` de la même ligne | idem | étape existante (par `cle_nom`), sinon créée |
| `priorite` | `!!` = 2, `!!!` = 3 ; `p1` = 3, `p2` = 2, `p3` = 1 | idem | `priorite` |
| `etiquette` | `%mot` (lettre après `%`) | idem | existante (par `cle_nom`), sinon créée |
| `duree` | N min, N mn, N minutes, ~Nm, ~Nh ; `Nh`/`NhMM` nus si N ≤ 6 (NhMM : N ≤ 4) ; après « pendant / durée » : Nh, NhMM, N heures jusqu'à 16 h ; après « pour » : formes ≤ 6 h | N min, ~30m, N hours ; après « for » : formes ≤ 6 h ; après « during » : jusqu'à 16 h | `estimation_minutes`, borné 5-960 |
| `recurrence` | tous les [N] jours ; chaque lundi ; tous les lundis [et jeudis] ; toutes les N semaines ; chaque jour ouvré, chaque jour travaillé, en semaine ; chaque mois [le J] ; tous les N mois ; chaque fin de mois ; chaque premier / deuxième / troisième / quatrième / dernier vendredi ; chaque année ; suffixe « après fait » | every [N] day(s), every monday, every weekday, every N weeks, every month [on the J], every N months, every year ; `every!` = après fait | `RegleRecurrence` (§2) ; 1re occurrence → `jour_prevu` |
| `rappel` | rappel [date] [à] heure ; rappelle-moi [date] [à] heure | remind [me] [date] at heure | `rappel` (§1.6) |

Ambiguïtés tranchées : « 5/6 » = 5 juin (jamais 6 mai, même en anglais : choix Maroc) ; « 2h » = durée, « à 2h » =
heure ; « pour / for » + durée = durée, + date ou heure = échéance (« pour 15h » = échéance J 15:00, « pour 9h » à
10:00 = échéance J+1 09:00 + `heure_passee`) ; « pendant 8h » = durée 480 ; « 15h » nu = heure ; « 6h30 » nu = heure
06:30, « 1h30 » nu = durée 90.

### 1.4 Règles de contexte (lues dans la copie normalisée)

- **Moment nu** (matin, après-midi, soir, morning, afternoon, evening) : lu seulement s'il suit immédiatement un
  jeton `jour` (« demain matin », « lundi soir », « tomorrow morning »), OU s'il finit la ligne et n'est précédé ni
  de « du, de, d', le, la, au, the, of ». « Préparer le soir de gala », « Réunion du matin » : rien lu.
- **midi / noon** : lus seulement après « à / at » ou juste après un jeton `jour`.
- **Heure et moment** : un moment `apres_midi` ou `soir` (posé par la phrase) ajoute 12 h à une heure 1-11
  (« ce soir 9h » → 21:00). L'heure prime ensuite : `moment` = dérivé de l'heure (< 12 h `matin`, < 18 h
  `apres_midi`, sinon `soir`, invariant 15) même si la phrase disait autre chose.
- **Frontières** : `#`, `/`, `%`, `!` n'ouvrent un jeton qu'en début de mot ; `!!`/`!!!` ne doivent pas être suivis
  d'un `!`.

### 1.5 Choisir les jetons (sans chevauchement)

1. Tous les candidats `(debut, fin, type, source)` sont trouvés dans la copie masquée.
2. Tri : `debut` croissant, puis longueur décroissante, puis ordre des types : `recurrence` > `rappel` >
   `echeance` > `duree` > `heure` > `jour` > `moment` > `quelque_jour` > `projet` > `section` > `priorite` >
   `etiquette`.
3. Parcours : un candidat qui chevauche un candidat retenu est écarté ; un type déjà retenu → le second reste du
   texte et l'alerte `deux_<type>` est posée (« Appeler demain et vendredi » : `deux_jour`, titre « Appeler et
   vendredi »).
4. Titre = original moins les jetons retenus, espaces fusionnés. Titre vide → erreur `titre` « Le titre est vide une
   fois la date et le projet retirés. » (imbriquée par ligne).

### 1.6 Assembler (dérivations, dans cet ordre)

1. `recurrence` présente → `jour_prevu` = `premiere_occurrence(regle)` (prime sur tout jeton `jour`, qui reste texte
   avec `deux_jour`) ; `date_debut` = J.
2. `heure` sans jour : J si heure > maintenant (strictement), sinon J+1 + alerte `heure_passee` ; si le moment
   commence par ce/cet/this/tonight : J, et `heure_passee` si l'heure est passée. Avec un jour venu d'une
   récurrence ou d'un jeton : le jour ne bouge pas ; `heure_passee` si jour = J et heure ≤ maintenant.
3. `echeance` avec heure seule : même règle que 2 (J ou J+1). `echeance_heure` n'existe jamais sans `echeance`.
4. `moment` dérivé de l'heure quand une heure est posée (§1.4).
5. `rappel` : avec sa propre date → `{jour, heure}` absolu ; sans date et `jour_prevu` posé → `{ancre:"jour_prevu",
   decalage_jours:0, heure}` ; sans date ni jour prévu → jour = J si heure à venir, sinon J+1, absolu, ET
   `jour_prevu` = ce jour (A14-M6).
6. Projet, étape, étiquettes (§1.9). Priorité absente → 0.
7. `triee_le` : posé par `creer_taches()` dès qu'un projet, un jour (`jour_prevu`) ou « En réserve » est reconnu,
   par toute porte (invariant 1). Une échéance seule ne range PAS la tâche (elle reste À trier).

### 1.7 Bornes

| Champ | Borne | Hors borne |
|---|---|---|
| `estimation_minutes` | 5-960 partout (validation unique) ; redimensionnement de bloc à l'agenda par pas de 15, dans [15, 960] | analyseur : non lu ; PATCH : 400 `{"estimation_minutes":["Entre 5 et 960 minutes."]}` |
| `titre` | 1-280 caractères après retrait des jetons | 400 par ligne |
| récurrence `intervalle` | 1-99 | non lu |
| `jour_du_mois` | 1-31 ou −1 | non lu |
| texte collé | 200 lignes, 20 000 caractères (2 000 par le Copilote), 10 collages par aperçu | 400 sur `texte` |
| nouveaux projets | 10 par envoi | 400 `{"texte":["10 nouveaux projets au plus par envoi."]}` |

### 1.8 Portes (`analyser(…, porte)`)

| Porte | Types lus | Effets propres |
|---|---|---|
| `rapide` (`saisie-rapide/`) | tous | nouveau projet, étape, étiquette créés ; aperçu sans écriture |
| `capture` (`capture/`, jeton) | `jour`, `heure`, `moment`, `echeance`, `priorite`, `duree`, `projet` EXISTANT (A1) — par `#nom` ou par « projet <nom> » / « project <nom> » EN TÊTE (le plus long nom de projet existant qui suit, comparé par `cle_nom`) | jamais de création de projet, d'étape, d'étiquette, de récurrence, de rappel ; « un jour / en réserve » non lu (A15) ; `#inconnu` et « projet <inconnu> » restent du texte ; rien reconnu → À trier |
| `assistant` (lignes du Copilote) | la ligne SOURCE est analysée en `rapide` ; le `titre` envoyé par le modèle est ignoré | ≤ 3 écritures par tour ; tour marqué (toute lecture ou texte collé, §12 « Garde A5 ») → carte à valider |

Réponse de la capture : `dans` = `journee` si un jour est posé (quel qu'il soit), `projet` si un projet sans jour,
`a_trier` sinon — une échéance seule laisse la tâche dans À trier (invariant 1) ; message lu par Siri : `textes.md` §7.

### 1.9 Projet par la saisie

- `#nom` : comparaison par `cle_nom` aux projets `actif` et `en_pause` du propriétaire. Plusieurs → premier par
  `rang`, alerte `plusieurs_projets`. Un `termine`/`archive` → puce « Projet archivé : X », tâche À trier sauf tap
  « Réactiver X » (alerte `projet_archive`).
- Aucun (porte `rapide`) → « Nouveau projet : X » : le projet naît avec la tâche, `priorite` 2 « Moyenne » (A16-M3,
  A17-M3 : puce modifiable dans l'aperçu et dans la liste), couleur d'office = `couleur_d_office(user)` (seule
  fonction, `services/creation.py`, aussi pour `POST projets/`) : première clé de `Couleur` (10 clés, A15) absente des
  projets actifs, sinon la moins utilisée, égalité → ordre de l'énumération (spec-4 §A, IR6) ;
  `rang` au milieu entre le dernier actif de priorité ≥ 2 et le suivant (spec-4 §A). Annuler la saisie supprime la tâche ET le projet né
  vide (`soft_delete(record=False)`).
- Étape `/nom` : `get_or_create` par (`projet`, `nom_cle`) (contrainte `taches_section_nom_uniq`).

### 1.10 Coller une liste (`decouper_collage(textes, …)`)

1. Découpe par lignes ; le RETRAIT est mesuré avant normalisation (tabulation = 4 espaces).
2. Retirées : lignes vides ou de ponctuation seule ; puces de tête `- * • – — · N. N) [ ] ☐ □`.
3. `[x] [X] ✓ ✔ ☑` en tête → ligne « déjà faite », décochée dans l'aperçu.
4. **Titre de groupe** : ligne finissant par « : » suivie d'au moins une ligne → pas une tâche ; les lignes
   suivantes, jusqu'au titre suivant, prennent ce projet (§1.9) sauf `#` propre.
5. **Première ligne = projet (A14-M9)**, PAR collage (`textes[i]` → l'élément de `projets_communs[]` d'index
   `collage = i`, champ `collage` sur chaque ligne de l'aperçu) : la première ligne retenue est proposée comme projet
   commun de son collage (`source = "premiere_ligne"`, `priorite` 2) si (a) elle n'est pas un titre de groupe, (b) elle n'avait ni puce
   ni case, (c) aucun jeton n'y est reconnu, (d) ≤ 60 caractères, (e) au moins deux lignes la suivent. Projet
   existant par `cle_nom` → `nouveau:false`, sinon « Nouveau projet : … ». Un tap la rend tâche.
6. **Retrait** : ligne plus en retrait que la précédente (≥ 2 espaces de plus) → point de check-list de la dernière
   ligne non en retrait (bascule « En faire des sous-tâches »).
7. Chaque ligne passe par `analyser` (porte `rapide`) ; le projet commun de SON collage vaut pour ses lignes sans
   projet.
8. **Doublon** : `cle_nom(titre)` égale à celle d'une tâche ouverte du propriétaire (`doublon_de` = son id) ou d'une
   autre ligne du collage → décochée.
9. **Projet suggéré sans IA** : exactement un nom de projet actif (≥ 4 caractères) contenu comme mot entier dans le
   titre → puce « Projet suggéré : X », non appliquée tant qu'il ne la touche pas.

**Liste collée de « Planifier le projet »** (`planification/apercu/`, spec-4 §B) — autre grammaire, même module :
ligne finissant par « : » = étape ; lignes suivantes = tâches ; « - » ou « * » sous une tâche = sous-tâche ; « ◆ »
ou « jalon: » en tête = jalon ; vides ignorées ; 200 lignes au plus. Rien n'est analysé en dates.

### 1.11 Table de test (critère : `analyser` rend exactement ces champs ; vide = nul, 0 ou absent)

Colonnes : Jour = `jour_prevu` · H·M = `heure_debut` · `moment` · Éch. = `echeance` [`echeance_heure`] · Proj. ·
Prio · Autre. Repère §0. Les lignes **en gras** sont corrigées par rapport à l'annexe A d'origine.

| # | Saisie | Titre | Jour | H·M | Éch. | Proj. | Prio | Autre |
|---|---|---|---|---|---|---|---|---|
| A1 | Appeler Karim demain | Appeler Karim | 18/11 | | | | 0 | |
| A2 | Call Karim tomorrow | Call Karim | 18/11 | | | | 0 | |
| A3 | Envoyer le devis lundi #Polydesign | Envoyer le devis | 23/11 | | | 3 | 0 | |
| A4 | Relancer banque lundi prochain | Relancer banque | 23/11 | | | | 0 | |
| A5 | Send invoice next monday | Send invoice | 23/11 | | | | 0 | |
| A6 | Payer CNSS dans 3 jours | Payer CNSS | 20/11 | | | | 0 | |
| A7 | Review contract in 3 days | Review contract | 20/11 | | | | 0 | |
| **A8** | Réunion fournisseur 25/11 à 15h | Réunion fournisseur | 25/11 | 15:00 · apres_midi | | | 0 | moment dérivé |
| A9 | Rapport TVA fin de mois !!! | Rapport TVA | 30/11 | | | | 3 | |
| A10 | Rapport TVA pour fin de mois | Rapport TVA | | | 30/11 | | 0 | |
| A11 | Préparer offre ce soir | Préparer offre | 17/11 | · soir | | | 0 | |
| A12 | Lire contrat demain matin | Lire contrat | 18/11 | · matin | | | 0 | |
| **A13** | Call supplier at 3pm | Call supplier | 17/11 | 15:00 · apres_midi | | | 0 | |
| **A14** | Point équipe 9h | Point équipe | 18/11 | 09:00 · matin | | | 0 | `heure_passee` |
| A15 | Écrire article 2h | Écrire article | | | | | 0 | durée 120 |
| A16 | Trier emails 30 min | Trier emails | | | | | 0 | durée 30 |
| A17 | Prepare slides for 2h | Prepare slides | | | | | 0 | durée 120 |
| A18 | Dossier subvention pour vendredi | Dossier subvention | | | 20/11 | | 0 | |
| A19 | Finish report due friday 15:00 | Finish report | | | 20/11 15:00 | | 0 | |
| A20 | Préparer visite jeudi pour vendredi | Préparer visite | 19/11 | | 20/11 | | 0 | |
| A21 | Arroser plantes tous les 2 jours | Arroser plantes | 17/11 | | | | 0 | quotidien n=2 calendrier |
| A22 | Rapport hebdo chaque lundi #Polydesign | Rapport hebdo | 23/11 | | | 3 | 0 | hebdo `1000000` |
| A23 | Check bank every weekday | Check bank | 17/11 | | | | 0 | jours_ouvres |
| A24 | Payer loyer chaque mois le 5 | Payer loyer | 05/12 | | | | 0 | mensuel J=5 |
| **A25** | Changer filtre tous les 3 mois après fait | Changer filtre | 17/11 | | | | 0 | mensuel n=3 apres_fait |
| A26 | Water plants every! 3 days | Water plants | 17/11 | | | | 0 | quotidien n=3 apres_fait |
| A27 | Acheter câbles #Maison /Achats %magasin | Acheter câbles | | | | 5 (étape 8) | 0 | étiquette « magasin » (créée si absente) |
| A28 | Maquette #SiteWeb !! | Maquette | | | | nouveau « SiteWeb » (projet priorité 2) | 2 | |
| A29 | Plan lancement #Nouveau_site p1 | Plan lancement | | | | nouveau « Nouveau site » (projet priorité 2) | 3 | |
| A30 | Lire « Demain dès l'aube » | Lire « Demain dès l'aube » | | | | | 0 | guillemets : rien lu |
| A31 | Rappeler Ali 5/6 | Rappeler Ali | 05/06/2027 | | | | 0 | sam. 5 juin 2027 |
| A32 | Meeting 3/1 | Meeting | 03/01/2027 | | | | 0 | |
| A33 | Appeler Karim demain rappel 9h | Appeler Karim | 18/11 | | | | 0 | rappel ancre `jour_prevu`, 0, 09:00 |
| A34 | Envoyer rapport monthly | Envoyer rapport monthly | | | | | 0 | mot seul non lu |
| A35 | Remise 10% pour facture #12 ! | Remise 10% pour facture #12 ! | | | | | 0 | rien lu |
| A36 | Dîner ce soir 9h | Dîner | 17/11 | 21:00 · soir | | | 0 | +12 h |
| A37 | Apprendre l'arabe classique un jour | Apprendre l'arabe classique | | | | | 0 | `quelque_jour` |
| **A38** | Fix bug Nov 25 at 10am | Fix bug | 25/11 | 10:00 · matin | | | 0 | |
| A39 | Inventaire ce week-end | Inventaire | 21/11 | | | | 0 | |
| E1 | Email the accountant tomorrow at 9am #Polydesign | Email the accountant | 18/11 | 09:00 · matin | | 3 | 0 | |
| E2 | Book flight to London next friday | Book flight to London | 20/11 | | | | 0 | |
| E3 | Call Lydec this afternoon | Call Lydec | 17/11 | · apres_midi | | | 0 | |
| E4 | Pay rent every month on the 5 | Pay rent | 05/12 | | | | 0 | mensuel J=5 |
| E5 | Review slides in 2 weeks p2 | Review slides | 01/12 | | | | 2 | |
| E6 | Prepare offer due Nov 30 !!! | Prepare offer | | | 30/11 | | 3 | |
| E7 | Gym every weekday at 7am | Gym | 17/11 | 07:00 · matin | | | 0 | jours_ouvres ; `heure_passee` (la récurrence fixe le jour) |
| E8 | Send quote to Karim by end of week | Send quote to Karim | | | 20/11 | | 0 | |
| E9 | Meeting with bank 2026-12-03 at 14:30 | Meeting with bank | 03/12 | 14:30 · apres_midi | | | 0 | |
| E10 | Appeler Karim tomorrow 10 h | Appeler Karim | 18/11 | 10:00 · matin | | | 0 | « 10 h » avec espace |
| E11 | Relancer devis Settat tomorrow due friday #Polydesign | Relancer devis Settat | 18/11 | | 20/11 | 3 | 0 | |
| E12 | Prepare slides for 2h tomorrow morning | Prepare slides | 18/11 | · matin | | | 0 | durée 120 |
| E13 | Lunch at noon | Lunch | 17/11 | 12:00 · apres_midi | | | 0 | |
| E14 | Learn Spanish someday | Learn Spanish | | | | | 0 | `quelque_jour` |
| E15 | Call mum tomorrow remind me at 18:00 | Call mum | 18/11 | | | | 0 | rappel ancre `jour_prevu`, 0, 18:00 |
| E16 | Change filter every 3 months | Change filter | 17/11 | | | | 0 | mensuel n=3, J=17, calendrier |
| P1 | Réunion 5/6 à 9h | Réunion | 05/06/2027 | 09:00 · matin | | | 0 | 5 juin, jamais 6 mai |
| P2 | Appel client 15h | Appel client | 17/11 | 15:00 · apres_midi | | | 0 | « 15h » nu = heure |
| P3 | Réviser 15 min | Réviser | | | | | 0 | durée 15 |
| P4 | Atelier pendant 3h | Atelier | | | | | 0 | durée 180 |
| P5 | Rapport pour 9h | Rapport | | | 18/11 09:00 | | 0 | `heure_passee` |
| P6 | Rapport pour 6h | Rapport | | | | | 0 | durée 360 |
| P7 | Réunion lundi *(repère lun. 23/11 10:00)* | Réunion | 30/11 | | | | 0 | J exclu |
| P8 | Dîner mardi soir *(repère mar. 17/11)* | Dîner | 24/11 | · soir | | | 0 | dit un mardi : J+7 ; « ce soir » pour aujourd'hui |
| P9 | Bilan fin de semaine *(repère ven. 20/11)* | Bilan | 20/11 | | | | 0 | |
| P10 | Lire Demain dès l'aube | Lire dès l'aube | 18/11 | | | | 0 | sans guillemets : lu (× sur la puce pour annuler) |
| P11 | Préparer le soir de gala | Préparer le soir de gala | | | | | 0 | moment nu après « le » : non lu |
| P12 | Réunion du matin | Réunion du matin | | | | | 0 | non lu |
| P13 | Train 6h30 demain | Train | 18/11 | 06:30 · matin | | | 0 | NhMM nu ≥ 5 = heure |
| P14 | Appel 1h30 | Appel | | | | | 0 | durée 90 |
| P15 | Appeler aujourd’hui *(U+2019)* | Appeler | 17/11 | | | | 0 | |
| P16 | Payer le 1er décembre | Payer | 01/12 | | | | 0 | |
| P17 | Payer facture le 31/11 | Payer facture le 31/11 | | | | | 0 | date impossible : texte, `date_invalide` |
| P18 | Point 10 h 30 demain | Point | 18/11 | 10:30 · matin | | | 0 | |
| P19 | Facture #12 pour demain | Facture #12 | | | 18/11 | | 0 | |
| P20 | Karim ! demain | Karim ! | 18/11 | | | | 0 | |
| P21 | Appeler demain et vendredi | Appeler et vendredi | 18/11 | | | | 0 | `deux_jour` |
| P22 | Déjeuner à midi | Déjeuner | 17/11 | 12:00 · apres_midi | | | 0 | |
| P23 | Trier emails 2 min | Trier emails 2 min | | | | | 0 | durée < 5 : texte, `duree_hors_bornes` |
| P24 | Appeler 3pm demain | Appeler | 18/11 | 15:00 · apres_midi | | | 0 | |
| P25 | Call May 5 | Call | 05/05/2027 | | | | 0 | |
| C1 | *capture* Lait demain #Maison %magasin rappel 9h | Lait %magasin rappel | 18/11 | 09:00 · matin | | 5 | 0 | `%`, rappel non lus ; `dans:"journee"` |
| C2 | *capture* Appeler Karim un jour | Appeler Karim un jour | | | | | 0 | « un jour » non lu ; `dans:"a_trier"` |
| C3 | *capture* Maquette #SiteWeb | Maquette #SiteWeb | | | | | 0 | projet inconnu : texte ; `a_trier` |
| C4 | *capture* appeler le fournisseur demain 10 h | appeler le fournisseur | 18/11 | 10:00 · matin | | | 0 | Siri : « Ajouté pour demain 10 h : appeler le fournisseur » |
| C5 | *capture* projet Maison acheter du lait demain | acheter du lait | 18/11 | | | 5 | 0 | « projet <nom> » en tête ; `dans:"journee"` |
| C6 | *capture* Rapport pour vendredi | Rapport | | | 20/11 | | 0 | échéance seule : `dans:"a_trier"` |

Total : 39 (annexe A, dont 5 corrigées) + 16 anglaises et mixtes + 25 pièges + 6 captures = **86 phrases**.

### 1.12 Découpage du code (≤ 60 lignes logiques par fonction)

`normaliser` · `masquer_guillemets` · `MOTIFS = [(type, regex, convertisseur)]` (table, pas une fonction) ·
`candidats(masque, porte)` · `filtrer_contexte(cands, masque)` (§1.4, nus, bornes) · `choisir(cands)` (§1.5) · un
convertisseur par type (`conv_jour`, `conv_heure`, `conv_moment`, `conv_echeance`, `conv_duree`, `conv_recurrence`,
`conv_rappel`, `conv_priorite`, `conv_projet`, `conv_section`, `conv_etiquette`) · `assembler(choisis, texte,
contexte)` (§1.6, appelle `deriver_heure`, `deriver_rappel`) · `analyser` (orchestration ≤ 25 lignes) ·
`decouper_collage` (appelle `nettoyer_ligne`, `est_titre_groupe`, `projet_premiere_ligne`, `marquer_doublons`) ·
`decouper_plan`. Les dates passent par `saisie/dates_pures.py` (fonctions nommées au §0.1), partagé avec la récurrence.

## 2. La récurrence — `apps/taches/moteur/recurrence.py`

`prochaine_occurrence(regle, occurrence_du, aujourdhui, fait_le, est_ouvre) -> date | None`, pure ;
`est_ouvre(d)` injecté (production : `is_jour_ouvre(d, company)`, bitmask + fériés). `premiere_occurrence(regle)` ;
`libelle_regle(regle)` (textes : `textes.md` §2.10).

- **Séries** : `quotidien` = début + k·n jours ; `jours_ouvres` = jours où `est_ouvre` (le seul type qui consulte
  les fériés) ; `hebdo` = jours du masque dont la semaine (comptée depuis le lundi de `date_debut`) est multiple de n ;
  `mensuel` = quantième borné à la fin du mois (−1 = dernier jour ; absent = quantième de `date_debut`), ou N-ième /
  dernier jour de semaine (`rang_dans_mois` avec un seul jour au masque), tous les n mois ; `annuel` = jour et mois de
  `date_debut`, 29/02 → 28/02 les années non bissextiles (retour au 29/02 les années bissextiles).
- **Première occurrence** = première date de la série ≥ `date_debut` (`apres_fait` : `date_debut`).
- **`calendrier`** : suivante = première date de la série **> max(occurrence_du, aujourdhui)** (avance, retard, saut :
  jamais de pile).
- **`apres_fait`** : depuis la date locale de `fait_le` : + n jours ; + n jours ouvrés ; `hebdo` = premier jour du
  masque ≥ fait + 7n − 6 (IR8) ; + n mois bornés au quantième de `fait_le` (le décalage s'enchaîne : 31/01 → 28/02 →
  28/03) ; + n ans bornés.
- Au-delà de `date_fin` → `None` et `actif = False`. Une seule occurrence ouverte (invariant 5) ; une manquée reste
  seule. Sauter = occurrence `annule` + suivante. Modifier la règle vaut pour la suivante ; `appliquer_a_l_ouverte`
  recale l'ouverte sur la première date ≥ J. Arrêter = `actif = False`. Rouvrir supprime (`record=False`) la suivante
  née si sa `lock_version` n'a pas bougé.
- **Routine** (compte du rythme 0, puce « routine ») ⇔ `frequence ∈ {quotidien, jours_ouvres}` ET `intervalle = 1`.

**Les 25 cas datés (annexe B d'origine, recalculés exacts par `verif23/recurrence.py`, 25/25, relancé dans cette
session) — repris tels quels.** Fériés injectés 18/11/2026 et 01/01/2027.

| # | Règle | Occurrence ouverte | Fait / sauté le | Suivante attendue |
|---|---|---|---|---|
| B1 | hebdo lundi, calendrier, créée mar 17/11 | — (création) | — | lun 23/11/2026 |
| B2 | idem | lun 23/11 | 23/11 | lun 30/11/2026 |
| B3 | idem, en avance | lun 23/11 | sam 21/11 | lun 30/11/2026 |
| B4 | idem, en retard | lun 23/11 | mer 02/12 | lun 07/12/2026 (aucune pile) |
| B5 | idem, sautée | lun 23/11 | sauté mar 17/11 | lun 30/11/2026 |
| B6 | mensuel J=31, créée 17/11 | — | — | lun 30/11/2026 |
| B7 | mensuel J=31 | dim 31/01/2027 | 31/01 | dim 28/02/2027 |
| B8 | mensuel J=31 | dim 28/02/2027 | 28/02 | mer 31/03/2027 |
| B9 | chaque fin de mois (J=−1) | lun 30/11/2026 | 30/11 | jeu 31/12/2026 |
| B10 | jours ouvrés, calendrier | mar 17/11 | 17/11 | jeu 19/11/2026 (18/11 férié) |
| B11 | jours ouvrés | ven 20/11 | 20/11 | lun 23/11/2026 |
| B12 | jours ouvrés | jeu 31/12/2026 | 31/12 | lun 04/01/2027 |
| B13 | quotidien n=2, début 17/11 | mar 17/11 | mer 18/11 | jeu 19/11/2026 |
| B14 | quotidien n=3, après fait | — | ven 20/11 | lun 23/11/2026 |
| B15 | mensuel n=3, après fait | — | 20/01/2027 | mar 20/04/2027 |
| B16 | mensuel n=1, après fait | — | 31/01/2027 | dim 28/02/2027 |
| B17 | 2 jours ouvrés, après fait | — | mar 17/11 | ven 20/11/2026 |
| B18 | hebdo n=2 lun+jeu, début 17/11 | — (création) | — | jeu 19/11/2026 |
| B19 | idem | jeu 19/11 | 19/11 | lun 30/11/2026 |
| B20 | idem | lun 30/11 | 30/11 | jeu 03/12/2026 |
| B21 | annuel, début 29/02/2028 | mar 29/02/2028 | 29/02 | mer 28/02/2029 |
| B22 | hebdo lundi, date_fin 25/11/2026 | lun 23/11 | 23/11 | None (série close) |
| B23 | premier vendredi du mois, créée 17/11 | — | — | ven 04/12/2026 |
| B24 | idem | ven 04/12/2026 | 04/12 | ven 01/01/2027 (férié ignoré : seul `jours_ouvres` lit les fériés) |
| B25 | dernier vendredi du mois, créée 17/11 | — | — | ven 27/11/2026 |

## 3. Le classement et Proposé — `apps/taches/moteur/classement.py`

Entrées : `ItemPur` (§0.1), `J`, l'ensemble `travailles`, `objectif` (`int | None`), `faites`, `gardees_ouvertes`.

### 3.1 Où s'applique chaque règle

| Règle | S'applique à | Ne s'applique jamais à |
|---|---|---|
| `cle_tri` (§3.2) | l'ordre à l'INTÉRIEUR d'une section du jour (Essentiel, Prévu, Ce soir, À revoir), quand `rang_jour` est nul (invariant 32) ; l'ordre à l'intérieur d'un même groupe de « ce qui presse » (§3.4) | le choix des lignes de Proposé ; l'ordre du tour des projets |
| `proposer_plan` (§3.4) | QUELLES lignes Proposé montre et dans quel ordre ; la carte « Aide-moi à prioriser » (`classer_priorites`, §12) ; « Mes projets » de Planifier ma semaine | les sections gardées du jour |
| ordre du projet (`rang_projet`, puis `id`) | la prochaine action d'un projet ; la suite dépliée « toutes les tâches de mes projets » ; la vue d'un projet | — |

Dans **Prévu**, les tâches à `heure_debut` et les rendez-vous externes (§11) passent d'abord, par heure croissante ;
les `obligations` sans heure sont dans la bande « Toute la journée » au-dessus. `reordonner` numérote toute une
section par pas de 1 024.

### 3.2 `cle_tri(item: ItemPur, J, n_ouvres) -> tuple` — ordre total strict (inchangé)

`pmax = max(priorite, projet_priorite)` (sans projet : `priorite`) ; projet de la semaine (`focus`) ⇒ `pmax = 3` ;
activité ERP : `priorite = pmax = 0` ; `n` = jours travaillés d avec J < d ≤ échéance.

| Clé | Valeur |
|---|---|
| k1 bande | 1 = activité ERP due ≤ J, ou `echeance` = J, ou (`echeance` < J ∧ `pmax` = 3) ; 2 = (`echeance` > J ∧ n ≤ 3) ou (`pmax` = 3 ∧ pas d'échéance au-delà de J+14) ; 3 = le reste |
| k2 | échéance croissante (activité : `due_date` ; aucune = +∞) |
| k3 · k4 | −`pmax` · −`priorite` |
| k5 | `rang_jour` (nul en dernier) |
| k6 · k7 | `created_at` · (tâche 0 / activité 1, `id`) |

### 3.3 Jeu de test de `cle_tri` (J = mar. 17/11/2026, lun-ven, 18/11 férié ; travaillés suivants 19 (n=1), 20 (2), 23 (3))

`cle_tri` seul : 300 permutations → même ordre, clés toutes distinctes (`verif23/classement.py`, relancé en révision
3 : 300/300). La colonne « À l'écran le 17/11 » suit désormais §4.2 (A18-M2).

| Rang `cle_tri` | id | Titre | Faits | Bande | À l'écran le 17/11 |
|---|---|---|---|---|---|
| 1 | 7 | Payer fournisseur | éch. 16/11, prio 3, projet prio 2 | 1 | Proposé, en tête (`echeance_passee`, « échéance dépassée le 16/11 ») |
| 2 | 12 | Dossier subvention | éch. 17/11, prio 1, projet Admin prio 2 | 1 | Prévu (« échéance aujourd'hui ») |
| 3 | 101 | Rappeler Benali (activité) | due 17/11, créée 10/11 | 1 | Prévu (« activité ERP du jour ») |
| 4 | 15 | Dentiste | éch. 17/11, prio 0, créée 14/11 | 1 | Prévu |
| 5 | 20 | Devis Settat | éch. 19/11, prio 2, projet Ventes prio 3 | 2 | Proposé, en tête (`echeance_proche`, « échéance jeu. 19 ») |
| 6 | 21 | Déclaration TVA | éch. 20/11, prio 3 | 2 | Proposé, en tête (`echeance_proche`, « échéance ven. 20 ») |
| 7 | 30 | Préparer formation | sans date, projet Équipe prio 3 | 2 | Proposé, tour des projets (`prochaine_action`) |
| 8 | 40 | Renouveler abonnement | éch. 07/11, prio 1 | 3 | À revoir (`retard_ancien`, 10 jours) |
| 9 | 31 | Contrat assurance | éch. 15/04/2027, prio 3, sans projet | 3 | Proposé, tour (« Sans projet ») |
| 10 | 41 | Ranger le bureau | prévue 12/11, créée 05/11 | 3 | Proposé, en tête (`retard`, « prévue jeu. 12/11 ») |
| 11 | 42 | Timbres | prévue 17/11 | 3 | Prévu |
| 12 | 43 | Idée : vidéo | prévue 17/11 | 3 | Prévu |
| 13 | 44 | Idée : post | identique à 43 | 3 | Prévu |
| — | 50 | Site web | prévue 13/11, reports 3 | — | À revoir (`reportee_3_fois`) |
| — | 51 | Retour Lydec | `en_attente`, prévue 17/11 | — | En attente |
| — | 52 · 53 | Salon · Jeudi | `quelque_jour` · prévue 19/11 | — | absentes |

Ordres à l'écran : **Prévu** = 12, 101, 15, 42, 43, 44 ; **À revoir** = 40, 50 (`cle_tri`) ; **Proposé**, objectif 5,
aucune faite, 6 gardées ouvertes : N = 0, mais ce qui presse est toujours montré (IR21) : 41, 7, 20, 21 ; tour : rien.

### 3.4 `proposer_plan(items, J, travailles, objectif, faites, gardees_ouvertes, exclure, inclure, plan) -> PlanPropose`

**Candidates** (préfiltre `taches_de_la_journee`) : `type = tache`, `statut = a_faire`, `parent` nul, non bloquée,
¬`quelque_jour`, projet `actif` (sans projet : `triee_le` non nul), non gardée aujourd'hui (`jour_prevu ≠ J` ∧ `echeance ≠ J`), et
sans motif d'À revoir (§4.2) ; `exclure` retirés.

1. **N** = `max(0, objectif − faites − gardees_ouvertes)` (`objectif` : `OBJECTIF.nb` ; `libre` : 5 ; `tenir` en
   surchauffe : au plus ⌊R + b⌋ − faites − gardées). `plan.allege_le` posé → aucune ligne, `replie: true`.
2. **Ce qui presse** (A18-M2), raison et ordre fixes (`RaisonPropose`) :
   - `retard` : `jour_prevu` ∈ [J − 7, J − 1] ;
   - `echeance_passee` : `echeance` ∈ [J − 7, J − 1] ;
   - `echeance_proche` : `echeance` ∈ ]J, J + 2 jours travaillés] ∧ (`jour_prevu` nul ∨ `jour_prevu` > `echeance`).
   Trié par (rang de la raison, `cle_tri`). TOUJOURS montré en tête, même au-delà de N (IR21).
3. **Tour des projets** (A18-M1) sur les autres candidates à `jour_prevu` nul (une tâche prévue plus tard n'est pas
   proposée) : file de chaque projet triée par (`rang_projet`, `id`) ; projets triés par (−`priorite`, `rang`, `id`) ;
   les tâches sans projet (triées) forment un dernier « projet » de priorité la plus basse. Tour 1 : la 1re de chaque
   file (`prochaine_action`), tour 2 : la 2e de chaque file (`action_suivante`), etc. Aucun projet ne prend une 2e
   place tant qu'un autre projet a une action non prise. `inclure` passe en tête du tour (même au-delà de N).
4. **Sortie** : `pour_objectif` = presse + les `max(0, N − |presse|)` premières du tour, chacune avec `raison`
   (`{"code","texte"}`, textes §2.2 de `textes.md`) ; `reste_nb` = tour non pris ; `suite_par_projet` (`?tout=1`, « Voir
   toutes les tâches de mes projets ») = toutes les tâches ouvertes non gardées des projets actifs et des sans-projet
   triées, groupées par projet (ordre du tour), dans l'ordre du projet, prévues plus tard comprises (leur jour dit).
5. **Charge** (montrée à côté de « Garder ces N », jamais un filtre) : `minutes_estimees` (gardées + proposées),
   `sans_estimation`, `surcharge` = minutes > `disponible_minutes` (§3.6), `non_calculable` = plus de la moitié sans durée.
6. **Planifier ma semaine** : `agenda/?vue=semaine` → `mes_projets` = le tour complet (étape 3, sans N), groupé par
   projet ; toucher une tâche puis un jour = `planifier(jour_prevu=jour)`.

**Jeu de test (recalculé par un script jetable (rapport resté sur la branche de travail), cette session).** Projets : Ventes (haute,
rang 1024 ; 12 tâches V1…V12 sans date, `rang_projet` 1024…12288, + R4 reportée 3 fois), Maison (moyenne, rang 1024 ;
R1 prévue 16/11, M1 prévue ven. 20, M2, M3), Polydesign (moyenne, rang 2048 ; R2 échéance 12/11, D1 en réserve, D2
bloquée, D3, D4), Admin (basse ; A1 échéance jeu. 19, A2, A3, R3 prévue 05/11), Salon (haute, **en pause** : 2 tâches),
sans projet triées S1, S2 — 30 tâches. Faites 0, gardées 0 ; N = l'objectif.

| N | `pour_objectif` (raison) |
|---|---|
| 2 | R1 (`retard`), R2 (`echeance_passee`), A1 (`echeance_proche`) — ce qui presse dépasse N et reste entier |
| 3 | R1, R2, A1 |
| 5 | R1, R2, A1, V1 (`prochaine_action`), M2 (`prochaine_action`) |
| 8 | R1, R2, A1, V1, M2, D3, A2, S1 (tous `prochaine_action`) |
| 13 | … + V2, M3, D4, A3, S2 (`action_suivante`) |

À revoir : R4 (`reportee_3_fois`), R3 (`retard_ancien`). Absentes : Salon (en pause), D1 (en réserve), D2 (bloquée), M1
(prévue plus tard ; visible dans la suite dépliée). **Monopole** : avec l'ancien `cle_tri`, les 5 places du tour vont à
V1…V5 (Ventes est en bande 2) ; avec le tour : V1, M2, D3, A2, S1 — Ventes n'a sa 2e place (V2) qu'au tour 2.

### 3.5 `explication(item)` et raisons

Une ligne de Proposé dit sa `raison` (textes §2.2 : « prévue hier », « échéance dépassée le 12/11 », « échéance jeu.
19 », « prochaine action de Ventes », « suite de Ventes », « sans projet »). Les autres lignes gardent `explication`
(≤ 3 faits joints par « · », révision 1) ; les noms passent par `nom_pour(…, usage)` (§8).

### 3.6 `capacite(reglage, minutes_9j, jours_28)` et temps disponible

1. `Preference.capacite_jour_min` posée → (valeur, `reglage`) ; sinon, « comprendre mon rythme » allumé et ≥ 5 jours
   travaillés à minutes faites dans les 28 jours : médiane des minutes faites (`duree_reelle_minutes`, sinon
   `estimation_minutes`) des 9 derniers jours travaillés qui en ont → (arrondi, `historique`) ; sinon (240, `defaut`).
   Exemple [150, 180, 200, 210, 240, 250, 260, 300, 320] → 240.
2. **Temps disponible** (invariant 35) : `disponible_minutes = max(0, capacite_minutes − rendez_vous_minutes)` ;
   `rendez_vous_minutes` = `minutes_rendez_vous(evenements, J, fenetre)` (§11) : union des rendez-vous horodatés du
   jour, bornés aux heures de travail de la société (`fenetre_societe`), journée entière = 0.

| Capacité 240, fenêtre 08:30-19:00 | Rendez-vous | Disponible |
|---|---|---|
| 11:00-12:00 | 60 | 180 |
| 10:00-11:30 et 11:00-12:00 (chevauchés) | 120 | 120 |
| 07:00-09:00 (borné à 08:30) | 30 | 210 |
| un rendez-vous « journée entière » | 0 | 240 |
| 09:00-12:00 et 14:00-16:00 | 300 | 0 (jamais négatif) |
| 18:30-20:00 (borné à 19:00) | 30 | 210 |

Recalculés par `integ2/propose.py`.

## 4. La journée — `aujourdhui/`, `placer(t, J, plan)`

### 4.1 Ordre vertical (A14-M1) et ce que contient chaque clé

| # | Bloc (clé) | Contenu | Replié |
|---|---|---|---|
| 1 | `progression` | « N sur OBJECTIF » + essentiel ; au toucher : gardées faites, temps (`disponible_minutes`), Mon rythme | — |
| 2 | `carte_du_moment` | UN objet au plus, choisi par le serveur (§4.10) ; le navigateur insère le brouillon et l'astuce | — |
| 3 | `essentiel` | lignes du plan de J marquées `essentielle` (≤ 3), ouvertes ou faites aujourd'hui | non |
| 4a | `obligations` (« Toute la journée ») | visites, poses, interventions du jour (date seule, A16-N4) ; rendez-vous externes « journée entière » ; `touches` → ligne « Suivi des relances : n » dans Prévu | non |
| 4b | `journee` (« Prévu ») + `rendez_vous` | gardées du jour, hors soir : blocs et rendez-vous externes à leur heure en tête, puis tâches et activités ERP | non |
| 5 | `ce_soir` | du jour, `moment = soir` | non |
| 6 | `propose` | ce qui presse puis tour des projets (§3.4) ; « Garder ces N » ; `charge` ; « Voir toutes les tâches de mes projets » ; `replie` après Alléger | replié après Alléger |
| 7 | `a_decider` (« À revoir ») | reportées 3 fois, retards de plus de 7 jours, activités ERP en retard ; lot « Tout en réserve » | oui |
| 8 | `en_attente` | `en_attente` datées ≤ J ; + compte `a_trier.bloquees` | oui |
| 9 | `faites` | faites aujourd'hui | oui |
| 10 | Ailleurs dans l'ERP | route paresseuse `aujourdhui/ailleurs/` | oui |

Une section vide est absente (sauf l'invite ★ après « Garder »). Aujourd'hui n'est jamais vide tant qu'un projet actif
a une tâche ouverte (A11) : à défaut de toute ligne, Proposé montre au moins « Voir toutes les tâches de mes projets ».

### 4.2 Placement d'une tâche (préfiltre invariant 10, puis premier cas vrai)

1. `fait` ∧ `fait_le` local = J → `faites` (et reste dans `essentiel` si sa ligne y est).
2. `en_attente` ∧ (`jour_prevu` ≤ J ∨ `echeance` ≤ J) → `en_attente` ; sans date ≤ J → absente (visible dans son projet).
3. `reports ≥ reports_tranches + 3` ∧ `jour_prevu ≤ J` → `a_decider`, motif `reportee_3_fois`.
4. `jour_prevu = J` ∨ `echeance = J` → `essentiel` si une ligne `essentielle` la porte ; sinon `ce_soir` si `moment =
   soir` ; sinon `journee`.
5. `jour_prevu < J − 7` ∨ `echeance < J − 7` → `a_decider`, motif `retard_ancien`.
6. Ce qui presse (`retard`, `echeance_passee`, `echeance_proche`, §3.4) → `propose`, en tête, avec sa `raison`.
7. Candidate du tour des projets (§3.4) → `propose` (`pour_objectif` ou suite dépliée).
8. Sinon absente (prévue plus tard — visible dans la suite dépliée et l'agenda —, En réserve, À trier, bloquée…).

Activité ERP (`activites_ouvertes_pour`, si `erp_dans_journee`) : due J → `journee` ; due < J → `a_decider` motif
`activite_passee`. `obligations` (`FamilleObligation` : `visite`, `pose`, `intervention`, `touches`) : chacune une fois,
famille en échec absente. Cocher une activité = `POST records/activities/{id}/done/` (close dans l'ERP, sans
`geste_id`). « Lier une tâche » (`taches/lier-activite/`) crée une tâche à `activite_origine` et laisse l'activité ouverte
(invariant 30).

### 4.3 Ce qui compte comme un report (invariant 4)

`reports += 1` ⇔ ancien `jour_prevu ≤ J` ET le nouveau est plus tard ou « En réserve ». Ne comptent jamais :
futur → futur, avancer, poser un premier jour, `decaler`, `instancier`, Alléger, « Les remettre dans Proposé », le
passage de minuit. Comptent : Reporter, Choisir un jour plus tard, « Tout reporter » et « Reporter à … » du bilan, « Tout en réserve »,
le lot `planifier`. `trancher` (`Decision` : `aujourdhui`, `garder` = sa date si ≥ J, sinon J, `jour`, `un_jour`,
`abandonner`) : `aujourdhui`, `garder` ou `jour` posent `reports_tranches = reports` (la question revient 3 reports
plus tard ; tâche en retard gardée aujourd'hui : c'est un report de plus, verif-specs-2-3 m8).

### 4.4 « Garder ces N » (`journee/planifier/` `mode:"express"`) et gestes sur Proposé

- Le seul mode est `express` ; le triage d'À revoir n'est jamais exigé (A17-T2). Le matin, tant que rien n'est
  gardé, la carte du moment `garder` porte le bouton (A17-M1) ; il figure aussi en tête de Proposé.
- Les lignes de « ce qui presse » comptent dans « Garder ces N » comme les autres (A18-M2).
- N = nombre de lignes cochées de `pour_objectif` (toutes par défaut). Le geste : `planifier(J)` pour chacune
  (0 report : premier jour posé) ; `PlanJour` créé si absent, `planifie_le` = maintenant (la 1re fois),
  `objectif_du_jour` = `objectif.nb` ; une `LignePlanJour(prevue_au_plan=True)` pour chaque élément ouvert
  d'Essentiel, Prévu, Ce soir (tâches et activités vérifiées par `activites_ouvertes_pour`) et chaque ligne gardée.
  Revalider n'ajoute que des lignes (invariant 18).
- ★ seulement sur Essentiel et Prévu, JAMAIS sur Proposé (spec-7 r3.1 §9) : `journee/essentiel/` ; ligne
  `essentielle` créée (`prevue_au_plan = True` si le plan n'est pas validé, sinon `False`). 4e ★ → 400 « 3 au plus. ».
  Après « Garder ces N », l'invite « Touche ★ pour ton essentiel » s'affiche et le focus va sur « Prévu ».
- Un geste « Aujourd'hui » sur une ligne proposée : `planifier(J)` ; plan validé → ligne ajoutée (`prevue_au_plan =
  False`).
- Cocher une ligne proposée : `terminer` → faite aujourd'hui, comptée ; plan validé → ligne `prevue_au_plan = False,
  faite = True`.
- « Faire le plan » n'existe pas à part : le rituel est facultatif, la liste marche sans lui (A11).

### 4.5 « Alléger ma journée » (`journee/alleger/`)

Il coche ce qu'il garde parmi les lignes de Prévu (rien n'est coché d'avance). Les AUTRES tâches à `jour_prevu = J`
sans échéance ≤ J retournent à leurs projets (`jour_prevu` nul) par `planifier(…, compter_report=False)` ; leurs
lignes de plan (essentielles comprises) sont retirées ; activités ERP, obligations et tâches à échéance ≤ J restent.
`PlanJour.allege_le` est posé (remis à nul par l'annulation du geste) : jusqu'au lendemain, Proposé est **replié et
vide** (`replie: true`, `places = 0`, A16-N6).

### 4.6 Bilan du soir (`journee/cloture/`, `journee/cloturer/`)

- `restes` = tâches ouvertes d'Essentiel, Prévu, Ce soir ; `a_trancher` = tâches `reportee_3_fois` à `jour_prevu = J` ; activités
  ERP ouvertes à part (`activites_a_clore`, « à clore dans l'ERP »). Faites = `fait_le` local = J.
- Choix par reste (`Decision`) : `prochain_jour_ouvre` (« Reporter à {jour} »), `jour` (+ date), `un_jour` (En
  réserve), `abandonner` ; « Demain » n'est jamais un bouton de report (spec-7 r3). « Tout reporter »
  (`le_reste: true`) applique `prochain_jour_ouvre` aux restes non nommés. Les `a_trancher` sont marquées « À revoir » : non
  nommées, elles RESTENT en place (jamais de 400, parcours 8 de spec-7).
- Effets : `planifier()` (reports comptés, §4.3), lignes `reportee = True`, `cloture_le` = maintenant, `reflexion`
  (≤ 280). Possible jusqu'à J+1 12:00 (`possible_jusqua`) ; « demain » est relatif au jour clos.
- Contenu affiché : « N sur OBJECTIF » en première ligne, « gardées faites » en seconde (A16-M2), UN constat au plus
  (A14-M4, §6.9). Sauté : rien ne bouge, aucune trace négative. **Bilan d'hier** : `journee/cloture/?jour=` J−1 reste
  ouvert jusqu'à J 12:00 ; la carte du moment `bilan_hier` le propose si hier a des restes et `cloture_le` est nul.

### 4.7 Passage à minuit

Rien n'est écrit à minuit : le retard est calculé (`jour_prevu < J` → À revoir le lendemain), `reports` intact. La
tâche `taches.nocturne` (03:00) clôt le `PlanJour` de la veille (statut du jour, compteurs) sans toucher aux tâches.
La pastille ne change qu'à l'ouverture ou au push suivant (limite dite).

### 4.8 Retour d'absence (`retour_absence(jours, taches)`, carte `retour`, A14-B1)

- Détecté par `POST vu/` : fin d'un congé déclaré (dernier jour du congé < J et première ouverture depuis), OU ≥ 3
  jours travaillés strictement entre la dernière ouverture (`max(PlanJour.jour)` à `app_ouverte_le` non nul) et J.
  Une fois par retour (unicité `taches_incit_uniq`).
- `donnees` : `jours` = J − date de la dernière ouverture (jours calendaires) ; `taches` = tâches `a_faire` du
  préfiltre à `jour_prevu` dans [dernière ouverture + 1, J − 1].
- « Les remettre dans Proposé » → ces tâches à `jour_prevu` nul, `compter_report=False` (elles gardent leur échéance
  et peuvent donc tomber dans À revoir) ; « Les voir une par une » → À revoir déplié. Aucun report compté. La
  notification du matin ne compte que les tâches du jour. Ce jour-là, `progression.reprise = true` : la ligne de
  progression dit « Reprise » au lieu de « 0 sur 5 ». La carte `retour` n'est créée par `POST vu/` que si
  `ReglagesRythme` existe (invariant 29).

### 4.9 Capacité, progression, pastille

- **Capacité** : §3.6. `minutes_prevues` = Σ estimations des tâches (ouvertes et faites aujourd'hui) d'Essentiel et
  de Prévu.
- **`progression.faites` = `compte_du_jour`** (§6.1, invariant 13). `prevues` = `faites` + éléments ouverts gardés
  d'Essentiel, Prévu, Ce soir. `plan_tenues`/`plan_lignes` (« gardées faites ») = lignes `prevue_au_plan` faites /
  lignes `prevue_au_plan` (les ajouts comptent dans `faites`, pas au dénominateur ; les lignes retirées par Alléger
  n'y sont plus). Une gardée qui change de jour (tout chemin de `planifier`) GARDE sa ligne, marquée `reportee` et
  non tenue : seul Alléger retire une ligne (la déplacer ne gonfle jamais le taux). La ligne d'une activité ERP qui
  PORTE une tâche (lien ou conversion) ne compte ni au numérateur ni au dénominateur : sa tâche la représente, une
  même chose n'est jamais comptée deux fois (§6.1, `selectors.journee.ligne_gardee`) ; une activité gardée sans
  tâche est une ligne, tenue quand il la clôt ce jour-là. Partout l'écran montre « N sur OBJECTIF » ; les gardées
  faites sont une seconde donnée (A17-M2).
- **Pastille (UNE définition, invariant 11)** : `n` = éléments OUVERTS et GARDÉS d'Essentiel + Prévu + Ce soir
  (tâches ET activités ERP), plafonné à 99 ; JAMAIS Proposé (A16-N5) ; peut valoir 0 (→ `clearAppBadge`). Ni À revoir,
  En attente, À trier, ni obligations. Calculée par `compter_journee` pour `badge/`, `aujourdhui/` et `notify(badge=n)`.

### 4.10 La carte du moment (`carte_du_moment`, valeurs de `CarteDuMoment`)

Une seule, la première vraie dans cet ordre (spec-7 r3.1 §4) ; le navigateur insère « Reprendre » (brouillon de
saisie gardé) juste après `retour`, et l'astuce de geste avant la révélation `mon_iphone`.

| Type | Vraie si | `donnees` |
|---|---|---|
| `retour` | carte `retour` du jour non répondue (§4.8) | PROPOSITION |
| `bilan_hier` | avant 12:00, hier a des restes et le `cloture_le` d'hier est nul | `{"jour"}` |
| `garder` | rien n'est encore gardé (`planifie_le` nul) et `pour_objectif` non vide | `{"n","objectif"}` |
| `alleger` | à partir de `relance_jour`, `allege_le` nul, ≥ 1 gardée ouverte et `faites` < objectif / 2 (le seuil de la dérive, §7) | `{"faites","prevues"}` |
| `faire_bilan` | à partir de `heure_soir`, `cloture_le` nul, plan validé ou ≥ 1 faite | `{}` |
| `rythme` | une PROPOSITION ouverte (`proposition_palier`, `derive_tenir`, `garde_taille`, `constat`) | PROPOSITION |
| `pause` | une carte `pause` non répondue (type de sollicitation mis en pause) | PROPOSITION |
| `revelation` | une révélation du jour (I14) ; `mon_iphone` : `expire_le` = J+3 (A17-T3), placée en dernier, ne bloque pas les autres | PROPOSITION |

### 4.11 Hors ligne et conflit entre appareils

- **Hors ligne (A16-N11, `api.md` §5)** : trois gestes en file — ajouter (`saisie-rapide/`, `client_id`), cocher
  (`terminer/`), reporter (`planifier/`, `lock_version` du cache) ; chaque op porte `proprietaire_attendu` ; 409
  `autre_compte` → op jetée ; tout autre geste est grisé (« Possible une fois connecté ») ; la saisie en cours est
  gardée ; le Copilote dit une phrase.
- **Conflit (A16-N8)** : un 409 `conflit_version` n'écrase jamais la saisie en cours ; le bandeau propose « Garder la
  mienne » (renvoi avec `actuel.lock_version`) ou « Prendre l'autre » (affiche `actuel`) ; l'heure vient de
  `actuel.updated_at`. La liste est relue au retour du focus.

## 5. La santé d'un projet — `apps/taches/moteur/sante.py`

**Définitions** : *comptée* = tâche du projet, `parent` nul, vivante, statut ≠ `annule` ; *ouverte* = comptée
`a_faire` ou `en_attente` ; *actionnable* = ouverte, `a_faire`, ¬`quelque_jour`, non bloquée ; jours travaillés =
§0 (congés exclus).

| Fonction | Règle |
|---|---|
| `avancement` | F faites sur F + O comptées (« 12 sur 20 ») + « dernière faite le … » ; 0 comptée → pas de barre |
| `burnup` | par semaine close (fin dimanche) : total = comptées créées ≤ fin et non annulées ≤ fin ; faites = `fait_le` ≤ fin ; dès 2 semaines, légende « reconstruit depuis les dates actuelles » |
| `sans_prochaine_action` | ≥ 1 ouverte ∧ 0 actionnable ; phrase selon la cause (tout en réserve / tout attend / tout bloqué) |
| `tout_fait` | 0 ouverte ∧ F ≥ 1 → « Tout est fait : terminer le projet ? » |
| `a_l_arret` | ≥ 1 ouverte ∧ jours travaillés dans ]réf, J] ≥ N ; réf = max(dernier `fait_le` du projet, tous niveaux ; date de `statut_depuis`) ; N = `projet_arret_jours` (10, 5-30) |
| `echeance_menacee` | `echeance` ∧ ≥ 1 ouverte ∧ un signal : (a) `echeance < J` ; (b) k ouvertes datées (`jour_prevu` ou `echeance`) après elle ; (c) une étape finit après elle ; (d) si « comprendre mon rythme » allumé ET F28 ≥ 5 : besoin = ⌈O × J28 / F28⌉ > reste |
| `neglige(projets, faites_14j)` | P actif, ≥ 1 actionnable, `statut_depuis` ≤ J − 14 : négligé ⇔ d(P) = 0 ∧ ∃ Q actif de priorité strictement inférieure avec d(Q) ≥ 1 ; d = tâches du projet faites (tous niveaux) sur 14 jours calendaires ; Q nommé = le plus avancé (d max), égalité → priorité plus haute, puis `rang` |
| `constat_projets` | « {actifs} projets actifs, {k} ont avancé ces 7 jours » (≥ 1 faite tous niveaux en 7 jours calendaires) |

F28 = tâches comptées DU PROJET faites sur les 28 derniers jours calendaires ; J28 = jours travaillés de
l'utilisateur dans ]J − 28, J] ; O = ouvertes du projet ; reste = jours travaillés dans ]J, échéance] (verif-specs-4-6
m10). Ordre des signaux affichés : `echeance_menacee`, `a_l_arret`, `neglige`, `sans_prochaine_action`, `tout_fait`.

**Cas (recalculés par `integ2/recalcul.py`)** — J = mar. 17/11/2026, N = 10.

| Cas | Données | Signaux |
|---|---|---|
| Projet neuf | créé aujourd'hui, 0 tâche | aucun ; « À planifier » (actif ∧ `planification_le` nul ∧ 0 ouverte) |
| Neuf resté vide 10 jours | créé 03/11, 0 tâche | aucun (0 ouverte : ni arrêt, ni prochaine action) ; « À planifier » |
| Neuf avec tâches, rien fait | créé 03/11, 3 ouvertes | `a_l_arret` (10 jours travaillés depuis `statut_depuis`) |
| 2 tâches | 1 faite le 03/11, 1 ouverte ; F28 = 1 | « 1 sur 2 » ; `a_l_arret` (10) ; signal (d) muet (F28 < 5) |
| 2 tâches, férié | idem, 06/11 férié | 9 jours travaillés → pas à l'arrêt |
| Sans échéance | — | jamais `echeance_menacee` |
| Échéance tenable ? | F28 8, J28 20, O 12, reste 15 | (d) : besoin 30 > 15 → `echeance_menacee` ; F28 = 4 → (d) absent |
| Retour de congé | dernière faite 30/10, congé 02-13/11, 06/11 férié | 2 jours travaillés (16, 17/11) → pas à l'arrêt |
| Tout en réserve | 2 ouvertes `quelque_jour` | `sans_prochaine_action` (« tout est en réserve ») |
| Tout fait | 5 faites, 0 ouverte | `tout_fait` |
| Négligé | A (haute) d 0, B (moyenne) d 4, C (basse) d 1, tous ≥ 14 j | A négligé, Q nommé B |
| Négligés en chaîne | A d 0, B d 0, C d 1 | A et B négligés, Q = C pour les deux |
| Tous à 0 | d = 0, 0, 0 | aucun |

## 6. Le rythme — `apps/taches/moteur/rythme.py`

### 6.1 Ce qui compte comme fait (`compte_du_jour(taches, activites) -> (compte, detail)`)

Par jour local : tâche propre passée à `fait` = 1 ; parent = 1, **sous-tâche = 0** ; **routine = 0** (§2), autre
récurrence = 1 ; activité ERP close par lui ce jour = 1 ; sans estimation = 1 ; rouverte = retirée ; abandonnée = 0.
`detail` = `etapes`, `routines`, `micro_non_comptees`, `activites_closes`. **Hors de la première livraison** (A18,
critique m5 ; les champs restent) : le plafond des micro-tâches (estimation ≤ 10 min, 2 comptées au plus par jour) ;
en v1 une micro-tâche compte 1 et `micro_non_comptees` vaut 0.

### 6.2 La journée évaluée (`statut_jour(ouvre, conge, compte, plan, app)`)

Écran Mon rythme (rév. 3.1) : la série montrée (`RYTHME.serie`) est la fenêtre de la proposition, les 10 derniers
jours TRAVAILLÉS ; un jour férié ou en congé n'y a pas de barre (il est nommé sous la trace) ; un jour `sans_donnees`
a une barre vide.

`conge` · `non_ouvre` (non travaillé pour lui) · `sans_donnees` (travaillé, 0 compté, aucun plan validé, app non
ouverte) · `evalue`. Seul `evalue` entre dans un bloc, une référence ou un constat. Un samedi travaillé va dans les
totaux, jamais dans un bloc. Statut posé par la tâche nocturne sur le `PlanJour` de la veille.

### 6.3 Les trois modes

| Mode (`ReglagesRythme.mode`) | Objectif | Propositions | Alertes |
|---|---|---|---|
| `pousser` « En faire plus » (défaut) | palier (froid : 5 « valeur par défaut ») | +1 / −1 par bloc, jamais imposées | relance « dérive » |
| `tenir` « Garder ce rythme » | `arrondir(R)`, zone [R − b, R + b] | aucune | dérive hors zone, puis 28 jours de silence |
| `libre` « Sans objectif » | aucun (`nb: null`) | aucune | aucune ; les quatre faits restent affichés |

**Jour court** (`Preference.jours_courts`) : objectif `max(1, N − 1)` ce jour-là, évalué contre lui.

### 6.4 Journée réussie et les quatre faits

`journee_reussie(compte, objectif, choisis, faits)` = compte ≥ objectif ET (aucun essentiel choisi OU ≥ 1 fait) ;
`None` sans objectif. Toujours montrée par ses quatre faits (compte, objectif, essentiel, gardées faites), jamais par le
mot « ratée ». Les **paliers** ne lisent que « jours à N ou plus » (le compte seul).

### 6.5 POUSSER — l'objectif déclaré prime (A2)

1. **Objectif dit** (`objectif_dit(etat, nombre, sens)`, `POST rythme/`, Copilote) : s'applique **tout de suite**,
   au `PlanJour` de J s'il n'est pas clos : `palier` = nombre (1-12, sinon 400) ou ±1 depuis l'objectif affiché
   (plancher 1, plafond 12) ; `palier_source = dit` ; le mode passe à `pousser` par la même route (`POST rythme/`,
   seul chemin du mode) ; `refus_montee`, `blocs_a_sauter`, `baisse_refusee`, `essai_restant` remis à zéro ; nouveau
   bloc dès J+1 (`bloc_debut`) sauf en démarrage à froid. `ReglagesRythme.palier` est la SEULE source (aucune clé
   `Preference` pour l'objectif, I17).
2. **Démarrage à froid** ⇔ `bloc_debut` nul : objectif 5 « valeur par défaut » (ou le nombre dit). Au 10e jour
   évalué : journée type = `arrondir(min(médiane, moyenne))`, plancher 1 ; `bloc_debut` = lendemain. **Rien n'est
   imposé, ni baisse ni hausse** : sans objectif dit, si la journée type ≠ 5, la carte `premier` la propose
   ([Oui, {type}] `oui` → `palier` = type, `accepte` ; [Garder 5] `garder` → `palier` = 5, `accepte`) ; sans réponse
   en 7 jours elle expire et l'objectif reste 5 (`palier` nul) ; avec objectif dit, il est gardé et la carte
   `journee_type` propose le type. Pas de proposition de rythme avant ces 10 jours (spec-7 §8).
3. **Bloc** = 10 jours évalués au même palier (≈ 2 semaines travaillées), évalué à sa clôture puis remis à zéro ;
   une proposition au plus par bloc ; le bloc partiel est conservé pendant un congé.
4. **Proposer +1** si jours à N ou plus **≥ 5/10**, N < 12, aucun bloc à sauter, garde de taille passée, et N+1 n'est
   pas un palier quitté sans avoir été tenu (`echec_niveau = N+1`, `meilleur_tenu < N+1`) depuis moins de 42 j ×
   `echec_n`.
5. **Proposer −1** (jamais plus, jamais imposé, plancher 1) si jours à N ou plus **≤ 3/10** et baisse non refusée au
   bloc précédent ; bloc d'essai (le 1er après une montée acceptée) : seulement si 0 ou 1 jour tenu. 4/10 : rien.
6. **Réponses** : montée « Oui » → palier +1 (`accepte`), essai ; « Pas maintenant » → blocs sautés 1, 2, puis 4 ; à
   la 3e carte refusée de suite, le bouton « Garder ce rythme » s'ajoute (bascule `tenir`). Baisse « Oui » → palier
   −1, échec mémorisé si N > `meilleur_tenu` ; « Garder N » → pas de baisse au bloc suivant. Sans réponse en 7 jours :
   expirée, ce n'est pas un refus. La réponse vaut le jour même si elle précède la validation du plan, sinon le
   lendemain : un plan VALIDÉ fixe l'objectif du jour partout (Aujourd'hui, en-tête du Copilote, plan, bilan —
   `services.rythme.objectif_du_plan_valide`). « Oui » repart le bloc le lendemain (comme un objectif dit). Un
   palier qui change (objectif dit, +, −, réponse à une carte) abandonne les cartes de palier ouvertes ; une carte
   calculée d'un autre palier que le courant est close sans effet (jamais deux crans). `meilleur_tenu` = max des N
   d'un bloc à ≥ 5/10.
7. **Garde de taille** (HORS de la première livraison, critique m5) : référence = médiane des estimations des tâches
   faites des 10 jours initiaux ; pas de montée si la médiane du bloc < 70 % de la référence (≥ 10 tâches estimées de
   chaque côté) → carte `garde_taille`. De même la **mémoire d'échec** du point 4 (`echec_*`) n'est pas lue en v1 : la
   montée vers un palier quitté n'est pas retardée. Les champs restent ; une livraison ultérieure les allume.
8. **Pas de double saut** (A2.2). **Repère P60** (`RYTHME.repere`) : percentile 60 linéaire des `compte` des 9
   derniers `JourCompte` évalués (≤ 42 jours calendaires), à une décimale ; moins de 9 jours → `repere: null`. Exemples
   (`integ2/propose.py`) : [3,4,5,5,5,6,6,7,8] → 5,8 ; 9 × 5 → 5,0 ; [2…10] → 6,8. Repère affiché, jamais un objectif.

### 6.6 TENIR (`reference_tenir`, `bande_tenir`, `derive_tenir`)

- `plafonner_jours(comptes)` : chaque jour de la fenêtre plafonné à 2 × médiane(fenêtre) + 1 (A2.3).
- R = moyenne non arrondie des 14 derniers jours évalués (≤ 42 jours calendaires), plafonnés ; il en manque → R
  provisoire = palier courant (ou 5), fixée après 14 jours évalués. b = max(1 ; 0,2 R) ; affichage « environ
  arrondir(R) », zone « arrondir(R − b) à arrondir(R + b) ».
- Dérive = moyenne plafonnée des 14 derniers jours évalués DEPUIS la fixation de R, strictement hors zone → carte
  `derive_tenir` (`sous` / `au_dessus`), puis **28 jours de silence** quelle que soit la réponse ; `garder` garde R ;
  `passer` (bouton « Monter à {m} » ou « Descendre à {m} ») pose R = `arrondir(moyenne)`, fixée ce jour. Surchauffe : Proposé plafonné à ⌊R + b⌋ tâches.
- Planchers (revue F2 tour 2) : objectif montré `max(1, arrondir(R))`, bas de zone plancher 0 (jamais « 0 tâche »
  ni borne négative) ; dérive : `m = max(1, arrondir(moyenne))` ; aucune carte (ni silence) quand `m` = l'objectif gardé.

### 6.7 Bascules (`basculer(etat, mode, jour)`)

POUSSER → TENIR : R des 14 derniers jours évalués (rythme réel). TENIR → POUSSER : palier = `arrondir(R)`, plancher
1. → LIBRE : objectif nul, le palier est GARDÉ. LIBRE → POUSSER : on rend le dernier palier (celui d'avant « Sans
objectif », R2-122, choix C-7) ; sans palier encore, journée type des 10 derniers jours évalués (≤ 42 j), sinon
démarrage à froid. Toute bascule remet blocs, refus et essai à zéro, abandonne la proposition en attente ; `meilleur_tenu` et les
échecs sont gardés.

### 6.8 Ce qui fait faire plus au quotidien (A2.4 — à rendre visible)

| Levier | Où |
|---|---|
| Proposé rempli jusqu'à l'objectif | Aujourd'hui (§3.4) |
| Essentiel choisi d'abord | ★, notification du matin |
| Une heure pour chaque tâche gardée (« quand ? ») | Copilote (« quand et où »), fiche → Quand |
| Point de 15 h avec le compte réel | Message de 15 h (§7) |
| Découpe proposée pour toute tâche reportée 3 fois | À revoir, Copilote |
| Bilan du soir factuel | §4.6 |

### 6.9 Constats sur son comportement (`constats(donnees)`)

Calculés à 03:00 si « comprendre mon rythme » est allumé (C6 hors de la première livraison, faute de durée réelle
mesurée, critique m6) (coupé : rien calculé ni gardé, socle §8 — la nuit n'écrit alors ni `statut_jour` ni
`compte_rythme`, et `rythme/` ne sert ni série ni trace) ; fenêtre 28 jours
calendaires sauf mention ; 8 au plus ; un constat refusé (« Pas maintenant ») se tait 28 jours ; **un seul montré
par bilan du soir** (le plus récent jamais montré, puis par numéro), la liste vit dans Mon rythme (A14-M4).

| # | Formule | Minimum | Action proposée |
|---|---|---|---|
| C1 | gardées faites par `LignePlanJour.creneau` (`matin`, `apres_midi`, `fin_journee`, figé à la création), écart ≥ 25 points | 30 lignes par créneau | `essentiel_le_matin` (Preference, source `carte`) |
| C2 | essentiel fait quand il est 1er du plan (`LignePlanJour.rang` minimal) vs ailleurs, écart ≥ 30 points | 15 jours chacun | `essentiel_le_matin` |
| C3 | moyenne d'un jour de semaine ≤ moyenne générale − 1 | 8 jours de ce jour | ajouter le jour à `jours_courts` |
| C4 | gardées − gardées faites ≥ 2 sur ≥ 60 % des plans | 10 plans | « Garder ces N » limité à médiane faite + 1 tant que la carte acceptée est la dernière de C4 (I13) |
| C5 | part des tâches finies par tranche de 2 h (heure de `fait_le`) | 30 tâches | aucune (information) |
| C6 | réel / estimé médian par projet hors [0,8 ; 1,25] | 5 tâches estimées ET mesurées du projet | durée corrigée (minutes × ratio) dans `charge` tant que la carte acceptée est la dernière de C6 (I13) |
| C7 | lignes « Reportée 3 fois » d'À revoir au jour J (`reports ≥ reports_tranches + 3`, jour prévu ≤ J ; ni tranchée ni en réserve) — le nombre de lignes qu'ouvre son bouton | 1 | ouvrir À revoir |
| C8 | `neglige()` non vide (projet de plus haute priorité) | — | une de ses tâches actionnables dans Proposé de demain (`inclure`), lue sur la carte acceptée (I13) |

Chaque nombre d'une phrase figure dans `IncitationCoach.donnees` (ids, jamais de titres ; noms rendus à la lecture
par `nom_pour`).

**Hors de la première livraison (comme C6, revue F2 tour 2 #7)** : C1 et C2 (les lignes de plan ne portent encore ni
`creneau`, ni `rang`, ni `faite`), C4 et C8 (l'effet de leur « Oui » — limite de « Garder ces N », `inclure` de
Proposé — n'est pas branché : une carte dont le bouton ne change rien n'est pas montrée) ; les champs et les
formules restent, une livraison ultérieure les allume. Livrés : C3, C5, C7.

### 6.10 Exemples chiffrés — 49 de spec-5a §7 + 12 de A2 + 4 de la révision 2 + 5 variantes v1, RECALCULÉS

Recalculés par un script jetable (rapport resté sur la branche de travail) (bibliothèque standard, règles finales :
seuil 5/10, demie vers le bas, plafonnement, objectif dit, premier objectif proposé et jamais imposé, semaine
courte), relancé en révision 2 : **65/65 conformes**. Les 49 d'origine restent vrais au nouveau seuil (leurs blocs
font 7/10 et 2/10) ; `palier_initial` rend désormais (palier appliqué, journée type, carte), d'où les sorties 10-12
réécrites ; deux libellés d'entrée sont rendus recalculables (dérive « 11 × 3 + 3 × 4 », moyenne 3,21 ; bascules sans
la variante « plancher »).

| # | Fonction | Entrée | Sortie |
|---|---|---|---|
| 1 | `compte_du_jour` | 4 tâches de 30 min + 3 de 5 min | 6 (v1 : 7, sans plafond — n° 66) |
| 2 | `compte_du_jour` | 3 sous-tâches + leur parent | 1 |
| 3 | `compte_du_jour` | 1 routine + 1 tâche + 2 activités closes | 3 |
| 4 | `statut_jour` | (travaillé, pas congé, 0, pas de plan, app non ouverte) | `sans_donnees` |
| 5 | `statut_jour` | samedi, 2 faites | `non_ouvre` |
| 6 | `statut_jour` | (travaillé, pas congé, 0, plan, app ouverte) | `evalue` |
| 7 | `journee_reussie` | (6, 5, 1 choisi, 1 fait) | vrai |
| 8 | `journee_reussie` | (6, 5, 2 choisis, 0 fait) | faux |
| 9 | `journee_reussie` | (4, 5, 0, 0) | faux |
| 10 | `palier_initial` | [5,4,6,5,3,7,5,6,4,5], rien dit | (aucun, 5, aucune carte) : l'objectif 5 reste |
| 11 | `palier_initial` | [9,10,9,1,2,1,2,9,10,9] (rafales) | (aucun, 6, carte `premier`) : proposé, pas imposé |
| 12 | `palier_initial` | [3,3,2,4,3,3,2,3,4,3], dit 5 | (5, 3, carte `journee_type`) |
| 13 | `evaluer_bloc` | N 5, (5,6,5,4,7,5,3,6,5,4) : 7/10 | `monter` |
| 14 | `evaluer_bloc` | N 6, (5,4,6,5,3,5,6,4,5,4) : 2/10 | `baisser` |
| 15 | `evaluer_bloc` | 7/10, médiane des tailles 20, référence 40 | `taille` (v1 : `monter` — n° 67) |
| 16 | `clore_bloc` | montée refusée (1er refus) | 1 bloc sauté |
| 17 | `clore_bloc` | baisse 7 → 6 acceptée au j60 | palier 6, échec (7, j60, 1) (v1 : échec non lu — n° 68) |
| 18 | `evaluer_bloc` | N 6, 7/10, échec (7, 60, 1), j90 | rien (v1 : `monter` — n° 69) |
| 19 | `evaluer_bloc` | idem, j101 | rien (v1 : `monter` — n° 70) |
| 20 | `evaluer_bloc` | idem, j102 | `monter` |
| 21 | `reference_tenir` | 14 jours de somme 70 | 5,0 |
| 22 | `reference_tenir` | 13 jours | `None` |
| 23 | `reference_tenir` | 14 × 7 | 7,0 |
| 24 | `bande_tenir` | 5 | (4 ; 6) |
| 25 | `bande_tenir` | 8 | (6,4 ; 9,6) |
| 26 | `bande_tenir` | 2 | (1 ; 3) |
| 27 | `derive_tenir` | R 5, 11 × 3 + 3 × 4 (moyenne 3,21) | `sous` |
| 28 | `derive_tenir` | R 5, 13 × 7 + 6 (moyenne 6,93) | `au_dessus` |
| 29 | `derive_tenir` | silence jusqu'au j70, jour 50 | `None` |
| 30 | `objectif_affiche` | froid | (5, `defaut`) |
| 31 | `objectif_affiche` | dit 4 | (4, `dit`) |
| 32 | `objectif_affiche` | LIBRE | (`None`, `libre`) |
| 33 | `basculer` | TENIR R 5,6 → POUSSER | palier 6 |
| 34 | `basculer` | TENIR R 5,5 → POUSSER | palier 5 |
| 35 | `basculer` | TENIR R 4,5 → POUSSER | palier 4 |
| 36 | `basculer` | TENIR R 5,51 → POUSSER | palier 6 |
| 37 | `basculer` | POUSSER → TENIR, 14 derniers = 13 × 5 + 8 (73) | R 5,21 |
| 38 | `choisir_relance` | {négligé, échéance} | échéance |
| 39 | `choisir_relance` | {négligé, dérive} | dérive |
| 40 | `choisir_relance` | ∅ | `None` |
| 41 | `etat_decroissance` | 14 ignorées de suite | pause |
| 42 | `etat_decroissance` | 13 | normal |
| 43 | `etat_decroissance` | 20 puis 1 ouverte | normal |
| 44 | `derive_pousser_journee` | (2 à 15 h, objectif 5, essentiel non fait) | vrai |
| 45 | `derive_pousser_journee` | (3, 5, non) | faux |
| 46 | `derive_pousser_journee` | (1, 5, essentiel fait) | faux |
| 47 | `variante` | ordinal 739572 | 0 |
| 48 | `variante` | 739573 | 1 |
| 49 | `variante` | 739574 | 2 |
| 50 | `evaluer_bloc` | N 5, (5,5,5,5,5,4,4,4,4,4) : 5/10 | `monter` (seuil A2) |
| 51 | `evaluer_bloc` | N 5, 4/10 | rien |
| 52 | `evaluer_bloc` | N 5, 3/10 | `baisser` |
| 53 | `evaluer_bloc` | bloc d'essai, 2 jours tenus | rien |
| 54 | `evaluer_bloc` | bloc d'essai, 1 jour tenu | `baisser` |
| 55 | `clore_bloc` | N 6, 5/10, aucune décision | `meilleur_tenu` 6 |
| 56 | `plafonner_jours` | 13 × 5 + 30 | le 30 devient 11 |
| 57 | `reference_tenir` | 13 × 5 + 30 | 5,43 (sans plafond : 6,79) |
| 58 | `derive_tenir` | R 5, 13 × 5 + 30 | `None` (dans la zone) |
| 59 | `objectif_dit` | palier 5, dit 7 | palier 7, source `dit`, aujourd'hui |
| 60 | `objectif_dit` | « plus » sur 5 ; « moins » sur 1 | 6 ; 1 (plancher) |
| 61 | `objectif_dit` | dit 15 | 400 `{"objectif":["Entre 1 et 12."]}` |
| 62 | réponse `premier` | type 3, [Oui, 3] | palier 3, `accepte` |
| 63 | réponse `premier` | type 3, [Garder 5] | palier 5, `accepte` |
| 64 | `semaine_courte` | 2 jours `evalue` + 3 `sans_donnees` | vrai (revue sans chiffres) |
| 65 | `semaine_courte` | 3 `evalue` + 2 `sans_donnees` | faux |
| 66-70 | variantes v1 (m5) | n° 1, 15, 17, 18, 19 sans plafond ni garde ni mémoire d'échec | 7 · `monter` · palier 6 · `monter` · `monter` |

Signatures : `compte_du_jour(taches, activites) -> (int, dict)` · `statut_jour(ouvre, conge, compte, plan, app) ->
str` · `journee_reussie(compte, objectif, choisis, faits) -> bool | None` · `palier_initial(comptes10, dit) -> (palier | None, journee_type, carte | None)` · `plafonner_jours(comptes) -> list` · `evaluer_bloc(etat, jour) -> str | None` · `clore_bloc(etat, jour,
decision, reponse) -> etat` · `objectif_dit(etat, nombre, sens) -> etat` · `reference_tenir(comptes) -> float | None`
· `bande_tenir(R) -> (float, float)` · `derive_tenir(R, comptes, jour, silence) -> str | None` ·
`objectif_affiche(etat) -> (int | None, str, zone | None)` · `basculer(etat, mode, jour) -> etat` · `arrondir(x) ->
int` · `constats(donnees) -> list` · `retour_absence(jours, taches) -> dict | None` · `semaine_courte(statuts) -> bool`
(≥ 3 jours `sans_donnees` dans la semaine → `semaine_courte`, `bilan_semaine` nul, A16-N9). `etat` = valeurs de `ReglagesRythme` +
comptes du bloc (dataclass gelée, jamais l'ORM).

## 7. Les sollicitations — `apps/taches/moteur/sollicitations.py`

| Type push | Heure par défaut (`Preference`) | Envoyé si | `EventType` |
|---|---|---|---|
| `plan_matin` | `heure_matin` 08:30 | aucun plan validé ce jour ET (tâches du jour + Proposé) ≥ 1 | `TACHES_PLAN_DU_JOUR` |
| `relance` « Message de 15 h » | `relance_jour` 15:00 | `choisir_relance` rend un motif | `TACHES_RELANCE` |
| `bilan_soir` | `heure_soir` 18:00 | plan validé ou ≥ 1 faite, et pas jour de revue | `TACHES_BILAN_SOIR` |
| `revue_semaine` | `heure_soir`, jour `revue_semaine` (« auto » = dernier jour travaillé de la semaine) | à la place du bilan, jamais en plus | `TACHES_BILAN_SOIR` |

- **Dû** (`due(type, maintenant, prefs, fenetre)`) : tick du balayage dans [heure, heure + 15 min).
- **Le droit, relu à chaque passage** (`views/base.a_le_droit`, LA garde du module) : un compte sans `taches_voir`
  ne reçoit ni sollicitation ni rappel ; ses rappels dus ne partent pas et deviennent `manque` après 2 h ; la
  nuit ne lui sert ni carte ni révélation.
- **Sauté, jamais différé** si l'une est vraie : fenêtre de la société fermée ; maintenant ≥ `heure_limite` (20:00) ;
  jour non travaillé pour lui ; congé ; type `off` ou dans `pauses_sollicitations` ; compte inactif ou non interne ;
  module éteint ; compte sans `ReglagesRythme` (elle ne naît qu'à la première tâche créée, invariant 29, A15) ;
  plafond atteint ; **coupe-circuit** `ReglagesSociete.balayage_actif = False` (§13 ; rappels compris). Le contrôle
  est fait par `taches` AVANT `notify(…, respect_quiet_hours=False)` : `notify` ne diffère donc jamais une
  sollicitation (critique m10).
- **Plafond** (`plafond_atteint(journal)`) : 3 ENVOIS push par jour au plus (matin, soir ou revue, UN en journée) ;
  seuls les envois comptent (une sollicitation sautée ne compte pas) ; les cartes à l'écran (canal `ecran`), les
  rappels posés et le push de test sont hors plafond.
- **Priorité de la relance** (`choisir_relance`) : 1) échéance du jour non faite (≥ 1 tâche du préfiltre `a_faire` à
  `echeance = J`) ; 2) dérive — `pousser` : compte à l'heure du tick < objectif / 2 ET (aucun essentiel choisi OU
  aucun fait) ; `tenir` : compte ≥ haut de zone ; `libre` : jamais ; 3) projet prioritaire négligé (`neglige()`, le
  projet de plus haute priorité), au plus une fois par projet et par 7 jours (IR13). Deux types dus au même tick :
  `plan_matin` > `relance` > `bilan_soir`/`revue_semaine`, l'autre est sauté.
- **Ignorée** = non ouverte dans les 3 h et aucun `POST vu/` dans ces 3 h (`vu/` pose `ouvert_le` sur les push du
  jour encore dans leurs 3 h) ; marquée `ignoree` par la nocturne. **Pause** d'un type après 14 ignorées de suite
  (`etat_decroissance`) : type ajouté à `pauses_sollicitations` + carte `pause` ; « Le réactiver » le retire ; une
  ouverture remet la série à zéro.
- **Rotation** : `variante(J.toordinal())` = `% 3` (17/11/2026 → 2).
- **Liens** (`api.md` §7) : `plan_matin`, `relance` → `/taches/aujourdhui` (la carte du moment y porte Garder ou
  Alléger) ; `bilan_soir` → `/taches/aujourdhui?ouvrir=bilan` (critique m1) ; `revue_semaine` → `/taches/revue` ; rappel → `/taches/aujourdhui?tache=<id>`
  (fiche avec « Encore 10 min · 1 h · Demain 9 h » en tête) ; test → `/taches/reglages/iphone`.
- **Rappels posés par l'utilisateur** : hors plafond, à l'heure demandée même hors fenêtre, après l'heure limite et
  en congé (`NOTIFICATIONS_TOUJOURS_IMMEDIATES`) ; groupés par minute ; dus = `jour < J` ou (`jour = J` ∧ `heure ≤`
  maintenant) ; retard > 2 h → `manque`, jamais envoyé ; tâche close, abandonnée ou supprimée → `annule` ; ≤ 5 en
  attente par tâche, ≤ 100 par utilisateur ; posé hors fenêtre → avertissement `hors_fenetre` (par le Copilote :
  carte-écho, verif-securite m9) ; ancré : `jour` recalculé quand l'ancre bouge, ancre effacée → `annule`.
- **Question du premier rappel (A17-T4)** : à la pose d'un rappel tant que `titres_notifications_demande_le` est nul,
  la réponse porte `question_titres: true` ; l'écran demande « Montrer le titre sur l'écran verrouillé ? » ; la
  réponse passe par `PATCH reglages/` (`titres_notifications`, qui pose `titres_notifications_demande_le`) ; sans
  réponse : sans titre (socle §2.8). Même question à l'étape 1 de Mon iPhone.
- **Idempotence** : sollicitation = `get_or_create` du marqueur `IncitationCoach` (unicité `taches_incit_uniq`) +
  `notify` dans la même transaction ; rappel = `UPDATE … WHERE statut='en_attente'` (1 ligne = à moi) puis `notify`
  dans la même transaction. Rejouer le balayage n'envoie rien de plus.
- **Corps** : des comptes (`textes.md` §3) ; titres seulement si `titres_notifications` ET non confidentielle ; le
  matin ne compte que les tâches du jour (A14-B1) ; `badge` = `compter_journee()` à l'envoi.

## 8. La confidentialité — `apps/taches/confidentialite.py`

- `Tache.est_confidentielle()` = `confidentiel` ∨ `projet.confidentiel` ∨ `parent.confidentiel` ∨
  `parent.projet.confidentiel` (invariant 8, A6) ; un projet est confidentiel par son seul drapeau `confidentiel`.
- `nom_pour(obj, usage, reglages=None)` — le SEUL chemin d'un titre ou d'un nom vers un texte servi ; `reglages` =
  la `ReglagesRythme` déjà lue par l'appelant (pour `titres_*`, aucune requête par appel, verif-plan M10) :

| Usage | Tâche ordinaire | Tâche confidentielle | Projet confidentiel | Notes, check-list, `en_attente_de`, lien ERP d'une confidentielle |
|---|---|---|---|---|
| `ecran` | titre | titre (cadenas) | nom | servis |
| `assistant` (`X-Taqinor-Assistant: 1`) | titre | « Tâche confidentielle » | « Projet confidentiel » | jamais (notes jamais servies à l'assistant, même ordinaires) ; une confidentielle ne correspond à aucune recherche `q` par son titre |
| `flux` | titre si `titres_calendrier`, sinon « Tâche » | « Tâche confidentielle » | — (aucun projet au flux) | jamais |
| `tuile` | titre si `titres_tuile`, sinon « Tâche » | « Tâche confidentielle » | — | jamais |
| `notification` | `None` (gabarit sans titre) ; titre si `titres_notifications` | `None` | `None` | jamais |
| `siri` (réponse de `capture/`, inv. 38) | titre (coupé à 60) | « une tâche » | « un projet » (« Ajouté dans un projet ») | jamais |
| suggestion (`titre_propose`) | gabarit fixe sans nom (§9) | — | — | — |
| rendez-vous externe (§11) | à l'écran : son titre ; sous l'en-tête assistant : « Rendez-vous » ; jamais au flux, à la tuile, en notification | — | — | — |

Les phrases composées (explication, santé, constats, revue « attend X », « déjà dans X », bloquée par, aperçu de
changement) appellent `nom_pour` pour CHAQUE objet cité, avec l'usage de la route. Hors de l'écran,
l'explication d'une confidentielle omet le fait « en attente de : {qui} », et le message de geste
« En attente de : {qui} » d'une confidentielle (`gestes/`) devient « En attente de… » (TCH127).
- **Test canari** : un projet confidentiel « Canari-7Q9 » portant une tâche « Canari-X3K », une sous-tâche, et une
  tâche ordinaire bloquée par elle, toutes du jour, avec un rappel dû et `titres_notifications`, `titres_calendrier`,
  `titres_tuile` allumés ; on lit avec l'en-tête assistant `aujourdhui/`, `journee/proposition/`, `recherche/?q=Canari`,
  `rythme/`, `projets/{id}/vue/`, `revue/projets/`, `coach/entete/`, `changement/apercu/`, `saisie-rapide/`
  (aperçu, doublon) ; puis `flux/`, `tuile/`, les charges `notify` du balayage (rappel, matin, relance), `suggestions/`
  et `IncitationCoach.donnees` ; aucune chaîne servie ne contient « Canari » (casse et accents ignorés, JSON décodé).
  Le même test sans l'en-tête montre le titre à l'écran (preuve que le canari est vivant).

## 9. Les suggestions venues de l'ERP — `apps/taches/receivers.py` (pur : gabarit, clé, destinataire)

| Famille (défaut) | Événement (charge) | Destinataire | `titre_propose` | Clé | Lien |
|---|---|---|---|---|---|
| `devis_accepte` (allumée) | `devis_accepted` (`devis, user, avenant_de`) ; ignoré si `avenant_de` | responsable de `devis.lead` (lead STRICT du devis, jamais le repli « dernier lead du client ») ; sinon personne | « Préparer le chantier du devis accepté » | `devis_accepte:<devis.pk>` | `ventes.devis` |
| `chantier_receptionne` (allumée) | `chantier_receptionne` (`installation, user`) | responsable de `installation.lead` | « Demander un avis au client : chantier réceptionné » | `chantier_receptionne:<pk>` | `crm.lead` du chantier |
| `chantier_annule` (allumée) | `chantier_annule` (`installation, company, user`) | responsable de `installation.lead` | « Comprendre l'annulation du chantier » | `chantier_annule:<pk>` | `crm.lead` du chantier |
| `visite_validee` (éteinte) | `visite_validee` (`visite, lead_id`) | responsable du lead | « Préparer le devis : visite validée » | `visite_validee:<visite.pk>` | `crm.lead` |

- **Conditions** : destinataire actif, interne, `taches_voir`, module actif, possède une `ReglagesRythme` (a déjà
  créé une tâche, invariant 29), famille allumée dans `familles_suggestions`, ET cible visible par lui via le sélecteur de l'app
  cible (A3 ; sinon rien, sans trace). `suggestions_societe` (administrateur, AVANCÉ) : l'administrateur reçoit en plus
  sa propre ligne, mêmes contrôles.
- **Anti-doublon** : `get_or_create` sur (`company`, `proprietaire`, `cle`) ; refusée ou acceptée = jamais reproposée ; retirée (annulation de l'événement) = reproposée, comme neuve, quand l'événement se reproduit ; accepter une suggestion dont la cible n'est plus lisible crée la tâche sans lien.
  `devis_acceptation_annulee` → suggestion `proposee` du devis → `retiree`.
- **Vie** : visible 7 jours (`suggestions/` ≤ 20, les plus récentes), purgée à 30 ; aucun push, hors plafond. Accepter
  → `creer_taches(source='suggestion', lien=cible)` avec `titre_propose` (ou le titre édité) ; Refuser → `refusee`.
- **Effacement 09-08, deux portes** (verif-plan M24) : (1) récepteur `lead_erased(company, crm_lead_id)` ; (2)
  fournisseur `register_dsr_provider('taches', export=None, erase=effacer_sujet)` : `effacer_sujet(company,
  subject_identifier)` résout le sujet par `crm.selectors.cibles_du_sujet` → `{"leads","clients"}`. Les deux : suppression
  dure des `SuggestionTache` à `lead_ref` ∈ leads ; tâches liées : `lien_libelle` vidé, `lien_etat = efface` (« Lead effacé ») ;
  le titre tapé par l'utilisateur reste (dit dans Vie privée). Client anonymisé (sans événement) : libellé vidé à la
  prochaine ouverture de la fiche (revérification `introuvable`/`inaccessible`). Aucun titre de suggestion n'a de nom
  à réécrire (A4).

## 10. Le flux de calendrier et la tuile — `apps/taches/moteur/flux.py`

**Flux** (`evenements_flux(taches, jour, reglages, nom_pour)`, `GET flux/{jeton}.ics`) :
- Émis : tâches `a_faire` du préfiltre (invariant 10) à `jour_prevu` ∈ [J, J+14], hors À revoir (reportées 3 fois).
  Avec `heure_debut` → événement horodaté `start_dt` = jour + heure murale, `end_dt` = + `estimation_minutes`, sinon
  + 30 min ; sans heure → journée entière. `echeance_heure` ne place jamais un événement.
- Plafonds : 8 journées entières par jour (tri : priorité décroissante, `rang_jour`, `cle_tri`), puis UN événement
  journée entière « + N autres tâches » (UID `taches-autres-<aaaammjj>`) ; 200 événements au total, le dernier jour
  tronqué. UID `tache-<id>`.
- Exclus : faites, en attente, À trier, En réserve, bloquées, projets en pause, sous-tâches, activités ERP,
  obligations. `DESCRIPTION` vide, jamais de notes ; `SUMMARY` = `nom_pour(t, 'flux')` ; `calname` « Tâches
  Taqinor » ; `Cache-Control: no-store` ; jeton inconnu ou révoqué → 404.

**Tuile** (`GET tuile/`, `tuile_pure(…)`, mêmes règles de sélection que l'écran) :
- `faites`, `prevues` = `progression` ; `objectif` = `objectif.nb` (`null` en `libre`, `arrondir(R)` en `tenir`) ;
  `essentiel` = {`faites`, `prevues`}.
- `top` ≤ 6 TÂCHES ouvertes GARDÉES dans l'ordre de l'écran : Essentiel, Prévu (blocs à leur heure en tête), Ce soir
  — jamais Proposé (comme la pastille, A16-N5) ; les activités ERP comptent dans `prevues` et `reste` mais ne sont
  jamais titrées sur la tuile (IR15). `reste` = pastille − montrés. `prochaine_echeance` = tâche ouverte du
  préfiltre à plus petite (`echeance`, `echeance_heure`) ≥ J. Titres par `nom_pour(…, 'tuile')`, jamais de notes.
- `lien` = `https://erp.example/taches/aujourdhui` dans l’échantillon : l’hôte de la requête suivi de `/taches/aujourdhui`. Débit 120/h ; jeton refusé → 401 neutre.

## 11. Les agendas externes — `apps/taches/agenda_externe.py` (réseau) et `moteur/ics.py` (pur)

ESSENTIEL (A18-M4) : jusqu'à 3 adresses ICS par utilisateur (Microsoft 365, Google, iCloud…), lues côté serveur,
affichées en lecture seule, retranchées du temps disponible.

**Ajout** (`POST agendas-externes/`) : `webcal://` est réécrit en `https://` (même hôte, même chemin : l'iPhone donne
ses liens publics ainsi, IR22) ; tout autre schéma → 400 `{"url":["Adresse https publique attendue."]}` ; 4e adresse →
`{"url":["3 agendas au plus."]}` ; adresse déjà là → `{"url":["Cet agenda est déjà ajouté."]}` ; `hote` posé ; l'hôte est
validé par `apps/publicapi/validators.py` ; lecture immédiate, `dernier_etat` rendu.

**Lecture** (`lire_agenda_externe(agenda, du, au)`, garde de l'invariant 33), dans cet ordre, chaque échec posant son
`EtatAgendaExterne` et rien d'autre (jamais d'exception à l'écran) :

| Étape | Règle | Échec → `dernier_etat` |
|---|---|---|
| 1 Schéma | `https://` seulement | `pas_https` |
| 2 Hôte | résolu À CHAQUE lecture ; TOUTES les adresses obtenues publiques (ni privée, ni boucle, ni lien local, ni réservée, ni multidiffusion) ; connexion vers l'adresse vérifiée | `adresse_privee` · `injoignable` (pas de résolution, refus, TLS invalide) |
| 3 Redirections | 3 au plus, chacune revérifiée (étapes 1-2) | `adresse_privee` · `pas_https` |
| 4 Bornes | corps ≤ 2 Mo, délai total ≤ 10 s (IR23) | `trop_grande` · `delai` |
| 5 Contenu | `BEGIN:VCALENDAR` présent, au moins un VEVENT lisible ou un calendrier vide | `illisible` |
| 6 Succès | événements mis en cache par adresse, 15 min (IR23) ; `dernier_chargement_le`, `ok` | — |

`rafraichir/` ignore le cache. Les événements ne vont JAMAIS en base. Un échec REMPLACE le texte en cache de l'adresse
et y est retenu 15 min comme un succès : l'adresse n'est pas relue pendant ce temps, ses rendez-vous sont absents
(jamais d'anciens présentés comme frais) et son état est dit (Agenda, Réglages) ; « Rafraîchir » (`rafraichir/`) ou un
nouvel enregistrement de l'adresse la relit aussitôt (revue F2 #6). Le délai total est une échéance absolue (connexion,
redirections, en-têtes, corps) et une requête d'écran borne ensemble la lecture de tous ses agendas (10 s).

**`lire_evenements(texte, du, au) -> tuple[RendezVousPur]`** : lignes dépliées (RFC 5545 : une ligne commençant par une
espace continue la précédente) ; par VEVENT : `DTSTART`, `DTEND` ou `DURATION`, `SUMMARY` (échappements `\,` `\;` `\n`
retirés), `TZID` converti en `Africa/Casablanca` par `zoneinfo` (UTC si `Z`, heure locale sinon) ; `VALUE=DATE` →
`journee_entiere` ; `STATUS:CANCELLED` ignoré ; sans DTEND ni DURATION : 0 min (ou un jour si date seule). **`RRULE`
non lu en v1** : seule l'occurrence de `DTSTART` apparaît — limite dite dans l'aide (§2.8 de `textes.md`). Fenêtre
lue : [J − 1, J + 42] ; 2 000 événements au plus par adresse (au-delà : `trop_grande`). `cle` = `<agenda_id>-<8 hex du
SHA-256 de UID + DTSTART>`.

**Affichage** : Aujourd'hui → horodatés dans Prévu à leur heure (`rendez_vous`), journée entière dans « Toute la
journée » ; Agenda → blocs en lecture seule (`externes`) ; jamais au flux, à la tuile, dans une notification, ni dans
la pastille ; sous l'en-tête assistant, `titre` = « Rendez-vous » ; jamais comptés comme tâches.

**`minutes_rendez_vous(evenements, jour, fenetre) -> int`** : rendez-vous horodatés de `jour`, coupés à `fenetre`
(heures de travail de la société), unis s'ils se chevauchent, en minutes ; journée entière = 0. Exemples §3.6.

## 12. Le Copilote sans modèle — les quatre demandes prêtes (A18-M3)

Les quatre boutons appellent des routes DÉTERMINISTES et rendent leur carte SANS appel au modèle de langage : ils
marchent sans clé et sous tout fournisseur (`api.md` §8).

| Demande | Route | Ce qu'elle rend | Carte |
|---|---|---|---|
| Planifie ma journée | `GET journee/proposition/` | Proposé (§3.4) ; « Garder ces N » → `journee/planifier/` express | `plan_propose` |
| Aide-moi à prioriser | `GET journee/priorites/` | `classer_priorites` (ci-dessous) | `priorites` |
| Range ma liste | `POST saisie-rapide/` `{"ids":[À trier],"apercu":true}` | pour chaque tâche À trier, le projet suggéré par les mots (§1.10 point 9), sinon rien ; validation au doigt | `capture_apercu` |
| Où j'en suis ? | `GET journee/point/` | `point` (ci-dessous) | `point` |

**`classer_priorites(items, J, …) -> (lignes, garder_n, plus_tard)`** : toutes les tâches ouvertes du préfiltre NON
gardées aujourd'hui, dans l'ordre de Proposé étendu à tout le pool (ce qui presse, puis le tour des projets SANS
limite N), puis celles d'À revoir (motif dit) ; `garder_n` = N de §3.4 ; chaque ligne porte sa `raison` (ou son
`motif`). Gestes par ligne : Essentiel → `journee/essentiel/` (après `planifier(J)`), Aujourd'hui → `planifier(J)`, Plus
tard dans la semaine → `planifier(plus_tard)` ; « Garder ces N » → `journee/planifier/` avec les `garder_n` premières.
Jeu de §3.4 (N = 5) : R1, R2, A1, V1, M2, D3, A2, S1, V2, M3, D4, A3, S2, V3…V12, puis R4 (`reportee_3_fois`), R3
(`retard_ancien`) — l'ordre d'À revoir est `cle_tri` : R4, dans Ventes (priorité haute), passe avant R3, dans Admin (basse) ; `garder_n` = 5 (recalculé par `integ2/propose.py`).

**`plus_tard`** = le prochain jour travaillé APRÈS J dans la même semaine (lundi-dimanche), sinon le premier jour
travaillé de la semaine suivante. Mar. 17/11 (18 férié) → jeu. 19 ; ven. 20 → lun. 23 ; jeu. 19 → ven. 20.

**`journee/point/`** : `objectif`, `progression` (avec `disponible_minutes`) ; `essentiel_restant` = essentielles
ouvertes ; `prochaine` = la première ligne ouverte de Prévu hors essentielles, blocs encore à venir d'abord (heure ≥
maintenant), sinon Ce soir, sinon `null` ; `restes_nb` = gardées ouvertes ; `rendez_vous_restants` = rendez-vous
externes du jour qui commencent après maintenant ; `carte_du_moment`.

**`taches.tache.modifier`** (✎, `PATCH taches/{id}/`) : sur demande EXPLICITE seulement (« passe la TVA en priorité
haute »), champs `priorite`, `echeance`, `projet_id` ; `lock_version` requis ; `geste_id` rendu (Annuler) ; dans un tour
MARQUÉ (garde A5 ci-dessous) : carte-écho ; ≤ 3 écritures par tour. En pratique, désigner une tâche EXISTANTE par son
nom demande à l'assistant de la chercher (une lecture) : la modification arrive donc en carte à valider au doigt, puis
« Modifiée · Annuler ». Une création dictée d'un trait, sans lecture avant elle, s'écrit sans carte.

**Garde A5 — fermée par défaut (relecture adverse de la fusion 3).** Toute action qui n'est pas une écriture
`taches.*` — lecture ou écho `taches.*`, action d'une autre app, lien de document, lecture SQL, schéma, métrique
gouvernée, tout outil fixe sauf `report_gap` — MARQUE le tour dès son appel ; sous cette marque toute écriture
`taches.*` devient une carte à valider (rien n'est écrit avant le doigt). Une écriture exécutée ne rend au modèle que
ses ids, nombres, booléens, dates et heures (la carte garde tout) ; son échec marque le tour. Une action `taches.*`
inconnue qui n'est ni GET ni écho est traitée comme une écriture. La marque SUIT LA CONVERSATION : chaque message
d'agent gardé porte `contenu_tiers` (la marque de son tour, héritée comprise) ; un tour est marqué si un échange relu au
modèle l'est (LangChain : la fenêtre des 2 derniers échanges ; natif : la conversation gardée, récapitulée comprise) ;
un message sans la marque (écrit avant) compte comme marqué ; elle tombe à « Effacer » ou à l'expiration ; la reprise
après confirmation est marquée. La QUESTION elle-même marque le tour quand elle porte un passage entre guillemets, une
liste à virgules de 3 éléments ou plus, des puces à tirets ou une numérotation « 1. 2. » (texte collé). Limite écrite :
un texte collé court, sans guillemets ni liste, ne se distingue pas d'une demande tapée. Pourquoi plus strict que la
lettre de A5 (« dès qu'un contenu non fiable est entré dans le tour ») : une lecture `taches.*` rend des libellés
de leads, des résumés d'activités et des textes d'aperçu ; aucune liste blanche de lectures « sûres » n'a pu être
prouvée.

## 13. Activation par étapes et coupe-circuit

- **Activation** (A18-M5, M8, invariant 28) : F1 invisible (`taches_voir` déclaré, accordé à aucun rôle) ; fin de F2 :
  accordé au seul rôle Administrateur (Directeur exclu, `donnees.md` rév. 3) ; depuis le 18/11/2026 (TCH168) le
  Directeur le porte aussi — `init_roles` range le propriétaire et tout superuser sur ce rôle, l'exclure privait le
  fondateur de son module ; les autres rôles internes l'obtiennent par la case de l'éditeur des rôles, quand Reda le
  décide ; jamais aux rôles portail ni aux rôles à liste blanche d'apps.
- **Coupe-circuit** (invariant 39) : `ReglagesSociete.balayage_actif = False` (`PATCH reglages-societe/`, administrateur)
  → `taches.balayer` n'émet RIEN pour la société (ni sollicitation ni rappel), lu à chaque passage, sans redéploiement ;
  les rappels dus pendant la coupure deviennent `manque` au-delà de 2 h (jamais une rafale à la remise en marche) ;
  absent = actif.

## Décisions de l'intégrateur

- **IR1** Le titre garde les glyphes d'origine ; seule la copie d'analyse est normalisée, à longueur égale.
- **IR2** Moments nus et « midi / noon » ne sont lus qu'en position de jeton (§1.4).
- **IR3** Normalisation caractère par caractère sans changement de longueur.
- **IR4** Date impossible et durée hors bornes : texte + `date_invalide` / `duree_hors_bornes`.
- **IR5** « Nh » nu ≤ 6 = durée, ≥ 7 = heure ; « NhMM » nu ≤ 4 = durée, ≥ 5 = heure.
- **IR6** Couleur d'office par `couleur_d_office(user)` (spec-4 §A sur les 10 clés).
- **IR7** « en réserve » en fin de ligne = « un jour » ; jamais à la capture.
- **IR8** `apres_fait` hebdomadaire = premier jour du masque ≥ fait + 7n − 6 ; seul `jours_ouvres` lit les fériés.
- **IR9** La capture lit « projet <nom> » en tête (Siri ne dit pas « dièse »).
- **IR10** Une journée allégée ne remplit plus Proposé (`allege_le`).
- **IR11** Les `reportee_3_fois` du bilan sont marquées, jamais bloquantes.
- **IR12** « Froid » ⇔ `bloc_debut` nul ; l'objectif vit dans `palier` seul ; le premier objectif calculé est proposé.
- **IR13** La relance « projet négligé » ne vise pas le même projet plus d'une fois en 7 jours.
- **IR14** Suggestions réservées aux comptes qui ont une `ReglagesRythme`.
- **IR15** La tuile ne titre pas les activités ERP.
- **IR16** `sans_prochaine_action` garde la règle de la référence ; seule la phrase change.
- **IR17** Sous l'en-tête assistant, une tâche confidentielle ne correspond à aucune recherche par son titre.
- **IR18** Q nommé dans « négligé » = le projet moins prioritaire le plus avancé.
- **IR19** N = objectif − faites − gardées ouvertes (A18-M1).
- **IR20** Carte `alleger` : même seuil que la relance de dérive.
- **IR21** (rév. 3) Ce qui presse est TOUJOURS montré entier en tête de Proposé, même au-delà de N : sinon une tâche
  d'hier ou une échéance de jeudi, sorties d'À revoir par A18-M2, ne seraient plus nulle part. Le tour des projets prend
  `max(0, N − presse)` places.
- **IR22** (rév. 3) `webcal://` est réécrit en `https://` à l'ajout (c'est la forme des liens publics d'iCloud) ; la
  lecture reste https seule.
- **IR23** (rév. 3) Bornes de lecture d'un agenda externe, choix de conception (aucun chiffre n'est donné par la
  référence) : 2 Mo, 10 s, 3 redirections, cache 15 min, fenêtre J − 1 à J + 42, 2 000 événements.
- **IR24** (rév. 3) La capacité n'est plus un filtre de Proposé (A18-M1 ne la cite pas) : elle est montrée comme
  surcharge à côté de « Garder ces N ».
- **IR25** (rév. 3) Les tâches d'un projet prévues un jour futur ne sont pas proposées au tour (elles ont déjà leur
  jour) ; elles restent visibles dans la suite dépliée et dans l'agenda.
- **IR26** (rév. 3) Un rappel dû pendant le coupe-circuit devient `manque` au-delà de 2 h : la remise en marche
  n'envoie pas de rafale.

## Manques de la référence données/API (révision 3)

Repris par la révision 3 : bilan `?ouvrir=bilan`, valeur `pause` de `CarteDuMoment`, comptage de la semaine courte
(laissé à `sans_donnees`, sans objection). Restent :

1. `api.md` §8 (note des actions) dit encore « Passer à N » pour la carte `rythme` : à remplacer par « Monter à N » /
   « Descendre à N » (libellé décidé, `textes.md` §4.2).
2. `api.md` (« À répercuter ») ajoute `objectif_dit` à `EtatRythme` ; `donnees.md` y met `objectif` (en vigueur).
   J'applique `donnees.md` (I17 : aucune source d'objectif hors de `palier`) ; `objectif_dit` reste le nom de la fonction.
3. `api.md` §4 : l'erreur d'un schéma autre que https ne dit pas que `webcal://` est accepté et réécrit (IR22).
4. Les bornes de lecture d'agenda (IR23) ne figurent dans aucune des deux références : à y reporter si elles doivent
   y faire foi.

## Ce que je n'ai pas repris, et pourquoi

- « Arrondi inférieur » et le seuil 6/10 → demie vers le bas, 5/10 (A2).
- Proposer la journée type à chaque baisse quand l'écart ≥ 3 : non mesuré.
- Le premier palier appliqué d'office → proposé.
- La capture « toujours dans la Boîte, sans analyse » → A1.
- Le choix `demain` au bilan, le triage obligatoire, le mode `complet`, le 400 sur les reportées 3 fois.
- La pastille avec Proposé → gardées seules ; les obligations « à leur heure » → Toute la journée ; la ★ sur Proposé.
- (rév. 3) `cle_tri` comme règle du choix de Proposé et le pool « bande 1 / 2 » (révisions 1-2) → ce qui presse puis
  tour des projets (A18-M1/M2) ; `cle_tri` ne sert plus qu'à l'ordre dans une section.
- (rév. 3) Les motifs `jour_passe`, `echeance_passee`, `echeance_proche` d'À revoir → raisons de Proposé.
- (rév. 3) Le filtre de capacité de Proposé (révisions 1-2) → montré comme surcharge (IR24).
- (rév. 3) Plafond des micro-tâches, garde de taille, mémoire d'échec, constat C6 dans la première livraison (m5, m6) :
  règles gardées, éteintes en v1.
- Le pré-calcul d'un instant UTC pour les rappels ; visites de maintenance, auto-planification, rappel de lieu.

## Révision 2 : ce qui a changé

Pastille gardées seules ; `carte_du_moment` ; Proposé N = objectif − faites − gardées, replié après Alléger ; Toute la
journée ; bilan « Tout reporter » ; décision `garder` ; `palier` seule source, premier objectif proposé ;
`projets_communs[]` ; hors ligne et conflit ; question du premier rappel ; recalculs 65/65, 25/25, 300/300.

## Révision 3.1

Mon rythme montre les 10 derniers jours travaillés (§6.2) ; textes des maquettes unifiées repris dans `textes.md`.

## Révision 3 : ce qui a changé

1. Primauté A1-A18, `critique-finale.md`, `verif-plan-a-blanc.md`, référence rév. 3 ; noms revérifiés par script.
2. §0.1 : types d'entrée des modules purs (`ItemPur`, `LignePure`, `PlanPur`, `EtatRythme`, `JourCompte`,
   `RendezVousPur`, `Fenetre`, `Analyse`, `PlanPropose`) et fonctions de `saisie/dates_pures.py`.
3. §3 : Proposé = ce qui presse (retard ≤ 7 j, échéance passée ≤ 7 j, échéance dans 2 jours travaillés) puis tour des
   projets par prochaine action ; raisons par ligne ; suite par projet ; où s'applique `cle_tri`.
4. Nouveau jeu de Proposé (30 tâches, 5 projets + sans projet, N = 2, 3, 5, 8, 13, monopole) ; `cle_tri` 300/300 inchangé.
5. À revoir = reportées 3 fois, retards de plus de 7 jours, activités ERP en retard.
6. §11 agendas externes (ajout, garde, lecture ICS, cache, erreurs, affichage) ; temps disponible − rendez-vous.
7. §12 Copilote sans modèle : quatre demandes, `classer_priorites`, `plus_tard`, `journee/point/`, `taches.tache.modifier`.
8. §13 activation par étapes et coupe-circuit ; `notify` jamais différé.
9. §6 : plafond des micro-tâches, garde de taille, mémoire d'échec et C6 hors v1 ; règle de `repere.p60` ; « Monter à ».
10. §7 bilan `?ouvrir=bilan` ; §4.10 carte `pause` ; §8 usages `siri` et `reglages` ; §9 deux portes d'effacement.
11. Recalculs : rythme 70/70 (65 + 5 variantes v1), récurrence 25/25, `cle_tri` 300/300, Proposé et temps disponible
    par `integ2/propose.py`.
