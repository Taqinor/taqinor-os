"""AIC — vues de LECTURE servies à l'assistant (actions ``crm.*`` du registre).

Ces routes sont internes : elles n'ont d'autre consommateur que le relais
FastAPI de l'assistant (JWT de l'utilisateur relayé, permission et société
re-vérifiées ICI). Aucune n'écrit, aucune n'envoie : elles LISENT ce que les
écrans lisent déjà (``selectors``), sans recopier leurs règles.

Fichier à part car ``apps/crm/views.py`` appartient au propriétaire crm
(fichier-dieu en découpe SPL).
"""
import datetime
import re

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes)
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import (
    HasPermissionOrLegacy, IsResponsableOrAdmin)
from core.parseurs import PARSEURS_JSON, ChoixDocumente, corps_valide

from . import schema_docs as sd
from . import stages

#: Plafond de lignes servies à l'assistant (le total, lui, est complet).
LIMITE_LIGNES = 20

#: ``portee`` de l'assistant -> ``scope`` de la file du cockpit
#: (``selectors.relance_etapes_dues``). Une seule file, jamais une copie.
_PORTEES = {'aujourd_hui': 'today', 'retard': 'overdue', 'semaine': 'week'}


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
    from .controle_suivi import jours_de_retard_par_etape

    retards = jours_de_retard_par_etape(etapes, company, today)
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
            # COP-C2 — de quoi enchaîner : la touche elle-même (jamais
            # `etape`, qui est l'étape du FUNNEL du lead).
            'touche_id': etape.pk,
            'touche_cle': etape.template_cle or '',
            'cadence': etape.cadence,
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
        'id': d['id'], 'reference': d['numero'], 'statut': d['statut'],
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


def prochaines_touches(company, lead_ids):
    """``{lead_id: RelanceEtape}`` — la prochaine touche À FAIRE de chaque
    lead demandé, en UNE requête (``DISTINCT ON`` du premier rang du tri de
    ``cadence_selectors.prochaine_touche_par_lead``, qui ne rend pas
    l'identifiant). Un lead sans touche ouverte est ABSENT."""
    from django.db.models import F

    from .models import RelanceEtape

    if not lead_ids:
        return {}
    lignes = (RelanceEtape.objects
              .filter(company=company, lead_id__in=list(lead_ids),
                      statut=RelanceEtape.Statut.A_FAIRE)
              .order_by('lead_id', F('due_at').asc(nulls_last=True),
                        'due_date', 'ordre')
              .distinct('lead_id'))
    return {etape.lead_id: etape for etape in lignes}


def _bloc_prochaine_touche(lead):
    etape = prochaines_touches(lead.company, [lead.pk]).get(lead.pk)
    if etape is None:
        return None
    return {
        'touche_id': etape.pk,
        'libelle': etape.libelle or '',
        'due_at': etape.due_at.isoformat() if etape.due_at else None,
        'due_date': etape.due_date.isoformat() if etape.due_date else None,
        'cadence': etape.cadence, 'canal': etape.canal,
    }


def _alertes_lead(lead, devis, touche, today):
    alertes = []
    if any(d['statut'] == 'expire' for d in devis):
        alertes.append('devis_expire')
    # ALEA59 : règle unique du retard (même borne que badge, cockpit, filtres).
    from .controle_suivi import seuil_retard
    seuil = seuil_retard(lead.company, today)
    due = touche and touche['due_date']
    if (due and datetime.date.fromisoformat(str(due)[:10]) < seuil) or (
            lead.relance_date and lead.relance_date < seuil):
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


#: Objectifs du brouillon de suivi -> mot-clé du modèle société à reprendre
#: (recherché dans le NOM du modèle). COP-C7 : AUCUNE phrase de repli — sans
#: modèle société, le texte reste vide (le Guide interdit « avez-vous pu le
#: consulter ? » : la commerciale écrit elle-même, le lien ouvre la
#: conversation nue).
_OBJECTIFS_BROUILLON = {
    'relance_devis': 'devis',
    'apres_visite': 'visite',
    'reveil_froid': 'réveil',
}
_CANAUX_BROUILLON = ('whatsapp', 'sms', 'email')
#: Longueur maximale d'un brouillon WhatsApp.
LONGUEUR_WHATSAPP = 500

_CORPS_BROUILLON = sd.corps(
    'CrmAssistantBrouillonSuiviRequest',
    canal=ChoixDocumente(_CANAUX_BROUILLON),
    langue=ChoixDocumente(['fr', 'ar'], required=False),
    objectif=ChoixDocumente(sorted(_OBJECTIFS_BROUILLON)),
)


def _modele_societe(company, objectif, langue):
    """Le modèle société (non archivé) de l'objectif, dans la langue demandée
    (``ar`` = darija) ; ``(modèle, langue servie)``. Sans modèle dans la
    langue, repli français ; sans modèle du tout, ``(None, 'fr')``."""
    from .models_cadence import MessageTemplate

    mot = _OBJECTIFS_BROUILLON[objectif]
    base = MessageTemplate.objects.filter(
        company=company, archived=False, nom__icontains=mot)
    if langue == 'ar':
        modele = base.filter(langue=MessageTemplate.Langue.DARIJA).first()
        if modele is not None:
            return modele, 'ar'
    return base.filter(langue=MessageTemplate.Langue.FR).first(), 'fr'


def _tronquer(texte, limite):
    """Coupe à ``limite`` caractères sur une frontière de mot."""
    if len(texte) <= limite:
        return texte
    return texte[:limite].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'


@extend_schema(request=_CORPS_BROUILLON, responses=sd.OBJ)
@api_view(['POST'])
@parser_classes(PARSEURS_JSON)
@permission_classes([HasPermissionOrLegacy('crm_modifier')])
def lead_brouillon_suivi(request, lead_id):
    """AIC32 — ``POST /api/django/crm/leads/<id>/brouillon-suivi/`` : un TEXTE
    de suivi à relire puis copier ou ouvrir par ``wa.me`` — l'assistant
    n'envoie JAMAIS. Le modèle société prime ; l'expéditeur est le
    responsable du lead (aucun prénom codé en dur) ; rien n'est écrit.
    ACVI110 — règle MRY13 des touches : seules les valeurs non vides sont
    remplacées, toute phrase qui garde un placeholder est omise (jamais un
    « { » ni « je suis  de »). COP-C7 — sans modèle société AUCUNE phrase de
    repli n'est écrite (le Guide interdit « avez-vous pu le consulter ? ») :
    ``texte`` vaut ``""`` et le lien ouvre la conversation nue. ``wa_url`` est
    la clé lue par la carte ; ``lien_wa_me`` (même valeur) reste servi."""
    from apps.ventes import selectors as ventes
    from apps.ventes.utils.whatsapp import build_wa_url

    from . import cadence_messages as cm
    from .serializers import pii_masquee_pour

    donnees = corps_valide(request, _CORPS_BROUILLON)
    lead = _lead_en_portee_ou_404(request.user, lead_id)
    cm.garde_contact_du_lead(lead)  # ACVI103 (D-ACVI-7) — opposé/perdu/archivé : 409
    objectif, canal = donnees['objectif'], donnees['canal']
    modele, langue_servie = _modele_societe(
        lead.company, objectif, donnees.get('langue') or 'fr')
    civilite, prenom = cm._civilite_et_prenom(lead, 'fr')
    salut = f'{civilite} {prenom}'.strip()
    conseiller = cm._nom_affiche_conseiller(lead, request.user)
    marque = cm._nom_affiche_marque(lead)
    devis = ventes.dernier_devis_envoye_par_lead(
        lead.company, [lead.pk]).get(lead.pk)
    validite = cm._date_validite_comme_le_pdf(devis)
    valeurs = {'prenom': salut, 'ville': lead.ville or '', 'conseiller': conseiller,
               'marque': marque, 'civilite': civilite, 'societe': cm._societe_du_lead(lead),
               'reference': devis.reference if devis else '',
               'date_validite': validite.strftime('%d/%m/%Y') if validite else ''}
    texte = (modele.corps or '') if modele is not None else ''
    for cle, valeur in valeurs.items():
        texte = texte.replace('{' + cle + '}', valeur) if valeur.strip() else texte
    texte = cm._omettre_phrases_incompletes(texte, sorted(set(re.findall(r'\{(\w+)\}', texte))))
    if canal == 'whatsapp':
        texte = _tronquer(texte, LONGUEUR_WHATSAPP)
    telephone = '' if pii_masquee_pour(request.user) else cm.numero_joignable(lead)  # ACVI50
    lien = (build_wa_url(telephone, texte)
            if canal == 'whatsapp' and telephone else None)
    if lien and not texte:
        lien = lien.split('?text=')[0]  # conversation nue, sans texte pré-rempli
    return Response({
        # COP-C7 — `wa_url` est la clé lue par la carte ; `lien_wa_me` (même
        # valeur) reste servi pour un écran resté en cache.
        'texte': texte, 'wa_url': lien, 'lien_wa_me': lien,
        'modele_source': modele.nom if modele else None,
        'langue_servie': langue_servie,
    })


#: Lignes servies par bloc du digest du matin.
LIMITE_DIGEST = 10
#: « Sans réponse » : devis envoyé depuis plus de 7 jours (règle de la tâche).
SEUIL_SANS_REPONSE_JOURS = 7


def _bloc_devis_sans_reponse(user, maintenant):
    """Devis ENVOYÉS (statut ``envoye``, jamais un accepté/refusé/expiré)
    depuis plus de ``SEUIL_SANS_REPONSE_JOURS`` jours, sur les leads visibles
    de ``user`` — lus par ``ventes.selectors.devis_envoyes_en_attente``."""
    from apps.ventes import selectors as ventes

    from .models import Lead
    from .portee_selectors import leads_visibles

    limite = maintenant - datetime.timedelta(days=SEUIL_SANS_REPONSE_JOURS)
    visibles = set(leads_visibles(user, user.company).values_list(
        'id', flat=True))
    devis = [d for d in ventes.devis_envoyes_en_attente(user.company)
             if d.lead_id in visibles and d.date_envoi <= limite]
    noms = dict(Lead.objects.filter(
        pk__in={d.lead_id for d in devis}).values_list('id', 'nom'))
    return {
        'total': len(devis),
        'lignes': [{
            'devis_id': d.pk, 'reference': d.reference, 'lead_id': d.lead_id,
            'nom': noms.get(d.lead_id, ''),
            'envoye_le': d.date_envoi.isoformat(),
            'jours_sans_reponse': (maintenant - d.date_envoi).days,
        } for d in devis[:LIMITE_DIGEST]],
    }


def _bloc_visites_du_jour(user, today):
    from apps.visites import selectors as visites

    journee = visites.ma_journee_du_commercial(
        user.company, user, aujourdhui=today)
    return {
        'total': len(journee['visites']),
        'en_retard': journee['en_retard_count'],
        'lignes': journee['visites'][:LIMITE_DIGEST],
    }


@extend_schema(responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('visites_voir')])
def digest_matin(request):
    """AIC35 — ``GET /api/django/crm/assistant/digest-matin/`` : « mon matin »
    en blocs bornés (10 lignes + total), au MÊME compte que les écrans source
    — la file du cockpit (``lignes_a_relancer``, AIC30), l'agenda des visites
    (``visites.selectors``) et les devis envoyés (``ventes.selectors``). Un
    rôle sans CRM (commercial terrain) ne reçoit que ses visites."""
    from django.utils import timezone

    from core.dates import aujourd_hui_local
    from core.permissions import _user_has_or_legacy

    from apps.agent import selectors as agent

    user = request.user
    aujourdhui = aujourd_hui_local()
    reponse = {'visites': _bloc_visites_du_jour(user, aujourdhui)}
    if _user_has_or_legacy(user, 'crm_voir'):
        total, lignes = lignes_a_relancer(user, 'all', LIMITE_DIGEST)
        reponse['relances'] = {'total': total, 'lignes': lignes}
        reponse['devis_sans_reponse'] = _bloc_devis_sans_reponse(
            user, timezone.now())
        reponse['manques_signales_hier'] = {
            'total': agent.manques_signales_hier(
                user.company, user, aujourdhui)}
    return Response(reponse)


# ── COP-C1 — retrouver un lead (« le lead de Bouskoura », « retrouve Alami ») ──

#: ``?limite=`` : 10 lignes par défaut, 25 au plus.
LIMITE_RECHERCHE = 10
LIMITE_RECHERCHE_MAX = 25


def _leads_trouves(request, terme, etape):
    """Les leads de la PORTÉE de l'appelant (société + visibilité de son rôle,
    comme la liste) filtrés par la recherche de ``LeadViewSet`` (mêmes
    ``search_fields``, jamais une troisième recherche) et par étape. Sans
    ``client_pii_voir``, ni le téléphone ni l'e-mail ne servent de critère
    (la recherche ne devient pas un oracle du numéro masqué)."""
    from rest_framework.filters import SearchFilter

    from .portee_selectors import leads_visibles
    from .serializers import pii_masquee_pour
    from .views import LeadViewSet

    leads = leads_visibles(request.user, request.user.company)
    if etape:
        leads = leads.filter(stage=etape)
    if terme:
        masque = pii_masquee_pour(request.user)
        champs = [c for c in LeadViewSet.search_fields
                  if not (masque and c in ('telephone', 'email'))]
        filtre = SearchFilter()
        filtre.search_param = 'q'
        leads = filtre.filter_queryset(
            request, leads, type('VueRecherche', (), {'search_fields': champs}))
    return leads.select_related('owner').order_by('-date_creation', 'id')


def _ligne_lead(lead, touche, masque):
    from .serializers import nom_affichable_responsable

    return {
        'lead_id': lead.pk,
        'nom': (f'{lead.prenom or ""} {lead.nom}').strip(),
        'societe': lead.societe or '', 'ville': lead.ville or '',
        'telephone': '' if masque else (lead.telephone or ''),
        'etape': lead.stage,
        'etape_libelle': stages.STAGE_LABELS.get(lead.stage, lead.stage),
        'responsable': nom_affichable_responsable(lead.owner) or '',
        'cree_le': lead.date_creation.isoformat() if lead.date_creation else None,
        'prochaine_touche': None if touche is None else {
            'touche_id': touche.pk, 'libelle': touche.libelle or '',
            'canal': touche.canal,
            'prevue_le': (touche.due_date.isoformat()
                          if touche.due_date else None)},
    }


@extend_schema(
    parameters=[
        sd.param('q', description=(
            'Nom, prénom, société, e-mail, téléphone, ville ou référence '
            'client (comme la liste des leads).')),
        sd.param('etape', enum=list(stages.STAGES),
                 description='Étape du funnel (clé de STAGES.py).'),
        sd.param('limite', OpenApiTypes.INT,
                 description='10 par défaut, 25 au plus.')],
    responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('crm_voir')])
def leads_recherche(request):
    """COP-C1 — ``GET /api/django/crm/assistant/leads/?q=&etape=&limite=`` :
    recherche COMPACTE de leads dans la portée de l'utilisateur (contrat
    ``assistant_leads_recherche.json``) — chaque ligne porte ``lead_id`` et,
    quand une touche est ouverte, ``prochaine_touche.touche_id`` (UNE requête
    pour toutes les lignes). Aucune fiche complète, aucun prix d'achat."""
    from .params_requete import entier_param
    from .serializers import pii_masquee_pour

    terme = (request.query_params.get('q') or '').strip()
    etape = (request.query_params.get('etape') or '').strip()
    if etape and etape not in stages.STAGES:
        raise ValidationError({'etape': (
            'Valeur inconnue : « %s ». Valeurs : %s.'
            % (etape, ', '.join(stages.STAGES)))})
    limite = entier_param(request, 'limite', LIMITE_RECHERCHE, mini=1,
                          maxi=LIMITE_RECHERCHE_MAX, tolerant=True)
    leads = _leads_trouves(request, terme, etape)
    total = leads.count()
    page = list(leads[:limite])
    touches = prochaines_touches(request.user.company, [x.pk for x in page])
    masque = pii_masquee_pour(request.user)
    return Response({
        'q': terme, 'etape': etape, 'total': total, 'limite': limite,
        'lignes': [_ligne_lead(x, touches.get(x.pk), masque) for x in page],
    })


# ── COP-C7 — l'aperçu WhatsApp d'un devis, avec de quoi appeler le commit ──

@extend_schema(request=sd.corps(
    'CrmAssistantWhatsappApercuRequest',
    devis_ids=sd.ids_requis(),
    langue=ChoixDocumente(['fr', 'darija', 'ar'], required=False)),
    responses=sd.OBJ)
@api_view(['POST'])
@parser_classes(PARSEURS_JSON)
@permission_classes([IsResponsableOrAdmin, HasPermissionOrLegacy('crm_modifier')])
def lead_whatsapp_devis_apercu(request, lead_id):
    """COP-C7 — ``POST /api/django/crm/assistant/leads/<id>/whatsapp-devis-
    apercu/`` : l'APERÇU de l'écran (``whatsapp-devis-apercu``, mêmes gardes,
    même message, SANS EFFET) plus ``lead_id`` et ``devis_ids`` — la carte
    « wa_devis » s'en sert pour appeler le COMMIT ``whatsapp-devis`` au moment
    où elle ouvre WhatsApp (sans lui, le devis reste brouillon et le suivi ne
    démarre jamais). Ne change pas la route de l'écran."""
    from apps.ventes.utils.whatsapp import build_wa_url

    from .devis_views import (
        LeadDevisActionsMixin, _refus_pii_whatsapp, _refuser_si_oppose)

    refus = _refus_pii_whatsapp(request)
    if refus is not None:
        return refus
    lead = _lead_en_portee_ou_404(request.user, lead_id)
    _refuser_si_oppose(lead)
    erreur, construit = LeadDevisActionsMixin()._whatsapp_devis_message(
        request, lead, enregistrer=False)
    if erreur is not None:
        return erreur
    devis, phone, message, links = construit
    return Response({
        'wa_url': build_wa_url(phone, message), 'phone': phone,
        'message': message, 'links': links,
        'lead_id': lead.pk, 'devis_ids': [d.pk for d in devis],
    })


# ── COP-C6 — le message de visite, forme de la carte « wa_message » ─────────

@extend_schema(
    parameters=[
        sd.param('cle', required=True,
                 enum=['visite_proposition', 'visite_confirmation',
                       'visite_releve_point_eau'],
                 description='Clé du message de visite.'),
        sd.param('langue', enum=['fr', 'darija'],
                 description='Langue du texte (défaut : celle du lead).')],
    responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('crm_voir')])
def lead_message_visite(request, lead_id):
    """COP-C6 — ``GET /api/django/crm/assistant/leads/<id>/message-visite/
    ?cle=&langue=`` : le message de visite VALIDÉ (même rendu que
    ``leads/<id>/message-visite/``) mis à la forme de la carte « wa_message »
    — ``texte`` et ``wa_url`` — pour UNE langue. Rien n'est écrit ni envoyé
    (la route de l'écran, elle, rend les deux langues à la fois)."""
    from .cadence_messages import (
        cles_message_visite_du_lead, garde_contact_du_lead,
        langue_relance_du_lead, message_visite_pour_lead,
        refus_langue_relance)
    from .serializers import pii_masquee_pour

    lead = _lead_en_portee_ou_404(request.user, lead_id)
    cle = (request.query_params.get('cle') or '').strip()
    langue = (request.query_params.get('langue') or '').strip()
    langue = langue or langue_relance_du_lead(lead)
    if refus_langue_relance(langue):
        raise ValidationError({'langue': refus_langue_relance(langue)})
    garde_contact_du_lead(lead)
    rendu = message_visite_pour_lead(
        lead, cle, user=request.user,
        masquer_numero=pii_masquee_pour(request.user))
    if rendu is None:
        raise ValidationError({'cle': (
            'Message de visite inconnu « %s ». Clés : %s.'
            % (cle, ', '.join(cles_message_visite_du_lead(lead))))})
    suffixe = 'darija' if langue == 'darija' else 'fr'
    return Response({
        'texte': rendu['corps_' + suffixe], 'wa_url': rendu['wa_url_' + suffixe],
        'lien_wa_me': rendu['wa_url_' + suffixe],
        'modele_source': cle, 'langue_servie': suffixe,
    })
