# Vérifie APDF — contre-visite de clôture du groupe pdf (X4), 24/10/2026

Commande `vérifie APDF` (METHODE §C.4.2, skill audit §5), lancée par `loop audit` (4ᵉ itération du 24/10, après ASAV,
ACRM et APAR). `audit_registre.py --du` liste APDF en clôture (≥ 95 % : 53/54). C'est la deuxième contre-visite du groupe,
après celle de mi-parcours du 11/10 (`docs/audits/2026-10-11-pdf-verifie.md`).

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test rouge nommé et le code de `main` avec
les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 à sonde obligatoire est prouvé par
une sonde exécutée en transaction annulée. Les écarts confirmés sont déposés en tâches v3 dans le plan du propriétaire des
fichiers. La contre-visite n'a rien construit et n'a lancé aucun deploy. Une seule lecture de production, en lecture seule
(accord permanent `docs/claude-memory/prod-read-access.md`), annoncée dans la conversation : voir §0.

## 0. Préconditions

- **SHA.** `origin/main` = `90cf82d6b` (PR #1028), re-fetch en début d'itération. Branche de claim : `verifie-apdf-cloture`
  (commit vide `ac1a898f2`, poussé).
- **Registre.** X4 `pdf`, groupe APDF, statut calculé `vérifié` avant ce dépôt (53/54, 98 %, mi-parcours sans écart S1-S2).
- **Inventaire (déterministe).** 57 tâches APDF, 53 `[x]`. Restent : APDF35, APDF36, APDF48 `[BLOCKED: acceptation]`,
  APDF99 (acceptation en direct du groupe).
- **Échantillon (graine = SHA `90cf82d6bb04e778ae7a582b9ccd2fbaf41f91f3`).** Les 8 P0/S1 cochées (APDF2, 3, 4, 5, 21, 22,
  45, 90) et 25 % du reste tirées par `random.Random(int(sha, 16)).sample` (11 sur 45) : APDF9, 15, 25, 26, 27, 29, 31, 32,
  43, 91, 100. Total : **19 tâches**.
- **Pile des sondes.** Conteneur jetable `sonde-verifie-asav` rafraîchi au code de `main` (`90cf82d6b`) ; base de démo à
  jour (0 migration en attente). Rendus `/proposal` réels (WeasyPrint), réseau coupé, transactions annulées : base inchangée.
- **Production (lecture seule).** Commit déployé `90cf82d6b`. **Une seule société** (« TAQINOR Démo ») : 119 devis sur 30
  jours, 22 au statut envoyé. Profil : RC, ICE et logo renseignés ; **`capital_social` et `forme_juridique` vides**.
  Conséquences : les écarts d'identité d'une autre société (§3) sont latents tant qu'une seule société émet des devis ; en
  revanche les nouveaux rendus des devis TAQINOR n'impriment plus « forme juridique au capital de … », puisque APDF3 a retiré
  les littéraux et que D-APDF-1 demandait de renseigner le profil d'abord (voir §3, constat de données).

## 1. Vérificateurs (6 agents frais, opus, effort élevé, lecture seule, même répertoire, 2 à 5 tâches chacun)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | APDF2, 3, 15, 21, 22, 25, 26, 27, 29, 32, 43, 90, 91, 100 |
| partiel | **5** | APDF4 (S1 + S4), APDF5 (S3), APDF9 (S3 + S4), APDF31 (S3), APDF45 (S1 + S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Points saillants des tâches ok : APDF2 / APDF3 (une seule fonction pour la ligne RIB et pour la bande légale, lue par tous
les gabarits ; champs vides omis, jamais « None » ; acceptation en direct PASS du 11/10 pour APDF3) ; APDF25 (aucune police
arabe vendorisée ; l'image Django porte 8 polices système à glyphes arabes, dont Noto Sans Arabic — vérifié par `fc-list`) ;
APDF32 (ICE / IF / RC / patente sur BL FR et AR, PV et dossier de remise depuis la source unique, prestations hors PV/BL) ;
APDF43 (économies du portail au tarif de la société, recalcul à la main conforme).

## 2. Sondes (2 REPRO)

| Sonde | Tâche | Observé (code de `main`, rendu `/proposal` réel, société « SOLAIRE EXEMPLE SARL ») |
|---|---|---|
| `docs/audits/sondes/APDF/C-APDF-VER-001.py` | APDF45 | titre du PDF résidentiel complet (`include_etude`) : **« Devis TAQINOR N° DEV-SONDE-APDF-001 »** ; une-page : « Devis SOLAIRE EXEMPLE SARL N° … » |
| `docs/audits/sondes/APDF/C-APDF-VER-002.py` | APDF4 | société sans logo, devis envoyé avec lien de partage : 2 QR du PDF construits avec `logo=True`, donc avec l'asset `logo.png` du moteur au centre ; le lien pointe sur `taqinor.ma/proposition/…` |

## 3. Écarts retenus

| Constat | Tâche | Écart de | Crit. | Grav. | Emplacement | Observé → attendu | Sonde |
|---|---|---|---|---|---|---|---|
| C-APDF-VER-009 | sans tâche : action fondateur | APDF3 (D-APDF-1) | C9 | S1 | `apps/parametres/models_company.py::CompanyProfile` | en production, `capital_social` et `forme_juridique` vides : depuis le retrait des littéraux (APDF3), les nouveaux rendus des devis TAQINOR n'impriment plus la forme ni le capital → renseigner Paramètres › Société (écran d'APDF22) | lecture production (§0) |
| C-APDF-VER-001 | APDF101 | APDF45 | C1 | S1 | `apps/ventes/quote_engine/generate_devis_premium.py::build_html` | titre `<title>Devis TAQINOR N° …</title>` codé en dur : le titre du PDF complet d'une autre société est « Devis TAQINOR » → `ENT_NOM_MARQUE`, comme le une-page | `docs/audits/sondes/APDF/C-APDF-VER-001.py` |
| C-APDF-VER-002 | APDF102 | APDF4 | C1 | S1 | `apps/ventes/quote_engine/residential/theme.py::qr_data_uri` | `logo=True` par défaut incruste l'asset du moteur (logo TAQINOR) au centre du QR « Scannez pour signer » (signature résidentielle, document agricole) → logo imprimé de la société ou aucun | `docs/audits/sondes/APDF/C-APDF-VER-002.py` |
| C-APDF-VER-008 | APDF108, APDF109 (+ APDF111, test lead réaligné) | critique (voisin d'APDF5) | C1 | S1 | `frontend/src/features/ventes/clientProposalLink.js::proposalWhatsappText` | texte WhatsApp pré-rempli pour le client « … proposition d'installation solaire Taqinor » pour toute société ; même marque dans le texte de consentement de témoignage (`ConsentScreen.jsx`) → sans marque codée | `docs/audits/sondes/APDF/C-APDF-VER-008.mjs` (sonde Node, fonction pure) |
| C-APDF-VER-007 | APDF110 (contrat d'abord), APDF107 | hors tâche (routage du dossier du 08/10 jamais déposé) | C3 | S2 | `apps/web/src/pages/proposition/[...token].astro` | le bloc « Qui est Taqinor ? » lit l'identité légale TAQINOR (`lib/nap.ts`) pour toute société ; une société sans site reçoit le lien `taqinor.ma/proposition/…` → identité de l'émetteur servie, sinon bloc masqué | STATIQUE |
| C-APDF-VER-003 | APDF103 | APDF45 | C20 | S3 | `apps/ventes/tests/test_pdf_apdf_identite.py::GardeIdentiteTests` | la garde ne rend que des brouillons (ni lien, ni QR) et compare les images par taille : le QR et le titre TAQINOR passent vert → état envoyé, titre et QR contrôlés | STATIQUE |
| C-APDF-VER-004 | APDF104 | APDF5 | C10 | S3 | `apps/ventes/quote_engine/builder.py::build_quote_data` | le lien de signature du PDF est construit sur le site de la société (page absente), l'e-mail sur `url_proposition` : deux liens pour un devis → `url_proposition` seul | STATIQUE |
| C-APDF-VER-005 | APDF105 | APDF9 | C1 | S3 | `apps/ventes/quote_engine/residential/trust.py::build` | le titre des clauses reste « Clauses particulières » en en / ar sur le premium résidentiel et C&I (jumeau oublié) → langue du document | STATIQUE |
| C-APDF-VER-006 | APDF106 | APDF31 | C1 | S3 | `apps/ventes/utils/pdf.py::generate_releve_pdf` | relevé client en français sans mention de repli pour un client arabe (D-APDF-3) → même mention que le BC / pro-forma | STATIQUE |

**Constats S1-S2 : 5** (4 S1 dont 1 de données de production, 1 S2). Hors données de production, ils sont **latents** :
la production n'a aujourd'hui qu'une société, TAQINOR elle-même ; ils deviennent réels au premier devis d'une deuxième
société. Tâches routées par propriétaire : MOTEUR (APDF101-105, APDF113), FACTURATION (APDF106), DEVIS (APDF110, moitié contrat
M0 de la page web, puis APDF108), WEB (APDF112, copie web du contrat, et APDF107 après APDF110, `docs/WEB_PLAN.md`),
ACQUISITION (APDF109), LEAD (APDF111). Deux lots se livrent dans le même merge : APDF110 + APDF112 + APDF113 (contrat
`proposal_data` servi, ses deux copies et le compte de clés du test de forme), et APDF108 + APDF111 (texte WhatsApp et test
de la fiche lead qui en porte l'ancien littéral). L'API publique de la proposition ne sert aujourd'hui aucune identité d'émetteur :
la page web ne peut s'aligner qu'une fois ce contrat livré. Elles entrent dans le périmètre de l'acceptation de groupe APDF99, toujours ouverte.

**Action fondateur (C-APDF-VER-009).** Renseigner « Capital social » et « Forme juridique » dans Paramètres › Société
(production) : les prochains rendus de devis réimprimeront la bande légale complète. Aucun code à changer.

## 4. Critique de complétude (1 appel Fable, effort élevé)

Des écarts S1 subsistant, la critique Fable unique a été jouée (contexte frais, lecture seule), avec un balayage de toutes
les sorties client à la recherche d'une identité TAQINOR restante.

- **C-APDF-VER-001 / 002 confirmés en S1 latent.** WeasyPrint tire le titre du PDF du seul `<title>` (aucune autre
  métadonnée posée) ; le QR des pages de couverture et du premium passe déjà `logo=False`, seuls la signature résidentielle
  et le document agricole l'incrustent.
- **Prémisse vérifiée.** `CompanyProfile.get` crée toujours le profil avec le nom de la société : les replis « TAQINOR » du
  moteur (sans profil) sont morts pour toute société nommée.
- **Trou ajouté, sondé.** Le texte WhatsApp pré-rempli pour le client (C-APDF-VER-008, sonde Node REPRO) et son voisin du
  consentement de témoignage.
- **Balayé sans écart.** Noms de fichiers des PDF, sujets et corps d'e-mail (« L'équipe {nom} »), littéraux ICE / RC / RIB
  (replis, démo, site public légitime), QR hors moteur (SAV, GED), gabarits `templates/pdf/*`, relances internes.
- **Spot-check des « ok »** (APDF3, APDF32) : aucune divergence.
- **Optionnels.** `alt="TAQINOR"` sur l'image du logo legacy (visible seulement si l'image ne charge pas) ;
  `_identite_textes` replie sur `settings.ENTREPRISE_*` pour une société sans adresse (non vérifié : valeur de l'environnement
  de production non lue) ; BL des installations et bordereau de remise sans patente (hors périmètre d'APDF32).

## 5. Optionnel (non déposé)

- APDF4 (S4) : le document agricole de 3 pages n'imprime aucun logo de société (absence, aucune fuite).
- APDF9 (S4) : unités françaises restées sur le une-page en / ar (« kWh/an », « MAD/kWc », « kWh/mois ») alors que les clés
  du catalogue existent ; `alt` du QR en français.
- APDF2 : `test_sans_profil_ligne_historique` vit dans `RegleUniqueTests` (nommage) ; le test HTML ne passe pas par PyMuPDF
  (couvert par la garde réelle d'APDF45).
- APDF22 : le chargement réel profil → formulaire n'est pas testé ; l'écran n'a jamais été rejoué en direct.
- APDF25 : le test n'a pas la comparaison d'image demandée par la tâche (extraction du texte seulement).
- APDF27 : le test ne vérifie ni la raison sociale ni le rendu arabe ; les avoirs rendus avant la tâche gardent leur PDF.
- APDF29 / APDF31 : branches de test non exercées (validité calculée, pro-forma en repli).
- APDF43 : le portail utilise le tarif à plat de la société, le devis le prix moyen par tranches ; pas de test à deux sociétés.
- APDF45 : `alt="TAQINOR"` sur l'image du logo legacy ; « main-d'œuvre TAQINOR » dans un sous-libellé de garantie non imprimé.
- APDF90 / APDF91 : décisions consignées sans la phrase du fondateur mot pour mot.

## 6. Couverture et non-couvert

- **Couvert.** 19 tâches sur 53 cochées (les P0/S1 + 25 %), commits, tests nommés (lus ; le rapport du nocturne
  release-verify du 24/10 relu pour les tests `@tag pdf`), code de `main`, décisions D-APDF-1 à 4, une lecture de production.
- **Non couvert.** Les 34 autres tâches cochées ; aucun aller-retour en direct à l'écran (APDF99 ouverte) ; la page publique
  `/proposition` d'apps/web n'a pas été rendue (constat statique).
- **Statut du registre.** Après ce dépôt : 53 cochées sur 67 constructibles (79 %, APDF101-113 ajoutées) ; contre-visite de
  clôture **avec 5 écarts S1-S2** → statut calculé `audité` ; le cycle n'est pas sorti.

## 7. Coût

- 6 vérificateurs opus (effort élevé) : ≈ 1,02 M de jetons, 239 appels d'outil. 1 critique Fable (effort élevé) : ≈ 0,17 M.
  1 rédacteur opus : ≈ 0,31 M (13 tâches v3 dans 6 plans, propriétaires vérifiés fichier par fichier, dépendances de contrat
  repérées : copie web du contrat, compte de clés, test de la fiche lead).
- Orchestrateur : échantillon déterministe, triage des 19 verdicts, contrôle des polices arabes de l'image, lecture de
  production en lecture seule, 3 sondes écrites et jouées (2 rendus `/proposal` réels, 1 sonde Node), routage, rédaction.
- H0 S0 O7 F1 · jetons sous-agents ≈ 1,5 M

<!-- verifie | groupe: APDF | pct: 98 | ecarts_s1_s2: 5 -->
