"""Services (écritures) du module fidélité — NTRET9.

Frontière inter-app (CLAUDE.md) : ce module ne lit ``crm`` QUE via la FK à
chaîne portée par ``CompteFidelite.client`` — jamais un import de
``apps.crm.models``. Aucune écriture dans ``pos``/``ventes``/``crm`` : le
crédit de points est déclenché EXCLUSIVEMENT par l'abonné
``receivers.py`` sur l'événement ``core.events.vente_validee``.
"""
from decimal import ROUND_DOWN, Decimal

from django.db import IntegrityError, transaction
from django.db.models import F

from .models import CompteFidelite, MouvementFidelite, ProgrammeFidelite


def crediter_points_pour_vente(*, company, client, montant_ttc, source_type,
                               source_id=None, user=None):
    """NTRET9 — crédite les points de fidélité pour UNE vente validée.

    BEST-EFFORT et JAMAIS BLOQUANT (appelé depuis un récepteur d'événement,
    ``receivers.py``) : renvoie ``None`` (no-op) si ``company``/``client`` est
    absent, si AUCUN programme n'est ACTIF pour la société (programme
    désactivé = aucun mouvement créé), ou si le montant ne produit aucun point
    entier. Renvoie le ``MouvementFidelite`` créé sinon.
    """
    if company is None or client is None or not montant_ttc:
        return None
    programme = ProgrammeFidelite.objects.filter(
        company=company, actif=True).first()
    if programme is None:
        return None
    montant = Decimal(str(montant_ttc))
    if montant <= 0:
        return None
    points = int((montant * programme.points_par_mad).to_integral_value(
        rounding=ROUND_DOWN))
    if points <= 0:
        return None

    with transaction.atomic():
        compte = CompteFidelite.objects.select_for_update().filter(
            company=company, client=client).first()
        if compte is None:
            try:
                with transaction.atomic():  # savepoint : course de création rare
                    compte = CompteFidelite.objects.create(
                        company=company, client=client, solde_points=0)
            except IntegrityError:
                # Un autre thread a créé le compte entre-temps (client 1-1) :
                # on le relit, verrouillé.
                compte = CompteFidelite.objects.select_for_update().get(
                    company=company, client=client)
        # UPDATE atomique (jamais un read-modify-write applicatif) : compile en
        # `SET solde_points = solde_points + points` côté base.
        CompteFidelite.objects.filter(pk=compte.pk).update(
            solde_points=F('solde_points') + points)
        compte.refresh_from_db(fields=['solde_points'])
        mouvement = MouvementFidelite.objects.create(
            company=company, compte=compte,
            type_mouvement=MouvementFidelite.TypeMouvement.GAIN,
            points=points, source_type=source_type, source_id=source_id,
            montant_source=montant,
            motif=f"Vente {source_type} #{source_id}" if source_id
            else f"Vente {source_type}",
            created_by=user,
        )
    return mouvement
