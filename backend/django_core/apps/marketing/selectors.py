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


def heatmap_engagement(company, *, jours=180, maintenant=None):
    """NTMKT24 — taux d'ouverture historique par JOUR DE SEMAINE × HEURE
    D'ENVOI, pour suggérer le meilleur moment d'envoi.

    LECTURE SEULE, purement informative : elle ne bloque jamais un envoi
    planifié. Source = ``EnvoiCampagne`` (XMKT2) réellement envoyés sur la
    fenêtre (``envoye_le`` non nul), heure LOCALE. Une société sans historique
    renvoie une grille vide et ``meilleur=None`` (état vide propre côté écran).
    """
    from django.utils import timezone
    from .models import EnvoiCampagne

    if not company:
        return {'cellules': [], 'meilleur': None, 'total_envois': 0}
    maintenant = maintenant or timezone.now()
    depuis = maintenant - timezone.timedelta(days=max(int(jours or 0), 1))
    lignes = (EnvoiCampagne.objects
              .filter(company=company, envoye_le__isnull=False,
                      envoye_le__gte=depuis)
              .values_list('envoye_le', 'ouvert_le'))

    grille = {}
    total = 0
    for envoye_le, ouvert_le in lignes:
        local = timezone.localtime(envoye_le)
        cle = (local.weekday(), local.hour)
        case = grille.setdefault(cle, {'envois': 0, 'ouvertures': 0})
        case['envois'] += 1
        total += 1
        if ouvert_le is not None:
            case['ouvertures'] += 1

    cellules = []
    for (jour, heure), case in sorted(grille.items()):
        taux = (case['ouvertures'] / case['envois']) if case['envois'] else 0.0
        cellules.append({
            'jour': jour,
            'heure': heure,
            'envois': case['envois'],
            'ouvertures': case['ouvertures'],
            'taux_ouverture': round(taux, 4),
        })
    # « Meilleur créneau » : jamais un créneau à 1 envoi (bruit) tant qu'une
    # case plus fournie existe — on trie par taux puis par volume.
    meilleur = None
    if cellules:
        meilleur = sorted(
            cellules,
            key=lambda c: (c['taux_ouverture'], c['envois']),
            reverse=True)[0]
    return {'cellules': cellules, 'meilleur': meilleur, 'total_envois': total}


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


# ── NTMKT18 — Score de maturité, lu par ``apps.crm`` (jamais l'inverse) ────

def maturite_active_pour_mql(company):
    """NTMKT18 — le seuil MQL (XMKT21, ``apps.crm.services.maybe_assign_mql``)
    doit-il se déclencher AUSSI sur le score de maturité (en plus du score de
    qualité QJ6, jamais modifié) ? Défaut ``False`` = comportement XMKT21
    actuel strictement inchangé."""
    if not company:
        return False
    from . import services as marketing_services
    parametres = marketing_services.parametres_marketing_pour(company)
    return bool(parametres.mql_sur_score_maturite)


def score_maturite_valeur(company, lead_id):
    """NTMKT18 — valeur courante (0-100) du score de maturité d'un lead pour
    un appelant cross-app (``crm``), sans exposer le modèle. Recalcule
    (jamais une valeur périmée) ; ``0`` si le module est désactivé pour la
    société (comportement par défaut, jamais bloquant)."""
    if not company or not lead_id:
        return 0
    from . import services as marketing_services
    score = marketing_services.recalculer_score_maturite(company, lead_id)
    return score.valeur if score is not None else 0
