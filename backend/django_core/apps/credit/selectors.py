"""apps.credit.selectors — lectures pures (jamais d'écriture ici).

Toute lecture cross-app passe par le ``selectors.py`` PUBLIC déjà exposé de
l'app cible (jamais un import direct de ``apps.ventes.models``/
``apps.crm.models`` ni une modification du ``selectors.py`` d'une autre app —
frontière inter-app CLAUDE.md). Quand aucun sélecteur existant ne couvre
exactement un besoin, on compose avec ceux qui existent plutôt que d'en
ajouter un nouveau côté ventes.
"""
from decimal import Decimal


def encours_client(client):
    """NTCRD4 — encours documentaire réel d'un client : Σ factures ouvertes
    (hors ``ANNULEE``/``PAYEE``), via le sélecteur EXISTANT
    ``apps.ventes.selectors.encours_clients_par_tiers`` (YLEDG13, déjà exposé
    cross-app — jamais un nouvel import/édition de ``ventes.selectors``).

    LIMITE CONNUE (périmètre de ce lane) : ne compte QUE les factures
    ouvertes — les BC ``LIVRE`` sans facture liée ne sont pas inclus, faute
    d'un sélecteur ventes existant les exposant sans modifier
    ``apps.ventes.selectors`` (hors périmètre déclaré de cette app). Un
    sélecteur ventes dédié (``encours_ouvert``) pourrait fermer cet écart
    dans une lane ventes future."""
    from apps.ventes.selectors import encours_clients_par_tiers

    entries = encours_clients_par_tiers(client.company)
    for entry in entries:
        if entry['tiers_id'] == client.id:
            return entry['encours']
    return Decimal('0')


def disponible_credit(client):
    """NTCRD5 — disponible de crédit d'un client.

    ``montant_limite - encours_client`` ; ``None`` (illimité) si aucune
    ``LimiteCredit`` active n'est définie pour ce client — comportement
    historique inchangé (aucun hold possible sans limite). Renvoie
    ``{'limite': Decimal|None, 'encours': Decimal, 'disponible': Decimal|None,
    'pct_utilise': float|None, 'depasse': bool}``."""
    from .models import LimiteCredit

    encours = encours_client(client)
    limite_obj = LimiteCredit.objects.filter(
        client=client, actif=True).first()
    montant_limite = limite_obj.montant_limite if limite_obj else None

    if montant_limite is None:
        return {
            'limite': None, 'encours': encours, 'disponible': None,
            'pct_utilise': None, 'depasse': False,
        }

    disponible = montant_limite - encours
    pct_utilise = (
        float(encours / montant_limite) if montant_limite > 0 else 0.0)
    return {
        'limite': montant_limite, 'encours': encours,
        'disponible': disponible, 'pct_utilise': pct_utilise,
        'depasse': disponible < 0,
    }


def fiche_credit(client):
    """NTCRD10 — vue consolidée « fiche crédit client » : limite, encours,
    disponible, pct utilisé, lettre de score (via
    ``apps.ventes.selectors.comportement_paiement`` — jamais réimplémenté ici),
    mode de hold actif, et historique des dérogations. Lecture seule."""
    from apps.ventes.selectors import comportement_paiement

    from .models import DerogationCredit, LimiteCredit

    dispo = disponible_credit(client)
    limite_obj = LimiteCredit.objects.filter(client=client, actif=True).first()
    score = comportement_paiement(client)

    derogations = [
        {
            'id': d.id, 'montant_demande': d.montant_demande,
            'statut': d.statut, 'motif': d.motif,
            'date_creation': d.date_creation,
            'date_decision': d.date_decision,
            'valide_jusqu_au': d.valide_jusqu_au,
            'est_valide': d.est_valide,
        }
        for d in DerogationCredit.objects.filter(client=client)
    ]

    return {
        'client_id': client.id,
        'limite': dispo['limite'],
        'encours': dispo['encours'],
        'disponible': dispo['disponible'],
        'pct_utilise': dispo['pct_utilise'],
        'depasse': dispo['depasse'],
        'mode_hold': limite_obj.mode_hold if limite_obj else None,
        'lettre_score': score['lettre'],
        'score': score['score'],
        'derogations': derogations,
    }


def quota_assurance_utilise(client):
    """NTCRD18 — compare l'encours du client (NTCRD4) au ``montant_garanti``
    de sa police active. Un client sans encours garanti ``accorde`` est « non
    couvert » (``garanti=None``, aucune fausse alerte). Un dépassement de la
    garantie assureur N'IMPLIQUE PAS un blocage (juste une alerte — l'assureur
    reste souverain). Renvoie ``{'garanti': Decimal|None, 'utilise': Decimal,
    'pct': float|None, 'depasse_garantie': bool}``. Lecture seule."""
    from .models import EncoursGarantiClient

    utilise = encours_client(client)
    garanti_obj = EncoursGarantiClient.objects.filter(
        client=client, police__actif=True,
        statut_agrement=EncoursGarantiClient.StatutAgrement.ACCORDE,
    ).order_by('-montant_garanti').first()

    if garanti_obj is None:
        return {
            'garanti': None, 'utilise': utilise, 'pct': None,
            'depasse_garantie': False,
        }

    garanti = garanti_obj.montant_garanti
    pct = float(utilise / garanti) if garanti > 0 else 0.0
    return {
        'garanti': garanti, 'utilise': utilise, 'pct': pct,
        'depasse_garantie': utilise > garanti,
    }


def badge_credit(client):
    """NTCRD23 — pastille d'état crédit d'un client pour les listes
    (devis/BC) : ``vert`` (marge OK), ``orange`` (proche/mode avertissement en
    dépassement) ou ``rouge`` (blocage actif + dépassement). Lecture seule,
    léger."""
    from .models import LimiteCredit

    limite_obj = LimiteCredit.objects.filter(client=client, actif=True).first()
    if limite_obj is None or limite_obj.montant_limite is None:
        return 'vert'

    dispo = disponible_credit(client)
    if dispo['depasse']:
        if limite_obj.mode_hold == LimiteCredit.ModeHold.BLOCAGE:
            return 'rouge'
        return 'orange'
    if dispo['pct_utilise'] is not None and dispo['pct_utilise'] >= 0.8:
        return 'orange'
    return 'vert'


def badges_credit(company, client_ids):
    """NTCRD23 — pastilles d'état crédit pour une liste d'ids clients (batch,
    company-scopé). Renvoie ``{client_id: 'vert'|'orange'|'rouge'}``."""
    from apps.crm.selectors import client_base_qs

    clients = client_base_qs(company).filter(id__in=client_ids)
    return {c.id: badge_credit(c) for c in clients}


def limite_suggeree(client):
    """NTCRD27 — limite de crédit SUGGÉRÉE pour un client sans limite.

    Règle simple DOCUMENTÉE (jamais opaque) et toujours modifiable par le
    Directeur avant validation : ``2 × encours_actuel`` arrondi au millier
    supérieur (marge de sécurité au-dessus de l'exposition constatée) ; 0 si le
    client n'a aucun encours (le Directeur saisit alors manuellement).

    NOTE — la variante « 2× la moyenne des 3 dernières factures payées à temps »
    évoquée par NTCRD27 nécessiterait un sélecteur ventes exposant l'historique
    des factures payées (absent) : hors périmètre de ce lane (jamais un import
    de ``facturation.models`` ni une édition de ``ventes.selectors``). La règle
    basée sur l'encours reste cohérente et modifiable."""
    from decimal import Decimal

    encours = encours_client(client)
    if encours <= 0:
        suggestion = Decimal('0')
    else:
        millier = (encours / Decimal('1000')).to_integral_value(
            rounding='ROUND_CEILING') * Decimal('1000')
        suggestion = millier * 2
    return {
        'suggestion': suggestion,
        'base_encours': encours,
        'regle': '2 x encours actuel, arrondi au millier superieur',
    }


def segment_du_client(client):
    """NTCRD13 — segment crédit affecté à un client (repli local
    ``SegmentClientCredit``), ou ``None`` si aucun (comportement société par
    défaut inchangé)."""
    from .models import SegmentClientCredit

    lien = SegmentClientCredit.objects.filter(client=client).first()
    return lien.segment if lien else None


def condition_paiement_client(client):
    """NTCRD13 — condition de paiement résolue pour un client : la
    ``ConditionPaiementSegment`` de son segment si présent, sinon ``None``
    (l'appelant retombe alors sur les réglages société actuels — AUCUN
    changement du comportement par défaut). Lecture seule."""
    from .models import ConditionPaiementSegment

    segment = segment_du_client(client)
    if not segment:
        return None
    return ConditionPaiementSegment.objects.filter(
        company=client.company, segment=segment).first()


def rapport_exposition(company, clients=None):
    """NTCRD19 — rapport d'exposition consolidée : pour tous les clients actifs
    de ``company`` (ou la liste ``clients`` fournie — NTCRD36 visibilité
    restreinte), encours réel, limite, disponible, lettre de score et garantie
    assurance si applicable, trié par RISQUE décroissant (pondération simple
    documentée : score de la lettre + pct utilisé). Lecture seule.

    Le tri combine deux signaux normalisés (0-1) sans nouvel algorithme opaque :
    ``risque = lettre_num/4 + min(pct_utilise, 1)`` — une lettre E (num 4) et un
    dépassement pèsent le plus. Tri stable (id en clé secondaire)."""
    from apps.ventes.selectors import comportement_paiement

    from .models import LimiteCredit

    if clients is None:
        from apps.crm.selectors import client_base_qs
        clients = list(client_base_qs(company))

    lettre_num = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
    limites = {
        lc.client_id: lc
        for lc in LimiteCredit.objects.filter(company=company, actif=True)
    }

    lignes = []
    for client in clients:
        dispo = disponible_credit(client)
        score = comportement_paiement(client)
        quota = quota_assurance_utilise(client)
        lc = limites.get(client.id)
        pct = dispo['pct_utilise'] or 0.0
        risque = lettre_num.get(score['lettre'], 0) / 4.0 + min(pct, 1.0)
        lignes.append({
            'client_id': client.id,
            'client_nom': (f"{client.prenom or ''} {client.nom}".strip()),
            'encours': dispo['encours'],
            'limite': dispo['limite'],
            'disponible': dispo['disponible'],
            'pct_utilise': dispo['pct_utilise'],
            'depasse': dispo['depasse'],
            'lettre_score': score['lettre'],
            'mode_hold': lc.mode_hold if lc else None,
            'garantie_assurance': quota['garanti'],
            'depasse_garantie': quota['depasse_garantie'],
            '_risque': risque,
        })

    lignes.sort(key=lambda ligne: (-ligne['_risque'], ligne['client_id']))
    for ligne in lignes:
        del ligne['_risque']
    return lignes


def rapport_derogations(company, date_debut=None, date_fin=None, client_id=None):
    """NTCRD26 — liste des ``DerogationCredit`` d'une société sur une période
    (``date_creation`` dans [date_debut, date_fin]), avec statut, montant,
    décideur et délai de traitement moyen (heures création→décision, sur les
    dérogations décidées). Renvoie ``{'lignes': [...], 'nb_approuvees': int,
    'delai_traitement_moyen_h': float|None}``. Company-scopé, lecture seule."""
    from .models import DerogationCredit

    qs = DerogationCredit.objects.filter(company=company).select_related(
        'demandeur', 'approuvee_par', 'client')
    if date_debut is not None:
        qs = qs.filter(date_creation__date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_creation__date__lte=date_fin)
    if client_id is not None:
        qs = qs.filter(client_id=client_id)

    lignes = []
    delais = []
    nb_approuvees = 0
    for d in qs:
        if d.statut == DerogationCredit.Statut.APPROUVEE:
            nb_approuvees += 1
        delai_h = None
        if d.date_decision and d.date_creation:
            delai_h = (d.date_decision - d.date_creation).total_seconds() / 3600.0
            delais.append(delai_h)
        lignes.append({
            'id': d.id,
            'client_id': d.client_id,
            'montant_demande': d.montant_demande,
            'statut': d.statut,
            'demandeur': getattr(d.demandeur, 'username', None),
            'decideur': getattr(d.approuvee_par, 'username', None),
            'date_creation': d.date_creation,
            'date_decision': d.date_decision,
            'delai_traitement_h': delai_h,
        })

    delai_moyen = round(sum(delais) / len(delais), 2) if delais else None
    return {
        'lignes': lignes,
        'nb_approuvees': nb_approuvees,
        'delai_traitement_moyen_h': delai_moyen,
    }


def score_credit(client):
    """NTCRD12 — enveloppe fine autour de
    ``apps.ventes.selectors.comportement_paiement`` (jamais réimplémenté ici)
    + la position vs limite de crédit (NTCRD5). Renvoie lettre A-E + disponible
    + une recommandation lisible. Lecture seule."""
    from apps.ventes.selectors import comportement_paiement

    score = comportement_paiement(client)
    dispo = disponible_credit(client)

    if dispo['limite'] is None:
        recommandation = 'Aucune limite définie — marge illimitée.'
    elif dispo['depasse']:
        recommandation = 'Limite atteinte, dérogation requise.'
    elif dispo['pct_utilise'] is not None and dispo['pct_utilise'] >= 0.8:
        recommandation = 'Proche de la limite — vigilance.'
    else:
        recommandation = 'Marge confortable.'

    return {
        'client_id': client.id,
        'lettre': score['lettre'],
        'score': score['score'],
        'limite': dispo['limite'],
        'encours': dispo['encours'],
        'disponible': dispo['disponible'],
        'pct_utilise': dispo['pct_utilise'],
        'depasse': dispo['depasse'],
        'recommandation': recommandation,
    }


def derogation_valide_pour(client, montant):
    """NTCRD9 — vrai si le client a une ``DerogationCredit`` APPROUVEE, non
    expirée, dont le ``montant_demande`` couvre ``montant`` (>= montant de la
    transaction). Lève ainsi le hold de blocage pour CE montant précis."""
    from decimal import Decimal

    from .models import DerogationCredit

    montant = Decimal(montant or 0)
    for d in DerogationCredit.objects.filter(
            client=client, statut=DerogationCredit.Statut.APPROUVEE):
        if d.est_valide and d.montant_demande >= montant:
            return True
    return False
