# Dossier contractuel — état du chantier L5 (à lire EN PREMIER pour reprendre)

Dernière écriture : 24/11/2026 par la session du poste fixe · branche `claude/erp-lead-contracts-e2fdab`.
**Prochaine action unique** : voir « Déroulé » — la dernière ligne non cochée.

## Demande et cadre
- Demande de Reda, mot pour mot (24/11/2026) : « i want you make ERP create 4 contract for each lead signed was we
  create the chantier, and those 4 contrat will be 1 : starting contract to send first, and contains the payments
  details that are in devis final and that can be changed, and of course contains a mention of our warranties, that
  also we can change. the second contract is the one of materiel delivered, to home, showing the part that need to be
  payed at this stage, and have 2 versions ready one with the remaining and the other that suppose the client payed
  his full 90%. the third is work complete properly that the client should sign after i finish the work, and that my
  lawyer told me i should have to protect myself if they dont pay at the end. and finall the finall contract when i
  get fully payed and that mentions our warenties and also advices on how they should change their consumption
  behaviour. i want you to go l5 in this and produce the best conract in terms of content and specially pretiness. »
- Niveau L5 (nommé par Reda) · régime **MIXTE** lu sur `origin/main@854d2adfe` (promesses servies 1,5 / 6 :
  `docs/contrats/conception.md` § 1).
- Coût : quota hebdomadaire lu à 82 % au départ (Fable 74 %), remise à zéro le 28/11 ; formule L4
  `k = min(3, floor((90 − 82 − 10) / 21)) = 0` → **cette session = tour 0 + construction + vérification finale** ; les
  tours de relecteurs commencent après le 28/11. Mesuré : tour 0 (4 éclaireurs + conception + maquettes réelles) =
  2 points « tous modèles », 4 points Fable.
- Poste mesuré : 8 cœurs, 42 Go de disque libre, pile `erp-agentique` en marche (non touchée), WebKit installé
  (`ms-playwright/webkit-2311`, `-2388`) → 2 lanes d'écriture au plus, 1 agent à navigateur.

## Contrat de sortie (écrit avant tout relecteur ; un seuil se resserre, ne se relâche jamais)
Périmètre fermé : les quatre actes (PDF), l'onglet « Contrats » de la fiche chantier, l'éditeur d'un acte, la
signature sur place. Hors périmètre signalé : signature par lien, version arabe, page publique, fiche lead.
Références nommées : le devis premium (`/proposal`, même famille visuelle), l'ancien procès-verbal de réception
(`document_pv_reception.html`, pour les paires avant / après), les règles de `juridique.md` § Mise en page.

| id | Critère | Seuil | Mesure |
|---|---|---|---|
| K1 | constats S1-S2 ouverts | 0 | registre des tours |
| K2 | tout montant imprimé = celui de la vente (`plan_facturation`, `solde_devis`) | au centime, 4 actes × 2 variantes | test serveur |
| K3 | pagination sur les données de référence | contrat ≤ 7 p., PV ≤ 2 p., clôture ≤ 4 p. | test serveur (rendu réel) |
| K4 | prix d'achat, marge | 0 occurrence dans le contenu et le texte des PDF | test serveur |
| K5 | parcours : acceptation → 5 brouillons → modifier → émettre → signer → PDF signé en GED ; dés-acceptation → annulés ; ré-acceptation → rétablis | 100 % ; L5 : 3 essais verts | tests serveur + spec e2e |
| K6 | envoyer le premier contrat depuis la fiche chantier | ≤ 4 gestes | relecteur |
| K7 | beauté par paires (ancien PV ↔ nouveau ; devis ↔ contrat) | ≥ 4 paires sur 5 préférées ou à égalité, 2 relecteurs aveugles | tours L5 |
| K8 | contraste du texte ; lisibilité en noir et blanc | ≥ 4,5:1 ; aucun état porté par la seule couleur | mesure sur le rendu en niveaux de gris |
| K9 | toute référence de loi citée dans `textes.py` figure dans `juridique.md` § 2 au niveau P | 100 % | test (grep) |
| K10 | les quatre documents existants | fichiers intacts, tests verts | `git diff` de la liste « à ne pas changer » |
| K11 | critique adverse du diff serveur | 0 bloquant (isolation société, perte de données, argent) | avant chaque merge |

## Déroulé
- [x] Tour 0 — éclaireurs (flux chantier et paiements, moteur PDF et écrans, droit marocain, mise en page de
      contrats), conception, contrat d'API, moteur de rendu et textes par défaut, PDF réels tirés et regardés
      (contrat 6 p., PV 2 p., clôture 4 p.). Décision de Reda en cours de route : pas de rétractation à domicile.
- [ ] Construction — lane serveur (modèles, contenu, services, récepteurs, API, tests) et lane écran (onglet,
      éditeur, signature), pliées sur cette branche.
- [ ] Vérification finale — un rejeu sur l'écran réel (pile privée), une critique adverse du diff serveur, puis le
      premier merge.
- [ ] Tours de relecteurs (après le 28/11) — fonction / simplicité / beauté × téléphone / bureau, K1 à K11.
- [ ] Seconde vague — signature par lien (cérémonie GED existante), version arabe, raccourci depuis la fiche lead.
- [ ] Étage « vraie vie » — Reda : deploy, un vrai chantier, relecture d'un juriste (`juridique.md` § 4).

## Décisions posées à Reda (24/11) — réponses recopiées ici puis dans `docs/claude-memory/`
Voir `conception.md` § 8 pour les choix pris seul et § 9 pour les décisions de Reda (24/11 : pas de rétractation
à domicile). Questions posées : date limite d'exécution par défaut, retard de paiement, version arabe.

## Où sont les choses
- Spécification : `docs/contrats/conception.md` · droit : `docs/contrats/juridique.md` · contrat d'API :
  `backend/django_core/apps/documents/contract_samples/{dossier_contractuel,acte_contractuel}.json`.
- Tirage des PDF d'exemple (sans base, conteneur jetable, hors réseau) : scripts du tour 0 dans le scratchpad de la
  session — à promouvoir en commande `manage.py` par la lane serveur (`apercu_actes`).
