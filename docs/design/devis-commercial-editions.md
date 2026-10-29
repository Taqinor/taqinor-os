# Devis commercial (C&I) — étude de design « deux éditions » (29/10/2026)

Demande du fondateur (28/10, soir) : « le plus beau devis commercial du monde », deux
publics possibles (dirigeant lettré / commerçant de tous les jours), **sans toucher au
devis actuel** — une version à côté, à juger le lendemain. Investigation niveau L3
(`go-deep`) : 7 lanes de recherche web, synthèse, construction, 3 lentilles de
vérification. Le code vit dans `apps/ventes/quote_engine/commercial_editions/` ; il
n'est **pas branché** sur le dispatch (`builder.registre_renderers`) et se rend par
`commercial_editions/apercu.py` (règle #4 : un seul chemin client, `/proposal` ; les
éditions sont destinées à devenir un *choix de gabarit* de ce même chemin, jamais un
second chemin).

## Ce que la recherche a établi (sources dans `scratchpad/research/01-07`, non versionnées)

| Fait | Source (lane) | Conséquence de design |
|---|---|---|
| Au Maroc, parmi les alphabétisés 10+, 99,2 % lisent l'arabe, 57,7 % le français (HCP 2024 via Le Matin) ; darija écrite rare (39 %) | 02 | L'arabe a sa place dans le document : libellés doublés FR/AR **depuis le catalogue** (jamais une traduction écrite dans le code) ; titres en arabe standard simple |
| Les devis marocains attendent un squelette : ICE/RC/IF du vendeur, numéro, validité, tableau désignation/qté/PU HT/TVA/total, « Bon pour accord », cachet | 06 (Clicpaie, AMDE) | Le squelette reste intégral dans les deux éditions (page devis + accord) |
| Les meilleures propositions solaires mettent UN chiffre personnalisé en couverture, la valeur avant le prix, ≤ 3 chiffres-titres ; ROI à côté du prix | 01 (Aurora/OpenSolar/Qwilr/Proposify) | Couverture = économie année 1 en héros, retour + part couverte + production en 4 faits, investissement sur sa rangée |
| Barres groupées > empilées ; facture « avant / après » en deux barres ; cumul réservé au point de retour (MeasuringU : 82-88 % lisent mal la pente d'un cumul) ; pictogrammes toujours avec le nombre | 04 | `graphiques.py` : barres mensuelles groupées, facture avant/après, frise du cumul avec point de retour, rangée de soleils + « 47 % » |
| Lecteur peu lettré : un chiffre-héros, une idée par page, pas de HT/TVA/kWc en pages 1-2, un vrai visage et un numéro, chiffres latins, isolats bidi | 05 (NN/g, CFPB, Medhi CHI 2009, MicroSave) | Édition Directe : question « ce que vous gagnez » → facture → prix → qui appeler |
| Jurys / systèmes de design : 3 rôles typographiques, filets au lieu de cartes, une couleur d'accent, pas d'or métallisé, marges asymétriques, chiffres tabulaires | 07 (Vercel, Butterick, Strom, Stripe) | Système commun `commun.py` : Fraunces (grands chiffres) + IBM Plex Sans (tabulaire par défaut) + IBM Plex Sans Arabic ; filets 0,5 pt ; un accent par édition |
| Les 3 polices actuelles n'ont pas de chiffres tabulaires et pas de glyphe U+202F (séparateur de milliers du moteur) ; l'or #F5A623 échoue au contraste en texte | 03 (mesuré fontTools) | Plex Sans suit toujours Fraunces/Plex Arabic dans la pile (il porte U+202F) ; l'ocre #B7791F ne sert qu'en filet/point, jamais en texte courant |
| Une couverture claire lit mieux sur téléphone qu'un aplat sombre (NN/g) ; la vignette WhatsApp n'est pas garantie | 03, 05 | Photo réelle en bandeau haut à voile plat, papier clair ; exporter la page 1 en image pour WhatsApp = suite à décider |

Une seule marque, deux éditions : la lane Maroc conclut que les preuves justifient une
scission **langue / densité**, pas deux marques. Les deux éditions partagent polices,
grille, filets et squelette légal ; elles diffèrent par le ton (encre pétrole / papier
chaud terracotta), la densité et la langue.

## Les deux éditions

**Signature** (dirigeant) — p1 couverture-affiche (photo, projet, héros « économies
estimées / an », facture avant/après, 4 faits, investissement ancré en bas) · p2 énergie
mois par mois, installation en bref, activité, position nette sur 25 ans (frise, jalons,
retour, TRI), bases du calcul · p3 le devis (tableau tabulaire, chaîne de totaux, option
batterie, options proposées, surplus), garanties, échéancier, services, étapes,
conditions, bon pour accord style contrat, bande légale.

**Directe** (commerçant) — p1 « ce que vous gagnez » (héros, facture avant/après en
grand, part couverte en soleils + nombre, prix clé en main, retour, échéancier, qui
appeler + QR) · p2 « ce que vous recevez » (devis, garanties, étapes, installation en
bref, activité, énergie mois par mois) · p3 retour sur 25 ans, bases du calcul,
services, conditions, accord avec cachet, bande légale. Libellés FR doublés en arabe
quand le catalogue porte la clé.

## Garanties tenues (vérifié le 29/10)

- **Zéro chiffre inventé** : `donnees.modele` lit `synthese_ci` / `totaux_all` /
  `chiffres_cles` et formate par les helpers existants ; parité des ancres
  `data-figure` avec le renderer actuel = identique sur hotel / boulangerie / café /
  dégradé (script `parite.py`). Les seuls nombres « nouveaux » sont des valeurs servies
  en décimales (facture avant/après, jalons du cumul, TRI) imprimées à l'unité comme la
  page finance industrielle.
- **Pages exactes, rien sous le pied** (`commercial.equip._tient`) sur les 3 fixtures,
  la fixture dégradée, la fixture complexe (deux options, sections, options proposées,
  note, interlocuteur), le devis réel DEV-202610-0119 (21 lignes, 2 taux de TVA,
  arrondi, QR) et en arabe — avec 3 paliers de densité (CIQ317).
- Python 3.11 (`compileall`), CSS tables seulement, polices OFL vendorisées en TTF
  statiques (les woff2 variables de Google ne sont pas lus par l'image prod — mesuré).

## Décisions à prendre (fondateur)

1. **Brancher ou non** : option `gabarit=signature|directe` de `/proposal`
   (`clean_pdf_options`) et choix par devis / par lead ; les tests de pages (AMOT36) et
   de parité suivent. Tant que non branché, rien ne change pour les clients.
2. **Économie mensuelle** : les lecteurs peu lettrés décident sur « par mois » (NREL,
   lane 04/05) ; le moteur ne sert pas ce chiffre (`economie_ci`), les éditions ne le
   calculent donc pas. L'ajouter côté moteur = une clé servie, pas un calcul de gabarit.
3. **14 clés à cataloguer** (3 langues, traductions fondateur) :
   `donnees.CLES_A_CATALOGUER` — hors français elles impriment leur littéral FR.
4. **Photo** : une seule photo C&I réelle (`industriel-45-couchant.jpg`) ; la
   bibliothèque `assets/installations/` gagne à recevoir des photos par activité.
5. **WhatsApp** : exporter la page 1 en image 4:5 (rasterisation du même PDF) ; la
   vignette PDF n'est pas garantie.
6. Le logo PNG actuel est petit et pâle sur photo ; un SVG/PNG haute définition de la
   marque améliorerait les deux couvertures.

## Révision du 29/10 (matin) — direction Khatam, trois éditions

Retour du fondateur sur la première passe : « Directe » devait porter beaucoup moins
d'information, « Signature » n'était pas assez marocaine et trop claire, et il faut trois
versions (Signature, Normale, Basique) qui rendent le devis actuel bien meilleur.

**Panel de conception (Workflow, 8 agents)** : quatre directions marocaines
indépendantes — Khatam (géométrie, marine et or), Majorelle & safran (couleur, arc
outrepassé), Riad (tadelakt, vert zellige, terracotta), Atlas (vert et or
institutionnel) — notées par trois juges (jury design, patron de PME marocaine,
ingénieur WeasyPrint) sur premium / marocain / sans cliché / lisibilité / marque /
faisabilité. **Khatam gagne à l'unanimité** (143 points contre 121-122 et 107) ; la
synthèse greffe : Fraunces 400 au lieu de 300 (réponse au « trop léger »), fenêtre en arc
pour la photo (de Majorelle, sans clipPath), double filet encre + or et laiton #7A5C1E
comme seul or lisible en texte (d'Atlas), accroche en italique (de Riad), QR dans la
Basique.

**Système** : marine #0F2345 en aplats tramés d'un carreau khatam (étoile à huit
branches au trait, SVG base64, jamais d'opacité), or #C9A04E en filets et losanges
seulement, bleu royal #1E4A8C réservé aux données, contrastes WCAG mesurés (script du
panel). Une seule marque ; seul le papier change (#FAF8F3 Signature, blanc ailleurs).

| Édition | Pages | Contenu | Aplat |
|---|---|---|---|
| Signature | 3 | tout le devis actuel + énergie mois par mois + position nette 25 ans ; photo en arc, héros 60 pt, bloc prix marine, cartouche d'accord | ≈ 44 % en page 1 |
| Normale | 3 | exactement le contenu actuel, registre de six faits, prix sur papier ; variante A (garanties + échéancier en page 2) puis B | bandeau 64 mm |
| Basique | 1 (2 si tableau long) | titre, client, réserve, trois chiffres, tableau simple, chaîne de totaux, échéancier et garanties sur une ligne, conditions, QR, accord, bande légale ; FR/AR du catalogue | bandeau 30 mm, pied à filets |

**Vérifié** : 15 rendus fixtures + devis réel DEV-202610-0119 + arabe, pages exactes ;
parité des ancres de chiffres avec le moteur actuel. **À signaler au moteur** : la bande
légale servie porte « Gérant : … » (contraire à D-APDF) ; la société TAQINOR Solutions
n'a pas de logo dans son profil (les éditions impriment la marque en lettres).
