# Captures avant / après — refonte UI (P69)

> **Étape MANUELLE.** Les captures d'écran réelles ne peuvent pas être
> produites dans l'environnement de build sans tête (pas de navigateur, pas de
> serveur de dev). **Aucune image n'est fabriquée ni commitée par l'automate.**
> Ce fichier est le manifeste : il dit quoi capturer, comment, et sous quel nom
> de fichier. Voir le système de design dans [`tokens.md`](./tokens.md).

## Procédure de capture

1. **Lancer l'app en local :**
   ```bash
   cd frontend
   npm install      # si besoin
   npm run dev
   ```
2. **Se connecter** avec un compte de démo (données réalistes pour des captures
   parlantes).
3. **Capturer chaque écran à deux largeurs** (DevTools → device toolbar) :
   - **Desktop : 1440 px** de large.
   - **Mobile : 390 px** de large (iPhone-like).
   Capturer en **clair** ; refaire les écrans clés en **sombre** si l'on veut
   illustrer le thème (suffixe `-dark` optionnel).
4. **Enregistrer les PNG dans ce dossier** (`docs/ui-redesign/`) avec la
   convention de nommage ci-dessous.

## Convention de nommage

```
<ecran>[-mobile]-before.png     # état AVANT refonte
<ecran>[-mobile]-after.png      # état APRÈS (= actuel)
```

Exemples : `dashboard-after.png`, `dashboard-mobile-after.png`,
`crm-leads-before.png`, `devis-generator-after.png`.

- **« before »** = état **pré-refonte**. Récupérable depuis l'historique git si
  besoin (checkout d'un commit antérieur à la refonte, capture, retour sur la
  branche courante). Ne pas l'inventer.
- **« after »** = état **actuel** (post-refonte).

## Écrans clés à capturer

| Écran | Route | Notes de capture |
|-------|-------|------------------|
| Dashboard | `/dashboard` | KPIs (`Stat`), cartes, graphes |
| CRM — Leads (kanban + liste) | `/crm/leads` | capturer la **vue kanban** ET la **vue liste** (DataTable) |
| CRM — Clients | `/crm` | liste clients |
| Devis — générateur | `/ventes/devis/nouveau` | les 3 modes (Résidentiel / Industriel-Commercial / Agricole) |
| Devis — liste | `/ventes/devis` | DataTable + dialog PDF |
| Factures | `/ventes/factures` | statuts de paiement (`StatusPill`) |
| Chantiers | `/chantiers` | suivi des installations |
| SAV (tickets) | `/sav` | tickets + `StatusPill` |
| Stock | `/stock` | liste articles + mouvements |
| Paramètres | `/parametres` | onglets (`Tabs`), formulaires |
| Vitrine UI (`/ui`) | `/ui` | `UIShowcase` — style guide / tous les primitifs |

> Capturer la vitrine `/ui` en **clair et sombre** : elle montre l'ensemble des
> primitifs et sert de preuve visuelle du système de tokens.

## Suivi

- [ ] Captures « after » (1440 + 390) des 11 écrans ci-dessus.
- [ ] Captures « before » des écrans déjà migrés (depuis l'historique git).
- [ ] Vitrine `/ui` en clair + sombre.

Une fois les PNG déposés ici, lier les paires avant/après depuis cette page ou
depuis [`tokens.md`](./tokens.md).
