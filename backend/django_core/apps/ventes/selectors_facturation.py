"""Sélecteurs LECTURE SEULE de la facturation (factures, paiements, encours,
recouvrement, références) — sortis de ``apps/ventes/selectors.py`` par SPL143
(déplacement pur, corps inchangés ; propriétaire : facturation).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle).
"""


def compter_factures(company):
    """SCA22 — nombre de factures d'une société (console fondateur). Lecture
    seule cross-app (jamais un import direct des modèles ventes)."""
    from .models import Facture
    return Facture.objects.filter(company=company).count()


def factures_echues(company, *, today=None):
    """YEVNT3 — Factures en retard d'une société : échéance dépassée, non
    payées, non annulées. Point d'entrée cross-app sanctionné pour
    `apps.notifications` (jamais un import direct de `apps.ventes.models`).
    Lecture seule ; renvoie un QuerySet (peut être vide)."""
    from django.utils import timezone as _tz

    from .models import Facture
    today = today or _tz.localdate()
    return Facture.objects.filter(
        company=company, date_echeance__isnull=False,
        date_echeance__lt=today,
    ).exclude(
        statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE],
    ).select_related('client', 'created_by')


def get_facture_scoped(company, facture_id):
    """XFAC14 — Facture (AR) scopée société par id, ou ``None``. Point
    d'entrée cross-app (compensation AR/AP) : lire une facture client sans
    importer ``apps.ventes.models``. Lecture seule."""
    from .models import Facture
    return (Facture.objects
            .select_related('client')
            .filter(id=facture_id, company=company).first())


def releve_client_portail(client):
    """XFAC26 — Relevé de compte self-service (portail client) : réutilise
    ``recouvrement._releve_data`` (même patron que l'écran interne, sans
    filtre de portée — le portail montre TOUT le compte du client, jamais un
    sous-ensemble par créateur) et ajoute une mini balance âgée
    (0-30/31-60/61-90/90+) + le solde courant, cohérents avec
    ``balance_agee``. Point d'entrée cross-app (jamais un import de
    ``apps.ventes.models``). Lecture seule."""
    from decimal import Decimal

    from .models import Facture
    from .recouvrement import _releve_data

    data = _releve_data(client, user=None)

    buckets = {
        'b0_30': Decimal('0'), 'b31_60': Decimal('0'),
        'b61_90': Decimal('0'), 'b90_plus': Decimal('0'),
    }
    qs = (Facture.objects
          .filter(client=client)
          .exclude(statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE]))
    for facture in qs:
        du = facture.montant_du
        if not du:
            continue
        jr = facture.jours_retard
        if jr <= 30:
            buckets['b0_30'] += du
        elif jr <= 60:
            buckets['b31_60'] += du
        elif jr <= 90:
            buckets['b61_90'] += du
        else:
            buckets['b90_plus'] += du

    data['solde_courant'] = data['totaux']['du']
    data['balance_agee'] = {k: str(v) for k, v in buckets.items()}
    return data


def releve_client_pdf_bytes(client):
    """XFAC26 — PDF du relevé de compte (portail client), même rendu que
    l'écran interne (``client_releve_pdf``). Lecture seule, jamais un import
    de ``apps.ventes.models`` hors de ce module."""
    from .recouvrement import _releve_data
    from .utils.pdf import generate_releve_pdf

    return generate_releve_pdf(client, _releve_data(client, user=None))


def paiements_des_factures(facture_ids, *, debut=None, fin=None):
    """NTSUB20 — Paiements ENCAISSÉS sur un ensemble de factures, période bornée.

    Thin selector cross-app (relevé d'abonnement) : jamais un import de
    ``ventes``/``facturation.models`` depuis l'extérieur. Les paiements REJETÉS (YLEDG5) sont exclus — ils ne
    représentent aucun encaissement réel.

    Renvoie une liste de dicts ``{'id', 'facture_id', 'date_paiement',
    'montant', 'mode', 'mode_libelle', 'reference'}``, du plus ancien au plus
    récent. Lecture seule.
    """
    from .models import Paiement

    if not facture_ids:
        return []
    qs = Paiement.objects.filter(
        facture_id__in=list(facture_ids), statut=Paiement.Statut.ENCAISSE)
    if debut:
        qs = qs.filter(date_paiement__gte=debut)
    if fin:
        qs = qs.filter(date_paiement__lte=fin)
    return [{
        'id': p.id,
        'facture_id': p.facture_id,
        'date_paiement': p.date_paiement,
        'montant': p.montant,
        'mode': p.mode,
        'mode_libelle': p.get_mode_display(),
        'reference': p.reference or '',
    } for p in qs.order_by('date_paiement', 'id')]


def paiements_totaux_par_mode(facture_ids):
    """Totaux + nombre de ``Paiement`` groupés par mode, pour un ensemble de
    factures (thin selector pour apps.pos — rapport Z de session XPOS4)."""
    from django.db.models import Count, Sum
    from .models import Paiement
    if not facture_ids:
        return []
    return list(
        Paiement.objects.filter(facture_id__in=facture_ids)
        .values('mode')
        .annotate(total=Sum('montant'), nb=Count('id')))


# ── XFAC15 — score comportement de paiement (agrège FG365) ────────────────

_SCORE_BANDS = (
    (0.20, 'A'), (0.40, 'B'), (0.60, 'C'), (0.80, 'D'),
)


def _score_to_letter(score):
    for threshold, letter in _SCORE_BANDS:
        if score < threshold:
            return letter
    return 'E'


def _retard_reel_jours(facture):
    """Jours émission → encaissement RÉELS pour une facture soldée par
    paiement (dernière date de paiement enregistrée moins émission). Renvoie
    ``None`` si la facture n'a aucun paiement (rien à mesurer)."""
    dernier = None
    for p in facture.paiements.all():
        if p.date_paiement and (dernier is None or p.date_paiement > dernier):
            dernier = p.date_paiement
    if dernier is None or not facture.date_emission:
        return None
    delta = (dernier - facture.date_emission).days
    return delta if delta > 0 else 0


def comportement_paiement(client):
    """XFAC15 — score de comportement de paiement agrégé d'un client.

    AGRÈGE les scores FG365 (``core.payment_delay.payment_delay_risk``, jamais
    ré-implémenté ici) de toutes les factures ouvertes du client + son retard
    moyen RÉEL (jours émission → encaissement, sur les factures déjà payées) →
    une lettre A (excellent payeur) à E (à risque). Un client sans historique
    exploitable (aucune facture payée, aucune facture ouverte) reçoit un score
    NEUTRE (``used_fallback=True`` du moteur pur).

    Renvoie un dict :
      ``{'score': float, 'lettre': 'A'..'E', 'retard_moyen_jours': float,
         'nb_factures_ouvertes': int, 'nb_factures_historique': int,
         'used_fallback': bool}``
    """
    from core.payment_delay import payment_delay_risk
    from .models import Facture

    # AUD158 — LE PRÉFETCH DIT EXACTEMENT CE QUE CE SÉLECTEUR LIT. Il ne
    # préchargeait que `paiements`/`avoirs` alors que `montant_du` touche AUSSI
    # `lignes`, `notes_debit`, `retenues_subies` et `affectations_paiement`, et
    # que la boucle de score lisait `relances.count()` : chaque facture du
    # client coûtait donc ~18 requêtes, et `balance_agee` appelait ce sélecteur
    # une fois PAR FACTURE — un coût quadratique en portefeuille.
    factures = list(
        Facture.objects.filter(client=client)
        .exclude(statut=Facture.Statut.ANNULEE)
        .prefetch_related(
            'lignes', 'paiements', 'relances',
            'avoirs', 'avoirs__lignes',
            'notes_debit', 'notes_debit__lignes',
            'retenues_subies', 'affectations_paiement__paiement'))

    retards_reels = []
    for f in factures:
        if f.statut == Facture.Statut.PAYEE:
            r = _retard_reel_jours(f)
            if r is not None:
                retards_reels.append(r)

    retard_moyen = (
        sum(retards_reels) / len(retards_reels) if retards_reels else None)

    # AUD158 — `montant_du` ré-agrège six relations : une SEULE lecture par
    # facture (le filtre, `jours_retard` et la feature en faisaient trois).
    dus = {f.pk: f.montant_du for f in factures}
    ouvertes = [f for f in factures if dus[f.pk] > 0]
    prior_late = sum(1 for r in retards_reels if r > 0)

    if not ouvertes:
        # Aucune facture ouverte à scorer : le score client se base
        # uniquement sur l'historique (ou tombe au neutre si aucun non plus).
        features = {}
        if retard_moyen is not None:
            features['client_avg_delay_days'] = retard_moyen
            features['client_prior_late_count'] = prior_late
        result = payment_delay_risk(features)
    else:
        scores = []
        for f in ouvertes:
            feats = {
                'days_overdue': f.jours_retard,
                'montant_du': float(dus[f.pk]),
                # AUD158 — `relances` est préchargé : `len()` lit le cache, là
                # où `.count()` repartait en base pour CHAQUE facture.
                'relance_count': len(f.relances.all()),
            }
            if retard_moyen is not None:
                feats['client_avg_delay_days'] = retard_moyen
                feats['client_prior_late_count'] = prior_late
            scores.append(payment_delay_risk(feats))
        avg_score = sum(r.score for r in scores) / len(scores)
        result = scores[0]
        result.score = avg_score
        result.band = (
            'faible' if avg_score < 0.34 else
            'moyen' if avg_score < 0.67 else 'élevé')

    return {
        'score': round(result.score, 4),
        'lettre': _score_to_letter(result.score),
        'retard_moyen_jours': (
            round(retard_moyen, 1) if retard_moyen is not None else None),
        'nb_factures_ouvertes': len(ouvertes),
        'nb_factures_historique': len(retards_reels),
        'used_fallback': result.used_fallback,
    }


def date_encaissement_prevue(facture, retard_moyen_jours=None):
    """XFAC15 — date d'encaissement PRÉVUE d'une facture ouverte.

    Échéance théorique + retard moyen RÉEL du client (comportemental) au lieu
    de la seule échéance théorique. Sans échéance ou sans retard moyen connu,
    renvoie l'échéance théorique inchangée (comportement neutre/dégradé)."""
    from datetime import timedelta
    if not facture.date_echeance:
        return None
    if not retard_moyen_jours:
        return facture.date_echeance
    return facture.date_echeance + timedelta(days=round(retard_moyen_jours))


# ── XACC29 — Références (pour rapport de continuité des séquences) ────────

def references_factures(company):
    """XACC29 — Références de toutes les ``Facture`` (hors annulées) d'une
    société, pour la détection de trous de séquence côté ``compta`` (jamais un
    import de ``ventes.models`` en dehors de ce module). Lecture seule."""
    from .models import Facture
    return list(
        Facture.objects
        .exclude(statut=Facture.Statut.ANNULEE)
        .filter(company=company)
        .exclude(reference='')
        .values_list('reference', flat=True)
    )


def references_avoirs(company):
    """XACC29 — Références de tous les ``Avoir`` d'une société. Lecture seule."""
    from .models import Avoir
    return list(
        Avoir.objects.filter(company=company)
        .exclude(reference='')
        .values_list('reference', flat=True)
    )


def encours_clients_par_tiers(company):
    """YLEDG13 — encours documentaire (reste dû) par client, factures NON
    annulées d'une société. Point d'entrée cross-app sanctionné
    (rapprochement auxiliaire, jamais un import direct de ``ventes.models``). Renvoie une liste de dicts ``{'tiers_id', 'nom',
    'encours', 'references'}`` (encours > 0 seulement, ``references`` = les
    factures ouvertes de ce client). Lecture seule."""
    from decimal import Decimal
    from .models import Facture

    par_client = {}
    qs = (Facture.objects
          .filter(company=company)
          .exclude(statut=Facture.Statut.ANNULEE)
          .select_related('client')
          # AUD158 — EXACTEMENT les relations que `montant_du` lit. Sans
          # elles, ce point d'entrée cross-app (compta ET credit) posait
          # SIX requêtes par facture ouverte du portefeuille.
          .prefetch_related('lignes', 'paiements', 'avoirs', 'notes_debit',
                            'retenues_subies',
                            'affectations_paiement__paiement'))
    for facture in qs:
        du = facture.montant_du
        if not du:
            continue
        client = facture.client
        entry = par_client.setdefault(client.id, {
            'tiers_id': client.id,
            'nom': (f'{client.prenom} {client.nom}'.strip()
                    if hasattr(client, 'prenom') else str(client)),
            'encours': Decimal('0'),
            'references': [],
        })
        entry['encours'] += Decimal(du)
        entry['references'].append(facture.reference)
    return [v for v in par_client.values() if v['encours'] > 0]


def encours_ouvert_par_tiers(company):
    """NTCRD4 — encours documentaire OUVERT par client, filtré PAR STATUT :
    somme du reste dû des factures dont le statut n'est ni ``PAYEE`` ni
    ``ANNULEE``. Distinct de ``encours_clients_par_tiers`` (YLEDG13, montant-dû
    only, qui inclut une ``PAYEE`` sans règlement enregistré) : ici l'exclusion
    est portée par le STATUT du document, ce que le module crédit exige (une
    facture marquée soldée ne compte plus dans l'exposition, quel que soit son
    reste dû résiduel). Point d'entrée cross-app sanctionné (jamais un import
    direct de ``ventes.models``). Renvoie une liste de dicts
    ``{'tiers_id', 'nom', 'encours', 'references'}`` (encours > 0). Lecture
    seule."""
    from decimal import Decimal
    from .models import Facture

    par_client = {}
    qs = (Facture.objects
          .filter(company=company)
          .exclude(statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE])
          .select_related('client')
          # AUD158 — EXACTEMENT les relations que `montant_du` lit (voir
          # `encours_clients_par_tiers`). AUD153 va solliciter davantage
          # encore ce sélecteur en branchant le credit-hold.
          .prefetch_related('lignes', 'paiements', 'avoirs', 'notes_debit',
                            'retenues_subies',
                            'affectations_paiement__paiement'))
    for facture in qs:
        du = facture.montant_du
        if not du:
            continue
        client = facture.client
        entry = par_client.setdefault(client.id, {
            'tiers_id': client.id,
            'nom': (f'{client.prenom} {client.nom}'.strip()
                    if hasattr(client, 'prenom') else str(client)),
            'encours': Decimal('0'),
            'references': [],
        })
        entry['encours'] += Decimal(du)
        entry['references'].append(facture.reference)
    return [v for v in par_client.values() if v['encours'] > 0]


def reste_du_factures_brouillon(company, client_id):
    """WIR93 — reste dû des factures ``BROUILLON`` d'un client, borné société.

    ``encours_ouvert_par_tiers`` inclut les brouillons, tandis que
    ``crm.selectors.client_credit_warning`` (moteur FG41/XFAC28) ne compte que
    ``emise``/``en_retard``. Point d'entrée cross-app sanctionné (jamais un
    import direct de ``ventes.models``). Lecture seule."""
    from decimal import Decimal
    from .models import Facture

    total = Decimal('0')
    qs = (Facture.objects
          .filter(company=company, client_id=client_id,
                  statut=Facture.Statut.BROUILLON)
          .prefetch_related('paiements', 'avoirs'))
    for facture in qs:
        du = facture.montant_du
        if du:
            total += Decimal(du)
    return total


def ca_devis_factures_par_clients(company, client_ids):
    """XSAL9 — CA (devis + factures) agrégé, PAR client, pour une liste
    d'ids clients d'une même société. Point d'entrée cross-app sanctionné
    pour ``apps.crm`` (consolidation groupe — ``crm.selectors.
    consolidation_client``), jamais un import direct de ``ventes.models``.

    Renvoie un dict ``{client_id: {'ca_devis': Decimal, 'ca_factures':
    Decimal, 'nb_devis': int, 'nb_factures': int}}`` — un client sans devis/
    facture n'apparaît PAS dans le résultat (l'appelant fournit un défaut à
    zéro). Lecture seule ; jamais de fuite cross-société — filtré par
    ``company`` (le devis/facture) ET ``client__company=company`` (le client
    lui-même) EN PLUS de ``client_id__in`` : un ``client_id`` d'une AUTRE
    société ne doit jamais fuiter des chiffres même si (par bug amont ou
    appel API malveillant) un ``Devis``/``Facture`` avait été mal rattaché à
    un client d'une société différente de la sienne."""
    from decimal import Decimal

    from .models import Devis, Facture

    client_ids = list(client_ids or [])
    if not client_ids:
        return {}

    out = {}
    devis_qs = (Devis.objects
                .filter(company=company, client_id__in=client_ids,
                        client__company=company)
                .exclude(statut=Devis.Statut.REFUSE))
    for devis in devis_qs:
        entry = out.setdefault(devis.client_id, {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        })
        try:
            entry['ca_devis'] += Decimal(str(devis.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_devis'] += 1

    facture_qs = (Facture.objects
                  .filter(company=company, client_id__in=client_ids,
                          client__company=company)
                  .exclude(statut=Facture.Statut.ANNULEE))
    for facture in facture_qs:
        entry = out.setdefault(facture.client_id, {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        })
        try:
            entry['ca_factures'] += Decimal(str(facture.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_factures'] += 1

    return out


def acompte_paye_pour_devis(devis_id, company):
    """YSERV1 — vrai si le devis a au moins une ``Facture`` de
    ``type_facture='acompte'`` au statut ``payee`` — point d'entrée cross-app
    sanctionné pour ``apps.installations`` (jamais un import direct de
    ``apps.ventes.models``). Lecture seule ; ``devis_id`` sans facture
    d'acompte payée (ou inconnu/autre société) renvoie ``False``."""
    from .models import Facture
    if not devis_id:
        return False
    return Facture.objects.filter(
        devis_id=devis_id, company=company,
        type_facture=Facture.TypeFacture.ACOMPTE,
        statut=Facture.Statut.PAYEE,
    ).exists()


def etat_recouvrement_client(company, client_id):
    """YCASH4 — État de recouvrement d'UN client, pour le front du funnel.

    Agrège ce que le blueprint L2C appelle "l'état recouvrement remontant au
    commercial" : le retard maximum parmi ses factures ouvertes, le niveau de
    relance atteint (réutilise ``recouvrement._current_level`` — jamais une
    nouvelle échelle), et l'encours échu total (= somme des ``montant_du``
    des factures en retard, jamais un montant TTC non dû). Ne modifie AUCUN
    statut ; pur agrégat lecture seule pour l'avertissement FG41 enrichi.

    Renvoie :
      ``{'retard_max_jours': int, 'niveau_relance': dict|None,
         'encours_echu': Decimal, 'a_jour': bool}``
    Un client sans facture en retard renvoie ``a_jour=True`` et
    ``encours_echu=0`` — l'appelant n'affiche alors aucun avertissement."""
    from decimal import Decimal
    from .models import Facture
    from .recouvrement import _levels, _current_level

    factures = (
        Facture.objects
        .filter(company=company, client_id=client_id)
        .exclude(statut=Facture.Statut.ANNULEE)
        .prefetch_related('paiements', 'avoirs')
    )

    retard_max = 0
    encours_echu = Decimal('0')
    for f in factures:
        jr = f.jours_retard
        if jr > 0:
            retard_max = max(retard_max, jr)
            encours_echu += f.montant_du

    if retard_max <= 0:
        return {
            'retard_max_jours': 0, 'niveau_relance': None,
            'encours_echu': Decimal('0'), 'a_jour': True,
        }

    niveau = _current_level(retard_max, _levels(company))
    return {
        'retard_max_jours': retard_max,
        'niveau_relance': niveau,
        'encours_echu': encours_echu,
        'a_jour': False,
    }


def analyse_facturation(company, debut, fin):
    """ZFAC10 — Analyse de facturation : agrégat HT/TVA/TTC des factures
    scopées société, groupé par mois d'émission ET par client ET par statut,
    sur ``[debut, fin)``. Factures annulées EXCLUES du CA. Lecture pure —
    aucune écriture. Renvoie une liste de dicts triée par mois puis client :

    ``{'mois': 'YYYY-MM', 'client_id', 'client_nom', 'statut',
       'total_ht', 'total_tva', 'total_ttc', 'nb_factures'}``
    """
    from decimal import Decimal

    from .models import Facture

    factures = (
        Facture.objects
        .filter(company=company, date_emission__gte=debut,
                date_emission__lt=fin)
        .exclude(statut=Facture.Statut.ANNULEE)
        .select_related('client')
    )

    buckets = {}
    for f in factures:
        mois = f.date_emission.strftime('%Y-%m') if f.date_emission else ''
        client_nom = (
            f"{f.client.nom} {f.client.prenom or ''}".strip()
            if f.client_id else ''
        )
        key = (mois, f.client_id, f.statut)
        entry = buckets.setdefault(key, {
            'mois': mois, 'client_id': f.client_id, 'client_nom': client_nom,
            'statut': f.statut, 'total_ht': Decimal('0'),
            'total_tva': Decimal('0'), 'total_ttc': Decimal('0'),
            'nb_factures': 0,
        })
        entry['total_ht'] += f.total_ht
        entry['total_tva'] += f.total_tva
        entry['total_ttc'] += f.total_ttc
        entry['nb_factures'] += 1

    rows = list(buckets.values())
    rows.sort(key=lambda r: (r['mois'], r['client_nom'], r['statut']))
    return rows


def devis_a_facturer(company, *, jours=7, today=None):
    """ZFAC12 — ``Devis`` ``accepte`` d'une société, sans ``Facture`` liée
    depuis PLUS de ``jours`` jours (revenu bloqué en amont, backlog à
    facturer). Un devis déjà facturé (au moins une ``Facture`` via
    ``devis.factures``) est ignoré. Lecture seule."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import Devis

    today = today or timezone.now().date()
    seuil = today - timedelta(days=jours)

    candidats = (
        Devis.objects
        .filter(company=company, statut=Devis.Statut.ACCEPTE,
                date_acceptation__isnull=False,
                date_acceptation__lte=seuil)
        .exclude(factures__isnull=False)
        .distinct()
    )
    return list(candidats)


def tranche_facturee(devis, type_facture):
    """YSERV7 — la facture d'échéancier ``type_facture`` (acompte/
    intermediaire/solde) existe-t-elle déjà pour ce devis ? Lecture seule,
    point d'entrée cross-app sanctionné pour ``apps.installations`` (jamais un
    import direct de ``apps.ventes.models``). Une facture ANNULÉE ne compte
    pas comme émise (la tranche reste due). Renvoie un booléen."""
    if devis is None or not type_facture:
        return False
    from .models import Facture
    return (
        Facture.objects
        .filter(devis=devis, type_facture=type_facture)
        .exclude(statut=Facture.Statut.ANNULEE)
        .exists()
    )


def jours_impaye_facture(facture_id, company):
    """ZCTR2 — Nombre de jours DEPUIS lesquels une facture est impayée.

    Point d'entrée cross-app en LECTURE SEULE (clôture automatique des
    contrats impayés) — jamais un import direct de ``apps.ventes.models``. Renvoie ``0`` si la facture est introuvable (id
    NULL/inconnu, autre société), déjà payée, annulée, ou sans
    ``date_echeance`` (rien à mesurer) : dans tous ces cas rien n'est dû,
    cohérent avec ``Facture.jours_retard``. Sinon renvoie le nombre de jours
    entiers écoulés depuis ``date_echeance`` (0 si l'échéance n'est pas
    encore dépassée)."""
    from .models import Facture
    if not facture_id:
        return 0
    facture = Facture.objects.filter(
        pk=facture_id, company=company).first()
    if facture is None:
        return 0
    return facture.jours_retard


def montants_factures_par_devis(devis_ids, company, exclure_annulee=True):
    """CHT12 — Montants HT/TTC des factures RATTACHÉES à chaque devis,
    agrégés PAR devis, EN BATCH (Facture via le shim ``ventes.models`` —
    ODX17 laisse ``facturation.selectors`` vide).

    Point d'entrée cross-app en LECTURE SEULE — jamais un import direct de
    ``ventes.models``. Renvoie ``{devis_id: {'ht': Decimal, 'ttc': Decimal}}``;
    un devis sans facture rattachée n'apparaît PAS dans le résultat.
    ``exclure_annulee`` (défaut ``True``) exclut les factures ``ANNULEE`` de
    l'agrégat."""
    from decimal import Decimal

    from .models import Facture

    devis_ids = list(devis_ids or [])
    if not devis_ids:
        return {}
    qs = Facture.objects.filter(company=company, devis_id__in=devis_ids)
    if exclure_annulee:
        qs = qs.exclude(statut=Facture.Statut.ANNULEE)
    out = {}
    for facture in qs:
        entry = out.setdefault(
            facture.devis_id, {'ht': Decimal('0'), 'ttc': Decimal('0')})
        try:
            entry['ht'] += Decimal(str(facture.total_ht or 0))
            entry['ttc'] += Decimal(str(facture.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser l'agrégat
            pass
    return out


def carnet_commande_par_mois(company, mois_debut, mois_fin):
    """NTFPA12 — revenu ENGAGÉ (carnet de commandes) par mois de facturation
    prévue, pour ``apps.fpa`` (driver revenu engagé).

    Agrège les ``Devis`` ``accepte`` NON encore facturés (aucune ``Facture``
    liée) dont la date de référence (``date_acceptation``) tombe dans
    ``[mois_debut, mois_fin]``. C'est du signé (100 % pondéré), distinct du
    pipeline probabiliste NTFPA11 — un devis accepté sort automatiquement du
    pipeline (son lead passe SIGNED), donc pas de double-compte. Lecture seule ;
    renvoie ``{'YYYY-MM': Decimal}``.
    """
    from decimal import Decimal

    from .models import Devis

    candidats = (
        Devis.objects
        .filter(company=company, statut=Devis.Statut.ACCEPTE,
                date_acceptation__isnull=False,
                date_acceptation__gte=mois_debut,
                date_acceptation__lte=mois_fin)
        .exclude(factures__isnull=False)
        .distinct()
        .prefetch_related('lignes')
    )
    par_mois = {}
    for devis in candidats:
        d = devis.date_acceptation
        cle = f'{d.year:04d}-{d.month:02d}'
        try:
            montant = Decimal(str(devis.total_ttc or 0))
        except Exception:
            montant = Decimal('0')
        par_mois[cle] = par_mois.get(cle, Decimal('0')) + montant
    return par_mois


# ── AUD112 — UN prédicat unique « ce devis est-il déjà facturé ? » ──────────
# Les DEUX voies de facturation étaient totalement aveugles l'une à l'autre :
# ``bon_commande.creer_facture`` ne gardait que
# ``Facture.objects.filter(bon_commande=bc)``, et l'échéancier comptait les
# tranches via ``devis.factures``, qui ne voit AUCUNE facture de la chaîne BC.
# Un devis converti en BC puis facturé pouvait donc être facturé une SECONDE
# fois par l'échéancier — le client recevait deux fois la même facture, jusqu'à
# 200 %. Ces trois selectors sont la source unique consultée par les deux
# portes.

def factures_via_bon_commande(devis, *, inclure_annulees=False):
    """Factures de la chaîne BON DE COMMANDE de ce devis (queryset).

    C'est le trou : que ``Facture.devis`` soit réservé à l'échéancier est
    assumé — ce qui ne l'était pas, c'est que RIEN ne regardait
    ``bon_commande__devis``."""
    from .models import Facture
    qs = Facture.objects.filter(bon_commande__devis=devis)
    if not inclure_annulees:
        qs = qs.exclude(statut=Facture.Statut.ANNULEE)
    return qs


def factures_du_devis(devis, *, inclure_annulees=False):
    """TOUTES les factures d'un devis, LES QUATRE PORTES CONFONDUES (queryset).

    ``Q(devis=devis) | Q(bon_commande__devis=devis) | Q(sources__devis=devis)``
    : l'échéancier et la facture complète (``devis``), le bon de commande ET
    la facture consolidée (ATOT2 — ``FactureSource`` : une consolidée porte
    ``devis=None``, elle était invisible). Les factures ANNULÉES sont exclues
    par défaut (elles ne consomment plus rien)."""
    from django.db.models import Q

    from .models import Facture
    qs = Facture.objects.filter(
        Q(devis=devis) | Q(bon_commande__devis=devis)
        | Q(sources__devis=devis))
    if not inclure_annulees:
        qs = qs.exclude(statut=Facture.Statut.ANNULEE)
    return qs.distinct()


def devis_deja_facture(devis):
    """LE prédicat partagé : ce devis est-il déjà (partiellement) facturé ?

    Appelé depuis LES DEUX portes — ``bon_commande.creer_facture`` (qui refuse
    en 400 si des tranches d'échéancier existent) et
    ``utils.echeancier.creer_facture_tranche`` (qui refuse si la chaîne BC a
    déjà facturé). Un devis sans facture active renvoie ``False`` : les deux
    portes restent grandes ouvertes dans le cas normal."""
    if devis is None:
        return False
    return factures_du_devis(devis).exists()


class DevisDejaFacture(ValueError):
    """ATOT2 — refus d'une porte de facturation (message FR prêt pour un 400)."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


#: ATOT2 — les quatre portes de facturation d'un devis.
PORTES_FACTURATION = ('tranche', 'bc', 'complete', 'consolidee')


def est_facture_de_tranche(facture, devis=None):
    """ATOT2 — ``facture`` est-elle une facture de TRANCHE d'échéancier ?

    Une tranche porte son devis (``Facture.devis``), aucun bon de commande et
    n'est pas la facture COMPLÈTE (``facturer-complet``). La facture de BC
    porte aussi ``devis`` (AUD112) mais garde son ``bon_commande`` ; la
    consolidée ne porte pas de devis (``FactureSource``)."""
    from .models import Facture
    if facture.devis_id is None or facture.bon_commande_id is not None:
        return False
    if devis is not None and facture.devis_id != devis.id:
        return False
    return facture.type_facture != Facture.TypeFacture.COMPLETE


def exiger_devis_facturable(devis, porte):
    """ATOT2 (C-ATOT-001) — LA garde unique des quatre portes de facturation.

    « Une vente ne se facture qu'une fois » : ``porte`` ∈
    ``PORTES_FACTURATION``. La porte ``tranche`` reste ouverte tant que les
    seules factures actives du devis sont ses propres tranches (l'échéancier
    continue) ; toute autre porte exige un devis sans AUCUNE facture active
    (``factures_du_devis``, consolidée comprise). Lève ``DevisDejaFacture``
    en nommant la ou les factures existantes ; ne renvoie rien sinon."""
    if porte not in PORTES_FACTURATION:
        raise ValueError(f'Porte de facturation inconnue : {porte!r}.')
    if devis is None:
        return
    actives = list(factures_du_devis(devis).order_by('id'))
    if porte == 'tranche':
        bloquantes = [f for f in actives
                      if not est_facture_de_tranche(f, devis)]
    else:
        bloquantes = actives
    if not bloquantes:
        return
    refs = ', '.join(f.reference for f in bloquantes)
    if len(bloquantes) > 1:
        motif = (f'Ce devis est déjà facturé par {refs} : '
                 'corrigez-les par un avoir.')
    else:
        motif = (f'Ce devis est déjà facturé par {refs} : '
                 'corrigez-la par un avoir.')
    raise DevisDejaFacture(motif)


def kpis_factures(qs):
    """AUD157 (FAC-13) — LE PROPRIÉTAIRE UNIQUE des chiffres monétaires de
    l'écran Factures.

    Le KPI « Encaissé ce mois » (et son jumeau mois précédent) vivait dans
    ``FactureList.jsx``, qui sommait ``p.montant`` de tous les paiements des
    factures chargées SANS filtrer ``p.statut`` : l'écran affichait « Encaissé
    ce mois : 480 000 » en comptant des chèques revenus impayés. Un chiffre
    d'argent calculé côté écran, sans propriétaire backend, avec une définition
    DIFFÉRENTE de ``Facture.montant_paye`` — laquelle exclut bien les paiements
    rejetés (YLEDG5) et compte l'escompte accordé (XFAC12).

    ``qs`` est le queryset DÉJÀ scopé société/portée par l'appelant : ce
    sélecteur ne décide jamais de la visibilité, il ne fait qu'agréger.

    Renvoie des chaînes décimales (jamais des flottants) et les deux mois
    couverts, pour que l'écran n'ait aucun calcul de période à refaire.
    Contrat PACT10 : ``apps/ventes/contract_samples/factures_kpis.json``.
    """
    from datetime import timedelta
    from decimal import Decimal

    from django.db.models import Sum
    from django.utils import timezone

    from .models import Facture, Paiement

    aujourdhui = timezone.localdate()
    premier_du_mois = aujourdhui.replace(day=1)
    fin_mois_precedent = premier_du_mois - timedelta(days=1)
    premier_mois_precedent = fin_mois_precedent.replace(day=1)
    dans_7_jours = aujourdhui + timedelta(days=7)

    def _encaisse(debut, fin):
        """Encaissé d'une période : MÊME définition que ``montant_paye`` —
        les paiements REJETÉS sont exclus, l'escompte accordé compte."""
        agg = (Paiement.objects
               .filter(facture__in=qs.values('pk'),
                       date_paiement__gte=debut, date_paiement__lte=fin)
               .exclude(statut=Paiement.Statut.REJETE)
               .aggregate(montant=Sum('montant'),
                          escompte=Sum('escompte_montant')))
        return ((agg['montant'] or Decimal('0'))
                + (agg['escompte'] or Decimal('0')))

    # L'encours se lit sur les propriétés modèles (source unique) : elles sont
    # le seul endroit qui sait ce que « reste dû » veut dire (avoirs, notes de
    # débit, retenues subies, abandon de créance). Le queryset est borné aux
    # factures VIVANTES et porte le préfetch complet (AUD158/AUD159).
    # ERR-QAH-VENTES-FACTURES-KPI-ENCAISSER — une facture PAYÉE est soldée pour
    # l'écran (Dû 0, hors « Total dû ») même si un marquage sec a laissé un
    # reste théorique : elle sort de l'encours comme annulées et brouillons.
    ouvertes = (qs.exclude(statut__in=[Facture.Statut.ANNULEE,
                                       Facture.Statut.BROUILLON,
                                       Facture.Statut.PAYEE])
                  .prefetch_related('lignes', 'paiements', 'avoirs',
                                    'notes_debit', 'retenues_subies',
                                    'affectations_paiement__paiement'))
    total_du = Decimal('0')
    total_en_retard = Decimal('0')
    total_a_echoir_7j = Decimal('0')
    nb_impayees = 0
    nb_en_retard = 0
    for facture in ouvertes:
        du = facture.montant_du
        if du <= 0:
            continue
        nb_impayees += 1
        total_du += du
        # Une facture au statut « En retard » compte même sans échéance : la
        # tuile doit dire ce que les lignes affichent (ERR-QAH-VENTES-…-KPI).
        if (facture.jours_retard > 0
                or facture.statut == Facture.Statut.EN_RETARD):
            nb_en_retard += 1
            total_en_retard += du
        elif (facture.date_echeance
                and aujourdhui <= facture.date_echeance <= dans_7_jours):
            total_a_echoir_7j += du

    return {
        'mois': aujourdhui.strftime('%Y-%m'),
        'mois_precedent': fin_mois_precedent.strftime('%Y-%m'),
        'encaisse_mois': str(_encaisse(premier_du_mois, aujourdhui)),
        'encaisse_mois_precedent': str(
            _encaisse(premier_mois_precedent, fin_mois_precedent)),
        'total_du': str(total_du),
        'nb_impayees': nb_impayees,
        'total_en_retard': str(total_en_retard),
        'nb_en_retard': nb_en_retard,
        'total_a_echoir_7j': str(total_a_echoir_7j),
    }
