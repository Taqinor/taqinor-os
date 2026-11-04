"""ASTK263 (C-ASTK-VER4-060, D-ASTK-VER4-1 = retour_annulation) — reprise
d'une réservation de chantier que la vente avait SOLDÉE quand la facture
annulée a rendu son stock (ASTK262). Nouveau fichier car : ``services.py``
(7 894 l.) est un mur. Les marqueurs « <produit_id>:<qte> » de
``solder_reservations_vente`` se lisent ici en NET (contre-marqueurs
négatifs compris)."""
from decimal import Decimal


def net_marqueurs_vente(installation, produit_id, reference=None):
    """Σ net des marqueurs de solde vente du chantier pour ce produit (sous
    ``reference`` si donnée), contre-marqueurs « <pid>:-<n> » compris."""
    from .models import InstallationActivity
    from .services import _MARQUEUR_SOLDE_VENTE
    qs = InstallationActivity.objects.filter(
        installation=installation, field=_MARQUEUR_SOLDE_VENTE,
        new_value__startswith=f'{produit_id}:')
    if reference is not None:
        qs = qs.filter(old_value=reference)
    total = Decimal('0')
    for valeur in qs.values_list('new_value', flat=True):
        try:
            total += Decimal(valeur.split(':', 1)[1])
        except (IndexError, ArithmeticError, ValueError):
            continue
    return total


def rouvrir_reservations_vente(installation, reference, user=None):
    """Rouvre, par produit, ``max(0, net des marqueurs sous reference −
    max(0, Σ SORTIE − Σ ENTRÉE sous reference))`` : ``quantite += rouvre``,
    ``consomme=False``, contre-marqueur ``<produit_id>:-<rouvre>`` (même
    ``old_value``) + note chatter. No-op pour un chantier annulé ou clôturé ;
    idempotent (le contre-marqueur annule le net). Renvoie le nombre de
    réservations rouvertes."""
    from django.db.models import Sum
    from apps.stock.selectors import mouvements_par_reference
    from apps.stock.services import (
        mouvement_type_entree, mouvement_type_sortie,
    )
    from .models import Installation, InstallationActivity, StockReservation
    from .services import _MARQUEUR_SOLDE_VENTE
    reference = str(reference or '').strip()
    if installation is None or not reference or installation.annule or (
            Installation.canonical_statut(installation.statut)
            == Installation.Statut.CLOTURE):
        return 0
    produits = {v.split(':', 1)[0] for v in InstallationActivity.objects
                .filter(installation=installation, field=_MARQUEUR_SOLDE_VENTE,
                        old_value=reference)
                .values_list('new_value', flat=True)}
    signe = {mouvement_type_sortie(): 1, mouvement_type_entree(): -1}
    sorti = {}
    for row in (mouvements_par_reference(installation.company, reference)
                .filter(type_mouvement__in=list(signe)).order_by()
                .values('produit_id', 'type_mouvement')
                .annotate(t=Sum('quantite'))):
        sorti[row['produit_id']] = (sorti.get(row['produit_id'], 0)
                                    + signe[row['type_mouvement']] * row['t'])
    rouvertes = 0
    for pid in sorted(int(p) for p in produits if p.isdigit()):
        rouvre = int(max(Decimal('0'), net_marqueurs_vente(
            installation, pid, reference) - max(0, sorti.get(pid, 0))))
        resa = (StockReservation.objects.select_for_update()
                .filter(installation=installation, produit_id=pid,
                        active=True).order_by('-id').first())
        if rouvre <= 0 or resa is None:
            continue
        resa.quantite += rouvre
        resa.consomme = False
        resa.date_consommation = None
        resa.save(update_fields=['quantite', 'consomme', 'date_consommation'])
        InstallationActivity.objects.create(
            company=installation.company, installation=installation,
            user=user, kind=InstallationActivity.Kind.NOTE,
            field=_MARQUEUR_SOLDE_VENTE, old_value=reference,
            new_value=f'{pid}:-{rouvre}',
            body=(f'Réservation rouverte : {rouvre} rendu(s) au stock par '
                  f'l\'annulation de la facture ({reference}).'))
        rouvertes += 1
    return rouvertes
