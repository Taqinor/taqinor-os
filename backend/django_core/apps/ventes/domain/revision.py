"""Renouvellement, révision et aval financier de version (SPL263, déplacé de ``domain/cycle_vie.py``).

NTCPQ13 ``renouveler_devis`` (nouveau brouillon depuis un accepté/expiré),
QJR521/QJR558 ``reviser_devis`` (V+1 unique, jamais de fourche) et
QJR560 ``rattacher_aval_financier_revision`` (BC et factures de la V1
reprises par la V2, seul l'écart régularisé). Ce module n'importe JAMAIS
``cycle_vie`` ; ``accept_devis`` (qui y reste) lit
``rattacher_aval_financier_revision`` d'ici, en bas de son fichier. Aucun
statut n'est réécrit (règle #4). Déplacement pur : corps octet-identiques,
prouvé par ``tests/golden/split_dm_rev.json``.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


def renouveler_devis(devis, *, user=None):
    """NTCPQ13 — Renouvelle un devis EXPIRÉ (VNT106 : plus jamais un accepté).

    Crée un NOUVEAU ``Devis`` en ``brouillon`` reprenant les lignes actuelles
    avec les prix COURANTS recalculés (``prix_applicable`` — jamais une simple
    copie figée), lié au devis source par ``devis_origine`` (racine de chaîne)
    et portant ``numero_renouvellement`` = source + 1.

    DISTINCT de ``reviser`` (T10) : celui-ci crée la V+1 d'un devis envoyé,
    accepté, refusé ou expiré (D-QJR5-2 — un accepté se révise, son chantier
    et son contrat passent à la V2, QJR559) et supersède l'original ;
    ``renouveler`` laisse le devis source
    strictement intact (statut, chaîne BC/Facture, historique).

    VNT106 (arbitrage 7) — un ACCEPTÉ lève ``ConflitEtat`` (409
    ``deuxieme_affaire``) : le renouveler sur le MÊME lead laissait deux ventes
    en vigueur. Tout autre état non renouvelable lève aussi ``ConflitEtat``
    (409 ``{statut}`` — CI #997 fuzz : c'est l'état du devis qui s'oppose,
    l'appel sans corps est valide). Renvoie le nouveau devis."""
    from django.db import transaction
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from apps.ventes.domain.creation_clone import (
        conditions_ci_pour_copie, echeancier_pour_copie)
    from apps.ventes.utils.company_settings import create_numbered
    from core.conflit_etat import ConflitEtat

    RENOUVELABLES = (Devis.Statut.EXPIRE,)

    def _controler_statut(devis):
        if devis.statut == Devis.Statut.ACCEPTE:
            raise ConflitEtat({'code': 'deuxieme_affaire', 'detail': (
                'Ce devis est accepté : une nouvelle vente se crée sur une '
                'deuxième affaire (nouvelle fiche lead) ; pour changer le prix, '
                'utilisez Réviser ou Prix négocié.')})
        if devis.statut not in RENOUVELABLES:
            raise ConflitEtat({'statut': (
                'Seul un devis expiré peut être renouvelé '
                '(un devis en cours se corrige avec « réviser »).')})

    _controler_statut(devis)
    company = devis.company
    cree = {}

    def _save(ref):
        cree['obj'] = Devis.objects.create(
            company=company, reference=ref, client=devis.client,
            lead=devis.lead, statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva, remise_globale=devis.remise_globale,
            note=devis.note, mode_installation=devis.mode_installation,
            # QJR117 / CS6 — le renouvellement RE-TARIFE les lignes au
            # catalogue courant : garder l'étude chiffrée aux ANCIENS prix
            # servait au client un devis dont les lignes disent un prix et
            # dont le payback en dit un autre. La CONFIGURATION reste.
            etude_params=etude_params_pour_copie(devis.etude_params),
            prix_cible_kwc=devis.prix_cible_kwc,
            # QJR146 (a) — l'échéancier était bien copié, mais par RÉFÉRENCE :
            # deux devis partageaient la même liste JSON, exactement le piège
            # que QJR117 a fermé pour ``etude_params``. Et ``custom_data``
            # manquait.
            echeancier=(list(devis.echeancier)
                        if isinstance(devis.echeancier, list)
                        else devis.echeancier),
            custom_data=(dict(devis.custom_data)
                         if isinstance(devis.custom_data, dict)
                         else devis.custom_data),
            devise=devis.devise,
            taux_change=devis.taux_change, entite=devis.entite,
            created_by=user, devis_origine=racine,
            numero_renouvellement=(devis.numero_renouvellement or 0) + 1,
            # CIQ219 — conditions C&I recopiées (référence de commande du
            # client VIDÉE : un renouvellement est une nouvelle offre).
            **conditions_ci_pour_copie(devis))
        return cree['obj']

    def _prix_courant(ligne):
        """Le prix que CE renouvellement pose sur la ligne clonée.

        QJR84 / D12 — un prix TAPÉ par le commercial n'est pas re-tarifé,
        même par un renouvellement : c'est un prix NÉGOCIÉ, pas une valeur de
        catalogue périmée. Sans cette garde, le marqueur ``prix_manuel``
        cloné protégerait une valeur qui vient d'être réécrite.
        """
        if ligne.produit_id is None or ligne.prix_manuel:
            return ligne.prix_unitaire
        try:
            prix = prix_applicable(
                produit=ligne.produit, client=devis.client,
                quantite=ligne.quantite)['prix']
        except Exception:  # noqa: BLE001 — repli sur le prix historique (D-ENF22-BLE001)
            logger.exception(
                'NTCPQ13 : prix courant indisponible (ligne %s)', ligne.pk)
            return ligne.prix_unitaire
        # ADVS35 — catalogue sans prix (prestation C&I, forfait d'installation
        # posés par le moteur) : la ligne garde le sien, jamais 0.
        return prix or ligne.prix_unitaire

    # ── QJR146 (c) — LE DEVIS ET SES LIGNES NAISSENT ENSEMBLE, OU PAS ──────
    # ``create_numbered`` n'ouvrait de transaction que pour son PROPRE retry de
    # référence (savepoint de ``core.numbering.create_with_reference``), et
    # elle était commitée avant le clonage : une erreur pendant
    # ``cloner_lignes`` laissait un renouvellement BROUILLON à ZÉRO ligne —
    # donc à zéro dirham — dans la liste du commercial, sous un numéro
    # définitivement consommé. Les deux entrent maintenant dans le MÊME bloc.
    # Le savepoint interne reste valide : imbriqué, ``atomic()`` pose un
    # SAVEPOINT, et le retry sur collision de référence continue de rouler
    # jusqu'à lui seul.
    # ``rafraichir_etudes_du_devis`` reste DEHORS : best-effort par contrat
    # (aucun rafraîchisseur ne lève), il n'a pas à tenir la transaction.
    with transaction.atomic():
        # ACNC13 — source relue SOUS VERROU (patron ``reviser_devis``) : deux
        # « renouveler » concurrents ne créent qu'UN brouillon ; le 2e le rend.
        devis = Devis.objects.select_for_update(of=('self',)).get(pk=devis.pk)
        _controler_statut(devis)
        racine = devis.devis_origine or devis
        existant = Devis.objects.filter(
            company=company, devis_origine=racine, statut=Devis.Statut.BROUILLON,
            numero_renouvellement=(devis.numero_renouvellement or 0) + 1).first()
        if existant is not None:
            existant.deja_renouvele = True
            return existant
        create_numbered(Devis, company, 'devis', _save)
        nouveau = cree['obj']
        # QJR116 — le renouvellement clone par le MÊME cloneur unique que le
        # duplicata et la gamme sœur (``domain/lignes.cloner_lignes``) ; il
        # n'y ajoute que sa re-tarification. C'est là que la liste maintenue à
        # la main avait le plus divergé : elle clonait ``optionnelle`` sans
        # ``variante``, et aucune des trois ne clonait ``lot``.
        cloner_lignes(devis, nouveau, prix_unitaire=_prix_courant)
        echeancier_pour_copie(nouveau)  # AGNR53 — au TTC re-tarifé
    # QJR117 — les études du RENOUVELLEMENT sont recalculées sur ses lignes
    # RE-TARIFÉES (force : le dimensionnement se court-circuite sinon sur
    # empreinte concordante, et l'édition de ligne ne rattrape pas).
    rafraichir_etudes_du_devis(nouveau, force=True)

    activity.log_devis_note(
        nouveau, user,
        f'Renouvellement n° {nouveau.numero_renouvellement} du devis '
        f'{devis.reference} — prix catalogue actuels appliqués.')
    activity.log_devis_note(
        devis, user,
        f'Renouvelé par le devis {nouveau.reference} '
        f'(renouvellement n° {nouveau.numero_renouvellement}).')
    return nouveau


class RevisionError(Exception):
    """QJR521 — une révision refusée (déjà remplacé, brouillon) → 409.
    VNT24 — ``code`` machine (``version_remplacee`` | ``brouillon``) et, pour
    une version remplacée, ``successeur`` ``{id, reference}`` (tête de chaîne)
    lu SOUS le verrou."""

    def __init__(self, message, *, code=None, successeur=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.successeur = successeur


#: R6-N1 (suite) — QUI calcule les études de la V+1, et QUAND
#: (``reviser_devis(etudes=…)``). Défaut : le chemin d'hier (la vue
#: « Réviser », hors transaction, les calcule une fois après la re-liaison ;
#: dans une transaction, le clonage les calcule et elles sont refaites au
#: commit si un calepinage est re-lié à une V+1 restée brouillon).
ETUDES_REVISION = 'revision'
#: « Prix négocié » : la V+1 est ACCEPTÉE dans la transaction de l'appelant et
#: rien n'est réécrit après l'acceptation. Le clonage ne calcule RIEN (avec ou
#: sans calepinage) ; le calepinage lié à la V1 est re-lié à la V+1 DANS la
#: transaction ; l'APPELANT calcule les études UNE fois, après avoir posé le
#: prix négocié et avant l'acceptation (l'option « avec batterie » C&I lit
#: ``option_totaux``). Rien au commit.
ETUDES_AVANT_ACCEPTATION = 'avant_acceptation'
#: « Réviser le devis » de l'atelier : l'appelant recompose la V+1. Quand un
#: calepinage lié à la V1 va être re-lié, le clonage ne calcule rien : UN
#: calcul forcé au commit, après la re-liaison (le dernier calcul d'hier).
ETUDES_APRES_RECOMPOSITION = 'apres_recomposition'
#: Révision après la visite C&I : l'appelant re-lie le calepinage à la fin de
#: sa recomposition (:func:`relier_calepinage_de_la_revision`) et refait
#: lui-même les études, forcées, après son commit ; le clonage calcule comme
#: hier. Aucun calcul au commit ici quand un calepinage est à re-lier.
ETUDES_PAR_L_APPELANT = 'par_l_appelant'


def reviser_devis(devis, *, user=None, etudes=ETUDES_REVISION):
    """QJR521 — « Réviser » : LE service de domaine qui crée la V+1.

    Une seule V+1, jamais de fourche, jamais de réactivation :
      * ``transaction.atomic`` + relecture ``select_for_update(of=('self',))``
        — un double clic ou un second vendeur attend le premier, puis lit
        ``is_active=False`` et reçoit 409 « Déjà remplacé par <ref> » ;
      * BROUILLON → 409 « Un brouillon se modifie directement » ; envoyé,
        accepté, refusé, expiré sont révisables (D-QJR5-2) ;
      * ``cloner_devis`` PUIS ``is_active`` / ``superseded_by`` DANS la même
        transaction : un incident entre les deux ne laisse plus v1 active à
        côté d'un brouillon v2 orphelin ;
      * chatter v1 « Remplacé par <ref v2> (révision) » et v2 « Révision de
        <ref v1> ».
    Le statut de v1 n'est JAMAIS écrit (règle #4) — seuls ``is_active`` et
    ``superseded_by`` bougent. Renvoie la nouvelle version.

    R6-N1 — LES ÉTUDES DE LA V+1 SUIVENT SON CALEPINAGE. Le calepinage n'est
    re-lié à la V+1 qu'APRÈS le commit (abonné ``devis_revise`` du
    calepinage) : calculées dans le clonage, ses études ne le voyaient pas
    (``calepinage_du_devis(V+1)`` vide ⇒ ni l'ombrage servi, ni la pose
    réelle, ni les chaînes du calepinage) et rien ne les refaisait. Appelé
    HORS transaction (la vue « Réviser ») : le clonage ne calcule plus rien,
    les études sont calculées UNE fois, après la re-liaison, hors du verrou
    de la V1, et avant le retour (la réponse les porte). Appelé DANS la
    transaction d'un appelant (prix négocié, révision après visite,
    révision sur la conception) : le clonage les calcule comme avant, et
    elles sont refaites au commit seulement si un calepinage a été re-lié à
    une V+1 restée brouillon (:func:`_etudes_apres_reliaison`).

    R6-N1 (suite) — ``etudes`` (:data:`ETUDES_REVISION` par défaut) : les
    trois appelants qui tiennent une transaction disent qui calcule. Sans
    calepinage lié à la V1, l'atelier et la visite sont le défaut, à l'octet ;
    le prix négocié ne calcule jamais au clonage (l'appelant calcule au prix
    négocié, décision de l'orchestrateur du 26/11)."""
    from django.db import transaction
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from apps.ventes.domain.creation_clone import cloner_devis
    from apps.ventes.selectors import racine_groupe

    differees = etudes == ETUDES_REVISION and _hors_transaction()
    with transaction.atomic():
        old = (Devis.objects.select_for_update(of=('self',))
               .get(pk=devis.pk))
        if not old.is_active:
            from apps.ventes.domain.modifiabilite import (
                CODE_VERSION_REMPLACEE, successeur_actif)
            tete = successeur_actif(old)
            raise RevisionError(
                f"Déjà remplacé par {tete['reference']}." if tete
                else 'Ce devis est archivé : il ne se révise plus.',
                code=CODE_VERSION_REMPLACEE, successeur=tete)
        if old.statut == Devis.Statut.BROUILLON:
            raise RevisionError(
                'Un brouillon se modifie directement (pas de révision).',
                code='brouillon')
        # R6-N1 (suite) — un mode explicite avec un calepinage à re-lier :
        # ``au_commit`` dit le calcul qui reste à faire au commit (None :
        # aucun), ``au_clonage`` si le clonage calcule.
        a_relier = etudes != ETUDES_REVISION and _calepinage_a_relier(old)
        au_clonage = (not differees and etudes != ETUDES_AVANT_ACCEPTATION
                      and not (a_relier and etudes == ETUDES_APRES_RECOMPOSITION))
        # QJR558 — ``revision=True`` : la V+1 garde le travail manuel
        # (toiture 3D, registre D12, tailles explorées, rendu toiture).
        nd = cloner_devis(
            old, user=user, note=old.note,
            version=old.version + 1,
            version_parent=racine_groupe(old), revision=True,
            etudes=au_clonage)
        old.is_active = False
        old.superseded_by = nd
        old.save(update_fields=['is_active', 'superseded_by'])
        activity.log_devis_note(
            old, user, f'Remplacé par {nd.reference} (révision).')
        activity.log_devis_note(
            nd, user, f'Révision de {old.reference}.')
        if a_relier and etudes == ETUDES_AVANT_ACCEPTATION:
            # V1 inactive : la re-liaison est permise ; les études que
            # l'appelant calculera (celles que l'acceptation portera) voient
            # SON calepinage.
            relier_calepinage_de_la_revision(old, nd, user=user)
        au_commit = _calcul_au_commit(etudes, a_relier, differees)

    # ACAL91 (C-ACAL-115) — l'événement de domaine ``devis_revise`` part APRÈS
    # le commit (jamais pour une V+1 annulée par un rollback), UNE fois, en
    # best-effort : ``send_robust`` rend l'exception d'un abonné au lieu de la
    # lever — la révision est déjà actée, un abonné en échec est journalisé.
    # Aucun statut n'est écrit ici (règle #4).
    from core.events import devis_revise

    def _emettre_devis_revise():
        for recepteur, resultat in devis_revise.send_robust(
                sender=Devis, ancien=old, nouveau=nd, user=user):
            if isinstance(resultat, Exception):
                logger.warning(
                    'ACAL91 : abonné %r de devis_revise en échec (%s -> %s) : %s',
                    recepteur, old.reference, nd.reference, resultat)
        # R6-N1 — APRÈS les abonnés (calepinage re-lié, ou re-liaison en
        # échec journalisée) : les études de la V+1 voient sa conception.
        if au_commit is not None:
            _etudes_apres_reliaison(
                nd, differees=differees,
                exiger_calepinage=au_commit == _AU_COMMIT_SI_RELIE)

    transaction.on_commit(_emettre_devis_revise)
    return nd


def _hors_transaction():
    """R6-N1 — vrai quand ``reviser_devis`` est appelé HORS de toute
    transaction (la vue « Réviser », en autocommit) : son ``on_commit`` part
    alors tout de suite, avant le retour."""
    from django.db import transaction
    return not transaction.get_connection().in_atomic_block


#: R6-N1 (suite) — le calcul au commit : refait si un calepinage est re-lié à
#: une V+1 restée brouillon (hier) / LE calcul d'une V+1 que le clonage n'a
#: pas calculée, re-liaison réussie ou non.
_AU_COMMIT_SI_RELIE = 'si_relie'
_AU_COMMIT_TOUJOURS = 'toujours'


def _calcul_au_commit(etudes, a_relier, differees):
    """R6-N1 (suite) — le calcul que ``_emettre_devis_revise`` fait après les
    abonnés, ou ``None``. Avant l'acceptation, l'appelant les calcule au prix
    négocié, dans sa transaction : rien. L'appelant de la visite les refait
    lui-même : rien. Après la recomposition de l'atelier : LE calcul de la
    V+1. Sinon : hier."""
    if differees:
        return _AU_COMMIT_TOUJOURS
    if etudes == ETUDES_AVANT_ACCEPTATION:
        return None
    if a_relier and etudes == ETUDES_PAR_L_APPELANT:
        return None
    if a_relier and etudes == ETUDES_APRES_RECOMPOSITION:
        return _AU_COMMIT_TOUJOURS
    return _AU_COMMIT_SI_RELIE


def _calepinage_a_relier(ancien):
    """R6-N1 (suite) — vrai quand un calepinage est lié DIRECTEMENT à
    ``ancien`` : celui que l'abonné ``devis_revise`` du calepinage re-lie à
    la V+1 (même test que lui, ``calepinage.devis_id == ancien.pk``)."""
    from apps.ventes.conception.porte_calepinage import calepinage_lie_au_devis
    calepinage = calepinage_lie_au_devis(ancien.pk, ancien.company)
    return calepinage is not None and calepinage.devis_id == ancien.pk


def relier_calepinage_de_la_revision(ancien, nouveau, *, user=None):
    """R6-N1 (suite) — re-lie MAINTENANT, dans la transaction de l'appelant,
    le calepinage lié directement à ``ancien`` (la V1, déjà inactive) à
    ``nouveau`` (sa V+1) : LE service du calepinage
    (``services.relier_au_devis_revise`` : version figée « Version envoyée —
    <réf.> » puis ``lier_devis``), celui que son abonné ``devis_revise``
    appelle au commit — il y trouve alors le calepinage déjà sur la V+1 et
    n'écrit rien : un seul lien, une seule version figée. Un rollback de
    l'appelant défait les deux (le calepinage reste sur la V1). Point de
    sauvegarde ; un échec est journalisé, jamais propagé (l'abonné du commit
    retente). Rend vrai quand ``nouveau`` porte désormais ce calepinage."""
    from django.db import transaction

    from apps.ventes.conception.porte_calepinage import (
        calepinage_lie_au_devis as calepinage_du_devis,
        relier_calepinage_au_devis_revise)

    try:
        with transaction.atomic():
            relier_calepinage_au_devis_revise(
                ancien, nouveau, user=user)
    except Exception:  # noqa: BLE001 — la révision ne casse jamais sur une re-liaison (D-ENF22-BLE001)
        logger.exception('R6-N1 : re-liaison du calepinage en échec (%s -> %s)',
                         getattr(ancien, 'reference', '?'),
                         getattr(nouveau, 'reference', '?'))
    calepinage = calepinage_du_devis(nouveau.pk, nouveau.company)
    return calepinage is not None and calepinage.devis_id == nouveau.pk


def _etudes_apres_reliaison(nd, *, differees, exiger_calepinage=True):
    """R6-N1 — les études de la V+1 ``nd``, après la re-liaison du calepinage.

    ``differees`` (appel hors transaction) : le clonage n'a rien calculé — LE
    calcul, une fois, sur l'instance rendue à la vue. Sinon le clonage les a
    calculées sans calepinage : refaites seulement si un calepinage est
    désormais celui de la V+1 et qu'elle est encore un brouillon actif (une
    V+1 déjà acceptée dans la transaction de l'appelant n'est jamais
    réécrite) ; sans calepinage, rien (le résultat d'hier, à l'octet).
    ``exiger_calepinage=False`` (R6-N1 suite, atelier) : le clonage n'a rien
    calculé — LE calcul de la V+1 relue, brouillon actif, re-liaison réussie
    ou non.
    Best-effort : la révision est actée ; un échec est journalisé (jamais
    muet) et la première écriture suivante du brouillon recalcule (clés
    dérivées absentes)."""
    from apps.ventes.models import Devis
    try:
        cible = nd
        if not differees:
            from apps.ventes.conception.porte_calepinage import (
                calepinage_lie_au_devis as calepinage_du_devis)
            if exiger_calepinage and calepinage_du_devis(
                    nd.pk, nd.company) is None:
                return
            cible = Devis.objects.filter(
                pk=nd.pk, company_id=nd.company_id, is_active=True,
                statut=Devis.Statut.BROUILLON).first()
            if cible is None:
                return
        rafraichir_etudes_du_devis(cible, force=True)
    except Exception:  # noqa: BLE001 — la révision est actée, l'échec journalisé (D-ENF22-BLE001)
        logger.exception('R6-N1 : études de la révision %s non calculées',
                         getattr(nd, 'reference', '?'))


def abandonner_revision(v2, user=None, *, retrait=False):
    """VNT55 (D-ADEV-1 = (a), couvre ADEV16) — la révision ``v2`` d'une vente
    ACCEPTÉE est abandonnée (brouillon supprimé, version archivée, refusée ou
    expirée) : la V1 acceptée qu'elle remplaçait REDEVIENT la vente en vigueur
    (``is_active=True``, ``superseded_by=None``), dans la transaction de
    l'appelant, avec la note « révision abandonnée » au chatter.

    À appeler AVANT la suppression de ``v2`` (le lien ``superseded_by`` est
    remis à NULL par la cascade). Une V2 ACCEPTÉE n'abandonne rien (elle est
    la vente). Le statut n'est jamais écrit (règle #4) : seuls ``is_active``
    et ``superseded_by``. Rend la liste des versions réactivées.

    ADEV16 — ``retrait=True`` (suppression, archivage : ``v2`` quitte la
    chaîne) réactive le prédécesseur QUEL QUE SOIT son statut : toute chaîne
    garde une version active. Sinon V1 acceptée → V2 envoyée → V3 brouillon
    supprimée laissait V1 et V2 inactives, sans révision possible. Refus et
    expiration (``retrait=False``) : ``v2`` reste la version active ; seul un
    prédécesseur accepté en reprend la place."""
    from django.db import transaction
    from apps.ventes import activity
    from apps.ventes.models import Devis

    if getattr(v2, 'pk', None) is None or v2.statut == Devis.Statut.ACCEPTE:
        return []
    predecesseurs = Devis.objects.filter(
        company_id=v2.company_id, superseded_by_id=v2.pk)
    if not retrait:
        predecesseurs = predecesseurs.filter(statut=Devis.Statut.ACCEPTE)
    reactivees = []
    with transaction.atomic():
        for v1 in (predecesseurs.select_for_update(of=('self',))
                   .order_by('pk')):
            v1.is_active = True
            v1.superseded_by = None
            v1.save(update_fields=['is_active', 'superseded_by'])
            role = ('la vente' if v1.statut == Devis.Statut.ACCEPTE
                    else 'la version')
            activity.log_devis_note(
                v1, user,
                f'Révision {v2.reference} abandonnée : {v1.reference} '
                f'redevient {role} en vigueur (révision abandonnée).')
            reactivees.append(v1)
        if reactivees:
            # ACON41 — SYNCHRONE (pas d'``on_commit``) : l'abonné lit le
            # lien vers la V2 AVANT la cascade SET_NULL de sa suppression ;
            # un abonné en échec ne bloque jamais l'abandon.
            from core.events import revision_abandonnee

            for recepteur, resultat in revision_abandonnee.send_robust(
                    sender=Devis, ancien=v2, reactivees=list(reactivees),
                    user=user):
                if isinstance(resultat, Exception):
                    logger.warning(
                        'ACON41 : abonné %r de revision_abandonnee en échec '
                        '(%s) : %s', recepteur, v2.reference, resultat)
    return reactivees


def _paniers_ecart_par_taux(precedent, devis):
    """ATOT22 / ATOT44 — l'écart SIGNÉ des bases (et de la TVA) PAR TAUX entre
    la version facturée ``precedent`` et la V2 ``devis`` (option effective,
    chaîne canonique ``argent.totaux`` vue NET), pour TOUS les taux dont la
    base bouge (un taux à écart nul n'a pas de panier). Rend
    ``[{taux, base_ht, montant}]`` (Decimal signés), triés par taux."""
    from decimal import Decimal

    from apps.ventes.domain.argent import Vue, totaux

    def _paniers(d):
        out = {}
        for e in totaux(d, vue=Vue.NET).tva_par_taux:
            t = Decimal(str(e['taux']))
            base, tva = out.get(t, (Decimal('0'), Decimal('0')))
            out[t] = (base + Decimal(str(e['base'])),
                      tva + Decimal(str(e['montant'])))
        return out

    avant, apres = _paniers(precedent), _paniers(devis)
    zero = (Decimal('0'), Decimal('0'))
    paniers = []
    for t in sorted(set(avant) | set(apres)):
        d_base = apres.get(t, zero)[0] - avant.get(t, zero)[0]
        d_tva = apres.get(t, zero)[1] - avant.get(t, zero)[1]
        if d_base:
            paniers.append({'taux': t, 'base_ht': d_base, 'montant': d_tva})
    return paniers


def _documents_ecart(precedent, devis, reste):
    """ATOT44 (D-ATOT-VER-2 = ``separes``) — les documents d'écart
    ``[(signe, ttc, paniers positifs)]``. Taux de sens opposés ⇒ DEUX
    documents, chacun ventilé par ses seuls taux : un complément (Σ TTC des
    taux en hausse) et un avoir (taux en baisse) tels que complément − avoir
    = ``reste`` ; un complément de révision déjà fait pour la V2 (rejeu
    confirmé) n'est pas refait. Sinon UN document de ``|reste|`` ventilé par
    les taux de son sens (comme avant)."""
    from decimal import Decimal

    from apps.ventes.models import Facture
    from core.money import quantize_mad

    paniers = _paniers_ecart_par_taux(precedent, devis)
    hausse = [p for p in paniers if p['base_ht'] > 0]
    baisse = [{'taux': p['taux'], 'base_ht': -p['base_ht'],
               'montant': -p['montant']} for p in paniers if p['base_ht'] < 0]
    if hausse and baisse:
        deja = Facture.objects.filter(
            devis=devis,
            libelle__startswith=f'Complément révision {devis.reference} (',
        ).exclude(statut=Facture.Statut.ANNULEE).exists()
        complement = Decimal('0') if deja else quantize_mad(sum(
            (p['base_ht'] + p['montant'] for p in hausse), Decimal('0')))
        avoir = complement - reste
        if complement >= 0 and avoir >= 0:
            return [d for d in ((1, complement, hausse), (-1, avoir, baisse))
                    if d[1] > 0]
    signe = 1 if reste > 0 else -1
    return [(signe, abs(reste), hausse if signe > 0 else baisse)]


def _ventiler_document(devis, paniers, montant_ttc):
    """ATOT22 (C-ATOT-004) — HT / TVA / taux / ventilation d'un document
    d'écart : la TVA est celle de l'ÉCART RÉEL des bases par taux (jamais un
    « taux mélangé ») : un taux unique ⇒ HT/TVA à CE taux ; plusieurs ⇒
    ventilés au centime par le service unique ``ventilation_document_fige``
    (ATOT6) ; aucun (reste issu d'avoirs ou d'arrondis) ⇒ le chemin d'hier."""
    from decimal import Decimal

    from apps.ventes.utils.echeancier import blended_tva_pct
    from core.money import quantize_mad

    ventilation = None
    if len(paniers) == 1:
        taux = paniers[0]['taux']
        montant_ht = quantize_mad(
            montant_ttc / (1 + Decimal(str(taux)) / 100))
    elif paniers:
        from apps.facturation.totaux import ventilation_document_fige
        ventilation = ventilation_document_fige(
            [{'taux': str(p['taux']), 'base_ht': str(p['base_ht']),
              'montant': str(p['montant'])} for p in paniers],
            montant_ttc)
        montant_ht = sum((Decimal(b['base_ht']) for b in ventilation),
                         Decimal('0'))
        taux = blended_tva_pct(devis)
    else:
        taux = blended_tva_pct(devis)
        montant_ht = quantize_mad(
            montant_ttc / (1 + Decimal(str(taux)) / 100))
    return montant_ht, montant_ttc - montant_ht, taux, ventilation


def rattacher_aval_financier_revision(devis, *, user=None,
                                      confirmer_avoir=False):
    """QJR560 / D-QJR5-11 — V2 d'un devis signé acceptée : l'aval FINANCIER
    de la version remplacée passe à la V2, seul l'écart est régularisé.

    Appelée à l'acceptation de ``devis`` (sous la transaction d'``accept_devis``)
    quand un prédécesseur de révision (``selectors.
    devis_predecesseurs_revision_ids``) est ACCEPTÉ. Aucun statut inventé, la
    chaîne BC / Facture reste 1:1 (règle #4) :

    1. le BC non annulé de la V1 est RATTACHÉ à la V2 (``BonCommande.devis`` est
       OneToOne : un BC « complémentaire » est impossible sans migration — le BC
       rendu après rattachement lit donc les lignes de la V2, ``utils/pdf.py``
       relisant ``bc.devis`` ; question fondateur consignée au DONE LOG),
       et les factures (``Facture.devis``) et ``FactureSource`` de la V1 aussi :
       les documents émis restent valables ;
    2. l'écart TTC est régularisé AU CENTIME, jamais un montant inventé :
       tant qu'il reste une tranche d'échéancier à facturer sur la V2 (et
       qu'aucune facture de BC ne solde la vente), la tranche finale le porte
       déjà (solde = total V2 − déjà facturé) — une note le dit ; si la vente
       est entièrement facturée, reste > 0 → facture COMPLÉMENTAIRE brouillon
       (rattachée à la V2), reste < 0 → AVOIR(S) par ``crediter_ecart_de_
       vente`` (ATOT45 : chacun sous le créditable de sa facture) ;
       des taux en sens opposés ⇒ les DEUX, chacun à ses seuls taux (ATOT44).

    La commission apporteur encore À_PAYER est recalculée par ``crm`` sur
    l'option acceptée de la V2 (``crm/receivers.py``, même événement).

    VNT64 — LA lecture de la vente : le reste se lit sur ``plan_facturation``
    (toute la chaîne de versions, les quatre portes, brouillons repris =
    PRÉVU, jamais émis ; seuls les avoirs de CORRECTION remis) — plus de
    somme locale. Un AVOIR d'écart n'est émis QUE confirmé
    (``confirmer_avoir``, aperçu « Prix négocié » ``avoir_a_confirmer``) ;
    sinon une note le dit et le résultat porte ``avoir_a_confirmer``.

    Rend un dict ``{bc, factures, sources, ecart_ttc, document}`` ou ``None``
    quand aucun prédécesseur accepté n'existe."""
    from decimal import Decimal

    from apps.ventes import activity
    from apps.ventes.models import (
        Avoir, BonCommande, Devis, Facture, FactureSource)
    from apps.ventes.selectors import predecesseurs_acceptes
    from apps.ventes.utils.company_settings import create_provisoire
    from apps.ventes.utils.options import option_totaux
    from apps.ventes.vente_facturation import STATUTS_EMIS, plan_facturation

    # VNT51 — LA lecture partagée avec ``devis_accepted(avenant_de=…)``.
    acceptes = predecesseurs_acceptes(devis)  # le plus proche d'abord
    if not acceptes:
        return None
    precedent = acceptes[0]
    ids = [d.pk for d in acceptes]

    # (1) BC — un seul non annulé, rattaché à la V2 si elle n'en a pas.
    bc = None
    if not BonCommande.objects.filter(devis=devis).exists():
        bc = (BonCommande.objects.filter(devis_id__in=ids)
              .exclude(statut=BonCommande.Statut.ANNULE)
              .order_by('-pk').first())
        if bc is not None:
            ancien = bc.devis.reference if bc.devis_id else '?'
            bc.devis = devis
            bc.save(update_fields=['devis'])
            activity.log_devis_note(
                devis, user,
                f'Bon de commande {bc.reference} repris de {ancien} '
                f'(révision acceptée) — document émis inchangé.')
    # (1) Factures d'échéancier et sources de facture consolidée.
    factures = list(Facture.objects.filter(devis_id__in=ids)
                    .values_list('reference', flat=True))
    Facture.objects.filter(devis_id__in=ids).update(devis=devis)
    sources = 0
    for src in FactureSource.objects.filter(devis_id__in=ids):
        if FactureSource.objects.filter(
                facture_id=src.facture_id, devis=devis).exists():
            continue
        src.devis = devis
        src.save(update_fields=['devis'])
        sources += 1
    if factures:
        activity.log_devis_note(
            devis, user,
            'Factures reprises de la version remplacée (révision) : '
            + ', '.join(factures) + '.')

    # (2) L'écart, au centime.
    ecart = (Decimal(str(option_totaux(devis)['ttc']))
             - Decimal(str(option_totaux(precedent)['ttc'])))
    # Relecture sur une instance FRAÎCHE (celle de l'appelant garde ses caches).
    devis = Devis.objects.select_related('client', 'lead', 'company').get(
        pk=devis.pk)
    # VNT64 — LA lecture de la vente (plan_facturation) : prévu = émis net
    # des avoirs de CORRECTION (ATOT36) + brouillons repris (PRÉVU).
    plan = plan_facturation(devis)
    parts = plan['factures_parts']
    document = None
    if not parts:
        # Rien de facturé : l'échéancier de la V2 facturera la V2.
        return {'bc': bc, 'factures': factures, 'sources': sources,
                'ecart_ttc': ecart, 'document': None}
    via_bc = any(f.bon_commande_id for f, _r in parts)
    from core.money import quantize_mad
    reste = quantize_mad(plan['prix_convenu_ttc'] - plan['prevu'])
    encore_une_tranche = (not via_bc) and plan['prochaine'] is not None
    if reste == 0 or (encore_une_tranche and reste > 0):
        activity.log_devis_note(
            devis, user,
            f'Écart de révision {ecart:.2f} MAD TTC porté par la suite de '
            f"l'échéancier (reste à facturer {reste:.2f} MAD).")
        return {'bc': bc, 'factures': factures, 'sources': sources,
                'ecart_ttc': ecart, 'document': None}

    emises = [f for f, _r in parts if f.statut in STATUTS_EMIS]
    resultat = {'bc': bc, 'factures': factures, 'sources': sources,
                'ecart_ttc': ecart, 'document': None}
    company = devis.company
    # ATOT44 (D-ATOT-VER-2) — taux de sens opposés : complément ET avoir.
    for signe, montant_ttc, paniers in _documents_ecart(
            precedent, devis, reste):
        if signe < 0 and (not confirmer_avoir or not emises):
            # VNT64 — jamais un avoir d'écart sans confirmation (D-VNT-2).
            activity.log_devis_note(
                devis, user,
                f'Écart de révision {ecart:.2f} MAD TTC : avoir de '
                f'{montant_ttc:.2f} MAD à confirmer (aucun avoir émis '
                'automatiquement).')
            resultat['avoir_a_confirmer'] = montant_ttc
            continue
        montant_ht, montant_tva, taux, ventilation = _ventiler_document(
            devis, paniers, montant_ttc)
        if signe > 0:
            def _facture(ref):
                return Facture.objects.create(
                    company=company, reference=ref, devis=devis,
                    client=devis.client, lead=devis.lead,
                    statut=Facture.Statut.BROUILLON,
                    type_facture=Facture.TypeFacture.COMPLETE,
                    libelle=(f'Complément révision {devis.reference} '
                             f'(remplace {precedent.reference})')[:255],
                    montant_ht=montant_ht, montant_tva=montant_tva,
                    montant_ttc=montant_ttc, taux_tva=taux,
                    ventilation_tva=ventilation, created_by=user)
            # ATOT27 — brouillon hors série ; numéro légal à l'émission.
            document = create_provisoire(_facture)
            activity.log_devis_note(
                devis, user,
                f'Facture complémentaire {document.reference} (brouillon) : '
                f'{montant_ttc:.2f} MAD TTC — écart de révision.')
        else:
            # ATOT45 — LE constructeur d'avoir d'écart (ATOT43) : plafond par
            # facture, répartition, statuts recalculés, ``avoir_cree``.
            from apps.ventes.domain.facturation_vente import (
                crediter_ecart_de_vente)
            avoirs = crediter_ecart_de_vente(
                devis, montant_ttc, paniers or [
                    {'taux': taux, 'base_ht': montant_ht,
                     'montant': montant_tva}], user=user,
                motif=(f'Révision {devis.reference} (remplace '
                       f'{precedent.reference}) — écart de révision.'))
            # ATOT22 — le taux de l'écart, jamais celui de la facture visée.
            Avoir.objects.filter(pk__in=[a.pk for a in avoirs]).update(
                taux_tva=taux)
            document = avoirs[0]
            activity.log_devis_note(devis, user, 'Avoir(s) ' + ', '.join(
                f'{a.reference} : {a.montant_ttc:.2f} MAD TTC sur '
                f'{a.facture.reference}' for a in avoirs)
                + ' — écart de révision.')
        resultat['document'] = resultat['document'] or document
    return resultat


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (règle de ``domain/__init__.py``) : ils s'exécutent
# après toutes les définitions de ce module et visent le module qui PORTE le
# corps — jamais la façade. ``cloner_devis`` reste un import FONCTION-LOCAL de
# ``reviser_devis`` (déplacement pur).
from apps.ventes.domain.etudes import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    etude_params_pour_copie,
    rafraichir_etudes_du_devis,
)
# QJR84 — l'écrivain unique des lignes (le seul constructeur de LigneDevis).
from apps.ventes.domain.lignes import cloner_lignes  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
from apps.ventes.domain.tarification import prix_applicable  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
