# Scénario unique des maquettes (fait foi pour TOUS les écrans)

Toutes les maquettes racontent LA MÊME journée. Un chiffre, une heure, un titre affiché doit se retrouver ici ; ce qui
n'est pas ici n'existe pas. Les comptes de la barre latérale et des onglets ne s'écrivent plus à la main : `coque.js`
les tire de §7 selon `<body data-heure>`.

## 0. Errata du 18/11/2026 (acceptation en direct de la fusion 2)

Le semis `seed_taches_demo` rejoue maintenant cette journée par les VRAIS services (une table heure → geste) et un test
compare ses chiffres à ce document (`apps/taches/tests/test_seed_demo.py::ScenarioTests`). Six phrases d'origine ne
peuvent pas être produites par les règles de la référence ; elles se lisent ainsi (le reste du document est inchangé) :

1. §1, « À revoir » : les deux tâches sans projet sont « prévues mar. 17 puis reportées 3 fois (jeu. 19, ven. 20,
   lun. 23) » — une tâche seulement « prévue lun. 23 » serait proposée, pas « À revoir » (`regles.md` §4.2).
2. §1, « À trier (5…) » : en fusion 2, À trier porte 4 lignes et le bandeau « 1 à-faire personnel » (la facture
   d'acompte, que le parcours convertit) ; 5 lignes dès 10:30 avec la tâche liée au rappel. La ligne « Suggéré par
   l'ERP » n'existe qu'à partir de la fusion 4.
3. §2, Site web : « 0 sur 4, toutes sans jour » — l'état « À planifier » exige zéro tâche ouverte (`regles.md`,
   santé d'un projet).
4. §3 : à 10:30, « Lier une tâche » sur « Rappeler pour le devis » (sans ce lien, sa clôture de 10:40 compterait et
   15:00 dirait « 4 sur 5 »). Le bilan dit bien « 4 des 5 gardées » : l'activité liée n'est pas une gardée de plus
   (`regles.md` §4.9).
5. §3 et §4, « Visite technique à Témara » : une visite venue de l'ERP se nomme « Visite — {nom du lead} ».
6. §6, retour du 7 décembre : seule la phrase de la carte (« Tu reviens après 10 jours… ») est reproduite ; les
   nombres de ce jour-là (18 tâches, 3 à trier, 12 relances) ne sont pas semés.
7. §3 et §4, la visite et les relances de l'ERP : ce document ne dit ni quand elles ont été posées, ni sur quels
   leads. Le semis fixe : visite « Visite — Témara » planifiée le ven. 20 à 10:00, sur un lead SANS responsable
   (avec le compte pour responsable, l'ERP poserait en plus « Confirmer la visite » la veille, le débrief et une
   activité « Relance commerciale » dans « À revoir ») ; 5 leads « Relance de démonstration 1 à 5 », leurs appels
   posés le lun. 23 à 18:00 et dus le mar. 24 à 11:00, dont 3 faits à 11:30 (« Suivi des relances : 5 » le matin,
   2 à 15:00). La bande « Toute la journée » de l'agenda ne porte que la visite : la ligne des relances est une
   ligne de Prévu.

## 1. Le cadre
- **Aujourd'hui = mardi 24 novembre 2026.** Semaine du lundi 23 au dimanche 29 (sam. 28 et dim. 29 non travaillés).
  Le mercredi 18 novembre est férié. Premier jour de l'app : lundi 2 novembre.
- **Objectif du jour : 5** (source « accepté »). Mode « En faire plus ». Temps disponible : 4 h.
- Projets (couleur `data-p` · priorité · échéance) : Chantier Benali 9 kWc (ambre · Haute · ven. 4 déc., jalon « Mise
  en service » jeu. 3 déc.) · Salon Solaire Expo (indigo · Haute · ven. 27 nov.) · Recrutement technicien (vert ·
  Moyenne · ven. 15 janv.) · Administratif (prune · Basse · sans échéance) · Site web (ciel · Moyenne · sans échéance,
  « À planifier »).
- Activités de l'ERP du 24 : « Visite technique à Témara » (Toute la journée, jamais d'heure) ; « Rappeler pour le
  devis » 10:30, Lead Ouazzani (activité ERP, close à 10:40). « Suivi des relances » : **5** le matin, **2** dès 11:30
  (3 relances faites), 2 au bilan.
- À trier (5, le matin comme le soir) : « Préparer le chantier du devis accepté » (Suggéré par l'ERP) · « Envoyer la
  facture d'acompte » (à-faire d'Activités, échéance ven. 27) · « Acheter des cartouches pour l'imprimante » (dicté) ·
  « Demander le devis d'assurance décennale » (noté lun. 23) · « Filmer le chantier pour Instagram » (collé dim. 22).
- À revoir (2, toute la journée) : « Mettre à jour le planning des poses » et « Rappeler le bureau de contrôle » (sans
  projet, prévues lun. 23, 30 min chacune). En attente (1) : « Poser la structure · attend : Réceptionner les 16
  panneaux ». En réserve : 7 tâches (dont « Comparer deux devis d'impression », Salon).

## 2. Toutes les tâches des projets (état : matin 8 h 30 → 15 h → bilan)
« ✓ date » = faite ce jour-là. « ○ » = ouverte. Durée entre parenthèses. ★ = essentielle du 24.

**Chantier Benali 9 kWc — 18 tâches** · 12 sur 18 le matin (6 ouvertes) · 14 sur 18 à 15 h et au bilan (4 ouvertes) ·
10 sur 18 le ven. 20 au soir.
| Étape | Tâche | État | Jour · heure (durée) |
|---|---|---|---|
| Études | Visiter le site | ✓ lun. 9 | |
| Études | Relever les factures du client | ✓ mar. 10 | |
| Études | Valider le dimensionnement | ✓ jeu. 12 | |
| Études | Préparer le devis | ✓ ven. 13 | |
| Études | Faire signer le devis | ✓ lun. 16 | |
| Études | Encaisser l'acompte | ✓ mar. 17 | |
| Études | Valider l'étude de toiture | ✓ jeu. 19 | |
| Études | Envoyer le devis révisé ★ (priorité haute, échéance mer. 25) | ○ matin → ✓ 10:50 | mar. 24 · 09:00 (2 h), placée le ven. 20 |
| Démarches | Déposer la demande de raccordement | ✓ lun. 16 | |
| Démarches | Prévenir le syndic | ✓ jeu. 19 | |
| Démarches | Obtenir l'accord du bureau de contrôle | ✓ ven. 20 | |
| Matériel | Commander les onduleurs | ✓ lun. 23 | (09:00, 1 h) |
| Matériel | Commander les 16 panneaux | ✓ lun. 23 | (11:00, 30 min) |
| Matériel | Commander les rails de fixation | ○ matin (proposée) → ✓ 08:52 | mar. 24 · 08:30 (30 min) |
| Matériel | Valider le plan de calepinage (échéance jeu. 26) | ○ | mer. 25 · 09:00 (1 h) |
| Matériel | Réceptionner les 16 panneaux | ○ | jeu. 26 · 09:00 (1 h) |
| Pose | Poser la structure — attend : Réceptionner les 16 panneaux | ○ | sans jour (1 j) |
| Pose | Mise en service — jalon | ○ | jeu. 3 déc. |
Étapes : Études 7 sur 8 le matin · Démarches 3 sur 3 · Matériel 2 sur 5 le matin, 3 sur 5 dès 08:52 · Pose 0 sur 2.
Santé (« à surveiller ») : 12 faites en 19 jours travaillés (27 oct.–23 nov., férié ôté) ; 6 ouvertes → il faudrait
10 jours travaillés ; il en reste 8 (25, 26, 27 nov., 30 nov., 1, 2, 3, 4 déc.). Écran : « À ce rythme : 10 jours
travaillés, il en reste 8 ».

**Salon Solaire Expo — 11 tâches** · 3 sur 11 le matin (8 ouvertes) · 4 sur 11 dès 10:20 (7) · 5 sur 11 dès 16:30 (6) ·
2 sur 11 le ven. 20 au soir. Santé : « à surveiller » (8 ouvertes, 3 jours travaillés avant l'échéance).
| Étape | Tâche | État | Jour · heure (durée) |
|---|---|---|---|
| Stand | Réserver le stand | ✓ mar. 3 nov. | |
| Stand | Confirmer la réservation du stand ★ (échéance aujourd'hui) | ○ → ✓ 16:30 | mar. 24, sans heure (30 min) |
| Stand | Préparer le matériel du stand | ○ | jeu. 26 · 14:00 (1 h) |
| Stand | Imprimer les badges de l'équipe | ○ | ven. 27 · 11:30 (30 min) |
| Supports | Envoyer le visuel à l'imprimeur | ✓ jeu. 19 | |
| Supports | Valider le texte des brochures | ✓ lun. 23 | (14:00, 1 h) |
| Supports | Imprimer les kakémonos | ○ | mer. 25 · 11:00 (30 min) |
| Supports | Comparer deux devis d'impression | ○ En réserve | — (30 min) |
| Démo | Appeler le fournisseur (priorité haute) | ○ matin (proposée) → ✓ 10:20 | mar. 24 · 10:00 (30 min) |
| Démo | Préparer la démo onduleur hybride | ○ | sans jour (2 h) ; placée jeu. 26 dans `agenda-semaine-planifier-pose` |
| Logistique | Réserver l'hôtel du salon | ○ | sans jour (30 min) |

**Recrutement technicien — 9 tâches** · 4 sur 9 le ven. 20 et le 24 (5 ouvertes, inchangé de la journée).
Faites : Valider le budget du poste (✓ mar. 10) · Choisir les sites d'annonce (✓ jeu. 12) · Définir le profil
recherché (✓ lun. 16) · Publier l'annonce (✓ jeu. 19). Ouvertes : Trier les CV reçus (mer. 25 · 14:00, 1 h ; la
« prochaine action ») · Rédiger la fiche de poste (sans jour, proposée puis gardée à 08:31 ;
14:10 Choisir un jour → jeu. 26, 1 h — ligne estampillée « → jeu. 26 ») · Planifier les entretiens (attend : Trier les
CV reçus, 30 min) · Préparer les questions d'entretien (sans jour, 45 min) · Appeler les candidats retenus (attend :
Planifier les entretiens, 30 min).

**Administratif — 10 tâches** · 7 sur 10 (3 ouvertes, inchangé). Faites : Payer la CNSS d'octobre (✓ lun. 2) ·
Envoyer les factures d'octobre (✓ mar. 3) · Payer le loyer du dépôt (✓ lun. 9) · Renouveler l'abonnement téléphonique
(✓ mer. 11) · Archiver les relevés bancaires (✓ ven. 13) · Payer la CNSS de novembre (✓ mar. 17) · Classer les factures
fournisseurs (✓ ven. 20). Ouvertes : Relire le contrat de maintenance (mar. 24 Ce soir, 45 min ; reste au bilan →
mer. 25) · Préparer la déclaration de TVA (ven. 27 · 10:00, 1 h) · Payer l'assurance du camion (ven. 27 · 15:00, 30 min).

**Site web — 4 tâches** · 0 sur 4, « À planifier », toutes sans jour : Lister les pages du site (1 h, prochaine action) ·
Choisir l'hébergeur (1 h) · Rédiger la page d'accueil (2 h) · Photographier trois chantiers (1 h).

## 3. La journée du mardi 24, minute par minute
- **08:20–08:29** (avant le matin) : saisie d'exemple « relancer l'imprimeur jeudi #Salon Solaire Expo !!! » (jamais
  validée : ne compte nulle part ; variante « #Stand partenaire » = projet absent de la barre latérale), fiche, erreur
  de champ, « Pas à jour », À trier (08:28), Copilote (08:29). Tous montrent l'état du matin.
- **08:30 — le matin** : **0 sur 5 · essentiel 0/2**. Essentiel : « Envoyer le devis révisé » (09:00, échéance mer.
  25) · « Confirmer la réservation du stand » (échéance aujourd'hui). Toute la journée : la visite. Prévu : « Rappeler
  pour le devis » 10:30 · « Suivi des relances : 5 ». Proposé = objectif − faites − gardées ouvertes = 5 − 0 − 2 = **3**,
  SANS heure, dans l'ordre de la règle (prochaine action de chaque projet, priorité du projet puis rang) :
  « Commander les rails de fixation » (Benali, Haute) · « Appeler le fournisseur » (Salon, Haute, priorité haute de la
  tâche) · « Rédiger la fiche de poste » (Recrutement, Moyenne). « Relire le contrat de maintenance »
  (Administratif, Basse) n'est PAS proposé : Reda l'ajoute à la main à 09:10 pour ce soir. Carte du moment « 3 tâches proposées pour atteindre 5 ·
  Garder ces 3 ». Repliés : À revoir 2 · En attente 1. Agenda du bureau : devis 09:00–11:00, Rappeler 10:30.
- **08:31** Garder ces 3 ; dans l'Agenda : rails à 08:30, fournisseur à 10:00 ; la fiche de poste reste sans jour. **08:52** rails faits. **09:10** Reda ajoute à la main
  « Relire le contrat de maintenance » pour ce soir (45 min).
- **09:41** (Agenda, tuile) : **1 sur 5 · essentiel 0/2**. Heure pleine masquée à moins de 20 min du trait : 10:00
  n'est pas écrite dans la gouttière.
- **10:00** rappel du fournisseur (`rappel-ouvert`). **10:20** fournisseur fait. **10:40** « Rappeler pour le devis »
  close. **10:45** conflit (`etat-conflit`). **10:50** devis envoyé. **11:30** 3 relances faites. **14:10** fiche de poste → jeu. 26 ; toast « Prévue jeu. 26 · Annuler » (Choisir un
  jour, `textes.md` §2.15 ; un REPORT dirait « Reportée à mer. 25 · Annuler », le jour réel).
- **15:00** : **3 sur 5 · essentiel 1/2**. Essentiel : devis 09:00 (fait, barré) · stand. Prévu, dans l'ordre :
  rails 08:30 (fait) · fournisseur 10:00 (fait) · Rappeler 10:30 (fait, activité ERP) · fiche de poste « → jeu. 26 » ·
  « Suivi des relances : 2 ». Ce soir : le contrat. Proposé : 5 − 3 − 2 = 0 → « Objectif couvert par ce que tu as
  gardé. » Colonne Agenda du bureau : rails 08:30, devis 09:00–11:00, fournisseur 10:00, Rappeler 10:30, tous barrés.
  Cockpit (15:02) : **3 sur 5 · 2 à faire** (stand, contrat). Hors ligne : 15:20.
- **16:30** stand confirmé.
- **18:20 — bilan** : **4 sur 5 · essentiel 2 sur 2**, puis « 4 des 5 gardées ». Faites : devis, fournisseur, rails,
  stand. Reste 1 : « Relire le contrat de maintenance » → « Reporter à mer. 25 » ; lot « Tout reporter à mer. 25 ». Un
  constat : « Tu finis plus souvent ton essentiel quand il est placé avant midi. »
- La tuile (maj 09:41) dit 1 sur 5 : c'est l'état de 9 h 41. Lignes dans l'ordre d'Aujourd'hui : devis 09:00 · stand ·
  visite (Toute la journée) · fiche de poste · fournisseur 10:00 · Rappeler 10:30 · contrat (soir) ; pied : « Valider le plan de
  calepinage · échéance jeu. 26 ».

## 4. La semaine du 23 au 29 (vue à 09:41 le mardi)
| Jour | Prévu (heure · durée) | Charge |
|---|---|---|
| lun. 23 (passé) | ✓ Commander les onduleurs 09:00 · ✓ Commander les 16 panneaux 11:00 · ✓ Valider le texte des brochures 14:00 · ✓ Rappeler le comptable 16:00 (sans projet). Non faites → À revoir : planning des poses, bureau de contrôle | 4 faites |
| mar. 24 | rails 08:30 (30 min) · devis 09:00 (2 h) · fournisseur 10:00 (30 min) · stand sans heure (30 min) · fiche de poste sans heure (1 h, jusqu'à son report de 14:10) · contrat ce soir (45 min) ; ERP : visite (Toute la journée), Rappeler 10:30 | 6 tâches · 5 h 15 pour 4 h |
| mer. 25 | Valider le plan de calepinage 09:00 (1 h) · Imprimer les kakémonos 11:00 (30 min) · Trier les CV reçus 14:00 (1 h) | 3 tâches · 2 h 30 pour 4 h |
| jeu. 26 | Réceptionner les 16 panneaux 09:00 (1 h) · Préparer le matériel du stand 14:00 (1 h) ; + démo onduleur (2 h) une fois posée | 2 tâches · 2 h pour 4 h (posée : 3 · 4 h pour 4 h) |
| ven. 27 | Préparer la déclaration de TVA 10:00 (1 h) · Imprimer les badges de l'équipe 11:30 (30 min) · Payer l'assurance du camion 15:00 (30 min) | 3 tâches · 2 h pour 4 h |
| sam. 28, dim. 29 | non travaillés | — |
« Toute la journée » ne porte QUE les éléments de l'ERP sans heure (visites, poses). Une tâche du jour sans heure vit
dans « À placer ». **À placer · 12** (Jour et Semaine, 09:41) : Aujourd'hui 3 (stand 30 min, fiche de poste 1 h, contrat ce soir 45 min) ·
À revoir 2 · Mes projets 7 (Salon : démo onduleur 2 h, hôtel 30 min ; Recrutement : questions
d'entretien 45 min ; Site web : pages 1 h, hébergeur 1 h, page d'accueil 2 h, photos 1 h). Ni une tâche en attente, ni
une tâche En réserve n'est à placer.
Plus loin (À venir, Mois) : lun. 30 nov. « Pose — Chantier Benali 9 kWc » (ERP, Toute la journée) · mer. 2 déc.
« Visite technique — Dar Bouazza » (ERP) · jeu. 3 déc. Mise en service (jalon Benali) · ven. 4 déc. échéance Benali.

## 5. Les jours passés (Mon rythme, Mois, revue)
| Jour | Faites | Dont, dans les projets (le reste est sans projet) |
|---|---|---|
| lun. 9 | 5 | Visiter le site · Payer le loyer du dépôt |
| mar. 10 | 5 | Relever les factures du client · Valider le budget du poste |
| mer. 11 | 4 | Renouveler l'abonnement téléphonique |
| jeu. 12 | 6 | Valider le dimensionnement · Choisir les sites d'annonce |
| ven. 13 | 3 | Préparer le devis · Archiver les relevés bancaires |
| lun. 16 | 5 | Faire signer le devis · Déposer la demande de raccordement · Définir le profil recherché |
| mar. 17 | 4 | Encaisser l'acompte · Payer la CNSS de novembre |
| mer. 18 | férié | — |
| jeu. 19 | 7 | Valider l'étude de toiture · Prévenir le syndic · Envoyer le visuel à l'imprimeur · Publier l'annonce |
| ven. 20 | 5 | Obtenir l'accord du bureau de contrôle · Classer les factures fournisseurs |
| lun. 23 | 4 | Commander les onduleurs · Commander les 16 panneaux · Valider le texte des brochures (+ Rappeler le comptable) |
Titres sans projet (réservoir) : Rappeler le comptable · Répondre au syndic de l'immeuble · Passer à la banque ·
Relancer M. Alaoui pour son avis · Commander des gants de sécurité · Mettre à jour le site de Google · Payer le parking
du dépôt · Envoyer les photos du chantier Salé.
**Mon rythme** : « Les 10 derniers jours travaillés » = 5, 5, 4, 6, 3, 5, 4, 7, 5, 4 (du lun. 9 au lun. 23, sans le 18) ;
total 48 ; 5 faites ou plus **6 jours sur 10**. Proposition (`textes.md` §4.2) : « Ces 10 jours travaillés, tu as fait
au moins 5 tâches 6 fois. On passe à 6 ? » — boutons **« Monter à 6 » · « Pas maintenant »** (une baisse : « Descendre
à 4 » · « Pas maintenant ») ; jamais « Passer à 6 », qui se confond avec « Passer ».
**Revue de la semaine** (ven. 20 à 17:40, à la place du bilan) : 5 + 4 + 7 + 5 = **21** faites en 4 jours · objectif
atteint 3 jours sur 4 · essentiel fait 3 jours sur 4. Par projet : Benali 6 faites (montrées : toiture, acompte,
signature), 10 sur 18 ; Salon 1 (visuel), 2 sur 11 ; Recrutement 2 (profil, annonce), 4 sur 9 ; Administratif 2 (CNSS,
factures), 7 sur 10 ; Site web 0, 0 sur 4 ; sans projet 10. Prochaines actions : Envoyer le devis révisé · Appeler le
fournisseur · Trier les CV reçus · Relire le contrat de maintenance · Lister les pages du site.

## 6. Autres journées (ne jamais les mêler au 24)
- **Lun. 2 nov., premier usage** (`data-histoire="2-nov-vide"` puis `"2-nov"`) : aucun projet ; la liste collée crée
  6 tâches dans Salon Solaire Expo (Réserver le stand, Imprimer les kakémonos, Préparer la démo onduleur hybride) et
  Recrutement technicien (Publier l'annonce, Trier les CV reçus, Valider le budget du poste) ; « 5 proposées pour ton
  objectif ».
- **Mar. 3 nov.** (`"3-nov"`, astuce et question du rappel) : 1 sur 5 ; Salon 2 ouvertes, Recrutement 2.
- **Lun. 7 déc., retour** (`"retour"`) : « Tu reviens après 10 jours : 18 tâches attendaient. » ; À trier 3 ; relances
  12 ; « Visite technique à Salé » ; proposées : Préparer la réception du chantier · Faire le point sur les contacts du
  salon · Appeler les candidats retenus · Payer la vignette du camion · Rédiger la page d'accueil.

## 7. Comptes de la coque (tâches OUVERTES ; `coque.js`)
| Heure du 24 | À trier | Benali | Salon | Recrutement | Administratif | Site web |
|---|---|---|---|---|---|---|
| avant 08:52 | 5 | 6 | 8 | 5 | 3 | 4 |
| 08:52–10:19 | 5 | 5 | 8 | 5 | 3 | 4 |
| 10:20–10:49 | 5 | 5 | 7 | 5 | 3 | 4 |
| 10:50–16:29 | 5 | 4 | 7 | 5 | 3 | 4 |
| dès 16:30 | 5 | 4 | 6 | 5 | 3 | 4 |
Le lot Projets est à 08:30 (12 sur 18, 3 sur 11). Une activité de l'ERP faite reste visible, barrée, à son heure.

## 8. Formes et mots
- UNE forme par idée : **segments** pour la journée (Aujourd'hui, bilan, tuile, cockpit, Copilote, Mon rythme) ;
  **barre fine** pour un projet ; ni anneau ni camembert. Compteur de cartes d'un rituel : « 1/5 ».
- La tuile n'est pas interactive : un point de couleur de projet devant chaque ligne, une icône pour l'ERP.
- Vocabulaire : `spec-7-ecrans.md` §3 et `textes.md` §1 ; interdits contrôlés par `outils/verifier.cjs`. Une tâche
  qui en attend une autre porte la puce « attend : {titre} ».
