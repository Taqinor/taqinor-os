# Vérifie ACVI — contre-visite de clôture du parcours PA1 contact → visite, 05/11/2026

Commande `loop audit` (reprise du 04-05/11). La contre-visite de mi-parcours du 04/11 au matin (63 %) avait déposé ACVI100-101 ;
le groupe compte 99 tâches cochées sur 101 (ACVI46, ACVI87 ouvertes, 98 %) : la clôture est due. La contre-visite n'a rien
construit, n'a lancé aucun deploy, n'a rien écrit en prod. Pile locale partagée ; chaque sonde tourne en transaction annulée,
les e-mails restent en mémoire.

## 0. Préconditions

- **SHA.** `origin/main` = `64c9c7317` (code identique au moment de la rédaction). Branche de claim : `verifie-acvi-0411-cloture`.
- **Registre.** PA1 `contact-visite`, groupe ACVI, 101 tâches, 99 `[x]`.
- **Échantillon (graine = SHA `64c9c7317`).** Les 9 P0/S1 cochées + ACVI100-101 (écarts du matin) + 22 tirées = **33 tâches**,
  4 lots.
- **Déjà déposé, non redéposé.** ADEV108-109 (origine d'upsell), ASEC66 et suivantes, contre-visites du 04/11.

## 1. Vérificateurs (4 lots, opus, effort élevé, frais, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **29** | ACVI1, 2, 7, 11, 19, 21, 22, 25, 26, 29, 33, 39, 42, 44, 54, 59, 62, 69, 74, 77, 79, 81, 89, 90, 92, 93, 99, 100, 101 |
| partiel | **4** | ACVI6, 43, 53, 98 (jumeau oublié) |
| non-fait / faux / régression | **0** | — |

Écarts du matin : ACVI100 et ACVI101 fermés (sondes VER1-202 et VER1-106 rejouées). Garde `check_garde_contact.py` rejouée verte —
mais elle ne scanne que deux apps (voir §4).

## 2. Tests nommés

Tous présents dans un module existant. Tests faibles relevés : ACVI29 (marqueur posé à la main au lieu d'un PATCH), ACVI62 et
ACVI69 (fonctions appelées directement), ACVI98 (« 0 activité » non vérifié). Aucun test rejoué en local (CI d'abord).

## 3. Sondes

| Sonde | Tâche | Verdict |
|---|---|---|
| `docs/audits/sondes/ACVI/C-ACVI-VER4-001.py` | ACVI43 | REPRO : le rappel demandé lève l'opposition mais garde son empreinte |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-002.py` | ACVI98 | REPRO : le brouillon de suivi de l'assistant rend un lien WhatsApp vers un lead opposé |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-010.py` | ACVI98 | REPRO : aperçu et envoi WhatsApp d'un devis vers un lead opposé, devis passé « envoyé » |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-011.py` | ACVI6 | REPRO : un Commercial de portée « soi » lit les commentaires et activités du lead d'un collègue |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-012.py` | critique | REPRO : e-mail du devis au lead opposé (moteur PDF simulé), lien de partage et PDF partagé passent « envoyé », résumé envoyé à l'associé |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-020.py` | ACVI54 | REPRO : brouillon de l'assistant avec accolades et expéditeur vide |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-021.py` | ACVI53 | REPRO : fichier WhatsApp en masse qui écrit notre marque à la place de la société du client |
| `docs/audits/sondes/ACVI/C-ACVI-VER4-030.py` | ACVI62 | conforme |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ACVI-VER4-010 (+ -012) | ACVI98 | S1 | aucun envoi de devis ne lit l'opposition : WhatsApp, e-mail réel, lien de partage et PDF partagé vers un lead « ne plus contacter » (D-ACVI-7) | REPRO (+ L2) | ACVI102 |
| C-ACVI-VER4-002 | ACVI98 | S1 | brouillon WhatsApp de l'assistant vers un lead opposé | REPRO (+ L2) | ACVI103 |
| C-ACVI-VER4-012 | critique | S2 | résumé envoyé à l'associé avec le lien de proposition d'un lead opposé | REPRO | ACVI104 |
| C-ACVI-VER4-011 | ACVI6 | S2 | commentaires et activités d'un lead hors portée lisibles par les listes génériques (liste et détail) | REPRO | ACVI105, ACVI106 |
| critique | ACVI89, ACVI98 | S3 | la garde des contacts ne scanne que crm et automation et tolère à tort des sites corrigés ; D-ACVI-10 = les messages contractuels vers un client signé restent permis | lecture | ACVI107 |
| C-ACVI-VER4-001 | ACVI43 | S3 | empreinte d'opposition gardée après un rappel demandé | REPRO | ACVI108 |
| C-ACVI-VER4-021 | ACVI53 | S3 | `{societe}` du fichier en masse rendu avec notre marque | REPRO | ACVI109 |
| C-ACVI-VER4-020 | ACVI54 | S3 | brouillon de l'assistant non rendu comme les touches | REPRO | ACVI110 |
| critique | ACVI89 | S3 | générateurs de messages sans garde interne : tout nouvel appelant fuit | lecture | ACVI111 |

Seconde lentille sur les S1 : maintenus, élargis (e-mail réel du devis, lien de partage, PDF, résumé à l'associé ; la garde ne
voit ni ventes ni installations). Critique Fable (1) : inventaire de tous les envois vers un lead, un client ou un tiers ;
distinction contractuel / prospection (D-ACVI-10) ; point de passage unique à l'enregistrement « envoyé ».

## 5. Optionnel (non déposé)

- `notifications_acceptation._build_acceptance_wa_url` et `leads_notifications._build_lead_wa_reply_url` construisent un lien
  vers un lead sans lire l'opposition (S3 inférés, non sondés).
- OTP de signature demandé par le client lui-même : non bloqué (c'est la personne qui agit).
- ACVI42 : un rappel convenu peut être entraîné par le report d'une touche antérieure (rare, non sondé).
- ACVI19 : `--company-id 0` traite toutes les sociétés.
- Ordre de construction : ACVI107 (garde) en dernier dans le groupe, sinon ses entrées de liste blanche deviennent périmées.

## 6. Couverture et sortie de cycle

- **Couvert.** 33 tâches sur 99 cochées ; 8 sondes jouées (et 2 rejouées) dans la pile locale.
- **Non couvert.** Les 66 autres tâches cochées ; aucun rejeu navigateur ; e-mail du devis prouvé avec le moteur PDF simulé.
- **Statut.** 2 écarts S1 et 2 S2 ⇒ ACVI reste dans le cycle : prochaine clôture due quand ACVI102-111 seront cochées.

## 7. Coût

- 4 vérificateurs + 1 seconde lentille + 1 lot de sondes de critique (opus, effort élevé) ≈ 1,6 M de jetons ; 1 critique
  Fable ≈ 0,2 M ; 1 rédacteur.

<!-- verifie | groupe: ACVI | pct: 98 | ecarts_s1_s2: 4 -->
