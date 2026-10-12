"""Annulation d'une facture — le service unique (Groupe VNT).

VNT10 — DÉPLACEMENT PUR du corps de ``FactureViewSet.annuler``
(``views/facture.py``) : la vue n'est plus qu'un délégué mince, et une
commande ou « Prix négocié » peuvent annuler une facture sans passer par HTTP.
Comportement inchangé au caractère près : chaque ``return Response(..., 400)``
de la vue est devenu ``raise AnnulationRefusee(<même corps>)`` ; la vue le
renvoie tel quel en 400.
"""
from decimal import Decimal

from django.db import transaction


#: VNT12 — directive : les paiements deviennent une avance client (XFAC1).
GARDER_EN_AVANCE = 'garder_en_avance'


class AnnulationRefusee(Exception):
    """L'annulation est refusée : ``corps`` = le corps JSON du 400, tel quel."""

    def __init__(self, corps):
        super().__init__(corps.get('detail', ''))
        self.corps = corps


def _refuser_payee(facture, action):
    """VNT12 — une PAYÉE ne s'annule qu'avec ``garder_en_avance`` ; sans
    directive, l'argent qu'elle porte est nommé (``directive_acompte_requise``,
    contrat ``facture_annulation.json``)."""
    if action == GARDER_EN_AVANCE:
        return
    if not action:
        _refuser_si_argent(facture, Decimal(str(facture.montant_paye)))
    raise AnnulationRefusee(
        {'detail': 'Une facture payée ne peut pas être annulée.'},
    )


def _refus_prealable(facture, action=''):
    """Refus lus HORS verrou : payée (VNT12 : sauf garde en avance), déjà
    annulée, ND active (AFAC32), avoir actif (AFAC12)."""
    from ..models import Facture
    if facture.statut == Facture.Statut.PAYEE:
        _refuser_payee(facture, action)
    if facture.statut == Facture.Statut.ANNULEE:
        raise AnnulationRefusee(
            {'detail': 'Cette facture est déjà annulée.'},
        )

    # AFAC32 (D-AFAC-C4) — jamais une note de débit ÉMISE sur une facture
    # annulée : la ND active s'annule d'abord (par avoir de ND).
    from .facturation_ops import notes_debit_actives
    nd_actives = notes_debit_actives(facture)
    if nd_actives:
        raise AnnulationRefusee(
            {'detail': (
                'Cette facture porte une note de débit active ('
                + ', '.join(nd.reference for nd in nd_actives)
                + ') : annulez-la d\'abord (avoir de note de débit).'
            ),
             'code': 'note_debit_active'},
        )
    # AFAC12 (C-AFAC-002) — jamais une facture annulée sous un avoir
    # ACTIF : l'avoir crédite une facture vivante ; il s'annule d'abord.
    # L'avoir de note de débit (AFAC32 : il NEUTRALISE une ND, `note_debit_id`
    # renseigné) n'est pas un crédit client : il ne bloque pas l'annulation.
    avoirs_actifs = [a for a in facture.avoirs.all()
                     if a.statut != 'annulee'
                     and getattr(a, 'note_debit_id', None) is None]
    if avoirs_actifs:
        raise AnnulationRefusee(
            {'detail': (
                'Cette facture porte un avoir actif ('
                + ', '.join(a.reference for a in avoirs_actifs)
                + ") : annulez-le d'abord."
            ),
             'code': 'avoir_actif'},
        )


def _cible_du_transfert(locked, directive, net_acompte):
    """FG50 / AFAC9 / AUD125 — la facture cible du transfert, validée sous
    le verrou (même société, même devis, vivante, encaissable, et qui
    peut absorber le net transféré)."""
    from ..models import Facture
    if net_acompte <= 0:
        raise AnnulationRefusee(
            {'detail': (
                'Aucun acompte à transférer sur cette facture.'
            )},
        )
    cible_id = directive.get('facture_cible')
    if not cible_id:
        raise AnnulationRefusee(
            {'detail': 'La facture cible est requise.'},
        )
    try:
        cible_id = int(cible_id)
    except (TypeError, ValueError):
        raise AnnulationRefusee(
            {'detail': 'Facture cible invalide.'},
        )
    if cible_id == locked.pk:
        raise AnnulationRefusee(
            {'detail': (
                "La facture cible doit être différente de celle "
                "annulée."
            )},
        )
    # Le devis source doit exister pour relier les deux factures.
    if locked.devis_id is None:
        raise AnnulationRefusee(
            {'detail': (
                "Transfert impossible : la facture n'est pas liée "
                "à un devis."
            )},
        )
    cible = Facture.objects.select_for_update().filter(
        pk=cible_id).first()
    # Validation multi-tenant + même devis + cible vivante.
    if cible is None or cible.company_id != locked.company_id:
        raise AnnulationRefusee(
            {'detail': 'Facture cible inconnue.'},
        )
    if cible.devis_id != locked.devis_id:
        raise AnnulationRefusee(
            {'detail': (
                "La facture cible doit appartenir au même devis."
            )},
        )
    if cible.statut == Facture.Statut.ANNULEE:
        raise AnnulationRefusee(
            {'detail': (
                "Impossible de transférer vers une facture "
                "annulée."
            )},
        )
    # AFAC9 — la facture CIBLE passe LA porte unique
    # d'encaissement (brouillon, soldée, acompte CAD122).
    from .encaissements import motif_non_encaissable
    motif_cible = motif_non_encaissable(cible)
    if motif_cible and cible.statut != Facture.Statut.PAYEE:
        raise AnnulationRefusee(
            {'detail': f'Facture cible : {motif_cible}'},
        )
    # AUD125 — CE QUE LA CIBLE PEUT ABSORBER. Le transfert
    # re-pointait les paiements sans jamais lire `cible.montant_du`
    # ni le comparer au net transféré : un acompte de 30 000
    # déplacé sur une facture de solde de 20 000 créait un
    # trop-perçu de 10 000 INVISIBLE (aucune des deux factures ne
    # le signale). La garde est la même que celle du chemin
    # unitaire (ERR72) : tolérance d'un centime, lecture sous le
    # verrou déjà pris sur la cible.
    from core.money import quantize_mad
    reste_cible = cible.montant_du
    if quantize_mad(net_acompte) - reste_cible > Decimal('0.01'):
        raise AnnulationRefusee(
            {'detail': (
                f"L'acompte transféré "
                f"({quantize_mad(net_acompte):.2f} MAD) dépasse le "
                f"reste à payer de la facture cible "
                f"({reste_cible:.2f} MAD)."
            )},
        )
    return cible


def _contre_passer(locked, user, motif=''):
    """VNT11 (D-VNT-1) — passe ``locked`` ANNULÉE ; renvoie l'avoir ou None.

    Le critère est la RÉFÉRENCE, pas le statut : une référence LÉGALE (émise,
    payée, en retard, ou brouillon remis en brouillon) est contre-passée par
    un avoir CORRECTION émis — LE constructeur unique ``creer_avoir_facture``
    en mode ``contre_passation`` (numéro ``create_numbered``, ventilation TVA,
    chatter, ``avoir_cree``, bascule ANNULÉE) : jamais un trou ni une
    réutilisation de numéro. Un ``BROUILLON-<id>`` n'a rien à contre-passer :
    il bascule seul. L'avoir d'une annulée ne double-compte pas : les
    lecteurs (``avoirs_correction``, ``plan_facturation``) ne lisent que les
    factures actives."""
    from core.numbering import est_reference_provisoire
    from ..models import Avoir, Facture
    if est_reference_provisoire(locked.reference):
        locked.statut = Facture.Statut.ANNULEE
        locked.save(update_fields=['statut'])
        return None
    from .facturation_ops import AvoirRefuse, creer_avoir_facture
    try:
        avoir = creer_avoir_facture(
            facture=locked, user=user,
            motif=motif or f'Annulation de la facture {locked.reference}',
            mode='contre_passation', type_avoir=Avoir.Type.CORRECTION)
    except AvoirRefuse as refus:
        raise AnnulationRefusee({'detail': refus.motif,
                                 'code': 'avoir_refuse'})
    locked.refresh_from_db()
    return avoir


def _transferer_acompte(locked, directive, paiements, net_acompte, user,
                        motif=''):
    """FG50 — re-pointe l'acompte (paiements + avances ventilées) vers la
    cible, annule la facture morte (VNT11 : avoir si référence légale),
    solde la cible si couverte (AUD125)."""
    from .. import activity
    from ..models import Facture, Paiement
    cible = _cible_du_transfert(locked, directive, net_acompte)
    # Re-pointe les paiements vers la cible : les soldes des deux
    # factures se redérivent (propriétés calculées).
    nb = len(paiements)
    from .encaissements import _rattacher_paiement
    for p in paiements:
        # AFAC17 — LE geste de déplacement partagé avec
        # ``reaffecter_paiement``.
        _rattacher_paiement(p, cible)
    # AFAC12 — les avances VENTILÉES suivent aussi : le net
    # transféré (``montant_paye``) les comptait déjà, mais elles
    # restaient sur la facture morte (la cible recevait moins).
    for a in locked.affectations_paiement.select_related(
            'paiement'):
        if a.paiement.statut in Paiement.STATUTS_NON_COMPTES:
            continue
        a.facture = cible
        a.save(update_fields=['facture'])
        nb += 1
    locked.avoir_annulation = _contre_passer(locked, user, motif)
    activity.log_facture_acompte_transfere_sortie(
        locked, user, cible, net_acompte, nb)
    activity.log_facture_acompte_transfere_entree(
        cible, user, locked, net_acompte, nb)
    # AUD125 (moitié restante) — quand le transfert SOLDE la
    # cible, elle doit basculer PAYÉE et émettre `facture_payee`,
    # faute de quoi elle reste EMISE donc relancée bien
    # qu'entièrement couverte. Cette bascule DOIT passer par le
    # service unique `marquer_facture_soldee` d'AUD102 : le
    # dépôt compte déjà neuf transitions concurrentes, en écrire
    # une dixième ici est exactement ce qu'AUD125 interdit.
    # AUD102 est sur cette base : bascule par LE service unique,
    # sur la cible rafraîchie — jamais une 10e transition manuelle.
    cible.refresh_from_db()
    if cible.montant_du <= 0 and cible.statut != Facture.Statut.PAYEE:
        from .encaissements import marquer_facture_soldee
        marquer_facture_soldee(
            cible, montant=net_acompte, user=user,
            source='transfert_acompte')
    return locked


def _reclasser_avance(paiement):
    """VNT12 — ``statut_affectation`` d'une avance redérivé de ce qu'il lui
    reste ventilé (aucune → non affectée ; une part → partiellement)."""
    from ..models import Paiement
    paiement.refresh_from_db()
    if paiement.facture_id is not None:
        return
    ventile = sum((a.montant for a in paiement.affectations.all()),
                  Decimal('0'))
    if ventile <= 0:
        statut = Paiement.StatutAffectation.NON_AFFECTE
    elif paiement.montant - ventile > 0:
        statut = Paiement.StatutAffectation.PARTIELLEMENT_AFFECTE
    else:
        statut = Paiement.StatutAffectation.AFFECTE
    if paiement.statut_affectation != statut:
        paiement.statut_affectation = statut
        paiement.save(update_fields=['statut_affectation'])


def _garder_en_avance(locked, paiements, net_acompte, user):
    """VNT12 — directive ``garder_en_avance`` : les paiements comptés de la
    facture sont DÉTACHÉS et deviennent une avance client non affectée
    (XFAC1 : ``facture`` vide, ``client`` posé) ; les avances ventilées sur
    elle sont DÉFAITES (l'affectation disparaît, l'avance retrouve son
    disponible). Jamais un paiement supprimé ni recréé : la trace reste."""
    from ..models import FactureActivity, Paiement
    if net_acompte <= 0:
        raise AnnulationRefusee(
            {'detail': 'Aucun paiement à garder en avance sur cette facture.'},
        )
    if locked.client_id is None:
        raise AnnulationRefusee(
            {'detail': (
                "Une avance exige un client : cette facture n'en a pas.")},
        )
    if any(p.montant < 0 for p in paiements):
        raise AnnulationRefusee(
            {'detail': (
                'Cette facture porte déjà un remboursement : choisissez '
                '« rembourser » pour le reste.')},
        )
    for p in paiements:
        p.facture = None
        p.client_id = locked.client_id
        p.statut_affectation = Paiement.StatutAffectation.NON_AFFECTE
        p.save(update_fields=['facture', 'client', 'statut_affectation'])
    for a in list(locked.affectations_paiement.select_related('paiement')):
        if a.paiement.statut in Paiement.STATUTS_NON_COMPTES:
            continue
        avance = a.paiement
        a.delete()
        _reclasser_avance(avance)
    FactureActivity.objects.create(
        company=locked.company, facture=locked, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='acompte', field_label='Acompte gardé en avance',
        old_value=str(net_acompte),
        body=(f'{net_acompte} MAD gardés en avance client (non affectée) à '
              "l'annulation de la facture."))


def _refuser_si_argent(locked, net_acompte):
    """AFAC12 — sans directive, une facture qui porte de l'argent est
    refusée (400 ``directive_acompte_requise``)."""
    if net_acompte > 0:
        from .encaissements import (
            argent_rattache, decrire_argent_rattache,
        )
        argent = argent_rattache(locked)
        raise AnnulationRefusee(
            {'code': 'directive_acompte_requise',
             'detail': (
                 "Cette facture porte de l'argent ("
                 + decrire_argent_rattache(argent)
                 + ') : choisissez de le transférer vers une '
                 'autre facture du devis ou de le rembourser '
                 "avant d'annuler."),
             'argent_rattache': {
                 cle: f'{Decimal(str(v or 0)):.2f}'
                 for cle, v in argent.items()}},
        )


def annuler_facture(facture, *, user, directive=None, motif=''):
    """Annule une facture — admin only.

    FG50 — sort l'acompte de la facture morte. Le corps peut porter une
    directive ``acompte`` traitant les paiements (acompte) restés sur la
    facture annulée :

      - ``{"acompte": {"action": "transferer", "facture_cible": <id>}}``
        re-pointe TOUS les paiements de la facture annulée vers une AUTRE
        facture (active) du MÊME devis (mêmes société + devis) ; les soldes
        des deux factures se redérivent automatiquement (``montant_paye`` /
        ``montant_du`` sont calculés depuis les lignes Paiement).
      - ``{"acompte": {"action": "rembourser"}}`` écrit un Paiement NÉGATIF
        de contre-passation sur la facture annulée : son ``montant_paye``
        net retombe à 0 et l'écriture négative matérialise l'obligation de
        remboursement (l'acompte n'est plus « coincé » sur une facture
        morte).
      - ``{"acompte": {"action": "garder_en_avance"}}`` (VNT12) : les
        paiements deviennent une avance client non affectée, les avances
        ventilées sont défaites — la SEULE directive qui annule une PAYÉE.

    AFAC12 — sans directive, une facture qui porte de l'argent est
    REFUSÉE (400 ``directive_acompte_requise``) ; une facture sous avoir
    actif aussi (400 ``avoir_actif``). Les avances ventilées suivent le
    transfert.

    VNT11 (D-VNT-1) — chaque branche finit par :func:`_contre_passer` : une
    référence LÉGALE reçoit son avoir de contre-passation CORRECTION (le
    devis est libéré, jamais de trou), un ``BROUILLON-<id>`` bascule seul.
    La facture rendue porte ``avoir_annulation`` (l'avoir, ou None).
    """
    from ..models import Facture, Paiement
    directive = directive or {}
    if not isinstance(directive, dict):
        raise AnnulationRefusee(
            {'detail': 'Directive « acompte » invalide.'},
        )
    acompte_action = (directive.get('action') or '').strip()
    _refus_prealable(facture, acompte_action)

    # Paiements « bloqués » sur la facture morte (l'acompte versé). On ne
    # déplace/contre-passe que le NET : si la facture porte déjà des
    # écritures négatives (remboursement partiel antérieur), elles entrent
    # dans le total.
    from .. import activity
    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        if locked.statut == Facture.Statut.ANNULEE or (
                locked.statut == Facture.Statut.PAYEE
                and acompte_action != GARDER_EN_AVANCE):
            raise AnnulationRefusee(
                {'detail': 'Cette facture ne peut plus être annulée.'},
            )
        # ATOT7 (D-ATOT-4) — LA définition unique du payé : un paiement
        # REJETÉ (chèque impayé) n'est ni remboursé ni transféré, et le
        # net est `Facture.montant_paye` — plus aucune somme locale de
        # `p.montant` (elle remboursait 45 000 jamais encaissés).
        paiements = [p for p in locked.paiements.all()
                     if p.statut not in Paiement.STATUTS_NON_COMPTES]
        net_acompte = Decimal(str(locked.montant_paye))

        if acompte_action == 'transferer':
            facture = _transferer_acompte(
                locked, directive, paiements, net_acompte, user, motif)

        elif acompte_action == 'rembourser':
            if net_acompte <= 0:
                raise AnnulationRefusee(
                    {'detail': (
                        'Aucun acompte à rembourser sur cette facture.'
                    )},
                )
            # Contre-passation : un Paiement négatif soldant l'acompte. Le
            # net retombe à 0 → l'acompte n'est plus « coincé » ; la ligne
            # négative porte l'obligation de remboursement.
            from django.utils import timezone as _tz
            Paiement.objects.create(
                facture=locked, company=locked.company,
                montant=-net_acompte, date_paiement=_tz.now().date(),
                mode=Paiement.Mode.AUTRE,
                note='Remboursement acompte (annulation facture)',
                created_by=user,
            )
            locked.avoir_annulation = _contre_passer(locked, user, motif)
            activity.log_facture_acompte_rembourse(
                locked, user, net_acompte)
            facture = locked

        elif acompte_action == GARDER_EN_AVANCE:
            _garder_en_avance(locked, paiements, net_acompte, user)
            locked.avoir_annulation = _contre_passer(locked, user, motif)
            facture = locked

        elif acompte_action:
            raise AnnulationRefusee(
                {'detail': (
                    "Action acompte invalide. Valeurs : « transferer », "
                    "« rembourser », « garder_en_avance »."
                )},
            )
        else:
            # AFAC12 (C-AFAC-002, D-AFAC-C5 a) — une facture qui porte de
            # l'argent (paiements valides, avances ventilées, escomptes)
            # ne s'annule JAMAIS sans dire où il va : l'argent restait
            # sur une facture morte et la porte suivante re-facturait
            # 100 % (contrat ``facture_annulation.json``).
            _refuser_si_argent(locked, net_acompte)
            # Sans argent rattaché : bascule (+ avoir si référence légale).
            locked.avoir_annulation = _contre_passer(locked, user, motif)
            facture = locked

        # AFAC23 (C-AFAC-018) — les trois branches convergent vers
        # ANNULEE : les liens « Payer en ligne » ouverts sont fermés dans
        # la même transaction (la page client répond « annulé »).
        from .encaissements import fermer_liens_paiement
        from ..models import PaymentLink
        fermer_liens_paiement(facture, PaymentLink.Statut.ANNULE)

    # YEVNT6 — événement documentaire (best-effort), une fois pour les
    # trois branches ci-dessus (toutes convergent vers ANNULEE).
    from core.events import facture_annulee
    facture_annulee.send(
        sender=Facture, instance=facture, company=facture.company)
    return facture


def avoir_annulation_corps(facture):
    """VNT4 — clé ``avoir`` du contrat ``facture_annulation.json`` :
    ``{id, reference, montant}`` (montant TTC en texte décimal) de l'avoir
    de contre-passation posé par :func:`annuler_facture`, ``None`` pour un
    ``BROUILLON-<id>`` (aucun avoir)."""
    avoir = getattr(facture, 'avoir_annulation', None)
    if avoir is None:
        return None
    return {'id': avoir.pk, 'reference': avoir.reference,
            'montant': f'{Decimal(str(avoir.total_ttc)):.2f}'}


def retirer_brouillons_de_la_vente(devis, *, user, motif=''):
    """VNT11 — LE helper partagé par « Prix négocié » et le cycle facture :
    chaque BROUILLON de la vente de ``devis`` (``factures_de_la_vente`` :
    toute la chaîne de versions), sans paiement compté, est ANNULÉ par
    :func:`annuler_facture` — jamais supprimé : un ``BROUILLON-<id>`` bascule
    seul, un brouillon à référence LÉGALE reçoit son avoir. Une facture
    consolidée (devis hors chaîne) n'est jamais retirée ici. Renvoie la liste
    des factures annulées (triée par id)."""
    from ..models import Paiement
    from ..vente_facturation import (
        STATUT_BROUILLON, chaine_vente, factures_de_la_vente)
    ids = {d.pk for d in chaine_vente(devis)}
    retires = []
    for f in factures_de_la_vente(devis):
        if f.statut != STATUT_BROUILLON or f.devis_id not in ids:
            continue
        if any(p.statut not in Paiement.STATUTS_NON_COMPTES
               for p in f.paiements.all()):
            continue
        retires.append(annuler_facture(f, user=user, motif=motif))
    return retires
