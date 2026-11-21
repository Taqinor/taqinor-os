# Brief A — dégel des tâches après les décisions du fondateur du 21/11/2026 (campagne L5 calepinage, vague 2)

Tu es un rédacteur de tâches v3 (TAQINOR OS). Tu n'édites AUCUN fichier du dépôt ni AUCUN fichier de lot : tu écris
UN fichier de sortie `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\integ\A-sortie.md`
qui contient, pour chaque tâche traitée, la ligne COMPLÈTE de remplacement (une ligne physique par tâche, format v3
identique aux lots), rangée sous la ligne `## → <plan>` de son propriétaire (`## → docs/plans/PLAN_AUDIT_CALEPINAGE.md`
pour le propriétaire calepinage, `## → docs/plans/PLAN_AUDIT_DEVIS.md`, `## → docs/WEB_PLAN.md`, etc.), et, pour une
tâche à SUPPRIMER, une ligne `SUPPRIMER ACALnnn — <raison en une phrase>` sous le titre `## Suppressions`.
L'intégrateur remplacera chaque ligne par id. Dépôt (lecture seule) : `C:\dev\taqinor-os\.claude\worktrees\calpinage-module-enhance-04bba5`.
Lots (lecture seule) : `…\scratchpad\l5\lots2\lot-D1.md … lot-D7.md` et `lot-D<n>-autres-plans.md`.

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## Forme (lis d'abord)
- Règle de forme v3 : `…\scratchpad\plan\brief-redacteur.md` (14 clauses dans l'ordre, ancres `fichier::symbole` qui
  EXISTENT, `n/a — raison`, une ligne physique, `Files:` en dernier, `(@model: …)`, catégorie) puis l'addendum
  `…\scratchpad\l5\brief-redacteur-vague2.md` (tampon `(gen manuel 207c7a7)`, mention `STATIQUE (lecture du 21/11 sur 207c7a70e)`,
  constat `C-ACAL-L5-<id>`, sections, propriété).
- Validateur : `PYTHONIOENCODING=utf-8 python "…\scratchpad\l5\integ\v2.py" "…\scratchpad\l5\integ\A-sortie.md"` → 0 KO
  (il attend le propriétaire du `## →` courant). Il est lent (≈ 1-2 s par tâche) : lance-le une fois à la fin, corrige, relance.
- Une tâche qui change ce que voit le client dit : « devis déjà envoyés : inchangés ; dry-run des écarts montré à Reda
  avant application ». Rien ne passe par `/proposal` (règle #4) sauf ce que la décision dit ; aucun prix hors devis.
- Une tâche répondue ne garde ni `[GATED …]` ni texte conditionnel (« Si (a) : », « selon la décision de Reda ») : elle
  CITE l'id de la décision (`D-ACAL-3x`) comme fait établi. `scripts/check_decisions.py` refuse le conditionnel.
- `@after` : seulement vers une tâche du MÊME plan cible ; une dépendance vers un autre plan s'écrit en phrase dans la
  clause Constat (« après ACALnnn de docs/plans/PLAN_X.md »).
- Numéros de migration : jamais choisis ; écrire « numéro de migration à relire sur origin/main à la construction ».

## Décisions du fondateur (21/11/2026, toutes RÉPONDUES)
- D-ACAL-35 : pour les NOUVEAUX devis avec calepinage enregistré, le PDF imprime la production de la pose réelle ; sans calepinage : standard ville ; devis envoyés inchangés ; écarts montrés à Reda avant tout changement.
- D-ACAL-36 : toit + champ au sol ⇒ l'écran liste les surfaces avant de générer le devis, toutes cochées par défaut ; la commerciale peut en décocher.
- D-ACAL-37 : éléments visibles du client hors PDF du devis (jamais de prix ; chiffres = ceux du devis) : les QUATRE sont autorisés — (a) soleil animé sur la page publique du devis, (b) courte vidéo 3D pour WhatsApp, (c) panneaux sur la photo du site, (d) fiche « pertes en mots simples » remise au client. Chacun reste HORS `/proposal` et réutilise la page publique de proposition / son suivi existants là où le juge D6 l'a dit.
- D-ACAL-38 : toit en pente, panneaux posés à plat sur le toit (affleurant) : le devis ne contient que le kit de fixation (crochets, rails, pinces), ni structures acier ni socles lestés ; ceux-ci restent pour toit plat et champ au sol ; devis envoyés inchangés.
- D-ACAL-39 : sans consommation connue : aucune économie, aucun TRI, aucun retour affiché ni imprimé ; l'écran dit « renseignez la facture » et mène au champ. (L'intégrateur traite ACAL976/905 : NE LES TOUCHE PAS.)
- D-ACAL-40 : pompage : le bilan du réservoir jour par jour reste INTERNE (écran et rapport d'étude) ; le document client agricole de 3 pages ne change pas.
- D-ACAL-41 : exemples : uniquement des MODÈLES de la bibliothèque marqués « Exemple », attachés à aucun lead ni client, sans devis, jamais comptés dans les chiffres ; rien d'autre en production.
- D-ACAL-42 : distributeurs : UN dossier marocain générique que l'équipe remplit une fois (pièces, limites, chacune avec sa source), rien de prérempli ni deviné ; des profils par distributeur viendront plus tard (réserve).

## Ce que tu fais (une entrée par id, dans cet ordre)
1. ACAL968 (lot-D7.md, GATED D-ACAL-36) → buildable, section M1 : cases à cocher des surfaces, TOUTES cochées par défaut, décochables, liste visible avant « Générer le devis ». Vérifie qu'elle ne double pas ACAL915/916 (D7) : elle les complète.
2. ACAL927 (lot-D7-autres-plans.md, plan DEVIS, GATED) → buildable selon D-ACAL-38, section M1 (P0 : visible au PDF) ; niveau de règles + dry-run des écarts comme pour toute figure client ; nomme le golden/test à réaligner seulement au nouveau niveau.
3. ACAL697 (lot-D4.md, GATED) → buildable selon D-ACAL-37(d) : la fiche est remise au client (lien sur la page publique de proposition ou pièce interne envoyée par la commerciale — choisis d'après le code : ce qui existe déjà pour partager hors `/proposal`), sans prix, chiffres = servis. ACAL898 (lot-D6.md) est un DOUBLON (même fiche en 6 postes) : `SUPPRIMER ACAL898`.
4. ACAL896 (vidéo d'orbite WhatsApp), ACAL897 (modules sur la photo, client) (lot-D6.md) → buildable selon D-ACAL-37(b)(c). ACAL897 se construit APRÈS ACAL528-529 (lot-D1.md : tracé des modules sur la photo et export interne) — même plan : `@after: ACAL529` ; vérifie que 528/529 ne contredisent pas D-ACAL-37(c) (sinon, réécris-les aussi).
5. D-ACAL-37(a) : soleil animé sur la PAGE PUBLIQUE du devis. La moitié calepinage est ACAL487 (groupe du 20/11, `docs/plans/PLAN_AUDIT_CALEPINAGE.md`, GATED « autre propriétaire ») — n'y touche pas. Cherche (`git grep -n "soleil" docs/WEB_PLAN.md docs/plans`) si la moitié de la page publique existe déjà ; sinon écris-la, id ACAL1026, sous le plan de son propriétaire (`python scripts/check_ownership.py --owner-of <fichier>` sur le fichier de page publique concerné). Sa dépendance à ACAL487 s'écrit en phrase (autre plan).
6. ACAL895 (lot-D6.md, GATED) → buildable selon D-ACAL-41 : semis IDEMPOTENT de modèles de bibliothèque marqués « Exemple », aucun lead, client, utilisateur ni devis créé, jamais compté dans les chiffres (nomme l'endroit où les compteurs les excluent).
7. ACAL899 (lot-D6.md) et ACAL785 (lot-D5.md), GATED distributeurs → réécrits selon D-ACAL-42 (UN dossier marocain générique rempli une fois par l'équipe, chaque pièce et limite avec sa source, rien de prérempli). S'ils portent la même surface, garde-en UN et `SUPPRIMER` l'autre. Relis aussi ACAL822 (lot-D5.md : gabarit réglementaire qui porte un distributeur) : s'il contredit « générique d'abord », réécris-le ou supprime-le, et dis pourquoi.
8. ACAL765 (lot-D4.md, bilan carbone) : reste GATED, mais la raison devient : `[GATED : attend un facteur d'émission du réseau marocain daté et sourcé — recherche documentaire à mener par une session ultérieure, pas une question au fondateur]` (n'écris ni « décision » ni « réponse » dans le crochet).
9. ACAL804 et ACAL814 (lot-D5-autres-plans.md, plan DEVIS) : remplace toute mention « décision de Reda » par D-ACAL-40 (bilan INTERNE, document client inchangé). ACAL849 (même fichier, GATED) : `SUPPRIMER` si une autre tâche montre déjà le bilan en interne (écran ou rapport d'étude : cherche dans lot-D5.md) ; sinon réécris-la en interne seulement (propriétaire calepinage ou devis selon les fichiers).
10. Deux constats de relecteurs restés sans tâche (dossier `…\scratchpad\l5\T1\` et `docs/audits/l5-calepinage/registre/constats/T1-*.jsonl` sur le dépôt) : **T1-T1-006** (lien des raccourcis clavier montré sur écran tactile) → ACAL1027 ; **T1-B1-016** (croquis grisé du schéma unifilaire) → ACAL1028. Lis le constat, trouve la cause `fichier::symbole`, écris la tâche (propriétaire réel ; section M2 sauf si P0/P1).

## Compte rendu (≤ 25 lignes, via ta réponse finale)
Ids écrits (plan, section), ids supprimés (raison), prémisses trouvées fausses, dernière ligne du validateur, et toute
décision encore nécessaire du fondateur (une phrase) — n'en invente pas.
