# Vague C — lanes de reprise d'après le tour 3 (23/11/2026)

Les vérificateurs du tour 3 ont rejoué sur l'écran réel les corrections livrées aujourd'hui. Ce fichier donne à trois
lanes les défauts GRAVES qu'ils ont vus (donnée perdue, chiffre faux, geste qui ne fait rien, écran qui gêne l'usage).
Règles de travail : `docs/audits/l5-calepinage/T2/brief-lanes.md` (à lire en entier ; §0 à §6 s'appliquent, bloc
d'ancrage compris). Les gestes exacts, les captures et les valeurs de chaque défaut sont dans les fichiers du tour 3 :
`docs/audits/l5-calepinage/registre/constats/T3-*.jsonl` (constats `T3-…-00n`),
`docs/audits/l5-calepinage/registre/evenements/T3-*-cv.jsonl` (verdicts, champ `reste`) et les rapports
`docs/audits/l5-calepinage/T3/*.md`. LIS la ligne de chaque défaut de ta lane avant d'y toucher : ses gestes sont ton
test rouge. Ces défauts ne sont pas encore des lignes du plan : `python scripts/audit_tache.py` ne les connaît pas —
fais toi-même, par grep, appelants, assertions existantes et jumeaux, et colle-les dans le message du commit.
Identifiant de commit : celui donné ci-dessous (`ACAL19nn — …`).

Communs aux trois lanes :
- Une quatrième lane (« moteur-unique ») travaille EN MÊME TEMPS sur : `apps/ventes/selectors_calepinage.py`,
  `apps/calepinage/services/electrique.py`, `equipements.py`, `liens.py`, `creation.py`, `pret_a_envoyer.py`,
  `apps/calepinage/receivers.py`, la vue et le contrat de `GET resultat/`, `core/electrique/onduleurs.py`,
  `apps/crm/devis_auto.py`, et côté front `atelier/coque/etapes/` : `EtapeResultats.jsx`, `EtapeElectrique.jsx`,
  `panneaux/sources.js`, `production/ResultatIncomplet.jsx`, la cible (`roofPro11/cible.ts`, `prefill.ts`). N'ÉDITE
  AUCUN de ces fichiers : si ton défaut y mène, écris une demande croisée (brief §3) et passe au suivant.
- Aucun chiffre vu par un client ne change sans que le défaut le nomme. Aucun `git push`. Rien vers la production.
- La pile de conteneurs est chargée : un seul appel `tester.sh` à la fois, et seulement les modules de test que tu
  touches (jamais la suite entière). Les tests du front et du moteur de dessin se jouent sur l'hôte (jonctions du brief).
- Une tâche impossible proprement en moins d'une heure : sortie « impossible » avec la raison et le plus petit
  changement qui débloquerait ; ne bloque pas la lane.
- Fichier d'événements : `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/l5b/T2-lane-<nom de ta lane>.jsonl` (`"tour":3`).

## Lane « pose-reprise » (moteur de dessin `apps/web/src/scripts/roofPro11/` + pose de l'atelier)

Dans l'ordre :
1. **ACAL1900 — Une pose enregistrée se rouvre à l'identique** (constat T3-POSE-004, S1, classe K-HYDRATATION ;
   décision D-ACAL-75 prise par l'orchestrateur : on REJOUE la pose enregistrée, on ne re-pose pas). Aujourd'hui : cible
   5, « Remplir automatiquement » ⇒ 16 panneaux enregistrés (le serveur a 16) ; au rechargement la carte n'en montre
   que 5 et « Enregistrer » sans geste écrase le serveur à 5. Fini quand : la pose rouverte = la pose enregistrée
   (nombre, emplacements), quelle que soit la cible ; un enregistrement sans geste ne change ni le nombre ni
   l'empreinte ; l'écart à la cible est DIT, jamais appliqué. Test : ouverture d'un document à 16 pour une cible 5.
   Jumeaux : pose de 60 (déjà bonne, ne la casse pas), pose « Le plus de panneaux », document à plusieurs pans.
2. **ACAL1901 — Le bouton Annuler défait comme Ctrl+Z** (T3-POSE-001, S2 ; reste d'ACAL1403). Coin de toit glissé
   (70 → 91 m²), clic sur Annuler : les boutons basculent mais le toit reste déformé ; Ctrl+Z défait. Fini quand : clic
   Annuler ⇒ 70 m² ; Rétablir ⇒ 91 m² ; même chose après un obstacle posé.
3. **ACAL1902 — Un retrait saisi retire des panneaux** (T3-POSE-007, S2 ; ACAL1504 et DC-7 non faits). Retraits à
   0,8 m sur un pan de 3 × 1,5 m puis 2 m sur 10 × 7 : la note dit « Retraits appliqués » mais ni la pose ni le balayage
   « Comparer les poses » ne changent. Fini quand : 3 × 1,5 à 0,8 m ⇒ 0 panneau ; 10 × 7 à 2 m ⇒ moins de panneaux, dans
   la pose ET dans le balayage (mêmes comptes).
4. **ACAL1903 — « Au plus N panneaux » dit le vrai maximum du toit** (T3-POSE-002, S2 ; ACAL1618 non fait). « Au plus
   17 827 kWh/an avec 16 panneaux » alors que « + » en pose 20. Fini quand : le maximum annoncé est celui que « + »
   atteint (portrait ou paysage, le meilleur), et la production annoncée est celle de ce maximum.
Ne grossis aucun fichier de 2 000 lignes ou plus (`optimizer.ts`, `roof-tool-pro11.ts`, `layoutEditor.ts`) : extrais.
Après toute retouche : les tests du dossier `roofPro11` touché et `npx vitest run tests/estimatorPreviewPro11.test.ts`.

## Lane « ecrans-s2 » (coque de l'atelier : React + CSS du calepinage, client d'API)

Dans l'ordre :
1. **ACAL1904 — La carte d'adresse ne cache plus le zoom et n'avale plus les clics de tracé** (T3-ECRANS-001, S2).
   Calepinage sans toit, 1440 × 900 : la carte d'adresse (890 × 232) recouvre la pile de zoom et la boussole, et les
   clics de tracé tombent dessus. Fini quand : zoom et boussole restent cliquables, un clic de tracé hors des champs
   arrive à la carte, et la carte d'adresse tient la hauteur d'un champ une fois l'adresse posée (maquette `Main`).
2. **ACAL1905 — Une réponse lente n'est pas une connexion coupée** (T3-PROD-005 et T3-PROD-006, S2). (a) Résultats :
   « La connexion a expiré » alors que `GET resultat/` répond 200 en 5 à 17 s ⇒ l'écran attend (délai adapté à cette
   route) et dit « Calcul en cours… » avec « Réessayer » si le délai est dépassé. (b) Enregistrer : toast « Le serveur
   n'a pas répondu » alors que l'enregistrement est fait ⇒ après un délai dépassé, l'écran RELIT l'état du serveur
   (empreinte) et dit « Enregistré » si elle a changé, au lieu de pousser à ré-enregistrer. Test de rendu pour chacun.
3. **ACAL1906 — Le curseur « Heure du soleil » se touche au doigt** (ACAL1818 non fait) : zone tactile ≥ 44 px
   (atelier et vue client `.cal-client-soleil`), sans grossir le trait visible.
4. **ACAL1907 — Rien de la carte ne dépasse ni ne se cache** (T3-ECRANS-003, -004, -008, -002, S3, même famille) :
   la pile de zoom suit le décalage du bandeau d'alerte (GPS / C&I) ; en Expert > Résultats le panneau plein couvre
   toute la carte (plus de « Recherche limitée au pays », de coin doré ni de barre d'outils autour) ; « Localiser » a la
   hauteur d'un champ (44 px) et n'est plus un aplat doré étiré ; la barre sombre de 425 × 12 px au-dessus du bandeau
   disparaît. Un test de rendu par point quand c'est mesurable sans navigateur, sinon dis-le.
5. **ACAL1908 — Plus de défilement résiduel** (ACAL1344 : 11 px de trop à l'étape nommée dans le verdict).
CSS : jetons seulement (`--cal-*`), aucun `z-index` en dur, `:hover` sous `@media (hover: hover)`.

## Lane « production-s2 » (serveur du calepinage hors fichiers de « moteur-unique », panneau de consommation)

Dans l'ordre :
1. **ACAL1909 — Les mois de facture enregistrés se relisent** (ACAL1610 non fait ; donnée écrasée). Au rechargement,
   « Mes factures » ne relit pas les mois enregistrés ; un mois ajouté ensuite part seul et écrase les autres. Fini
   quand : trois mois enregistrés se relisent au rechargement, un quatrième ajouté donne quatre mois au serveur.
2. **ACAL1910 — Le module nommé est celui qui est POSÉ** (T3-PROD-013, S2). 13 modules Canadian posés, module par
   défaut de l'entrée Jinko : les étapes « niveau d'éclairement » et « qualité module » et la planche unifilaire du
   rapport d'étude nomment Jinko. Fini quand : ils nomment le module posé du pan (même source que l'étape thermique
   depuis ACAL1607). Si la planche passe par `services/electrique.py` : demande croisée, et corrige les deux étapes.
3. **ACAL1911 — Des fenêtres qui ne s'appliquent pas n'effacent pas la batterie** (T3-PROD-003, S2). Fenêtres de
   charge / décharge saisies + stratégie « autoconso » ou « backup » ⇒ tout le bloc batterie est omis (« Une donnée
   manque »). Fini quand : les fenêtres sont ignorées avec un avertissement nommé, la batterie reste simulée.
4. **ACAL1912 — Les panneaux raccordés à rien sont dits** (reste d'ACAL1602). 13 posés dont 4 raccordés à aucun
   onduleur : l'avertissement « 4 panneaux ne sont raccordés à aucun onduleur : ils ne sont pas comptés » manque dans
   `resultat.avertissements`, à l'écran et au rapport. Fini quand : il est servi en tête (la vue de `GET resultat/`
   est à l'autre lane : sers-le par le bloc `avertissements` existant, sans nouvelle clé) et rendu au rapport.
5. **ACAL1913 — La consommation du jour n'est plus « 0,0 kWh »** (T3-PROD-004, S3) : le panneau « Affiner ma
   consommation » montre la consommation tirée de la facture plus la charge ajoutée.
