"""Sélecteurs (lecture) de l'app `apps.transport`.

Destiné à être importé PAR D'AUTRES APPS (ex. `apps.stock` pour le landed
cost FG316/DC38) en LOCAL/FONCTION — jamais au niveau module. Toute lecture
d'un modèle d'une autre app (`installations.Transporteur`…) passe par le
`selectors.py` de cette app cible ou, faute de sélecteur dédié, par
`django.apps.apps.get_model(...)` en LECTURE SEULE (jamais un
`from apps.X.models import ...` statique) — même patron que FG294
`installations.selectors.budget_projet_synthese`.
"""
from decimal import Decimal


def _ordre_scoped(ordre_transport_id, company=None):
    """`OrdreTransport` scopé société par id, ou `None`. Lecture seule."""
    from .models import OrdreTransport

    qs = OrdreTransport.objects.all()
    if company is not None:
        qs = qs.filter(company=company)
    return qs.filter(pk=ordre_transport_id).first()


def comparer_transporteurs(ordre_transport_id, company=None):
    """NTLOG7 — comparateur de coûts d'affrètement : pour l'ordre donné,
    renvoie chaque `installations.Transporteur` actif (`active=True`) trié
    par prix croissant.

    Lu via `django.apps.apps.get_model('installations', 'Transporteur')`
    (LECTURE SEULE, jamais un import de modèle) — `installations` n'expose
    pas encore de sélecteur dédié pour cette lecture transverse. Le prix
    affiché est `tarif_base` (le tarif de référence du transporteur) :
    NTLOG6 (`GrilleTarifaireTransporteur`, hors périmètre de cette lane)
    apportera un tarif au poids/zone plus précis — à brancher ICI en
    remplacement de `tarif_base` dès qu'il existera, sans changer la forme
    du retour. Le champ `zone` n'existe pas encore sur `Transporteur` : la
    liste renvoyée n'est donc PAS filtrée par zone de destination (limite
    documentée, pas un blocage — le critère d'acceptation ne demande qu'un
    prix trié)."""
    ordre = _ordre_scoped(ordre_transport_id, company=company)
    if ordre is None:
        return []

    from django.apps import apps as django_apps

    Transporteur = django_apps.get_model('installations', 'Transporteur')
    qs = Transporteur.objects.filter(
        company=ordre.company, active=True).order_by('tarif_base', 'nom')
    return [
        {
            'transporteur_id': t.id,
            'nom': t.nom,
            'type_transporteur': t.type_transporteur,
            'tarif_base': t.tarif_base,
            'prix_applicable': t.tarif_base,
            'contact': t.contact,
            'telephone': t.telephone,
        }
        for t in qs
    ]


def transporteur_nom_pour_ordre(ordre):
    """NTLOG19 — nom du transporteur affrété (`installations.Transporteur`)
    d'un ordre, ou `''` si non affrété/inconnu. Lecture seule, jamais un
    import de modèle."""
    if not ordre.installations_transporteur_id:
        return ''
    from django.apps import apps as django_apps

    Transporteur = django_apps.get_model('installations', 'Transporteur')
    transporteur = Transporteur.objects.filter(
        id=ordre.installations_transporteur_id, company=ordre.company).first()
    return transporteur.nom if transporteur else ''


def frais_transport_pour_landed_cost(company, bon_commande_fournisseur_id):
    """NTLOG16 — somme des `CoutFretReel.montant_ht` d'un
    `stock.BonCommandeFournisseur` donné, scopée société (jamais un import
    de modèle `stock`). Point de lecture UNIQUE que le landed cost
    FG316/DC38 (`apps.stock.services`) pourra consommer — pas de calcul
    dupliqué."""
    from django.db.models import Sum

    from .models import CoutFretReel

    total = CoutFretReel.objects.filter(
        company=company,
        stock_boncommandefournisseur_id=bon_commande_fournisseur_id,
    ).aggregate(total=Sum('montant_ht'))['total']
    return total or Decimal('0')


def estimer_co2_transport(ordre_transport_id, company=None):
    """NTLOG20 — estimation INDICATIVE des émissions CO2 d'un ordre :
    poids total (tonnes) × distance (km) × facteur d'émission éditable
    (`FacteurEmissionCO2`, par mode route/mer/air). Toujours recalculée en
    LECTURE DIRECTE (aucun cache) : éditer le facteur en Paramètres se
    répercute immédiatement sur le prochain appel."""
    from django.db.models import Sum

    from .models import FacteurEmissionCO2

    ordre = _ordre_scoped(ordre_transport_id, company=company)
    if ordre is None:
        return None

    libelle = 'Estimation indicative — facteurs génériques, non certifiée.'
    poids_total_kg = ordre.lignes.aggregate(
        total=Sum('poids_kg'))['total'] or Decimal('0')
    poids_tonnes = Decimal(poids_total_kg) / Decimal('1000')

    base = {
        'ordre_transport_id': ordre.id,
        'mode': ordre.mode_acheminement_physique,
        'poids_total_kg': poids_total_kg,
        'distance_km': ordre.distance_km,
        'facteur_kg_co2_par_tonne_km': None,
        'estimation_kg_co2': None,
        'libelle': libelle,
    }
    if ordre.distance_km is None:
        base['motif'] = 'distance_km non renseignée.'
        return base

    facteur = FacteurEmissionCO2.objects.filter(
        company=ordre.company, mode=ordre.mode_acheminement_physique).first()
    if facteur is None:
        base['motif'] = (
            f"Aucun facteur d'émission configuré pour le mode "
            f"« {ordre.mode_acheminement_physique} » (Paramètres).")
        return base

    estimation = poids_tonnes * ordre.distance_km * facteur.facteur_kg_co2_par_tonne_km
    base['facteur_kg_co2_par_tonne_km'] = facteur.facteur_kg_co2_par_tonne_km
    base['estimation_kg_co2'] = estimation
    return base


def _filtre_periode(qs, periode, champ='created_at'):
    """Filtre `qs` sur ``<champ>__year``/``<champ>__month`` pour une
    ``periode`` au format ``YYYY-MM`` — no-op si absente/invalide. Convention
    PARTAGÉE par NTLOG24 (dashboard)/NTLOG27 (export fret)/NTLOG31 (relevé
    litiges) : les trois filtrent sur ``created_at``, jamais sur des champs
    différents, pour que les totaux affichés/exportés correspondent au
    dernier chiffre près (critères d'acceptation NTLOG27/31)."""
    if not periode:
        return qs
    try:
        annee, mois = periode.split('-')
        return qs.filter(**{
            f'{champ}__year': int(annee), f'{champ}__month': int(mois)})
    except (ValueError, TypeError):
        return qs


def tableau_bord_logistique(company, periode=None):
    """NTLOG24 — synthèse logistique d'une société sur une `periode`
    optionnelle (``YYYY-MM``, filtre `_filtre_periode` sur ``created_at``) :
    coût/kg transporté, taux de service, litiges ouverts + montant contesté,
    répartition flotte propre/affrètement, CO2 total estimé. Exclut TOUJOURS
    les ordres annulés (`OrdreTransport.Statut.ANNULE`).

    « Taux de service » = part des ordres LIVRÉS dont la dernière étape de
    livraison (`EtapeTransport.date_reelle`) est ≤ `date_livraison_prevue` ;
    un ordre sans `date_livraison_prevue` renseignée ou sans étape de
    livraison clôturée n'est pas jugeable en retard et compte « à temps »
    (aucune preuve du contraire) — comportement documenté, pas un bug."""
    from django.db.models import Count, Sum

    from .models import CoutFretReel, EtapeTransport, LitigeTransport, OrdreTransport

    ordres_qs = _filtre_periode(
        OrdreTransport.objects.filter(company=company)
        .exclude(statut=OrdreTransport.Statut.ANNULE),
        periode)
    ordres = list(ordres_qs.prefetch_related('lignes', 'etapes'))

    couts_qs = _filtre_periode(
        CoutFretReel.objects.filter(company=company), periode)
    total_fret_ht = (
        couts_qs.aggregate(total=Sum('montant_ht'))['total'] or Decimal('0'))

    livres = [o for o in ordres if o.statut == OrdreTransport.Statut.LIVRE]
    poids_livre_kg = sum(
        (ligne.poids_kg for o in livres for ligne in o.lignes.all()),
        Decimal('0'))
    cout_par_kg_transporte = (
        (total_fret_ht / poids_livre_kg) if poids_livre_kg else None)

    a_temps = 0
    for o in livres:
        dates_reelles = [
            e.date_reelle for e in o.etapes.all()
            if e.type_etape == EtapeTransport.TypeEtape.LIVRAISON
            and e.date_reelle]
        if (not o.date_livraison_prevue or not dates_reelles
                or max(dates_reelles) <= o.date_livraison_prevue):
            a_temps += 1
    taux_service_pct = (
        round(a_temps / len(livres) * 100, 1) if livres else None)

    litiges_qs = _filtre_periode(
        LitigeTransport.objects.filter(
            company=company, statut=LitigeTransport.Statut.OUVERT),
        periode)
    litiges_agg = litiges_qs.aggregate(
        nb=Count('id'), montant=Sum('montant_conteste'))

    repartition_mode_transport = {
        OrdreTransport.ModeTransport.FLOTTE_PROPRE: 0,
        OrdreTransport.ModeTransport.AFFRETEMENT: 0,
    }
    for o in ordres:
        if o.mode_transport in repartition_mode_transport:
            repartition_mode_transport[o.mode_transport] += 1

    co2_total_estime_kg = Decimal('0')
    for o in ordres:
        if o.distance_km is None:
            continue
        resultat = estimer_co2_transport(o.id, company=company)
        if resultat and resultat.get('estimation_kg_co2') is not None:
            co2_total_estime_kg += resultat['estimation_kg_co2']

    return {
        'periode': periode,
        'nb_ordres': len(ordres),
        'nb_livres': len(livres),
        'total_fret_ht': total_fret_ht,
        'poids_livre_kg': poids_livre_kg,
        'cout_par_kg_transporte': cout_par_kg_transporte,
        'taux_service_pct': taux_service_pct,
        'litiges_ouverts_count': litiges_agg['nb'] or 0,
        'litiges_ouverts_montant_conteste': (
            litiges_agg['montant'] or Decimal('0')),
        'repartition_mode_transport': repartition_mode_transport,
        'co2_total_estime_kg': co2_total_estime_kg,
    }
