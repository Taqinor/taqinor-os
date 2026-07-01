# TAQINOR — App mobile native (Capacitor)

Ce dossier empaquette la PWA existante (`../frontend`) en **application native
iOS et Android** grâce à [Capacitor](https://capacitorjs.com/). C'est un wrapper
**isolé** : il a son propre `package.json` et ses propres dépendances, qui ne
touchent **jamais** `frontend/package.json` ni `frontend/package-lock.json` (le
CI frontend fait `npm ci` sur Linux — ajouter des dépendances natives dans
`frontend/` casserait ce lock). Rien à installer dans `frontend/`.

- **appId** : `ma.taqinor.erp`
- **appName** : `TAQINOR`
- **webDir** : `www` (copie du build `../frontend/dist`)
- **Capacitor** : `8.4.1` (core, cli, ios, android — voir `package.json`)

L'app charge **le même code** que la PWA web (React/Vite). Toute la logique métier,
l'authentification par cookies, le CRM, les devis, le stock — identiques. Le
wrapper natif ajoute seulement l'enveloppe (icône sur l'écran d'accueil, plein
écran, présence dans les stores, accès device natif si on ajoute des plugins).

---

## Prérequis (poste de build)

- **Node.js 18+** et npm.
- **iOS** : un Mac avec **Xcode 15+** + CocoaPods (`sudo gem install cocoapods`).
  On ne peut PAS produire un build iOS depuis Windows/Linux — il faut un Mac.
- **Android** : **Android Studio** (Giraffe+) avec le SDK Android et un JDK 17.
  Fonctionne sous Windows, macOS ou Linux.

---

## Flux de build (à chaque nouvelle version)

Depuis la racine du repo :

```bash
# 1) Construire la PWA (produit frontend/dist)
cd frontend
npm run build

# 2) Installer les dépendances Capacitor de CE wrapper (une seule fois)
cd ../mobile
npm install

# 3) Copier le build web dans mobile/www
npm run build          # exécute scripts/copy-web.mjs : frontend/dist -> mobile/www

# 4) Ajouter les plateformes natives (une seule fois par plateforme)
npx cap add ios        # crée mobile/ios/    (Mac uniquement)
npx cap add android    # crée mobile/android/

# 5) Synchroniser le web + les plugins vers les projets natifs
npx cap sync

# 6) Ouvrir dans l'IDE natif pour builder / signer / publier
npx cap open ios       # ouvre Xcode
npx cap open android   # ouvre Android Studio
```

Pour une mise à jour ultérieure du contenu (après un nouveau `npm run build`
côté frontend), il suffit de refaire les étapes **1 → 3 → 5** puis rebuilder dans
l'IDE. Les scripts npm raccourcis disponibles ici : `build`, `sync`, `copy`,
`add:ios`, `add:android`, `open:ios`, `open:android`, `doctor`.

> `mobile/www`, `mobile/node_modules`, `mobile/ios` et `mobile/android` sont
> gitignorés : ce sont des artefacts régénérables, pas de la source.

---

## Accès device natif (optionnel)

La PWA utilise déjà les capacités web du navigateur (géolocalisation, appareil
photo via `<input type="file" capture>`, notifications web). Une fois empaquetée,
ces capacités **continuent de fonctionner** dans le webview.

Pour un accès **natif** plus poussé (caméra native, push APNs/FCM, biométrie…),
ajoute les plugins Capacitor officiels — **install trivial, aucune config requise
côté web** :

```bash
# Caméra native
npm install @capacitor/camera && npx cap sync

# Notifications push (nécessite aussi la config Firebase/APNs — voir plus bas)
npm install @capacitor/push-notifications && npx cap sync

# Géolocalisation native
npm install @capacitor/geolocation && npx cap sync
```

Ces plugins ne sont **volontairement pas** déclarés dans `package.json` : ils ne
sont pas nécessaires pour un premier build fonctionnel et chacun demande une
configuration de permissions (Info.plist / AndroidManifest) qui est un choix
produit. Ajoute-les au besoin.

---

## Ce qui reste À FAIRE par Reda (dépendance EXTERNE — bloquant store)

Le wrapper est **prêt à empaqueter**. La **publication sur les stores** exige des
comptes et des certificats de signature qui sont personnels/organisationnels et
ne peuvent pas être fournis par l'agent :

### Apple App Store (iOS)
1. **Compte Apple Developer Program** (99 USD/an) — s'inscrire sur
   developer.apple.com.
2. **Certificat de distribution** + **provisioning profile** (généré dans Xcode
   avec « Automatically manage signing », ou manuellement dans le portail Apple).
3. **App ID** enregistré : `ma.taqinor.erp`.
4. **Fiche App Store Connect** : nom, description, mots-clés, captures d'écran
   (par taille d'appareil), icône 1024×1024, politique de confidentialité (URL),
   catégorie, classification d'âge.
5. **Archive + upload** : dans Xcode, `Product > Archive` puis `Distribute App >
   App Store Connect`. Soumettre pour revue Apple.

### Google Play Store (Android)
1. **Compte Google Play Console** (frais unique de 25 USD).
2. **Keystore de signature** (`.jks`/`.keystore`) — **à générer et conserver
   précieusement** (le perdre empêche toute mise à jour). Configurer la signature
   d'app Play (Play App Signing recommandé).
3. **Fiche Play Store** : nom, description courte/longue, captures d'écran,
   icône 512×512, image de mise en avant, politique de confidentialité (URL),
   classification de contenu, formulaire de sécurité des données.
4. **Build release** : dans Android Studio, `Build > Generate Signed Bundle /
   APK > Android App Bundle (.aab)`, signer avec le keystore.
5. **Upload** de l'`.aab` dans la Play Console, remplir la fiche, publier.

> Résumé : l'agent livre le projet Capacitor prêt à builder ; **Reda fournit les
> comptes développeurs (Apple + Google), les certificats/keystores de signature,
> les fiches store et effectue le premier upload.** Ces éléments sont
> personnels/payants et externes au repo.

---

## Note isolation CI

Ce dossier n'ajoute **aucune** dépendance à `frontend/` ni au backend. Ses propres
dépendances Capacitor sont déclarées dans `mobile/package.json` mais **ne sont pas
installées** dans le repo (pas de `mobile/node_modules`, pas de `mobile/package-lock.json`
commité). Le CI frontend (`npm ci` sur `frontend/package-lock.json`) est donc
totalement inchangé.
