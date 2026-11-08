# Audit PA2 « conception » — 2026-11-08 — L3
<!-- dossier-v3 | groupe: ACON | base: 8b62d8c | fraicheur: 76344a2 | constats: 39 | taches: 45 | decisions: 4 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PA2 (pilote calepinage) : lu `apps/calepinage/**`, `apps/ventes/{domain,horaire,public,views/devis_calepinage.py,public_views.py}`, `apps/crm/{portee,fiche}_selectors.py`, `apps/parametres/{models_company,selectors}.py`, `core/events`, `frontend/src/{features/calepinage,pages/ventes}`, `apps/web/src/lib/proposition.ts` ; table `PA2.json` |
| Niveau | L3 — chiffre client d'un devis envoyé (ombrage, marché C&I), séparation des tâches de l'approbation, fuite entre commerciaux, livrables 82-21 sur une conception non vendue, plusieurs portes par geste |
| Données | demo (pile locale, 22 sondes en transaction annulée) ; anon : non requis ; prod lecture seule le 08/11 : 2 brouillons C&I nés d'un calepinage en mode résidentiel (devis 418 et 154), 1 devis envoyé lié, 0 divergence vivante |
| Critères retenus | C1, C2, C3, C4, C5, C6, C7, C9, C10, C17 |
| Étapes | PA2.1 création · PA2.2 relevé terrain · PA2.3 conception du toit · PA2.4 variantes · PA2.5 simulation · PA2.6 approbation · PA2.7 retenir une variante · PA2.8 publication vers le devis · PA2.9 resynchroniser le devis · PA2.10 livrables techniques · PA2.11 dossiers 82-21 · PA2.S1 adoption par un devis · PA2.S2 V2 re-liée (parcours : PA2) |
| NE PAS REFAIRE | le moteur PDF et le gabarit `/proposal` (audits moteur et pdf) ; le devis après sa création (PA3) ; ACAL351, ACAL366, ACAL367 (seuls ouverts du calepinage au départ) ; ACAL35, ACAL38, ACAL92, ACAL182 (cochées : adoption, miroir retiré, re-liaison de la V2, porte unique de création) ; ACAL295 (portée de la liste, choix fondateur) |
| Non-objectifs | rendu réel du gabarit `/proposal` (règle #4) ; traduction des livrables ; seuils 82-21 (kW AC contre kWc DC) ; atelier 3D `roofPro11` ; Django admin ; écrans en navigateur |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| découverte : création, relevé, layout | opus/high | `calepinage/services/{creation,releve,layout,export_projet,modeles,variantes,reprise_public}.py`, `calepinage/views/{releve,depuis_lead,bibliotheque,calepinages}.py`, `PanneauReleve.jsx` | atelier 3D `roofPro11`, `fond_plan.py` |
| découverte : variantes, simulation, approbation | opus/high | `calepinage/services/{variantes,simulation,approbation,electrique,feu_vert}.py`, `selectors.py`, `ventes/horaire/ombrage.py`, `Approbation.jsx` | affectation manuelle après retenue |
| découverte : devis, packs, 82-21 | opus/high | `calepinage/services/{devis,liens,pack_technique,reglementaire,empreinte_livrable}.py`, `ventes/domain/{creation_calepinage,revision}.py`, `BoutonDevis.jsx` | pipeline ventes interne, rendu `/proposal` |
| sondes (4 lots) | opus/high | 21 constats rejoués sur la pile locale | écrans en navigateur |
| seconde lentille | opus/high | 3 S1 relus au geste d'écran, six rafraîchisseurs un à un, requête prod | navigateur |
| critique de complétude | fable/high | 7 trous, 4 sondés, 3 lus | traduction des livrables |
| rédaction des tâches | opus/high | 45 tâches v3 (3 rédacteurs) | — |
| dossier et registre | sonnet/high | ce dossier, `unites.yml`, `decisions.yml` | — |
Détecteurs : `scripts/check_parcours.py` → 7 tables, 83 étapes, 0 échec @76344a2 (dette gelée sans portes : PA5, PA7) ; `scripts/check_ownership.py` → OK @76344a2 · non exécutés : `scripts/rejouer_parcours.py PA2` (sondes de parcours à la place), `scripts/audit_tache.py` (greps équivalents dans chaque tâche).
Live : 22 sondes `docs/audits/sondes/ACON/` (REPRO, vraies routes HTTP, transaction annulée), dont un rejeu élargi (-L2 : société avec profil, devis né de « Générer le devis ») et une mesure de temps (C-ACON-063) · prévus non joués : écrans en navigateur, moitié écran de C-ACON-001 et C-ACON-002 (vitest).
Prod (lecture seule, 08/11) : 2 brouillons industriels ou commerciaux nés d'un calepinage en mode résidentiel (devis 418 et 154, signalés, non réparés) ; 1 devis envoyé lié à un calepinage, 0 divergence vivante d'ombrage ou d'empreinte : seul le S1 de marché a un objet dans l'état fautif.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ACON-001 | PA2.2 | C2 | S2 | `frontend/src/features/calepinage/atelier/PanneauReleve.jsx::enregistrer` | « Nouveau relevé » R2 daté du 01/11 après R1 (05/11) : « Enregistrer » corrige `releve_courant_id` = R1, écrasé par le contenu de R2 ; « Supprimer » aussi → viser le relevé affiché | `docs/audits/sondes/ACON/C-ACON-001.py` | ACON1 |
| C-ACON-002 | PA2.2 | C2 | S2 | `apps/calepinage/views/releve.py::releve_appliquer_cote` | « Appliquer la cote » sans jeton : 200, version 0 → 1 ; le « Enregistrer » de l'atelier tombe en 409 sur sa propre scène → jeton exigé (428 sans, 409 périmé), scène rechargée | `docs/audits/sondes/ACON/C-ACON-002.py` | ACON2 |
| C-ACON-003 | PA2.1 | C5 | S2 | `apps/calepinage/services/creation.py::creer_pour_lead` | Commercial A : le lead de B est en 404 au CRM mais `depuis-lead` et `POST calepinages/` rendent 201 et servent nom, adresse et GPS → portée CRM (`leads_visibles`), 404 sur toute porte | `docs/audits/sondes/ACON/C-ACON-003.py` | ACON3 |
| C-ACON-004 | PA2.1 | C6 | S3 | `apps/calepinage/services/export_projet.py::importer_projet` | lead avec C1 ouvert : `POST calepinages/` 409 mais import de projet 201, ouverts [228, 226] → même porte unique, 409 nommant C1 | `docs/audits/sondes/ACON/C-ACON-004.py` | ACON4 |
| C-ACON-005 | PA2.1 | C6 | S3 | `apps/calepinage/services/modeles.py::demarquer_modele` | C1 démarqué alors que C2 est l'ouvert du lead : 200, ouverts [231] → [231, 230] → 409 nommant C2 (D-ACAL-12) | `docs/audits/sondes/ACON/C-ACON-005.py` | ACON5 |
| C-ACON-020 | PA2.5 | C1 | S1 | `apps/ventes/horaire/ombrage.py::perte_ombrage_du_devis` | devis envoyé : un PUT des réglages de simulation fait passer la page publique de 8 357 à 9 084 kWh/an, le PDF garde 9 084 ; `simuler` 202 → perte figée à l'envoi, `simuler` 409 sur devis figé | `docs/audits/sondes/ACON/C-ACON-020.py` | ACON20, ACON30, ACON85, ACON87 |
| C-ACON-021 | PA2.9 | C1 | S1 | `apps/calepinage/selectors.py::ombrage_servi` | devis 8 panneaux, calepinage passé à 16 modules sans resynchroniser : perte servie 3,2 → 19,6 %, production du devis −17 % → perte servie seulement à empreintes égales, envoi gardé | `docs/audits/sondes/ACON/C-ACON-021.py` | ACON21, ACON86 |
| C-ACON-022 | PA2.6 | C5 | S2 | `apps/calepinage/services/approbation.py::_concepteurs` | concepteur de 6 versions, ou auteur d'une variante retenue par un autre : approbation 200 par lui-même → 409 « Vous avez conçu… » (D-ACAL-11) | `docs/audits/sondes/ACON/C-ACON-022.py` | ACON22 |
| C-ACON-023 | PA2.6 | C4 | S2 | `apps/calepinage/views/approbation.py::approbation` | relecteur approuve H1 pendant qu'un concepteur enregistre H2 : 200, accord posé sur H2 jamais relu, jeton ignoré → empreinte vue exigée, 409 | `docs/audits/sondes/ACON/C-ACON-023.py` | ACON23 |
| C-ACON-024 | PA2.6 | C4 | S3 | `apps/calepinage/services/approbation.py::est_approuve` | onduleur et chaîne forcée changés après accord : empreinte inchangée, accord valide, pièces d'exécution ouvertes ; conforme à D-ACON-3 mais non dit à l'écran → écrire la limite | `docs/audits/sondes/ACON/C-ACON-024.py` | ACON24 |
| C-ACON-025 | PA2.7 | C3 | S3 | `apps/calepinage/services/variantes.py::retenir_variante` | « Retenir A » puis +4 modules dans l'atelier : comparatif sur 8 modules, re-retenir A efface les 4 ajouts → la retenue suit la conception | `docs/audits/sondes/ACON/C-ACON-025.py` | ACON25 |
| C-ACON-040 | PA2.8 | C1 | S1 | `apps/ventes/domain/creation_calepinage.py::build_devis_from_layout` | leads industriel et commercial : `generer-devis` et `from-layout` 201 en résidentiel avec les économies du layout (41 234) ; agricole 201 sur `from-layout` → devis au marché du lead (D-ACON-1) | `docs/audits/sondes/ACON/C-ACON-040.py` | ACON40, ACON90 |
| C-ACON-041 | PA2.S2 | C3 | S2 | `apps/ventes/domain/revision.py::abandonner_revision` | V2 supprimée ou désactivée : V1 réactivée sans événement, calepinage délié ou resté lié à V2 verrouillé, 2e calepinage à l'ouverture 3D → événement et re-liaison à V1 | `docs/audits/sondes/ACON/C-ACON-041.py` | ACON41, ACON91 |
| C-ACON-042 | PA2.10 | C3 | S2 | `apps/calepinage/views/reglementaire.py::generer_dossier` | devis accepté 6,6 kWc, conception passée à 8,8 : dossier 82-21, pack technique et remise de documents rendus sans alerte → 409 nommant le devis | `docs/audits/sondes/ACON/C-ACON-042.py` | ACON42 |
| C-ACON-043 | PA2.11 | C2 | S2 | `apps/calepinage/services/reglementaire.py::_pieces_du_dossier` | pièce jointe obligatoire (titre, plan) illisible : dossier généré 200, `signalements` vide, PDF sans la pièce → 409 nommant la pièce | `docs/audits/sondes/ACON/C-ACON-043.py` | ACON43 |
| C-ACON-044 | PA2.11 | C10 | S3 | `apps/calepinage/views/reglementaire.py::generer_dossier` | approbation exigée, calepinage non approuvé : `pack-technique` 409 mais `generer-dossier` 200 → porte d'exécution aussi sur le dossier | `docs/audits/sondes/ACON/C-ACON-044.py` | ACON44, ACON45 |
| C-ACON-046 | PA2.8 | C6 | S3 | `apps/calepinage/services/devis.py::_generer` | deux générations concurrentes : 2 brouillons de même empreinte dont un orphelin ; deux clics successifs : 201 puis `deduplique` → verrou de ligne, garde « en cours » avant l'enregistrement | `docs/audits/sondes/ACON/C-ACON-046.py` | ACON46 |
| C-ACON-060 | PA2.4 | C1 | S2 | `apps/calepinage/services/variantes.py::dupliquer` | Dupliquer vers le lead B : la copie garde courbe, appareils, facture, production et pin de A (219 km du repère de B), la simulation de B part de la courbe de A → règle de copie du modèle | `docs/audits/sondes/ACON/C-ACON-060.py` | ACON11 |
| C-ACON-061 | PA2.8 | C1 | S2 | `apps/calepinage/services/archivage.py::archiver` | archiver le calepinage d'un brouillon le détache : perte d'ombrage 8,0 % → `None`, production du brouillon 8 357 → 9 084 kWh/an sans un mot sur le devis → refus nommé | `docs/audits/sondes/ACON/C-ACON-061.py` | ACON30, ACON31, ACON87 |
| C-ACON-062 | PA2.1 | C7 | S3 | `apps/calepinage/services/archivage.py::_refus_devis_porte` | devis refusé ou expiré : calepinage verrouillé, archivage 400 « détachez-le d'abord » (geste inexistant), place d'ouvert du lead occupée → archivage permis, instantané gardé | `docs/audits/sondes/ACON/C-ACON-062.py` | ACON12 |
| C-ACON-063 | PA2.10 | C9 | S4 | `apps/calepinage/tests/test_cal224_perf.py::PerfPlancheTest` | à 2 000 modules : pack technique 22-24 s, dossier 4,5-5,9 s, loin des 120 s ; mais le test de budget ne borne qu'un layout de 2 modules → borner la composition à 2 000 modules | `docs/audits/sondes/ACON/C-ACON-063.py` | ACON51 |
| C-ACON-130 | PA2.S1 | C6 | S3 | `apps/calepinage/services/creation.py::adopter_ou_creer_pour_devis` | second devis actif B d'un lead dont C1 porte A : C2 créé sans D-ACAL-12, « Concevoir » ouvre C2 en silence → B variante liée de C1 (D-ACON-2) | STATIQUE (lecture) | ACON6, ACON80 |
| C-ACON-131 | PA2.1 | C17 | S3 | `apps/calepinage/services/reprise_public.py::reprendre_trace_public` | tracé public à contour croisé : création puis tracé hors transaction commune, refus avalé → calepinage vide et muet, jamais repris → une transaction, motif au chatter | STATIQUE (lecture) | ACON7 |
| C-ACON-132 | PA2.3 | C6 | S3 | `apps/calepinage/services/layout.py::contours_croises` | `poseSurfaces[].vertices` hors contrôle alors que le champ au sol compte au devis (D-ACAL-5) → contour croisé refusé en 400 nommé | STATIQUE (lecture) | ACON8 |
| C-ACON-133 | PA2.3 | C2 | S3 | `apps/ventes/views/devis_calepinage.py::_ecrire_conception` | `sync-layout` et `POST layout` du devis sans en-tête If-Match écrivent sans comparaison (API seule) → 428 dès qu'un calepinage est lié | STATIQUE (lecture) | ACON9 |
| C-ACON-134 | PA2.2 | C2 | S3 | `apps/calepinage/services/releve.py::enregistrer_releve` | créer un relevé ne passe pas le verrou que corriger et supprimer passent, boutons actifs en lecture seule → 409 et boutons grisés | STATIQUE (lecture) | ACON10 |
| C-ACON-135 | PA2.2 | C2 | S4 | `apps/calepinage/views/photos.py::PhotosSiteMixin.photo_detail` | photo de site ajoutée, corrigée ou supprimée sur un calepinage figé (objet effacé, sans corbeille) → 409 verrou aux portes HTTP | STATIQUE (lecture) | ACON13 |
| C-ACON-136 | PA2.7 | C10 | S3 | `apps/calepinage/services/variantes.py::retenir_variante` | variante sans conception (`{}`) retenue : la conception courante est écrasée par un document vide ; `None` bascule « Retenue » sans écrire → 409 nommé comme `simuler` | STATIQUE (lecture) | ACON26 |
| C-ACON-137 | PA2.10 | C1 | S3 | `apps/calepinage/services/electrique.py::_ecart_devis` | aucune comparaison d'empreintes : conception passée de 12 à 20 modules sans resynchroniser, le rapport d'étude imprime « Écart étude / devis » → `None` si empreintes différentes | STATIQUE (lecture) | ACON27 |
| C-ACON-138 | PA2.6 | C7 | S3 | `apps/calepinage/services/approbation.py::statut_derive` | un refus d'approbation se range sous « Brouillon » et « Générer le devis » n'en dit rien → statut « Refusé » et avertissement dans la réponse | STATIQUE (lecture) | ACON28 |
| C-ACON-139 | PA2.7 | C7 | S4 | `apps/calepinage/services/variantes.py::retenir_variante` | deux « Retenir » simultanés : retenue lue hors transaction, contrainte partielle → 409 générique sans nom (le « 500 » est réfuté) → verrou de ligne avant la lecture | STATIQUE (lecture) | ACON29 |
| C-ACON-140 | PA2.5 | C1 | S4 | `apps/parametres/models_company.py::CompanyProfile.get` | une lecture (`get_or_create`) crée le profil société, le fuseau entre dans l'empreinte de simulation et périme toute simulation d'une société sans profil → lecture sans écriture | STATIQUE (lecture) | ACON30, ACON87 |
| C-ACON-141 | PA2.10 | C3 | S3 | `apps/calepinage/services/empreinte_livrable.py::_entrees_du_livrable` | empreinte sans lignes du devis lié, approbation ni verrou : approuver après le pack ne crée pas de version, la réponse décrit le rendu jeté → empreinte étendue | STATIQUE (lecture) | ACON45 |
| C-ACON-142 | PA2.11 | C2 | S3 | `apps/calepinage/services/reglementaire.py::_lignes_des_champs` | saisie contredisant le calepinage (6,6 contre 8,8 kWc) imprimée sans alerte à la génération → signalement nommant le champ et les deux valeurs | STATIQUE (lecture) | ACON47 |
| C-ACON-143 | PA2.11 | C3 | S4 | `apps/calepinage/services/empreinte_livrable.py::_lignes_liees` | l'empreinte de chaque dossier hache les saisies de TOUS les dossiers : joindre une pièce au dossier B périme A et le pack → hacher ses seules saisies | STATIQUE (lecture) | ACON48 |
| C-ACON-144 | PA2.8 | C10 | S4 | `apps/calepinage/services/devis.py::_generer` | second `generer-devis` avec `taux_tva` 10 sur un brouillon à 20 % : brouillon rendu tel quel, montant ignoré en silence (API seule) → 409 nommant le champ | STATIQUE (lecture) | ACON49 |
| C-ACON-145 | PA2.8 | C1 | S3 | `apps/ventes/public_views.py::_safe_zone_geometry` | la page publique dessine 600 panneaux par zone et republie le compte complet : une zone de 1 200 en montre 600 sans mention → tout dessiner jusqu'à 2 000 (D-ACON-4) | STATIQUE (lecture) | ACON50 |
| C-ACON-146 | PA2.8 | C1 | S3 | `apps/ventes/calepinage_options.py::capacite_du_layout` | même plafond de 600 par zone sur la contenance annoncée, sous le posé d'un toit de 1 200 modules → 2 000 par zone | STATIQUE (lecture) | ACON92 |
| C-ACON-147 | PA2.8 | C1 | S3 | `apps/web/src/lib/proposition.ts::buildViewerModel` | la visionneuse partage un budget de 600 panneaux entre toutes les zones : un toit 4 × 500 dessine 500 + 100 + 0 + 0, sans mention → 2 000 par zone, mention « vue simplifiée » | STATIQUE (lecture) | ACON93 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-ACON-139 | requalifié | le « 500 » est réfuté : le gestionnaire global rend un 409 `unique_conflict` sans nom, S4 |
| C-ACON-024 | requalifié S2 → S3 | D-ACON-3 : l'accord ne porte que sur la conception imprimée, reste à le dire à l'écran |
| C-ACON-063 | requalifié S3 → S4 | mesure sans dépassement (pack 22-24 s à 2 000 modules) : seul le test de budget est trop étroit |
| C-ACON-020 | élargi | seconde lentille : un devis né de « Générer le devis » range un bloc sans ombrage (PDF 27 251, page 25 071) dès le 1er envoi ; l'écart vu en sonde venait d'une société sans profil (résidu S4 : C-ACON-140) |
| C-ACON-040 | élargi | le refus agricole n'existe que sur le pont calepinage : `from-layout` rend 201 sur un lead agricole |
| C-ACON-042 | fusionné | remise de 13 documents et présentation compacte sans garde de divergence : une seule tâche, ACON42 |
| C-ACON-020, 021, 040, 041, 130, 145 | scindés | une tâche par geste ou propriétaire : ACON20, 85, 30, 87 · ACON21, 86 · ACON40, 90 · ACON41, 91 · ACON6, 80 · ACON50, 92, 93 |
Porte : 0 constat réfuté sur 30 candidats de découverte et 7 trous de la critique (le « 500 » de C-ACON-139 écarté, constat gardé en S4) ; 39 constats : 36 candidats, une fusion dans C-ACON-042, trois lectures nées de la rédaction (C-ACON-140, 146, 147) · seconde lentille : 3 S1 → maintenus 3, élargis 1 (C-ACON-020), 0 réfuté.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| multi-société | devis d'une autre société refusé par `adopter_ou_creer_pour_devis`, `demarrer_depuis_modele`, `lier_devis` ; `company` et `cree_par` jamais lus du corps | la portée CRM reste à part (C-ACON-003) |
| un ouvert par lead | verrou sur `POST calepinages/`, `depuis-lead`, `depuis-modele`, Dupliquer, restauration, changement de lead | l'import et le démarquage restent hors verrou (C-ACON-004, 005) |
| écriture de la conception | `POST layout/` exige If-Match (428) et compare sous verrou ; `layout/section/` exige `base_empreinte` | « Appliquer la cote » et les routes du devis restent sans jeton (C-ACON-002, 133) |
| variantes et simulation | la retenue ne se supprime pas ; retenir passe verrou figé, feu vert et verdict électrique ; simulation de variante écrite sur la variante seule | la retenue suit la conception (C-ACON-025) |
| approbation | code `calepinage_approuver` distinct ; refus sans motif, conception vide ou verdict bloquant : rien n'écrit ; empreinte périmée par tout changement imprimé | les auteurs de versions restent à exclure (C-ACON-022) |
| génération du devis | lead et client lus du calepinage ; montants validés avant écriture ; garde kWh déclaré dans la transaction ; garde électrique et feu vert à générer et resynchroniser | la course reste ouverte (C-ACON-046) |
| pack et dossier 82-21 | pièce obligatoire non rendue : refus nommé ; somme des pages contrôlée ; panne GED : refus `ged` ; pièces jointes PDF seulement, bornées à la société | la jointe illisible passe (C-ACON-043) |
| page publique et modèle | `_safe_roof_layout` retire économies, consommation, fond et prix par liste blanche ; le modèle translate et retire la consommation (D-ACAL-15) | Dupliquer n'en fait rien (C-ACON-060) |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ACON-1 | un calepinage sur un lead commercial ou industriel : refuser « Générer le devis » ou construire le devis au marché du lead | devis_au_marche_du_lead | ACON40 |
| D-ACON-2 | un second devis actif d'un lead dont le calepinage ouvert porte déjà un devis : variante, refus ou un calepinage par devis | variante_de_c1 | ACON6 |
| D-ACON-3 | l'approbation doit-elle couvrir la saisie électrique et la fixation | conception_seule | ACON24 |
| D-ACON-4 | la page publique et la visionneuse ne dessinent que 600 panneaux | tout_dessiner_2000 | ACON50 |

## 7. Optionnel (jamais une tâche)
- Avec `vue_restreinte_au_responsable` éteint (défaut), la liste et le détail des calepinages existants ignorent la portée CRM : choix fondateur (ACAL295), à instruire avec C-ACON-003 si Reda change le réglage.
- Le jumeau `io_layout.py::import_layout` (import JSON de conception, sans jeton) : lu, non rejoué, laissé à un autre geste (remplacement explicite).
- L'API `entree-electrique` n'écrit pas au chatter que l'accord porte sur un autre câblage ; `generer-dossier` ne liste pas les pièces attendues manquantes : lus, non sondés.
- « Créez une variante » proposé par le 409 d'un calepinage verrouillé : la création de variante passe-t-elle le verrou ? non rejoué ; lead purgé de la corbeille (identifiant qui pend) : non instruit.

## 8. Limites, non couvert, écarts
- Non couvert : écrans en navigateur ; atelier 3D `roofPro11` ; Django admin ; gabarit `/proposal` rendu pour les devis C&I (règle #4, déduit de `mode_installation`) ; traduction des livrables ; seuils 82-21 (kW AC contre kWc DC).
- Non couvert (suite) : double POST concurrent sur `pack-technique`, `generer-dossier` et `remettre-document` ; plan de câblage et rapport d'ombrage sur un C&I simulé ; dépôt GED de `construire_pack` (hors mesure).
- Écart à la méthode : `PA2.json` ne porte aucun constat de ce groupe (`constats` vide à chaque étape) → ponctuel : les rattacher au `vérifie ACON`.
- Écart à la méthode : 18 constats sans sonde (13 S3 et 5 S4, aucun S1-S2) ; sondes jouées dans le conteneur monté sur c38868a62, ancêtre de la base, diff des mécanismes vide → ponctuel : conteneur du jour.
- Limites des sondes : météo rejouée, fiches module et onduleur injectées (020 à 025) ; PDF de pièces simulés, gabarit, fusion et GED réels (042 à 044) ; concurrence de 046 par crochet sur une connexion.
- Fraîcheur : `main` a avancé de 8b62d8c à 76344a2 (137 commits) pendant l'audit ; le diff des mécanismes ne touche que des codes de refus 404 → 409 du plan importé, une colonne de devise de `CompanyProfile` et un schéma de factures : aucun symbole ancré modifié, les 3 S1 restent.
- Incident prod : aucun incident ouvert ; le S1 de marché est réel sur 2 brouillons (devis 418 et 154), signalés pour un geste humain, jamais réparés par un script (D-ACON-1) : ACON40 couvre les nouveaux devis.

## 9. Coût et routage
Coût : H0 S1 O14 F1 · jetons sous-agents ≈ 5,5 M · tâches 45 (P0 6 P2 11 P3 28 GATED 0).
Fable : une critique de complétude, 7 trous (2 S2, 4 S3, 1 S4) dont 4 sondés (Dupliquer vers un autre lead, archivage qui détache, devis refusé, temps de rendu) et 3 lus (page publique à 600 panneaux, remise de documents, photos hors verrou) ; elle a trouvé deux S2 que la découverte n'avait pas (copie du foyer d'un client vers un autre, archivage qui change la production d'un brouillon).
Routage : `PLAN_AUDIT_CALEPINAGE.md` 35 · `PLAN_AUDIT_DEVIS.md` 6 · `PLAN_AUDIT_TRANSVERSE.md` 2 · `PLAN_AUDIT_PARAMETRES.md` 1 · `WEB_PLAN.md` 1 · aucune tâche d'acceptation posée · PR #0.
