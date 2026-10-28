# Pile locale `erp-agentique` — note du gardien (session CORC)

Mise à jour : 27/10/2026, après-midi — base de dev revenue de sa récupération post-crash (fsync ~40 min, ne pas la
redémarrer pendant ce temps) et MIGRÉE au niveau de `main` (crm 0141_equipecommerciale_recoit_leads, ventes 0142_regles_calcul_niveau_2710).

Mise à jour précédente : 27/10/2026, nuit.

- Le stack tourne et monte le checkout PRINCIPAL (`C:\dev\taqinor-os`, sur `main` e0fe749cc). Base de dev à jour avec `origin/main`
  (crm 0140, ventes 0141). **Ne lancez pas `migrate` vous-mêmes** : CORC le fait après chaque merge qui apporte une migration
  (#1074 apporte `crm 0141_categories_commerce_talon`).
- **Instantané anonymisé de la prod chargé** : société `taqinor-anon` (id **156**), login `anon_admin` (mot de passe dans
  `authentication/management/commands/qa_import_anonymise.py`, DEV seulement). 581 leads, 421 devis, catalogue C&I (38 articles C&I chiffrés).
- Les forfaits de prestations C&I (`CompanyProfile.forfaits_ci`, prix du fondateur du 26/10) ne voyagent PAS dans l'instantané
  (absents de la liste blanche `PRICING_PROFILE_FIELDS`) : je les ai recopiés à la main dans `taqinor-anon`. Constat routé au plan.
- L'instantané n'emporte **aucune fiche technique** (`stock.FicheTechnique` : 0 → tout devis C&I refusé « Pmax »). J'ai recopié les
  82 fiches catalogue de prod (lecture seule) dans `taqinor-anon`, rattachées par nom d'article. Constat routé au propriétaire de
  `authentication/anonymise.py` (securite).
- **Le stack principal (`django_core-1`) monte le checkout PRINCIPAL**, pas vos worktrees : pour rendre depuis votre branche, utilisez
  `docker compose -p erp-agentique run --rm --no-deps -T django_core python manage.py shell -c "exec(open('_mon_script.py').read())" < /dev/null`
  lancé depuis VOTRE worktree, script posé dans `backend/django_core/` (exclu de git). **Ne passez pas le script par l'entrée standard
  (`shell < script.py`) : sous Git Bash le conteneur reste bloqué sans rien lire** (mesuré 3 fois cette nuit).
- **Leads de démo C&I** (société 156, noms « Démo — … » sans « C&I » : le nom du lead est imprimé au PDF) : 2227 Boulangerie 6 000 kWh/mois 7/7 6-22 h · 2228 Bureaux 5 000 kWh 5/7 8-18 h ·
  2229 Hôtel 15 000 kWh 7/7 24 h · 2230 Supermarché 20 000 kWh 7/7 8-22 h · 2231 Usine textile MT 60 000 kWh 6/7 7-19 h.
  Tous BT patenté triphasé bac acier Casablanca (sauf l'usine : MT, Tarif Général). Le lead **2195** est la copie anonymisée
  d'un vrai lead commercial (10 000 kWh, 3 brouillons — probablement le 1637 de prod).
- Rendre un PDF depuis votre branche sans écrire en base : faites tout dans `with transaction.atomic(): … transaction.set_rollback(True)`
  (exemple : script `r1_probe2.py` de CORC, dans ce dossier si vous en avez besoin — demandez).
- Lancer `manage.py shell` dans un conteneur prend ~60 s au démarrage (chargement des apps) : prévoir le délai.
