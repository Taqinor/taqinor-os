"""NTWMS40 — Sélecteur et service du réappro de casier picking.

``casiers_picking_a_reapprovisionner`` LIT ; ``generer_taches_reappro_interne``
ÉCRIT (idempotent : jamais deux tâches ouvertes sur le même casier cible).
"""
import logging

logger = logging.getLogger(__name__)


def _quantite_en_casier(company, bin_id, produit_id):
    """Quantité indicative du produit dans ce casier (FG319
    ``BinAffectation``) — lue, jamais écrite depuis ``stock``."""
    from apps.installations.models import BinAffectation
    aff = BinAffectation.objects.filter(
        company=company, bin_id=bin_id, produit_id=produit_id).first()
    return int(aff.quantite) if aff else 0


def _casier_source_le_plus_proche(company, seuil, quantite_requise):
    """Casier de STOCKAGE le plus proche du casier cible portant assez de
    stock du produit. « Proche » = plus petit écart d'ordre de parcours
    (FG319 ``BinLocation.ordre``) — jamais un tri arbitraire."""
    from apps.installations.models import BinAffectation

    ordre_cible = getattr(seuil.bin, 'ordre', 0) or 0
    candidats = (BinAffectation.objects
                 .filter(company=company, produit_id=seuil.produit_id,
                         quantite__gte=quantite_requise,
                         bin__archived=False)
                 .exclude(bin_id=seuil.bin_id)
                 .select_related('bin'))
    meilleur, meilleur_ecart = None, None
    for aff in candidats:
        ecart = abs((aff.bin.ordre or 0) - ordre_cible)
        if meilleur_ecart is None or ecart < meilleur_ecart:
            meilleur, meilleur_ecart = aff.bin, ecart
    return meilleur


def casiers_picking_a_reapprovisionner(company):
    """Casiers de picking DUS (quantité < seuil), avec la source proposée.

    Lecture seule. Un casier sans seuil déclaré n'apparaît jamais — c'est ce
    qui rend le lot additif.
    """
    from .models import SeuilReapproCasier

    seuils = (SeuilReapproCasier.objects
              .filter(company=company, actif=True)
              .select_related('bin', 'produit')
              .order_by('bin__ordre', 'bin_id'))
    dus = []
    for seuil in seuils:
        if getattr(seuil.bin, 'archived', False):
            continue
        presente = _quantite_en_casier(company, seuil.bin_id,
                                       seuil.produit_id)
        if presente >= seuil.seuil:
            continue
        manque = max(seuil.cible - presente, 0)
        source = _casier_source_le_plus_proche(company, seuil, manque)
        dus.append({
            'seuil_id': seuil.id,
            'bin': seuil.bin_id,
            'bin_code': seuil.bin.code,
            'zone': seuil.bin.zone or '',
            'produit': seuil.produit_id,
            'produit_nom': seuil.produit.nom,
            'quantite_presente': presente,
            'seuil': seuil.seuil,
            'quantite_cible': seuil.cible,
            'quantite_a_transferer': manque,
            'bin_source': (source.id if source else None),
            'bin_source_code': (source.code if source else ''),
        })
    return dus


def generer_taches_reappro_interne(company, user=None):
    """Crée une tâche de réappro pour chaque casier dû SANS tâche ouverte.

    Idempotent : appelé deux fois de suite, il ne double jamais une tâche
    (contrainte unique partielle sur (société, casier cible, statut ouvert)).
    Renvoie la liste des tâches CRÉÉES.
    """
    from django.db import IntegrityError, transaction

    from .models import TacheReapproInterne

    creees = []
    for du in casiers_picking_a_reapprovisionner(company):
        if du['quantite_a_transferer'] <= 0:
            continue
        try:
            with transaction.atomic():
                if TacheReapproInterne.objects.filter(
                        company=company, bin_cible_id=du['bin'],
                        statut=TacheReapproInterne.Statut.A_FAIRE).exists():
                    continue
                creees.append(TacheReapproInterne.objects.create(
                    company=company, produit_id=du['produit'],
                    bin_cible_id=du['bin'], bin_source_id=du['bin_source'],
                    quantite=du['quantite_a_transferer'], cree_par=user,
                    note=(f"NTWMS40 — casier {du['bin_code']} sous son seuil "
                          f"({du['quantite_presente']} < {du['seuil']}).")))
        except IntegrityError:
            # Course : une autre requête vient de créer la tâche ouverte.
            continue
    logger.info('NTWMS40 taches de reappro creees=%d (company=%s)',
                len(creees), getattr(company, 'id', None))
    return creees
