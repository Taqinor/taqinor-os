# ADSENG34 — Boucle `ctwa_clid` complète : dossier de DÉCISION

> **Statut : GATED — décision fondateur (coût + architecture). RIEN N'EST CONSTRUIT.**
> Ce document est une **spec de décision**, pas un plan de build. Aucun champ,
> aucun webhook, aucun code n'est ajouté par cette tâche. Il documente ce que la
> boucle apporterait, ce qu'elle exige, ce qu'elle coûte, et le déclencheur qui
> rendrait la décision pertinente. Source : `docs/engine/research/dd-attribution.md`
> §2.4–2.5 (vérifié contre la doc primaire Meta, 16 juil. 2026).

## 1. Ce que la boucle apporterait

L'**attribution exacte clic → conversation** pour le canal WhatsApp :

- **Aller (clic → lead)** : à la **première** entrée d'une nouvelle conversation
  WhatsApp, capter `referral.ctwa_clid` (l'identifiant de clic Click-to-WhatsApp)
  **et** `referral.source_id` (= `ad_id`, la **vraie granularité par variante**),
  puis les stocker sur le `Lead` (`ctwa_clid` + `meta_ad_id`). Le bandit (ENG8) et
  la réconciliation (ENG31) gagnent alors, pour WhatsApp, la même qualité
  d'attribution par-ad que les Lead Ads — au lieu du tag manuel
  `canal='whatsapp_ctwa'` (une supposition humaine, jamais une attribution).
- **Retour (signature → Meta)** : renvoyer les événements qualifiés via la
  **Conversions API for Business Messaging** (`action_source='business_messaging'`,
  `messaging_channel='whatsapp'`, `user_data.ctwa_clid` — documenté « ne pas
  hacher », contrairement à email/téléphone). C'est la moitié « feedback » qui
  ferme la boucle d'optimisation.

C'est une capacité Meta **propre, documentée et pleinement supportée** — le
blocage est **opérationnel/coût**, pas technique.

## 2. La contrainte vérifiée : impossible avec `wa.me` aujourd'hui

**VÉRIFIÉ — zéro chemin `ctwa_clid` possible dans la configuration actuelle :**

- Le `ctwa_clid` est injecté par Meta dans un objet `referral` livré **uniquement**
  dans le payload webhook d'un message entrant reçu **via la WhatsApp Business
  Platform (Cloud API)** — ou un BSP bâti dessus (360dialog, Twilio, Sinch…).
- L'app **WhatsApp Business gratuite** n'a **aucune** surface webhook/API : il n'y
  a **rien** pour recevoir l'objet `referral`, même en principe.
- Un lien `wa.me/<numéro>?text=…` **ne porte aucun paramètre de click-id** visible
  côté appareil/app : l'identifiant n'existe que côté serveur, sur l'infra Meta,
  livré au propriétaire de l'abonnement Cloud API du numéro.

**Conséquence :** aujourd'hui, le **seul** signal CTWA possible est le tag manuel
`canal='whatsapp_ctwa'`. L'attribution réelle par-ad/par-clic WhatsApp est
**catégoriquement indisponible** sans adopter la Cloud API.

### 2.1 Palliatif intérimaire (process, PAS du code)
Les pubs CTWA supportent un **message pré-rempli « personnalisé » par ad**. En
posant une phrase distincte par campagne/créatif (ex. « Bonjour, offre Toit A »),
un agent peut **inférer manuellement** quelle pub a lancé un fil WhatsApp et
taguer `canal`/`utm_campaign` à la main. C'est de la discipline de process, pas de
l'attribution : ne jamais l'afficher dans la console avec le même niveau de
confiance qu'un vrai match `meta_ad_id`.

## 3. Ce que la boucle exige (changement d'architecture)

1. Enregistrer le numéro WhatsApp sur la **Cloud API** (directement Meta ou via BSP).
2. Monter un **récepteur webhook** (nouvel endpoint — `apps/crm/webhooks.py` est le
   foyer naturel, à l'image de `meta_lead_ads_webhook`).
3. Capter `referral.ctwa_clid` + `referral.source_id` au **premier message entrant**,
   les stocker sur `Lead`.
4. Émettre la **CAPI Business Messaging** au moment de la qualification.
5. **Renoncer** au workflow WhatsApp personnel/Business-App gratuit (le vrai coût
   caché : c'est un changement de flux de travail, pas seulement une facture).

> **Note de préparation, à NE PAS confondre avec « construire » :** un champ
> `ctwa_clid = models.CharField(max_length=500, blank=True, null=True)` sur
> `crm.Lead` est additif et inoffensif. Il peut être ajouté plus tard **par la
> tâche CRM propriétaire du modèle** — PAS ici (ADSENG34 ne touche aucun modèle).
> Ne jamais construire le récepteur webhook tant que la décision Cloud API n'est
> pas prise : une colonne nullable inutilisée est acceptable ; de la plomberie
> webhook pointant vers une infra inexistante ne l'est pas.

## 4. Coûts BSP connus (dossiers antérieurs)

La structure de coût (les **montants exacts en MAD restent à confirmer par le
fondateur** au moment de la décision — ne pas les figer ici) :

- **Tarif par conversation Meta** : facturé par catégorie (marketing / utility /
  service / authentication), par pays. Les conversations **initiées par
  l'utilisateur** (le cas CTWA : c'est le prospect qui écrit) tombent dans les
  catégories les moins chères, voire dans la fenêtre de service gratuite selon la
  politique en vigueur.
- **Frais de plateforme BSP** : soit un **abonnement mensuel forfaitaire** (modèle
  360dialog — pas de marge par message), soit une **marge par message** au-dessus
  du tarif Meta (modèle Twilio/Sinch). Pour un volume solaire (dizaines de
  conversations/semaine), le forfait mensuel est généralement le moins cher.
- **Coût d'intégration** : ponctuel (mise en place du webhook + vérification du
  numéro), interne.

Le poste dominant à ce volume n'est pas la facture Meta/BSP (faible) mais le
**changement de workflow** (perte de l'app WhatsApp gratuite).

## 5. Déclencheur de décision

Ouvrir la décision « adopter la WhatsApp Cloud API » devient pertinent quand **au
moins l'une** de ces conditions est atteinte :

- **Volume** : le canal WhatsApp génère **≥ 15–25 leads/semaine** — assez pour que
  l'attribution par-variante change les allocations du bandit (en-dessous, le MDE
  est trop large, l'attribution manuelle suffit).
- **Deuxième répondeur** : un **2ᵉ agent** répond sur WhatsApp — le tag manuel ne
  scale plus de façon cohérente entre plusieurs personnes, la capture automatique
  devient le seul moyen fiable.

Tant qu'aucune condition n'est remplie, la boucle est **superflue** : le tag
manuel + le message pré-rempli distinct par ad couvrent le besoin. La décision
reste **séparée** du reste de la colonne d'attribution (ADSENG31/32/33), qui
fonctionne pleinement **sans** elle.

## 6. Recommandation

Traiter « adopter la WhatsApp Cloud API » comme sa **propre décision gated**
(COST/DECISION), signature fondateur requise — **jamais** un bloqueur pour livrer
le reste du moteur. Ne rien construire tant que la décision n'est pas prise.
