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


def sert_les_deux(demande_les_deux, *, a_reseau, a_hybride, a_batterie):
    """QJR97 — LA GARDE ANTI-MENSONGE, écrite UNE fois. Forme booléenne.

    « Les deux (Sans + Avec) » promet au client une COMPARAISON : l'option
    « sans » a besoin d'un onduleur RÉSEAU, l'option « avec » d'un onduleur
    HYBRIDE **et** d'une BATTERIE. Un document qui déclare les deux sans
    pouvoir en servir une moitié ment — et le moteur PDF, qui lit cette
    déclaration (PV86/QF6), rendrait une comparaison dont un côté est vide.

    CE QUE CETTE FONCTION FERME. La règle vivait EN ENTIER à DEUX endroits —
    à la création (``pipeline.ecrire_etude_params``, sur les DÉSIGNATIONS
    composées) et à la resynchronisation (sur les LIGNES du devis) — avec deux
    formulations différentes des mêmes conditions. Deux écritures d'une même
    règle finissent toujours par diverger ; celle-ci décide de ce qu'un client
    voit sur sa proposition.

    ``demande_les_deux`` est la DEMANDE (le scénario voulu par ce devis-là) ;
    les trois autres décrivent ce que la composition ou les lignes servent
    RÉELLEMENT.
    """
    return bool(demande_les_deux and a_reseau and a_hybride and a_batterie)


def scenario_servable(demande_les_deux, *, a_reseau, a_hybride, a_batterie):
    """QJR97 — LE LIBELLÉ à ranger dans ``etude_params['scenario']``.

    Jumelle de :func:`sert_les_deux` : « Les deux » quand les deux côtés sont
    servis, sinon le libellé MONO honnête — « Avec batterie » seulement quand
    l'équipement peut réellement le servir (onduleur hybride ET batterie).
    Fonction PURE : elle ne lit ni base ni registre. La DÉCLARATION humaine,
    elle, prime toujours et se lit par :func:`scenario_effectif` — l'appelant
    enveloppe donc ce résultat, comme il le faisait déjà.
    """
    if sert_les_deux(demande_les_deux, a_reseau=a_reseau, a_hybride=a_hybride,
                     a_batterie=a_batterie):
        return SCENARIO_LES_DEUX
    return _scenario_stocke(bool(a_batterie and a_hybride))


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


def ligne_panneau_dominante(lignes):
    """La ligne PANNEAU qui porte le plus grand nombre de panneaux, ou ``None``.

    QJR217 — c'est l'argument que :func:`domain.overrides.preseance_nb_panneaux`
    attend : la ligne sur laquelle un ``quantite_manuelle`` du vendeur peut
    contredire la surcharge de NIVEAU DEVIS. Le critère de dominance est celui
    que ``domain/resynchronisation`` applique déjà (le plus grand compte), et le
    prédicat panneau est le lecteur unique ``solar_design.is_panel`` — jamais
    une seconde définition.
    """
    from apps.ventes import solar_design as _sd

    panneaux = [
        li for li in lignes
        if _sd.is_panel(getattr(li, 'designation', '') or '',
                        getattr(getattr(li, 'produit', None), 'nom', '') or '')]
    if not panneaux:
        return None
    return max(panneaux,
               key=lambda li: float(getattr(li, 'quantite', 0) or 0))


def puissance_kwc_du_devis(devis, *, avertissements=None):
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

    QJR217 — LA RÈGLE DE PRÉSÉANCE R4-A S'APPLIQUE ICI, ET ELLE LE DIT.
    ``domain.overrides.preseance_nb_panneaux`` écrivait la règle en trois
    phrases et n'avait AUCUN appelant de production : quand une ligne panneau
    VERROUILLÉE (``quantite_manuelle``) contredisait ``taille.nb_panneaux``, ce
    lecteur suivait silencieusement le niveau DEVIS pendant que le moteur PDF
    (``quote_engine.builder``, qui ne lit que ``taille.kwc``) suivait les
    LIGNES — deux consommateurs de kWc qui divergeaient sans que personne ne
    le sache. Désormais : le verrou de ligne gagne pour la quantité de CETTE
    ligne (phrase 1), le chemin de niveau devis reste LU tel quel par
    ``decider_taille`` (phrase 2 — cette étape ne passe pas ici), et un
    désaccord émet l'avertissement FR qui NOMME la ligne (phrase 3) dans
    ``avertissements`` quand une liste est fournie.

    LECTURE PURE (règle #4).
    """
    from apps.ventes.domain.overrides import (
        SOURCE_DEVIS, effectif, preseance_nb_panneaux,
    )
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
    verdict = preseance_nb_panneaux(
        devis, ligne_panneau_dominante(lignes),
        avertissements=avertissements)
    # Seule la préséance de NIVEAU DEVIS déplace le kWc : quand la ligne est
    # verrouillée (R4-A phrase 1), le kWc décrit ce qui est RÉELLEMENT vendu,
    # c'est-à-dire les lignes — et l'avertissement vient d'être émis.
    if (verdict.source_ligne == SOURCE_DEVIS
            and verdict.cible_dimensionnement and watt_lu):
        try:
            return round(
                int(verdict.cible_dimensionnement) * float(watt_lu) / 1000, 2)
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
