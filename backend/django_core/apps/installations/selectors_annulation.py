"""Sélecteur cross-app : le blocage d'une annulation d'acceptation par le chantier
(module à part : ``selectors.py`` est un fichier mur, garde C20)."""


def blocage_annulation_acceptation(devis_id, company):
    """Décision fondateur (08/10/2026) — le chantier né de l'acceptation du
    devis ``devis_id`` empêche-t-il d'annuler cette acceptation ?

    Raison en français, ou ``None`` si chaque chantier non annulé est INITIAL :
    « Signé », ni pose, ni intervention DATÉE (ACSV90), ni stock SORTI, ni BCF envoyé ou
    reçu tant qu'il n'est pas annulé (D-ADVS-5, ACSV6). Une réservation non consommée est libérée par l'annulation.
    Lecture seule, bornée à ``company`` (jamais de fuite cross-tenant)."""
    from apps.achats.selectors import bcf_du_chantier
    from .models import Installation
    qs = Installation.objects.filter(devis_id=devis_id, annule=False)
    if company is not None:
        qs = qs.filter(company=company)
    for inst in qs.order_by('pk'):
        if (Installation.canonical_statut(inst.statut)
                != Installation.Statut.SIGNE):
            return (f'le chantier {inst.reference} est déjà à l’étape '
                    f'« {inst.get_statut_display()} ».')
        if inst.date_pose_prevue is not None:
            return (f'la pose du chantier {inst.reference} est déjà '
                    'planifiée.')
        nb = inst.interventions.filter(
            annulee=False, date_prevue__isnull=False).count()
        if nb:
            return (f'le chantier {inst.reference} a déjà {nb} '
                    "intervention(s) planifiée(s). Annulez-les d'abord.")
        if inst.reservations.filter(consomme=True).exists():
            return (f'du stock a déjà été sorti pour le chantier '
                    f'{inst.reference}.')
        for bon in bcf_du_chantier(inst):
            if bon['statut'] in ('envoye', 'recu'):
                etat = 'reçu' if bon['statut'] == 'recu' else 'envoyé'
                return (f"le bon de commande fournisseur {bon['reference']} "
                        f"est {etat} : annulez-le d'abord.")
    return None
