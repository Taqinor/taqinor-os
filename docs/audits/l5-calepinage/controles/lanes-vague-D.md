# Vague D — construire les décisions du fondateur du 23/11/2026

Le fondateur a répondu le 23/11 (questions interactives) à toutes les décisions ouvertes du module, puis a dit :
« Build everything now ». Sa règle générale, mot pour mot : « i only want one engine calculating every number so no
more then one number for each value and you keep the most realistic number ». Ses réponses sont dans
`docs/audits/decisions.yml` (D-ACAL-75 à D-ACAL-96, champ `reponse` et fin du champ `source`).

Règles de travail : `docs/audits/l5-calepinage/T2/brief-lanes.md` (à lire en entier ; §0 à §6, bloc d'ancrage compris).
Chaque tâche ci-dessous EXISTE au plan (`grep -n "<ID> —" docs/plans/PLAN_AUDIT_*.md`, ligne à 14 clauses ;
`python scripts/audit_tache.py <ID>` donne ses clauses calculées). Son préfixe « [GATED : décision … ouverte] » est
périmé : la décision est répondue, la réponse PRIME sur toute alternative « si (a) … si (b) » du texte.

Communs à toutes les lanes :
- Base : la branche LOCALE d'intégration `claude/calpinage-module-l5-aadbde` (première commande donnée dans ton message).
- Un commit par tâche, test rouge d'abord dans le module de test existant ; aucun `git push` ; aucun `docker compose` ;
  rien vers la production ; tu n'édites ni `docs/plans/*`, ni `docs/CODEMAP.md`, ni `docs/openapi-schema.yml`.
- Un chiffre vu par un client ne change QUE comme la décision le dit ; les devis déjà ENVOYÉS ne sont jamais recalculés
  ni modifiés (règle du 08/10 : nouveaux rendus seulement). Aucun `prix_achat` vers un écran ou un document client.
- Le PDF du devis (`apps/ventes/quote_engine/`) : tu n'y touches que si ta tâche le nomme.
- Gardes qui ont rougi la CI aujourd'hui : aucun littéral de perte en dur dans `apps/calepinage` hors des fichiers de
  données (`'perte_x': 12.3` dans un test ou un service est refusé : passe par les données ou par des variables) ; aucun
  `skipTest` ; aucun test serveur qui lit un fichier du front ; un test de logique pure (`*.test.mjs`) lit parfois une
  liste figée (racines de jetons, repères `cal-*`) : mets-la à jour dans le même commit ; goldens du devis et du CRM
  (`apps/ventes/tests/golden/`, `apps/crm/tests_scission_golden`) : toute clé ou texte servi qui change se recapture
  dans le même commit (lis `C:/Users/kasri/.claude/projects/C--dev-taqinor-os/memory/plan-drain-ci-bug-classes.md`,
  entrées 6, 8, 16, 22, 36, 46).
- La pile de conteneurs est chargée : UN appel `tester.sh` à la fois, modules touchés seulement, sauf si ta section
  demande une suite entière.
- Une tâche impossible proprement : sortie « impossible » avec la raison ; ne bloque pas la lane.
- Fichier d'événements : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/l5b/T2-lane-<nom>.jsonl` (`"tour":4`).

## Lane « pertes-simulation » (serveur du calepinage : données, cascade de pertes, file de simulation)

1. **ACAL1968 + ACAL1349 — valeurs de départ des quatre pertes** (D-ACAL-82). Valeurs ACCEPTÉES par le fondateur :
   salissure 3 % par an ; dégradation initiale 1,5 % (PERC et technologie inconnue), 1 % (TOPCon, HJT) ;
   indisponibilité 2 % ; câbles 1,5 % en continu + 1 % en alternatif (valeurs de conception quand les longueurs réelles
   ne sont pas connues ; un calcul sur câbles réels PRIME). Sources, fourchettes et conditions :
   `docs/audits/l5-calepinage/controles/R-pertes-par-defaut.md` — cite-les dans les données (`apps/calepinage/data/
   profil_depart.json`, mêmes champs de source que les valeurs déjà présentes). Chaque valeur est servie et affichée
   « supposé » avec sa source, et reste modifiable par société. Fini quand : « Démarrage rapide » sur une société neuve
   donne un résultat COMPLET (plus aucun des quatre postes « non renseigné »), et qu'un résultat complet est accepté par
   `apps/ventes/horaire/productible_pose.py::base_depuis_servi` (lis-le, ne l'édite pas) : test de bout en bout côté
   calepinage (`selectors_devis`).
2. **ACAL1671 — chaleur des panneaux par type de pose** (D-ACAL-84) : châssis ⇒ ligne « pose libre » ; affleurant ⇒
   ligne « dos isolé ».
3. **ACAL1987 (neuve) — la simulation part seule** (D-ACAL-90 RENVERSÉE : « Simulation must start by itself »). À
   l'enregistrement d'une pose complète (toit, panneaux, matériel électrique désigné), la simulation est mise en file
   d'elle-même par la file existante (cherche `recalculer_simulations_societe`, le job de simulation et sa borne de
   livraisons) ; un enregistrement sans changement de conception n'en relance pas ; l'écran dit « Simulation en
   cours… » puis le résultat, sans clic. Fini quand : enregistrer une pose neuve crée UN job ; ré-enregistrer sans geste
   n'en crée pas ; une pose incomplète n'en crée pas et dit ce qui manque. Le bouton « Simuler » reste (relance à la main).
4. **ACAL1967 — même forme horaire de consommation que le devis** : le calepinage prend le profil choisi au CRM (présence
   en journée du résidentiel, archétype du commercial) par un sélecteur de `apps/ventes` / `apps/crm`, au lieu d'une
   forme uniforme.
Fichiers interdits (une autre lane les édite) : `apps/calepinage/services/electrique.py`, `equipements.py`, `liens.py`,
`creation.py`, `pret_a_envoyer.py`, `receivers.py`, la vue et le contrat de `GET resultat/`, `EtapeResultats.jsx`.
Avant ton rapport : la suite ENTIÈRE `apps.calepinage` une fois (`tester.sh … pertessimu apps.calepinage`, ≈ 40 min :
lance-la en dernier et donne les nombres ; les échecs « front absent de ce montage » et `IndexError` de
`parents[5]` sont connus et locaux — liste les AUTRES).

## Lane « ombrage-p90-nasa » (serveur du calepinage : ombrage proche, incertitude, seconde source météo)

1. **ACAL1407 + ACAL1501 — l'ombre proche se mesure sur les panneaux posés** (D-ACAL-83) : moyenne sur les panneaux
   posés ; sans panneau, sur une grille du pan. Plus une commande de gestion qui LISTE (sans rien écrire) les
   calepinages dont la perte d'ombrage change et de combien (`--appliquer` absent : c'est une liste ; le recalcul se
   fait à la prochaine simulation). Fini quand : obstacle au centre d'un pan dont les panneaux sont ailleurs ⇒ perte
   proche de 0 ; obstacle devant les panneaux ⇒ perte ; pan sans panneau ⇒ grille.
2. **ACAL1672 — le P90 compose les incertitudes** (D-ACAL-85) : variabilité entre années + incertitude du modèle, de la
   météo et de la fiche, CHACUNE citée avec sa source. Si le texte de la tâche et `docs/audits/l5-calepinage/T2/
   R2-fonctions.md` ne donnent pas de valeur publiée pour une composante, cherche-la (10 recherches web au plus, pages
   ouvertes par toi, aucune donnée de l'entreprise dans la recherche) ; sans source ouverte : la composante est omise
   et DITE omise — jamais un nombre inventé.
3. **ACAL746 — NASA POWER en seconde source météo** (D-ACAL-81 : « Yes, use it ») : comparaison à côté de PVGIS dans
   l'étude, PVGIS reste la source du chiffre (un seul chiffre par valeur) ; appel sans clé, délai court, repli
   silencieux si le service ne répond pas ; nouvelle dépendance extérieure GRATUITE à dire au rapport.
Fichiers interdits : ceux de la lane « pertes-simulation » (`data/profil_depart.json`, `chaine_pertes.py`, la file de
simulation) et ceux listés pour elle ci-dessus. Si ACAL1672 ou ACAL746 demande `simulation.py` : demande croisée.

## Lane « devis-auto-ci » (moteur de devis commercial et industriel + garde de la fiche) — APRÈS le pli de « moteur-unique »

1. **ADEV125** (D-ACAL-92) — contrat d'électricité absent : tarif basse tension supposé, dit avec le champ
   `contrat_electricite`, devis marqué estimation.
2. **ADEV126** (D-ACAL-93) — phase absente : triphasé supposé pour tout commercial et industriel, dit avec `raccordement`.
3. **ADEV127** (D-ACAL-94) — le régime d'équipes suffit ; jours ouvrés supposés lundi-samedi, dits.
4. **ADEV124** — les deux suppositions tues du C&I sortent au journal du devis automatique.
La garde `apps/crm/devis_auto.py` et le moteur disent LA MÊME chose (une règle, lue par sélecteur, jamais copiée).
Mesure de départ en production (23/11) : 4 leads commerciaux prêts sur 42 qui ont une facture.
Avant ton rapport : les suites `apps.crm` et `apps.ventes` touchées (modules de test des fichiers édités + goldens).

## Lane « regles-communes » (une règle pour le devis et le calepinage) — APRÈS le pli de « moteur-unique »

1. **ADEV121** — le moteur C&I importe la règle de l'hybride (capacité publiée) depuis `core/electrique/` au lieu de sa
   copie : aucun chiffre de devis ne change (prouve-le sur les goldens).
2. **ADEV122 + ACAL1553** (D-ACAL-80 : le minimum de l'année type du lieu) — UNE politique de température de froid pour
   la longueur de chaîne, dans `core/electrique/`, lue par le devis (C&I et résidentiel) et par le calepinage ; sans
   épingle ni année type : −5 °C, dit. Les NOUVEAUX devis seulement.
3. **ADEV123** — le devis automatique résidentiel dit ses suppositions avec le champ de la fiche.
4. **APAR92** (D-ACAL-95) — orthographes courantes et noms en arabe des villes DÉJÀ dans la table reconnus (« casa »,
   « casablaca », « kech », Fès et Tanger en arabe…) ; le reste refusé. Liste mesurée en production :
   `docs/audits/l5-calepinage/controles/C3-mesures-prod.md`.

## Lane « ecrans-d » (écrans du calepinage) — APRÈS le pli de « moteur-unique »

1. **ACAL1755** (D-ACAL-86 et D-ACAL-96) — un seul chiffre de production : l'étude et l'atelier montrent le chiffre le
   plus réaliste (la simulation de la pose) ; quand un devis ENVOYÉ en porte un autre, l'écran et le rapport disent les
   deux et proposent « Réviser le devis » (le geste de révision existe côté devis : branche-le, ne le réécris pas).
2. **ACAL1840** (D-ACAL-88) — « Montrer au client » montre l'estimation de la pose, dite « estimation », avant un
   résultat complet.
3. Restes vus en direct sur la vague C (`docs/audits/l5-calepinage/T3/T3-VAGUEC.md`) : **ACAL1908** (11 px de défilement
   à Démarrage rapide, mesure réelle), **ACAL1985** (en Guidé à Documents, « Générer le devis » est encore l'ancien
   bouton 163 × 52), **ACAL1912** (l'avertissement des panneaux non raccordés manque à Guidé > Résultats),
   **ACAL1905** (l'étape Résultats guidée dit « Calcul en cours… » avec « Réessayer » sur un délai dépassé :
   `delaiReseau.js::messageResultatIndisponible`).

## Lane « taille-auto » (moteur de dessin) — APRÈS le pli de « pose-reprise-2 »

1. **ACAL1331 + ACAL1448** (D-ACAL-76 : « Place them automatically ») — sur un calepinage vierge, dès que le toit est
   tracé, les panneaux se posent à la taille tirée de la facture du lead (la cible servie), le commercial ajuste ;
   une pose déjà enregistrée n'est JAMAIS re-posée (ACAL1900).
