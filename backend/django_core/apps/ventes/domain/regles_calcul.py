"""Règles de calcul d'un rendu de devis — « nouveaux rendus seulement ».

Décision fondateur (08/10/2026) : les corrections du moteur qui changent des
chiffres imprimés (AMOT8…AMOT60, ADEV28) ne s'appliquent qu'aux NOUVEAUX
rendus. Un devis déjà envoyé à la date de la migration 0138 porte
``regles_calcul = 1`` et continue d'être rendu (PDF, ``/proposal``, page
publique, cartes de tailles) avec les règles d'origine : le client relit
exactement ce qu'il a reçu. Tout autre devis (brouillons, devis créés ensuite,
révisions V2) porte 2.

Niveau 3 (corrections résidentielles du 27/10/2026, D-RES-2710-1 ombrage du
calepinage dans le moteur horaire, D-RES-2710-2 voiture électrique déjà
possédée) : la migration 0142 laisse à 2 tout devis non brouillon (envoyé
après le 08/10) et passe les brouillons et tout devis neuf à 3. Ces
corrections se branchent sur ``regles_au_moins(devis, REGLES_CORRIGEES_2710)``
— jamais sur ``calcul_corrige``, qui reste vrai dès le niveau 2 (les gardes
existantes ne bougent pas).

Pourquoi un drapeau et pas un PDF figé : rien n'est figé aujourd'hui —
``/proposal`` re-rend à chaque appel (``persist=False``) et
``cle_pdf_a_jour`` re-rend dès que l'empreinte du dict de rendu change, ce que
fait mécaniquement toute correction de code. Le drapeau est lu au seul endroit
où le calcul diverge ; c'est le même moteur, jamais un second.
"""

REGLES_ORIGINE = 1
REGLES_CORRIGEES = 2
REGLES_CORRIGEES_2710 = 3
#: Niveau 4 (D-CI-SENSIB-ENVOYES, fondateur 30/10/2026) : sensibilités C&I du
#: scénario production par le moteur du central (ERR-CI-SENSIBILITE-P90-INVERSEE).
#: La migration 0143 laisse à 3 tout devis non brouillon : il garde son tableau.
REGLES_SENSIBILITES_3010 = 4
#: Niveau 5 (D-CI-SENSIB-ENVOYES, « nouveaux rendus seulement », 30/10/2026) :
#: retour de l'option « avec batterie » d'un devis C&I non accepté
#: (ERR-CEC6-RETOUR-AVEC-BATTERIE-PERDU) et curseur de stockage ancré sur le TTC
#: du devis (ERR-AMOT59-CURSEUR-STOCKAGE-PRIX). Le niveau 4 est en production
#: depuis le matin : un devis envoyé au niveau 4 garde ses chiffres. La
#: migration 0144 laisse à 4 tout devis non brouillon. Porte aussi
#: D-CI-BATTERIE-NON-RENTABLE (fondateur 30/10/2026) : une option C&I « avec
#: batterie » hors de la règle marginale des 10 ans est MONTRÉE (meilleur
#: groupe de modules, ``batterie_rentable: false``, l'offre réseau reste
#: recommandée) au lieu d'être cachée — un devis de niveau ≤ 4 la cache encore.
REGLES_RETOURS_3010B = 5
#: Niveau 6 (D-ENF-ARRONDI-PDF, fondateur 30/10/2026, « nouveaux rendus
#: seulement ») : l'argent AFFICHÉ par le moteur de devis (cartes d'option,
#: totaux multi-villa, prix au kWc, économies, cumul 25 ans des tailles…) est
#: arrondi MOITIÉ VERS LE HAUT (``core.money.quantize_mad``) au lieu de
#: l'arrondi bancaire de ``round()`` — un écart d'une unité, sur les seules
#: valeurs exactement à moitié. La migration 0145 laisse à 5 tout devis non
#: brouillon : il garde l'arrondi qu'il a reçu (``montants.arrondi_affichage``).
REGLES_ARRONDI_3010 = 6
#: Niveau 7 (écarts de la contre-visite AMOT du 31/10/2026, C-AMOT-VER-003/006,
#: « nouveaux rendus seulement ») : le payback du curseur de stockage
#: (AMOT103), de l'échelle batterie (AMOT102) et de la carte « avec » de repli
#: (AMOT107) suit la définition de ``roi_a`` (part stockée 0, rendement du
#: devis, provision d'onduleur réelle). La migration 0146 laisse à 6 tout devis
#: non brouillon : il garde les paybacks qu'il a reçus.
REGLES_ECARTS_3110 = 7
#: Niveau 8 (contre-visite AGNR du 01/11/2026, C-AGNR-VER-007, AGNR54,
#: « nouveaux rendus seulement ») : la consommation de TOUS les lecteurs
#: publics (estimation mois par mois, journée type, couverture batterie,
#: simulateur, repli de ``monthly_consumption``) est résolue par
#: ``etude_horaire.profil_conso_du_devis`` (factures écran, kWh déclaré
#: CAD166, barème société) — la même série que l'étude. La migration 0147
#: laisse à 7 tout devis non brouillon : il garde la page qu'il a reçue.
#: Porte aussi AGNR52 : les % d'échéancier imprimés (puce CGV, marqueur C&I,
#: cases agricoles) sont dérivés des montants servis, branches MAD dès 2 tranches.
REGLES_CONSO_PUBLIQUE_0111 = 8
#: Niveau 9 (contre-visite AMOT du 01/11/2026, C-AMOT-VER-040/030, AMOT116 et
#: AMOT115, « nouveaux rendus seulement ») : un devis C&I dont la consommation
#: est connue ne demande plus « vos 12 dernières factures » mais nomme le
#: manque réel (contrat d'électricité, horaires d'activité) ; en base « deux »,
#: chaque carte d'option imprime l'économie TTC à côté de la HT. La migration
#: 0148 laisse à 8 tout devis non brouillon (drapeau de rendu
#: ``regles_ecarts_0111_historique``) : il garde la phrase et les cartes reçues.
REGLES_ECARTS_0111 = 9
#: Niveau 10 (ADVS5/ADVS6, D-ADVS-3, 02/11/2026, « nouveaux rendus seulement ») :
#: UNE règle range chaque ligne dans ses options (``utils.options.panier_de_ligne`` :
#: variante, rôle stocké, tout accessoire de batterie dans « avec » seulement,
#: mots-clés en repli), pour le PDF, la page et l'argent du noyau. La migration
#: 0149 laisse à 9 tout devis non brouillon : il garde ses deux répartitions
#: d'hier (moteur : rôle seul ; noyau : variante puis mots-clés), écart compris.
REGLES_PANIER_UNIQUE_0211 = 10
#: Niveau 11 (ADVS3, D-ADVS-4, 03/11/2026, « nouveaux rendus seulement ») : un TTC à
#: moins d'1 MAD sous une centaine y remonte au lieu de perdre 100 MAD. La migration
#: 0151 laisse tout devis non brouillon à son niveau : il garde le total reçu.
#: Porte aussi AGNR42-D6 : facture annuelle de la source « étude horaire » = somme exacte
#: arrondie une fois (factures hiver/été décimales : 17 010 et non 17 016).
#: Porte aussi ERR-CADV83-COUVERTURES : la réserve « prix révisable au-delà » sur les
#: couvertures (dessous : ``regles_validite_historique``, la pastille reçue).
REGLES_CENTAINE_0311 = 11
#: AMOT118 (C-AMOT-VER4-010, 04/11/2026) — niveau 12, contrat UNIQUE des correctifs
#: de chiffres de la contre-visite AMOT du 04/11 (AMOT120 provision d'onduleur
#: hors réseau, AMOT121 port batterie off-grid, AMOT122 branche d'échéancier,
#: AMOT123 économie TTC C&I, AMOT126 une-page C&I en ``fmt_dirhams``). La migration
#: 0153 ne passe que les brouillons jamais envoyés de 11 à 12 : un envoyé garde son rendu.
REGLES_ECARTS_0411 = 12
#: Niveau 13 (décision fondateur du 19/11/2026, « cycles publiés, usage réel »,
#: « nouveaux rendus seulement ») : sur le flux 25 ans de l'option C&I « avec
#: batterie », la batterie est remplacée l'année ⌊cycles publiés de la fiche ÷
#: cycles par an de l'étude⌋ + 1 — jamais au-delà de l'horizon, la garantie n'est
#: plus un plafond (``economie_ci_options.annee_remplacement_batterie``). La même
#: année sert le flux, la montée de la banque et le verdict « non rentable ». La
#: migration 0158 ne passe que les brouillons jamais envoyés de 12 à 13 : un devis
#: envoyé garde l'année de remplacement que le client a reçue.
REGLES_CYCLES_BATTERIE_1911 = 13
#: Niveau 14 (D-SENS-1, fondateur 19/11/2026 « Yes, fix it », « nouveaux rendus
#: seulement ») : le tableau des sensibilités C&I imprime le retour de CHAQUE
#: scénario au dixième (``retour_dixieme_ans``, même interpolation que la ligne
#: centrale) et l'option « avec batterie » sert ses propres sensibilités
#: (``domain/sensibilites_option_avec.py`` : dispatch batterie re-simulé pour la
#: production, remplacement au niveau 13 du bilan du scénario). Drapeau de rendu
#: ``regles_sensibilites_historique``. La migration 0159 ne passe que les
#: brouillons jamais envoyés de 13 à 14 : un devis envoyé garde son tableau.
REGLES_SENSIBILITES_1911 = 14
#: Niveau 15 (D-ACAL-36 + D-ACAL-39, fondateur 21/11/2026, DÉCLARÉ, PAS
#: courant) : la production imprimée vient de la pose réelle du calepinage
#: enregistré (plus du standard de la ville) et un toit en pente à panneaux
#: affleurants ne vend que le kit de fixation. Un seul niveau pour toute la
#: vague ACAL ; rendu courant, avec sa migration des seuls brouillons jamais
#: envoyés, par ACAL1001 après le dry-run des écarts (ACAL1000).
#: Porte aussi T4-U1-019 : une économie résidentielle, un arrondi — la facture
#: « avec solaire » (page 1 et exemple de la page 4) = « avant » − l'économie
#: imprimée (``renderer._apres_annuel``, ``etude_restitution._facture_avec_affichee``).
#: Et T4-U2-019 : un profil C&I dont l'heure ou les jours ont été supposés est
#: dit « profil type — estimation », jamais « horaires déclarés »
#: (``quote_engine/ci/synthese._methode_profil``) ; passée aux nouveaux rendus
#: par D-ACAL-102 (voir :data:`COUPURE_PHRASES_PROFIL`).
#: Porte aussi ADEV155 (D-ACAL-108, fondateur 25/11/2026 « Yes, with level 15 ») :
#: la production d'un lead SANS toit tracé vient de la simulation du plan par
#: défaut (même cascade que la pose, ``conception/moteur.plan_par_defaut_ouvert``),
#: allumée le même jour que le reste du niveau 15, jamais avant.
REGLES_POSE_REELLE_2111 = 15
#: Niveau 16 (HT24, fondateur 24/11/2026 « With battery now also picks from HV
#: inverters », DÉCLARÉ, PAS courant — il suit le 15) : l'option C&I « avec
#: batterie » se compose aussi sur un hybride HAUTE tension quand la basse
#: tension n'en compose aucune. Un devis qui le porte l'ouvre ; en attendant
#: qu'il devienne courant (il ne peut pas l'être sans rendre le 15 courant),
#: :func:`hybrides_ht_ouverts` fait ce que la migration d'un niveau courant
#: ferait : ouverte aux brouillons jamais envoyés et aux devis envoyés à partir
#: de :data:`COUPURE_HYBRIDES_HT`, fermée aux devis envoyés avant.
REGLES_HYBRIDES_HT_2411 = 16
#: Jour (inclus) à partir duquel un devis ENVOYÉ a pu recevoir la haute tension
#: (le lendemain de la décision ; rien n'était en ligne avant).
COUPURE_HYBRIDES_HT = (2026, 11, 25)
#: D-ACAL-102 (fondateur 25/11/2026 « Live now », « nouveaux rendus
#: seulement ») : les deux phrases corrigées du PDF C&I du niveau 15 —
#: T4-U2-019 (horaires SUPPOSÉS dits « profil type — estimation », jamais
#: « horaires déclarés ») et T4-U2-020 (« bases du calcul ci-dessous » dit
#: seulement quand le bloc est rendu) — passent aux nouveaux rendus SANS rendre
#: le niveau 15 courant : :func:`phrases_profil_ouvertes`, ouverte aux
#: brouillons jamais envoyés et aux devis envoyés à partir de ce jour (le
#: lendemain de la décision ; rien n'était en ligne avant), fermée aux devis
#: envoyés avant — ils gardent la phrase reçue. Rien d'autre du niveau 15.
COUPURE_PHRASES_PROFIL = (2026, 11, 26)
#: D-ACAL-111 à 114 (fondateur 25/11/2026, « nouveaux rendus seulement ») :
#: la ligne sous la facture actuelle recalculée (résidentiel), le titre sans
#: numéro d'un devis à UNE option (résidentiel), le devis FINAL de pompage
#: sans « à vérifier à la visite » — UNE coupure, UN prédicat
#: (:func:`phrases_pdf_2511_ouvertes`), même mécanique que
#: :data:`COUPURE_PHRASES_PROFIL` ; le niveau 15 n'est pas rendu courant.
COUPURE_PDF_2511 = (2026, 11, 26)
#: SCHEL-B4 (lot 6, fondateur 26/11/2026 — le schéma électrique du calepinage
#: remplace le schéma unifilaire du devis) : l'annexe technique PV46 du PDF
#: dessine le schéma électrique pour les NOUVEAUX RENDUS seulement — même
#: mécanique que :data:`COUPURE_PDF_2511`, le niveau 15 n'est pas rendu
#: courant. Le lendemain de la décision (comme D-ACAL-102), À CONFIRMER avec
#: Reda : un devis envoyé avant garde l'annexe qu'il a reçue.
COUPURE_SCHEMA_ELECTRIQUE = (2026, 11, 27)
#: D-ACAL-139 (orchestrateur 26/11/2026, À CONFIRMER avec Reda) : l'étude
#: électrique du devis (``electrical_service`` → ``core.electrique.concevoir``)
#: câble des chaînes INÉGALES d'une entrée MPPT à l'autre quand la partition
#: égale ne tient pas (35 × 715 Wc sur un hybride 2 entrées à 54 A : 12 + 12 |
#: 11, plus 5 × 7 hors spécification). Calculs NEUFS seulement : même mécanique
#: que :data:`COUPURE_SCHEMA_ELECTRIQUE`, le niveau 15 n'est pas rendu courant ;
#: un devis envoyé avant garde son étude, son annexe et son bordereau.
COUPURE_CHAINES_INEGALES = (2026, 11, 27)
#: T4-V2-010 (lot 8, 26/11/2026, « rien d'imprimé que la fiche ne prouve ») :
#: la description d'un variateur de pompage n'imprime plus « protection marche
#: à sec » quand sa fiche technique ne publie pas cette protection
#: (``var_protection_marche_a_sec`` différent de vrai) — l'écran du devis dit
#: déjà « la fiche ne dit pas s'il protège la pompe ». Nouveaux rendus
#: seulement, même mécanique que :data:`COUPURE_SCHEMA_ELECTRIQUE` (le niveau
#: 15 n'est pas rendu courant) ; date posée par l'orchestrateur à la PR du lot 8 :
#: le 28/11/2026, comme toutes les coupures du lot 8 — le lot doit être déployé
#: AVANT cette date (à déplacer avant de déployer s'il glisse).
COUPURE_PROTECTION_FICHE = (2026, 11, 28)
#: Niveau posé sur un devis neuf (défaut du modèle ``Devis.regles_calcul``).
REGLES_COURANTES = REGLES_SENSIBILITES_1911


def _ouvert_aux_nouveaux_rendus(devis, niveau, coupure) -> bool:
    """« Nouveaux rendus seulement » sans niveau courant : vrai pour ``None``
    (aperçu), une doublure sans champ, un devis au ``niveau``, un BROUILLON
    jamais envoyé et tout devis envoyé à partir de ``coupure`` ; faux pour un
    devis sorti du brouillon avant (repère : ``date_envoi``, à défaut
    ``date_creation``)."""
    from datetime import date
    if devis is None or regles_au_moins(devis, niveau):
        return True
    envoi = getattr(devis, 'date_envoi', None)
    if envoi is None and getattr(devis, 'statut', None) in (None, '', 'brouillon'):
        return True
    repere = envoi or getattr(devis, 'date_creation', None)
    if repere is None:
        return True
    jour = repere.date() if hasattr(repere, 'date') else repere
    return jour >= date(*coupure)


def phrases_profil_ouvertes(devis) -> bool:
    """D-ACAL-102 — les deux phrases corrigées du PDF C&I (T4-U2-019,
    T4-U2-020) pour ce devis ? Voir :data:`COUPURE_PHRASES_PROFIL`."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111, COUPURE_PHRASES_PROFIL)


def drapeaux_phrases_profil(devis) -> dict:
    """D-ACAL-102 — le drapeau de RENDU des deux phrases, posé pour le cas
    OUVERT : ``{'phrases_profil_ouvertes': True}`` pour un devis commercial /
    industriel dont le rendu change (nouveaux rendus), ``{}`` sinon. Ainsi
    l'empreinte des données (``builder.empreinte_donnees_pdf``) bouge pour les
    devis dont le PDF change — le fichier stocké d'un brouillon est re-rendu —
    et la charge utile d'un devis qui garde ce que son client a reçu (envoyé
    avant la coupure, autre marché) ne bouge pas d'un octet."""
    marche = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    if marche in ('commercial', 'industriel') and phrases_profil_ouvertes(devis):
        return {'phrases_profil_ouvertes': True}
    return {}


def phrases_pdf_2511_ouvertes(devis) -> bool:
    """D-ACAL-111 à 114 — les corrections du PDF du 25/11/2026 pour ce devis ?
    Voir :data:`COUPURE_PDF_2511`."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111, COUPURE_PDF_2511)


def drapeaux_pdf_2511(devis) -> dict:
    """D-ACAL-111 à 114 — drapeau de RENDU du cas OUVERT : ``{'phrases_pdf_2511':
    True}`` pour un devis résidentiel ou agricole dont le rendu change, ``{}``
    sinon (envoyé avant la coupure, commercial / industriel) : l'empreinte des
    données bouge exactement pour les devis dont le PDF change."""
    marche = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    if marche not in ('commercial', 'industriel') and phrases_pdf_2511_ouvertes(devis):
        return {'phrases_pdf_2511': True}
    return {}


def schema_electrique_ouvert(devis) -> bool:
    """SCHEL-B4 — l'annexe PV46 de ce devis dessine-t-elle le schéma
    électrique ? Voir :data:`COUPURE_SCHEMA_ELECTRIQUE`."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111,
                                       COUPURE_SCHEMA_ELECTRIQUE)


def chaines_inegales_ouvertes(devis) -> bool:
    """D-ACAL-139 — l'étude électrique de ce devis peut-elle câbler des chaînes
    inégales entre entrées MPPT ? Voir :data:`COUPURE_CHAINES_INEGALES`. Hors
    de toute empreinte : une étude rangée n'est jamais recalculée pour ça."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111,
                                       COUPURE_CHAINES_INEGALES)


def protection_fiche_ouverte(devis) -> bool:
    """T4-V2-010 — la description d'un variateur ne dit « protection marche à
    sec » que si sa fiche la publie, pour ce devis ? Voir
    :data:`COUPURE_PROTECTION_FICHE`. Pas de drapeau de rendu : la description
    retirée change elle-même l'empreinte des données des seuls devis ouverts."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111,
                                       COUPURE_PROTECTION_FICHE)


def drapeaux_schema_electrique(devis) -> dict:
    """SCHEL-B4 — drapeau de RENDU du cas OUVERT : ``{'schema_electrique_annexe':
    True}`` quand l'annexe dessine le schéma électrique, ``{}`` sinon. Posé
    SEULEMENT quand l'annexe est demandée (``quote_engine/artefacts_rendu``) :
    l'empreinte des données ne bouge que pour les PDF dont l'annexe change."""
    return {'schema_electrique_annexe': True} if schema_electrique_ouvert(devis) else {}


def drapeaux_nouveaux_rendus(devis, *, annexe=False) -> dict:
    """Les drapeaux de rendu « nouveaux rendus seulement » posés par le builder
    (D-ACAL-102, D-ACAL-111 à 114, lot 8 : :func:`drapeaux_pdf_2611`) : cas
    OUVERT seulement. ``annexe`` (SCHEL-B4) ajoute celui de l'annexe
    technique ; le builder ne le passe pas (l'annexe pose le sien elle-même),
    sa charge reste donc identique."""
    return {**drapeaux_phrases_profil(devis), **drapeaux_pdf_2511(devis), **drapeaux_pdf_2611(devis),
            **(drapeaux_schema_electrique(devis) if annexe else {})}


def hybrides_ht_ouverts(devis) -> bool:
    """HT24 — l'option « avec batterie » peut-elle se composer en HAUTE
    tension pour ce devis ? « Nouveaux rendus seulement » : seul un devis que
    le client a DÉJÀ reçu sans elle la garde fermée.

    Ouverte pour ``None`` (aperçu), une doublure sans champ, le niveau 16, un
    BROUILLON jamais envoyé (rien n'a été montré au client) et tout devis
    envoyé à partir de :data:`COUPURE_HYBRIDES_HT`. Fermée pour un devis sorti
    du brouillon avant cette date (envoyé, accepté, refusé, expiré — repère :
    ``date_envoi``, à défaut ``date_creation``) : il garde ce qu'il a reçu.
    """
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_HYBRIDES_HT_2411, COUPURE_HYBRIDES_HT)


def regles_au_moins(devis, niveau: int) -> bool:
    """Vrai si ce devis est rendu avec les règles de ``niveau`` ou plus récentes.

    ``None`` (pas de devis) ou un objet sans le champ (doublure de test,
    ``SimpleNamespace``) suit les règles courantes : seules les lignes
    explicitement marquées à un niveau inférieur en base gardent l'ancien
    calcul.
    """
    valeur = getattr(devis, 'regles_calcul', REGLES_COURANTES)
    try:
        return int(valeur) >= niveau
    except (TypeError, ValueError):
        return True


def calcul_corrige(devis) -> bool:
    """Vrai si ce devis est rendu avec les règles corrigées.

    ``None`` (pas de devis) ou un objet sans le champ (doublure de test,
    ``SimpleNamespace``) suit les règles corrigées : seules les lignes
    explicitement marquées 1 en base gardent l'ancien calcul.
    """
    return regles_au_moins(devis, REGLES_CORRIGEES)


#: D-ACAL-149 (fondateur 26/11/2026, « nouveaux rendus seulement ») : sur un
#: toit PLAT, ``zones[].pitchDeg`` n'est que la valeur mémorisée du curseur
#: (22° par défaut) ; la pente lue est 0 (``core.calepinage.geo.
#: pente_effective_du_pan``). Même mécanique que
#: :data:`COUPURE_CHAINES_INEGALES` (prédicat seul, aucun drapeau de rendu) ;
#: le niveau 15 n'est pas rendu courant. Date À POSER par l'orchestrateur (le
#: lendemain du déploiement) : un devis envoyé avant garde ce qu'il a reçu.
COUPURE_TOIT_PLAT = (2026, 11, 28)


def toit_plat_ouvert(devis) -> bool:
    """D-ACAL-149 — ce devis lit-il la pente d'un toit plat comme 0 (et non la
    valeur du curseur) ? Voir :data:`COUPURE_TOIT_PLAT`."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111,
                                       COUPURE_TOIT_PLAT)


#: Lecteurs en aval (fondateur 24/11/2026, « un produit se reconnaît à son rôle
#: et à sa fiche avant son nom ») : le moteur PDF, le noyau des paniers, l'étude
#: électrique et les lectures de lignes classent une ligne par le rôle déclaré
#: de son produit, puis sa fiche, puis les mots-clés (``domain.classe_ligne``).
#: « Nouveaux rendus seulement » : même mécanique et même date que
#: :data:`COUPURE_TOIT_PLAT` (le niveau 15 n'est pas rendu courant) ; un devis
#: envoyé avant garde le classement par les mots-clés qu'il a reçu.
COUPURE_CLASSE_PAR_ROLE = (2026, 11, 28)


def classe_par_role_ouverte(devis) -> bool:
    """Lecteurs en aval — ce devis classe-t-il ses lignes par le rôle et la
    fiche du produit avant les mots-clés ? Voir :data:`COUPURE_CLASSE_PAR_ROLE`."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111,
                                       COUPURE_CLASSE_PAR_ROLE)


#: D-ACAL-168 (fondateur, 26/11/2026) — un toit PLAT sur lequel aucune table n'est encore posée
#: (pas de ``geometry.tiltDeg``) prend 20° d'inclinaison des panneaux pour la production du devis,
#: annoncée au VENDEUR comme supposée (jamais imprimée pour le client) ; ni l'« Inclinaison par
#: défaut » de la société (30°), ni 10°. Lu par la lecture corrigée
#: (``geometrie.extract_roof_config(toit_plat_corrige=True)``), création et resynchro d'un devis ouvert.
INCLINAISON_TOIT_PLAT_SUPPOSEE_DEG = 20


#: Lot 8 (fondateur 26/11/2026, « nouveaux rendus seulement ») — les
#: corrections du PDF décidées ce jour-là : D-AMOT-9 (UNE économie « avec
#: batterie » par PDF résidentiel : la facture « avec solaire » de la page 1
#: et de l'exemple de la page 4 = « avant » − l'économie des cartes, la
#: correction T4-U1-019 sortie du niveau 15), D-AMOT-10 (la puce CGV par
#: défaut dit « barème national de référence », plus « ONEE/SRM ») et
#: D-ACAL-167 (le document industriel imprime une ligne courte « Bases du
#: calcul » quand le tableau des hypothèses a cédé). UNE coupure, UN prédicat
#: (:func:`phrases_pdf_2611_ouvertes`), même mécanique que
#: :data:`COUPURE_PDF_2511` ; le niveau 15 n'est pas rendu courant. Même date
#: que :data:`COUPURE_TOIT_PLAT`, À POSER par l'orchestrateur (le lendemain du
#: déploiement) : un devis envoyé avant garde ce qu'il a reçu.
COUPURE_PDF_2611 = (2026, 11, 28)
#: Les marchés dont le PDF ne change pas avec :data:`COUPURE_PDF_2611` (leur
#: charge utile ne reçoit pas le drapeau) : le commercial (aucune des trois
#: corrections ne le touche) et l'agricole (ni économie résidentielle ni
#: puce « Tarifs de référence »).
MARCHES_HORS_PDF_2611 = ('commercial', 'agricole')


def phrases_pdf_2611_ouvertes(devis) -> bool:
    """Lot 8 — les corrections du PDF du 26/11/2026 pour ce devis ? Voir
    :data:`COUPURE_PDF_2611`."""
    return _ouvert_aux_nouveaux_rendus(devis, REGLES_POSE_REELLE_2111, COUPURE_PDF_2611)


def drapeaux_pdf_2611(devis) -> dict:
    """Lot 8 — drapeau de RENDU du cas OUVERT : ``{'phrases_pdf_2611': True}``
    pour un devis dont le rendu change (marché hors
    :data:`MARCHES_HORS_PDF_2611`), ``{}`` sinon : l'empreinte des données
    bouge exactement pour les devis dont le PDF change."""
    marche = (getattr(devis, 'mode_installation', None) or '').strip().lower()
    if marche not in MARCHES_HORS_PDF_2611 and phrases_pdf_2611_ouvertes(devis):
        return {'phrases_pdf_2611': True}
    return {}


#: Liaison DC tracée (suite ACAL1317, lot 8, 26/11/2026 — règle fondateur du
#: 23/11 « un seul moteur, un seul chiffre par valeur, le plus réaliste ») :
#: quand le plan du calepinage porte un tracé DC MESURÉ du pan jusqu'à
#: l'onduleur et qu'aucune longueur n'est saisie, la liaison DC de la
#: SIMULATION (perte ohmique DC) et de la vérification de chute du calepinage
#: est ce tracé (``apps/calepinage/services/cables.py::longueur_dc``). Calculs
#: faits à partir de ce jour seulement : une simulation rangée n'est jamais
#: réécrite, elle ne change qu'à sa prochaine simulation. L'étude électrique
#: du devis n'en dépend pas (elle ne lit que la longueur SAISIE ``dc_m``) ; un
#: devis au niveau :data:`REGLES_POSE_REELLE_2111` (DORMANT) lit la production
#: de la simulation du calepinage, donc cette perte — seulement une fois ce
#: niveau rendu courant, jamais un devis déjà envoyé. Date = lendemain du
#: déploiement du LOT 9 (posée le 26/11 au soir : le lot 9 part après le lot 8,
#: donc un jour après :data:`COUPURE_TOIT_PLAT` ; à repousser si le lot 9
#: n'est pas déployé le 28/11 au plus tard). Le tracé n'y remplace que la
#: partie HORIZONTALE de la liaison.
COUPURE_LIAISON_DC_TRACEE = (2026, 11, 29)


def liaison_dc_tracee_ouverte(jour) -> bool:
    """Liaison DC tracée — un calcul du calepinage fait le ``jour``
    (``datetime.date``) prend-il le tracé DC du plan ? Voir
    :data:`COUPURE_LIAISON_DC_TRACEE`."""
    from datetime import date
    return jour >= date(*COUPURE_LIAISON_DC_TRACEE)
