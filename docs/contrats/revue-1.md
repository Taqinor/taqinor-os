# Dossier contractuel — revue 1 (24-25/11/2026) : constats triés et répartis

Cinq relecteurs neufs ont lu ou regardé le travail avant le premier merge : critique adverse du code serveur, revue du
code de l'écran, revue du contenu français, vérification de la traduction arabe par retraduction, revue d'impression
(31 pages regardées, français et arabe, couleur et niveaux de gris). Ce fichier est la LISTE DE TRAVAIL des quatre
lanes de correction : chaque ligne a son verdict (retenu / écarté) et sa lane. Une lane ne touche que ses fichiers.

Noms PARTAGÉS, fixés ici pour que deux lanes ne les inventent pas chacune de leur côté :

| Nom | Sens | Qui le pose | Qui le lit |
|---|---|---|---|
| repère `{contrat_du}` | fragment « ␠du 24 novembre 2026 » (date d'émission du contrat de ce chantier), `''` si inconnue | S (`_contexte`, fr et ar) | T |
| repère `{adresse_societe}` | adresse de la société | S | T |
| repère `{reste_a_regler}` | prix − total réglé (la valeur de l'encadré) | S | T |
| libellé `part_retenue` | « Part du solde retenue jusqu'à la levée des réserves : ………… DH » | T (`libelles.py`, fr + ar) | R |
| libellé `signature_en_fin` | « Signature en dernière page » | T | R |
| libellé `ce_que_vous_convenez` | devient « Ce que nous convenons ensemble » (plus de `{nom}`) | T | R |
| code d'erreur `paiement_non_enregistre` (409) | émission de la variante « tranche réglée » sans encaissement enregistré | S | écran (affiche `detail`) |
| code d'erreur `montant_fige` (409) | émission d'un acte dont un texte personnalisé cite un montant qui n'est plus celui de la vente | S | écran (affiche `detail`) |

## Lane S — serveur (`contrats/contenu.py`, `services.py`, `selectors.py`, `types.py`, `models.py` + migration, `views_contrats.py`, `serializers_contrats.py`, `tests/test_contrats_dossier.py`, `tests/test_contrats_api.py`)

- **S1 (bloquant) — un texte personnalisé ne doit jamais figer une valeur.** Aujourd'hui, corriger un article le stocke
  en entier avec ses montants, sa date limite et ses options déjà écrits : la frise suit la vente, l'article non
  (`contenu.py::compacter_articles`, `resoudre_articles`, `articles_de_base`). À faire : (a) la base de comparaison
  des articles applique les réglages COMMUNS de l'acte (options, dates) mais pas ses textes ; (b) un article ou un
  quitus personnalisé est stocké en GABARIT : à l'enregistrement, chaque valeur vivante du contexte présente dans le
  texte (les plus longues d'abord : liste des tranches, montants, dates, références, noms) est remplacée par son
  repère `{…}`, et le rendu reformate avec le contexte vivant ; (c) à l'émission, refus 409 `montant_fige` (phrase
  qui nomme l'article) si un article ou un quitus personnalisé contient encore un montant en dirhams absent des
  valeurs vivantes. Tests : pénalité réglée puis retirée après correction d'un article ; échéancier corrigé sur la
  vente après correction de l'article Paiement ; réserve de propriété décochée puis recochée.
- **S2 (bloquant) — le quitus dit ce qui a été réellement réglé.** Avec un avoir, « avoir reçu la somme totale de
  {total_ttc} » est faux. Le quitus cite le total réglé ; le tableau des paiements et sa ligne de total viennent de
  la même source ; un écart (avoir, avance, escompte) apparaît en ligne nommée.
- **S3 (bloquant) — la variante « tranche réglée » ne s'émet pas sur une supposition.** Signée, elle vaut reçu
  contre la société. Le brouillon reste prêt et se prévisualise ; l'émission est refusée 409
  `paiement_non_enregistre` tant que les paiements enregistrés ne couvrent pas la cible cumulée de la livraison.
  `peut_emettre` et l'avertissement suivent.
- **S4 — la livraison sans tranche « livraison ».** `index_livraison` prend l'avant-dernière tranche : avec 50 / 50
  ou quatre tranches, l'acte réclame la mauvaise étape. Le texte devient neutre (lane T) ; côté serveur, la somme
  due à la livraison = cibles cumulées des tranches dont la clé désigne la commande ou la livraison, sinon la
  seule première tranche, et un avertissement le dit.
- **S5 — les garanties sont les mêmes dans les deux langues.** En arabe, seuls `designation`, `garant`, `detail`
  se personnalisent ; lignes, `duree_mois`, `fin` viennent du français. `delais.date_limite` est commune elle
  aussi (l'arabe ne règle que `detail`) et ne déclenche plus l'avertissement de traduction.
- **S6 — le PDF servi est toujours celui du contenu figé.** Si le dépôt GED a échoué, le téléchargement rend
  aujourd'hui l'ancienne version. Comparer l'empreinte et la version stockées ; en cas d'écart, re-rendre depuis le
  contenu figé et retenter le dépôt.
- **S7 — supprimer un chantier.** `PROTECT` bloque désormais toute suppression. Des brouillons ou des actes annulés
  ne doivent pas l'empêcher ; un acte émis ou signé, si (fonction `on_delete` propre, migration `0001` corrigée en
  place : elle n'est pas encore sur `main`).
- **S8 — portail client.** `rouvrir` et `annuler_dossier` retirent le partage (ou mettent le document à la
  corbeille) : le client ne doit pas voir deux procès-verbaux de livraison contradictoires ni un acte annulé.
- **S9 — deux variantes émises en même temps.** Verrouiller toutes les lignes de livraison du chantier avant le
  contrôle de la jumelle.
- **S10 — vider un champ.** Une chaîne vide est aujourd'hui ignorée (la valeur par défaut revient) : pour les
  champs facultatifs (dates de livraison / mise en service, délai de levée des réserves, horaires du SAV,
  représentant), vide = effacé.
- **S11 — `peut_*` dit la vérité.** Ils reflètent les mêmes droits que les routes d'écriture (rôle + droit de la
  grille), pour que l'écran ne propose jamais un geste que le serveur refusera.
- **S12 — repères du contexte** : poser `contrat_du`, `adresse_societe`, `reste_a_regler` (français et arabe) ;
  vérifier par un test que le contexte ARABE porte le vrai nom de la société et jamais celui de `FORMES_CTX`.
- **S13 — arabe dans `contenu.py`** : `solde` → « باقي الثمن » partout (libellé de tranche, ligne d'engagement) ;
  un libellé arabe pour chaque clé de tranche (commande, livraison du matériel, mise en service, réception
  définitive…) ; « تسلُّم » écrit de la même façon partout.
- **S14 — `sections_modifiables`** : `paiement` ne propose que `modalites` ; `conseils_intro` reste modifiable.
- Écartés ou reportés : chantier créé à la main lié à un devis non accepté (non confirmé) ; `logo_uri` figé dans
  chaque contenu (volume, sans effet) ; date de signature papier antérieure à l'émission (à revoir au tour 2).

## Lane T — textes (`contrats/textes.py`, `contrats/textes_ar.py`, `rendu/libelles.py`, `docs/contrats/juridique.md` § 4)

Toute modification du français est portée à l'identique en arabe, mêmes `cle`, mêmes conditions.

- **T1 — réception sans case cochée, client qui refuse de signer.** `une_seule_case` : ajouter « Si aucune case
  n'est cochée, la signature vaut réception sans réserve. » Article `reception` du contrat : ajouter « Si le Client
  refuse de signer le procès-verbal, il indique par écrit, dans les sept jours qui suivent la mise en service, les
  défauts qui motivent son refus ; {societe} y remédie, puis une nouvelle réception est proposée. Sans réponse
  écrite dans ce délai, {societe} peut mettre le Client en demeure de recevoir les travaux (article 774 du Dahir
  des obligations et des contrats). » — et ajouter ce point à `juridique.md` § 4.
- **T2 — part du solde retenue.** Acte 3 `solde`, 2e paragraphe : « Si des réserves sont inscrites, les parties
  chiffrent ci-dessus, d'un commun accord, la part du solde retenue jusqu'à leur levée ; elle ne peut dépasser la
  valeur des travaux qui restent à faire. Le reste est payable à la signature ; la part retenue est payable dans
  les huit jours qui suivent le constat écrit de la levée. Sans montant chiffré, aucune retenue ne s'applique. »
  Même règle, en une phrase, à l'article `reception` du contrat. Libellé `part_retenue` (voir le tableau).
- **T3 — portée de la réception.** Acte 3 `portee`, 1er paragraphe : « En signant, le Client reconnaît que
  {societe} a achevé les travaux prévus au contrat {contrat_reference}{contrat_du} et au devis {devis_reference},
  que l'installation est conforme à ces documents et fonctionne, et qu'il n'a constaté aucun défaut apparent en
  dehors des réserves écrites ci-dessus. »
- **T4 — la somme due, sans équivoque.** Acte 3 `solde`, 1er paragraphe : « Le Client reconnaît devoir à
  {societe} la somme de {exigible_maintenant} ({exigible_lettres}), reste du prix du contrat {contrat_reference}
  encore dû à ce jour, payable à la signature du présent procès-verbal. »
- **T5 — documents remis à la réception.** Acte 3 `portee`, dernier paragraphe : « Les garanties prévues au
  contrat **commencent ce jour**. Les notices et les fiches techniques sont remises au Client ce jour ; le
  certificat de garantie récapitulatif lui est remis avec l'acte de clôture. » Constat ajouté à la réception :
  « J'ai **reçu les notices et les fiches techniques** de mon installation. » Contrat `engagements_societe` : « à la
  réception » au lieu de « à la clôture » pour les notices et fiches, « à la clôture » pour le certificat.
- **T6 — livraison, version « tranche réglée ».** « {societe} confirme avoir encaissé à ce jour {total_regle},
  soit {pourcentage_regle} du prix. Rien n'est à payer à la livraison. » puis « Le reste du prix, soit
  {reste_a_regler}, sera exigible à la réception des travaux. »
- **T7 — livraison, version « reste à régler ».** « Selon l'échéancier du contrat {contrat_reference}, les sommes
  dues à la date de ce procès-verbal s'élèvent à {exigible_maintenant} ({exigible_lettres}). Le Client reconnaît
  avoir reçu le matériel listé ci-dessus et devoir cette somme à {societe}. » puis la phrase sur la pose.
- **T8 — une seule règle de garde**, la même phrase au contrat (`propriete`), à l'acte 2 (`garde`) et à l'acte 3 :
  « De la livraison au début de la pose, le Client a la garde du matériel livré : il le conserve à l'abri, dans un
  lieu fermé, et répond des pertes ou des dégradations dues à son fait ou à un défaut de surveillance. Pendant la
  pose et jusqu'à la réception, {societe} a la garde du chantier ; à la réception, la garde de l'installation
  passe au Client. » (acte 2 : garder « sans l'ouvrir ni le déplacer » ; acte 3 : la seule dernière proposition).
- **T9 — exclusions de garantie liées à la cause** (contrat `garanties`, acte 4 `exclusions`) : « une intervention
  ou une modification de l'installation par un tiers sans l'accord de {societe}, lorsqu'elle est la cause du
  dommage ; un choc, un incendie, une inondation, la foudre ou une surtension du réseau, sauf défaut des
  protections posées par {societe} ; un défaut de l'entretien décrit dans les notices remises à la réception, ou
  un usage contraire à ces notices. »
- **T10 — `paiement_intro`** : « Chaque étape correspond à un moment précis du chantier : l'acompte lance la
  commande de votre matériel, les paiements suivants suivent la livraison puis la fin des travaux. »
- **T11 — quand chaque étape est due** (contrat `paiement`, après la liste) : « « À la signature » : le jour où
  le contrat est signé. « À la livraison » : le jour où le matériel est déposé à l'adresse du chantier, constaté
  par le procès-verbal de livraison. « À la réception » : le jour où le procès-verbal de réception est signé. »
  `engagements_client` : « payer chaque étape au moment prévu à l'article Paiement ».
- **T12 — délais** : aux suspensions, ajouter « et pendant l'attente de la réponse du gestionnaire du réseau,
  lorsque son accord est requis avant les travaux » (à ajouter à `juridique.md` § 4) ; 3e paragraphe (consommateur) :
  « Si la date limite, prolongée des suspensions ci-dessus, est dépassée de plus de sept jours, le Client peut,
  dans les cinq jours qui suivent, mettre fin au contrat par écrit (articles 12 à 14 de la loi n° 31-08) ;
  {societe} lui rembourse alors les sommes versées dans les sept jours. »
- **T13 — acte 4 `garantie_legale`**, 2e paragraphe : deux textes selon `consommateur` (entreprise : « tribunal
  compétent du siège de {societe} », comme au contrat).
- **T14 — français et arabe** (contrat `dispositions_finales`, consommateur) : « Le contrat est accompagné de sa
  traduction en arabe, remise en même temps (loi n° 31-08, article 206). En cas de différence entre les deux
  textes, l'interprétation la plus favorable au Client s'applique (article 9 de la même loi). »
- **T15 — fin anticipée** : ajouter « Le matériel ainsi payé est remis au Client ; si {societe} peut le rendre à
  son fournisseur ou le réutiliser, elle ne retient que les frais de retour justifiés. »
- **T16 — données** : ajouter aux destinataires « le fabricant de l'onduleur, dont l'application de suivi peut
  héberger les données de production et de consommation hors du Maroc, et les autorités ou conseils lorsque la
  loi ou le recouvrement d'une somme due l'exige ».
- **T17 — acte 4 `demarche`** : ajouter « les réparations sont faites sur place ou à l'atelier de {societe},
  {adresse_societe} ; le matériel à renvoyer au fabricant passe par {societe} ».
- **T18 — clarté** : `chapeau_contrat` + « Dans ce contrat, « vous » et « le Client » désignent la même
  personne. » ; `conditions_particulieres_intro` : « priment sur les articles ci-dessus » ; quitus : « quitte du
  prix de ce contrat » ; garantie légale : ajouter « et, pour le travail de pose, articles 767 et 772 du même
  Dahir » ; `ce_que_vous_convenez` → « Ce que nous convenons ensemble » ; `signature_en_fin`.
- **T19 — conseils et entretien** : entretien « rincez à l'eau claire, sans nettoyeur haute pression ni produit,
  sans monter ni marcher sur les panneaux ; sur un toit en pente, appelez-nous » ; conseil Veilles : « …sauf
  réfrigérateur, congélateur et box internet ; ne coupez jamais l'onduleur ni ses disjoncteurs » ; sans batterie :
  « Pendant une coupure du réseau, l'installation s'arrête : c'est une sécurité. » ; avec batterie : « Pendant une
  coupure du réseau, seuls les circuits secourus restent alimentés, si votre installation en comporte » ; gros
  appareils : « lave-linge, lave-vaisselle, four, fer à repasser, pompe ou surpresseur d'eau » ; « un à la fois » :
  « en fin de matinée… en début d'après-midi ».
- **T20 — arabe, les deux écarts de sens** : `demarche` puce 2 → « إذا كان العطب مشمولًا بأحد الضمانات… » ;
  `propriete` → « ابتداءً من تسليم المعدات لديه ».
- **T21 — arabe, langue** : garde (`propriete`, `garde`) → « ويُسأل عن ضياعها أو تلفها متى كان ذلك ناتجًا عن فعله
  أو عن تقصير منه في الحراسة » ; intro batterie → « …بقيت البطارية أكثر امتلاءً لليل » ; libellé `jusqua` → « المدة
  القصوى: {duree} » ; `engagements_client` puce 1 → « تمكين {societe} من الولوج إلى الورش ومن الماء والكهرباء… » ;
  `reception` → « ولا تحول التحفظات دون استعمال المنظومة » ; `portee` → « ويُثبَت رفعها في محرَّر يوقّعه الزبون » ;
  les dix retouches de style du relecteur (liste dans son rapport, reprise ici : « يتوقف سريان هذا الأجل… السيئة »,
  « متوقفة عن الاشتغال », « تتولى معالجة الطلب », « اتحاد الملاك المشتركين », « تسري الضمانات », « خلل ظاهر »,
  « بمبلغ إجمالي قدره », « أي … برسم الضريبة على القيمة المضافة », « التعريف الموحد للمقاولة (ICE) » / « البطاقة
  الوطنية للتعريف » / « خدمة ما بعد البيع لدى {nom} »).
- Écartés : promettre que la date de fin de garantie imprimée vaut même si le fabricant compte plus tôt (engagement
  nouveau : à trancher par Reda) ; reprise du matériel aux frais de la société après résolution (ajout hors loi) ;
  constat d'achèvement par commissaire judiciaire (non vérifié).

## Lane R — rendu (`rendu/documents.py`, `rendu/composants.py`, `rendu/style.py`, `tests/test_contrats_rendu.py`)

Cibles de pagination à tenir sur les exemples, français ET arabe : contrat ≤ 7, procès-verbaux 2, clôture 3.

- **R1 — réserves** : encadré de la réception à 4 lignes + la ligne `part_retenue` ; livraison à 3 lignes (la
  place existe en bas de page 1).
- **R2 — clôture** : plus de saut de page forcé avant les conseils (seulement si la place manque) ; la carte du
  service après-vente remonte juste sous l'article « Qui appeler » ; deux paragraphes du quitus espacés.
- **R3 — rien ne se coupe au mauvais endroit** : RIB sur sa propre ligne et insécable ; « n° 31-08 », « IF
  00000000 », références `CTR-…` / `DEV-…` insécables ; pied : la ligne légale ne passe plus sur trois lignes à
  côté des paraphes.
- **R4 — noir et blanc** : bordures des paraphes, des cadres de signature, des lignes à remplir et de la pastille
  « À venir » à ≥ 3:1 ; l'état « à régler » et l'étape en cours marqués par un anneau bleu nuit épais et un
  chiffre gras (en gris, l'or seul devient le plus clair) ; vert des états assombri (`#0F6630`).
- **R5 — signatures** : cadre du client ≥ 38 mm dans les quatre actes ; le numéro de CIN du client (ou « CIN :
  …… ») sous son nom ; le bloc de signature ne part jamais seul sur une page.
- **R6 — dates** : une seule forme, la longue (« 2 décembre 2026 »), y compris dans les pastilles et la colonne
  « Jusqu'au ».
- **R7 — en-tête courant** : la référence s'imprime en haut des pages 2 et suivantes (`string-set` posé sur un
  élément visible de taille nulle, pas sur un `display:none`).
- **R8 — articles** : un article court (≤ 3 paragraphes) ne se coupe pas entre deux pages.
- **R9 — titre de la livraison** : double échappement du nom de société (`c.h2(libelle(...))` reçoit un nom déjà
  échappé) ; le titre lit le nouveau libellé `ce_que_vous_convenez`.
- **R10 — réception en arabe** : titre + frise + encadré du montant dû dans un même bloc insécable.
- **R11 — page 1 du contrat** : la ligne `signature_en_fin` sous la frise.
- Écartés : désignations du catalogue en français dans l'acte arabe (voulu) ; équilibrage des lignes d'un seul mot.

## Lane F — écran (`frontend/src/pages/installations/contrats/**`, `frontend/src/styles/chantiers/contrats.css`, `frontend/src/api/documentsApi.js`)

- **F1** — en arabe, la date limite s'affiche en lecture seule et n'est pas envoyée ; les durées et dates de fin
  des garanties aussi (seuls désignation, garant, couverture se modifient en arabe).
- **F2** — fermer l'éditeur avec des modifications non enregistrées demande confirmation (bouton, croix, Échap,
  clic à côté), comme le changement de langue.
- **F3** — « Enregistrer comme modèle » est désactivé tant que des modifications ne sont pas enregistrées.
- **F4** — « Délai d'exécution » n'apparaît que sur le contrat.
- **F5** — champs ajoutés : `paiement.modalites` (texte) et `conseils_intro`.
- **F6** — si le chargement en arabe échoue après un changement de langue, l'éditeur ne garde pas le brouillon
  français sous l'étiquette arabe.
- **F7** — accessibilité : chaque case de constat nommée par son texte, cible ≥ 44 px, zone de texte étiquetée ;
  le numéro de l'étape en cours lisible en thème sombre ; les boutons de chaque carte reliés au titre de leur
  acte (`aria-describedby`).
- **F8** — les gestes d'écriture suivent UNIQUEMENT les `peut_*` du serveur.
- **F9** — tests : les `sections_modifiables` du test arabe viennent de l'exemple de contrat, jamais d'une liste
  écrite à la main ; un test par section fait passer le corps envoyé par la forme attendue de l'exemple
  (`corps_patch`).
