"""Scénario, option recommandée, puissance — ce qu'un devis DÉCLARE.

Les trois scénarios batterie, le scénario effectif et l'option recommandée
d'un devis — tous deux lus via le REGISTRE de surcharges (QJR64), pour
qu'une déclaration humaine survive à tout recalcul aval — et l'UNIQUE
propriétaire du kWc d'un devis (QJR63) : son écriture estampillée
(`poser_puissance_kwc`) et sa lecture (`puissance_kwc_du_devis`).

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


# PVSCE — vocabulaire du choix de scénario, tel que le moteur PDF le LIT dans
# ``etude_params['scenario']`` (quote_engine/builder.py, QF6). Le LIBELLÉ
# FRANÇAIS est le contrat : un 'reseau'/'avec_batterie' n'y serait pas reconnu
# et le moteur retomberait sur l'inférence par les lignes — c'est-à-dire sur le
# repli qu'on cherche précisément à ne plus dépendre.
SCENARIO_SANS_BATTERIE = 'Sans batterie'
SCENARIO_AVEC_BATTERIE = 'Avec batterie'
#: U2 — devis à DEUX OPTIONS : le client compare « sans » et « avec » dans un
#: seul document. Libellé RECONNU TEL QUEL par le moteur PDF
#: (``quote_engine/builder.py``) : ne pas le reformuler.
SCENARIO_LES_DEUX = 'Les deux (Sans + Avec)'


def _scenario_stocke(avec_batterie):
    """Le libellé à ranger dans ``etude_params['scenario']``.

    On ne stocke « Avec batterie » que quand l'équipement peut réellement le
    servir (onduleur hybride ET batterie) : un choix stocké que les lignes ne
    peuvent pas honorer serait un mensonge que le moteur devrait défaire.
    """
    return SCENARIO_AVEC_BATTERIE if avec_batterie else SCENARIO_SANS_BATTERIE


def scenario_effectif(devis, auto):
    """QJR64 — LE SCÉNARIO QUI FAIT FOI : le registre d'abord, la dérivation
    moteur seulement en son ABSENCE.

    CE QUI ÉTAIT FAUX. ``etude_params['scenario']`` était protégé par un CAS
    PARTICULIER CODÉ EN DUR dans la fusion ``etude_extra`` de
    ``build_devis_auto``, et RE-DÉRIVÉ sans condition par la resynchro : selon
    le chemin emprunté, un « Les deux (Sans + Avec) » déclaré par un humain
    pouvait redevenir « Avec batterie » sans que personne ne l'ait demandé —
    et le PDF cessait alors de rendre la comparaison.

    LA RÈGLE (décision fondateur D12) : ``scenario`` est un chemin du REGISTRE
    de surcharges. Un scénario DÉCLARÉ survit à TOUT recalcul aval ; la
    dérivation moteur ne s'applique qu'en son absence. Un changement de marché
    PROPOSE (il pose un override, ou n'en pose pas), il n'écrase plus.

    Une valeur surchargée qui n'est pas un scénario connu est IGNORÉE (on
    retombe sur ``auto``) : une surcharge illisible ne doit pas rendre un
    document muet.
    """
    from apps.ventes.domain.overrides import effectif

    connus = (SCENARIO_SANS_BATTERIE, SCENARIO_AVEC_BATTERIE,
              SCENARIO_LES_DEUX)
    try:
        valeur, source = effectif(devis, 'scenario', auto)
    except Exception:  # noqa: BLE001 — un registre illisible ne décide rien
        return auto
    if source == 'auto' or valeur not in connus:
        return auto
    return valeur


def recommended_option_effective(devis, auto):
    """QJR64 — jumelle de :func:`scenario_effectif` pour l'option MISE EN AVANT.

    ``recommended_option`` désigne laquelle des deux options le document
    recommande. Même règle : la déclaration du vendeur (registre) prime, la
    dérivation moteur ne joue qu'à défaut. Une valeur inconnue est ignorée.
    """
    from apps.ventes.domain.overrides import effectif

    connus = (SCENARIO_SANS_BATTERIE, SCENARIO_AVEC_BATTERIE)
    try:
        valeur, source = effectif(devis, 'recommended_option', auto)
    except Exception:  # noqa: BLE001 — un registre illisible ne décide rien
        return auto
    if source == 'auto' or valeur not in connus:
        return auto
    return valeur


def puissance_kwc_du_devis(devis):
    """QJR63 — LE kWc D'UN DEVIS. Une règle, un propriétaire, deux sources.

    CE QUI ÉTAIT FAUX. ``etude_params['puissance_kwc']`` avait QUATRE
    écrivains : ``build_devis_from_layout`` (depuis le layout),
    ``sync_devis_from_layout`` (depuis le layout, MÊME quand la règle de
    plafond de variante avait fait atterrir le devis sur un AUTRE compte),
    ``build_devis_auto`` (depuis ``target_kwc`` / la taille souhaitée du lead),
    et une RE-DÉRIVATION au rendu par ``quote_engine.builder`` (PVUNI, depuis
    les LIGNES — qui recalibrait et gagnait). Le kWc STOCKÉ pouvait donc
    décrire une installation NON VENDUE, et ``models.Devis.save`` le figeait
    ensuite pour toujours dans ``prix_par_kwc``.

    LA RÈGLE, désormais unique :

    1. le REGISTRE de surcharges (décision fondateur D12) — ``taille.kwc`` s'il
       est posé, sinon ``taille.nb_panneaux`` × le wattage RÉELLEMENT LU sur
       les lignes ;
    2. sinon la DÉRIVATION DEPUIS LES LIGNES —
       ``quote_engine.builder.panneaux_et_watt_lu``, exactement celle de PVUNI
       (« les lignes sont la source unique ») ; jamais une seconde dérivation.

    ``None`` quand rien n'est lisible : aucun panneau, ou un compte sans
    wattage. On n'invente pas un kWc à partir d'un wattage supposé (M3), et le
    calepinage 3D n'est PAS une source ici — il modélise à 720 W constants,
    ce n'est pas le panneau vendu.

    LECTURE PURE (règle #4).
    """
    from apps.ventes.domain.overrides import effectif
    from apps.ventes.quote_engine.builder import panneaux_et_watt_lu

    lignes = [li for li in devis.lignes.select_related(
        'produit', 'produit__fiche_technique').all()
        if getattr(li, 'type_ligne', 'produit') == 'produit'
        and not getattr(li, 'optionnelle', False)]
    nb_lu, watt_lu = panneaux_et_watt_lu(lignes)
    auto = (round(nb_lu * watt_lu / 1000, 2)
            if nb_lu > 0 and watt_lu else None)

    kwc_surcharge, source = effectif(devis, 'taille.kwc', None)
    if source != 'auto' and kwc_surcharge:
        try:
            return round(float(kwc_surcharge), 2)
        except (TypeError, ValueError):
            pass
    nb_surcharge, source_nb = effectif(devis, 'taille.nb_panneaux', None)
    if source_nb != 'auto' and nb_surcharge and watt_lu:
        try:
            return round(int(nb_surcharge) * float(watt_lu) / 1000, 2)
        except (TypeError, ValueError):
            pass
    return auto


def poser_puissance_kwc(devis):
    """QJR63 — L'UNIQUE ÉCRIVAIN de ``etude_params['puissance_kwc']``.

    La clé devient un CACHE de :func:`puissance_kwc_du_devis` : elle n'est plus
    une valeur d'origine différente selon le chemin qui l'a posée. Écrite par
    l'écrivain unique d'``etude_params`` (QJR62), donc en fusion et sans
    toucher ni statut, ni ligne, ni total (règle #4).

    ``None`` (rien de lisible) RETIRE la clé — règle Z2 : mieux vaut une
    absence qu'un kWc qui décrit une autre installation. Ne lève jamais.
    """
    from apps.ventes.domain.etude_schema import CALEPINAGE, ecrire
    try:
        ecrire(devis, proprietaire=CALEPINAGE,
               puissance_kwc=puissance_kwc_du_devis(devis))
    except Exception:  # noqa: BLE001 — un cache raté ne casse jamais un devis
        logger.warning('puissance_kwc non posée sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
    return (devis.etude_params or {}).get('puissance_kwc')
