# Vérifie AMSG — contre-visite de clôture du parcours PF8 « messages sortants », 14/11/2026

<!-- verifie | groupe: AMSG | pct: 96 | ecarts_s1_s2: 2 -->

Commande `loop audit` (14/11). Le groupe AMSG vient de franchir 95 % de tâches cochées : c'est la contre-visite de
**clôture** (METHODE §C.4.2). Les deux passes du 13/11 (`docs/audits/2026-11-13-messages-sortants-verifie.md`) avaient
relu 55 tâches ; celle-ci relit les **20 tâches cochées depuis**, dont AMSG92 (seul écart S2 du 13/11) et AMSG96.
Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `a12f40f82` (après `git fetch`), branche `verifie-cloture-1411`.
- **Registre.** PF8 `messages-sortants`, groupe AMSG : `audit_registre.py --du` (acceptation neutralisée, §C.4.5 f) dit
  « 96 % cochées (60/62) — vérifie dû, clôture ». Ouvertes : AMSG72 (rappel J-1 à 08:30) et AMSG83.
- **Échantillon.** Les 20 tâches cochées depuis le 13/11 sont relues, toutes : AMSG3, 10, 30, 36, 44, 62, 73, 84, 85, 86,
  87, 88, 89, 90, 91, 92, 93, 94, 95, 96. Quatorze touchent l'opposition / STOP (3, 84, 91), Meta (10, 36), un envoi à un
  tiers (62, 92, 93, 96), les horaires d'envoi (44, 73, 88) ou un message client (85, 86) : 100 % de ces familles.
- **Méthode.** Commits de chaque tâche (`git log --grep`), code sur `a12f40f82`, tests nommés, appelants et jumeaux par
  grep ; sondes hôte rejouées ; gardes hôte `check_garde_contact.py` et `check_beat_active_companies.py` : OK. Aucune
  pile, aucun Docker, aucun test Django lancé, aucune production consultée, aucun message envoyé.

## 1. Vérificateurs

Un vérificateur (opus, effort moyen), sans sous-agent, qui n'a construit aucune de ces tâches. Chaque écart retenu a été
relu une seconde fois dans le code avant d'être écrit.

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **16** | AMSG30, 36, 44, 62, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95 |
| partiel | **4** | AMSG3 (paires antérieures), AMSG10 (jumeau Odoo), AMSG73 (reprise différée), AMSG96 (jumeau SAV) |
| non-fait / faux / régression / déjà-présent | **0** | — |

Deux reverts du 13/11 (`45ae9bb4c3`, `aeb68bbf38`) visent des **doublons** d'AMSG10 et AMSG90 construits par une
seconde session ; le code d'origine (`cb4f6954ce`, `e95ef13efc`) et ses tests sont toujours présents
(`capi_crm.py` : un seul test `is_opposed` par constructeur ; `sav/views.py` : `public_url` aux trois sites).

## 2. Tests nommés

Les 20 tests nommés existent et sont comportementaux (vraie route, vraie tâche ou vraie commande ; état relu). Quatre
remarques : AMSG95 est un test de couverture (pas de code produit, conforme à la tâche) ; le test d'AMSG73 simule la
fenêtre à + 45 min, il ne couvre pas une ouverture lointaine (écart C-AMSG-VER3-101) ; le test d'AMSG3 crée la paire
APRÈS le code et ne couvre pas une empreinte déjà posée (écart C-AMSG-VER3-100) ; AMSG89 et AMSG94 ont leur test
d'écran (Vitest) non rejoué ici.

## 3. Sondes et preuve en direct

- **Rejeu des sondes existantes (hôte, 14/11).** `C-AMSG-001`, `002`, `006`, `010`, `012` : `repro: false`.
  `C-AMSG-VER2-101` : `repro: False` avec témoin vrai (backend qui envoie ⇒ 1 e-mail, `email_envoye` servi, réponse lue
  par l'écran) : **l'écart S2 du 13/11 est fermé dans le code** (AMSG92). Périmées (ne s'exécutent plus contre le code
  d'aujourd'hui, NON citées comme preuve) : `003`, `004`, `005` (`leads_doublons` importe désormais `activity`), `007`,
  `008`, `009`, `011` (symboles déplacés). AMSG3 a été revérifié par une sonde nouvelle (ci-dessous).
- **Sonde nouvelle** `docs/audits/sondes/AMSG/C-AMSG-VER3-100.py` (hôte, sans Django ni réseau), jouée le 14/11 :
  **repro: True**. Elle exécute le vrai `Lead.save`, les vrais `leads_doublons` et `portee_selectors`, le vrai receveur
  post_save `_empreinte_opposition_lead` et le vrai `tracer_opposition_registre`. Paire (A opposée, B au même numéro)
  présente au déploiement, empreinte de A déjà posée par la migration 0154 : après un nouveau STOP sur A, un
  enregistrement de A et un de B, `peut_contacter(B)` reste vrai. Témoin (même paire créée après AMSG3) : B2 cochée avec
  sa ligne de chatter, ce qui prouve que la chaîne réelle est traversée.
- **Preuve en direct.** Aucun enregistrement d'acceptation ne couvre encore ces 20 tâches (les trois du 13/11 couvrent
  AMSG1-64). Dix sont « code livré, preuve en direct due » (AMSG3, 30, 62, 84, 89, 92, 93, 94, 95, 96 ; AMSG56-58 et 68
  de la passe précédente aussi) ; elles restent à l'orchestrateur d'une session avec pile.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-AMSG-VER3-100 | AMSG3 | **S2** | `poser_empreintes_opposition` ne coche les fiches sœurs que pour une empreinte NEUVE ; la migration 0154 a posé celles de tous les opposés existants : une paire (opposée, non opposée au même contact) antérieure au déploiement n'est jamais rattrapée, la sœur reste contactable (prod du 11/11 : 2 numéros) | `docs/audits/sondes/AMSG/C-AMSG-VER3-100.py` | AMSG97 |
| C-AMSG-VER3-101 | AMSG73 | S3 | le balayage de 07:45 tourne tous les jours et programme la relance de signature par `eta` jusqu'au lundi (≈ 49 h) ou au jour ouvré suivant un férié, au-delà du `visibility_timeout` Redis (5 400 s) : message re-livré en boucle, plusieurs reprises le lundi 08:30 sans verrou ⇒ relance en double possible au signataire externe (latent : 0 demande en prod) | lecture | AMSG98 |
| C-AMSG-VER3-102 | AMSG96 | S3 | jumeau noté « autre geste » sans tâche : `sav/notifications_client.py::remettre_brouillon_whatsapp` ne pose jamais `assigned_to` ; l'auto-clôture du beat passe `user=None` : la tâche « Envoyer ce WhatsApp » n'est dans « Mes activités » de personne (latent : réglage éteint par défaut) | lecture | AMSG99 |
| C-AMSG-VER3-103 | AMSG10, AMSG36 | S3 | jumeau oublié de D-AMSG-3 : `capi_odoo.py` (`build_received_event`, `build_signed_event`) envoie `lead_id` et téléphone haché d'un contact opposé (latent : émission manuelle hors planning) | lecture | AMSG100 |
| C-AMSG-VER3-104 | AMSG43, 44, 88 | S3 | D-AMSG-1 dit « jours ouvrés » : rappel avant échéance et relevé mensuel partent un jour férié de semaine (18/11, 1er mai) ; la borne d'AMSG88 ignore les fériés (latent : e-mail en console) | lecture | AMSG101 |

Gravités rejugées.
- **C-AMSG-VER3-100 est S2.** Opposition légale (loi 09-08), données réelles au 11/11 (non relues aujourd'hui), et aucun
  geste ordinaire ne la rattrape. Le « fini quand » d'AMSG3 est tenu pour un STOP neuf ; l'écart porte sur l'existant.
  La correction est une réparation de données : commande en dry-run, liste montrée à Reda avant `--appliquer` (décisions
  du 11/11). Ne pas « corriger » en appelant `_opposer_fiches_soeurs` à chaque enregistrement : une sœur décochée
  délibérément serait recochée.
- Les quatre S3 sont latents (réglage éteint, e-mail en console, émission manuelle, 0 demande de signature).
- **Marqueur : 2 écarts S1-S2** = C-AMSG-VER3-100 (nouveau) + C-AMSG-VER2-101 d'origine, fermé dans le code mais dont la
  tâche AMSG92 est encore bloquée sur sa preuve en direct (§C.4.6). AMSG96 (S2, constat de la relecture du rejeu AMSG56)
  est conforme dans le code, preuve en direct due elle aussi.

Les cinq tâches v3 (AMSG97-101) sont prêtes, une par plan propriétaire (lead, documents, sav, acquisition,
facturation), aucune multi-propriétaire.

## 5. Optionnel (non déposé) et points pour le fondateur

- **AMSG36.** Le garde lit l'opposition par `devis.lead` ; un devis créé depuis la fiche client (sans lead) envoie à
  Meta l'e-mail et le téléphone hachés du client, même si ce contact porte une empreinte d'opposition. Fermer ce cas
  demanderait `porte_une_opposition` sur les coordonnées du client (cas rare, lead-primary).
- **AMSG62.** Le téléphone « fictif » posé par `neutraliser_contacts_demo` (`+212600` + 6 chiffres) a la forme d'un vrai
  mobile marocain, alors que la tâche demande des valeurs non délivrables ; même remarque qu'AMSG60 le 13/11.
- **AMSG96, jumeau automatisations.** `automation/actions.py::_send_whatsapp` crée aussi « Envoyer ce WhatsApp » sans
  `assigned_to` (propriétaire parametres) ; visible sur la fiche, pas dans « Mes activités ».
- **AMSG73.** `relancer_signataires_dus` ne verrouille pas les signataires dus ; inoffensif tant qu'une seule reprise
  par jour est programmée (AMSG98).
- **AMSG94.** Le refus garde aussi le toast du pont global (`api/axios.js`) en plus du message sous le champ.
- **AMSG30.** La commande n'est pas bornée à une société (ids explicites, geste du fondateur) : conforme au texte.
- Sondes périmées : `C-AMSG-003` à `005`, `007` à `009`, `011` ne tournent plus contre le code d'aujourd'hui ; à
  réaligner si l'on veut les rejouer.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 20 tâches cochées depuis le 13/11 : code, commits, tests nommés, appelants, jumeaux (autre canal,
  autre tâche Celery, autre gabarit), décisions D-AMSG-1 à 3 et 5-6 ; treize sondes rejouées (six encore exécutables), une sonde nouvelle.
- **Non couvert (sans pile).** Aucun test Django ni Vitest lancé (la preuve des tests est la CI de `main`) ; aucun rejeu
  navigateur (AMSG89, 92, 94 sont des écrans) ; aucune lecture de la production (les 2 paires du 11/11 n'ont pas été
  recomptées ; la présence de `CAPI_CRM_DATASET_ID` et l'état de `notifications_client_sav` ne sont pas connus) ; la
  re-livraison Redis d'AMSG73 est lue (réglage + limite connue de Celery), pas reproduite.
- **Statut.** Un écart S2 nouveau (C-AMSG-VER3-100, AMSG97) et quatre S3 (AMSG98-101). Le groupe reste « construit » :
  il ne peut devenir « vérifié » qu'après une contre-visite d'AMSG97 cochée et la preuve en direct d'AMSG92.

## 7. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0 M (aucun sous-agent ; jetons du vérificateur non relevés) ; aucun appel Fable.
