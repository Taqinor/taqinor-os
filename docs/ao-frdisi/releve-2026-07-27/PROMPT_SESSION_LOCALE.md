# PROMPT À COLLER DANS LA NOUVELLE SESSION LOCALE (copier tout ce bloc)

Tu reprends le dossier AO FRDISI (solaire Mohammedia) exactement où la session
cloud du 27/07/2026 l'a laissé. Procède dans cet ordre :

1. `git fetch origin claude/brief-session-cloud-protocol-7573w9 && git checkout
   claude/brief-session-cloud-protocol-7573w9` puis LIS EN PREMIER
   `docs/ao-frdisi/releve-2026-07-27/05 - BRIEF_PASSATION_SESSION_SUIVANTE.md`
   (l'état complet : montants révisés, résultats du relevé, questions ouvertes).
   Tout le reste du travail cloud est dans `docs/ao-frdisi/releve-2026-07-27/` :
   vues de toiture définitives (3 bâtiments), bordereau Excel révisé, Word
   Accordia, note de synthèse, scripts Python régénérables, paquet
   ENVOI_ACCORDIA_MAJ.

2. Localise mon OneDrive local : dossier `TAQINOR/AO FRDISI - Solaire
   Mohammedia 2026` (cherche sous `~/OneDrive*` ou demande-moi le chemin).
   Tu y as un accès COMPLET en lecture/écriture — c'est l'avantage vs le cloud.

3. MISSION IMMÉDIATE — assembler le dossier tender final DANS OneDrive :
   a) Copier `ENVOI ACCORDIA - Offre complète` en `ENVOI ACCORDIA - FINAL 27-07` ;
   b) Y REMPLACER le bordereau par
      `docs/ao-frdisi/releve-2026-07-27/ENVOI_ACCORDIA_MAJ/04 - Bordereau des
      prix - REVISE 27-07.xlsx` (batteries 2 800 DH/kWh, câbles DC 60/45/45,
      TOTAL 4 349 400,00 HT / 5 219 280,00 TTC, clause de réserve quantités en
      pied — totaux déjà vérifiés) ;
   c) Y AJOUTER le Word `00 - A REMPLIR PAR ACCORDIA avant depot.docx` (même
      dossier repo) et supprimer l'ancien LISEZ-MOI txt ;
   d) OUVRIR la Simulation xlsx et corriger : feuille Rentabilité C7 =
      3 576 600 ; toute mention du TTC 5 413 680 → 5 219 280 ;
   e) VÉRIFIER la Lettre de soumission : si un montant y figure →
      5 219 280,00 DH TTC (« cinq millions deux cent dix-neuf mille deux cent
      quatre-vingts dirhams ») ;
   f) Créer dans le dossier AO un sous-dossier `updated` avec le contenu de
      `docs/ao-frdisi/releve-2026-07-27/updated/` (vues de toiture, note de
      synthèse, brief) ;
   g) Supprimer dans `07 - POUR DEMAIN` les 2 fichiers obsolètes
      `CALEPINAGE - Ecole (dossier).pdf` et `CALEPINAGE - Residence (dossier).pdf`
      (version 608 périmée — fermer Acrobat d'abord si verrouillés).

4. QUESTIONS OUVERTES à me poser si je ne les ai pas déjà tranchées (elles
   changent les vues) : arc — mes chaînes de cotes couvraient-elles chaque
   segment de muret à muret (sinon le développé ≈68 m remonte vers ≈90) ?
   école — profondeur réelle de la cage d'escalier (déduite ≈14,42) ?
   Les vues se régénèrent avec les scripts Python du dossier repo
   (matplotlib + numpy requis : `pip install matplotlib numpy openpyxl`).

5. RÈGLES : bleu = mesuré · orange = à confirmer · gris = plan/déduit ; ne
   JAMAIS afficher un « maximum posable » supérieur à l'engagement dans un
   document client ; la clause de réserve quantités doit rester dans le
   bordereau et la lettre ; CLAUDE.md du repo s'applique (modèles par tâche,
   Fable = passes finales uniquement).
