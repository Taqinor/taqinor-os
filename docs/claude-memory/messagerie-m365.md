# Messagerie taqinor.ma : Microsoft 365 depuis le 14/10/2026

**Fait durable (fondateur, 14/10/2026).** Les adresses `@taqinor.ma` ne sont plus sur l'hébergement
mutualisé ADK (cPanel, `mail.taqinor.ma` = 174.142.95.86, tombé injoignable ce jour-là) mais sur
Microsoft 365, tenant `AtlenciaX.onmicrosoft.com` (compte de facturation « Atlencia », MCA, GB).

- **Comptes** : `reda.kasri@taqinor.ma` (admin ; ancien identifiant `RedaKasri@AtlenciaX.onmicrosoft.com`)
  et `meryem.hida@taqinor.ma`, licence **Business Basic (sans Teams)**, annuelle, renouvellement
  13/10/2027. Boîtes partagées gratuites `contact@` et `stages@` (accès complet + envoi pour les deux).
- **Business Basic n'inclut PAS l'application « nouvel Outlook » Windows** (« Ce compte n'est pas pris
  en charge » — comportement officiel pour les SKU sans licence client Outlook). Décision fondateur :
  rester en Basic, utiliser Outlook web en fenêtre d'application (raccourci Bureau « Outlook TAQINOR »,
  Chrome `--app=https://outlook.office.com/mail/`). Téléphone : applications Outlook / Office mobiles
  incluses. Montée en gamme si besoin : Business Standard (sans Teams), bouton « Upgrade » du Marketplace.
- **DNS (Cloudflare)** : MX `taqinor-ma.mail.protection.outlook.com`, `autodiscover` CNAME
  `autodiscover.outlook.com`, SPF `v=spf1 include:spf.protection.outlook.com include:spf.brevo.com -all`
  (Brevo conservé : l'ERP envoie depuis `@taqinor.ma`). DKIM Microsoft non activé, DMARC `p=none`.
- **Guide utilisateur** : `docs/meryem/source/guide_messagerie_m365.html` → PDF `docs/meryem/Guide_messagerie_M365.pdf`, publié dans la GED (Documentation → « Guides — Responsables », `acces: responsable` du manifeste) à chaque déploiement.
- **Reste à faire** : migration IMAP des anciens mails ADK vers M365 dès que `mail.taqinor.ma:993`
  répond (`Test-NetConnection mail.taqinor.ma -Port 993`), puis résilier l'hébergement ADK en gardant
  l'enregistrement du domaine (`clients.adk-media.com`, +212 5 22 50 52 00).
- **Leçon facturation** : le renouvellement M365 de juillet 2026 a échoué (carte annulée) → abonnement
  supprimé ; le centre d'administration refusait toute nouvelle carte et le domaine jusqu'à l'ajout de la
  carte **via le portail Azure** (Cost Management + Billing → profil de facturation → Moyens de paiement).
  Pour tout problème de paiement M365, passer directement par là.
- **`taqinor.com` n'existe pas** (NXDOMAIN vérifié le 17/10/2026 chez Google DNS) : `contact@taqinor.com` était pourtant
  publié par le site (`apps/web/src/lib/nap.ts` → pied de page, page contact, JSON-LD ; `llms.txt`) et dans les replis du
  moteur PDF — remplacé partout par `contact@taqinor.ma` (PR du 17/10). Tout mail vers l'ancienne adresse rebondissait.
  Reste à aligner à la main : la fiche Google Business Profile (elle portait le `.com`).
