# Spec 8 — Langage visuel de Tâches (décisions rendues)

Preuve : `docs/taches/maquettes/taches.css` + 11 planches (`composants.html`, `composants-1…10.html`), rendues en
iPhone 390 et bureau 1440, clair et sombre (`maquettes/captures/`, 44 PNG), 4 tours de rendu. Contrastes mesurés par
script sur les couleurs CALCULÉES par Chromium (fond composité à travers les ancêtres), pas sur les valeurs écrites.

## 1. Typographie
| Rôle | Police | Graisse | iPhone | Bureau |
|---|---|---|---|---|
| Titre de page (le seul) | Archivo | 700, −0,02 em | 28 px / 1,15 | 28 px |
| Date au-dessus du titre | Hanken | 500, `--muted-foreground` | 14 px | 14 px |
| Section (Essentiel, Ce soir…) | Hanken | 650 | 17 px | 16 px |
| Titre de tâche | Hanken | 400 (2 lignes max, puis coupé) | 17 / 23 px | 16 / 22 px |
| Méta | Hanken | 400, `--muted-foreground` | 14 / 20 px | 13 / 18 px |
| Heures, compteurs | Hanken | 600, `tabular-nums` | 13 px | 12 px |
Aucun texte sous 12 px. Mesuré : les chiffres de Hanken sont tabulaires PAR DÉFAUT (« 1111 » = « 0000 » = 89,6 px
à 40 px, avec ou sans `tnum`) ; Archivo est proportionnelle (83,4 / 91,7 px) et devient tabulaire avec `tnum` —
donc jamais d'Archivo pour une heure. Sora : chargée par l'ERP, non utilisée ici.

## 2. Ligne de tâche, rayons, élévations
- Ligne : 52 px mini (bureau 44), 65 px avec méta ; gouttière 16 px (bureau 24) ; case ronde 22 px (trait 1,75 px)
  centrée dans une cible de 44 px, alignée sur la PREMIÈRE ligne du titre ; colonne de fin = heure, ★ ou drapeau.
- Aucun trait entre lignes, aucune ombre ; survol = `--muted` à 70 % ; bureau : survol arrondi 10 px, inset 8 px.
- Une section sans titre suit Essentiel (le titre « Aujourd'hui » répétait le titre de page) ; « Ce soir »,
  « Proposé pour aujourd'hui », « Faites 3 ⌄ » (replié) gardent le leur.
- Rayons : bloc d'agenda 8 · champ, bandeau « Pas à jour » 12 · bouton 12 (`--radius` + 2) · carte, bandeau, tuile 16
  (tuile 14) · feuille 20 · puce 999.
- Élévations : liste à plat sur `--card` ; panneaux (bandeau, carte de rythme, tuiles) = `--muted`, sans bordure ;
  feuille et popover = `--popover` + `--shadow-lg` ; bouton flottant `--shadow-md` ; toast inversé `--shadow-lg`.

## 3. Palette de projet (OKLCH, L et C fixes, seule la teinte change)
Teintes : terre 55 · ambre 85 · olive 115 · vert 150 · menthe 180 · ciel 215 · bleu 250 · indigo 285 · prune 320 ·
rose 355 (le rouge 25 est exclu, réservé).
| Rôle | Clair | Sombre | Contraste calculé (10 teintes, toutes dans sRGB) |
|---|---|---|---|
| Point, filet, camembert | `oklch(61% .105 H)` | `oklch(72% .115 H)` | clair 3,60–4,01 sur blanc ; sombre 7,02–7,81 sur `--card` |
| Fond de bloc | `oklch(95.5% .02 H)` | `oklch(28% .045 H)` | — |
| Texte sur bloc | `oklch(46% .08 H)` | `oklch(83% .085 H)` | clair 6,03–6,49 ; sombre 8,49–8,79 |
Rendu : point le plus faible 3,22:1 (ambre sur fond teinté de sélection), toujours ≥ 3:1. Le point est TOUJOURS suivi
du nom du projet. La couleur vit sur un point de 8 px, le camembert du projet, le filet de 3 px d'un bloc d'agenda,
le jeton `#projet` de la saisie — jamais sur une ligne entière.

## 4. Usage de la couleur
- **Rouge** (`--destructive`) : « échéance aujourd'hui » ou dépassée, et les actions destructives. Rien d'autre
  (« échéance lun. 23 » proche = `--foreground` 500, sans teinte).
- **Azur** (`--info`, accent de l'app) : heure courante, jour courant, sélection, onglet actif, estampille « → lun. 23 »,
  Reporter, jetons reconnus, liens d'action, pastille d'À trier.
- **Vert** (`--success`) : la case faite et l'anneau. **Or** : le bouton plein (laiton) et l'étoile Essentielle
  (remplissage `--primary`, contour `--primary-text` ≥ 3:1 sur blanc).
- Priorité haute = drapeau lucide en `--foreground`, jamais une teinte. En attente = case en pointillé + texte.
- Contraste du texte, 1 204 éléments × 4 vues : 0 sous le seuil. Plus faibles : clair 4,92:1 (méta sur ligne
  sélectionnée), sombre 5,56:1 (« échéance aujourd'hui »). Repères graphiques : case 5,81 (clair) / 6,84 (sombre).
- Cibles : 0 sous 44 px (puces 34 px, Copilote 36 px, × de puce, segments : zone étendue par `::after`, mesurée).

## 5. Mouvement (durées = jetons `--motion-*`, donc 0 ms en mouvement réduit)
| Geste | Durée | Courbe | Propriétés |
|---|---|---|---|
| Appui, survol | 120 | `--ease-standard` | fond, `scale(.88)` de la case |
| Cocher | 180 | `--tch-ease-entree` | rond 0,8 → 1,08 → 1, coche tracée (`stroke-dashoffset`), titre barré 1 px |
| Ligne faite | reste barrée jusqu'à la sortie de l'écran | — | — |
| Balayage relâché, retour | 260 | `--tch-ease-entree` | `transform` |
| Ajout d'une ligne | 260 | `--tch-ease-entree` | opacité + 8 px, `@starting-style` (jamais au chargement) |
| Feuille ouverte / fermée | 260 / 180 | entrée / `--tch-ease-sortie` | `transform` |
| Anneau qui avance | 260 | `--tch-ease-entree` | `stroke-dashoffset` |
Rien au-delà de 260 ms ; aucun mouvement ne retient la main.

## 6. États vides et icônes
Pastille ronde 72 px teintée (`--tch-accent-doux`, ou le fond du projet pour un projet vide) + pictogramme lucide
34 px trait 1,5 ; une phrase 17 px 500 (26 caractères de large) ; un bouton (plein seulement pour « Coller mes
listes »). Icônes lucide (tracés réels de `lucide-react`) : 20 px trait 1,75 en ligne, 14 px trait 2 en méta,
24 px trait 2 dans la barre d'onglets. Squelette statique, sans reflet animé.

## 7. Refusé, et pourquoi
- Carte ou bordure par tâche, barre de couleur à gauche de chaque ligne : faute 1, bruit.
- Fond de ligne à la couleur du projet : criard dès 3 projets.
- Archivo pour les heures (chiffres proportionnels, faute 12) ; Sora (3ᵉ police sans rôle).
- Une icône devant chaque option du sélecteur Quand : remplacée par trois tuiles texte (faute 4).
- Titre de section « Aujourd'hui » sous le titre de page « Aujourd'hui » : redite.
- Reflet animé du squelette, confettis, son : bruit, faute 9.
- Mélanges vers `transparent` en OKLCH : tirent vers le rose (vu au tour 1) → toujours en sRGB.
- Feuille de saisie à 50 % sous clavier : 86 px utiles ; la feuille prend la hauteur de son contenu, posée sur le
  clavier ; les crans 50/85 % valent clavier fermé (planche 6).

## 8. Nouveaux jetons à verser dans `tokens.css` (clair ET sombre)
`--tch-font-titre`, `--tch-font-texte` ; `--tch-titre-page`, `--tch-section`, `--tch-tache`, `--tch-tache-lh`,
`--tch-meta`, `--tch-meta-lh`, `--tch-chiffre` (valeurs bureau sous 768 px) ; `--tch-ligne-h`, `--tch-cible`,
`--tch-case`, `--tch-gouttiere`, `--tch-rayon-bloc/-champ/-carte/-feuille/-puce`, `--tch-heure-h`, `--tch-onglets-h` ;
`--tch-ease-entree`, `--tch-ease-sortie` ; `--tch-point-l/-c`, `--tch-fond-l/-c`, `--tch-texte-l/-c`,
`--tch-teinte-{terre…rose}` ; alias `--tch-surface`, `--tch-surface-haute`, `--tch-panneau`, `--tch-texte`,
`--tch-texte-doux`, `--tch-accent`, `--tch-accent-texte`, `--tch-fait`, `--tch-fait-texte`, `--tch-etoile`,
`--tch-etoile-fond`, `--tch-alerte`, `--tch-surveiller`, `--tch-trait`, `--tch-trait-grille`, `--tch-piste` ;
mélanges `--tch-survol`, `--tch-selection`, `--tch-accent-doux`, `--tch-jeton`, `--tch-barre-fond`,
`--tch-segment-actif`, `--tch-bloc-erp` ; littéraux `--tch-inverse-accent`, `--tch-voile`.
NE PAS verser : la réplique des primitives `@theme` (maquette seulement), `--tch-zone-sure-bas`, `--tch-clavier-h`.
La nouvelle feuille de l'app entre dans `GUARDED_SELECTORS` de `check_hex.mjs`.

## 9. Ce qui déplaît encore
- Le balayage gauche coupe le titre au bord (« …monos ») : fidèle au geste, pas joli en planche.
- Le camembert d'un projet à 0 ressemble à une case : seule la couleur l'en distingue.
- Les blocs ambre et olive en sombre tirent vers le brun.
- Quatre couleurs de rôle (azur, vert, or, rouge) en plus des projets : chacune rare, l'ensemble à éprouver sur
  une vraie journée chargée.
- Non vérifié : rendu sur un vrai iPhone (Safari, `backdrop-filter`, haptique), daltonisme, contraste augmenté iOS.

## Choix par défaut
Date fictive des maquettes : vendredi 20 novembre 2026 (demain = sam. 21, prochain jour travaillé = lun. 23,
cohérent avec « → lun. 23 »). Couleur de la case faite = `--success` plutôt que l'azur, pour que « fait » ait la
même couleur partout (case, balayage, anneau).
