# Phase de contrôles (après le L5) — missions C1 et C2

Demande du fondateur (22/11/2026, citée mot pour mot) : « you check the mockups and the functionality and you make
sure that all my quotes can get calculated automatically, with the right assumtions » ; « my ERP should be able to
solve and have default for everything should only need the bill and one consumption profil picked as what is hapening
in my CRM » ; « there should be one engine that should be the CRM one » ; et le cas : « the lead cpge go plus that have
problems in his calculation while my sizing engine calculated the quote and i already sent it to client ».

Ces deux missions sont des ENQUÊTES en lecture seule sur le code (aucune écriture hors le rapport, aucun `git add`,
aucun commit, aucune commande `docker`, RIEN vers la production, aucune donnée de client envoyée à un service
extérieur ni tapée dans une recherche web). Dossier : `C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde`.
Lis d'abord `CLAUDE.md` (règle n° 4 : `/proposal` est la seule voie du PDF client ; le moteur ne fait que RENDRE), puis
`docs/CODEMAP.md` §3-§4 pour situer les apps `crm`, `ventes`, `calepinage`, `core/electrique`, et les mémoires
`docs/claude-memory/ci-decisions-fondateur.md`, `dimensionnement-decisions-2310.md`, `calculateur-suppositions-dites.md`,
`calepinage-decisions-fondateur.md` (D-ACAL-36 à 46 : production de la pose réelle au PDF des nouveaux devis),
`residentiel-decisions-2710.md`.

## C1 — « Un seul moteur, celui du CRM » et le lead 1742

Question : combien de moteurs calculent aujourd'hui la taille, la production et l'électrique d'une installation, où
divergent-ils, et que faut-il pour que le calepinage se serve du moteur du CRM (celui qui a calculé le devis envoyé) au
lieu de recalculer autrement ?

1. Dresse la CARTE des moteurs, `fichier::symbole` à l'appui : dimensionnement automatique du CRM / des devis (serveur :
   `apps/ventes/` — moteur résidentiel, moteur C&I, moteur agricole ; écran : `frontend/src/features/ventes/solar.js`),
   vérifications électriques (`core/electrique/`, `apps/ventes/solar_design.py`, `apps/calepinage/services/electrique.py`),
   production (étude horaire du devis ; simulation du calepinage `services/simulation.py` ; estimation de l'atelier dans
   `apps/web/src/scripts/roofPro11/`), consommation (profils types, facture, barèmes). Pour chaque grandeur (nombre de
   panneaux, kWc, onduleur retenu, longueur de chaîne, ratio DC/AC, tension à froid, production annuelle,
   autoconsommation) : QUI la calcule, avec quelles entrées et quelles valeurs par défaut, et où deux moteurs peuvent
   donner deux réponses pour le même lead.
2. Le cas du lead 1742 « CPE Go Plus » — faits déjà relevés en production (lecture seule, le 22/11) :
   `C:/Users/kasri/AppData/Local/Temp/claude/0f9063243c725bde/b36b49db-06cb-474e-a24f-5b0f5d71f674/scratchpad/cas-cpe-go-plus.md`
   et `…/scratchpad/probe1.out`. Résumé : le calepinage 9 est rattaché au devis BROUILLON 554 au lieu du devis ENVOYÉ
   564 ; il porte 48 panneaux (l'option « avec batterie ») quand l'option recommandée en a 35 ; borne DC/AC de 1,35
   contre la règle de la fiche technique (D-HYB-1) ; longueur de chaîne 12 contre 16 ; production « non simulée ».
   Pour CHAQUE écart : la cause dans le code (`fichier::symbole`, statut « lue » ou « probable »), si les corrections de
   la campagne L5 d'aujourd'hui le changent (`git log --oneline bfb859c90..HEAD -- <fichier>`), et ce qu'il faut pour
   que le calepinage d'un devis déjà envoyé reprenne EXACTEMENT ce que le moteur du devis a retenu (panneaux, onduleur,
   chaînes) sans rien recalculer d'autre. Ces faits sont des données internes : ne les recopie pas hors du rapport.
3. Propose le chemin vers UN moteur : ce que le calepinage doit LIRE du devis (par `apps/ventes/selectors.py`, jamais
   ses modèles), ce qu'il doit cesser de recalculer, ce qui reste propre au calepinage (géométrie, ombrage, câblage du
   chantier). Écris les tâches (titre, constat, fichiers, « fini quand », propriétaire d'après
   `python scripts/check_ownership.py --owner-of <fichier>`), sans les inscrire au plan : l'orchestrateur le fera.
4. Dis les requêtes de LECTURE en production qui manquent pour chiffrer le problème (ex. : combien de calepinages
   rattachés à un devis qui n'est pas le dernier envoyé ; combien dont le nombre de panneaux diffère de celui du devis),
   sous la forme d'un script `manage.py shell` en lecture seule, ASCII, sans nom de client en sortie (des identifiants
   et des comptes seulement) : l'orchestrateur le jouera.

Sortie : `docs/audits/l5-calepinage/controles/C1-moteur-unique.md` (150 lignes au plus) : carte des moteurs (table) ;
lead 1742 (un écart par ligne : cause, corrigé aujourd'hui ou non, correctif) ; chemin vers un moteur ; tâches ;
requêtes de lecture à jouer ; ce que tu n'as pas couvert.

## C2 — « Tous mes devis se calculent seuls, avec les bonnes hypothèses »

Question : à partir d'un lead qui n'a QUE sa facture et un profil de consommation choisi, le devis automatique
aboutit-il, pour chaque marché (résidentiel, commercial, industriel, agricole) ? Sinon, à quelle entrée s'arrête-t-il,
et quelle hypothèse par défaut manque ou n'est pas dite ?

1. Suis le chemin du devis automatique depuis la fiche du lead jusqu'au PDF `/proposal` (services du CRM et des ventes,
   écran `/ventes/devis/nouveau`, moteurs serveur C&I et agricole) et dresse la TABLE DES ENTRÉES : pour chaque entrée
   que le calcul lit — son champ sur le lead ou le devis, sa valeur par défaut dans le code (`fichier::symbole`), d'où
   vient ce défaut (décision du fondateur citée, valeur publiée, valeur inventée ou absente), et si l'écran ou le PDF
   DIT qu'elle est supposée (règle du 17/11 : tout ce qui est supposé est dit avec le champ de la fiche).
2. Liste les ARRÊTS : chaque condition qui refuse, bloque ou rend un devis vide (409, « à renseigner », devis
   préliminaire, visite avant devis…), avec le message montré, si c'est voulu par une décision du fondateur (cite-la)
   ou si c'est un défaut manquant.
3. Le calepinage dans ce chemin : depuis la campagne d'aujourd'hui, que reçoit-il du lead (facture, profil), que
   suppose-t-il, où reste-t-il « incomplet » faute de valeur par défaut (décision D-ACAL-82 : quatre pertes sans
   valeur) ? Donne la liste EXACTE des valeurs par défaut qu'il faudrait pour qu'un résultat soit complet au premier
   jour, chacune avec une valeur de référence PUBLIÉE et sa source quand tu en trouves une dans le dépôt
   (`apps/calepinage/data/profil_depart.json`, `docs/audits/l5-calepinage/T2/R2-fonctions.md`), sinon « à donner par le
   fondateur ».
4. Propose les tâches (comme en C1, sans les inscrire) et, pour chaque valeur par défaut qui change un chiffre vu par
   un client, la question à poser au fondateur avec tes options.

Sortie : `docs/audits/l5-calepinage/controles/C2-devis-automatiques.md` (150 lignes au plus) : table des entrées par
marché ; arrêts ; le calepinage ; valeurs par défaut manquantes ; tâches ; questions au fondateur ; non couvert.

## Règles communes

Vocabulaire : cause « lue » (ligne ouverte par toi), « probable », « à reproduire ». Jamais une ancre `fichier:ligne`.
Calibrage : justesse et spécification seulement. Tu peux lancer des lectures (`grep`, `git log`, tests Python purs sur
l'hôte) ; aucun conteneur. Message final : 15 lignes au plus.
