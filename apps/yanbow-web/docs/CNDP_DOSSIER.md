# Dossier CNDP — préparation (YBW29)

> **Document de travail, AUCUN dépôt.** Rien n'est déposé à la CNDP par ce
> dépôt ni par un agent : la déclaration (et le choix de la voie) est une
> action de Reda, après avis du conseil (YBWM6, YBWM9). Ce dossier ne s'applique
> que si la SARLAU marocaine est désignée responsable du traitement du
> formulaire (YBWM8) — sinon voir `EU_REPRESENTATIVE.md` et le conseil.

Sources des données de ce dossier (aucune n'est inventée ici) :

- champs : le contrat partagé `backend/django_core/apps/crm/contract_samples/demande_rdv_site.json`
  (YBW50) — le registre du site `src/lib/rdv/champs.ts` (YBW53) n'existe pas
  encore ; quand il existera, ce tableau se relit contre lui ;
- destinataires et sous-traitants : `src/lib/subprocessors.ts` (YBW26) et
  `docs/DATA_FLOWS.md` ;
- identité du responsable : `src/lib/legal.ts` (YBW25) — tout `null` au
  07/10/2026.

## Traitement unique : « demandes de rendez-vous du site »

| Rubrique | Contenu |
| --- | --- |
| Responsable | à désigner (YBWM8) : `legal.ts > commun.responsableTraitement` = `null` |
| Finalité | répondre à la demande de rendez-vous envoyée par le visiteur (aucune prospection automatique, aucune cadence automatique) |
| Personnes concernées | dirigeants et salariés d'entreprises qui demandent un rendez-vous |
| Champs obligatoires | `nom` (≤ 120), `societe` (≤ 160), `email` (≤ 254), `produit` (solarbow / marketingbow / sur_mesure), `langue` (fr / en), `consentement` (vrai), `consentement_le` (horodatage), `idempotency_key` (technique, anti-doublon) |
| Champs facultatifs | `telephone` (≤ 30), `message` (≤ 2000), `page` (≤ 200), `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` (≤ 300) |
| Données jamais collectées | IP et agent du visiteur (non transmis à l'ERP), aucune donnée sensible (jamais de CIN) |
| Destinataires | la société ERP liée à la clé du site (utilisateurs « Directeur » / « Commercial responsable » / « Administrateur » notifiés) |
| Sous-traitants | Cloudflare (hébergement, Worker, journaux) ; serveur de l'ERP (Allemagne) ; WhatsApp (Meta) seulement si le visiteur clique sur le lien ; stockage KV de reprise : inexistant (`KV_REPRISE_DUREE_JOURS = null`) |
| Transferts hors du Maroc | Allemagne (serveur de l'ERP) ; réseau de Cloudflare ; Royaume-Uni si la société britannique est responsable — **voie de transfert à confirmer par le conseil** (formulaire F-118, art. 44 de la loi 09-08 selon la page CNDP citée ci-dessous) |
| Durée | 3 ans après le dernier contact, puis ANONYMISATION — seulement quand Reda arme `CRM_LEAD_RETENTION_ACTIF` (sinon aucune purge automatique : ne jamais écrire « supprimé ») |
| Sécurité | relais signé HMAC-SHA256 (horodatage, 300 s), société tirée de la clé, refus de tout `company*` dans le corps, aucune IP stockée, HTTPS, CSP stricte sans hôte tiers |

## Formulaires à demander / remplir (page CNDP lue le 07/10/2026)

Source : <https://www.cndp.ma/notifier-une-declaration-type-de-declaration-formulaires/>
et <https://www.cndp.ma/procedures-de-notification-process/>, lues le 2026-10-07.

- Déclaration simplifiée **F214** ou déclaration normale **F211** (préalable au
  traitement) ; récépissé délivré sous 24 h ; la CNDP peut, sous 8 jours, exiger
  une autorisation préalable si le traitement présente des dangers manifestes.
- Autorisation préalable : F-112 / F-113 (cas complexes).
- Transfert à l'étranger : **F-118**.
- Pièce jointe : document prouvant que le signataire engage la personne morale.

## Questions ouvertes (pour le conseil — YBWM9)

1. La délibération « gestion des clients » de la CNDP couvre-t-elle des
   **prospects** (demandes de rendez-vous) ou faut-il une déclaration normale ?
2. Quelle entité est responsable du traitement (Ltd britannique ou SARLAU) ? Si
   c'est la Ltd, la loi 09-08 s'applique-t-elle (traitement hors du Maroc,
   visiteurs marocains) ?
3. Le transfert vers le serveur en Allemagne et vers Cloudflare relève-t-il du
   F-118 ?

## Ce qui n'est PAS lu à la source par cette tâche

Les articles 2, 10, 19 et 43 de la loi 09-08 sont cités par le plan
(`docs/plans/PLAN_YANBOW_WEB.md`, § Faits établis) mais leur texte n'a pas été
relu ici (le texte intégral n'a pas pu être ouvert le 07/10/2026 :
<https://www.cndp.ma/loi-09-08/> est l'entrée à lire). → `LEGAL_REVIEW.md`.
