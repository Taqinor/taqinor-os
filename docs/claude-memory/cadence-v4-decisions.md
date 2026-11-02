---
name: cadence-v4-decisions
description: 01-02/11/2026 — douze décisions fondateur sur le suivi des leads (cadence v4) : protocole 5 appels + 3 WhatsApp sur 7 j, réveils selon l'historique, après-devis à J28 + validité 30 j découplée, champs de parcage, accusé API utilitaire, balayages week-end, file partagée, archive Odoo + pilote 50 appels, réparation dry-run, chemins par segment, messages K6 sous conditions
metadata:
  type: project
---

Conception « Lead handling v4 » (`docs/crm/cadence-v4-design-2026-11-01.md`, groupe CADV, décisions `D-CADV-1..12` dans `docs/audits/decisions.yml`). Reda a tranché les onze le 01/11/2026 (et la douzième le 02/11) par quatre questions interactives groupées, toutes à l'option recommandée (ne jamais re-demander) :

- **D-CADV-1** protocole contact v4 : 5 appels + 3 WhatsApp sur 7 jours, fenêtres 10-14 h / 16-18 h, plus de barreau dimanche ni d'heure 17:30-18:30 par défaut (rouvre « ni nombre ni ordre ni J+N » du 21/09 et CAD25 : cette conception est la mesure CAD87 demandée).
- **D-CADV-2** réveils selon l'historique : aucun barreau individuel pour un lead jamais joint ni chiffré (157 messages → 0 conversation), appel humain J30 + message J60 pour un lead joint ou chiffré, petit pilote d'appel sur les jamais-joints à facture ≥ 2 000 MAD (rouvre CAD74 Q20 en partie).
- **D-CADV-3** après-devis v4 (J1 WA, J2 appel, J3 conditionnel, J7 appel, J10 contenu, J14 appel, J28 appel, J60, J90) ; validité 30 jours depuis l'envoi, DÉCOUPLÉE du dernier barreau (VALID1 du 07/09 la liait) ; J28 = point de prolongation car un devis « expiré » ne se prolonge pas, il se révise (rouvre CAD57, VALID1, « touche J14-J30 » et « troisième vague »).
- **D-CADV-4** modèle de parcage en CHAMPS (`parc_etat` standby/nurture/archive, `parc_raison`, `parc_jusqu_au`), contrat d'abord, jamais une étape nouvelle (STAGES.py) ; invariants nocturnes.
- **D-CADV-5** accusé de réception automatique hors heures via la WhatsApp Business Platform, gabarit UTILITAIRE seulement (≈ 2 $/mois), après la case d'opt-in nommant WhatsApp et téléphone sur le formulaire Meta ; test click-to-WhatsApp optionnel (rouvre RELANCE-WA / D-WHATSAPP pour ce seul message).
- **D-CADV-6** deux balayages WhatsApp-first de 60 min le week-end (sam. 10:00, dim. 17:00), un week-end sur deux, compensés.
- **D-CADV-7** file partagée « À prendre » avec un commercial de permanence pour le résidentiel, propriété après le premier contact, échelle T+5/T+15/T+30 ; les leads C&I gardent le propriétaire pro nommé (D-CIQ-20 intact) ; les leads de Reda entrent dans la file ; Asmaa à ≥ 0,8 siège sur le même cockpit.
- **D-CADV-8** archive Odoo : étiquette `archive_odoo` sur les 423 contacts froids/perdus dans Odoo (étape Odoo conservée), pilote de 50 appels humains sur les 96 dossiers avancés dans Odoo ; aucune campagne WhatsApp sur la liste Odoo.
- **D-CADV-9** réparation unique : les 125 leads rebondis par l'alignement Odoo reviennent en Froid avec raison, les perdus/archivés sortent des comptages vivants, ~160 réveils aveugles annulés — dry-run, liste d'ids validée par Reda, puis `--apply` (règle `reconfirm-client-visible-repairs`).
- **D-CADV-10** chemins par segment : parcours C&I (pièces → devis, second contact, veille trimestrielle, jamais Froid à J14), agricole en veille aux dates du client (AGR512 : aucune saison inventée), via chaînes moteur et règles de veille, pas de second gabarit (rouvre CAD52 et B2B7 ; CAD124 reste fermée).
- **D-CADV-11** un WhatsApp 1:1 tapé à la main aux 155 leads Meta mai-août jamais joints (origine de la demande citée, ligne STOP, 20-25/jour), SEULEMENT après le récépissé F211 (fichier de prospection déclaré à la CNDP) et la lecture du disclaimer du formulaire Meta ; sinon appels seuls.
- **D-CADV-12** (02/11/2026) un lead déjà parqué en Froid qui renvoie le formulaire Meta est ROUVERT chez son propriétaire (une seule fiche) ; D-CRX1 du 02/09 (« un contact connu crée toujours un nouveau lead ») reste vraie pour les leads vivants, signés et archivés (CADV101).

**Why:** mesures prod du 01/11 (180 leads depuis le 06/09 : 94 % des premiers contacts de Meryem dans les 7 jours ; touches 5-11 : 1 rappel sur 25 ; appels 27-29 % vs WhatsApp 2-3 % ; 178 réveils exécutés en WhatsApp → 1 conversation ; capacité ≈ 124 touches/semaine pour ≈ 257 demandées) ; cadre légal (loi 09-08 art. 10, fiche CNDP, loi 31-08 art. 23-24/31/51, politique WhatsApp) relu par un vérificateur indépendant.
**How to apply:** les tâches CADV (vague 1 réparation/garde/mesure ; vague 2 cadences + parcage ; vague 3 intégrations) dans les plans propriétaires ; la vague 1 ne dépend que de D-CADV-9. Rien n'est construit au 01/11 ; aucune écriture prod. Voir aussi `prod-read-access.md` pour les sondes.
