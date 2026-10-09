"""NTCRM16 — Score d'engagement multi-signaux d'un CLIENT (fidélisation/
upsell).

CAD140 (audit L3 du 21/09/2026, round 2 ; LIVRÉ le 23/09/2026) — le module
avait ABANDONNÉ à sa création le seul signal réellement COMPORTEMENTAL qu'il
devait porter (l'ouverture de PDF/ShareLink), faute d'un sélecteur PAR CLIENT
côté `apps.ventes` (hors périmètre de la lane `crm` qui l'a créé — voir
CLAUDE.md frontière cross-app) : son poids était redistribué sur les quatre
signaux administratifs ci-dessous (25 pts chacun plutôt que 20). Ce
sélecteur existe désormais (`apps.ventes.selectors.devis_ouverts_ratio_
client`, CAD140/CAD137) : le signal est RÉINTÉGRÉ, à son poids d'origine
(20 pts, la part symétrique des 5 signaux sur 100 — jamais un poids inventé,
voir git 67b2644f pour la redistribution qu'il inverse).

Distinct du lead-scoring existant (`scoring.py`, qui porte sur les LEADS en
phase de conversion) : ce module porte sur les `Client` déjà signés, pour
détecter qui mérite une action de fidélisation/upsell avant de dormir
(NTCRM14). Même taxonomie de labels que le lead-scoring (Chaud/Tiède/Froid)
pour rester cohérent côté UX.

Pur et stateless : aucune écriture, aucun état partagé entre appels. Signaux
utilisés (20 pts chacun, total 0-100) :

  ouverture_propositions
                       ratio de devis (hors brouillon) OUVERTS au moins une
                       fois par le client (`ShareLink.view_count`, compteur
                       de visites DISTINCTES fiabilisé par CAD137) — LE
                       signal comportemental (`apps.ventes.selectors.
                       devis_ouverts_ratio_client`, jamais `apps.ventes.
                       models`).
  fréquence_contact   `crm.PointContact` récents (90 derniers jours) sur les
                       leads liés au client — signal crm natif.
  activite_recente     dernier `LeadActivity`/`PointContact` sur un lead lié —
                       recency, même esprit que `scoring._recency_score`.
  paiements_a_temps    ratio de factures PAYÉES parmi les factures émises
                       (proxy — `apps.ventes.selectors.factures_du_client_
                       portail`, jamais `apps.ventes.models`).
  ratio_devis_acceptes ratio de devis ACCEPTÉS parmi les devis envoyés
                       (`apps.ventes.selectors.devis_du_client_portail`).

APRF22 — ces cinq signaux sont lus EN LOT (``engagement_pour_clients`` :
quatre requêtes ``GROUP BY client`` par société, relations inverses en
chaînes, mêmes populations que les sélecteurs cités ci-dessus) ; le calcul
unitaire de la fiche client passe par la même fonction.
"""
from __future__ import annotations

from django.utils import timezone

_W_OUVERTURE = 20
_W_CONTACT = 20
_W_RECENCE = 20
_W_PAIEMENTS = 20
_W_DEVIS_ACCEPTES = 20

RECENCE_FENETRE_JOURS = 90
CONTACT_FENETRE_JOURS = 90


# APRF22 — statuts de DOCUMENT lus (couche séparée du funnel STAGES.py, règle
# #4) : mêmes valeurs que les sélecteurs ventes d'origine
# (``devis_ouverts_ratio_client``, ``devis_du_client_portail``,
# ``factures_du_client_portail``), lues par relations inverses en chaînes —
# jamais un import de ``apps.ventes.models``.
_STATUT_BROUILLON = 'brouillon'
_STATUT_DEVIS_ACCEPTE = 'accepte'
_STATUT_FACTURE_PAYEE = 'payee'


def _signaux_pour_clients(company_id, client_ids, now):
    """APRF22 — les cinq signaux bruts de TOUS ``client_ids`` (même société)
    en QUATRE requêtes ``GROUP BY client`` (devis, factures, points de
    contact, activités), quel que soit le nombre de clients.

    Mêmes populations que les lectures unitaires d'avant : devis non
    brouillons (ouverture : toutes versions ; ratio accepté : versions
    actives), factures non brouillons, ``PointContact``/``LeadActivity`` des
    leads de la société liés au client. Renvoie ``{client_id: dict}``."""
    from django.db.models import Count, Max, Q

    from .models import Client

    base = Client.objects.filter(pk__in=client_ids).order_by()
    devis_nb = Q(devis__company_id=company_id) & ~Q(
        devis__statut=_STATUT_BROUILLON)
    devis_actif = devis_nb & Q(devis__is_active=True)
    signaux = {pk: {} for pk in client_ids}
    for r in base.values('pk').annotate(
            d_total=Count('devis', filter=devis_nb, distinct=True),
            d_ouverts=Count('devis', filter=devis_nb & Q(
                devis__share_links__view_count__gt=0), distinct=True),
            d_actifs=Count('devis', filter=devis_actif, distinct=True),
            d_acceptes=Count('devis', filter=devis_actif & Q(
                devis__statut=_STATUT_DEVIS_ACCEPTE), distinct=True)):
        signaux[r['pk']].update(r)
    fact_nb = Q(factures__company_id=company_id) & ~Q(
        factures__statut=_STATUT_BROUILLON)
    for r in base.values('pk').annotate(
            f_total=Count('factures', filter=fact_nb, distinct=True),
            f_payees=Count('factures', filter=fact_nb & Q(
                factures__statut=_STATUT_FACTURE_PAYEE), distinct=True)):
        signaux[r['pk']].update(r)
    seuil = now - timezone.timedelta(days=CONTACT_FENETRE_JOURS)
    leads_soc = Q(leads__company_id=company_id)
    for r in base.values('pk').annotate(
            c_recents=Count('leads__points_contact', filter=leads_soc & Q(
                leads__points_contact__date_contact__gte=seuil),
                distinct=True),
            c_dernier=Max('leads__points_contact__date_contact',
                          filter=leads_soc)):
        signaux[r['pk']].update(r)
    for r in base.values('pk').annotate(
            a_derniere=Max('leads__activites__created_at',
                           filter=leads_soc)):
        signaux[r['pk']].update(r)
    return signaux


def _score_depuis_signaux(sig, now):
    """APRF22 — LA formule (5 × 20 pts), appliquée aux signaux bruts d'un
    client — unique pour la fiche (unitaire) et les listes (en lot)."""
    score = 0
    # ouverture_propositions — aucun devis non brouillon = 0 (neutre).
    if sig.get('d_total'):
        score += round(_W_OUVERTURE * sig['d_ouverts'] / sig['d_total'])
    # fréquence_contact — 3+ contacts sur la fenêtre = score plein.
    score += min(_W_CONTACT, (sig.get('c_recents') or 0) * (_W_CONTACT // 3 or 1))
    # activite_recente — dégressif linéaire sur RECENCE_FENETRE_JOURS.
    dates = [d for d in (sig.get('a_derniere'), sig.get('c_dernier')) if d]
    if dates:
        age_jours = (now - max(dates)).days
        if age_jours <= 0:
            score += _W_RECENCE
        elif age_jours < RECENCE_FENETRE_JOURS:
            score += round(_W_RECENCE * (1 - age_jours / RECENCE_FENETRE_JOURS))
    # paiements_a_temps — aucune facture émise = 0 (neutre).
    if sig.get('f_total'):
        score += round(_W_PAIEMENTS * sig['f_payees'] / sig['f_total'])
    # ratio_devis_acceptes — aucun devis envoyé = 0 (neutre).
    if sig.get('d_actifs'):
        score += round(_W_DEVIS_ACCEPTES * sig['d_acceptes'] / sig['d_actifs'])
    return min(score, 100)


def engagement_pour_clients(clients, now=None) -> dict:
    """APRF22 — score d'engagement de TOUS ``clients`` en quelques requêtes
    ``GROUP BY client`` (quatre par société), jamais une série par client.
    Renvoie ``{client_id: score}``."""
    now = now or timezone.now()
    par_societe = {}
    for client in clients:
        par_societe.setdefault(client.company_id, []).append(client.pk)
    scores = {}
    for company_id, ids in par_societe.items():
        for pk, sig in _signaux_pour_clients(company_id, ids, now).items():
            scores[pk] = _score_depuis_signaux(sig, now)
    return scores


def compute_engagement_score(client, now=None) -> int:
    """Calcule le score d'engagement (entier 0-100) d'un `Client`. Pur —
    aucune écriture. `now` injectable pour des tests déterministes.
    APRF22 — même logique que le calcul en lot (``engagement_pour_clients``)."""
    now = now or timezone.now()
    return engagement_pour_clients([client], now=now).get(client.pk, 0)


def engagement_label(score: int) -> str:
    """Libellé FR — même taxonomie/seuils que `scoring.score_label`."""
    if score >= 70:
        return 'Chaud'
    if score >= 45:
        return 'Tiède'
    return 'Froid'


def engagement_for_client(client, now=None) -> dict:
    """Résultat complet pour UN client — consommé par l'endpoint détail."""
    score = compute_engagement_score(client, now=now)
    return {
        'client_id': client.id,
        'score': score,
        'label': engagement_label(score),
    }


def engagement_bulk(clients, now=None) -> list[dict]:
    """Résultat pour une liste de clients — consommé par `engagement-bulk/`."""
    now = now or timezone.now()
    clients = list(clients)
    # APRF22 — tous les scores en lot, puis la même forme qu'avant.
    scores = engagement_pour_clients(clients, now=now)
    out = []
    for c in clients:
        score = scores.get(c.pk, 0)
        out.append({'client_id': c.id, 'score': score,
                    'label': engagement_label(score)})
    return out
