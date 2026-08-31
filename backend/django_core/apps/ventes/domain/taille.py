"""Taille — combien de panneaux, et pourquoi on refuse d'en dire un.

La décision de DIMENSION prise depuis le lead : la phase client retenue
pour le dimensionnement, le compte de panneaux issu de l'étude horaire, la
recommandation rendue, le compte résidentiel, et les quatre MOTIFS de refus
avec leurs libellés — un devis automatique qui ne peut pas être dimensionné
le DIT, il n'invente pas une taille.

QJR75 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``. Les corps
sont recopiés à l'identique ; la SEULE retouche est mécanique et obligatoire :
un corps descendu d'un cran (`apps/ventes/` → `apps/ventes/domain/`) voit son
point de départ relatif descendre avec lui, donc `from .x import y` devient
`from ..x import y` — MÊME cible (`apps.ventes.x`), au caractère près.

ORDRE DE CHARGEMENT (voir ``domain/bordereau.py``) : ``services.py`` importe
``domain/`` à la toute fin ; un module de ``domain/`` importe en BAS de fichier
les noms qu'il lit ailleurs. Quel que soit le module chargé le premier, chaque
attribut lu à l'import existe déjà.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom
précis (``assertLogs('apps.ventes.services')``). Un déplacement pur ne change
pas le nom sous lequel une ligne de journal est émise.
"""
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


# ── Copilote — devis AUTOMATIQUE (résidentiel) ───────────────────────────────
# Le Copilote ne doit JAMAIS créer un devis vide : il passe toujours par ce
# dimensionnement automatique, puis délègue à build_devis_from_layout
# (catalogue, numérotation, brouillon).
#
# ORDRE FONDATEUR (29/08/2026) — « ALL sizing should go through the new sizing
# tool, and i said ALL sizing ». La règle historique « 8 panneaux par tranche de
# 900 MAD de facture d'hiver » (port de ``estimerPanneaux`` de solar.js) NE
# DIMENSIONNE PLUS AUCUN DEVIS : elle a été SUPPRIMÉE de ce module. Deux leads
# portant la MÊME facture repartaient sinon avec deux tailles issues de deux
# règles différentes selon qu'un profil d'appel avait été rempli ou non
# (incident test18/test19 : 15/14 panneaux par le moteur contre 16/16 par la
# tranche). Désormais : le moteur horaire dimensionne DÈS QU'UNE DONNÉE DE
# CONSOMMATION EXISTE (la facture d'hiver suffit), et seule une puissance
# demandée — ``target_kwc`` pour ce devis, ou ``taille_souhaitee_kwc`` sur la
# fiche — reste souveraine (le commercial sait ce qu'il vend).

_AUTO_PANEL_WATT = 710        # Wc — panneau catalogue par défaut (cf. solar.js)


class AutoDevisError(Exception):
    """Le devis automatique ne peut pas être dimensionné (donnée manquante ou
    marché non géré). L'endpoint la traduit en 422 et l'agent demande la donnée
    (ou oriente vers le générateur) plutôt que de produire un devis vide."""

    def __init__(self, message, *, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def phase_client_pour_dimensionnement(lead):
    """Raccordement normalisé du lead (mono/tri/None) — PVCOMPAT, une seule
    lecture. Isolé pour être appelable AVANT le dimensionnement, alors que
    ``build_devis_auto`` ne résout la phase qu'au moment de composer."""
    from apps.ventes.compatibilites import normaliser_phase
    return normaliser_phase(getattr(lead, 'raccordement', None))


#: Motifs d'ABSTENTION du moteur horaire — la donnée exacte qui manque, pour
#: que ``build_devis_auto`` puisse la NOMMER au commercial au lieu de retomber
#: en silence sur une autre règle (ordre fondateur du 29/08/2026 : il n'y a
#: plus d'autre règle).
MOTIF_FACTURE_ABSENTE = 'facture_absente'
MOTIF_LOCALISATION = 'localisation_inconnue'
MOTIF_CATALOGUE = 'catalogue_incomplet'
MOTIF_MOTEUR_INDISPONIBLE = 'moteur_indisponible'

#: Ce que l'agent doit demander pour chaque motif : ``{motif: (message, champ)}``.
#: Un refus NOMME la donnée manquante — c'est ce qui remplace l'ancien repli
#: silencieux sur la règle des 900 DH/mois.
_REFUS_DIMENSIONNEMENT = {
    MOTIF_FACTURE_ABSENTE: (
        "Données insuffisantes pour dimensionner le devis : renseignez la "
        "facture d'électricité d'hiver (ou la taille souhaitée en kWc) du lead.",
        'facture_hiver'),
    MOTIF_LOCALISATION: (
        "Le chantier n'est pas localisé : la ville du lead est vide ou n'est "
        "pas reconnue (villes du Maroc et leurs orthographes courantes), et "
        "aucune coordonnée GPS n'est posée — sans localisation, le "
        "productible solaire du site est inconnu et aucune taille ne peut "
        "être calculée. Corrigez la ville ou posez le point GPS sur la fiche.",
        'ville'),
    MOTIF_CATALOGUE: (
        "Le catalogue de la société ne permet de composer aucune installation "
        "résidentielle pour ce lead : complétez-le (panneau, onduleur) puis "
        "relancez le devis automatique.",
        'catalogue'),
    MOTIF_MOTEUR_INDISPONIBLE: (
        "Le moteur de dimensionnement est momentanément indisponible : le "
        "devis n'a pas été créé plutôt que d'être dimensionné par une autre "
        "règle. Réessayez, ou précisez la taille souhaitée (kWc) du lead.",
        'dimensionnement'),
}


def _refus_dimensionnement(motif):
    """L'``AutoDevisError`` (→ 422) correspondant à un motif d'abstention.

    Motif inconnu ⇒ on refuse quand même, en le citant : on ne crée JAMAIS un
    devis dont la taille viendrait d'ailleurs que du moteur.
    """
    message, champ = _REFUS_DIMENSIONNEMENT.get(
        motif,
        ("Le devis n'a pas pu être dimensionné (motif « %s »)." % motif,
         'dimensionnement'))
    return AutoDevisError(message, field=champ)


def _panneaux_dimensionnement_horaire(*, lead, company, phase):
    """``(nb_panneaux, panel_watt, source, avec)`` recommandés par le moteur.

    C'EST LE SEUL DIMENSIONNEMENT du devis automatique quand aucune puissance
    n'est demandée (ordre fondateur du 29/08/2026). Il n'exige PAS un profil
    d'appel rempli : la seule donnée de consommation nécessaire est la facture
    d'hiver du lead.

    D'OÙ VIENNENT LES kWh QUAND LE LEAD N'A QU'UNE FACTURE. De
    ``etude_horaire.profil_depuis_factures`` → ``serie_mad_mensuelle`` (la
    facture d'hiver répétée sur les douze mois, remplacée par la facture d'été
    sur mai→octobre quand ``ete_differente`` en déclare une distincte) →
    ``serie_kwh_depuis_mad``, qui inverse le VRAI barème ONEE
    (``quote_engine.bareme.kwh_depuis_facture_mad`` : tranches progressives/
    sélectives, location + entretien, TPPAN) — JAMAIS une division par un prix
    moyen, jamais un tarif écrit ici.

    DÉFAUT DE FORME, DOCUMENTÉ (QJR10 / décision fondateur D4 du 29/08/2026).
    Sans réponse d'occupation sur la fiche, la silhouette 24 h est celle du
    DÉFAUT RÉSIDENTIEL FONDATEUR (``courbes_journalieres.DEFAUT_RESIDENTIEL``
    = présence en journée), exactement comme sur l'aperçu écran : le même lead
    ne peut plus être dimensionné sur deux journées différentes selon le chemin
    emprunté. Un équipement déclaré sans sa grandeur n'ajoute aucune couche.
    C'est le SEUL défaut : rien d'autre n'est supposé.

    Traduit la fiche du lead en entrées du dimensionnement, puis lit la
    recommandation. ``panel_watt`` est le wattage du panneau RÉEL sur lequel le
    balayage a décidé : l'appelant doit composer avec le MÊME, sinon la
    puissance livrée ne serait pas celle qui a été évaluée.

    L-2OPT — ``avec`` est le QUATRIÈME élément, et c'est la nouveauté : la
    recommandation de l'axe AVEC BATTERIE (``recommandation_avec``, le balayage
    CONJOINT champ × stockage de DIM2), rendue sous la forme
    ``{'nb_panneaux', 'kwc', 'panel_watt', 'batterie_kwh'}``. Ce gagnant
    existait depuis DIM2 mais n'alimentait AUCUN chemin de génération de
    lignes — il ne servait qu'à l'affichage. ``None`` quand le moteur n'a
    trouvé aucune configuration avec batterie livrable : l'appelant compose
    alors l'option « avec » sur le MÊME champ que l'option « sans »
    (comportement historique — jamais un chiffre inventé pour combler le trou).

    IMPOSSIBILITÉ ⇒ ``(0, None, <motif>, None)`` où ``<motif>`` est l'un des
    ``MOTIF_*`` ci-dessus — la donnée qui manque, NOMMÉE. Il n'y a plus de
    repli : l'appelant refuse le devis en citant ce motif (ordre fondateur —
    « the 900dh path must no longer decide ANY devis »). Ne lève jamais.
    """
    try:
        from apps.ventes.dimensionnement import recommander_taille
        from apps.ventes.domain.entrees import entrees_depuis_lead

        # QJR42 — LECTURE UNIQUE de la fiche : le MÊME adaptateur que le chemin
        # devis (``EntreesMoteur``), donc la même facture, la même
        # localisation, la même occupation (QJR10 / D4 — défaut PRÉSENCE) et
        # les 15 champs d'équipement du sélecteur CRM (QJR9). Il n'y a plus de
        # seconde traduction lead → entrées dans ce module.
        entrees = entrees_depuis_lead(lead, company)
        conso = entrees.conso_kwh_mensuelles if entrees else None
        if not conso:
            return 0, None, MOTIF_FACTURE_ABSENTE, None

        resultat = recommander_taille(
            company=entrees.company, conso_kwh_mensuelles=conso,
            ville=entrees.ville, lat=entrees.lat, lon=entrees.lon,
            occupation=entrees.occupation, equipements=entrees.equipements,
            phase=phase, source_conso=entrees.source_conso,
            jour_reference=entrees.jour_reference,
            # QJR46 — le barème de la SOCIÉTÉ, celui que le devis appliquera.
            tranches=entrees.tranches,
            charges_fixes_mad=entrees.charges_fixes_mad)
        recommandation = resultat.get('recommandation')
        if not recommandation:
            # Le tableau est vide pour DEUX raisons distinctes, et le
            # commercial n'a pas le même geste à faire : un ancrage de
            # productible introuvable se corrige sur la FICHE (ville ou tracé
            # GPS), un catalogue incomplet se corrige dans le CATALOGUE. On
            # relit donc la localisation — lecture en table/cache, pas un
            # second dimensionnement — pour nommer la bonne.
            from apps.parametres.pvgis_profils import productible_mensuel
            situe = productible_mensuel(
                ville=entrees.ville, lat=entrees.lat, lon=entrees.lon)
            return (0, None,
                    MOTIF_CATALOGUE if situe else MOTIF_LOCALISATION, None)
        return (int(recommandation['panneaux']),
                recommandation.get('panel_watt'), 'moteur_horaire',
                _recommandation_avec_rendue(resultat.get('recommandation_avec')))
    except Exception:  # noqa: BLE001 — l'appelant REFUSE le devis (il n'y a
        # plus de règle de repli) : on ne masque pas la panne, on la nomme.
        logger.warning('dimensionnement horaire indisponible', exc_info=True)
        return 0, None, MOTIF_MOTEUR_INDISPONIBLE, None


def _recommandation_avec_rendue(recommandation_avec):
    """L-2OPT — la ligne ``recommandation_avec`` du moteur, réduite à ce que la
    composition sait consommer : ``{nb_panneaux, kwc, panel_watt,
    batterie_kwh}``.

    ``None`` dès que la recommandation est absente ou ne porte pas de nombre de
    panneaux exploitable — REPLI EXPLICITE : l'appelant compose alors l'option
    « avec » sur le champ de l'option « sans », comme aujourd'hui. Aucun
    chiffre n'est ni inventé ni arrondi ici : tout vient du moteur.
    """
    if not isinstance(recommandation_avec, dict):
        return None
    try:
        panneaux = int(recommandation_avec.get('panneaux') or 0)
    except (TypeError, ValueError):
        return None
    if panneaux <= 0:
        return None
    batterie = recommandation_avec.get('batterie_kwh')
    try:
        batterie = float(batterie) if batterie not in (None, '') else None
    except (TypeError, ValueError):
        batterie = None
    return {
        'nb_panneaux': panneaux,
        'kwc': recommandation_avec.get('kwc'),
        'panel_watt': recommandation_avec.get('panel_watt'),
        'batterie_kwh': batterie if batterie and batterie > 0 else None,
    }


def _residential_panel_count(*, taille_kwc=None, panel_watt=_AUTO_PANEL_WATT):
    """CONVERSION SEULE : une puissance demandée (kWc) → un nombre de panneaux.

    Ce n'est plus un dimensionnement — c'est de l'arithmétique. La branche
    « facture d'hiver ÷ 900 MAD × 8 panneaux » a été RETIRÉE le 29/08/2026
    (ordre fondateur « ALL sizing should go through the new sizing tool ») :
    une facture se dimensionne désormais par ``_panneaux_dimensionnement_horaire``
    et par rien d'autre. Ne subsiste ici que le chemin SOUVERAIN — la puissance
    que le commercial demande (``target_kwc``) ou que la fiche du lead porte
    (``taille_souhaitee_kwc``).

    U1 — le compte est un PLAFOND (``plafond_panneaux``), comme
    ``panneauxPourKwc`` / ``composition_residentielle`` : on ne descend jamais
    sous la puissance vendue. Renvoie 0 sans taille exploitable (le caller lève
    alors ``AutoDevisError``)."""
    if taille_kwc not in (None, '') and Decimal(str(taille_kwc)) > 0:
        return max(1, plafond_panneaux(float(taille_kwc) * 1000 / panel_watt))
    return 0


# ── PONT M3 : nom hébergé ailleurs ───────────────────────────────────────────
# Import EN BAS DE FICHIER, visant le module qui PORTE le corps.
from apps.ventes.domain.catalogue import plafond_panneaux  # noqa: E402,F401
