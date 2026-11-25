---
name: contrats-chantier-decisions
description: 24/11/2026 — dossier contractuel d'un chantier (quatre actes créés avec le chantier) : décisions de Reda (pas de rétractation à domicile, date limite 30 jours, pas de pénalité chiffrée, signataire nommé, version arabe dans la même vague), choix pris seul, où vit le travail
metadata:
  type: project
---

**Demande de Reda (24/11/2026, « go L5 »)** : l'ERP crée quatre contrats pour chaque lead signé, au moment où le
chantier est créé — (1) contrat de démarrage (paiements du devis final et garanties, modifiables), (2) matériel livré
au domicile avec la part à payer, en deux versions prêtes (reste à régler / le client a payé ses 90 %), (3) travaux
bien terminés, signé par le client (protection si le solde n'est pas payé), (4) contrat final au paiement complet
(garanties + conseils de consommation). Le meilleur contenu, et surtout la beauté.

**Décisions de Reda (24/11/2026)** — ne pas re-demander :
- **Pas de droit de rétractation « signature à domicile »** dans les actes : pour lui le chapitre démarchage de la loi
  n° 31-08 vise la vente à domicile, pas une société que le client contacte de lui-même ; « forget about it and dont
  integrate it ». L'acompte reste exigible à la signature. (L'article 45 dit « même à sa demande » : noté pour un
  juriste dans `docs/contrats/juridique.md` § 4, rien de plus.)
- **Date limite d'exécution imprimée : 30 jours après la date du contrat**, par défaut (choisi contre « 60 jours »
  recommandé ; la loi n° 31-08 art. 12-13 permet au client d'annuler si elle est dépassée de plus de 7 jours).
- **Retard de paiement : sans pénalité chiffrée** (mise en demeure, puis suspension, justice ou reprise du matériel).
- **Signataire : son nom et sa qualité**, saisis une fois dans le modèle de la société, imprimés « Représentée par … »
  sur les contrats — le devis reste sans nom de gérant (D-APDF-1 inchangée).
- **Version arabe dans la même vague** (choisi contre « seconde vague » recommandé) : chaque acte se rend en français
  et en arabe ; la traduction arabe accompagne l'acte français (loi n° 31-08, art. 206).
- **Logo : celui du devis, partout** (24/11/2026, « this should be the logo used everywhere, and the logo you just
  added should not be used anywhere ») : tout acte imprime le logo que le moteur de devis imprime (détouré, lettres
  blanches et soleil doré sur l'en-tête bleu nuit), lu par la porte `apps.ventes.selectors.logo_entete_html`. Jamais
  le fichier téléversé posé tel quel, jamais de pastille blanche autour — ni dans un nouveau document.
  Étendu le même jour à TOUS les autres documents PDF (« yes use the quote logo on all other documents too ») :
  factures, avoirs, bons, procès-verbaux, reçus, SAV, rapports — une pièce commune `templates/pdf/_logo.html`,
  alimentée par `apps.ventes.utils.pdf.logo_document_html` (rôle « couverture », variante claire) ; un test refuse
  tout gabarit qui imprimerait `logo_uri` lui-même.
  Reda le même soir, sur les exceptions restantes : « why there is still another logo, i told you, only one
  everywhere » → AUCUNE exception : l'ancien PDF de devis de secours passe par la pièce ; les documents du
  calepinage impriment le logo du devis du profil (le thème `TenantTheme` ne donne plus que les couleurs et un
  logo de repli) ; la marque des écrans de l'ERP (`TaqinorMark`), ses icônes et ses images de démarrage sont
  l'emblème officiel (8 rayons dorés, éclair bleu nuit `#022F53`). Les e-mails n'ont pas d'image de logo (nom en
  texte). Ne jamais réintroduire un autre dessin du soleil ni un logo propre à un module.
- **Textes retirés du contrat après sa lecture en production (24/11/2026)** — ne pas les remettre : la phrase
  « si deux lignes se contredisent… » (article 1) ; l'article « Démarches auprès du réseau électrique » ; « la société
  a la garde du chantier » pendant la pose ; et tout engagement de S'OCCUPER de la garantie (« we should not be
  obliged by this contract to take care of his warranty ») : interlocuteur unique, diagnostic, démarche auprès
  du fabricant, frais de transport, pièces détachées — dans le contrat comme dans le certificat. Les garanties
  restent citées (tableau, durées, garantie légale, exclusions). Détail : `docs/contrats/conception.md` § 9.
- **Bouton « Régénérer »** (24/11/2026) : Reda devait refaire un devis pour obtenir un contrat à jour. Un acte émis
  non signé se refait en un geste (`POST documents/actes/<id>/regenerer/`), tout ou rien ; jamais un acte signé.
- **Logo affiché par Google = l'emblème seul** (24/11/2026, « just keep the sun and the bolt ») : icônes du site
  (`apps/web/public/favicon.*`, `icon-*.png`, `apple-touch-icon.png`) et logo de la donnée structurée
  (`logo-embleme.png`) = soleil doré à huit rayons + éclair bleu nuit, géométrie de `Logo.astro`. `logo.png` reste
  le logo complet téléchargeable de la page « à propos ».

- **Icônes de l'application ERP : fond bleu nuit, jamais blanc** (24/11/2026 soir, « the only logo I had a problem
  with was the one with white background » ; « the blue background is ok ») : l'icône des notifications, de
  l'application installée, de l'onglet et d'Apple (`frontend/public/pwa-*.png`, `favicon.*`,
  `apple-touch-icon-180.png`) reste le soleil et l'éclair sur fond bleu nuit. « Un seul logo partout » visait le
  logo sur fond blanc ; régénérer ces icônes sur fond blanc ou transparent était l'inverse de la demande (fait
  puis annulé le même jour).

- **Durée de garantie : réglable depuis le certificat (25/11/2026, « Oui, garder »)** : Reda a tapé 36 mois sur
  le 4ᵉ acte (certificat), l'écran revenait à 24 parce que la clôture lit la durée du contrat. Décision : tant que
  le contrat est un brouillon, une durée ou une ligne de garantie enregistrée sur le certificat est portée au
  contrat ; contrat émis ou signé, lecture seule sur le certificat avec sa raison (rouvrir le contrat émis, jamais
  un signé). Ne pas revenir à « la durée ne se règle que sur le contrat ». Règle d'écran tirée du même défaut : un
  champ que le serveur reprend d'un autre acte ne s'affiche jamais comme modifiable (la case « Réserve de
  propriété » des procès-verbaux est grisée, « réglée sur le contrat »). Spécification : conception.md § 8 (C18).

- **Client société (Reda, 24/11 soir)** : « on ne montre le nom du client (le gérant ou le responsable) que pour
  signer, mais pour le nom du client il devient le nom de la société » + « l'ICE sur les 4 contrats ». Donc, pour
  une fiche client `entreprise` : « le Client » = la raison sociale (`Client.nom`, jamais prénom + nom) ; l'ICE
  figure sur les quatre actes (parties du contrat, cadre de signature des actes 1 à 3, quitus de l'acte 4), ou
  une ligne à remplir s'il manque ; la personne (`contact_nom`, `contact_fonction`) n'est imprimée qu'au cadre de
  signature (« Représentée par … »). Même soir : « I should be able to make a residential quote but for a company
  with ICE » → un lead qui porte une raison sociale fait passer son client particulier en entreprise
  (`synchroniser_identite_client`, jamais une fiche divergée ni un ICE différent sans « Mettre à jour la fiche
  client »). Un client entreprise reçoit le contrat « professionnel » (option `consommateur` à faux).

**Why :** Reda a des soldes impayés sur des chantiers posés (≈ 50 090 DH au 23/11) ; son avocat lui a dit de faire
signer la bonne exécution des travaux.

**How to apply :** la spécification est `docs/contrats/conception.md` (§ 8 choix pris seul et à confirmer, § 9
décisions de Reda), le droit lu et les dix points à faire trancher par un juriste dans `docs/contrats/juridique.md`,
l'état du chantier L5 dans `docs/contrats/ETAT.md`. Le code vit dans `apps/documents/contrats/` (jamais dans
`apps/contrats`, coquille parquée) et `frontend/src/pages/installations/contrats/`. Aucun montant ne se modifie dans
un acte : l'échéancier se corrige sur la vente. Le quitus est refusé tant que la vente n'est pas réglée dans l'ERP.
Les textes par défaut ne sont PAS un avis juridique ; l'arabe doit être relu par un arabophone avant un usage réel.

Related: [[apdf-decisions-fondateur]], [[strategie-v2-2311]], [[decisions-audit-0810]]
