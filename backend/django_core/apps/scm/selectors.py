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


def tableau_bord_reappro(company, *, statut=None, classe_abc=None, fournisseur_id=None):
    """NTSCM7 — tableau de bord réappro consolidé (remplace/étend FG364 brut).

    Pour chaque produit avec ``PolitiqueStock`` (NTSCM6), combine :

      * le stock actuel (``stock.Produit.quantite_stock``, champ canonique) ;
      * :func:`core.stock_reorder.predict_reorder` (FG364, déjà bâti) —
        date de rupture prévue + quantité suggérée ;
      * la politique de stock (NTSCM6) — ROP, stock de sécurité effectif ;
      * le fournisseur le moins cher
        (``apps.stock.services.cheapest_prix_fournisseur``, déjà bâti).

    Statut par ligne : ``'ok'`` (pas de réappro nécessaire), ``'a_commander'``
    (``reorder_now`` mais la rupture n'arrive pas avant qu'une commande
    lancée aujourd'hui ne livre), ``'rupture_imminente'`` (la rupture
    surviendrait AVANT la livraison d'une commande lancée aujourd'hui —
    ``jours_avant_rupture <= délai_fournisseur``).

    LECTURE SEULE — ne réutilise QUE des primitives déjà exposées par
    ``apps.stock`` (``services.cheapest_prix_fournisseur``,
    ``apps.scm.services.lead_time_moyen_fournisseur`` qui s'appuie lui-même
    sur ``apps.stock.services.supplier_performance``) ; jamais un import de
    modèle ``apps.stock``."""
    from django.utils import timezone

    from apps.stock.services import cheapest_prix_fournisseur
    from core.stock_reorder import predict_reorder

    from . import services
    from .models import PolitiqueStock

    qs = PolitiqueStock.objects.filter(company=company).select_related('produit')
    if classe_abc:
        qs = qs.filter(classe_abc=classe_abc)

    today = timezone.localdate()
    lignes = []
    for politique in qs:
        produit = politique.produit
        lead_time = services.lead_time_moyen_fournisseur(company, produit)
        calc = services.appliquer_politique_stock(
            produit, politique.service_level_pct, company, lead_time_days=lead_time)
        stock_securite_effectif = float(
            politique.stock_securite_manuel
            if politique.stock_securite_manuel is not None
            else politique.stock_securite_calcule
        )

        resultat = predict_reorder(
            current_stock=produit.quantite_stock, today=today,
            avg_daily_consumption=calc['avg_daily_consumption'],
            lead_time_days=lead_time, safety_stock=stock_securite_effectif,
        )

        if not resultat.reorder_now:
            ligne_statut = 'ok'
        elif (resultat.days_until_rupture is not None
                and resultat.days_until_rupture <= lead_time):
            ligne_statut = 'rupture_imminente'
        else:
            ligne_statut = 'a_commander'

        if statut and ligne_statut != statut:
            continue

        cheapest = cheapest_prix_fournisseur(produit)
        fid = cheapest.fournisseur_id if cheapest else produit.fournisseur_id
        if fournisseur_id and str(fid) != str(fournisseur_id):
            continue

        lignes.append({
            'produit_id': produit.id,
            'produit_nom': produit.nom,
            'classe_abc': politique.classe_abc,
            'stock_actuel': produit.quantite_stock,
            'point_commande': politique.point_commande,
            'quantite_suggeree': resultat.suggested_quantity,
            'statut': ligne_statut,
            'rupture_date': (
                resultat.rupture_date.isoformat() if resultat.rupture_date else None),
            'fournisseur_id': fid,
            'fournisseur_nom': cheapest.fournisseur.nom if cheapest else None,
            'prix_achat_unitaire': str(cheapest.prix_achat) if cheapest else None,
        })

    return lignes
