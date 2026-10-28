"""AIC — vues de LECTURE servies à l'assistant (actions ``crm.*`` du registre).

Ces routes sont internes : elles n'ont d'autre consommateur que le relais
FastAPI de l'assistant (JWT de l'utilisateur relayé, permission et société
re-vérifiées ICI). Aucune n'écrit, aucune n'envoie : elles LISENT ce que les
écrans lisent déjà (``selectors``), sans recopier leurs règles.

Fichier à part car ``apps/crm/views.py`` appartient au propriétaire crm
(fichier-dieu en découpe SPL).
"""
import datetime

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy

from . import schema_docs as sd

#: Plafond de lignes servies à l'assistant (le total, lui, est complet).
LIMITE_LIGNES = 20

#: ``portee`` de l'assistant -> ``scope`` de la file du cockpit
#: (``selectors.relance_etapes_dues``). Une seule file, jamais une copie.
_PORTEES = {'aujourd_hui': 'today', 'retard': 'overdue', 'semaine': 'week'}


def _jours_de_retard(etapes, company, today):
    """``{id d'étape: jours de retard COMPTÉS}`` — LA règle du cockpit
    (``controle_suivi._jours_comptes`` : jours ouvrés de la société, hors
    absence déclarée du responsable), jamais une seconde définition."""
    from apps.notifications.calendar_utils import jours_ouvres_entre

    from . import cadence_absence
    from .controle_suivi import _jours_comptes

    en_retard = [e for e in etapes if e.due_date and e.due_date < today]
    if not en_retard:
        return {}
    debut = min(e.due_date for e in en_retard) + datetime.timedelta(days=1)
    ouvres = jours_ouvres_entre(company, debut, today)
    absences = cadence_absence.couverture(company, debut, today)
    return {
        e.pk: _jours_comptes(e.due_date, today, e.lead.owner_id,
                             ouvres, absences)
        for e in en_retard
    }


def _derniers_contacts(company, lead_ids):
    """``{lead_id: dernier instant de touche traitée}`` — UNE requête."""
    from django.db.models import Max

    from .models import RelanceEtape

    lignes = (RelanceEtape.objects
              .filter(company=company, lead_id__in=list(lead_ids),
                      statut=RelanceEtape.Statut.FAIT)
              .values('lead_id').annotate(dernier=Max('traite_le')))
    return {ligne['lead_id']: ligne['dernier'] for ligne in lignes}


def lignes_a_relancer(user, scope, limite=LIMITE_LIGNES):
    """``(total, lignes)`` de la file du cockpit de ``user`` pour ``scope`` —
    exactement ``selectors.relance_etapes_dues`` (même compte, même ordre),
    bornée à ``limite`` lignes. Partagée avec le digest du matin."""
    from core.dates import aujourd_hui_local

    from .selectors import relance_etapes_dues

    company = user.company
    today = aujourd_hui_local()
    qs = relance_etapes_dues(company, user, scope=scope, today=today)
    total = qs.count()
    etapes = list(qs[:limite])
    retards = _jours_de_retard(etapes, company, today)
    contacts = _derniers_contacts(company, {e.lead_id for e in etapes})
    lignes = []
    for etape in etapes:
        lead = etape.lead
        dernier = contacts.get(lead.pk) or lead.first_contacted_at
        lignes.append({
            'lead_id': lead.pk,
            'nom': (f'{lead.prenom or ""} {lead.nom}').strip(),
            'etape': lead.stage,
            'touche': etape.libelle or '',
            'touche_prevue': (etape.due_date.isoformat()
                              if etape.due_date else None),
            'retard_jours_ouvres': retards.get(etape.pk, 0),
            'canal': etape.canal,
            'dernier_contact': dernier.isoformat() if dernier else None,
        })
    return total, lignes


@extend_schema(
    parameters=[sd.param_enum_ou_vide(
        'portee', sorted(_PORTEES),
        'aujourd_hui (défaut) | retard | semaine.')],
    responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('crm_voir')])
def leads_a_relancer(request):
    """AIC30 — ``GET /api/django/crm/assistant/a-relancer/`` : « mes leads à
    relancer » = la file du cockpit « contrôle du suivi » de l'utilisateur
    connecté (jamais une copie de la règle de retard), bornée à
    ``LIMITE_LIGNES`` avec le total. ``?portee=aujourd_hui|retard|semaine``."""
    portee = (request.query_params.get('portee') or 'aujourd_hui').strip()
    if portee not in _PORTEES:
        raise ValidationError({'portee': (
            'Valeur inconnue : « %s ». Valeurs : %s.'
            % (portee, ', '.join(sorted(_PORTEES))))})
    total, lignes = lignes_a_relancer(request.user, _PORTEES[portee])
    return Response({
        'portee': portee, 'total': total, 'limite': LIMITE_LIGNES,
        'lignes': lignes,
    })


def _lead_en_portee_ou_404(user, lead_id):
    """Le lead de ``user`` (société + portée) ou 404 — un lead d'une autre
    société (ou hors portée) est traité comme ABSENT."""
    from django.http import Http404

    from .portee_selectors import leads_en_portee

    lead = leads_en_portee(user).filter(pk=lead_id).first()
    if lead is None:
        raise Http404
    return lead


def _bloc_chatter(lead, n=5):
    from .models import LeadActivity

    return [{
        'type': a.kind,
        'champ': a.field_label or a.field or '',
        'texte': (a.body or '')[:300],
        'le': a.created_at.isoformat(),
    } for a in LeadActivity.objects.filter(
        lead=lead, company=lead.company).order_by('-created_at', '-id')[:n]]


def _bloc_devis(lead):
    """Devis du lead lus chez ``ventes`` (``devis_lecture_seule_pour_lead`` :
    jamais de ``prix_achat`` ni de marge), sans les lignes."""
    from apps.ventes import selectors as ventes

    envoye = ventes.dernier_devis_envoye_par_lead(
        lead.company, [lead.pk]).get(lead.pk)
    return [{
        'reference': d['numero'], 'statut': d['statut'],
        'total_ttc': d['total_ttc'],
        'envoye_le': (envoye.date_envoi.isoformat()
                      if envoye and envoye.reference == d['numero']
                      else None),
    } for d in ventes.devis_lecture_seule_pour_lead(lead)]


def _bloc_visites(lead, n=3):
    from apps.visites import selectors as visites

    return [{
        'date': v['date_realisee'] or v['date_prevue'],
        'resultat': v['statut_libelle'],
    } for v in visites.visites_pour_lead(lead)[:n]]


def _bloc_prochaine_touche(lead):
    from .selectors import prochaine_touche_par_lead

    touche = prochaine_touche_par_lead(lead.company, [lead.pk]).get(lead.pk)
    if touche is None:
        return None
    due_at, due_date, cadence, canal = touche
    return {
        'due_at': due_at.isoformat() if due_at else None,
        'due_date': due_date.isoformat() if due_date else None,
        'cadence': cadence, 'canal': canal,
    }


def _alertes_lead(lead, devis, touche, today):
    alertes = []
    if any(d['statut'] == 'expire' for d in devis):
        alertes.append('devis_expire')
    due = touche and touche['due_date']
    if (due and due < today.isoformat()) or (
            lead.relance_date and lead.relance_date < today):
        alertes.append('relance_en_retard')
    return alertes


@extend_schema(responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('crm_voir')])
def lead_resume(request, lead_id):
    """AIC31 — ``GET /api/django/crm/leads/<id>/resume/`` : le lead en un
    objet pour préparer un appel. Chaque bloc est lu chez son propriétaire
    (chatter ici ; devis via ``ventes.selectors`` ; visites via
    ``visites.selectors`` ; touche via ``cadence_selectors``). Aucun
    ``prix_achat``, aucune marge ; lead d'une autre société : 404."""
    from core.dates import aujourd_hui_local

    from .serializers import pii_masquee_pour

    lead = _lead_en_portee_ou_404(request.user, lead_id)
    devis = _bloc_devis(lead)
    touche = _bloc_prochaine_touche(lead)
    return Response({
        'identite': {
            'id': lead.pk, 'nom': lead.nom, 'prenom': lead.prenom or '',
            'societe': lead.societe or '', 'ville': lead.ville or '',
            'telephone': ('' if pii_masquee_pour(request.user)
                          else lead.telephone or ''),
        },
        'etape': lead.stage,
        'contact_prefere': lead.contact_preference or '',
        'chatter': _bloc_chatter(lead),
        'devis': devis,
        'visites': _bloc_visites(lead),
        'prochaine_touche': touche,
        'alertes': _alertes_lead(lead, devis, touche, aujourd_hui_local()),
    })
