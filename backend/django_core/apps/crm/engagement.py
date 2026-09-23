"""NTCRM16 — Score d'ACTIVITÉ COMMERCIALE multi-signaux d'un CLIENT
(fidélisation/upsell).

CAD140 (audit L3 du 21/09/2026, round 2) — RENOMMÉ EN TÊTE (23/09/2026) : ce
module s'appelait « score d'engagement » alors qu'il a ABANDONNÉ le seul
signal réellement COMPORTEMENTAL qu'il devait porter (l'ouverture de PDF/
ShareLink) et ne mesure plus, en pratique, que quatre signaux
ADMINISTRATIFS (fréquence de contact, récence, paiements à temps, taux
d'acceptation) — une vraie mesure d'activité commerciale, pas d'engagement
client. Les NOMS PUBLICS (`compute_engagement_score`, `engagement_label`,
`engagement_for_client`, `engagement_bulk`) ne sont PAS renommés ici : ils
sont consommés depuis `apps/crm/views.py`, hors du périmètre de cette lane
(fichier possédé par une autre lane du même run — voir la garde de lane) ;
un renommage de l'API publique attend une lane qui peut toucher `views.py`
dans le MÊME commit.

Distinct du lead-scoring existant (`scoring.py`, qui porte sur les LEADS en
phase de conversion) : ce module porte sur les `Client` déjà signés, pour
détecter qui mérite une action de fidélisation/upsell avant de dormir
(NTCRM14). Même taxonomie de labels que le lead-scoring (Chaud/Tiède/Froid)
pour rester cohérent côté UX.

Pur et stateless : aucune écriture, aucun état partagé entre appels. Signaux
utilisés (25 pts chacun, total 0-100) :

  fréquence_contact   `crm.PointContact` récents (90 derniers jours) sur les
                       leads liés au client — signal crm natif.
  activite_recente     dernier `LeadActivity`/`PointContact` sur un lead lié —
                       recency, même esprit que `scoring._recency_score`.
  paiements_a_temps    ratio de factures PAYÉES parmi les factures émises
                       (proxy — `apps.ventes.selectors.factures_du_client_
                       portail`, jamais `apps.ventes.models`).
  ratio_devis_acceptes ratio de devis ACCEPTÉS parmi les devis envoyés
                       (`apps.ventes.selectors.devis_du_client_portail`).

NOTE DE PÉRIMÈTRE (toujours vraie au 23/09/2026 — RECONFIRMÉE, pas seulement
héritée) : reprendre le signal d'ouverture de PDF exigerait un sélecteur
PAR CLIENT côté `apps.ventes` — `apps.ventes.selectors.
devis_view_tracking_segments` existe déjà mais agrège en PANIER de contacts
(email/téléphone), jamais par `client_id`, et `apps.ventes.selectors.
devis_du_client_portail` (déjà lu ci-dessus pour `ratio_devis_acceptes`) ne
porte aucune colonne de consultation. Toute app `apps/ventes/*` est HORS
PÉRIMÈTRE de cette lane (`apps/crm` uniquement — voir CLAUDE.md frontière
cross-app) : son poids reste redistribué sur les 4 signaux ci-dessus plutôt
que de bloquer la tâche. À réintégrer par une lane `ventes` future qui ajoute
ce sélecteur PAR CLIENT (le compteur de consultations visé par CAD140 sera
fiabilisé par CAD137).
"""
from __future__ import annotations

from django.utils import timezone

_W_CONTACT = 25
_W_RECENCE = 25
_W_PAIEMENTS = 25
_W_DEVIS_ACCEPTES = 25

RECENCE_FENETRE_JOURS = 90
CONTACT_FENETRE_JOURS = 90


def _lead_ids_for_client(client):
    from .models import Lead
    return list(Lead.objects.filter(
        company=client.company, client=client).values_list('id', flat=True))


def _frequence_contact_score(client, lead_ids, now):
    """25 pts max — nombre de `PointContact` sur les leads du client dans les
    `CONTACT_FENETRE_JOURS` derniers jours (3+ contacts = score plein)."""
    if not lead_ids:
        return 0
    from .models import PointContact
    seuil = now - timezone.timedelta(days=CONTACT_FENETRE_JOURS)
    n = PointContact.objects.filter(
        lead_id__in=lead_ids, date_contact__gte=seuil).count()
    return min(_W_CONTACT, n * (_W_CONTACT // 3 or 1))


def _activite_recente_score(client, lead_ids, now):
    """25 pts max — âge de la dernière activité (LeadActivity/PointContact)
    sur un lead lié : plus récent = plus de points, dégressif linéaire sur
    `RECENCE_FENETRE_JOURS`."""
    if not lead_ids:
        return 0
    from .models import LeadActivity, PointContact
    dates = []
    last_act = (LeadActivity.objects.filter(lead_id__in=lead_ids)
                .order_by('-created_at').values_list('created_at', flat=True).first())
    if last_act:
        dates.append(last_act)
    last_ct = (PointContact.objects.filter(lead_id__in=lead_ids)
               .order_by('-date_contact').values_list('date_contact', flat=True).first())
    if last_ct:
        dates.append(last_ct)
    if not dates:
        return 0
    derniere = max(dates)
    age_jours = (now - derniere).days
    if age_jours <= 0:
        return _W_RECENCE
    if age_jours >= RECENCE_FENETRE_JOURS:
        return 0
    return round(_W_RECENCE * (1 - age_jours / RECENCE_FENETRE_JOURS))


def _paiements_a_temps_score(company, client):
    """25 pts max — ratio de factures PAYÉES parmi les factures émises
    (proxy « paiements à temps » ; aucune facture émise = score neutre 0,
    jamais une pénalité fantôme pour un client encore sans facture)."""
    from apps.ventes.selectors import factures_du_client_portail
    factures = factures_du_client_portail(company, client.id, limit=200)
    if not factures:
        return 0
    payees = sum(1 for f in factures if f.get('payee'))
    return round(_W_PAIEMENTS * payees / len(factures))


def _ratio_devis_acceptes_score(company, client):
    """25 pts max — ratio de devis ACCEPTÉS parmi les devis envoyés au client."""
    from apps.ventes.selectors import devis_du_client_portail
    devis = devis_du_client_portail(company, client.id, limit=200)
    if not devis:
        return 0
    acceptes = sum(1 for d in devis if d.get('accepte'))
    return round(_W_DEVIS_ACCEPTES * acceptes / len(devis))


def compute_engagement_score(client, now=None) -> int:
    """Calcule le score d'engagement (entier 0-100) d'un `Client`. Pur —
    aucune écriture. `now` injectable pour des tests déterministes."""
    now = now or timezone.now()
    company = client.company
    lead_ids = _lead_ids_for_client(client)
    score = 0
    score += _frequence_contact_score(client, lead_ids, now)
    score += _activite_recente_score(client, lead_ids, now)
    score += _paiements_a_temps_score(company, client)
    score += _ratio_devis_acceptes_score(company, client)
    return min(score, 100)


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
    return [engagement_for_client(c, now=now) for c in clients]
