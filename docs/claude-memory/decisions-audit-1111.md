# Décisions audits (11/11/2026) — 33 réponses du fondateur

Reda a répondu le 11/11/2026 (après-midi, questions interactives) aux 33 décisions ouvertes des audits PF4 à PF8 et du
journal des problèmes. Toutes suivent l'option recommandée. Le détail fait foi dans `docs/audits/decisions.yml`.

**Droits (D-ADRG)** — réglages de société écrits depuis un module : droit « Modifier » des paramètres (5) ; recette de mise
en service : droits des chantiers (3) ; bouton « Exporter » CSV : suit la case « Exporter » (4) ; règle d'équipe du 28/10
inscrite, avec en plus un droit d'écriture du CRM (6) ; verrou d'un document GED : « Gérer » (7) ; droits d'accès, quotas,
tampon GED : « Gouvernance » (8) ; logistique logée dans les chantiers : « Modifier » du stock (10) ; clôture d'un comptage :
administrateur, comme côté stock (11) ; restauration depuis la corbeille : il faut aussi le droit du module (12) ; registres
RGPD : droit de traiter les demandes RGPD (13) ; écrire un rôle : « Gérer les utilisateurs » (14). Restent au droit de
vente : baisser le prix d'une vente signée (1), mettre un client en relance manuelle (9). Supprimer un élément rattaché à
un lead = « Modifier » du CRM (2).

**Lecture (D-ALEC)** — tarif de transport, frais de livraison estimés, économie de regroupement, caution : montants d'achat,
masqués sans « voir les prix d'achat » (1, 5) ; tableaux de bord et calepinages : portée du rôle (2, 4) ; journal des
réglages : droit « Journal d'activité » (3).

**Accès publics (D-APUB)** — une demande de rappel depuis le lien du devis NE lève PLUS seule l'opposition : le commercial
la lève après l'appel, à son nom (1 — remplace sur ce point D-ACRM-5) ; chat public fermé par défaut (2) ; API publique
ouverte après correctifs (3) ; lien du compte-rendu d'intervention : 90 jours + bouton « Couper le lien » (4) ; le site
public n'appelle plus l'ERP avec la session de l'employé (5).

**Tests (D-ATST)** — un code de droit inconnu n'accorde aucun palier (1) ; les trois tests navigateur de la page du devis
tournent, site servi dans le run de bout en bout (2).

**Messages (D-AMSG)** — relances de facture, rappels, relevés : même fenêtre que les messages commerciaux, à partir de
8 h 30, jours ouvrés (1) ; un STOP s'étend à toutes les fiches vivantes aux mêmes coordonnées (2) ; rien vers Meta pour une
personne opposée (3) ; lever « ne plus contacter » hors demande du client : responsable ou administrateur, motif
obligatoire (4) ; les 4 factures aux niveaux de relance consommés sans envoi repartent au niveau 1, APRÈS une liste montrée
au fondateur (5) ; coordonnées du jeu de démonstration resté en production neutralisées, APRÈS une liste montrée au
fondateur, sauf celles qu'il confirme (6).

**Journal des problèmes (D-JPB-6)** — pas de point de collecte public hors session.

**How to apply:** ne jamais re-poser ces questions ; les deux réparations de données (D-AMSG-5, D-AMSG-6) passent par une
commande en `--dry-run` dont la liste est montrée à Reda avant toute écriture (règle « re-confirmer les réparations »).
