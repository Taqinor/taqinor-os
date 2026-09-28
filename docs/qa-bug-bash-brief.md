# Bug bash — brief pour testeurs humains (QAH9)

Ce document sert à briefer 1 ou 2 testeurs francophones qui n'écrivent pas de
code : des séances courtes, minutées, où ils essaient de « casser » l'ERP
comme le ferait un vrai commercial, un vrai technicien ou une vraie
comptable — puis ils décrivent ce qu'ils ont vu avec le gabarit ci-dessous.

Contexte : un agent logiciel (LLM) explore bien mais juge mal — voir
`docs/PLAN.md`, GROUPE QAH. Les tests automatiques (QAH2-QAH8) couvrent les
invariants d'argent, la cohérence des documents et l'isolation entre
sociétés. Ce bug bash humain couvre l'autre moitié : « est-ce que ça a l'air
correct et agréable à utiliser pour quelqu'un qui n'a jamais vu le code ? »

## Avant de commencer

* **Environnement** : la stack locale de démonstration uniquement
  (`docker compose up`), **jamais** le serveur de production
  (`api.taqinor.ma`). Si vous ne savez pas sur quelle machine vous êtes,
  demandez avant de commencer.
* **Connexion** : ouvrez `/login`. Deux sociétés de démonstration existent
  (utile aussi pour vérifier qu'on ne voit jamais les données de l'autre) :

  | Société | Identifiant | Rôle | Mot de passe |
  |---|---|---|---|
  | TAQINOR Démo | `demo_admin` | Administrateur | voir `authentication/management/commands/seed_demo.py` |
  | TAQINOR Démo | `demo_resp` | Responsable | voir `authentication/management/commands/seed_demo.py` |
  | TAQINOR Démo (complet) | `demo_admin_full` | Administrateur | voir `authentication/management/commands/seed_demo_company.py` |
  | TAQINOR Démo (complet) | `demo_resp_full` | Responsable | voir `authentication/management/commands/seed_demo_company.py` |

  (Les mots de passe sont dans ces deux fichiers, en clair — ce sont des
  comptes de démo locaux, jamais utilisables en production.) Si la base de
  démo est vide ou trop abîmée après une séance, quelqu'un côté technique
  peut la repeupler avec `python manage.py seed_demo` /
  `python manage.py seed_demo_company`, ou tout remettre à zéro avec
  `python manage.py reset_demo_company --slug taqinor-demo-full`.

* **Zones interdites — ne JAMAIS faire, même « pour tester » :**
  * N'envoyez un e-mail ou un message WhatsApp qu'à une adresse/un numéro
    fictif (ceux des clients de démo) — jamais à une vraie personne.
  * N'allez pas sur `/publicite/cockpit` pour créer ou lancer une VRAIE
    campagne Meta.
  * Ne lancez aucun scraper (il n'y a pas de bouton pour ça dans l'écran —
    si vous en voyez un, c'est déjà en soi une anomalie à signaler).
  * Ne supprimez rien de façon irréversible en dehors des données de démo.
  * Si un écran vous demande une vraie carte bancaire ou un vrai compte —
    stop, c'est un constat, pas une action à faire.

## Méthode : sessions exploratoires minutées (SBTM), 90 minutes

Une session = une **charte** (une zone de l'appli + un risque à chercher) +
un **minuteur de 90 minutes** + un **debrief**. Vous explorez librement dans
le périmètre de la charte, vous notez tout ce qui vous semble faux, moche,
lent ou incohérent — sans attendre la fin pour écrire, notez au fil de
l'eau. En fin de session, relisez vos constats 10 minutes et complétez ce
qui manque (capture d'écran, étapes de repro) pendant que c'est frais.

Une session par rôle est un bon point de départ ; si le temps le permet,
refaites-en une deuxième sur la même charte avec l'autre société de démo
(pour croiser les données et repérer une éventuelle fuite entre sociétés).

## Chartes par rôle

### Charte 1 — Commercial : lead → devis → relance → signature

Parcours à explorer (utilisez les écrans réels, dans cet ordre logique) :
1. Créez un lead dans `/crm/leads`, ouvrez sa fiche (`/crm/leads/:id`) et
   remplissez-la comme si vous veniez de raccrocher avec un prospect.
2. Transformez-le en devis via `/ventes/devis/nouveau` (essayez les 3 modes
   si le temps le permet : Résidentiel, Industriel/Commercial, Agricole).
   Testez des cas bizarres : quantités à virgule, remise à 0 %, remise à
   100 %, un devis à deux options.
3. Ouvrez le devis dans la liste `/ventes/devis`, générez son PDF et
   vérifiez la chaîne affichée : Sous-total HT → Remise → Total HT → TVA →
   Total TTC — est-ce que ça retombe juste, à vue d'œil, sur une
   calculatrice ?
4. Suivez la relance (`/ventes/relances` ou `/crm/relances`) puis simulez
   l'acceptation côté client (l'espace client est à `/portail/client/devis`
   — le lien réel serait envoyé par e-mail/partagé, jamais à une vraie
   adresse ici).
5. Vérifiez que le devis passe bien au bon statut une fois « signé » et
   que rien ne se contredit entre la liste des devis et sa fiche.

**Consigne spéciale : essayez de casser les totaux et la génération PDF**
(remises extrêmes, lignes vides, deux options, gros volumes de lignes).

### Charte 2 — Technicien : visite → calepinage → chantier → SAV (sur mobile)

Ouvrez ces écrans depuis le navigateur de votre téléphone (site responsive,
rien à installer) :
1. `/visites` (« Ma journée ») puis une visite existante `/visites/:id` —
   remplissez le relevé de toiture, testez `/visites/:id/calage`.
2. `/calepinage` puis `/calepinage/nouveau` (ou ouvrez un calepinage
   existant `/calepinage/:id`) — posez des panneaux, changez l'inclinaison,
   regardez si l'estimation de production a l'air cohérente.
3. `/chantiers` puis `/interventions`/`/planification` — suivez un chantier
   comme si vous étiez sur site (photos, checklist, statut).
4. `/sav` — ouvrez un ticket, changez son statut, essayez de le rattacher
   à un contrat de maintenance (`/sav/contrats`).

Sur mobile, portez une attention particulière à : boutons trop petits/trop
proches, champs qui obligent à zoomer, clavier qui cache le bouton
« valider », photo qui ne s'uploade pas avec une connexion lente.

### Charte 3 — Comptable : BC → facture → paiement/avoir, TVA

1. `/ventes/bons-commande` — ouvrez un bon de commande, vérifiez sa
   cohérence avec le devis d'origine.
2. `/ventes/factures` — générez/ouvrez une facture depuis ce BC, vérifiez à
   nouveau la chaîne HT → remise → TVA → TTC, et le cas d'une TVA mixte
   (10 %/20 %) si vous trouvez un devis qui en a.
3. `/ventes/paiements` — enregistrez un paiement partiel puis un paiement
   qui solde la facture ; vérifiez que le statut et le reste-à-payer
   suivent.
4. `/ventes/avoirs` — créez un avoir sur une facture remisée et vérifiez
   qu'il crédite bien le montant NET (remisé), jamais le brut — c'est un
   piège d'argent réel déjà rencontré une fois sur ce module (AUD106).

**Consigne spéciale : essayez de casser les totaux et la génération PDF**
(facture à cheval sur deux taux de TVA, avoir partiel, gros montants,
montants à zéro).

## Gabarit de constat

Pour chaque anomalie trouvée, une entrée avec ces champs (copier/coller ce
gabarit autant de fois que nécessaire) :

```
### [Sévérité: bloquant / majeur / mineur / cosmétique] Titre court du problème

Écran : /chemin/de/l-ecran
Rôle/charte : Commercial | Technicien | Comptable
Société de démo utilisée : TAQINOR Démo | TAQINOR Démo (complet)

Repro (étapes exactes, dans l'ordre) :
1. ...
2. ...
3. ...

Attendu : ce qui aurait dû se passer
Vu : ce qui s'est vraiment passé

Capture d'écran : (nom de fichier / lien)
```

**Sévérité — repère rapide :** bloquant = empêche de finir le parcours
(erreur, page blanche, total faux dans un document remis au client) ;
majeur = ça marche mais donne un résultat trompeur ou perd du temps ;
mineur = gênant mais contournable ; cosmétique = esthétique/texte.

## Où déposer vos constats

Les testeurs n'écrivent pas eux-mêmes dans le dépôt de code : envoyez vos
constats (le gabarit rempli + les captures) à Reda. C'est lui qui les
transforme en tâches `ERR-...` dans `docs/ERROR_PLAN.md`, qui est ensuite
drainé par la commande « work on error plan » — vous n'avez rien d'autre à
faire une fois vos constats envoyés.
