# L'app Visites terrain

Depuis le groupe VTA (commande fondateur du 12/09/2026), la visite technique
n'est plus un écran du CRM : c'est une **app à part entière**
(`apps/visites` côté serveur, `/visites` côté écran). La raison est une phrase
du fondateur : *« l'utilisateur qui fera la visite n'aura probablement pas
l'accès CRM »*. Tant que la visite vivait dans le CRM, lui ouvrir la visite lui
ouvrait l'annuaire des leads. La frontière est maintenant **structurelle**, pas
déclarative.

---

## 1. Le rôle « Commercial terrain »

C'est le rôle de la personne qui se déplace. Il est **semé automatiquement**
dans chaque société (comme Directeur, Commercial, Technicien…), donc il est déjà
là : rien à créer.

**Ce qu'il voit :**

- l'app **Visites**, et elle seule — son écran d'accueil ne montre que cette
  tuile ;
- **ses** visites : celles qui lui sont assignées. Pas celles de ses collègues ;
- dans une visite : la fiche client (nom, téléphone, WhatsApp, adresse, GPS) et
  les devis du client en **lecture seule**, avec les prix **client**.

**Ce qu'il ne voit pas :**

- le CRM. L'annuaire des leads lui répond « accès refusé » — ce n'est pas un
  menu caché, c'est le serveur qui refuse ;
- aucun prix d'achat, aucune marge, nulle part ;
- il **ne peut pas valider** sa propre visite : le feu vert appartient à
  quelqu'un d'autre (voir plus bas).

**Les autres rôles ne changent pas.** Commercial, Commercial responsable,
Responsable et Directeur gardent exactement l'accès aux visites qu'ils avaient ;
le rôle **Technicien** n'est pas touché du tout (c'est le métier du
*post-vente*, avec sa propre journée dans le module Installations).

---

## 2. Créer un utilisateur terrain

**Paramètres → Utilisateurs → Nouvel utilisateur**, puis choisir le rôle
**« Commercial terrain »**.

C'est tout. Il se connecte avec ses identifiants, arrive directement sur « Ma
journée », et n'a accès à rien d'autre.

Pour qu'il reçoive du travail, il faut ensuite lui **assigner** des visites
(section suivante) : il est prévenu par la cloche à chaque assignation.

---

## 3. Le flux d'une visite

1. **Planifier.** Depuis la fiche d'un lead (onglet Visites) ou depuis l'app
   Visites : on choisit le client, la date, et **l'assigné**.
2. **Assignation.** L'assigné reçoit une notification (cloche) avec un lien
   direct vers la visite. Une réassignation prévient le nouvel assigné ; une
   simple correction de notes ne sonne personne.
3. **Ma journée.** C'est l'accueil de l'app : les visites **du jour** et celles
   **en retard**, avec pour chacune l'heure, le client, la ville, un lien de
   navigation et un badge de complétude.
4. **En route → Arrivé.** Deux boutons au pouce. L'heure est posée par le
   **serveur** (le téléphone ne choisit pas l'heure), les deux boutons sont sans
   danger si on appuie deux fois, et seul l'assigné peut les utiliser. Oublier
   « En route » n'empêche pas de pointer « Arrivé ».
5. **Remplir.** Photos par emplacement nommé (toiture, tableau électrique, mur
   de l'onduleur, cheminement, façade) et mesures par catégorie. Le module
   **n'émet aucun verdict** : il enregistre ce qui a été relevé, il ne dit
   jamais si c'est « suffisant ».
6. **Terminer.** Le serveur **refuse** tant qu'il manque une photo obligatoire
   ou une mesure attendue, et la réponse **liste ce qui manque**, nommément.
7. **Feu vert.** Une personne portant le droit **« valider »** (Commercial
   responsable, Technicien responsable, Responsable, Directeur) relit le dossier
   et donne — ou refuse — le feu vert au calepinage. Si elle refuse, elle
   **renvoie** la visite avec le motif, et les photos/mesures visées
   redeviennent à refaire.
8. **Retour sur la fiche client.** Au feu vert, le lead porte lui-même
   « visite effectuée » et un récapitulatif court des mesures **réellement
   relevées** — jamais un chiffre inventé pour combler un trou. Une note écrite
   à la main n'est jamais écrasée, et une re-validation ne duplique rien.

Une visite validée est **gelée** (lecture seule). Pour la rouvrir, il faut la
renvoyer.

---

## 4. Hors ligne

Le terrain, c'est souvent un toit sans réseau. L'app s'appuie sur la
**file d'attente hors-ligne partagée de l'ERP** (la même que les autres
modules — jamais une seconde file maison) :

- les photos et les mesures saisies sans réseau sont **mises en attente** ;
- elles repartent toutes seules au retour du réseau, ou quand on revient sur
  l'app ;
- le badge habituel de l'ERP indique ce qui reste à envoyer ;
- si un envoi échoue définitivement, c'est **visible**, avec un bouton pour
  réessayer — jamais une perte silencieuse.

Ce qui exige le serveur reste en ligne : la complétude, les horodatages « En
route / Arrivé », et le feu vert.

---

## 5. Ce qui n'a pas changé

- Les **données** n'ont pas bougé d'un octet : les visites déjà enregistrées
  sont exactement les mêmes, sur les mêmes tables.
- Le **statut d'une visite** reste un état interne au document : il ne touche
  jamais l'étape commerciale du lead (le funnel de `STAGES.py`).
- La texture de toit assemblée alimente toujours l'atelier 3D / calepinage,
  qui la demande « pour ce lead » sans rien savoir du module visite.
- Les anciens liens `/crm/visites/…` déjà envoyés en notification ont été
  réécrits vers `/visites/…` : aucune cloche ne mène à un écran mort.

---

## 6. Repères techniques

| Quoi | Où |
| --- | --- |
| App serveur | `backend/django_core/apps/visites/` |
| Contrats d'API | `apps/visites/contract_samples/visite_terrain.json`, `ma_journee.json` |
| Accueil de l'app | `GET /api/django/visites/ma-journee/` |
| Agrégat d'une visite | `GET /api/django/visites/visites/<id>/` |
| Checklist (source unique) | `apps/visites/visite_checklist.py` |
| Droits | `visites_voir` / `visites_creer` / `visites_modifier` / `visites_valider` |
| Retour vers le CRM | événement `visite_validee` (`core/events.py`) → `apps/crm/receivers.py` |

La visite lit le CRM et les ventes **uniquement** par leurs `selectors.py` /
`services.py` ; elle n'importe jamais leurs modèles. Un contrat import-linter
le verrouille.
