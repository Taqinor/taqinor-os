"""« Utilisé dans » : leads utilisant un produit (SPL87, scission de
`selectors.py`).

Déplacement pur ; `apps.crm.selectors` ré-exporte le nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.
"""


def leads_utilisant_produit(company, produit_id, limit=20, *, user=None):
    """STKCAT25 — les leads RÉCENTS qui dépendent de ce produit.

    Frontière cross-app : ``apps.stock`` (onglet « Utilisé dans » de la fiche
    produit) lit les leads PAR ICI — jamais un import de ``apps.crm.models``
    depuis une autre app.

    CE QU'« UTILISER » VEUT DIRE ICI, ET RIEN D'AUTRE : un lead utilise un
    produit À TRAVERS SES DEVIS. La jointure passe par le lien devis→lead
    (``ventes.Devis.lead``, ``related_name='devis'``) en pure relation ORM
    string-FK — ``apps.ventes.models`` n'est jamais importé.

    Depuis STKCAT9, ``Lead.structure_produit`` (la structure choisie sur le
    lead) est un SECOND lien direct : un lead qui a retenu ce produit comme
    structure est listé même sans devis.

    ``user`` (optionnel, mot-clé) rejoue la portée de
    ``LeadViewSet.get_queryset`` — ``scope_queryset(..., ['owner'])`` : un rôle
    restreint ne voit pas par le Stock un lead que /crm/leads lui masque. Sans
    ``user``, la lecture reste bornée à la SOCIÉTÉ (jamais globale).

    Renvoie une liste de dicts ``{id, nom, ville, stage, date}``, du plus
    récent au plus ancien, bornée à ``limit``. ``stage`` est la clé canonique
    de ``STAGES.py`` telle que stockée (l'écran en rend le libellé français).
    Forme contractuelle : ``apps/stock/contract_samples/produit_utilise_dans.json``.
    """
    from django.db.models import Q

    from core.scoping import scope_queryset

    from .models import Lead

    if company is None or not produit_id:
        return []
    try:
        limite = int(limit)
    except (TypeError, ValueError):
        limite = 0
    if limite <= 0:
        return []

    # STKCAT25 bis — deux liens : à travers ses devis, OU directement par la
    # structure choisie sur le lead (``Lead.structure_produit``, STKCAT9).
    qs = Lead.objects.filter(company=company).filter(
        Q(devis__lignes__produit_id=produit_id)
        | Q(structure_produit_id=produit_id))
    # Comme la liste /crm/leads par défaut : les leads archivés n'y figurent pas.
    qs = qs.filter(is_archived=False)
    if user is not None:
        qs = scope_queryset(qs, user, ['owner'])
        # NTADM3 — même périmètre d'entités que LeadViewSet (EntiteScopeMixin).
        from core.entite_scoping import scope_entite_queryset
        qs = scope_entite_queryset(qs, user)
    qs = qs.distinct().order_by('-date_creation', '-id')

    lignes = []
    for lead in qs[:limite]:
        nom = f"{lead.nom or ''} {lead.prenom or ''}".strip()
        lignes.append({
            'id': lead.id,
            'nom': nom,
            'ville': lead.ville or '',
            'stage': lead.stage or '',
            'date': (lead.date_creation.date().isoformat()
                     if lead.date_creation else ''),
        })
    return lignes
