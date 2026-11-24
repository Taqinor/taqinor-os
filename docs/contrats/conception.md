# Dossier contractuel d'un chantier — conception (24/11/2026)

Demande de Reda (24/11/2026) : l'ERP crée, pour chaque lead signé, **quatre contrats** au moment où le chantier est
créé — (1) le contrat de démarrage, envoyé en premier, avec les paiements du devis final (modifiables) et les
garanties (modifiables) ; (2) le matériel livré au domicile, avec la part à payer à ce stade, en **deux versions
prêtes** (reste à régler / le client a payé ses 90 %) ; (3) les travaux bien terminés, signé par le client à la fin
(protection si le solde n'est pas payé) ; (4) le contrat final au paiement complet, avec les garanties et des
conseils de consommation. Le meilleur contenu, et surtout la beauté.

Ce fichier est LA spécification de construction. Le contrat d'API est dans
`backend/django_core/apps/documents/contract_samples/` (il fait foi pour toute forme servie), le droit dans
`docs/contrats/juridique.md`, l'état du chantier L5 dans `docs/contrats/ETAT.md`.

## 1. Ce qui existait, ce qui est neuf (régime MIXTE, lu sur `origin/main@854d2adfe`)

| Promesse | Avant | Verdict |
|---|---|---|
| Un contrat de démarrage | rien (`apps/contrats` est une coquille parquée, à ne jamais toucher) | absent |
| Actes créés avec le chantier | rien | absent |
| Livraison + part à payer, deux versions | `documents.builders.generate_bon_livraison` : liste du matériel, aucun montant | partiel |
| Travaux terminés, signé | `generate_pv_reception` : « constate la réception », ni conformité, ni solde, ni réserves (résidentiel) | partiel |
| Document final : payé, garanties, conseils | `generate_dossier_remise` : garanties + conseils d'ENTRETIEN ; aucun quitus, aucun conseil de consommation | partiel |
| Textes modifiables par acte | `parametres.DocumentTemplates` (textes du devis seulement) | absent |

P = 1,5 / 6 → MIXTE. Les quatre documents existants (`pv-reception`, `bon-livraison`, `dossier-remise`,
`attestation`) restent tels quels : **liste à ne pas changer** = `apps/documents/builders.py`, `views.py`, leurs
gabarits `templates/pdf/document_*.html`, leurs tests, `signer-client`. Le dossier contractuel est une famille NEUVE à
côté, dans la même app.

## 2. Où vit le code

- **Serveur** — tout dans `backend/django_core/apps/documents/` (propriétaire `documents`) :
  `models.py` (les deux modèles), `migrations/0001_…`, `contrats/` (`textes.py`, `contenu.py`, `services.py`,
  `selectors.py`, `rendu/`), `receivers.py`, `views_contrats.py`, `serializers_contrats.py`, `urls.py` (ajout),
  `contract_samples/`, `tests/test_contrats_*.py`.
- **Écran** — `frontend/src/pages/installations/contrats/**` (propriétaire `chantiers`), un onglet « Contrats » dans
  `InstallationDetail.jsx` (deux insertions seulement : le déclencheur et le contenu), les appels dans
  `frontend/src/api/documentsApi.js`, les styles dans `frontend/src/styles/chantiers/contrats.css`.
- Aucun fichier de `ventes`, `facturation`, `crm`, `stock`, `sav`, `installations` (serveur) n'est modifié : lecture
  par leurs sélecteurs et services existants, événements existants de `core/events`.

## 3. Modèle de données (`apps/documents/models.py`)

`ActeContractuel` — une ligne par acte et par variante (cinq lignes par chantier) :
`company` (FK, jamais lue du corps), `chantier` (FK chaîne `installations.Installation`, PROTECT,
`related_name='actes_contractuels'`), `type` (`contrat_installation` | `pv_livraison` | `pv_reception` |
`cloture_garanties`), `variante` (`''` | `reste_a_regler` | `tranche_reglee`), `reference`, `statut` (`brouillon` |
`emis` | `signe` | `annule`), `version` (1…), `surcharges` (JSON : personnalisations de l'acte, par section),
`contenu` (JSON figé à l'émission, `null` en brouillon), `emis_le`, `emis_par`, `signe_le`, `signataire_nom`,
`signature_client` (PNG en data-URL), `mode_signature` (`''` | `sur_place` | `papier` | `distance`), `preuve` (JSON :
empreinte SHA-256 du contenu figé, adresse IP, agent, utilisateur qui a recueilli), `statut_avant_annulation`,
`motif_annulation`, `created_by`, `created_at`, `updated_at`. Unicité `(company, chantier, type, variante)`.

`ModeleActe` — les textes par défaut de la société : `company`, `type`, `surcharges` (sections texte seulement),
`updated_by`, `updated_at` ; unicité `(company, type)`.

**Référence** = le préfixe de l'acte + la référence du chantier sans son préfixe : chantier `CHT-2026-11-0007` →
`CTR-2026-11-0007`, `LIV-…`, `REC-…`, `CLO-…`. Aucun compteur (règle maison : jamais `count()+1`), unique puisque la
référence du chantier l'est ; les deux variantes de livraison partagent `LIV-…` (une seule sera émise).

## 4. Le contenu : une seule source par valeur

`contenu` est le dictionnaire que l'écran modifie et que le PDF imprime, à l'identique (formes :
`contract_samples/acte_contractuel.json`). Brouillon : recalculé à chaque lecture ; émis : figé.

Fusion, dans cet ordre : **valeurs vivantes** (lues) → **textes par défaut** (`contrats/textes.py`) →
**modèle de la société** (`ModeleActe.surcharges`) → **personnalisations de l'acte** (`ActeContractuel.surcharges`).

| Section | Source vivante (lecture seule) | Modifiable dans l'acte |
|---|---|---|
| `societe` | `apps.ventes.utils.pdf._company_context` (profil société, logo) | `representant` seulement |
| `client` | client du chantier (`documents.builders._client_block` + CIN / ICE / RC) | non (se corrige sur la fiche) |
| `chantier`, `systeme` | chantier, nomenclature vendue (mêmes lignes que le PV existant, prestations exclues — D-APDF-4) | non |
| `prix` | `ventes.vente_facturation.plan_facturation(devis)` | **non** |
| `echeancier` (montants, %) | `plan_facturation(devis)['tranches']` | **non** — se corrige sur la vente (`PUT ventes/devis/<id>/echeancier/`) |
| `echeancier` (mots : quand, note) | défauts par clé de tranche | oui (`echeancier_textes`) |
| état des tranches, `paiement` | `ventes.utils.echeancier.solde_devis(devis)` | non |
| `garanties` | `ventes.utils.garanties.garanties_de_la_vente(devis)` + garantie d'installation (champ du chantier, sinon modèle société, sinon 24 mois : la promesse « Installation 2 ans » du devis) | oui |
| `articles`, `constats`, `quitus`, `conseils`, `entretien`, `conditions_particulieres` | `textes.py` | oui |
| `delais` | date limite = date du contrat + délai du modèle société | oui |
| `options` | particulier / entreprise, type d'installation | oui |

Règles fermes : aucun montant n'est modifiable dans un acte (un contrat qui dit 40 / 50 / 10 quand les factures
disent 30 / 60 / 10 est le défaut à ne pas créer) ; aucun prix d'achat, aucune marge, nulle part ; une valeur absente
s'imprime « à préciser » et lève un avertissement à l'écran, jamais un chiffre inventé.

**État d'une tranche** : `regle` si le payé cumulé couvre sa cible cumulée (au centime) ; `exigible` pour la première
tranche non réglée dont le moment est arrivé pour CET acte (contrat : la première ; livraison : jusqu'à la tranche de
livraison ; réception et clôture : toutes) ; `a_venir` sinon. Variante `tranche_reglee` : les tranches jusqu'à la
livraison comprise sont SUPPOSÉES réglées (c'est la version « le client a payé ses 90 % ») ; si l'ERP n'a pas
enregistré ces paiements, un avertissement le dit — l'acte reste émettable.

## 5. Cycle de vie

- **Création** : à `core.events.devis_accepted`, après le commit de l'acceptation (`transaction.on_commit`,
  jamais dans la transaction de signature, jamais bloquant), `services.preparer_dossier(chantier)` crée les cinq
  brouillons — idempotent. Un `GET …/contrats/` prépare aussi le dossier s'il manque (chantiers anciens ou créés à la
  main).
- **Dés-acceptation** (`devis_acceptation_annulee`) et **chantier annulé** (`chantier_annule`) : les actes non signés
  passent `annule` (jamais supprimés, `statut_avant_annulation` gardé) ; une ré-acceptation les rétablit. Un acte
  signé reste signé (la preuve ne se supprime jamais) et l'écran le signale.
- **Brouillon → émis** (`emettre`) : contenu et PDF figés, PDF déposé en GED (armoire « Chantiers », dossier = la
  référence du chantier, `source_type='documents.acte_<type>'`), partagé au portail client. Garde : le quitus
  (`cloture_garanties`) n'est émis que si la vente est réglée en totalité (409 `solde_non_regle`) — une attestation de
  paiement doit être vraie.
- **Émis → signé** : `signer` (signature tracée sur place, composant `SignaturePad` existant) ou `marquer-signe`
  (signature sur papier). Le PDF signé (trace, nom, date, empreinte) remplace le PDF émis en GED (nouvelle version).
  Preuve gardée : empreinte SHA-256 du contenu figé, IP, agent, utilisateur.
- **Émis → brouillon** (`rouvrir`) tant que l'acte n'est pas signé ; la ré-émission porte `version + 1`.
- **Variantes de livraison** : émettre l'une marque l'autre `ecarte` à l'affichage (calculé, pas un statut).
- **Prochaine action** (calculée) : contrat à envoyer et faire signer → livraison à faire signer → réception à faire
  signer → quitus à remettre (ou « solde non réglé »).

Droits : lecture comme les documents de chantier existants (`LectureChantiersOuVentes` + portée de la fiche) ;
écriture `IsResponsableOrAdmin` ; `modele` réservé au Directeur.

## 6. Contenu des quatre actes

Ordre de lecture (preuves : `docs/contrats/juridique.md` § Mise en page) : l'essentiel d'abord (quoi, combien,
quand), le détail ensuite, les clauses de risque à la fin, la signature en dernier.

1. **Contrat d'installation** — l'essentiel en quatre cartes, la frise de paiement, les parties, le matériel, les
   garanties, une quinzaine d'articles en français simple, les conditions particulières, les signatures.
2. **Procès-verbal de livraison** — le matériel livré, trois constats à cocher, les réserves, la frise avec l'état de
   chaque tranche, l'encadré « à régler à la livraison » (ou « réglé à ce jour »), garde et propriété du matériel.
3. **Procès-verbal de réception** — quatre constats (conforme, mis en service, expliqué, chantier propre), réception
   sans ou avec réserves, le solde exigible et la reconnaissance de la somme due, le début des garanties.
4. **Quitus et certificat de garantie** — attestation de paiement intégral avec l'historique des paiements, levée de
   la réserve de propriété, certificat de garantie (durée, date de fin, ce qui est couvert, comment faire une
   demande, la garantie légale rappelée), puis une page de conseils de consommation selon que l'installation a ou non
   une batterie.

## 7. Mise en page (`contrats/rendu/`)

Même famille que le devis (bleu nuit `#1A2B4A`, or `#F5A623`, DM Serif Display / DM Sans, logo société), mais une
mise en page de texte : pages qui s'enchaînent, titre d'article en marge, colonne de lecture d'une soixantaine de
signes, corps 10,2 à 10,5 pt aligné à gauche, pied répété (identité légale, référence, pagination, paraphes), parcours
des quatre actes sous l'en-tête, motif khatam dans l'en-tête et en puce des intertitres. Aucun texte en or sur blanc
(contraste) ; aucun état porté par la seule couleur (photocopie). Pagination de référence, données d'exemple :
contrat 6 pages, procès-verbaux 2 pages, clôture 4 pages.

Rendu : `rendu.html_de(contenu)` (fonction pure) puis `core.pdf.render_pdf` — jamais le moteur de devis (règle n° 4),
dont seules les polices et le traitement du logo sont importés.

## 8. Choix pris seul (réversibles, à confirmer par Reda)

| # | Choix | Pourquoi | Coût si faux |
|---|---|---|---|
| C1 | Les montants de l'échéancier ne se modifient que sur la vente ; l'acte n'en change que les mots | une seule vérité entre contrat et factures | un bouton à ajouter |
| C2 | Le quitus est refusé tant que la vente n'est pas réglée dans l'ERP | une attestation de paiement doit être vraie | saisir le paiement avant d'émettre |
| C3 | Référence dérivée de celle du chantier (`CTR-2026-11-0007`) | pas de compteur, lisible, les 4 actes se retrouvent | renommer un préfixe |
| C4 | Écriture réservée Responsable / Admin (comme la signature de livraison existante) | même règle que l'existant | ouvrir à un autre rôle |
| C5 | Garantie d'installation à 24 mois quand rien n'est saisi | c'est la promesse « Installation 2 ans » imprimée sur le devis | une valeur du modèle |
| C6 | Signature à distance par lien : seconde vague (la cérémonie GED existe : `ged.services.demander_signature`) | d'abord la signature sur place et papier | — |
| C7 | Version arabe : seconde vague | l'article 206 de la loi n° 31-08 demande une traduction arabe ; elle doit être relue par un arabophone | à faire avant un usage large |

## 9. Décisions de Reda pendant la construction

- **24/11/2026 — pas de droit de rétractation « signature à domicile » dans les actes.** Reda : le chapitre
  « démarchage » de la loi n° 31-08 vise la vente à domicile, pas une société que le client contacte de lui-même ; à
  oublier, ne pas l'intégrer. Retirés : l'option, l'article, l'annexe, le formulaire détachable. L'acompte est
  exigible à la signature. Le point reste, pour mémoire seulement, dans `juridique.md` § 4.
