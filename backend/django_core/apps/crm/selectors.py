"""Sélecteurs LECTURE SEULE du domaine CRM exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les clients à travers ces
fonctions plutôt qu'en important `apps.crm.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""


def client_base_qs(company=None):
    """Queryset Client, scopé société si fournie. Lecture seule."""
    from .models import Client
    qs = Client.objects.all()
    if company is not None:
        qs = qs.filter(company=company)
    return qs


def find_client_by_email(from_email, company=None):
    """Client dont l'email correspond (insensible à la casse), ou None. Scopé
    société si fournie."""
    if not from_email:
        return None
    return client_base_qs(company).filter(
        email__iexact=from_email.strip()).first()


def client_credit_warning(client, montant_ttc_nouveau=None):
    """FG41 — encours client + avertissement plafond.

    Calcule l'encours TTC total des factures ouvertes (émises + en_retard) de
    ce client, l'additionne avec un nouveau montant éventuel, et renvoie un dict :

    ::
        {
          'plafond': Decimal | None,   # plafond défini sur le client
          'encours': Decimal,          # encours actuel (TTC facturé non payé)
          'encours_avec_nouveau': Decimal | None,   # si montant_ttc_nouveau fourni
          'depasse': bool,             # encours actuel > plafond
          'depassera': bool | None,    # encours+nouveau > plafond (si applicable)
          'message': str | None,       # message d'avertissement prêt à l'affichage
        }

    ``depasse=False`` et ``depassera=False`` quand aucun plafond n'est défini.
    Lecture seule — jamais de blocage, uniquement utilisé pour les avertissements.
    """
    from decimal import Decimal
    # Import local pour éviter les cycles crm ↔ ventes au module scope.
    from apps.ventes.models import Facture
    STATUTS_OUVERTS = (
        Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value,
    )
    # montant_du de chaque facture ouverte (TTC − payé − avoirs).
    factures_ouvertes = Facture.objects.filter(
        client=client, statut__in=STATUTS_OUVERTS,
    ).prefetch_related('paiements', 'avoirs')
    encours = sum(
        (f.montant_du for f in factures_ouvertes), Decimal('0'))

    plafond = getattr(client, 'plafond_credit', None)
    depasse = plafond is not None and encours > plafond

    encours_avec_nouveau = None
    depassera = None
    if montant_ttc_nouveau is not None:
        montant_ttc_nouveau = Decimal(str(montant_ttc_nouveau))
        encours_avec_nouveau = encours + montant_ttc_nouveau
        depassera = plafond is not None and encours_avec_nouveau > plafond

    # Message d'avertissement (français, prêt pour l'UI).
    message = None
    if plafond is not None:
        if depassera:
            message = (
                f"⚠ Plafond de crédit dépassé : encours actuel "
                f"{encours:.2f} MAD + {montant_ttc_nouveau:.2f} MAD = "
                f"{encours_avec_nouveau:.2f} MAD > plafond {plafond:.2f} MAD."
            )
        elif depasse:
            message = (
                f"⚠ Plafond de crédit dépassé : encours {encours:.2f} MAD "
                f"> plafond {plafond:.2f} MAD."
            )

    return {
        'plafond': plafond,
        'encours': encours,
        'encours_avec_nouveau': encours_avec_nouveau,
        'depasse': depasse,
        'depassera': depassera,
        'message': message,
    }


def get_company_lead(company, lead_id):
    """B1 — Lead borné à la société, ou None. Point d'entrée cross-app pour que
    ventes résolve un lead par id sans importer ``apps.crm.models`` (un id d'une
    autre société renvoie None → l'appelant répond 404). Lecture seule."""
    if not lead_id:
        return None
    from .models import Lead
    return Lead.objects.filter(pk=lead_id, company=company).first()


def get_company_client(company, client_id):
    """B1 — Client borné à la société, ou None (cf. get_company_lead)."""
    if not client_id:
        return None
    return client_base_qs(company).filter(pk=client_id).first()


def lead_bills_for_devis(devis):
    """Factures électriques RÉELLES (MAD/mois) du lead d'un devis, ou None.

    Point d'entrée cross-app LECTURE SEULE pour que ``ventes`` lise le profil de
    facture sans importer ``apps.crm.models``. Résolution : le lead lié au devis
    en priorité, sinon le premier lead rattaché au client du devis. Renvoie un
    dict ``{'facture_hiver', 'facture_ete', 'ete_differente'}`` (floats/None +
    bool) quand une facture d'hiver existe, sinon None (la page masque alors le
    graphe de consommation). Aucune donnée fabriquée."""
    lead = getattr(devis, 'lead', None)
    if lead is None:
        client_id = getattr(devis, 'client_id', None)
        if client_id:
            from .models import Lead
            lead = (
                Lead.objects
                .filter(client_id=client_id,
                        company_id=getattr(devis, 'company_id', None))
                .order_by('-date_creation')
                .first()
            )
    if lead is None or lead.facture_hiver in (None, ''):
        return None
    return {
        'facture_hiver': float(lead.facture_hiver),
        'facture_ete': (float(lead.facture_ete)
                        if lead.facture_ete not in (None, '') else None),
        'ete_differente': bool(lead.ete_differente),
    }


def lead_card(lead_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un lead pour le partage dans la
    messagerie. Scopée société : renvoie None si le lead n'appartient pas à la
    société (jamais d'accès cross-tenant). Format {label, subtitle, url}."""
    from .models import Lead
    lead = Lead.objects.filter(pk=lead_id, company=company).first()
    if lead is None:
        return None
    nom = ' '.join(p for p in [lead.nom, (lead.prenom or '')] if p).strip()
    label = nom or f'Lead #{lead.pk}'
    parts = []
    try:
        parts.append(lead.get_stage_display())
    except Exception:  # pragma: no cover - défensif
        pass
    if lead.ville:
        parts.append(lead.ville)
    return {
        'label': label,
        'subtitle': ' · '.join(parts),
        'url': f'/leads/{lead.pk}',
    }
