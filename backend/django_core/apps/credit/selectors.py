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
