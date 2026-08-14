"""Sélecteurs (lecture seule) de planification supply chain (Groupe NTSCM)."""
from datetime import date
from decimal import Decimal


def classifier_abc(company, fenetre_mois=12, *, persist=True):
    """NTSCM4 — classification ABC (Pareto) des produits par valeur de
    sortie cumulée (``quantité × prix_vente`` HT, JAMAIS ``prix_achat``) sur
    ``fenetre_mois`` mois glissants.

    A = top 80% de la valeur cumulée, B = 80-95%, C = le reste (ou tout
    produit sans valeur de sortie sur la fenêtre).

    Lecture cross-app EN LECTURE SEULE de ``stock.Produit``/
    ``stock.MouvementStock`` via ``django.apps.apps.get_model`` — jamais un
    ``from apps.stock.models import ...`` statique, jamais une écriture dans
    ``apps.stock`` (même patron que
    ``apps.scm.services._historique_sorties_mensuelles``, précédent
    FG294/FG295).

    ADAPTATION DE PÉRIMÈTRE — voir la docstring de ``models.ClassificationABC`` :
    le résultat est persisté (si ``persist=True``, défaut) dans
    ``scm.ClassificationABC`` plutôt que sur ``stock.Produit.classe_abc``, et
    le filtre bonus ``stock/produits/?classe_abc=`` du plan d'origine n'est
    pas ajouté (nécessiterait aussi une écriture dans ``apps.stock``).

    Renvoie une liste de dicts triés par valeur décroissante :
    ``[{'produit', 'rang', 'classe', 'valeur_cumulee_ht', 'part_pct',
    'part_cumulee_pct'}, ...]`` — une entrée PAR produit actif de la société,
    la somme des classes couvre donc 100% des produits."""
    from django.apps import apps as django_apps
    from django.db.models import Sum
    from django.utils import timezone

    Produit = django_apps.get_model('stock', 'Produit')
    MouvementStock = django_apps.get_model('stock', 'MouvementStock')

    today = timezone.localdate()
    idx = today.year * 12 + (today.month - 1) - max(0, int(fenetre_mois))
    y0, m0 = divmod(idx, 12)
    debut = date(y0, m0 + 1, 1)

    sorties = (
        MouvementStock.objects
        .filter(
            company=company, type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            date__date__gte=debut)
        .values('produit_id')
        .annotate(total_qte=Sum('quantite'))
    )
    qte_par_produit = {row['produit_id']: row['total_qte'] or 0 for row in sorties}

    produits = list(Produit.objects.filter(company=company, is_archived=False))
    lignes = []
    for p in produits:
        qte = qte_par_produit.get(p.id, 0)
        valeur = Decimal(str(qte)) * (p.prix_vente or Decimal('0'))
        lignes.append({'produit': p, 'valeur': valeur})

    lignes.sort(key=lambda r: r['valeur'], reverse=True)
    total_valeur = sum((r['valeur'] for r in lignes), Decimal('0'))

    resultat = []
    cumul = Decimal('0')
    for rang, ligne in enumerate(lignes, start=1):
        cumul += ligne['valeur']
        if total_valeur <= 0:
            classe = 'C'
            part_cumulee = Decimal('0')
            part_individuelle = Decimal('0')
        else:
            part_cumulee = (cumul / total_valeur * 100)
            part_individuelle = (ligne['valeur'] / total_valeur * 100)
            if part_cumulee <= 80:
                classe = 'A'
            elif part_cumulee <= 95:
                classe = 'B'
            else:
                classe = 'C'
        resultat.append({
            'produit': ligne['produit'],
            'rang': rang,
            'classe': classe,
            'valeur_cumulee_ht': ligne['valeur'],
            'part_pct': part_individuelle.quantize(Decimal('0.01')),
            'part_cumulee_pct': part_cumulee.quantize(Decimal('0.01')),
        })

    if persist:
        from .models import ClassificationABC
        for row in resultat:
            ClassificationABC.objects.update_or_create(
                company=company, produit=row['produit'],
                defaults={
                    'classe': row['classe'],
                    'valeur_cumulee_ht': row['valeur_cumulee_ht'],
                    'part_valeur_pct': row['part_pct'],
                    'rang': row['rang'],
                    'fenetre_mois': fenetre_mois,
                },
            )

    return resultat
