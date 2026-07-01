# App mobile native (Capacitor) — FG387

L'ERP TAQINOR peut être empaqueté en **application native iOS et Android** via
[Capacitor](https://capacitorjs.com/), qui embarque la PWA existante
(`frontend/`) dans un webview natif publiable sur l'App Store et le Play Store.

Le wrapper vit dans un dossier **isolé** à la racine : [`../mobile/`](../mobile/).
Il a son propre `package.json` (dépendances Capacitor `8.4.1`, non installées dans
le repo) et **ne touche jamais** `frontend/package.json` / `frontend/package-lock.json`
— le CI frontend reste inchangé.

## Voir le mode d'emploi complet

Tout est documenté dans **[`mobile/README.md`](../mobile/README.md)** :

- flux de build (`cd frontend && npm run build` → `cd mobile && npm install &&
  npm run build && npx cap add ios/android && npx cap sync`) ;
- accès device natif optionnel (caméra / push / géoloc via plugins Capacitor) ;
- **ce qui reste à la charge de Reda (dépendance EXTERNE)** : comptes Apple
  Developer + Google Play, certificats/keystores de signature, fiches store et
  premier upload — l'agent livre le build packagé prêt à publier, mais ces
  éléments personnels/payants ne peuvent pas être fournis automatiquement.

- **appId** : `ma.taqinor.erp` · **appName** : `TAQINOR` · **webDir** : `www`
  (copie de `frontend/dist`).
