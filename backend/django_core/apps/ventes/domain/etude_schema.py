"""QJR61 — ``etude_params`` a enfin un SCHÉMA, un VALIDATEUR et UN ÉCRIVAIN.

CE QUE CE MODULE FERME. ``Devis.etude_params`` est un JSONField sans forme
déclarée, écrit par une douzaine de chemins (le générateur, les quatre
rafraîchisseurs serveur, la fusion ``etude_extra`` de l'auto-devis, la
resynchro, le PATCH du devis…). Personne ne pouvait dire QUELLE clé appartient
à QUI, ni si elle est une ENTRÉE du client ou une valeur DÉRIVÉE du moteur.
Conséquence vécue : un PATCH partiel venu de l'écran REMPLAÇAIT le bloc entier
et faisait disparaître en silence ``factures_mensuelles_reelles``, ``gamme``,
``etude_horaire`` et ``dimensionnement``.

LES TROIS PIÈCES.

* :data:`SCHEMA` — par clé de TÊTE : son type, son PROPRIÉTAIRE (l'étape qui a
  le droit de l'écrire) et sa nature (ENTRÉE du client / DÉRIVÉE du moteur).
* :func:`valider` — PURE, sans base : rend la liste des reproches (clé
  inconnue, type impossible), jamais une exception.
* :func:`ecrire` — LE SEUL écrivain. Il **FUSIONNE** (jamais un remplacement en
  bloc), REFUSE une clé DÉRIVÉE écrite par un non-propriétaire, et persiste en
  ``update_fields=['etude_params']`` — donc sans jamais toucher un statut, une
  ligne ou un total (règle #4).

POURQUOI « PROPRIÉTAIRE » ET PAS « LECTURE SEULE ». Une valeur dérivée n'est pas
interdite d'écriture : elle est interdite à QUI NE LA CALCULE PAS. Le
rafraîchisseur horaire a le droit de poser ``etude_horaire`` — c'est lui qui le
produit ; l'écran, non. Ce module NOMME cette différence au lieu de la laisser
se jouer au dernier arrivé.
"""

# ── Les PROPRIÉTAIRES (l'étape qui a le droit d'écrire une clé DÉRIVÉE) ──────
#: L'écran / le générateur de devis (entrées du commercial).
ECRAN = 'ecran'
#: Le rafraîchisseur d'étude horaire (``services.rafraichir_etude_horaire``).
MOTEUR_HORAIRE = 'moteur_horaire'
#: Le rafraîchisseur de dimensionnement (``rafraichir_dimensionnement_devis``).
MOTEUR_DIMENSIONNEMENT = 'moteur_dimensionnement'
#: ``profils_comparatifs.rafraichir_profils_comparatifs_devis``.
MOTEUR_PROFILS = 'moteur_profils'
#: La tâche d'étude bankable asynchrone (``tasks.task_simulate_bankable_study``).
MOTEUR_SIMULATION = 'moteur_simulation'
#: Le calepinage 3D (``build_devis_from_layout`` / ``sync_devis_from_layout``).
CALEPINAGE = 'calepinage'
#: La création automatique depuis un lead (``services.build_devis_auto``).
AUTO_DEVIS = 'auto_devis'
#: CIQ117 — le moteur SERVEUR C&I (``domain/etude_ci.py``, D-CIQ-0) : seul
#: écrivain de l'étude commerciale/industrielle v2 (``etude_ci``,
#: ``production_figee``). Un navigateur ne les écrit JAMAIS.
MOTEUR_CI = 'moteur_ci'
#: AGR122 — le moteur SERVEUR du pompage (``domain/pompage.etudier_pompage``,
#: D-AGR-1) via son rafraîchisseur (AGR123) : seul écrivain des dérivées de
#: l'étude agricole v2 ET des sept clés v1 que le rendu lit encore. Un
#: navigateur ne les écrit JAMAIS ; une copie/V2 les recalcule.
MOTEUR_POMPAGE = 'moteur_pompage'
#: L'ORDONNANCEUR lui-même (``domain/pipeline.appliquer``) — DC11/QJR106. Il ne
#: calcule rien : la seule clé dont il est propriétaire est l'ESTAMPILLE de
#: provenance, c'est-à-dire la trace de CE QU'IL A REPRIS du lead.
PIPELINE = 'pipeline'
#: Personne : clé HISTORIQUE que plus aucun chemin ne pose (voir les notes).
ORPHELINE = 'orpheline'

#: Nature d'une clé.
ENTREE = 'entree'
DERIVEE = 'derivee'


def _cle(type_attendu, proprietaire, nature, note='', moteur=False,
         exclusif=False):
    """Une règle de clé. ``moteur=True`` la déclare ENTRÉE DU MOTEUR.

    QJR222 (31/08/2026) — ``exclusif=True`` DÉCLARE UNE ENTRÉE RÉSERVÉE À SON
    PROPRIÉTAIRE. Le contrôle de propriété ne portait que sur les clés
    DÉRIVÉES ; une ENTRÉE dont le propriétaire est une ÉTAPE (et non le
    commercial) passait donc par ``PATCH /devis/<id>/etude-params/`` depuis le
    navigateur. Une ENTRÉE reste écrivable par n'importe quelle étape par
    DÉFAUT — c'est un choix du commercial, il peut arriver de plusieurs écrans
    — sauf quand elle est déclarée exclusive ici, NOMMÉMENT et avec sa raison.
    Une exclusion s'écrit, jamais par omission.

    QJR66 / passe Fable pré-merge (29/08/2026) — POURQUOI CE QUATRIÈME
    ATTRIBUT. Depuis que l'écran écrit ``etude_params`` par l'endpoint de
    FUSION (et non plus dans le corps atomique du devis), ses factures réelles
    arrivent APRÈS le rafraîchissement des quatre études : le PDF servait alors
    des économies dérivées d'entrées PÉRIMÉES — une régression franche par
    rapport au chemin d'hier. L'endpoint doit donc relancer les études quand,
    et seulement quand, une clé qui NOURRIT le moteur vient de bouger.

    Ce drapeau met cette liste LÀ OÙ ELLE APPARTIENT : dans le schéma, à côté
    de la clé, avec la trace de son consommateur. L'endpoint interroge
    :func:`entrees_du_moteur` — il n'en code aucune en dur, et une clé ajoutée
    demain se déclare ici, une seule fois.
    """
    return {'type': type_attendu, 'proprietaire': proprietaire,
            'nature': nature, 'note': note, 'moteur': bool(moteur),
            'exclusif': bool(exclusif)}


#: LE SCHÉMA des clés de TÊTE d'``etude_params``, relevé par scan de l'arbre
#: (29/08/2026). ``type`` est un tuple accepté par ``isinstance`` ; ``None`` y
#: est TOUJOURS toléré (une clé absente et une clé nulle disent la même chose :
#: « pas calculable », règle Z2).
SCHEMA = {
    # ── Les CHOIX du commercial (ENTRÉES) ────────────────────────────────────
    'scenario': _cle((str,), ECRAN, ENTREE,
                     'Sans batterie / Avec batterie / Les deux — QJR64 le fait '
                     'passer par le registre de surcharges. MOTEUR : '
                     '`quote_engine/builder.py` (`_stored_choice`) et '
                     '`utils/options.py` en tirent les lignes de l’option '
                     'vendue.', moteur=True),
    'recommended_option': _cle((str,), ECRAN, ENTREE),
    'gamme': _cle((str, dict), ECRAN, ENTREE),
    'mode_installation': _cle((str,), ECRAN, ENTREE),
    'tension_raccordement': _cle((str,), ECRAN, ENTREE),
    'distributeur': _cle((str,), ECRAN, ENTREE,
                         'MOTEUR : le barème qui chiffre la facture « avant » '
                         '(`quote_engine`, page client).', moteur=True),
    'categorie_commerciale': _cle((str,), ECRAN, ENTREE),
    'origine': _cle((str,), ECRAN, ENTREE),
    'nombre_proprietes': _cle((int,), ECRAN, ENTREE,
                              'MOTEUR : `selectors.py` multiplie le total du '
                              'devis par ce nombre (×N villas).', moteur=True),
    'factures_mensuelles_reelles': _cle((list,), ECRAN, ENTREE,
                                        'Les factures RÉELLES du client — la '
                                        'donnée la plus précieuse du dossier. '
                                        'MOTEUR : `domain/entrees.py`, '
                                        '`etude_horaire`, '
                                        '`profils_comparatifs`.',
                                        moteur=True),
    'conso_kwh_mensuelles': _cle((list,), ECRAN, ENTREE,
                                 'MOTEUR : `domain/entrees.py`, '
                                 '`dimensionnement`, `offres_tailles`.',
                                 moteur=True),
    'conso_annuelle': _cle((int, float), ECRAN, ENTREE,
                           'MOTEUR : les rendus industriel / commercial et '
                           '`generate_devis_premium` l’impriment.',
                           moteur=True),
    'toiture': _cle((dict,), ECRAN, ENTREE),
    'attribution': _cle((dict,), ECRAN, ENTREE),
    # ``{'date': <iso>}`` — un « depuis quand », écrasé à chaque resynchro
    # post-envoi (jamais un journal). Le booléen est toléré pour les devis
    # anciens qui n'ont qu'un drapeau.
    'resync_apres_envoi': _cle((bool, dict), CALEPINAGE, ENTREE),
    # ACAL90 (D-ACAL-22) — les classes de kit (``CLASSES_KIT_COMPLETABLES``)
    # RETIRÉES À LA MAIN : la resynchronisation ne les recrée jamais. Posée
    # par ``domain/lignes`` (suppression d'une ligne, enregistrement de
    # l'écran), lue par ``composition._completer_kit_residentiel``.
    'kit_retire': _cle((list,), ECRAN, ENTREE,
                       note='classes de kit retirées à la main (ACAL90).'),
    # DC11 / QJR106 — L'ESTAMPILLE DE PROVENANCE des valeurs énergie/toiture
    # REPRISES DU LEAD : ``{'source_lead_id', 'captured_at', 'valeurs'}``,
    # produite par ``crm.selectors.lead_provenance_stamp`` et posée par
    # ``pipeline.estampiller_provenance``. C'est une ENTRÉE, pas une dérivée :
    # elle ne CALCULE rien, elle enregistre ce que le pipeline a RECOPIÉ, et
    # c'est la comparaison de ces valeurs-là avec le lead COURANT
    # (``crm.selectors.lead_values_changed_since``) qui allume la bannière
    # « valeurs du lead modifiées depuis » sur l'écran générateur.
    # QJR222 — EXCLUSIVE. C'est l'ESTAMPILLE du pipeline, pas une saisie : sa
    # forme interne (``source_lead_id`` / ``captured_at`` / ``valeurs``) est
    # lue telle quelle par ``crm.selectors.lead_values_changed_since``, et une
    # forme malformée levait ENSUITE, à l'intérieur du bloc atomique du
    # pipeline — cassant durablement TOUT enregistrement de ligne sur ce devis
    # (déni de service auto-infligé, réversible mais silencieux à la pose).
    # Un navigateur ne peut donc plus l'écrire : refus 400 FR NOMMANT la clé.
    'provenance': _cle((dict,), PIPELINE, ENTREE,
                       'DC11 — d’où viennent les valeurs énergie/toiture du '
                       'devis. Jamais une entrée du moteur : rien ne se '
                       'calcule à partir d’elle.', exclusif=True),

    # QJR591 — LA VILLE SUR LAQUELLE LE DEVIS A ÉTÉ CHIFFRÉ, consignée par
    # ``pipeline.rafraichir_etudes`` à chaque recalcul des études :
    # ``{'ville': <ville tapée>, 'reference': <ville de calcul>}``. Le PDF la
    # lit (productible + ligne méta « X, près de Y ») au lieu de relire le lead
    # à chaque rendu : corriger la ville d'un lead ne change plus en silence
    # la production d'un devis ENVOYÉ.
    'ville_calcul': _cle((dict,), PIPELINE, DERIVEE,
                         'QJR591 — ville de calcul figée au recalcul des '
                         'études ; lue par `quote_engine/builder.py`.'),

    # ── Ce que le MOTEUR calcule (DÉRIVÉES) ──────────────────────────────────
    'etude_horaire': _cle((dict,), MOTEUR_HORAIRE, DERIVEE),
    'etude_horaire_sans': _cle((dict,), MOTEUR_HORAIRE, DERIVEE,
                               'I7 — le bloc horaire de l’option SANS, posé '
                               'SEULEMENT quand les deux options portent des '
                               'champs PV différents (L-2OPT) ; '
                               '`etude_horaire` décrit alors l’option AVEC.'),
    'dimensionnement': _cle((dict,), MOTEUR_DIMENSIONNEMENT, DERIVEE),
    'profils_comparatifs': _cle((dict,), MOTEUR_PROFILS, DERIVEE),
    'simulation': _cle((dict,), MOTEUR_SIMULATION, DERIVEE),
    'puissance_kwc': _cle((int, float), CALEPINAGE, DERIVEE,
                          'QJR63 lui donne UN propriétaire : le registre, '
                          'sinon la dérivation depuis les LIGNES.'),
    'production_annuelle': _cle((int, float), CALEPINAGE, DERIVEE),
    # ACAL101 (C-ACAL-113) — LA PROVENANCE de ``production_annuelle`` /
    # ``economies_annuelles`` : ``'calepinage'`` quand
    # :func:`cles_etude_du_layout` les a recopiées du layout (base 720 W du
    # calepinage, à RECALER sur les lignes —
    # ``domain.scenario.figure_production_du_devis``), ``'saisie'`` pour une
    # étude saisie (jamais recalée). Absente : jamais recalée.
    'production_source': _cle((str,), CALEPINAGE, DERIVEE,
                              'ACAL101 — « calepinage » | « saisie » ; lue '
                              'par `scenario.figure_production_du_devis`.'),
    # ACAL102 — trace de la migration 0132 (backfill de la marque ci-dessus
    # sur les devis existants) : seul son retour la lit, aucun écrivain.
    'production_source_backfill': _cle(
        (bool,), ORPHELINE, DERIVEE,
        'ACAL102 — posée par la migration ventes 0132 ; lue par son seul '
        'retour (retrait des marques qu’elle a posées).'),
    'economies_annuelles': _cle((int, float), CALEPINAGE, DERIVEE),
    'autoconso_sans': _cle((int, float), CALEPINAGE, DERIVEE),
    'autoconso_avec': _cle((int, float), CALEPINAGE, DERIVEE),

    # ── Le bloc AGRICOLE (pompage) — AGR122 (contrat AGR2
    #    `etude_pompage_preview.json`, `cles_etude_params_v2`). Les sept clés
    #    v1 que le RENDU lit encore (`quote_engine/agricole`, `payload_economie`)
    #    restent, mais DÉRIVÉES du moteur serveur : elles décrivent la pompe
    #    RETENUE, écrites par le rafraîchisseur (AGR123), jamais tapées.
    'pompe_cv': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                     'AGR122 — puissance_retenue.cv.'),
    'pompe_kw': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                     'AGR122 — puissance_retenue.kw.'),
    'hmt_m': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                  'AGR122 — hmt.valeur_m.'),
    'debit_hmt_m3h': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                          'AGR122 — pompe.debit_a_hmt_m3h.'),
    'm3_jour': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                    'AGR122 — production au mois critique (absente sans '
                    'production : jamais un m³/jour sans courbe).'),
    'champ_kwc': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                      'AGR122 — champ.kwc.'),
    'heures_pompage': _cle((int, float), MOTEUR_POMPAGE, DERIVEE,
                           'AGR122 — heures équivalentes au mois critique.'),

    # ── QJR66 / ARBITRAGE ORCHESTRATEUR (29/08/2026) — LE CONTRAT DE
    #    ROUND-TRIP `?edit=`. Le mappeur de réouverture de brouillon
    #    (`DevisGenerator.jsx`, effet `?edit=`) RELIT ces clés de TÊTE pour
    #    reposer le formulaire tel que le vendeur l'avait laissé. Elles étaient
    #    écrites par l'ancien remplacement EN BLOC et n'ont jamais eu de
    #    déclaration : hors schéma, la fusion QJR62 les refusait en 400 et le
    #    round-trip mourait en silence. Ce sont toutes des ENTRÉES du
    #    commercial (ce qu'il a TAPÉ), propriétaire ECRAN — JAMAIS des
    #    dérivées : aucun de ces nombres n'est calculé par le moteur.
    #
    #    Entrées du marché AGRICOLE — AGR122 (D-AGR-13) : les ENTRÉES v2 du
    #    contrat AGR2 (`cles_etude_params_v2.entrees`), chacune au nom de la
    #    clé du corps de l'aperçu (`hmt_entrees` = l'objet `hmt`). Les clés v1
    #    `debit_souhaite_m3h`, `heures_pompage` (désormais dérivée),
    #    `profondeur_m`, `distance_m`, `region`, `crop`, `surface_ha`,
    #    `hmt_static`, `hmt_drawdown`, `irrigation_method` QUITTENT le schéma
    #    (grep des lecteurs serveur du 06/10/2026 : aucun ne lit
    #    `etude_params[<clé>]` — le rendu agricole lit la synthèse v2 ;
    #    `quote_engine/agricole/schema.py` lit `profondeur_m`/`distance_m`
    #    d'une SYNTHÈSE construite depuis `source`/`distance_champ_m`). Aucune
    #    relecture d'un ancien devis agricole (D-AGR-13). `moteur=True` : un
    #    PATCH qui les touche relance les études, dont le pompage (AGR123).
    'mode_pompe': _cle((str,), ECRAN, ENTREE, 'AGR122 — neuve | existante.',
                       moteur=True),
    'plaque': _cle((dict,), ECRAN, ENTREE,
                   'AGR122 — {kw, tension_v, phases, cv, courant_a}.',
                   moteur=True),
    'besoin': _cle((dict,), ECRAN, ENTREE,
                   'AGR122 — mode, volume, débit souhaité, mois de pointe, '
                   'cultures, région (D-AGR-3).', moteur=True),
    'source': _cle((dict,), ECRAN, ENTREE,
                   "AGR122 — le point d'eau (débits, niveaux, forage).",
                   moteur=True),
    'hmt_entrees': _cle((dict,), ECRAN, ENTREE,
                        "AGR122 — l'objet `hmt` du corps : saisie_m ou "
                        'composantes.', moteur=True),
    'type_pompe': _cle((str,), ECRAN, ENTREE),
    'alim': _cle((str,), ECRAN, ENTREE),
    'localisation': _cle((dict,), ECRAN, ENTREE,
                         'AGR122 — {ville, lat, lon}.', moteur=True),
    'distance_champ_m': _cle((int, float), ECRAN, ENTREE, moteur=True),
    'options_cochees': _cle((list,), ECRAN, ENTREE,
                            'AGR122 — clés de `kit.options[].cle`.',
                            moteur=True),
    'taille': _cle((str,), ECRAN, ENTREE,
                   'AGR122 — recommandee | inferieure | superieure.',
                   moteur=True),
    # AGR206 (D-AGR-13, règle d'AGR122) — `current_fuel` et
    # `fuel_spend_current` QUITTENT le schéma : plus écrites (AGR212) ni lues
    # (lecteurs au grep du 05/10/2026 : `etudeMarcheBloc.js`, `etatDevis.js`
    # — retirés par AGR212 ; le moteur `economie_pompage.py` ne la lit
    # jamais). L'énergie et la dépense DÉCLARÉES vivent dans
    # `saisies_economie_pompage` (contrat `economie_pompage.json`, AGR3) :
    # ENTRÉE écran, recopiée par les copies et la V2 (jamais un calcul).
    'saisies_economie_pompage': _cle(
        (dict,), ECRAN, ENTREE,
        "AGR206 — consommation déclarée, prix payé daté, mois d'irrigation, "
        "facture réseau, entretien (contrat economie_pompage.json)."),
    # AGR217 (contrat AGR200) — l'attestation de destination AGRICOLE du
    # matériel (art. 91-I-C-6° CGI 2026 : « utilisée dans le secteur
    # agricole ») : {attestee, le, signataire}. Saisie, jamais calculée.
    'attestation_usage_agricole': _cle(
        (dict,), ECRAN, ENTREE,
        "Attestation d'usage agricole saisie : {attestee: bool, le: date "
        "ISO, signataire: texte}."),

    # AGR122 — les DÉRIVÉES v2 du moteur pompage, EXCLUSIVES `moteur_pompage`
    # (contrat AGR2 `cles_etude_params_v2.derivees`) : un navigateur ne les
    # écrit jamais, une copie/V2 les recalcule (CLES_DERIVEES_NON_COPIEES).
    'besoin_mensuel': _cle((list, dict), MOTEUR_POMPAGE, DERIVEE,
                           'AGR122 — besoin m³/jour par mois + nature.'),
    'production': _cle((dict,), MOTEUR_POMPAGE, DERIVEE),
    'couverture_pct_mois': _cle((list,), MOTEUR_POMPAGE, DERIVEE),
    'controle_conception': _cle((dict,), MOTEUR_POMPAGE, DERIVEE),
    'conception': _cle((dict,), MOTEUR_POMPAGE, DERIVEE),
    'champ': _cle((dict,), MOTEUR_POMPAGE, DERIVEE),
    'hmt_composantes': _cle((dict,), MOTEUR_POMPAGE, DERIVEE),
    'ha_irrigables': _cle((dict, int, float), MOTEUR_POMPAGE, DERIVEE),
    'autonomie_reservoir_jours': _cle((dict, int, float), MOTEUR_POMPAGE,
                                      DERIVEE),
    'kit': _cle((dict,), MOTEUR_POMPAGE, DERIVEE),
    'alertes_pompage': _cle((list,), MOTEUR_POMPAGE, DERIVEE),
    'hypotheses_pompage': _cle((list,), MOTEUR_POMPAGE, DERIVEE),
    'pvgis_fige': _cle((dict,), MOTEUR_POMPAGE, DERIVEE,
                       'AGR122 — coordonnées + profil PVGIS figés '
                       '(reproductibilité).'),
    'provenance_pompage': _cle((dict,), MOTEUR_POMPAGE, DERIVEE,
                               'AGR122 — {chemin: {origine, detail, date}} '
                               "des entrées résolues : un défaut n'est "
                               'jamais enregistré comme une saisie.'),

    # ── QJR66 (même arbitrage) — les ENTRÉES du marché industriel/commercial.
    #    `tension_raccordement` est déclaré plus haut (entrée générale) ; la
    #    RÉPARTITION horaire MT, elle, est la saisie qui l'accompagne : sans
    #    elle l'étude MT OMET économies et payback (aucune plage horaire MT
    #    officielle n'étant publiée, on n'en invente pas).
    'repartition_mt': _cle((dict,), ECRAN, ENTREE),

    # ── CIQ117 (contrat CIQ2 `etude_ci_preview.json`, `cles_etude_params_ci_v2`)
    #    — le C&I v2 sur UN moteur serveur (D-CIQ-0). ENTRÉES = ce que l'écran
    #    saisit (propriétaire ECRAN) ; DÉRIVÉES EXCLUSIVES `moteur_ci` : un
    #    navigateur ne les écrit jamais, une copie/V2 les recalcule (elles sont
    #    dans ``CLES_DERIVEES_NON_COPIEES``, QJR117). Les clés ÉCRAN v1 et les
    #    réponses de catégorie à plat ont QUITTÉ le schéma (CIQ129 :
    #    ``CLES_RETIREES_CI_V1``). `economie_ci` / `tva_recuperable` sont
    #    déclarées par D2 (CIQ3) ; `tarif_declare` par CIQ203.
    'mode': _cle((str,), ECRAN, ENTREE, 'CIQ117 — commercial | industriel.'),
    'site': _cle((dict,), ECRAN, ENTREE,
                 'CIQ117 — {ville, lat, lon} : un site par étude.'),
    'tension': _cle((str,), ECRAN, ENTREE, 'CIQ117 — bt | mt | inconnue.'),
    'phases': _cle((str,), ECRAN, ENTREE, 'CIQ117 — mono | tri | inconnu.'),
    'puissance_souscrite_kva': _cle((int, float), ECRAN, ENTREE),
    'consommation': _cle((dict,), ECRAN, ENTREE,
                         'CIQ117 — kwh_mensuels / kwh_annuel / factures_mad '
                         '/ registres_mt ; une tranche ouverte n\'est jamais '
                         'un montant (D-CIQ-19).'),
    'rythme': _cle((dict,), ECRAN, ENTREE,
                   'CIQ117 — jours ouverts, plages, équipes, fermetures, '
                   'talon : le profil DÉCLARÉ (D-CIQ-1).'),
    'courbe_mesuree': _cle((dict,), ECRAN, ENTREE),
    'toit': _cle((dict,), ECRAN, ENTREE),
    'contraintes': _cle((dict,), ECRAN, ENTREE),
    'options': _cle((dict,), ECRAN, ENTREE),
    'taille_explicite_kwc': _cle((int, float), ECRAN, ENTREE,
                                 'CIQ117 — souveraine (D-QJR5-13).'),
    # CIQ203 — le tarif DÉCLARÉ du client (contrat CIQ11 `tarifs_ci.json`) :
    # validé à l'écriture (`tarif_ci.reproches_tarif_declare`, 400 nommant
    # `etude_params.tarif_declare.<champ>`). Les saisies de l'économie C&I
    # (contrat CIQ3 `economie_ci.json`) : le schéma n'en contrôle que le type
    # objet, leurs sous-champs sont validés par le moteur (CIQ205-CIQ209).
    'tarif_declare': _cle((dict,), ECRAN, ENTREE,
                          'CIQ203 — prix de la facture du client d\'abord.'),
    'saisies_economie_ci': _cle((dict,), ECRAN, ENTREE,
                                'CIQ203 — TVA récupérable, actualisation, '
                                'revente, aide, offres écrites.'),
    'etude_ci': _cle((dict,), MOTEUR_CI, DERIVEE,
                     'CIQ117 — entrees_resolues, profil_charge, production, '
                     'taille, bilan, alertes, hypotheses, version, empreinte.'),
    'production_figee': _cle((dict,), MOTEUR_CI, DERIVEE,
                             'CIQ117 — coordonnées + réponse PVGIS figées '
                             '(reproductibilité, CIQ109).'),

    # ── Clé HISTORIQUE sans écrivain ─────────────────────────────────────────
    'payback_annees': _cle(
        (int, float), ORPHELINE, DERIVEE,
        "QJR48 a supprimé son unique écrivain (le récepteur QX24) : aucun "
        "consommateur du dépôt ne la lit. Déclarée ici pour qu'un devis "
        "ANCIEN qui la porte encore ne soit pas signalé comme invalide."),
}


#: CIQ129 (D-CIQ-21) — les clés QUI ONT QUITTÉ le schéma, avec l'endroit où
#: vit désormais leur valeur. Une clé reçue d'ici ⇒ refus 400 FR qui la NOMME
#: (:func:`valider`) ; jamais relue sur un ancien devis, jamais migrée.
#: Le rendu ne les lit plus : ``quote_engine/builder`` les retire de l'étude
#: rendue et une copie/V2 ne les reprend pas (``domain/etudes``).
_SOURCE_MOTEUR_CI = ('dérivée du moteur serveur C&I (`etude_ci`, servie par '
                     '`synthese_ci`) : jamais écrite par l’écran')
_SOURCE_REPONSE = ('réponse de catégorie : elle s’envoie dans '
                   '`rythme.reponses_categorie`')
CLES_RETIREES_CI_V1 = {
    'taux_autoconso': _SOURCE_MOTEUR_CI,
    'taux_couverture': _SOURCE_MOTEUR_CI,
    'payback': _SOURCE_MOTEUR_CI,
    'injection_kwh_an': _SOURCE_MOTEUR_CI,
    'injection_dh_an': _SOURCE_MOTEUR_CI,
    'etude_kwc_base': ('le moteur C&I recalcule `etude_ci` à chaque '
                       'changement de lignes'),
    'part_diurne_pct': ('le profil horaire se déclare dans `rythme` '
                        '(plages, équipes, talon)'),
    **{cle: _SOURCE_REPONSE for cle in (
        'chambres', 'occupation_pct', 'piscine', 'chambres_froides',
        'horaires', 'cuisson', 'surface_vente_m2', 'effectif', 'clim', 'lits',
        'garde_nuit', 'internat', 'fermeture_estivale', 'surface_m2',
        'chauffe', 'four', 'cuisson_nocturne', 'temperature_consigne',
        'volume_m3', 'saisonnalite_recolte')},
}

#: ACAL101 — les deux valeurs de ``etude_params['production_source']``.
PRODUCTION_CALEPINAGE = 'calepinage'
#: Aucun écrivain ne pose « saisie » aujourd'hui (``production_annuelle`` est
#: DÉRIVÉE, propriétaire CALEPINAGE) : valeur réservée, lue comme « absente ».
PRODUCTION_SAISIE = 'saisie'


#: CIQ117 — les marchés dont l'étude vient du moteur SERVEUR C&I : le layout
#: n'y apporte que la géométrie et le kWc, jamais production ni économies.
MARCHES_CI = ('commercial', 'industriel')


def cles_etude_du_layout(mode_installation, resultat):
    """CIQ117 — ce que la synchro d'un calepinage écrit dans l'étude.

    Résidentiel et agricole : ``production_annuelle`` et
    ``economies_annuelles`` du layout (comportement inchangé). Commercial ou
    industriel : RIEN — la production vient de CIQ109 (calepinage retenu lu
    par le moteur C&I) et l'économie du moteur C&I ; l'économie de l'outil de
    toiture n'est jamais imprimée sur un devis MT (C2-VA-01, C2-VB-01).
    """
    if (mode_installation or '').strip().lower() in MARCHES_CI:
        return {}
    resultat = resultat or {}
    cles = {}
    if resultat.get('annualKwh') is not None:
        # ACAL101 — ARRONDIE (jamais tronquée : 8843,66 → 8844) et MARQUÉE :
        # la provenance remplace l'égalité numérique devinée au rendu.
        cles['production_annuelle'] = int(round(float(resultat['annualKwh'])))
        cles['production_source'] = PRODUCTION_CALEPINAGE
    if resultat.get('savings') is not None:
        cles['economies_annuelles'] = int(resultat['savings'])
    return cles


def entrees_du_moteur(cles=None):
    """Les clés qui NOURRISSENT le moteur — déclarées, jamais codées en dur.

    Sans argument : l'ensemble complet. Avec ``cles`` (ce qu'un PATCH vient de
    poser) : l'INTERSECTION, c'est-à-dire « faut-il relancer les études ? ».

    Une clé absente du schéma n'est jamais du moteur (elle ne passe pas
    :func:`valider` de toute façon).
    """
    du_moteur = {cle for cle, regle in SCHEMA.items() if regle.get('moteur')}
    if cles is None:
        return du_moteur
    return du_moteur & set(cles)


def valider(etude_params):
    """Les reproches faits à un bloc ``etude_params`` — ``[]`` quand tout va.

    PURE, sans base, sans exception : c'est une LISTE de messages FR, pour que
    l'appelant décide (400 côté endpoint, avertissement côté outillage).

    Deux reproches seulement, et ils sont structurels :

    * une clé de TÊTE inconnue du schéma — c'est ainsi qu'un champ inventé
      côté client se glissait dans les entrées du PDF ;
    * une valeur du mauvais TYPE — une liste de factures rendue en texte, un
      bloc horaire rendu en liste.

    ``None`` est TOUJOURS toléré : une clé absente et une clé nulle disent la
    même chose (« pas calculable » — règle Z2).
    """
    if etude_params is None:
        return []
    if not isinstance(etude_params, dict):
        return ['`etude_params` doit être un objet JSON.']
    reproches = []
    for cle, valeur in etude_params.items():
        regle = SCHEMA.get(cle)
        if cle in CLES_RETIREES_CI_V1:
            reproches.append(
                "Clé retirée de l'étude : « %s » (CIQ129) — %s."
                % (cle, CLES_RETIREES_CI_V1[cle]))
            continue
        if regle is None:
            reproches.append(
                "Clé inconnue de l'étude : « %s ». Le schéma "
                '(`domain/etude_schema.py`) est la seule porte.' % cle)
            continue
        if valeur is None:
            continue
        if isinstance(valeur, bool) and bool not in regle['type']:
            reproches.append(
                '« %s » : un booléen n\'est pas une valeur admise ici.' % cle)
            continue
        if not isinstance(valeur, regle['type']):
            reproches.append(
                '« %s » : type %s inattendu (attendu : %s).'
                % (cle, type(valeur).__name__,
                   ' ou '.join(t.__name__ for t in regle['type'])))
            continue
        if cle == 'factures_mensuelles_reelles':
            reproches.extend(_reproches_factures(valeur))
        elif cle == 'tarif_declare':
            from apps.ventes.tarif_ci import reproches_tarif_declare
            reproches.extend(reproches_tarif_declare(valeur))
    return reproches


def _reproches_factures(factures):
    """ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — une facture mensuelle RÉELLE
    ne peut pas valoir moins que ses deux lignes fixes (location du compteur +
    entretien du branchement, ``bareme.charges_fixes_ttc`` : 39,94 MAD TTC/mois
    en 2026), dues même à zéro kWh.

    DEV-202609-0108 est parti au client avec une série dont l'hiver valait
    1 MAD/mois (``estimerMois(1, 1600)``) : l'économie, la facture actuelle et
    le retour en découlaient. Zéro reste admis (mois sans relevé) ; le
    contrôle de TYPE des éléments n'est pas l'objet de cette garde.
    """
    from apps.ventes.quote_engine import bareme
    plancher = bareme.charges_fixes_ttc()
    fautifs = [i + 1 for i, v in enumerate(factures)
               if isinstance(v, (int, float)) and not isinstance(v, bool)
               and 0 < v < plancher]
    reproches = []
    if fautifs:
        reproches.append(
            '« factures_mensuelles_reelles » : facture mensuelle inférieure '
            'aux lignes fixes du compteur (%.2f MAD TTC/mois) au(x) mois %s — '
            'une facture réelle ne peut pas être aussi basse. Corrigez la '
            'saisie (0 si le mois est inconnu).'
            % (plancher, ', '.join(map(str, fautifs))))
    return reproches


def cles_refusees_pour(proprietaire, cles):
    """Les clés RÉSERVÉES que ``proprietaire`` n'a pas le droit d'écrire.

    Une clé d'ENTRÉE est écrivable par n'importe quelle étape (c'est un choix
    du commercial, il peut arriver de plusieurs écrans). Une clé DÉRIVÉE
    n'appartient qu'à l'étape QUI LA CALCULE : la laisser écrire par une autre,
    c'est exactement le mécanisme par lequel un chiffre du moteur se faisait
    remplacer par un chiffre d'écran.

    QJR222 — LE CONTRÔLE COUVRE AUSSI LES ENTRÉES DÉCLARÉES EXCLUSIVES
    (``_cle(..., exclusif=True)``). Il ne portait que sur la NATURE, si bien
    qu'une entrée appartenant à une ÉTAPE — ``provenance``, l'estampille de
    dérive DC11 posée par le pipeline — était écrivable depuis le navigateur.
    L'extension est NOMMÉE clé par clé (et non appliquée à tout propriétaire
    déclaré) parce que le calepinage écrit LÉGITIMEMENT des entrées dont le
    propriétaire est l'écran (``scenario``, ``toiture``…) : un contrôle
    aveugle les refuserait et casserait la resynchro.

    ``proprietaire=None`` (aucune étape déclarée) ⇒ AUCUNE clé réservée n'est
    admise : un écrivain anonyme ne pose que des entrées ordinaires.
    """
    refusees = []
    for cle in cles:
        regle = SCHEMA.get(cle)
        if regle is None:
            continue
        if regle['nature'] != DERIVEE and not regle.get('exclusif'):
            continue
        if regle['proprietaire'] != proprietaire:
            refusees.append(cle)
    return refusees


def fusionner(bloc, *, proprietaire=None, **cles):
    """QJR62 — la FUSION seule : valide, refuse, fusionne. AUCUNE écriture.

    Sortie de :func:`ecrire` pour les appelants qui persistent ``etude_params``
    EN MÊME TEMPS que d'autres colonnes dans un seul ``save``
    (``sync_devis_from_layout`` écrit ``roof_layout`` + ``layout_hash`` +
    ``etude_params`` d'un bloc, et ``update_fields`` y EXCLUT ``statut`` — le
    scinder en deux écritures ferait deux allers-retour et deux fenêtres de
    course pour rien). La RÈGLE reste UNE : ils appellent tous cette fonction,
    seule la persistance diffère.

    Mêmes refus que :func:`ecrire` (``ValueError``), même sémantique du
    ``None`` (retirer la clé). Rend le nouveau bloc, sans toucher l'entrée.
    """
    refusees = cles_refusees_pour(proprietaire, cles)
    if refusees:
        raise ValueError(
            'Clé(s) réservée(s) %s : seule l\'étape PROPRIÉTAIRE peut les '
            'écrire (propriétaire déclaré : %s).'
            % (', '.join(sorted(refusees)), proprietaire or 'aucun'))
    reproches = valider(cles)
    if reproches:
        raise ValueError(' ; '.join(reproches))

    resultat = dict(bloc or {})
    for cle, valeur in cles.items():
        if valeur is None:
            resultat.pop(cle, None)
        else:
            resultat[cle] = valeur
    return resultat


def ecrire(devis, *, proprietaire=None, **cles):
    """L'UNIQUE écrivain d'``etude_params`` — il FUSIONNE, il ne remplace pas.

    C'EST LA DIFFÉRENCE QUI COMPTE. Un PATCH partiel écrasait le bloc entier :
    toute clé que l'émetteur ne reconstruisait pas lui-même
    (``factures_mensuelles_reelles``, ``gamme``, et tout ce que les quatre
    rafraîchisseurs du serveur avaient écrit) DISPARAISSAIT à la sauvegarde
    suivante. Ici, seules les clés REÇUES bougent ; les autres sont intouchées,
    bit à bit.

    ``proprietaire`` — l'étape qui écrit (voir les constantes du module). Une
    clé DÉRIVÉE dont elle n'est pas propriétaire lève ``ValueError``, jamais un
    silence : c'est l'appelant qui doit dire d'où vient son chiffre.

    Une valeur ``None`` RETIRE la clé (règle Z2 : une étude qui n'est plus
    calculable est retirée, jamais laissée périmée).

    Persiste en ``update_fields=['etude_params']`` : ni statut, ni ligne, ni
    total ne sont touchés (règle #4). Rend le bloc résultant.
    """
    bloc = fusionner(getattr(devis, 'etude_params', None) or {},
                     proprietaire=proprietaire, **cles)
    devis.etude_params = bloc
    if getattr(devis, 'pk', None) is not None:
        devis.save(update_fields=['etude_params'])
        # QJR545 — ``update_fields`` n'écrit pas ``updated_at`` : le jeton
        # d'édition avance explicitement (verrou optimiste).
        from apps.ventes.domain.verrou_devis import toucher
        toucher(devis)
    return bloc
