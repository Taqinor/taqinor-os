"""COP-G4 — libellés des devis et des factures nommés dans l'aperçu d'une
proposition de l'assistant, pour ``GET /api/django/agent/libelles/``.

Lecture seule, bornée à la SOCIÉTÉ et à la PORTÉE de l'utilisateur, avec la
règle de visibilité des viewsets (créateur dans la portée ; pour un devis, le
responsable du lead voit aussi les devis de SON lead ; périmètre d'entités).
Un objet inconnu, d'une autre société ou hors portée est ABSENT du résultat,
jamais une erreur. Le montant d'un devis est son total TTC, celui d'une facture
son total TTC et son reste dû — jamais un prix d'achat ni une marge. Montants
formatés par le formateur unique ``core.formats_fr`` (comme les documents).

Point d'entrée cross-app : ``apps.ventes.selectors`` (façade) a atteint les 2 000
lignes et ne grossit plus — l'app ``agent`` importe CE module de sélecteurs.
"""
from decimal import Decimal

from core.formats_fr import formater_montant, formater_nombre

DEVISE = 'MAD'


def _montant_ttc(valeur):
    return f'{formater_montant(Decimal(str(valeur or 0)), DEVISE)} TTC'


def _client_nom(document):
    client = getattr(document, 'client', None)
    return (getattr(client, 'nom', '') or '').strip()


def _assembler(*morceaux):
    return ' — '.join(m for m in morceaux if m)


def _devis_visibles(user):
    """Devis de la société que ``user`` voit (même règle que ``DevisViewSet``)."""
    from django.db.models import Q

    from authentication.scoping import visible_user_ids
    from core.entite_scoping import scope_entite_queryset

    from apps.crm.selectors import lead_ids_du_responsable

    from .models import Devis

    qs = Devis.objects.filter(company_id=user.company_id)
    visibles = visible_user_ids(user)
    if visibles is not None:
        qs = qs.filter(Q(created_by__in=visibles)
                       | Q(lead_id__in=lead_ids_du_responsable(user)))
    return scope_entite_queryset(qs, user, 'entite')


def _factures_visibles(user):
    from authentication.scoping import scope_queryset
    from core.entite_scoping import scope_entite_queryset

    from .models import Facture

    qs = scope_queryset(
        Facture.objects.filter(company_id=user.company_id), user,
        ['created_by'])
    return scope_entite_queryset(qs, user, 'entite')


def _libelle_devis(devis):
    """« DEV-202611-0045 — Benali — 84 500,00 MAD TTC (envoyé) »."""
    from .selectors import montants_devis

    ttc = montants_devis([devis.pk], devis.company).get(
        devis.pk, {}).get('ttc')
    return _assembler(devis.reference, _client_nom(devis),
                      _montant_ttc(ttc)) + f' ({devis.get_statut_display().lower()})'


def _libelle_facture(facture):
    """« FAC-202611-0012 — Benali — 25 350,00 MAD TTC, reste dû 25 350,00 »."""
    montant = _montant_ttc(facture.total_ttc)
    du = formater_nombre(Decimal(str(facture.montant_du or 0)), decimales=2)
    return _assembler(facture.reference, _client_nom(facture),
                      f'{montant}, reste dû {du}')


def libelles_ventes(user, *, devis=None, facture=None):
    """``{'devis': …, 'facture': …}`` pour les identifiants donnés qui existent
    dans la société ET la portée de ``user`` (les autres clés manquent). Un
    utilisateur sans société, ou sans le droit de LIRE les ventes
    (``ventes_voir``, la garde des listes devis et factures), ne voit rien."""
    from core.permissions import _user_has_or_legacy

    if (getattr(user, 'company_id', None) is None
            or not _user_has_or_legacy(user, 'ventes_voir')):
        return {}
    out = {}
    if devis:
        trouve = (_devis_visibles(user).filter(pk=devis)
                  .select_related('client', 'company').first())
        if trouve is not None:
            out['devis'] = _libelle_devis(trouve)
    if facture:
        trouve = (_factures_visibles(user).filter(pk=facture)
                  .select_related('client').first())
        if trouve is not None:
            out['facture'] = _libelle_facture(trouve)
    return out
