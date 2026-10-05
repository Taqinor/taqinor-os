# -*- coding: utf-8 -*-
"""``apps.ventes.domain.pipeline`` — LES ÉTAPES du parcours devis.

Le parcours devis a CINQ origines (l'écran générateur, le calepinage 3D, le
devis automatique depuis un lead, le tunnel du site, la resynchronisation) et,
jusqu'à M4, chacune recomposait à sa façon. Ce module est l'endroit où les
étapes deviennent COMMUNES, une par une, sans big-bang :

    resoudre_entrees → decider_taille → composer → verifier
        → ecrire_lignes → ecrire_etude_params → rafraichir_etudes
        → marge_snapshot + conception électrique

CETTE FLÈCHE EST UN ORDRE, PAS UN TUYAU DE DONNÉES (QJR243 (b)). L'étape 2 ne
CONSOMME pas la sortie de l'étape 1 : elle rend la cible déjà arrêtée par
l'appelant, ou demande au dimensionneur horaire, qui relit la fiche par le MÊME
adaptateur (``entrees_depuis_lead``). Le paramètre ``entrees`` que l'étape 2
déclarait sans jamais le lire a donc été retiré ; la sortie de l'étape 1, elle,
reste rendue par ``appliquer`` (clé ``entrees`` du compte rendu).

QJR80 pose la TROISIÈME étape, ``composer``, et elle seule. Les autres étapes
existent déjà, à leur place (``domain/entrees``, ``domain/taille``,
``domain/geometrie``, ``domain/lignes``, ``domain/etude_schema``,
``domain/etudes``) ; leur ORDONNANCEMENT est QJR85, les bascules des cinq
chemins sont M5. Rien ici n'appelle un chemin : ce sont les chemins qui
appellent ici.

RÈGLE D'IMPORT (cf. ``domain/__init__.py``) : les noms lus dans d'autres
modules de ``domain/`` sont importés EN BAS de ce fichier, en visant le module
qui porte le corps — jamais la façade ``services.py``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from dataclasses import dataclass
from decimal import Decimal
import logging

from django.db import transaction

# Alias module-local : les tests sans base (test_qjr_pipeline_appliquer)
# remplacent ``pipeline._atomic`` par un enregistreur no-op sans toucher au
# module ``django.db.transaction`` partagé.
_atomic = transaction.atomic

logger = logging.getLogger("apps.ventes.services")


# ── QJR85 — `appliquer()` : L'ORDRE UNIQUE DES HUIT ÉTAPES ──────────────────
#
# Constat QB85 (audit L3 du 29/08/2026) : les CINQ origines d'un devis
# enchaînent les mêmes étapes, mais chacune dans SON ordre, avec SES oublis.
# Ce n'est pas une divergence de règles — les règles, elles, viennent d'être
# rendues communes (QJR80 `composer`, QJR82 `verifier`, QJR83/QJR84
# `ecrire_lignes`, QJR62 `ecrire_etude_params`, L-1V `rafraichir_etudes`) —
# c'est une divergence d'ORDONNANCEMENT. Et un ordonnancement qui diverge
# produit des devis qui divergent : QJR20 a documenté le cas le plus cher, où
# les quatre études repartaient de la composition d'AVANT parce que personne
# n'avait relu l'instance verrouillée.
#
# ``appliquer`` est donc DÉLIBÉRÉMENT SANS RÈGLE PROPRE : elle ne compose pas,
# ne dimensionne pas, ne tarife pas. Elle APPELLE, dans l'ordre, huit étapes
# déjà en service, et c'est tout ce qu'elle fait. C'est ce qui la rend
# relisable, et c'est ce qui rendra chaque bascule (M5) vérifiable par un
# simple golden.
#
# LES BASCULES (M5) BRANCHENT LES CHEMINS UN PAR UN, chacune avec son golden et
# la SUPPRESSION de l'ancien corps dans le même commit (R4-C.7) : QJR93 a
# branché l'écran (``atomic`` / ``replace-lines``), QJR94 ``perform_update``,
# QJR95 la création depuis un calepinage 3D. Le ledger des chemins branchés est
# tenu par ``tests/test_qjr_pipeline_appliquer.py`` : tout appel non déclaré y
# est rouge.

#: QJR85 — les CINQ origines d'un devis. Elles ne changent AUCUNE règle : elles
#: nomment d'où vient la demande (journal, propriétaire d'étude, message).
ORIGINE_ECRAN = 'ecran'
ORIGINE_CALEPINAGE = 'calepinage'
ORIGINE_AUTO = 'auto'
ORIGINE_TUNNEL = 'tunnel'
ORIGINE_RESYNCHRONISATION = 'resynchronisation'
ORIGINES = (ORIGINE_ECRAN, ORIGINE_CALEPINAGE, ORIGINE_AUTO,
            ORIGINE_TUNNEL, ORIGINE_RESYNCHRONISATION)

#: LES HUIT ÉTAPES, dans l'ordre, nommées UNE fois. Le journal rendu par
#: ``appliquer`` les liste dans l'ordre où elles ont réellement tourné : c'est
#: ce que le test d'ordre assertit, et ce qu'une bascule pourra comparer.
ETAPES = ('resoudre_entrees', 'decider_taille', 'composer', 'verifier',
          'ecrire_lignes', 'ecrire_etude_params', 'rafraichir_etudes',
          'finaliser')

# ── QJR93 (M5) — LES MODES : QUELLES étapes le geste demandé recouvre ────────
#
# Une bascule ne peut pas faire passer un chemin par des étapes qu'il ne
# faisait pas : ce serait un changement de comportement déguisé en
# refactoring. Le mode DÉCLARE donc, une fois, le sous-ensemble d'étapes que
# chaque geste recouvre — et ``appliquer`` n'en exécute jamais d'autres.
#
# * ``composer``   — LE geste complet : le pipeline compose lui-même (les huit
#   étapes). C'est le mode de QJR85, et le DÉFAUT : une intention qui ne dit
#   rien se comporte exactement comme avant cette bascule ;
# * ``ecrire``     — LA COMPOSITION EST FOURNIE par l'appelant. C'est le geste
#   de l'ÉCRAN générateur (``atomic`` / ``replace-lines``, QJR93) : le
#   commercial a composé, édité, tapé des prix ; recomposer depuis le
#   catalogue DÉTRUIRAIT son travail. Les étapes 3 (``composer``) et 4
#   (``verifier``) n'ont donc rien à décider ici, et le pipeline se réduit à
#   l'ÉCRIVAIN UNIQUE des lignes ;
# * ``rafraichir`` — RIEN N'EST ÉCRIT : les quatre études repartent de
#   l'instance RELUE (QJR20). C'est la moitié « après la transaction » de
#   l'écran, et le geste entier de ``perform_update`` (QJR94).
#
# POURQUOI DEUX APPELS ET NON UN SUR LE CHEMIN DE L'ÉCRAN. Les lignes
# s'écrivent SOUS transaction (« soit RIEN, soit un devis complet ») ; les
# quatre études, elles, sont délibérément HORS transaction et best-effort — un
# devis correctement écrit ne doit jamais être annulé par une étude, et une
# étude qui avale une erreur de base à l'intérieur d'une transaction la rendrait
# inutilisable pour tout ce qui suit. Les deux modes gardent donc chacun leur
# côté de la frontière, exactement là où l'ancien corps les tenait.
#
# * ``reconcilier`` — QJR97 : le devis EXISTE, il est VIVANT, et on l'aligne
#   sur une nouvelle cible sans jamais le recomposer. C'est le geste de la
#   resynchronisation 3D et du chemin apply-taille : il porte des quantités,
#   permute un onduleur, complète un kit manquant — et laisse INTACTS les prix
#   négociés, les remises, les sections, les notes et l'ordre d'affichage. Une
#   recomposition les perdrait tous ; c'est pourquoi ce mode n'appelle NI
#   ``composer`` NI l'écrivain de lignes, et n'exécute QUE son étape.
MODE_COMPOSER = 'composer'
MODE_ECRIRE = 'ecrire'
MODE_RAFRAICHIR = 'rafraichir'
MODE_RECONCILIER = 'reconcilier'
MODES = (MODE_COMPOSER, MODE_ECRIRE, MODE_RAFRAICHIR, MODE_RECONCILIER)

#: Les étapes de CHAQUE mode, dans l'ordre. Le journal rendu par ``appliquer``
#: est exactement cette liste — c'est ce qu'une bascule compare.
ETAPES_PAR_MODE = {
    MODE_COMPOSER: ETAPES,
    MODE_ECRIRE: ('ecrire_lignes',),
    # QJR554 — le rafraîchissement remet aussi à jour les CACHES du devis
    # (kWc depuis les lignes, marge interne) : l'Édition complète ne laisse
    # plus ``puissance_kwc`` ni ``marge_snapshot`` périmés. PAS de second
    # ``concevoir_electrique`` : ``rafraichir_etudes`` le couvre déjà.
    MODE_RAFRAICHIR: ('rafraichir_etudes', 'finaliser_caches'),
    MODE_RECONCILIER: ('reconcilier',),
}


@dataclass(frozen=True)
class CibleDevis:
    """Le CHAMP PV arrêté par l'étape 2 — ce que le devis va vendre.

    GELÉ : une cible arrêtée ne se retouche pas en cours de pipeline ; on en
    dérive une autre (``dataclasses.replace``) si un plafond de toit mord.
    """

    nb_panneaux: int = 0
    panel_watt: object = None
    kwc: float = 0.0
    source: str = ''
    dimensionnement_avec: object = None


@dataclass(frozen=True)
class IntentionDevis:
    """LE jeu de paramètres du pipeline entier — un seul, pour les cinq
    origines. GELÉ, pour la même raison qu'``IntentionComposition``.

    * ``origine`` — laquelle des cinq (``ORIGINES``) ;
    * ``company`` / ``user`` — jamais lus d'un corps de requête ;
    * ``lead`` / ``client`` — au moins un des deux ; le client se résout depuis
      le lead par ``crm.services.resolve_client_for_lead``, jamais ici ;
    * ``mode_installation`` — le marché (``Devis.ModeInstallation``) ;
    * ``entrees`` — un ``EntreesMoteur`` DÉJÀ lu, quand l'appelant l'a
      (l'étape 1 le relit sinon) ;
    * ``cible`` — une ``CibleDevis`` DÉJÀ arrêtée, quand l'appelant l'a
      (l'étape 2 la demande au moteur horaire sinon). C'est ce qui permet à
      l'écran et au calepinage — où le commercial a DÉJÀ tranché — de ne pas
      se faire redimensionner sous les pieds ;
    * ``scenario`` — ``'sans'`` / ``'avec'`` / ``'les_deux'`` ; vide ⇒
      ``'les_deux'`` (le défaut fondateur U2) ;
    * ``layout`` — le calepinage 3D, quand il y en a un ;
    * ``exact`` — la cible vient d'un NOMBRE TAPÉ, pas d'un toit : les deux
      options y sont portées à la hausse comme à la baisse (cf.
      ``sync_devis_from_layout(cible_exacte=...)``).
    * ``mode`` — QJR93, lequel des ``MODES`` : quelles étapes le geste
      recouvre. ``'composer'`` (LE DÉFAUT) ⇒ les huit, comportement de QJR85
      strictement inchangé ;
    * ``composition`` — QJR93, les LIGNES DÉJÀ ARRÊTÉES par l'appelant, en mode
      ``'ecrire'``. Même souveraineté qu'``entrees`` et ``cible`` : ce que
      l'écran a composé/édité ne se refait pas. Acceptée sous les deux formes
      que ce dépôt produit — des ``LigneKit`` (une composition du pipeline) ou
      des dicts déjà au format de l'écrivain (le corps de l'écran) ;
    * ``etude_initiale`` — QJR95, l'étude que l'appelant apporte DÉJÀ au devis
      qu'il fait créer (le calepinage apporte sa toiture et son kWc de toit).
      Posée à la création, jamais recalculée ici ;
    * ``force_etudes`` — QJR94, ``force=True`` des quatre rafraîchisseurs :
      « recalcule même si l'empreinte concorde ». ``False`` (LE DÉFAUT) laisse
      l'empreinte décider (QJR43/QJR44/QJR47). QJR227 — il est transmis sur
      TOUS les modes qui rafraîchissent, plus seulement ``MODE_RAFRAICHIR`` :
      un appelant qui demandait des études forcées sur un compose/create
      recevait les études EN CACHE, sans le savoir.

    QJR227 — ``overrides`` A ÉTÉ SUPPRIMÉ DE CETTE INTENTION. Le champ était
    déclaré et documenté « le patch de surcharges déclarées (QJR58), appliqué
    par ``domain/overrides`` » et n'était POSÉ par personne ni LU par personne
    (grep du dépôt). Le registre de surcharges se pose par son endpoint
    (``PATCH /devis/<id>/overrides/`` → ``domain.overrides.fusionner`` +
    ``ecrire_colonne``) et se LIT par ``domain.overrides.effectif`` là où il
    compte ; le pipeline n'a jamais eu de rôle dedans. Arbitrage « câbler ou
    supprimer » : SUPPRIMER — un champ qui ment coûte plus qu'il ne rapporte.
    """

    origine: str
    company: object
    user: object = None
    lead: object = None
    client: object = None
    mode_installation: str = 'residentiel'
    entrees: object = None
    cible: object = None
    scenario: str = ''
    layout: object = None
    exact: bool = False
    taux_tva: Decimal = Decimal('20')
    remise_globale: Decimal = Decimal('0')
    structure_type: str = 'acier'
    #: STKCAT1/STKCAT7 — LE PRODUIT de structure choisi (id ``stock.Produit``),
    #: prioritaire sur ``structure_type`` (alias déprécié). ``None`` (LE
    #: DÉFAUT) ⇒ pipeline strictement inchangé.
    structure_produit_id: object = None
    mppt_paires: int = 1
    phase: object = None
    gamme_nom_devis: object = None
    mode: str = MODE_COMPOSER
    composition: object = None
    etude_initiale: object = None
    force_etudes: bool = False
    #: QJR-OFFGRID — site ISOLÉ (lead ``raccordement='aucun'`` ou demande
    #: explicite) : onduleur autonome + batterie, mono-option. ``False`` (LE
    #: DÉFAUT) ⇒ pipeline strictement inchangé.
    hors_reseau: bool = False
    #: QJR557 suivi — ``True`` (LE DÉFAUT) : sur un ENVOYÉ, ``appliquer``
    #: encadre ``ecrire_lignes`` / ``reconcilier`` de sa propre trace
    #: « corrigé après envoi » (QJR518). ``False`` : l'appelant ENGLOBE déjà
    #: le geste dans sa propre trace (la taille d'offre : resynchro + modules
    #: + matériel = UN geste) — le pipeline s'abstient, sans quoi le chatter
    #: portait deux entrées pour une seule correction.
    tracer_correction: bool = True


def _scenario_de(intention):
    """Le scénario du pipeline : celui de l'intention, sinon LES DEUX (U2)."""
    demande = (intention.scenario or '').strip().lower()
    return demande if demande in SCENARIOS_COMPOSABLES else COMPOSITION_LES_DEUX


def resoudre_entrees(devis, intention):
    """Étape 1 — LES ENTRÉES du moteur, lues UNE fois et par une seule
    fonction (``domain/entrees``, QJR42/QJR43).

    L'intention peut les porter déjà lues (l'appelant vient de les afficher) :
    on ne relit alors rien — deux lectures donneraient deux dimensionnements.
    """
    if intention.entrees is not None:
        return intention.entrees
    if devis is not None and getattr(devis, 'pk', None) is not None:
        return entrees_depuis_devis(devis)
    if intention.lead is not None:
        return entrees_depuis_lead(intention.lead, intention.company)
    return None


#: QJR304 — la SOURCE d'une cible arrêtée par le REGISTRE de surcharges
#: (``taille.nb_panneaux``, décision fondateur D12). Nommée comme les sources
#: du dimensionneur horaire : une cible dit toujours d'où elle vient.
SOURCE_CIBLE_REGISTRE = 'registre_surcharges'


def _cible_du_registre(devis):
    """QJR304 — la ``CibleDevis`` que le REGISTRE de ce devis DÉCLARE, ou
    ``None``.

    R4-A phrase 2, enfin vraie : ``taille.nb_panneaux`` est le chemin de NIVEAU
    DEVIS et il « alimente ``decider_taille`` » — ce que la règle affirmait
    depuis le 29/08/2026 sans qu'aucune ligne de code ne le fasse.

    LES DEUX LECTURES SONT CELLES DU REGISTRE, jamais des secondes :
    le compte vient de :func:`domain.overrides.cible_dimensionnement_du_devis`
    (la MÊME lecture que la table de préséance R4-A) et le wattage de
    ``taille.panel_watt`` s'il est déclaré, sinon de la carte AUTO du moteur
    (``overrides.autos_du_devis`` → ``builder.panneaux_et_watt_lu``, le lecteur
    unique PVUNI). Le repli ``_AUTO_PANEL_WATT`` est celui, et le seul, que le
    dimensionneur horaire applique déjà quelques lignes plus bas.

    ``None`` dès que le registre ne déclare rien de lisible : le pipeline
    repart alors EXACTEMENT comme avant (comportement byte-identique).
    """
    if devis is None or getattr(devis, 'pk', None) is None:
        return None
    from apps.ventes.domain.overrides import (
        autos_du_devis, cible_dimensionnement_du_devis, effectif,
    )
    nb = cible_dimensionnement_du_devis(devis)
    if not nb or nb <= 0:
        return None
    watt_declare, source_watt = effectif(devis, 'taille.panel_watt', None)
    watt = None
    if source_watt != 'auto':
        try:
            watt = int(float(watt_declare))
        except (TypeError, ValueError):
            watt = None
    if not watt:
        try:
            watt = int(float(autos_du_devis(devis).get('taille.panel_watt')))
        except (TypeError, ValueError):
            watt = None
    watt = watt or _AUTO_PANEL_WATT
    return CibleDevis(nb_panneaux=nb, panel_watt=watt,
                      kwc=round(nb * float(watt) / 1000.0, 2),
                      source=SOURCE_CIBLE_REGISTRE)


def decider_taille(intention, devis=None):
    """Étape 2 — LE CHAMP PV.

    Le pipeline NE REDIMENSIONNE PAS de sa propre initiative : une cible déjà
    arrêtée par l'appelant (écran, calepinage, puissance demandée) est
    SOUVERAINE. Vient ensuite le REGISTRE de surcharges du devis (QJR304 —
    R4-A phrase 2 : ``taille.nb_panneaux`` alimente CETTE étape). À défaut, et
    seulement à défaut, le moteur horaire tranche — le seul dimensionneur,
    ordre fondateur du 29/08/2026 (« ALL sizing should go through the new
    sizing tool ») — et son refus est NOMMÉ, jamais remplacé par un repli
    forfaitaire.

    ``devis`` — le devis dont on lit le registre (``None`` à la création, où
    aucun registre n'existe encore). Il n'est JAMAIS écrit ici : cette étape
    lit, elle ne persiste rien.

    QJR243 (b) — LE PARAMÈTRE ``entrees`` A ÉTÉ RETIRÉ, ET LA DOCUMENTATION
    CORRIGÉE AVEC LUI. Cette étape le DÉCLARAIT sans jamais le LIRE : la chaîne
    « ``resoudre_entrees`` → ``decider_taille`` » ne transportait donc rien, et
    le paramètre laissait croire l'inverse. Le dimensionneur horaire relit la
    fiche lui-même (``taille._panneaux_dimensionnement_horaire`` →
    ``entrees_depuis_lead``, MÊME adaptateur, mêmes valeurs) : c'est une
    RELECTURE, pas une seconde vérité, et elle est nommée ici plutôt que
    masquée par un argument décoratif.

    L'ÉTAPE 1 N'EST PAS MORTE POUR AUTANT : son résultat est rendu par
    ``appliquer`` (clé ``entrees`` du compte rendu), que ses appelants lisent.
    """
    if intention.cible is not None:
        return intention.cible
    declaree = _cible_du_registre(devis)
    if declaree is not None:
        return declaree
    if intention.lead is None:
        return None
    nb_panneaux, watt, source, avec = _panneaux_dimensionnement_horaire(
        lead=intention.lead, company=intention.company,
        phase=phase_client_pour_dimensionnement(intention.lead))
    if nb_panneaux <= 0:
        raise _refus_dimensionnement(source)
    watt = watt or _AUTO_PANEL_WATT
    return CibleDevis(
        nb_panneaux=nb_panneaux, panel_watt=watt,
        kwc=round(nb_panneaux * float(watt) / 1000.0, 2),
        source=source, dimensionnement_avec=avec)


def intention_de_composition(intention, cible, *, avertissements=None):
    """Traduit l'intention de devis en intention de COMPOSITION (étapes 3-4).

    Pure traduction : aucun choix n'est fait ici, tout vient de l'intention ou
    de la cible que l'étape 2 a arrêtée.
    """
    cible = cible or CibleDevis()
    return IntentionComposition(
        company=intention.company,
        kwc=cible.kwc,
        nb_panneaux=cible.nb_panneaux,
        panel_watt=cible.panel_watt,
        scenario=_scenario_de(intention),
        structure_type=intention.structure_type,
        structure_produit_id=getattr(intention, 'structure_produit_id', None),
        taux_tva=intention.taux_tva,
        mppt_paires=intention.mppt_paires,
        phase=intention.phase,
        gamme_nom_devis=intention.gamme_nom_devis,
        dimensionnement_avec=cible.dimensionnement_avec,
        avertissements=avertissements,
        # QJR-OFFGRID — traduction PURE, comme tout le reste de cette fonction.
        hors_reseau=bool(getattr(intention, 'hors_reseau', False)),
        # QJR604 — la ville du barème transport, lue UNE fois depuis le lead.
        ville=ville_du_lead(intention.lead),
    )


def ecrire_lignes(devis, composition, *, company, avertissements=None):
    """Étape 5 — les lignes, par L'ÉCRIVAIN UNIQUE (QJR73 + QJR84).

    L'ordre VOULU est posé EXPLICITEMENT (``ordre=index``), jamais laissé au
    tri de repli sur ``id`` : sans lui l'ordre par défaut de la société (PVORD)
    ne survivrait pas à la première renumérotation. La re-tarification des
    forfaits au panneau (QJR83) est faite par l'écrivain lui-même.

    QJR93 — DEUX FORMES D'ENTRÉE, UN SEUL ÉCRIVAIN. Une ``LigneKit`` (ce que
    ``composer`` rend) est TRADUITE ci-dessous ; un dict est passé TEL QUEL,
    sans un champ ajouté ni retiré. C'est ce qui permet à l'écran — qui envoie
    déjà le format de l'écrivain, avec ses sections, ses ``optionnelle`` et ses
    marqueurs de saisie manuelle (D12) — d'emprunter cette étape sans qu'un
    seul octet de son corps de requête change de sens en route.

    QJR304 — LA RÈGLE R4-A S'APPLIQUE ICI, AU POINT OÙ LA QUANTITÉ DEVIENT
    FACTURÉE. Voir :func:`_appliquer_preseance_quantite`.
    """
    # STKCAT23 (bis) — le rôle ÉMIS par la composition (``lignes.roles``,
    # parallèle aux specs) voyage avec chaque ligne jusqu'à l'écrivain : une
    # pergola (nom sans mot-clé, rôle non déclaré) est ainsi stockée avec son
    # rôle ``structure`` au lieu de NULL. Un dict passé par l'écran reste
    # TEL QUEL (il porte, ou non, son propre ``role_devis``).
    roles_emis = list(getattr(composition, 'roles', None) or ())
    lignes_in = [
        spec if isinstance(spec, dict) else {
            'produit': getattr(spec.produit, 'id', None),
            'designation': spec.designation,
            'quantite': str(spec.quantite),
            'prix_unitaire': str(spec.prix_unitaire),
            'ordre': index,
            'variante': getattr(spec, 'variante', '') or '',
            'role_devis': (roles_emis[index]
                           if index < len(roles_emis) else None),
            # ERR-QJR570 (D-QJR5-4) — une ligne posée par le MOTEUR : une
            # recomposition la remplace (un dict de l'écran porte la sienne).
            'ligne_composee': True,
        }
        for index, spec in enumerate(composition or ())
    ]
    _appliquer_preseance_quantite(devis, lignes_in,
                                  avertissements=avertissements)
    return remplacer_lignes(devis, lignes_in, company,
                            avertissements=avertissements)


class _SpecCommeLigne:
    """Une spec de ligne VUE COMME une ligne, le temps d'un arbitrage R4-A.

    ``preseance_nb_panneaux`` et ``ligne_panneau_dominante`` lisent des lignes
    par ``getattr`` (``designation`` / ``quantite`` / ``produit`` /
    ``quantite_manuelle``) : ce mince adaptateur leur présente une spec de
    l'écrivain sous cette forme, plutôt que de dupliquer leur logique pour un
    autre type d'entrée. ``produit`` est ici un IDENTIFIANT (l'écrivain ne
    porte pas l'objet) : le prédicat panneau retombe alors sur la seule
    désignation, ce qu'il sait faire.
    """

    __slots__ = ('index', 'designation', 'produit', 'quantite_manuelle',
                 '_quantite')

    def __init__(self, index, spec):
        self.index = index
        self.designation = spec.get('designation') or ''
        self.produit = spec.get('produit')
        self.quantite_manuelle = bool(spec.get('quantite_manuelle', False))
        try:
            self._quantite = int(float(spec.get('quantite') or 0))
        except (TypeError, ValueError):
            self._quantite = 0

    @property
    def quantite(self):
        """En LECTURE SEULE — cet adaptateur ne se réécrit jamais : la seule
        écriture de quantité de ce chemin est celle de la SPEC, faite par
        :func:`_appliquer_preseance_quantite` puis persistée par l'écrivain
        unique ``lignes.remplacer_lignes``."""
        return self._quantite


def _appliquer_preseance_quantite(devis, lignes_in, *, avertissements=None):
    """QJR304 — R4-A phrase 1, LÀ OÙ LA QUANTITÉ DEVIENT FACTURÉE.

    LE TROU QUE CECI FERME. ``PreseanceQuantite.quantite_ligne`` n'avait AUCUN
    consommateur de production : un devis dont le vendeur avait déclaré
    ``taille.nb_panneaux = 21`` au niveau DEVIS voyait son kWc passer à 21
    panneaux (``scenario.puissance_kwc_du_devis``, QJR217) pendant que la LIGNE
    — donc le total facturé, l'échéancier et le PDF — en comptait toujours 14 :
    deux nombres de panneaux pour une seule vente.

    LA RÈGLE APPLIQUÉE EST CELLE DE LA TABLE, PAS UNE SECONDE. La quantité
    retenue est ``overrides.quantite_ligne_panneau`` — donc : la ligne
    VERROUILLÉE (``quantite_manuelle``) garde la sienne (phrase 1), sinon le
    niveau devis décide, et un désaccord émet l'avertissement FR qui NOMME la
    ligne (phrase 3) dans ``avertissements``.

    LES DEUX CANAUX RESTENT DISTINCTS : ``cible_dimensionnement`` continue
    d'alimenter :func:`decider_taille` et n'est pas touché ici.

    NE FAIT RIEN quand le niveau devis n'a rien déclaré : sans surcharge
    ``taille.nb_panneaux``, l'arbitrage rendrait la quantité déjà présente et
    ce chemin est alors byte-identique à celui d'avant QJR304.
    """
    if devis is None or not lignes_in:
        return
    from apps.ventes.domain.overrides import (
        cible_dimensionnement_du_devis, quantite_ligne_panneau,
    )
    try:
        if cible_dimensionnement_du_devis(devis) is None:
            return
        vues = [_SpecCommeLigne(index, spec)
                for index, spec in enumerate(lignes_in)
                if isinstance(spec, dict)
                and (spec.get('type_ligne') or 'produit') == 'produit'
                and not spec.get('optionnelle')]
        dominante, quantite = quantite_ligne_panneau(
            devis, vues, avertissements=avertissements)
    except Exception:  # noqa: BLE001 — un arbitrage raté n'écrit rien
        logger.warning('préséance R4-A illisible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return
    if dominante is None or not quantite or quantite <= 0:
        return
    if quantite != dominante.quantite:
        lignes_in[dominante.index]['quantite'] = str(quantite)
        _reecrire_quantites_soeurs(lignes_in, quantite)


def _reecrire_quantites_soeurs(lignes_in, nb_panneaux):
    """QJR4-1 — LES QUANTITÉS SŒURS SUIVENT LE COMPTE DE PANNEAUX RÉÉCRIT.

    CE QUI ÉTAIT FAUX. ``_appliquer_preseance_quantite`` ne touchait QUE la
    ligne panneau dominante. Les quantités dérivées du MÊME compte — structure
    et socle — n'étaient posées qu'à la COMPOSITION : sur le chemin
    ``MODE_ECRIRE``, le devis sortait donc avec un nombre de panneaux À JOUR et
    une structure / des socles PÉRIMÉS. « N panneaux montés sur M structures » :
    une nomenclature fausse et un prix faux. ``ecrire`` et ``reconcilier`` ne se
    composaient pas.

    LA RÈGLE VIENT DE LA COMPOSITION, jamais d'une seconde formule :
    ``composition.quantites_derivees_du_compte`` en est la SEULE définition, et
    ``catalogue.classer_produit`` le SEUL classifieur qui apparie une ligne à sa
    catégorie. Ce site ne fait que les appliquer.

    D12 — UNE LIGNE VERROUILLÉE RESTE SOUVERAINE : une sœur portant
    ``quantite_manuelle`` n'est jamais réécrite (c'est la quantité que le
    commercial a tapée). Lignes de section/note et options non activées :
    hors périmètre, comme pour la dominante.
    """
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.domain.composition import quantites_derivees_du_compte

    derivees = quantites_derivees_du_compte(nb_panneaux)
    for spec in lignes_in:
        if not isinstance(spec, dict):
            continue
        if (spec.get('type_ligne') or 'produit') != 'produit':
            continue
        if spec.get('optionnelle') or spec.get('quantite_manuelle'):
            continue
        categorie = classer_produit(spec.get('designation') or '')
        if categorie in derivees:
            spec['quantite'] = str(derivees[categorie])


def ecrire_etude_params(devis, intention, composition):
    """Étape 6 — l'étude, par L'ÉCRIVAIN UNIQUE d'``etude_params`` (QJR62).

    Le pipeline n'écrit ici que ce qu'il vient lui-même d'arrêter : le
    SCÉNARIO réellement servable par les lignes (même garde anti-mensonge que
    ``_scenario_stocke`` — « Les deux » exige les deux onduleurs ET la
    batterie) et, quand un calepinage est fourni, la production et les
    économies qu'il porte. Le kWc, lui, a un propriétaire séparé
    (``poser_puissance_kwc``, QJR63) : il est posé à l'étape 8, sur les lignes
    RÉELLEMENT écrites.
    """
    # QJR97 — LA GARDE ANTI-MENSONGE EST ÉCRITE UNE FOIS, dans
    # ``domain/scenario``. Ce site et la resynchronisation la portaient tous
    # deux EN ENTIER, sous deux formulations : les deux appellent désormais la
    # MÊME fonction, sur les mêmes trois faits.
    scenario = scenario_servable(
        _scenario_de(intention) == COMPOSITION_LES_DEUX,
        a_reseau=any(_is_reseau_inverter(s.designation)
                     for s in (composition or ())),
        a_hybride=any(_is_hybrid_inverter(s.designation)
                      for s in (composition or ())),
        a_batterie=any(_is_battery(s.designation)
                       for s in (composition or ())),
        a_offgrid=any(_is_offgrid_inverter(s.designation)
                      for s in (composition or ())))

    cles = {'scenario': scenario}
    resultat = (intention.layout or {}).get('result') or {}
    if resultat.get('annualKwh') is not None:
        cles['production_annuelle'] = int(resultat['annualKwh'])
    if resultat.get('savings') is not None:
        cles['economies_annuelles'] = int(resultat['savings'])
    bloc = ecrire_etude(devis, proprietaire=CALEPINAGE, **cles)
    # DC11 / QJR106 — la PROVENANCE fait partie de l'étape 6 : c'est une clé
    # d'``etude_params``, écrite par le MÊME écrivain unique, dans la même
    # étape. Elle n'ouvre pas une neuvième étape (le journal des étapes est un
    # contrat) — elle est le dernier geste de celle-ci.
    return estampiller_provenance(devis, intention) or bloc


def estampiller_provenance(devis, intention):
    """DC11 / QJR106 — la TRACE de ce que le devis a REPRIS du lead.

    LE CONSTAT (audit L3 du 29/08/2026, décision fondateur D6). ``apps.crm``
    portait depuis DC11 un mécanisme de provenance ENTIÈREMENT écrit et testé —
    ``lead_provenance_stamp`` / ``lead_values_changed_since`` /
    ``LEAD_PROVENANCE_FIELDS`` — que PERSONNE n'appelait : ``etude_params`` n'a
    jamais porté de clé de provenance, et la bannière « valeurs du lead
    modifiées depuis » n'existait nulle part. La docstring du sélecteur, qui
    affirme « ``ventes`` appelle ceci à la création/maj du devis », était
    fausse. D6 tranche : BRANCHER, ne pas supprimer. Cette fonction est ce
    branchement, et rien d'autre — la RÈGLE reste chez ``crm``, qui seul sait
    quels champs du lead comptent.

    QUAND ELLE ÉCRIT, ET QUAND ELLE S'ABSTIENT. Elle estampille à la CRÉATION
    (le devis reprend les valeurs du lead : on note lesquelles) et à la MISE À
    JOUR (un devis né avant DC11, ou rattaché depuis à un autre lead, reçoit
    ainsi son estampille). Elle NE RÉÉCRIT PAS une estampille qui signale déjà
    une DÉRIVE : réestampiller là éteindrait précisément le signal que la
    bannière existe pour porter — un simple enregistrement de l'écran ferait
    disparaître un « le lead a bougé depuis » que personne n'a traité. Le
    verdict de dérive est demandé à ``crm``, par la MÊME fonction que la
    bannière lit : deux comparaisons différentes donneraient deux vérités.

    Rend le bloc ``etude_params`` écrit, ou ``None`` quand il n'y avait rien à
    estampiller (pas de lead, ou dérive en cours à préserver).
    """
    from apps.crm.selectors import (lead_du_devis, lead_provenance_stamp,
                                    lead_values_changed_since)

    lead = intention.lead
    # QJR585 — devis SANS lead : le lead est RÉSOLU (le plus récent du
    # client), il n'est pas lié — l'estampille d'une dérive en cours sur un
    # AUTRE lead ne doit pas être écrasée par lui.
    resolu = lead is None and getattr(devis, 'lead', None) is None
    if lead is None:
        lead = lead_du_devis(devis)
    if lead is None:
        return None

    stamp = lead_provenance_stamp(lead)
    if stamp is None:
        return None

    ancienne = (getattr(devis, 'etude_params', None) or {}).get('provenance')
    if isinstance(ancienne, dict) and (
            resolu or ancienne.get('source_lead_id') == getattr(
                lead, 'pk', None)):
        if lead_values_changed_since(ancienne, company=intention.company):
            return None
    return ecrire_etude(devis, proprietaire=PIPELINE, provenance=stamp)


def restamper_provenance(devis):
    """QJR588 (contrat QJR505) — le SEUL écrivain autorisé à ÉCRASER une
    estampille de provenance en dérive : il pose l'estampille des valeurs
    COURANTES du lead (:func:`crm.selectors.lead_du_devis`). Appelé
    uniquement par les deux gestes qui RÉSOLVENT la dérive — « reprendre les
    valeurs du lead » et « garder celles du devis » —, jamais par un
    enregistrement (:func:`estampiller_provenance` préserve, elle, une dérive
    en cours). Rend le bloc écrit, ou ``None`` sans lead."""
    from apps.crm.selectors import lead_du_devis, lead_provenance_stamp

    stamp = lead_provenance_stamp(lead_du_devis(devis))
    if stamp is None:
        return None
    return ecrire_etude(devis, proprietaire=PIPELINE, provenance=stamp)


def reappliquer_lead(devis, *, user=None, company=None):
    """QJR588 (contrat QJR505) — « Reprendre les valeurs du lead ».

    Sous UNE transaction, sur le devis VIVANT (jamais une recomposition) :

    1. les études sont recalculées depuis le lead COURANT (mode RAFRAICHIR,
       ``force_etudes``) ;
    2. en résidentiel, le compte de panneaux est RÉCONCILIÉ (mode
       RÉCONCILIER, ``exact``) sur la recommandation du moteur pour le lead
       courant — la même machinerie que « appliquer une taille » : prix
       négociés, remises, sections, notes et lignes manuelles intacts, seules
       des quantités bougent ;
    3. l'estampille est reposée (:func:`restamper_provenance`) ;
    4. sur un ENVOYÉ, l'état vu par le client est capturé avant et la
       correction est tracée en un point (« valeurs du lead reprises »).

    La garde de statut est celle de l'appelant (``exiger_modifiable``) ; le
    statut est LU, jamais écrit (règle #4). Rend ``{champs_repris,
    corrige_apres_envoi, avertissements}``.
    """
    from apps.crm.selectors import lead_du_devis, lead_values_changed_since
    from apps.ventes.domain.modifiabilite import (
        consigner_correction_apres_envoi, debut_de_geste_devis,
        empreinte_visible)

    company = company or getattr(devis, 'company', None)
    ancienne = (getattr(devis, 'etude_params', None) or {}).get('provenance')
    champs = (lead_values_changed_since(ancienne, company=company)
              if isinstance(ancienne, dict) else [])
    lead = lead_du_devis(devis)
    avertissements = []
    corrige = False
    with transaction.atomic():
        avant = debut_de_geste_devis(devis, user)
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_ECRAN, mode=MODE_RAFRAICHIR, company=company,
            force_etudes=True))
        if lead is not None and (getattr(devis, 'mode_installation', '')
                                 or 'residentiel') == 'residentiel':
            avertissements.extend(
                _reconcilier_sur_le_lead(devis, lead, company, user))
        devis.refresh_from_db()
        restamper_provenance(devis)
        if avant is not None and empreinte_visible(devis) != avant:
            consigner_correction_apres_envoi(
                devis, user=user, objet='lead',
                resume='valeurs du lead reprises')
            corrige = True
    return {'champs_repris': list(champs), 'corrige_apres_envoi': corrige,
            'avertissements': avertissements}


def _reconcilier_sur_le_lead(devis, lead, company, user):
    """QJR588 — porte le compte de panneaux du devis à la recommandation du
    moteur pour le lead COURANT, par le mode RÉCONCILIER (``exact``). Rend
    les avertissements (jamais une exception pour une recommandation
    impossible : on le DIT et le reste du geste continue)."""
    from apps.ventes import offres_tailles
    from apps.ventes.services import SyncLayoutError, extract_roof_config

    try:
        nb, _watt, _source, _avec = _panneaux_dimensionnement_horaire(
            lead=lead, company=company,
            phase=phase_client_pour_dimensionnement(lead))
    except AutoDevisError as erreur:
        return ['Taille non recalculée : %s' % erreur]
    if not nb:
        return ['Taille non recalculée : le moteur ne recommande aucun '
                'compte de panneaux pour ce lead.']
    if offres_tailles._compter_panneaux_du_devis(devis) == int(nb):
        return []
    contexte = offres_tailles._contexte(devis)
    if contexte is None:
        return ['Taille non recalculée : ce devis ne se dimensionne pas '
                '(profil de consommation ou catalogue).']
    try:
        resultat = appliquer(devis, IntentionDevis(
            origine=ORIGINE_RESYNCHRONISATION, company=company, user=user,
            layout=offres_tailles._layout_de_la_taille(
                devis, contexte, int(nb), 0, extract_roof_config),
            exact=True, mode=MODE_RECONCILIER, tracer_correction=False))
    except SyncLayoutError as erreur:
        return [str(getattr(erreur, 'detail', erreur))]
    return list((resultat.get('resynchro') or {}).get('avertissements') or ())


def rafraichir_etudes(verrou, *, force=False):
    """Étape 7 — LES QUATRE études, sur l'instance VERROUILLÉE **ET RELUE**.

    QJR20 (29/08/2026) — LA RELECTURE N'EST PAS UNE PRÉCAUTION, C'EST L'ÉTAPE.
    Les quatre études repartent des LIGNES du devis ; l'instance que le
    pipeline tient a été chargée AVANT l'écriture (et, côté viewset, avec un
    ``prefetch_related('lignes')``). Sans relecture, elles recalculent sur la
    composition d'AVANT et RÉÉCRIVENT ``etude_params`` par-dessus ce que les
    étapes 5-6 viennent d'y poser — la conception électrique, seule des quatre
    à n'être jamais recalculée à la lecture, PERSISTE alors un schéma faux.

    ``refresh_from_db()`` sans ``fields`` vide déjà
    ``_prefetched_objects_cache`` (Django) ; le vidage explicite est une
    ceinture, pour que ce contrat ne dépende pas d'un détail du framework.

    ``force`` (QJR94) — passé TEL QUEL aux quatre rafraîchisseurs : « recalcule
    même si l'empreinte concorde ». ``False`` (LE DÉFAUT) laisse l'empreinte
    décider, comme QJR47 l'a établi sur les chemins de l'écran ; ``True`` est
    ce que ``perform_update`` exigeait déjà de ses deux rafraîchisseurs et
    qu'il continue d'exiger des quatre.
    """
    verrou.refresh_from_db()
    verrou._prefetched_objects_cache = {}
    resultat = rafraichir_etudes_du_devis(verrou, force=force)
    consigner_ville_calcul(verrou)
    return resultat


def consigner_ville_calcul(devis):
    """QJR591 — consigne dans ``etude_params['ville_calcul']`` la ville sur
    laquelle les études viennent d'être chiffrées (``ville_effective`` du lead
    du devis) et la ville tapée qui l'accompagne. N'écrit que si elle a
    changé ; best-effort, jamais le statut (règle #4)."""
    try:
        from apps.crm.selectors import lead_du_devis, ville_effective
        lead = lead_du_devis(devis)
        if lead is None:
            return None
        valeur = {
            'ville': (getattr(lead, 'ville', '') or '').strip(),
            'reference': ville_effective(lead),
        }
        if (getattr(devis, 'etude_params', None) or {}).get(
                'ville_calcul') == valeur:
            return valeur
        ecrire_etude(devis, proprietaire=PIPELINE, ville_calcul=valeur)
        return valeur
    except Exception:  # noqa: BLE001 — la consignation ne bloque rien
        logger.warning('QJR591 : ville de calcul non consignée',
                       exc_info=True)
        return None


def finaliser_caches(devis):
    """QJR554 — les deux CACHES du devis : le kWc (QJR63, depuis les LIGNES)
    et la marge interne (QX23be, manager-only — jamais au PDF).

    Partagés par ``finaliser`` (mode ``composer``) et le mode ``rafraichir``
    (Édition complète, ``perform_update``, ``LigneDevisViewSet``). Best-effort,
    ne touche jamais au statut (règle #4).
    """
    poser_puissance_kwc(devis)
    refresh_marge_snapshot(devis)
    return devis


def finaliser(devis, intention):
    """Étape 8 — le kWc par son propriétaire, la marge interne, le schéma.

    Les trois sont BEST-EFFORT et n'annulent jamais un devis écrit :
    ``finaliser_caches`` (kWc QJR63 + marge QX23be) puis
    ``concevoir_electrique_du_devis`` (PV42).
    """
    finaliser_caches(devis)
    concevoir_electrique_du_devis(devis, origine=intention.origine)
    return devis


def _instantane(devis, intention):
    """QJR550 — l'instantané de configuration du geste (best-effort)."""
    from apps.ventes.domain.historique_config import instantane_de_geste
    try:
        instantane_de_geste(devis, user=intention.user)
    except Exception:  # noqa: BLE001 — l'historique n'est jamais bloquant
        logger.warning('QJR550 : instantané ignoré', exc_info=True)


def _verrouiller(devis):
    """Recharge le devis sous ``select_for_update`` — l'instance que le
    pipeline écrit, et la seule que l'étape 7 relit."""
    from apps.ventes.models import Devis

    return Devis.objects.select_for_update().get(pk=devis.pk)


def _creer_brouillon(intention):
    """Le devis n'existe pas encore : on le crée BROUILLON, avec la
    numérotation anti-collision (``core.numbering``, JAMAIS count()+1).

    Le client est résolu depuis le lead par ``crm.services`` — la frontière
    cross-app sanctionnée, jamais un import de ``crm.models``.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference

    client = intention.client
    if client is None:
        if intention.lead is None:
            raise ValueError(
                'appliquer() exige un lead ou un client pour créer un devis.')
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(intention.lead)

    def _create(reference):
        return Devis.objects.create(
            company=intention.company, reference=reference,
            client=client, lead=intention.lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=intention.taux_tva,
            remise_globale=intention.remise_globale,
            created_by=intention.user,
            mode_installation=intention.mode_installation,
            # QJR95 — l'étude que l'appelant APPORTE (la toiture du calepinage
            # et son kWc de toit) est posée à la création, comme le faisait le
            # corps de ``build_devis_from_layout``. Le pipeline n'en dérive
            # rien : il la transporte. Ce que le pipeline arrête LUI-MÊME est
            # écrit à l'étape 6, par l'écrivain unique.
            etude_params=(dict(intention.etude_initiale)
                          if intention.etude_initiale else None),
            roof_layout=intention.layout or None,
        )

    return create_with_reference(Devis, 'DEV', intention.company, _create)


def appliquer(devis, intention):
    """QJR85 — L'ORDRE UNIQUE des huit étapes. AUCUNE règle nouvelle.

    ``devis`` peut être ``None`` : le pipeline crée alors un BROUILLON (aucun
    statut aval n'est jamais touché — règle #4). Sinon il VERROUILLE le devis
    reçu et travaille sur l'instance verrouillée.

    Rend un dict ``{'devis', 'etapes', 'entrees', 'cible', 'composition',
    'avertissements'}``. ``etapes`` liste les étapes DANS L'ORDRE OÙ ELLES ONT
    RÉELLEMENT TOURNÉ — c'est le contrat que le test assertit, et ce qu'une
    bascule (M5) pourra comparer à l'ancien chemin.

    Lève ``AutoDevisError`` quand l'étape 4 refuse : refuser AVANT d'écrire
    vaut mieux que créer puis effacer (un devis effacé rendrait sa référence
    au compteur, et le numéro suivant la reprendrait).

    ``intention.mode`` (QJR93) choisit QUELLES étapes le geste recouvre — voir
    ``MODES``. Le défaut ``'composer'`` est le pipeline complet décrit
    ci-dessus ; ``'ecrire'`` et ``'rafraichir'`` sont les deux moitiés du geste
    de l'écran, de part et d'autre de la frontière de transaction.
    """
    if intention.origine not in ORIGINES:
        raise ValueError(
            'Origine de devis inconnue « %s » — attendu : %s.'
            % (intention.origine, ', '.join(ORIGINES)))
    mode = (intention.mode or MODE_COMPOSER)
    if mode not in MODES:
        raise ValueError(
            'Mode de pipeline inconnu « %s » — attendu : %s.'
            % (intention.mode, ', '.join(MODES)))
    if mode != MODE_COMPOSER:
        return _appliquer_sur_devis_existant(devis, intention, mode)

    journal = []
    avertissements = []

    entrees = resoudre_entrees(devis, intention)
    journal.append('resoudre_entrees')

    # QJR304 — le devis (quand il existe déjà) voyage jusqu'à l'étape 2 : c'est
    # SON registre qui porte ``taille.nb_panneaux``, la cible de niveau devis.
    cible = decider_taille(intention, devis)
    journal.append('decider_taille')

    intention_compo = intention_de_composition(
        intention, cible, avertissements=avertissements)
    composition = composer(intention_compo)
    journal.append('composer')

    refus = verifier(intention_compo)
    journal.append('verifier')
    if refus:
        raise AutoDevisError(refus[0], field='composition')

    # Passe Fable M5a (30/08/2026) — LA FRONTIÈRE TRANSACTIONNELLE DE L'ANCIEN
    # CHEMIN EST PRÉSERVÉE : `build_devis_from_layout` créait le Devis ET ses
    # lignes sous le `transaction.atomic()` de `create_with_reference` — une
    # panne en pleine écriture annulait TOUT (aucun brouillon fantôme, aucune
    # référence brûlée). Création + étapes 5-6 restent donc UN bloc atomique ;
    # les études (étape 7) restent DEHORS, comme sur tous les chemins.
    with _atomic():
        verrou = _verrouiller(devis) if devis is not None else _creer_brouillon(
            intention)

        ecrire_lignes(verrou, composition, company=intention.company,
                      avertissements=avertissements)
        journal.append('ecrire_lignes')

        ecrire_etude_params(verrou, intention, composition)
        journal.append('ecrire_etude_params')
        # QJR550 — UN instantané de configuration pour le geste, sous la
        # transaction (point de sauvegarde) ; aucune étape de journal.
        _instantane(verrou, intention)

    # QJR227 — ``force_etudes`` EST TRANSMIS ICI AUSSI. Il ne l'était que par
    # la branche ``MODE_RAFRAICHIR`` : un appelant qui demandait des études
    # FORCÉES sur un compose/create recevait silencieusement les études en
    # cache (les empreintes QJR43/QJR44 court-circuitent), c'est-à-dire
    # l'inverse exact de ce qu'il avait demandé.
    rafraichir_etudes(verrou, force=intention.force_etudes)
    journal.append('rafraichir_etudes')

    finaliser(verrou, intention)
    journal.append('finaliser')

    return {
        'devis': verrou,
        'etapes': journal,
        'entrees': entrees,
        'cible': cible,
        'composition': composition,
        'avertissements': avertissements,
    }


def _appliquer_sur_devis_existant(devis, intention, mode):
    """QJR93 — les deux modes qui travaillent sur un devis QUI EXISTE DÉJÀ.

    Ils ne créent rien, ne composent rien et ne décident rien : chacun exécute
    LA seule étape que son mode déclare (``ETAPES_PAR_MODE``), sur le devis que
    l'appelant tient. Aucune transaction n'est ouverte ni fermée ici — c'est
    l'appelant qui place la frontière, exactement là où son ancien corps la
    plaçait : les lignes DEDANS, les études DEHORS.

    Le devis n'est pas re-verrouillé : en mode ``'ecrire'`` l'appelant l'a créé
    ou chargé dans la transaction qu'il tient déjà, et un second
    ``select_for_update`` n'ajouterait qu'une requête. La RELECTURE, elle, n'est
    pas facultative : elle vit dans ``rafraichir_etudes`` (QJR20) et vaut donc
    pour ce mode comme pour le pipeline complet.
    """
    if devis is None:
        raise ValueError(
            'Le mode « %s » exige un devis existant : seul le mode « %s » '
            'crée un brouillon.' % (mode, MODE_COMPOSER))

    journal = []
    avertissements = []
    resynchro = None
    # QJR518 — une correction après envoi est tracée à UN point : l'état vu
    # par le client est capturé AVANT la première écriture (ENVOYÉ seulement,
    # no-op sinon), la trace est posée après si un contenu visible a changé.
    # QJR552 — l'instantané « avant » (``debut_de_geste_devis``) et
    # l'instantané « après » (``_instantane``, envoyé compris) encadrent ici
    # ``ecrire_lignes`` / ``reconcilier`` ; une seule implémentation de
    # capture (``historique_config.capturer_configuration_devis``).
    from apps.ventes.domain.modifiabilite import (
        debut_de_geste_devis, fin_de_geste_devis)
    avant_geste = (debut_de_geste_devis(devis, intention.user)
                   if mode in (MODE_ECRIRE, MODE_RECONCILIER)
                   and intention.tracer_correction else None)
    if mode == MODE_ECRIRE:
        ecrire_lignes(devis, intention.composition,
                      company=intention.company,
                      avertissements=avertissements)
        journal.append('ecrire_lignes')
        # DC11 / QJR106 — LE GESTE D'ENREGISTREMENT DE L'ÉCRAN passe ici, à la
        # création (``atomic``) comme à la mise à jour (``replace-lines``) :
        # c'est donc ici que la provenance des valeurs reprises du lead est
        # estampillée sur ce chemin-là. Aucune étape n'est ajoutée au journal —
        # ``ETAPES_PAR_MODE`` reste le contrat, et la fonction s'abstient
        # entièrement pour un devis SANS lead (le cas le plus courant).
        estampiller_provenance(devis, intention)
    elif mode == MODE_RECONCILIER:
        # QJR97 — L'ÉTAPE VIT DANS ``domain/resynchronisation``, comme
        # ``composer`` vit dans ``domain/composition`` et l'écrivain de lignes
        # dans ``domain/lignes`` : ``appliquer`` ORDONNE, elle n'a jamais de
        # règle propre. L'import est FONCTION-LOCAL et c'est délibéré :
        # ``resynchronisation`` importe ce module (son adaptateur appelle
        # ``appliquer``), et un import de haut de fichier des deux côtés ferait
        # lire un module à moitié construit.
        #
        # QJR220 — CE MODE N'APPELLE PAS ``ecrire_lignes``, ET C'EST VOULU : il
        # ajuste CHIRURGICALEMENT des lignes existantes (prix négociés, ordre,
        # groupes préservés), là où l'écrivain SUPPRIME et RECRÉE tout. La
        # re-tarification des forfaits au panneau (QJR83), que ``ecrire_lignes``
        # obtient gratuitement, est donc appelée par ``reconcilier`` lui-même,
        # après TOUTES ses écritures de lignes — jamais en faisant passer ce
        # mode par l'écrivain, ce qui détruirait ce qu'il protège.
        from apps.ventes.domain.resynchronisation import reconcilier

        resynchro = reconcilier(devis, intention)
        avertissements.extend(resynchro.get('avertissements') or ())
        journal.append('reconcilier')
    else:  # MODE_RAFRAICHIR — jamais d'instantané (rien n'est écrit)
        rafraichir_etudes(devis, force=intention.force_etudes)
        journal.append('rafraichir_etudes')
        # QJR554 — les caches suivent les lignes réellement écrites.
        finaliser_caches(devis)
        journal.append('finaliser_caches')
    if mode in (MODE_ECRIRE, MODE_RECONCILIER):
        # QJR550 — UN instantané par geste, après ecrire_lignes / reconcilier.
        _instantane(devis, intention)
    if avant_geste is not None:
        fin_de_geste_devis(
            devis, intention.user, avant=avant_geste,
            objet='lignes' if mode == MODE_ECRIRE else 'calepinage')

    return {
        'devis': devis,
        'etapes': journal,
        'entrees': None,
        'cible': None,
        'composition': intention.composition,
        'avertissements': avertissements,
        # QJR97 — le compte rendu de l'étape ``reconcilier`` (forme GELÉE :
        # ``{inchange, panneaux, kwc, scenario, batterie, lignes_modifiees,
        # lignes_ajoutees, avertissements}``), ``None`` pour les autres modes.
        'resynchro': resynchro,
    }


# ── PONTS M3/M4 : noms hébergés ailleurs ─────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.bordereau import (  # noqa: E402,F401
    concevoir_electrique_du_devis,
)
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_battery,
    _is_hybrid_inverter,
    _is_offgrid_inverter,
    _is_reseau_inverter,
    _pick_batterie,
    _pick_product,
    _plage_batterie_de_l_onduleur,
    carte_marques_composition,
    catalogue_de_la_societe,
    ordre_lignes_societe,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    CompositionLignes,
    _v_txt,
    composition_deux_optimiseurs,
    composition_residentielle,
)
from apps.ventes.domain.entrees import (  # noqa: E402,F401
    entrees_depuis_devis,
    entrees_depuis_lead,
)
from apps.ventes.domain.etude_schema import CALEPINAGE  # noqa: E402,F401
from apps.ventes.domain.etude_schema import PIPELINE  # noqa: E402,F401
from apps.ventes.domain.etude_schema import ecrire as ecrire_etude  # noqa: E402,F401,E501
from apps.ventes.domain.etudes import (  # noqa: E402,F401
    rafraichir_etudes_du_devis,
    refresh_marge_snapshot,
)
from apps.ventes.domain.lignes import remplacer_lignes  # noqa: E402,F401
from apps.ventes.domain.transport import ville_du_lead  # noqa: E402
# SPL265 — les étapes 3 et 4 (composer / verifier) vivent dans
# ``domain/etape_composer.py`` (une feuille qui n'importe rien d'ici) :
# ``appliquer`` les résout dans les globales de CE module.
from apps.ventes.domain.etape_composer import (  # noqa: E402
    COMPOSITION_LES_DEUX,
    SCENARIOS_COMPOSABLES,
    IntentionComposition,
    composer,
    verifier,
)
# QJR243 (a) — TROIS NOMS MORTS RETIRÉS D'ICI : ``SCENARIO_LES_DEUX``,
# ``_scenario_stocke`` et ``sert_les_deux`` n'étaient utilisés NI par ce module
# NI par personne à travers lui (grep : aucun ``from …pipeline import`` ne les
# vise, ils ne sont pas dans ``__all__``). Le ``# noqa: F401`` global les
# rendait invisibles à flake8 pour toujours — un pont mort qu'aucun linter ne
# pouvait plus signaler. Les deux noms restants, eux, sont RÉELLEMENT lus par
# ce module (``scenario_servable`` dans ``ecrire_etude_params``,
# ``poser_puissance_kwc`` dans ``finaliser``) : ils n'ont donc plus besoin du
# ``F401`` du tout — seul ``E402`` (import en bas de fichier) reste nécessaire.
from apps.ventes.domain.scenario import (  # noqa: E402
    poser_puissance_kwc,
    scenario_servable,
)
from apps.ventes.domain.taille import (  # noqa: E402,F401
    _AUTO_PANEL_WATT,
    AutoDevisError,
    _panneaux_dimensionnement_horaire,
    _refus_dimensionnement,
    phase_client_pour_dimensionnement,
)

__all__ = [
    'ETAPES',
    'ETAPES_PAR_MODE',
    'MODES',
    'MODE_COMPOSER',
    'MODE_ECRIRE',
    'MODE_RAFRAICHIR',
    'MODE_RECONCILIER',
    'ORIGINES',
    'ORIGINE_AUTO',
    'ORIGINE_CALEPINAGE',
    'ORIGINE_ECRAN',
    'ORIGINE_RESYNCHRONISATION',
    'ORIGINE_TUNNEL',
    'CibleDevis',
    'IntentionDevis',
    'appliquer',
    'decider_taille',
    'ecrire_etude_params',
    'ecrire_lignes',
    'estampiller_provenance',
    'finaliser',
    'finaliser_caches',
    'intention_de_composition',
    'rafraichir_etudes',
    'resoudre_entrees',
]
