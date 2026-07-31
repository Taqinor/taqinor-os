"""Selectors du module Marketing (``apps.marketing``).

Point d'entrée des LECTURES cross-app du domaine marketing (CLAUDE.md : les
autres apps lisent marketing via ``apps.marketing.selectors`` ou par string-FK,
jamais via ``apps.marketing.models``).

À la sortie de compta (ODX9/ODX10), AUCUNE autre app ne lit les modèles
marketing (aucune string-FK ``marketing.*`` hors marketing, vérifié) : ce
module est donc volontairement vide pour l'instant. Ajouter ici une fonction
de lecture fine dès qu'une autre app en aura besoin — jamais un import direct
de ``apps.marketing.models`` depuis l'extérieur.

WIR96 — première lecture cross-app réelle : ``apps.ventes`` affiche sur la
fiche devis le suivi d'ouverture du lien de partage (``OuverturePartage``) et
la liste des relances de devis abandonné (``RelanceDevisAbandonne``). Les deux
fonctions ci-dessous sont ce point d'entrée ; ``ventes`` n'importe JAMAIS
``apps.marketing.models``.
"""


def ouverture_partage_pour_token(company, token):
    """WIR96 — suivi d'ouverture d'un lien de partage, borné société.

    Renvoie ``{'nb_ouvertures', 'premier_vu_le', 'dernier_vu_le', 'cible',
    'cible_reference'}`` ou ``None`` si le lien n'a jamais été ouvert.
    Lecture seule."""
    if not company or not token:
        return None
    from .models import OuverturePartage

    obj = (OuverturePartage.objects
           .filter(company=company, token=token)
           .first())
    if obj is None:
        return None
    return {
        'nb_ouvertures': obj.nb_ouvertures,
        'premier_vu_le': obj.premier_vu_le,
        'dernier_vu_le': obj.dernier_vu_le,
        'cible': obj.cible,
        'cible_reference': obj.cible_reference,
    }


def relances_devis_abandonne(company, devis_id):
    """WIR96 — relances consignées pour un devis (référence opaque
    ``devis_id``, jamais une FK vers ``ventes``), bornées société et triées de
    la plus récente à la plus ancienne. Lecture seule."""
    if not company or not devis_id:
        return []
    from .models import RelanceDevisAbandonne

    qs = (RelanceDevisAbandonne.objects
          .filter(company=company, devis_id=devis_id)
          .order_by('-date_relance', '-id'))
    return [
        {
            'id': r.id,
            'date_relance': r.date_relance,
            'jours_sans_reponse': r.jours_sans_reponse,
            'canal': r.canal,
            'note': r.note,
            'devis_reference': r.devis_reference,
        }
        for r in qs
    ]
