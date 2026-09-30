# Cockpit CRM : le « Contrôle du suivi » et ses règles de mesure (30/09/2026)

**Décision fondateur (Reda, 30/09/2026)** : « work on the cockpit to make it follow those changes but also
to make reading the data and if the commercial did everything as she should. look on how does other
software show this and implement the best for my cockpit and test at the end. »

## Ce qui est établi (ne pas re-dériver)

- **Le contrat fait foi** : `backend/django_core/apps/crm/contract_samples/controle_suivi.json` (`pourquoi`
  et `notes`) porte les règles de mesure mot pour mot ; le serveur (`apps/crm/controle_suivi.py`,
  `GET crm/relance-etapes/controle/?jours=7|14|30&owner=`) et l'écran
  (`frontend/src/pages/crm/ControleSuiviPanel.jsx`, textes dans `controleSuiviTexte.js`) ne font que
  l'appliquer. Aucun chiffre n'est recalculé à l'écran.
- **Pas de note unique, pas de classement** (recherche Outreach/HubSpot/Close/Pipedrive/Gong/Zoho/noCRM/
  Odoo/NN-g) : un verdict (« Tout est à jour » / « À surveiller » / « Action requise »), des indicateurs
  séparés, et la LISTE des dossiers derrière chaque chiffre. La commerciale voit exactement ce que voit le
  responsable (transparence CKP3) — **même page, même ordre pour tous les rôles** : elle a le palier
  « responsable », un ordre par rôle ne la distingue pas du fondateur.
- **Le retard se compte en JOURS OUVRÉS** : une étape ouverte n'est « en retard » qu'à partir du premier
  jour ouvré qui suit son échéance ; week-ends, jours fériés de la société et absences déclarées de son
  responsable ne comptent pas (sinon : alerte rouge chaque lundi matin). Une étape close reste jugée sur
  son jour (à temps = close au plus tard le jour de l'échéance).
- **Un report ne cache plus un retard** : `RelanceEtape.due_initial_at` (échéance d'origine) et
  `nb_reports` (reports HUMAINS : « Reporter », « Mettre en veille », date saisie) ; les déplacements du
  MOTEUR (visite, ricochet, rappel demandé par le client) ne comptent pas — règle écrite une fois dans
  `services.deplacer_echeance_etape`.
- **Une étape close garde l'échéance de son traitement** (la planification d'une visite ne la redate plus).
- **Le délai de premier contact** se compte en heures d'horloge, jours non ouvrés retirés (pas « 24 heures
  ouvrées », qui valaient ~2,5 jours) ; la médiane reste en minutes ouvrées.
- **Seuils** (choisis par Claude, modifiables dans `controle_suivi.py`, servis dans `seuils`) : alerte à
  2 jours ouvrés de retard, tâche « en attente » à 2 jours ouvrés, étape « reportée plusieurs fois » à 2.
- **La file « À faire aujourd'hui »** : « Maintenant » = échéances du jour + retards + TÂCHES ouvertes
  quelle que soit leur date ; « Sauter » est refusé par le serveur sur une tâche.

## Comment le vérifier

- `apps/crm/tests_cockpit_scenario.py` + `apps/crm/cockpit_oracle_outils.py` : trois semaines de dossiers
  jouées par l'API réelle puis confrontées à un ORACLE indépendant (les règles du contrat recalculées sur
  les lignes de la base). La CI le joue à chaque merge. Un écart = l'un des deux s'écarte du contrat.
- Toute règle nouvelle se pose d'abord dans le contrat, puis dans le serveur ET dans l'oracle.

Pourquoi ici : ces règles décident de ce que le fondateur lit sur le travail de la commerciale ; les
changer sans le savoir fausserait le jugement porté sur une personne.
