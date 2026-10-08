# Mémoire Claude partagée (taqinor-os)

Importée par CLAUDE.md : chargée par toute session Claude, sur tout poste et tout compte, après `git pull`.
Faits durables seulement (décisions fondateur, accords permanents, incidents ouverts) — une entrée = un fichier ci-dessous.
Ajouter/modifier ici via une PR, comme le reste du dépôt ; ne jamais y mettre de secret (clés, jetons, mots de passe).

- [Prod read access](prod-read-access.md) — standing approval to READ prod data (read-only shell queries) for investigations
- [COUV-HOR donut incident](couv-hor-donut-incident.md) — 28 % vs 37 % donut, bills÷1.20; #738 merged, 128 quotes repaired, open items + handoff doc path
- [C&I sizing: conso only](ci-autoquote-conso-only.md) — founder decision: C&I sweep uses national-grid conso, keeps old savings model
- [QA coherence auditor](qa-coherence-auditor.md) — the 4 QA checks on real data (nightly prod auditor, figure parity, property tests, anonymised prod snapshot) and how to run them
- [Re-confirm client-visible repairs](reconfirm-client-visible-repairs.md) — dry-run diff before prod repairs; re-ask if sent quotes' figures change
- [Memory shared via repo](memory-shared-via-repo.md) — durable taqinor-os facts also go to docs/claude-memory/ (PR), imported by CLAUDE.md
- [Set up missing tools](setup-missing-tools.md) — founder rule: install/configure missing prerequisites (docker, keys, deps) instead of reporting a blocker
- [Demo accounts on prod](demo-accounts-prod-incident.md) — CLOSED 30/09: seeded demo_admin/demo_resp deactivated, 9 demo documents neutralised; seed catalogue/clients/leads kept (real use)
- [Suivi commercial : table du parcours](suivi-commercial-table-parcours.md) — 30/09/2026 : UNE table (parcours_suivi.json) tient écran + garde de test + guide PDF GED ; verrou CAD44 précisé (tâches jamais verrouillées) ; planification avant enregistrement
- [Cockpit : contrôle du suivi](cockpit-controle-suivi.md) — 30/09/2026 : règles de mesure dans le contrat `controle_suivi.json` (retard en jours ouvrés, reports comptés, pas de note unique, même page pour tous) ; garde scénario + oracle indépendant
- [Typed kWh vs bills](kwh-declare-vs-factures.md) — founder rule 30/09: typed kWh contradicting the bills (>2×) blocks saving the quote until the lead is corrected
- [Devis : parcours modifiable (QJR5)](devis-parcours-modifiable-qjr5.md) — 30/09/2026 : envoyé corrigé sur place, accepté → Réviser V2 tout rôle, fusion au recalcul, notes client, historique + restauration ; groupe QJR500-670 de PLAN2
- [Décisions QJR5](qjr5-decisions-fondateur.md) — 30/09–01/10 : réponses du fondateur aux 11 questions QJR659-669, QJR612 (panneaux ajoutés pour batterie pleine), changements visibles client confirmés
- [Leçons de la construction QJR5](lecons-construction-qjr5.md) — 02/10/2026 : 7 causes prouvées de tâches cochées mais fausses (déployable ≠ vert, état non persisté, source parquée/mockée, appelants oubliés, tests affaiblis, jumeau oublié, pas de preuve en direct) → critères d'acceptance obligatoires
- [Propriété des fichiers](propriete-fichiers.md) — 02→04/10/2026 : une tâche va dans le plan du propriétaire de ses fichiers (unités de docs/audits/unites.yml) ; multi-propriétaires → docs/plans/PLAN_AUDIT_TRANSVERSE.md ; registre docs/ownership.yml, garde check_ownership.py
- [Audits par module](audits-modules.md) — remplacé le 02/10/2026 par le skill audit + docs/audits/{METHODE.md,unites.yml} (audit first/next/status, continue/loop audit, audit <mot>, vérifie <groupe>) ; mots v1 résolus par METHODE §D.4
- [Décisions devis agricole (D-AGR)](agricole-decisions-fondateur.md) — 02/10/2026 : moteur serveur agricole ouvert, document 3 pages, volume déclaré d'abord, visite avant devis si forage inconnu, économies déclarées sur 10 ans, FDA = règle sans montant, pompe neuve ou existante, kit minimum + options ; anciens devis oubliés (seuls les nouveaux comptent)
- [Décisions devis commercial & industriel (D-CIQ)](ci-decisions-fondateur.md) — 03/10/2026 (+ 08/10 : contrat sur le lead, HSE non bloquant, PR modélisé) : moteur serveur C&I ouvert (D10), autoconso HEURE PAR HEURE sur profil déclaré (ferme « 60 % vs 80 % »), taille = règle des 10 ans, HT si TVA récupérable, QXG6 a/c/d sourcés, visite avant devis si MT/inconnues, PDF commerce 3 p. / usine 25 ans, client entreprise + ICE à la signature, financement sur offre écrite, pas de tiers-investisseur, SR500 candidater d'abord ; anciens devis oubliés
- [Décisions calepinage (D-ACAL)](calepinage-decisions-fondateur.md) — 04/10/2026 : audit D3, Groupe ACAL (docs/plans/PLAN_AUDIT_*.md) : calepinage = unique conception, variante retenue = conception, V2 re-liée, deux empreintes, sol = pan, production client = celle du devis, brancher plutôt que retirer
- [Décisions YanBow (06/10)](yanbow-decisions-fondateur.md) — YanBow = Ltd UK + SARLAU marocaine à nommer ; SolarBow remplace Ancreto ; site public FR+EN, rendez-vous, sans prix (PLAN_YANBOW_WEB)
- [Décisions revue sécurité vague 3 (ASEC)](asec-decisions-fondateur.md) — 07/10/2026 : verrou de connexion par compte+IP ; compte verrouillé = même 401 que faux ; Commercial/Technicien gardent l'agenda ; Admin Ventes sans `users_gerer`
- [Décisions audit stock (ASTK)](astk-decisions-fondateur.md) — 06/10/2026 : écart d'inventaire = stock à la saisie ; seed_catalogue ne comble que les fiches vides (`--reappliquer-fiches` pour écraser) ; RAS-TVA sur toute la TVA de la facture (acompte compris)
- [Prod sans sauvegarde](prod-sans-sauvegarde.md) — INCIDENT OUVERT 08/10 : 105/105 BackupRun en échec (pg_dump absent de l'image django), dernier dump manuel 12/06 ; ADEP1 P0
- [Devis envoyés : nouveaux rendus seulement](devis-envoyes-nouveaux-rendus.md) — 08/10/2026 : les correctifs de chiffres du moteur (AMOT) ne touchent que les nouveaux rendus ; un devis envoyé garde ce que le client a reçu ; dry-run des écarts, aucune réparation
