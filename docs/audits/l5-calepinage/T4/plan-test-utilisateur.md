# Partie 2 — plan du test utilisateur complet (demande du fondateur du 24/11/2026)

Statut : plan écrit le 24/11 pendant la construction de la partie 1 ; il se joue APRÈS la fusion de la partie 1.
Lieu : la pile privée `l5t` (fiche dans `../etat.md`), société « TAQINOR Anonymisé (QA) » (`taqinor-anon`), copie
anonymisée de la production du 24/11/2026. Jamais la production. Jamais le vrai `.env`.

## 1. Avant de tester : tout préremplir (rien d'« incomplet », aucun « prix à renseigner », aucun réglage vide)

Le registre de ce qui est rempli, avec la source de chaque valeur, vit dans `preremplissage.md` (même dossier).
Ordre :
1. Miroir de la production (fait le 24/11) : 93 fiches techniques, réglages du calepinage, forfaits C&I, délais.
2. Calepinage → Réglages → Démarrage rapide → « Remplir les réglages vides » (par l'écran, comme un utilisateur),
   puis mode météo et années, profils de consommation, réglages agricoles.
3. Fiches techniques complétées d'après les fiches publiques des fabricants (source écrite par valeur).
4. Prix des articles qu'un scénario utilise et qui n'en ont pas.
5. Clé de carte.
6. Comptes aux vrais rôles : Commercial, Commercial responsable, Technicien, Administrateur.
Ce qui ne peut pas être sourcé est DIT, jamais inventé ; le scénario qui en dépend est marqué « non couvert pour
cette raison ».

## 2. Qui teste, sur quoi

- Des relecteurs NEUFS (aucun n'a rien construit), par des clics dans un vrai navigateur. Deux navigateurs au plus à
  la fois sur ce poste.
- Moteurs : Chromium et WebKit. Tailles : bureau 1440 × 900, tablette 1180 × 820, téléphone 390 × 844 (tactile).
  Thèmes : clair et sombre.
- Rôles : Commercial, Commercial responsable, Technicien, Administrateur — chaque scénario est joué par le rôle qui
  le fait dans la vraie vie, et au moins une fois par un autre rôle (droits : ce qu'il ne doit PAS voir ou faire).

## 3. Les scénarios — chacun est un lead créé comme un utilisateur le crée, suivi jusqu'au bout

Chaîne complète : lead → devis automatique → devis retouché à la main → PDF `/proposal` dans chaque format → envoyé →
calepinage (toit, panneaux, électrique, résultats, documents) → rapport d'étude → devis révisé V2 → accepté →
chantier → facture → SAV.

| Code | Marché | Ce que l'utilisateur saisit | Ce qui doit se passer (à vérifier, pas à supposer) |
|---|---|---|---|
| a | Résidentiel | une facture en dirhams, ville tapée « casa », pas de GPS | ville reconnue ; devis automatique ; chaque supposition dite avec le champ à remplir |
| b | Résidentiel | kWh, été différent de l'hiver, GPS, toit à deux pans, une cheminée, l'ombre d'un voisin | deux pans tracés, obstacle, ombre proche mesurée sur les panneaux posés ; production de la pose |
| c | Résidentiel | batterie souhaitée | les deux options montrées côte à côte, chacune avec ses chiffres |
| d | Résidentiel | toit plat, châssis est-ouest | pose sur châssis, lestage ou sa mention, production par orientation |
| e | Commercial | un commerce : une facture, une ville, une catégorie | tout le reste supposé ET dit (basse tension, triphasé, jours ouvrés) ; devis marqué estimation |
| f | Commercial | tout déclaré (contrat, phase, horaires, courbe horaire), toit plat lesté, sans puis avec batterie | autoconsommation heure par heure sur la courbe déclarée ; deux options |
| g | Industriel | deux équipes, pas d'heure de début, pas de tension | début supposé 6 h, basse tension « force motrice » supposée, réserve de visite imprimée |
| h | Industriel | moyenne tension déclarée | comportement décidé pour la MT (visite avant devis) : dit clairement, jamais un chiffre inventé |
| i | Agricole | pompe neuve sur forage, HMT et débit donnés | pompe choisie sur sa courbe, variateur assorti, m³/jour, document 3 pages |
| j | Agricole | pompe existante gardée | champ dimensionné pour la pompe déclarée ; pas de m³/jour calculé sans courbe |
| k | Agricole | phase inconnue | le devis RESTE bloqué et dit pourquoi, avec le champ à remplir |
| l | Limite | kWh tapés qui contredisent les factures | l'enregistrement du devis est bloqué jusqu'à correction de la fiche |
| m | Limite | ville « maroc » | refusée ; la fiche dit « Manque : ville » |
| n | Limite | devis envoyé, puis la conception change au calepinage | les deux chiffres nommés, « Réviser le devis » ; le devis envoyé n'est jamais modifié |
| o | Limite | un calepinage sans lead | il se dessine, se simule et produit ses documents sans lead |
| p | Limite | champ au sol et ombrière | les deux types de pan se posent, se comptent une seule fois, se chiffrent |
| q | Limite | relevé au téléphone hors ligne, puis synchronisé | rien n'est perdu ; l'état « hors ligne » est dit ; la synchronisation est visible |
| r | Limite | deux utilisateurs enregistrent le même calepinage | conflit dit, aucune pose écrasée en silence |

## 4. Ce que chaque relecteur vérifie à chaque écran (oracles)

1. Chaque valeur montre UN chiffre, le même sur chaque écran et dans chaque PDF (taille, kWc, production, économies,
   retour, autoconsommation, couverture, m³/jour) — relevé dans une table « valeur × endroit ».
2. Toute supposition est dite, avec le champ de la fiche à remplir.
3. Rien de ce qu'un client lit n'est inventé (chaque chiffre client se retrouve dans une réponse du serveur).
4. Aucun prix d'achat nulle part (écrans, PDF, réponses lues par un écran client).
5. Aucune réponse 4xx ou 5xx, aucune erreur de console, aucune page blanche.
6. Le parcours ne mène jamais à une impasse : chaque refus dit quoi faire.
Plus les oracles 1-10 de `qa-explorer` (cités, non recopiés).

## 5. Couverture — table « écran × scénario × taille »

Tenue dans `couverture.md` (même dossier) : une ligne par écran, bouton, option et réglage du module calepinage, du
générateur de devis, de l'onglet devis de la fiche du lead et de la fenêtre des PDF ; une colonne par scénario ; la
case dit le moteur, la taille, le thème et le rôle qui l'ont joué. L'inventaire des lignes est tiré du code (routes,
composants, options), pas de mémoire. Une ligne sans case remplie à la fin est listée « NON COUVERT », avec sa raison.

## 6. Défauts

Chaque défaut : reproduit (gestes + capture regardée), corrigé (test rouge d'abord), rejoué par un relecteur NEUF.
Boucle jusqu'à DEUX tours de suite sans rien de nouveau. Registre : `../registre/` (un fichier par auteur).

## 7. À la fin

Un rapport en anglais simple — ce qui marche, ce qui a été corrigé, ce qui reste, ce que le fondateur doit décider —
et les enregistrements d'acceptation sous `docs/audits/acceptation/`.
