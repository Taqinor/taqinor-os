"""Cockpit d'équipe du responsable (fondateur, 28/10/2026) — contrat
``contract_samples/cockpit_equipe.json``.

Pour UNE équipe commerciale et UNE période : chaque membre ACTIF sur tous ses
points (objectifs contre réalisé, discipline de suivi, pipeline) et la ligne
d'équipe. Lecture pure. Aucune règle n'est réécrite ici :

* réalisé = ``clients_selectors.compute_attainment`` (le calcul de
  ``crm/objectifs/attainment/`` — jamais deux chiffres) ;
* premier contact = la règle de ``leads/kpi-premier-contact/`` (leads
  ``OS_NATIVE`` non archivés, minutes OUVRÉES, objectif de la société) ;
* relances en retard = ``controle_suivi.seuil_retard`` + ``etape_en_retard``
  (ALEA32, la définition unique) ;
* pipeline = ``clients_selectors._lignes_pipeline_ouvertes`` (étapes de
  STAGES.py) et les devis ``envoye`` en vigueur lus par ``lead.devis`` —
  jamais un import de ``apps.ventes.models``.

Accès : ``dispatch.peut_regler`` (responsable, tête du département,
Direction/Admin). Les mêmes personnes fixent les objectifs des membres de
leurs équipes (``peut_fixer_objectif``).
"""
import calendar
import datetime
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from core.dates import aujourd_hui_local

from . import dispatch, horaires
from .models_clients import AttributionEnAttente, EquipeCommerciale, ObjectifCommercial
from .params_requete import entier_param

Metric = ObjectifCommercial.Metric
PeriodType = ObjectifCommercial.PeriodType

#: Ordre d'affichage des métriques (contrat ``metriques``).
METRIQUES = (Metric.NB_LEADS, Metric.NB_CONTACTS, Metric.NB_RDV,
             Metric.NB_DEVIS, Metric.CA_SIGNE)
MOIS = ('Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
        'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre')
#: Statut ventes d'un devis ouvert (envoyé, en attente de réponse).
STATUT_DEVIS_OUVERT = 'envoye'

VIDE = {'equipes_accessibles': [], 'equipe': None, 'periode': None,
        'metriques': [], 'membres': [], 'equipe_totaux': None}


# ── Accès ────────────────────────────────────────────────────────────────────
def equipes_pilotees(user):
    """Équipes ACTIVES de la société que ``user`` pilote (``peut_regler``),
    par nom."""
    if not getattr(user, 'company_id', None):
        return []
    equipes = (EquipeCommerciale.objects
               .filter(company_id=user.company_id, actif=True)
               .select_related('company', 'departement', 'responsable')
               .order_by('nom', 'id'))
    return [e for e in equipes if dispatch.peut_regler(user, e)]


def peut_fixer_objectif(user, owner_id):
    """Qui écrit un objectif commercial : Direction/Admin toujours ; sinon
    seulement pour un ``owner`` MEMBRE d'une équipe active que ``user`` pilote
    (``peut_regler``). Un objectif sans owner (société/équipe) reste Admin."""
    if getattr(user, 'is_admin_role', False):
        return True
    if owner_id is None or not getattr(user, 'company_id', None):
        return False
    equipes = (EquipeCommerciale.objects
               .filter(company_id=user.company_id, actif=True,
                       membres__id=owner_id)
               .select_related('departement'))
    return any(dispatch.peut_regler(user, e) for e in equipes)


def verifier_objectif(user, *owners):
    """403 si ``user`` ne peut pas écrire l'objectif de CHACUN de ``owners``
    (instances utilisateur ou None)."""
    for owner in owners:
        if not peut_fixer_objectif(user, getattr(owner, 'pk', None)):
            raise PermissionDenied(
                "Seuls la Direction, le directeur commercial et le responsable "
                "de l'équipe fixent les objectifs de ses membres.")


# ── Période ──────────────────────────────────────────────────────────────────
def _borne(request, nom, mini, maxi):
    valeur = entier_param(request, nom)
    if valeur is not None and not mini <= valeur <= maxi:
        raise ValidationError({nom: f'Valeur attendue entre {mini} et {maxi}.'})
    return valeur


def lire_periode(request):
    """``?periode=month|quarter|year`` (month), ``?annee=``, ``?mois=``,
    ``?trimestre=`` — défaut : la période en cours (Casablanca). 400 nommant
    le paramètre invalide."""
    type_ = request.query_params.get('periode') or PeriodType.MONTH
    if type_ not in PeriodType.values:
        raise ValidationError({'periode': [
            f"Valeur « {type_} » invalide : attendu "
            f"{', '.join(PeriodType.values)}."]})
    annee = _borne(request, 'annee', 2000, 2100)
    mois = _borne(request, 'mois', 1, 12)
    trimestre = _borne(request, 'trimestre', 1, 4)
    today = aujourd_hui_local()
    annee = annee or today.year
    if type_ == PeriodType.MONTH:
        mois = mois or today.month
        debut = datetime.date(annee, mois, 1)
        fin = datetime.date(annee, mois, calendar.monthrange(annee, mois)[1])
        return {'type': type_, 'annee': annee, 'mois': mois, 'trimestre': None,
                'debut': debut, 'fin': fin,
                'libelle': f'{MOIS[mois - 1]} {annee}'}
    if type_ == PeriodType.QUARTER:
        trimestre = trimestre or (today.month - 1) // 3 + 1
        premier = (trimestre - 1) * 3 + 1
        debut = datetime.date(annee, premier, 1)
        fin = datetime.date(annee, premier + 2,
                            calendar.monthrange(annee, premier + 2)[1])
        return {'type': type_, 'annee': annee, 'mois': None,
                'trimestre': trimestre, 'debut': debut, 'fin': fin,
                'libelle': f'T{trimestre} {annee}'}
    return {'type': type_, 'annee': annee, 'mois': None, 'trimestre': None,
            'debut': datetime.date(annee, 1, 1),
            'fin': datetime.date(annee, 12, 31), 'libelle': f'Année {annee}'}


def _fenetre(periode):
    """``[début, fin[`` en datetimes conscients — mêmes bornes que
    ``compute_attainment``."""
    tz = timezone.get_current_timezone()
    debut = timezone.make_aware(
        datetime.datetime.combine(periode['debut'], datetime.time.min), tz)
    fin = timezone.make_aware(
        datetime.datetime.combine(periode['fin'], datetime.time.min), tz)
    return debut, fin + datetime.timedelta(days=1)


# ── Calculs ──────────────────────────────────────────────────────────────────
def _pct(realise, cible):
    if not cible:
        return None
    return round(float(Decimal(realise) / Decimal(cible) * 100), 1)


def _objectifs_existants(company, membre_ids, periode):
    qs = ObjectifCommercial.objects.filter(
        company=company, owner_id__in=membre_ids, period_type=periode['type'],
        period_year=periode['annee']).select_related('company', 'owner')
    if periode['type'] == PeriodType.MONTH:
        qs = qs.filter(period_month=periode['mois'])
    elif periode['type'] == PeriodType.QUARTER:
        qs = qs.filter(period_quarter=periode['trimestre'])
    return {(o.owner_id, o.metric): o for o in qs.order_by('id')}


def _objectifs_membre(company, membre, periode, existants):
    """Une entrée par métrique : réalisé de ``compute_attainment`` — sur
    l'objectif posé, sinon sur un objectif TRANSITOIRE (jamais enregistré)
    de la même période : même calcul, cible absente."""
    from .clients_selectors import compute_attainment
    out = {}
    for metric in METRIQUES:
        objectif = existants.get((membre.pk, metric.value))
        calcul = objectif or ObjectifCommercial(
            company=company, owner=membre, metric=metric.value,
            period_type=periode['type'], period_year=periode['annee'],
            period_month=periode['mois'], period_quarter=periode['trimestre'],
            cible=Decimal('0'))
        realise = compute_attainment(calcul)['realise']
        cible = objectif.cible if objectif is not None else None
        out[metric.value] = {
            'objectif_id': objectif.pk if objectif is not None else None,
            'cible': float(cible) if cible is not None else None,
            'realise': float(realise),
            'pct': _pct(realise, cible),
        }
    return out


def _premier_contact(company, membre_ids, debut, fin):
    """{owner_id: (mesurés, sous l'objectif)} — la règle de
    ``leads_selectors.kpi_premier_contact`` sur les leads arrivés dans la
    période, par propriétaire."""
    from .leads_selectors import _objectif_premier_contact
    from .models import Lead
    objectif = _objectif_premier_contact(company)
    leads = (Lead.objects
             .filter(company=company, is_archived=False,
                     source=Lead.Source.OS_NATIVE, owner_id__in=membre_ids,
                     date_creation__gte=debut, date_creation__lt=fin)
             .only('id', 'owner', 'date_creation', 'date_creation_origine',
                   'first_contacted_at'))
    out = {}
    for lead in leads:
        mesures, sous = out.get(lead.owner_id, (0, 0))
        if lead.first_contacted_at is not None and horaires.minutes_ouvrees_entre(
                lead.date_origine, lead.first_contacted_at, company) <= objectif:
            sous += 1
        out[lead.owner_id] = (mesures + 1, sous)
    return out


def _relances_en_retard(company, membre_ids):
    """{owner_id: étapes ouvertes en retard} — ALEA32 (jours COMPTÉS,
    absences du responsable comprises)."""
    from .controle_suivi import etape_en_retard, seuil_retard
    from .models import RelanceEtape
    today = aujourd_hui_local()
    etapes = RelanceEtape.objects.filter(
        company=company, statut=RelanceEtape.Statut.A_FAIRE,
        lead__is_archived=False, lead__owner_id__in=membre_ids,
        due_date__lt=seuil_retard(company, today)).select_related('lead')
    memo, out = {}, {}
    for etape in etapes:
        if etape_en_retard(etape, aujourd_hui=today, memo=memo):
            out[etape.lead.owner_id] = out.get(etape.lead.owner_id, 0) + 1
    return out


def _leads_ouverts(company, membre_ids):
    """{owner_id: (ouverts, jamais contactés)} — leads ouverts de
    ``_lignes_pipeline_ouvertes`` (STAGES.py, hors perdus/archivés)."""
    from .clients_selectors import _lignes_pipeline_ouvertes
    lignes = (_lignes_pipeline_ouvertes(company, membre_ids)
              .prefetch_related(None).order_by().values('owner_id')
              .annotate(n=Count('id'),
                        jamais=Count('id', filter=Q(first_contacted_at__isnull=True))))
    return {r['owner_id']: (r['n'], r['jamais']) for r in lignes}


def _devis_ouverts(company, membre_ids):
    """{owner_id: (nombre, valeur TTC)} — devis ``envoye`` en vigueur
    (``is_active``) des leads du membre, lus par ``lead.devis``."""
    from .models import Lead
    leads = (Lead.objects
             .filter(company=company, owner_id__in=membre_ids,
                     devis__statut=STATUT_DEVIS_OUVERT, devis__is_active=True)
             .distinct().prefetch_related('devis__lignes__produit'))
    out = {}
    for lead in leads:
        for devis in lead.devis.all():
            if devis.statut != STATUT_DEVIS_OUVERT or not devis.is_active:
                continue
            nombre, valeur = out.get(lead.owner_id, (0, Decimal('0')))
            out[lead.owner_id] = (nombre + 1,
                                  valeur + Decimal(str(devis.total_ttc or 0)))
    return out


def _attentes(equipe):
    """Leads de l'équipe en attente d'attribution (hors décidés ailleurs)."""
    attentes = (AttributionEnAttente.objects
                .filter(equipe=equipe, company_id=equipe.company_id)
                .select_related('lead', 'equipe'))
    return [a for a in attentes if not dispatch._deja_decide(a)]


def _suivi(mesures, sous, retard, jamais, attente):
    return {'premier_contact_5min_pct': (round(100.0 * sous / mesures, 1)
                                         if mesures else None),
            'premier_contact_mesures': mesures,
            'relances_en_retard': retard,
            'leads_non_contactes': jamais,
            'leads_en_attente': attente}


def _totaux(membres):
    objectifs = {}
    for metric in METRIQUES:
        lignes = [m['objectifs'][metric.value] for m in membres]
        cibles = [Decimal(str(ligne['cible'])) for ligne in lignes
                  if ligne['cible'] is not None]
        cible = sum(cibles, Decimal('0')) if cibles else None
        realise = sum((Decimal(str(ligne['realise'])) for ligne in lignes),
                      Decimal('0'))
        objectifs[metric.value] = {
            'cible': float(cible) if cible is not None else None,
            'realise': float(realise), 'pct': _pct(realise, cible)}
    pipeline = {cle: sum(m['pipeline'][cle] for m in membres)
                for cle in ('leads_ouverts', 'devis_ouverts')}
    pipeline['valeur_devis_ouverts'] = float(sum(
        (Decimal(str(m['pipeline']['valeur_devis_ouverts'])) for m in membres),
        Decimal('0')))
    return objectifs, pipeline


# ── Payload ──────────────────────────────────────────────────────────────────
def _equipe_demandee(user, equipe_id, accessibles):
    if equipe_id is None:
        return accessibles[0] if accessibles else None
    equipe = (EquipeCommerciale.objects
              .filter(pk=equipe_id, company_id=user.company_id)
              .select_related('company', 'departement', 'responsable').first()
              if user.company_id else None)
    if equipe is None:
        raise NotFound('Équipe introuvable.')
    if not dispatch.peut_regler(user, equipe):
        raise PermissionDenied(
            "Seuls le responsable de l'équipe, le directeur commercial et la "
            "Direction ouvrent son cockpit.")
    return equipe


def cockpit(user, request):
    """Le cockpit (contrat ``cockpit_equipe.json``). 400 paramètre invalide,
    404 équipe hors société, 403 sans droit, ``exemple_vide`` si l'utilisateur
    ne pilote aucune équipe."""
    equipe_id = entier_param(request, 'equipe')
    periode = lire_periode(request)
    accessibles = equipes_pilotees(user)
    equipe = _equipe_demandee(user, equipe_id, accessibles)
    if equipe is None:
        return dict(VIDE)
    company = equipe.company
    membres = sorted(
        equipe.membres.filter(is_active=True, company_id=equipe.company_id),
        key=lambda u: ((dispatch.nom_affiche(u) or '').lower(), u.pk))
    ids = [m.pk for m in membres]
    debut, fin = _fenetre(periode)
    existants = _objectifs_existants(company, ids, periode)
    contact = _premier_contact(company, ids, debut, fin)
    retard = _relances_en_retard(company, ids)
    ouverts = _leads_ouverts(company, ids)
    devis = _devis_ouverts(company, ids)
    attentes = _attentes(equipe)
    lignes = []
    for m in membres:
        mesures, sous = contact.get(m.pk, (0, 0))
        n_ouverts, jamais = ouverts.get(m.pk, (0, 0))
        n_devis, valeur = devis.get(m.pk, (0, Decimal('0')))
        lignes.append({
            'id': m.pk,
            'nom': dispatch.nom_affiche(m),
            'fonction': (m.poste or '').strip() or None,
            'objectifs': _objectifs_membre(company, m, periode, existants),
            'suivi': _suivi(mesures, sous, retard.get(m.pk, 0), jamais,
                            sum(1 for a in attentes if a.proposee_id == m.pk)),
            'pipeline': {'leads_ouverts': n_ouverts, 'devis_ouverts': n_devis,
                         'valeur_devis_ouverts': float(valeur)},
        })
    objectifs, pipeline = _totaux(lignes)
    mesures = sum(v[0] for v in contact.values())
    sous = sum(v[1] for v in contact.values())
    return {
        'equipes_accessibles': [{'id': e.pk, 'nom': e.nom} for e in accessibles],
        'equipe': {'id': equipe.pk, 'nom': equipe.nom,
                   'responsable': dispatch.nom_affiche(equipe.responsable)},
        'periode': {**periode, 'debut': periode['debut'].isoformat(),
                    'fin': periode['fin'].isoformat()},
        'metriques': [{'cle': m.value, 'libelle': str(m.label)} for m in METRIQUES],
        'membres': lignes,
        'equipe_totaux': {
            'objectifs': objectifs,
            'suivi': _suivi(mesures, sous, sum(retard.values()),
                            sum(v[1] for v in ouverts.values()), len(attentes)),
            'pipeline': pipeline,
        },
    }
