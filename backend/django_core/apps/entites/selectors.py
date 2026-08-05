"""Lectures de `apps.entites` — jamais d'écriture ici (cf. services.py)."""
from .models import Entite


def get_company_entite(company, entite_id):
    """Renvoie l'`Entite` `entite_id` bornée à `company`, ou None."""
    try:
        return Entite.objects.get(company=company, pk=entite_id)
    except (Entite.DoesNotExist, ValueError, TypeError):
        return None


def entite_tree(company):
    """NTADM1 — arbre des entités de `company` (`?tree=1`), racines d'abord.

    Renvoie une liste imbriquée de dicts {id, code, nom, actif, enfants:[...]}.
    """
    entites = list(Entite.objects.filter(company=company).order_by('nom'))
    by_parent = {}
    for e in entites:
        by_parent.setdefault(e.parent_id, []).append(e)

    def _node(e):
        return {
            'id': e.id,
            'code': e.code,
            'nom': e.nom,
            'actif': e.actif,
            'enfants': [_node(c) for c in by_parent.get(e.id, [])],
        }

    return [_node(e) for e in by_parent.get(None, [])]


def entites_actives_count(company):
    return Entite.objects.filter(company=company, actif=True).count()


def entites_accessibles(user, company):
    """NTADM26 — entités ACTIVES accessibles à ``user``, pour la bascule de
    l'en-tête (id/code/nom seulement).

    Un rôle SANS périmètre (tous les comptes existants) reçoit toutes les
    entités actives ; un rôle restreint (NTADM3) ne reçoit que les siennes.
    La liste sert à décider si la bascule s'affiche (≥ 2) et à la remplir —
    elle n'accorde aucun droit : le serveur reste seul juge à chaque requête.
    """
    from core.entite_scoping import entites_visibles_ids

    qs = Entite.objects.filter(company=company, actif=True).order_by('code')
    ids = entites_visibles_ids(user)
    if ids is not None:
        qs = qs.filter(id__in=ids)
    return [{'id': e.id, 'code': e.code, 'nom': e.nom} for e in qs]


def _montant(valeur):
    """Montant rendu en CHAÎNE à 2 décimales (jamais un float : pas de dérive
    de virgule flottante sur de l'argent)."""
    from decimal import Decimal
    return str(Decimal(str(valeur or 0)).quantize(Decimal('0.01')))


def consolidation_groupe(company):
    """NTADM25 — vue consolidée « Groupe », LECTURE SEULE.

    Une colonne de KPI par entité ACTIVE + une colonne Total. AUCUN calcul
    nouveau : chaque chiffre vient du sélecteur de l'app propriétaire, filtré
    sur le champ ``entite`` posé par NTADM2 —
    ``ventes.selectors.ca_par_entite`` (CA),
    ``crm.selectors.pipeline_pondere_par_entite`` (pipeline pondéré),
    ``stock.selectors.nb_produits_par_entite`` (catalogue). Ce n'est PAS une
    consolidation comptable (aucune élimination intragroupe).

    ``disponible`` vaut False tant que la société compte moins de DEUX entités
    actives : l'écran ne s'affiche qu'à partir d'un vrai groupe.

    L'EFFECTIF n'est pas ventilable par entité aujourd'hui (NTADM2 ne couvre
    pas ``rh.DossierEmploye``) : il n'est donné qu'au Total, à partir des
    comptes actifs de la société — ``effectif`` reste ``None`` par entité
    plutôt qu'un zéro qui mentirait.
    """
    from decimal import Decimal

    from apps.crm.selectors import pipeline_pondere_par_entite
    from apps.stock.selectors import nb_produits_par_entite
    from apps.ventes.selectors import ca_par_entite

    entites = list(
        Entite.objects.filter(company=company, actif=True).order_by('code'))
    ids = [e.id for e in entites]

    ca = ca_par_entite(company, ids)
    pipeline = pipeline_pondere_par_entite(company, ids)
    produits = nb_produits_par_entite(company, ids)

    colonnes = []
    total = {
        'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
        'ca': Decimal('0'), 'pipeline': Decimal('0'),
        'nb_devis': 0, 'nb_factures': 0, 'nb_leads': 0, 'nb_produits': 0,
    }
    for entite in entites:
        chiffres = ca.get(entite.id) or {}
        ca_devis = chiffres.get('ca_devis') or Decimal('0')
        ca_factures = chiffres.get('ca_factures') or Decimal('0')
        pipe = (pipeline.get(entite.id) or {})
        montant_pipeline = pipe.get('pipeline') or Decimal('0')
        nb_leads = pipe.get('nb_leads') or 0
        nb_produits = produits.get(entite.id) or 0

        total['ca_devis'] += ca_devis
        total['ca_factures'] += ca_factures
        total['ca'] += ca_devis + ca_factures
        total['pipeline'] += montant_pipeline
        total['nb_devis'] += chiffres.get('nb_devis') or 0
        total['nb_factures'] += chiffres.get('nb_factures') or 0
        total['nb_leads'] += nb_leads
        total['nb_produits'] += nb_produits

        colonnes.append({
            'id': entite.id,
            'code': entite.code,
            'nom': entite.nom,
            'ca_devis': _montant(ca_devis),
            'ca_factures': _montant(ca_factures),
            'ca': _montant(ca_devis + ca_factures),
            'pipeline': _montant(montant_pipeline),
            'nb_devis': chiffres.get('nb_devis') or 0,
            'nb_factures': chiffres.get('nb_factures') or 0,
            'nb_leads': nb_leads,
            'nb_produits': nb_produits,
            'effectif': None,
        })

    from authentication.models import CustomUser
    effectif = CustomUser.objects.filter(
        company=company, is_active=True).count()

    return {
        'disponible': len(entites) >= 2,
        'entites': colonnes,
        'total': {
            'code': 'TOTAL',
            'nom': 'Total groupe',
            'ca_devis': _montant(total['ca_devis']),
            'ca_factures': _montant(total['ca_factures']),
            'ca': _montant(total['ca']),
            'pipeline': _montant(total['pipeline']),
            'nb_devis': total['nb_devis'],
            'nb_factures': total['nb_factures'],
            'nb_leads': total['nb_leads'],
            'nb_produits': total['nb_produits'],
            'effectif': effectif,
        },
        'effectif_note': (
            "L'effectif n'est pas encore ventilé par entité : le total donne "
            "les comptes actifs de la société."
        ),
    }


def entites_pour_journal(company):
    """NTADM27 — entités d'une société ordonnées par date de création (pour le
    journal d'administration imprimable). Lecture publique via selector pour
    éviter un import direct de `entites.models` par une autre app."""
    return list(Entite.objects.filter(company=company).order_by('created_at'))
