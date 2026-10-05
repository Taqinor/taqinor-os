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
    """NTCPQ13 — Renouvelle un devis déjà ACCEPTÉ (ou expiré/clos).

    Crée un NOUVEAU ``Devis`` en ``brouillon`` reprenant les lignes actuelles
    avec les prix COURANTS recalculés (``prix_applicable`` — jamais une simple
    copie figée), lié au devis source par ``devis_origine`` (racine de chaîne)
    et portant ``numero_renouvellement`` = source + 1.

    DISTINCT de ``reviser`` (T10) : celui-ci crée la V+1 d'un devis envoyé,
    accepté, refusé ou expiré (D-QJR5-2 — un accepté se révise, son chantier
    et son contrat passent à la V2, QJR559) et supersède l'original ;
    ``renouveler`` laisse le devis source
    strictement intact (statut, chaîne BC/Facture, historique).

    Lève ``ValidationError`` si le devis n'est pas dans un état renouvelable.
    Renvoie le nouveau devis."""
    from rest_framework.exceptions import ValidationError
    from django.db import transaction
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from apps.ventes.utils.company_settings import create_numbered

    RENOUVELABLES = (Devis.Statut.ACCEPTE, Devis.Statut.EXPIRE)
    if devis.statut not in RENOUVELABLES:
        raise ValidationError({'statut': (
            'Seul un devis accepté ou expiré peut être renouvelé '
            '(un devis en cours se corrige avec « réviser »).')})

    company = devis.company
    racine = devis.devis_origine or devis
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
            # que QJR117 a fermé pour ``etude_params``. Et ``acompte_pct``
            # (une CONDITION) comme ``custom_data`` manquaient.
            # ``acompte_montant`` reste EXCLU : ce renouvellement re-tarife les
            # lignes au catalogue courant, donc le montant de l'acompte du
            # devis source ne décrit plus ce total.
            echeancier=(list(devis.echeancier)
                        if isinstance(devis.echeancier, list)
                        else devis.echeancier),
            acompte_pct=devis.acompte_pct,
            custom_data=(dict(devis.custom_data)
                         if isinstance(devis.custom_data, dict)
                         else devis.custom_data),
            devise=devis.devise,
            taux_change=devis.taux_change, entite=devis.entite,
            created_by=user, devis_origine=racine,
            numero_renouvellement=(devis.numero_renouvellement or 0) + 1)
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
            return prix_applicable(
                produit=ligne.produit, client=devis.client,
                quantite=ligne.quantite)['prix']
        except Exception:  # noqa: BLE001 — repli sur le prix historique
            logger.exception(
                'NTCPQ13 : prix courant indisponible (ligne %s)', ligne.pk)
            return ligne.prix_unitaire

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
        create_numbered(Devis, company, 'devis', _save)
        nouveau = cree['obj']
        # QJR116 — le renouvellement clone par le MÊME cloneur unique que le
        # duplicata et la gamme sœur (``domain/lignes.cloner_lignes``) ; il
        # n'y ajoute que sa re-tarification. C'est là que la liste maintenue à
        # la main avait le plus divergé : elle clonait ``optionnelle`` sans
        # ``variante``, et aucune des trois ne clonait ``lot``.
        cloner_lignes(devis, nouveau, prix_unitaire=_prix_courant)
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
    """QJR521 — une révision refusée (déjà remplacé, brouillon) → 409."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def reviser_devis(devis, *, user=None):
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
    ``superseded_by`` bougent. Renvoie la nouvelle version."""
    from django.db import transaction
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from apps.ventes.domain.creation_clone import cloner_devis

    with transaction.atomic():
        old = (Devis.objects.select_for_update(of=('self',))
               .get(pk=devis.pk))
        if not old.is_active:
            ref = (Devis.objects.filter(pk=old.superseded_by_id)
                   .values_list('reference', flat=True).first()
                   if old.superseded_by_id else None)
            raise RevisionError(
                f'Déjà remplacé par {ref}.' if ref
                else 'Ce devis est archivé : il ne se révise plus.')
        if old.statut == Devis.Statut.BROUILLON:
            raise RevisionError(
                'Un brouillon se modifie directement (pas de révision).')
        # QJR558 — ``revision=True`` : la V+1 garde le travail manuel
        # (toiture 3D, registre D12, tailles explorées, rendu toiture).
        nd = cloner_devis(
            old, user=user, note=old.note,
            version=old.version + 1,
            version_parent=old.version_parent or old, revision=True)
        old.is_active = False
        old.superseded_by = nd
        old.save(update_fields=['is_active', 'superseded_by'])
        activity.log_devis_note(
            old, user, f'Remplacé par {nd.reference} (révision).')
        activity.log_devis_note(
            nd, user, f'Révision de {old.reference}.')
    return nd


def rattacher_aval_financier_revision(devis, *, user=None):
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
       (rattachée à la V2), reste < 0 → AVOIR sur la dernière facture.

    La commission apporteur encore À_PAYER est recalculée par ``crm`` sur
    l'option acceptée de la V2 (``crm/receivers.py``, même événement).

    Rend un dict ``{bc, factures, sources, ecart_ttc, document}`` ou ``None``
    quand aucun prédécesseur accepté n'existe."""
    from decimal import Decimal

    from apps.ventes import activity
    from apps.ventes.models import (
        Avoir, BonCommande, Devis, Facture, FactureSource)
    from apps.ventes.selectors import devis_predecesseurs_revision_ids
    from apps.ventes.utils.company_settings import create_numbered
    from apps.ventes.utils.echeancier import (
        blended_tva_pct, factures_actives, next_tranche)
    from apps.ventes.utils.options import option_totaux

    preds = devis_predecesseurs_revision_ids(devis)
    if not preds:
        return None
    acceptes = list(Devis.objects.filter(
        pk__in=preds, company_id=devis.company_id,
        statut=Devis.Statut.ACCEPTE))
    if not acceptes:
        return None
    acceptes.sort(key=lambda d: preds.index(d.pk))  # le plus proche d'abord
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
    actives = {f.pk: f for f in factures_actives(devis)}
    from apps.ventes.selectors import factures_via_bon_commande
    via_bc = {f.pk: f for f in factures_via_bon_commande(devis)}
    actives.update(via_bc)
    document = None
    if not actives:
        # Rien de facturé : l'échéancier de la V2 facturera la V2.
        return {'bc': bc, 'factures': factures, 'sources': sources,
                'ecart_ttc': ecart, 'document': None}
    facture_ttc = sum((Decimal(str(f.total_ttc)) for f in actives.values()),
                      Decimal('0'))
    avoirs_ttc = sum((Decimal(str(f.avoirs_total)) for f in actives.values()),
                     Decimal('0'))
    from core.money import quantize_mad
    reste = quantize_mad(Decimal(str(option_totaux(devis)['ttc']))
                         - facture_ttc + avoirs_ttc)
    encore_une_tranche = (not via_bc) and next_tranche(devis) is not None
    if reste == 0 or (encore_une_tranche and reste > 0):
        activity.log_devis_note(
            devis, user,
            f'Écart de révision {ecart:.2f} MAD TTC porté par la suite de '
            f"l'échéancier (reste à facturer {reste:.2f} MAD).")
        return {'bc': bc, 'factures': factures, 'sources': sources,
                'ecart_ttc': ecart, 'document': None}

    taux = blended_tva_pct(devis)
    montant_ttc = abs(reste)
    montant_ht = quantize_mad(montant_ttc / (1 + Decimal(str(taux)) / 100))
    montant_tva = montant_ttc - montant_ht
    company = devis.company
    if reste > 0:
        def _facture(ref):
            return Facture.objects.create(
                company=company, reference=ref, devis=devis,
                client=devis.client, lead=devis.lead,
                statut=Facture.Statut.BROUILLON,
                type_facture=Facture.TypeFacture.COMPLETE,
                libelle=(f'Complément révision {devis.reference} '
                         f'(remplace {precedent.reference})')[:255],
                montant_ht=montant_ht, montant_tva=montant_tva,
                montant_ttc=montant_ttc, taux_tva=taux, created_by=user)
        document = create_numbered(Facture, company, 'facture', _facture)
        activity.log_devis_note(
            devis, user,
            f'Facture complémentaire {document.reference} (brouillon) : '
            f'{montant_ttc:.2f} MAD TTC — écart de révision.')
    else:
        # La facture qui peut le plus porter l'avoir (plafond AUD126 : jamais
        # au-delà du reste créditable) ; à reste égal, la plus récente.
        cible = max(actives.values(), key=lambda f: (
            Decimal(str(f.total_ttc)) - Decimal(str(f.avoirs_total)), f.pk))

        def _avoir(ref):
            return Avoir.objects.create(
                company=company, reference=ref, facture=cible,
                client=cible.client, statut=Avoir.Statut.EMISE,
                motif=(f'Révision {devis.reference} (remplace '
                       f'{precedent.reference}) — écart de révision.'),
                taux_tva=taux, montant_ht=montant_ht,
                montant_tva=montant_tva, montant_ttc=montant_ttc,
                created_by=user)
        document = create_numbered(Avoir, company, 'avoir', _avoir)
        activity.log_facture_avoir(cible, user, document)
        activity.log_devis_note(
            devis, user,
            f'Avoir {document.reference} : {montant_ttc:.2f} MAD TTC sur '
            f'{cible.reference} — écart de révision.')
    return {'bc': bc, 'factures': factures, 'sources': sources,
            'ecart_ttc': ecart, 'document': document}


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER (règle de ``domain/__init__.py``) : ils s'exécutent
# après toutes les définitions de ce module et visent le module qui PORTE le
# corps — jamais la façade. ``cloner_devis`` reste un import FONCTION-LOCAL de
# ``reviser_devis`` (déplacement pur).
from apps.ventes.domain.etudes import (  # noqa: E402
    etude_params_pour_copie,
    rafraichir_etudes_du_devis,
)
# QJR84 — l'écrivain unique des lignes (le seul constructeur de LigneDevis).
from apps.ventes.domain.lignes import cloner_lignes  # noqa: E402
from apps.ventes.domain.tarification import prix_applicable  # noqa: E402
