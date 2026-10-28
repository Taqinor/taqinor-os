# RGEN — constats R1 (27/10/2026) hors de mes fichiers

Rendu réel : conteneur à part `rgen-django` (:8012, code de ma branche copié, sans montage) + vite :5173, société 156, login anon_admin.

## Pour la coordinatrice (DevisGenerator.jsx n'a pas de propriétaire cette nuit)
- **Arrivée `?lead=` muette quand la liste des leads est lente** : `DevisGenerator.jsx:1315` `if (!leads.length || !produits.length) return` attend la liste ; `GET /crm/leads/?page=1` = **23,2 s, 337 Ko** sur la pile locale (mesuré en APIClient, 581 leads) > délai axios 20 s ⇒ le lead de l'URL n'est jamais appliqué, aucun message. AGNR19 dit « relu par son id » mais la garde passe avant. Propriétaires : lenteur liste → crm (perf, APRF) ; garde → generateur.

## Pour CGN (`ApercuSimulation.jsx`)
- Paybacks au point décimal anglais à l'écran : `3.34 ans`, `0.4 ans`, `payback 5.36 ans` (l.154, 207, 282 rendent la valeur brute, sans `formatNumber`).
- Avant Auto-remplir, carte « AVEC BATTERIE ★ RECOMMANDÉ — ROI **0.4 ans** — COÛT **8 400 MAD TTC** » : retour calculé sur des lignes sans prix (panneaux qté 0). Chiffre absurde montré au vendeur.
- Jargon visible : « Onduleur (règle 80 %) », « 704 % du kWc », « Falaise tarifaire », « critère « meilleur_payback » », « Moteur horaire », « Remplissage batterie ». « Option batterie non livrable pour cette taille (catalogue). » répété sur 15 lignes.
- Message « Estimation locale (hors ligne) — en attente du moteur horaire serveur » quand rien n'est saisi : rien n'est en attente, il manque la facture.

## Pour RHOR (`etude_horaire_view.py`)
- Confirmé : les 400 de l'aperçu ne portent que des corps malformés (rien à nommer pour le vendeur) — pas de tâche RGEN là-dessus.

## Fait par RGEN (vague 1)
- RGEN3 : la taille demandée sur la fiche vaut pour les deux options à l'écran (avant : champ 23 panneaux, lignes 17, devis auto 23 — lead 2141) ; bandeau « Taille demandée sur la fiche du lead ».

## R2 (27/10 après-midi) — rendu réel lead 2141 / 2191
- Écran ≠ PDF « avec batterie » en création : 30 571 vs 30 585 MAD/an (aperçu sans devis = rendement 0,90 + capacité nominale ; PDF = fiche 98 % + utile). Contrat proposé à RHOR (`batteries: [{produit, quantite}]` dans le corps de l'aperçu) ; RGEN7 @after.
- PDF résidentiel (envoyé à RPDF) : « Retour en 5.0 ans » (point décimal) ; hypothèse « tarif 0,90 MAD/kWh saisi » contredit « barème réel » ; garantie onduleur « 5 à 10 ans » p.2 vs « 10 ans » p.3.
- Lead sans facture ni taille (2191) : devis auto refuse en clair (« renseignez la facture d'électricité d'hiver (ou la taille souhaitée en kWc) du lead ») mais l'écran dit « Estimation locale (hors ligne) — en attente du moteur horaire serveur » (CGN, ApercuSimulation.jsx:80) + « Aucune facture exploitable : … estimation déguisée en mesure » (RHOR, etude_horaire_view.py:613) — sans nommer le champ. À aligner sur la phrase du devis auto.
- `DevisGenerator.jsx` : bandeau « au-delà de 36 kWc → mode Industriel ou Commercial » contredit la décision du 23/10 (résidentiel jusqu'à 120 panneaux, signaler au-delà) : une villa à 25 000 MAD (62 kWc) est poussée vers le C&I. Pour la coordinatrice (DevisGenerator sans propriétaire).
- Bandeau « avec batterie indisponible » affiché en mode AGRICOLE (golden gestes agricole) → AGV prévenue.

## État RGEN (27/10 soir) — en attente du jeton (#10)
- Branche `claude/res-rgen`, PR #1103 (hors file, sans merge auto) : 12 commits locaux non poussés au-dessus du dernier push — RGEN5 (économie « avec » nette niveau 3), RGEN6 (`rendement_global` ignoré), RGEN7 (corps de l'aperçu : `batteries`), RGEN8 (raisons batterie en clair), RGEN9 (grand système > 120 panneaux), RGEN10 (prix kWh « estimation » = serveur), correctifs Fable.
- Conditions avant mon push : #1095 (RHOR6) mergée ; contrat RHOR9 `batteries` sur main (sinon RGEN7 reste sans effet mais inoffensif : clé ignorée par le serveur).
- Round sec : aucun nouvel écart dans mes fichiers (part diurne 60 % = serveur ; 50 % n'est qu'un repli de parse).
