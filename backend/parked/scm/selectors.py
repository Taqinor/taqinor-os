"""Sélecteurs (lecture seule) de planification supply chain (Groupe NTSCM)."""
from datetime import date
from decimal import Decimal


def parametres(company):
    """NTSCM33 — réglages SCM de ``company`` (délègue au lazy get_or_create
    de ``services.parametres_scm`` : source UNIQUE, jamais deux chemins de
    création du même singleton). Tous les consommateurs (NTSCM5/6/15, tâches
    beat NTSCM21/35/36) lisent leurs seuils/défauts via CETTE fonction plutôt
    qu'une constante codée en dur — avec repli sur les défauts du modèle
    (voir ``models.ParametresSCM``) si la ligne vient d'être créée."""
    from . import services

    return services.parametres_scm(company)


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
            # NTSCM44 — id de la PolitiqueStock elle-même (distinct de
            # `produit_id`) : permet au frontend de lier vers la fiche détail
            # `/scm/politiques-stock/<id>` (réglages + fil d'activité).
            'politique_id': politique.id,
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


# Seuil d'alerte (jamais de blocage) sur l'écart CA prévisionnel vs forecast.
# NTSCM33 — repli historique UNIQUEMENT : `impact_financier_cycle` lit
# désormais `ParametresSCM.seuil_alerte_ecart_financier_pct` (même défaut,
# 15%) via `parametres(company)` ; cette constante ne reste que pour un
# éventuel appelant externe qui l'importait directement.
SEUIL_ALERTE_ECART_CA_PCT = Decimal('15')


def impact_financier_cycle(cycle):
    """NTSCM15 — impact financier (CA prévisionnel) du plan de demande d'un
    cycle S&OP, rapproché du forecast CA existant.

    Valorise ``LigneDemandeSOP.quantite_finale`` (NTSCM13) × ``Produit.
    prix_vente`` — JAMAIS ``prix_achat`` (règle transverse, moteur de devis
    RULE #4 : le prix d'achat n'apparaît jamais dans une sortie chiffrée
    destinée à un tableau de bord de pilotage) — agrégée en CA prévisionnel
    du mois du cycle.

    Compare au forecast CA calculé par :func:`core.forecast.forecast_series`
    (FG361, déjà bâti, réutilisé en LECTURE SEULE) à partir des 12 mois
    d'historique précédents. Aucun sélecteur de forecast CA mensuel n'existe
    encore côté ``apps.ventes``/``apps.reporting`` : l'historique est lu via
    ``apps.ventes.selectors.carnet_commande_par_mois`` (le carnet de
    commandes ENGAGÉ — devis acceptés non encore facturés — le meilleur
    proxy de CA mensuel déjà exposé en lecture seule par ``ventes``, jamais
    un import de son modèle). Signale une ALERTE (jamais un blocage) si
    l'écart dépasse :data:`SEUIL_ALERTE_ECART_CA_PCT`."""
    from calendar import monthrange

    from apps.ventes.selectors import carnet_commande_par_mois
    from core.forecast import forecast_series

    from .models import LigneDemandeSOP

    lignes = LigneDemandeSOP.objects.filter(cycle=cycle).select_related('produit')

    lignes_valorisees = []
    ca_previsionnel = Decimal('0')
    for ligne in lignes:
        prix_vente = ligne.produit.prix_vente or Decimal('0')
        valeur = ligne.quantite_finale * prix_vente
        ca_previsionnel += valeur
        lignes_valorisees.append({
            'produit_id': ligne.produit_id,
            'produit_nom': ligne.produit.nom,
            'quantite_finale': ligne.quantite_finale,
            'prix_vente': prix_vente,
            'valeur_ht': valeur,
        })

    y, m = int(cycle.periode[:4]), int(cycle.periode[5:7])
    idx_cible = y * 12 + (m - 1)
    y0, m0 = divmod(idx_cible - 12, 12)
    debut_hist = date(y0, m0 + 1, 1)
    yf, mf = divmod(idx_cible - 1, 12)
    fin_hist = date(yf, mf + 1, monthrange(yf, mf + 1)[1])

    historique_ca = carnet_commande_par_mois(cycle.company, debut_hist, fin_hist)
    points = [
        {'period': periode, 'value': float(valeur)}
        for periode, valeur in historique_ca.items()
    ]
    resultat_forecast = forecast_series(points, horizon=1)

    ca_forecast = None
    for point in resultat_forecast.forecast:
        if point.period == cycle.periode:
            ca_forecast = Decimal(str(point.value))
            break

    seuil_alerte_pct = parametres(cycle.company).seuil_alerte_ecart_financier_pct

    ecart_pct = None
    alerte_ecart = False
    if ca_forecast:
        ecart_pct = (
            (ca_previsionnel - ca_forecast) / ca_forecast * 100
        ).quantize(Decimal('0.01'))
        alerte_ecart = abs(ecart_pct) > seuil_alerte_pct

    return {
        'cycle_id': cycle.id,
        'periode': cycle.periode,
        'ca_previsionnel_ht': ca_previsionnel,
        'ca_forecast_ht': ca_forecast,
        'ecart_pct': ecart_pct,
        'alerte_ecart': alerte_ecart,
        'seuil_alerte_pct': seuil_alerte_pct,
        'lignes': lignes_valorisees,
    }


def suggerer_transferts_inter_sites(company):
    """NTSCM20 — étend FG326 (transfert min/max STATIQUE, réactif) : croise le
    stock disponible par ``stock.EmplacementStock`` (déjà multi-dépôt, FG62)
    avec la ``PrevisionDemande`` par segment (NTSCM1, quand un segment porte
    une localisation — match texte best-effort sur le nom de l'emplacement)
    pour proposer un transfert d'un dépôt en SURSTOCK PROJETÉ vers un dépôt en
    RUPTURE PROJETÉE, ANTICIPATIVEMENT — avant que FG326 ne déclenche sur un
    seuil déjà franchi.

    Lu en cross-app via ``django.apps.apps.get_model`` (LECTURE SEULE, même
    patron que ``classifier_abc``). Le seuil de comparaison est le
    ``stock.StockEmplacement.seuil_max``/``seuil_min`` PAR (produit,
    emplacement) déjà modélisé (FG62) — pas d'emplacement PRINCIPAL en
    source/cible de surstock (pas de seuil connu pour lui, comportement
    FG62 : « signaler qu'un emplacement NON-principal… »); seuil absent =
    0 par défaut côté déficit (tout stock négatif projeté compte), et AUCUN
    signal de surstock quand aucun ``seuil_max`` n'est configuré.

    Renvoie ``[{'produit_id', 'produit_nom', 'emplacement_source_id',
    'emplacement_source_nom', 'emplacement_destination_id',
    'emplacement_destination_nom', 'quantite_suggeree'}, ...]``."""
    from django.apps import apps as django_apps
    from django.utils import timezone

    from .models import PrevisionDemande

    EmplacementStock = django_apps.get_model('stock', 'EmplacementStock')
    StockEmplacement = django_apps.get_model('stock', 'StockEmplacement')
    Produit = django_apps.get_model('stock', 'Produit')

    emplacements = list(
        EmplacementStock.objects.filter(company=company, archived=False))
    secondaires = [e for e in emplacements if not e.is_principal]
    if len(secondaires) < 2:
        return []

    ventilation = {
        (se.produit_id, se.emplacement_id): se
        for se in StockEmplacement.objects.filter(company=company)
    }

    periode_min = timezone.localdate().strftime('%Y-%m')
    previsions_par_produit = {}
    for prevision in PrevisionDemande.objects.filter(
            company=company, periode__gte=periode_min).exclude(segment=''):
        previsions_par_produit.setdefault(prevision.produit_id, []).append(prevision)

    suggestions = []
    for produit in Produit.objects.filter(company=company, is_archived=False):
        previsions = previsions_par_produit.get(produit.id, [])
        if not previsions:
            continue

        projections = {}
        for emplacement in secondaires:
            se = ventilation.get((produit.id, emplacement.id))
            quantite = se.quantite if se else 0
            demande = sum(
                float(p.quantite_prevue) for p in previsions
                if emplacement.nom.lower() in (p.segment or '').lower())
            seuil_max = se.seuil_max if se and se.seuil_max is not None else None
            seuil_min = se.seuil_min if se and se.seuil_min is not None else 0
            projection = quantite - demande
            surplus = (projection - seuil_max) if seuil_max is not None and projection > seuil_max else 0
            deficit = (projection - seuil_min) if projection < seuil_min else 0
            projections[emplacement.id] = {'surplus': surplus, 'deficit': deficit}

        sources = sorted(
            [(eid, p['surplus']) for eid, p in projections.items() if p['surplus'] > 0],
            key=lambda item: -item[1])
        cibles = sorted(
            [(eid, p['deficit']) for eid, p in projections.items() if p['deficit'] < 0],
            key=lambda item: item[1])

        emap = {e.id: e for e in secondaires}
        for source_id, surplus_restant in sources:
            for cible_id, deficit in cibles:
                if source_id == cible_id or surplus_restant <= 0:
                    continue
                besoin = -deficit
                quantite_suggeree = min(surplus_restant, besoin)
                if quantite_suggeree <= 0:
                    continue
                suggestions.append({
                    'produit_id': produit.id,
                    'produit_nom': produit.nom,
                    'emplacement_source_id': source_id,
                    'emplacement_source_nom': emap[source_id].nom,
                    'emplacement_destination_id': cible_id,
                    'emplacement_destination_nom': emap[cible_id].nom,
                    'quantite_suggeree': round(quantite_suggeree, 2),
                })
                surplus_restant -= quantite_suggeree

    return suggestions


def precision_prevision(company, produit=None, fenetre_mois=6):
    """NTSCM24 — précision de prévision auto-mesurée (MAPE, Mean Absolute
    Percentage Error) : compare rétrospectivement ``PrevisionDemande.
    quantite_prevue`` du mois M à la consommation RÉELLE observée du mois M
    (une fois le mois ÉCOULÉ — le mois courant est exclu), sur les
    ``fenetre_mois`` derniers mois. Mêmes sources cross-app en LECTURE SEULE
    que ``classifier_abc``/``_historique_sorties_mensuelles``.

    Les mois SANS consommation réelle (réel=0) sont exclus (division par
    zéro non définie pour un MAPE). Plusieurs ``segment`` pour le même
    (produit, mois) sont SOMMÉS (même convention que
    ``services.geler_previsions_cycle``).

    Renvoie ``{'mape_global_pct', 'nb_mois_couverts', 'par_produit': [
    {'produit_id', 'produit_nom', 'mape_pct', 'nb_mois'}, ...]}`` (``None``
    quand aucun mois n'est exploitable)."""
    from django.apps import apps as django_apps
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    from .models import PrevisionDemande

    MouvementStock = django_apps.get_model('stock', 'MouvementStock')
    Produit = django_apps.get_model('stock', 'Produit')

    today = timezone.localdate()
    idx_debut = today.year * 12 + (today.month - 1) - max(0, int(fenetre_mois))
    y0, m0 = divmod(idx_debut, 12)
    debut = date(y0, m0 + 1, 1)
    fin_exclusive = date(today.year, today.month, 1)

    qs_previsions = PrevisionDemande.objects.filter(
        company=company, periode__gte=f'{y0:04d}-{m0 + 1:02d}')
    if produit is not None:
        qs_previsions = qs_previsions.filter(produit=produit)

    previsions = {}
    for p in qs_previsions:
        cle = (p.produit_id, p.periode)
        previsions[cle] = previsions.get(cle, Decimal('0')) + p.quantite_prevue

    qs_reel = MouvementStock.objects.filter(
        company=company, type_mouvement=MouvementStock.TypeMouvement.SORTIE,
        date__date__gte=debut, date__date__lt=fin_exclusive)
    if produit is not None:
        qs_reel = qs_reel.filter(produit_id=produit.id)
    qs_reel = (
        qs_reel.annotate(mois=TruncMonth('date')).values('produit_id', 'mois')
        .annotate(total=Sum('quantite')))

    noms_produits = {}
    if produit is not None:
        noms_produits[produit.id] = produit.nom
    else:
        noms_produits = dict(
            Produit.objects.filter(company=company).values_list('id', 'nom'))

    erreurs_par_produit = {}
    toutes_erreurs = []
    for row in qs_reel:
        periode = f'{row["mois"].year:04d}-{row["mois"].month:02d}'
        quantite_reelle = float(row['total'] or 0)
        if quantite_reelle <= 0:
            continue
        quantite_prevue = float(previsions.get((row['produit_id'], periode), Decimal('0')))
        erreur_pct = abs(quantite_reelle - quantite_prevue) / quantite_reelle * 100
        erreurs_par_produit.setdefault(row['produit_id'], []).append(erreur_pct)
        toutes_erreurs.append(erreur_pct)

    lignes = [
        {
            'produit_id': pid,
            'produit_nom': noms_produits.get(pid, ''),
            'mape_pct': round(sum(erreurs) / len(erreurs), 2),
            'nb_mois': len(erreurs),
        }
        for pid, erreurs in erreurs_par_produit.items()
    ]
    lignes.sort(key=lambda r: -r['nb_mois'])

    return {
        'mape_global_pct': (
            round(sum(toutes_erreurs) / len(toutes_erreurs), 2)
            if toutes_erreurs else None),
        'nb_mois_couverts': len(toutes_erreurs),
        'par_produit': lignes,
    }


def ecarts_prevision(company, *, fenetre_mois=6, produit=None):
    """NTSCM32 — écarts de prévision par produit sur la fenêtre demandée :
    quantité prévue totale, quantité réelle totale, écart absolu
    (réel − prévu) et écart % (écart absolu / réel × 100), pour l'export
    « Écarts de prévision » (bouton sur ``/scm/reappro``).

    Mêmes sources cross-app en LECTURE SEULE que :func:`precision_prevision`
    (NTSCM24, réutilisé au sens de la même fenêtre de mois ÉCOULÉS, mois
    courant exclu) — mais agrège les quantités BRUTES (prévu/réel) plutôt que
    des erreurs mensuelles moyennées (MAPE), ce que le rapport d'écarts a
    besoin d'afficher tel quel.

    Renvoie ``[{'produit_id', 'produit_nom', 'quantite_prevue_totale',
    'quantite_reelle_totale', 'ecart_absolu', 'ecart_pct'}, ...]`` trié par
    écart absolu décroissant (en valeur absolue) — les plus gros écarts
    d'abord."""
    from django.apps import apps as django_apps
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    from .models import PrevisionDemande

    MouvementStock = django_apps.get_model('stock', 'MouvementStock')
    Produit = django_apps.get_model('stock', 'Produit')

    today = timezone.localdate()
    idx_debut = today.year * 12 + (today.month - 1) - max(0, int(fenetre_mois))
    y0, m0 = divmod(idx_debut, 12)
    debut = date(y0, m0 + 1, 1)
    fin_exclusive = date(today.year, today.month, 1)

    qs_previsions = PrevisionDemande.objects.filter(
        company=company, periode__gte=f'{y0:04d}-{m0 + 1:02d}')
    if produit is not None:
        qs_previsions = qs_previsions.filter(produit=produit)

    prevu_par_produit = {}
    for p in qs_previsions:
        prevu_par_produit[p.produit_id] = (
            prevu_par_produit.get(p.produit_id, Decimal('0')) + p.quantite_prevue)

    qs_reel = MouvementStock.objects.filter(
        company=company, type_mouvement=MouvementStock.TypeMouvement.SORTIE,
        date__date__gte=debut, date__date__lt=fin_exclusive)
    if produit is not None:
        qs_reel = qs_reel.filter(produit_id=produit.id)
    qs_reel = (
        qs_reel.annotate(mois=TruncMonth('date')).values('produit_id')
        .annotate(total=Sum('quantite')))
    reel_par_produit = {
        row['produit_id']: Decimal(str(row['total'] or 0)) for row in qs_reel}

    noms_produits = {}
    if produit is not None:
        noms_produits[produit.id] = produit.nom
    else:
        noms_produits = dict(
            Produit.objects.filter(company=company).values_list('id', 'nom'))

    produit_ids = set(prevu_par_produit) | set(reel_par_produit)
    lignes = []
    for pid in produit_ids:
        prevu = prevu_par_produit.get(pid, Decimal('0'))
        reel = reel_par_produit.get(pid, Decimal('0'))
        ecart_absolu = reel - prevu
        ecart_pct = (
            (ecart_absolu / reel * 100).quantize(Decimal('0.01'))
            if reel else None)
        lignes.append({
            'produit_id': pid,
            'produit_nom': noms_produits.get(pid, ''),
            'quantite_prevue_totale': prevu,
            'quantite_reelle_totale': reel,
            'ecart_absolu': ecart_absolu,
            'ecart_pct': ecart_pct,
        })

    lignes.sort(key=lambda r: abs(r['ecart_absolu']), reverse=True)
    return lignes


def tableau_bord_executif(company):
    """NTSCM28 — tableau de bord SCM exécutif (LECTURE SEULE, agrège
    NTSCM7/24 + FG59, AUCUN nouveau modèle) : 4 KPI de synthèse.

      * ``taux_service_pct`` — % de SKU sous politique de stock (NTSCM6) qui
        ne sont PAS en rupture/à commander, sur le statut COURANT du tableau
        de bord réappro (NTSCM7 — un historique glissant 90j strict
        exigerait un nouveau modèle de snapshot quotidien, hors périmètre) ;
      * ``otif_pondere_pct`` — ADAPTATION DE PÉRIMÈTRE : le vrai OTIF
        promis-vs-livré (NTSCM8) n'est pas encore bâti (hors cette lane, déjà
        `[ ]` sur `docs/plans/PLAN_SUPPLY.md`). En attendant, moyenne du
        taux de remplissage FG59 (``apps.stock.services.
        supplier_performance``) de chaque fournisseur actif, PONDÉRÉE par sa
        dépense totale — même nom de champ, remplacé AUTOMATIQUEMENT par le
        vrai OTIF le jour où NTSCM8 atterrit ;
      * ``mape_global_pct`` — précision de prévision globale (NTSCM24) ;
      * ``valeur_stock_par_classe_abc`` — ``quantite_stock × prix_vente``
        (JAMAIS ``prix_achat`` — règle #4), regroupée par classe ABC
        (NTSCM4).

    Renvoie un dict plat, AUCUN champ n'expose de prix d'achat/marge."""
    from django.apps import apps as django_apps

    from apps.stock.services import supplier_performance

    from .models import ClassificationABC

    Fournisseur = django_apps.get_model('stock', 'Fournisseur')

    lignes_reappro = tableau_bord_reappro(company)
    taux_service_pct = (
        round(
            sum(1 for ligne in lignes_reappro if ligne['statut'] == 'ok')
            / len(lignes_reappro) * 100, 2)
        if lignes_reappro else None)

    total_depense = Decimal('0')
    somme_ponderee = Decimal('0')
    for fournisseur in Fournisseur.objects.filter(company=company):
        perf = supplier_performance(company, fournisseur)
        depense = Decimal(str(perf.get('total_achats_ht') or '0'))
        taux = perf.get('fill_rate_pct')
        if depense <= 0 or taux is None:
            continue
        total_depense += depense
        somme_ponderee += depense * Decimal(str(taux))
    otif_pondere_pct = (
        float((somme_ponderee / total_depense).quantize(Decimal('0.01')))
        if total_depense > 0 else None)

    mape_global_pct = precision_prevision(company)['mape_global_pct']

    valeur_par_classe = {'A': Decimal('0'), 'B': Decimal('0'), 'C': Decimal('0')}
    for classement in (
            ClassificationABC.objects.filter(company=company)
            .select_related('produit')):
        produit = classement.produit
        valeur_par_classe[classement.classe] = (
            valeur_par_classe.get(classement.classe, Decimal('0'))
            + Decimal(str(produit.quantite_stock or 0)) * (produit.prix_vente or Decimal('0')))

    return {
        'taux_service_pct': taux_service_pct,
        'otif_pondere_pct': otif_pondere_pct,
        'mape_global_pct': mape_global_pct,
        'valeur_stock_par_classe_abc': {
            classe: str(valeur.quantize(Decimal('0.01')))
            for classe, valeur in valeur_par_classe.items()
        },
    }
