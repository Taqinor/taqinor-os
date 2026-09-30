"""COCKPIT-CONTRÔLE (fondateur, 30/09/2026) — « a-t-elle fait ce qu'elle
devait ? », en UNE lecture.

Le bloc « Contrôle du suivi » du cockpit CRM. La FORME et les RÈGLES DE MESURE
sont celles du contrat ``contract_samples/controle_suivi.json`` (ses
``pourquoi`` et ``notes`` font foi, mot pour mot) ; ce module ne fait que les
appliquer. Patron ``mesure_cadence.py`` : il ne fait QUE LIRE — aucune
écriture, aucun seuil caché dans l'écran — et ``null`` dès qu'un dénominateur
est nul, jamais un 0 % inventé.

Ce qu'il sert :

* un VERDICT (niveau + les compteurs qui le justifient, comparés à la
  période de même longueur juste avant) — le niveau se lit sur l'état
  ACTUEL (les exceptions), jamais sur le seul pourcentage ;
* une FRISE d'un jour par case (jour Africa/Casablanca, échéance COURANTE) ;
* les EXCEPTIONS de l'instant, triées par ancienneté, 10 lignes au plus par
  liste (``total`` dit le vrai nombre) ;
* le détail PAR TYPE d'étape, dans l'ordre de la table du parcours ;
* la vitesse de PREMIER CONTACT (médiane, jamais la moyenne) ;
* trois RÉSULTATS lus à côté de l'effort (visites planifiées, devis envoyés,
  devis acceptés — par les sélecteurs de ``visites`` et ``ventes``, jamais
  leurs modèles).

Règles de jugement d'une étape due un jour donné (son échéance COURANTE) :
« à temps » = close « fait » au plus tard ce jour-là (ou excusée : née en
retard CAD22, ou échue un jour d'ABSENCE déclarée de son responsable CAD35 —
``selectors._a_lheure_ou_excusee``, réutilisé, jamais recopié) ; « en
retard » = close après ; « sautée » = sautée (``sautee`` est exclusivement
humain, CKP1) ; « ouvert » = encore à faire. Les annulations du MOTEUR
(``annulee``) sortent du dénominateur. Une étape d'aujourd'hui encore ouverte
n'est pas jugée (la journée n'est pas finie) : elle colore la case du jour
« en cours » sans entrer au verdict.

Transparence (décision fondateur CKP3) : aucune garde de rôle — seule la
portée de visibilité (``scope_queryset`` via le lead) borne la lecture, et
``owner`` restreint à un responsable. Multi-société : tout est borné par
``company``.
"""
import datetime

#: Les périodes servies (en jours calendaires), et celle par défaut.
JOURS_AUTORISES = (7, 14, 30)
JOURS_DEFAUT = 14

#: Les seuils du verdict (contrat, ``seuils``). ``premier_contact_heures``
#: n'est pas ici : c'est le délai de la société (``lead_sla_hours``).
RETARD_ALERTE_JOURS = 2
TACHE_ATTENTE_JOURS = 2
REPORTS_MIN = 2

#: Plafond de chaque liste d'exceptions (``total`` dit le vrai nombre).
LIGNES_MAX = 10

NIVEAU_ALERTE = 'alerte'
NIVEAU_ATTENTION = 'attention'
NIVEAU_OK = 'ok'
NIVEAU_VIDE = 'vide'

ETAT_VERT = 'vert'
ETAT_ORANGE = 'orange'
ETAT_ROUGE = 'rouge'
ETAT_EN_COURS = 'en_cours'
ETAT_VIDE = 'vide'

#: Les quatre jugements d'une étape due (clés du verdict, des cases et des
#: lignes ``par_type``).
A_TEMPS = 'a_temps'
EN_RETARD = 'en_retard'
SAUTEES = 'sautees'
OUVERT = 'ouvert'
JUGEMENTS = (A_TEMPS, EN_RETARD, SAUTEES, OUVERT)

#: Les refus nommés (400 ``{"erreurs": {champ: message}}``).
MESSAGE_JOURS = '« Période » : 7, 14 ou 30 jours.'
MESSAGE_OWNER = ('« Commercial » : responsable inconnu ou hors de votre '
                 'portée.')


# ── Paramètres ───────────────────────────────────────────────────────────────

def parametres_controle(company, user, jours_brut=None, owner_brut=None):
    """``(jours, owner, erreurs)`` depuis les paramètres de la requête.

    ``jours`` absent → 14 ; hors {7, 14, 30} → refus nommé. ``owner`` absent
    → toute la portée ; sinon l'identifiant d'un utilisateur de la SOCIÉTÉ,
    dans la portée de visibilité du demandeur — un identifiant inconnu ou
    hors portée est refusé du MÊME message (jamais un oracle d'existence)."""
    erreurs = {}
    jours = JOURS_DEFAUT
    brut = str(jours_brut if jours_brut is not None else '').strip()
    if brut:
        if brut.isdigit() and int(brut) in JOURS_AUTORISES:
            jours = int(brut)
        else:
            erreurs['jours'] = MESSAGE_JOURS
    owner = None
    brut = str(owner_brut if owner_brut is not None else '').strip()
    if brut:
        if brut.isdigit() and _owner_dans_la_portee(company, user, int(brut)):
            owner = int(brut)
        else:
            erreurs['owner'] = MESSAGE_OWNER
    return jours, owner, erreurs


def _owner_dans_la_portee(company, user, owner_id):
    from django.contrib.auth import get_user_model

    from authentication.scoping import visible_user_ids

    if not get_user_model().objects.filter(
            pk=owner_id, company=company).exists():
        return False
    visibles = visible_user_ids(user)
    return visibles is None or owner_id in visibles


# ── Petits outils de lecture ─────────────────────────────────────────────────

def _pct(numerateur, denominateur):
    """``null`` dès que le dénominateur est 0 (``selectors._pct``)."""
    from .selectors import _pct as pct
    return pct(numerateur, denominateur)


def _debut_du_jour(jour):
    from . import horaires
    return datetime.datetime.combine(jour, datetime.time(0, 0),
                                     tzinfo=horaires.CASABLANCA)


def _jour_local(instant):
    from . import horaires
    return instant.astimezone(horaires.CASABLANCA).date()


def _horodatage(instant):
    """Un instant rendu comme les autres champs date-heure de l'API (DRF,
    fuseau de la société) ; ``None`` reste ``None``."""
    if instant is None:
        return None
    from rest_framework import serializers
    return serializers.DateTimeField().to_representation(instant)


def _juger(etape, absences, proprietaire):
    """Le jugement d'une étape due (voir l'en-tête du module)."""
    from .models import RelanceEtape
    from .selectors import _a_lheure_ou_excusee

    if etape.statut == RelanceEtape.Statut.FAIT:
        return (A_TEMPS if _a_lheure_ou_excusee(etape, absences, proprietaire)
                else EN_RETARD)
    if etape.statut == RelanceEtape.Statut.SAUTEE:
        return SAUTEES
    return OUVERT


def _compteurs():
    return {'du': 0, A_TEMPS: 0, EN_RETARD: 0, SAUTEES: 0, OUVERT: 0}


def _etat_du_jour(case, aujourdhui):
    """``jours.etat`` (contrat, ``notes.jours.etat``)."""
    if not case['du']:
        return ETAT_VIDE
    if case[OUVERT]:
        return ETAT_EN_COURS if aujourdhui else ETAT_ROUGE
    if case[EN_RETARD] or case[SAUTEES]:
        return ETAT_ORANGE
    return ETAT_VERT


def _ligne_etape(etape, extra):
    """Une ligne d'exception qui ouvre le dossier (étape, lead, noms)."""
    from .serializers import nom_affichable_lead, nom_affichable_responsable
    from .suite_touche import est_tache, type_etape_connu

    ligne = {
        'etape': etape.pk,
        'lead': etape.lead_id,
        'lead_nom': nom_affichable_lead(etape.lead),
        'owner_nom': nom_affichable_responsable(etape.lead.owner),
        'libelle': (etape.libelle or '').strip() or etape.get_canal_display(),
        'type_etape': type_etape_connu(etape),
        'est_tache': est_tache(etape),
        'canal': etape.canal,
        'due_date': etape.due_date.isoformat(),
    }
    ligne.update(extra)
    return ligne


def _liste(lignes, owner):
    """``{total, lignes}`` d'une liste d'exceptions ``[(owner_id, ligne)]``
    filtrée sur ``owner`` — ``total`` exact, 10 lignes au plus."""
    retenues = [ligne for proprietaire, ligne in lignes
                if owner is None or proprietaire == owner]
    return {'total': len(retenues), 'lignes': retenues[:LIGNES_MAX]}


# ── Les exceptions de l'instant (toute la portée ; ``owner`` filtre après) ──

def _en_retard(etapes_en_retard, today, absences):
    lignes = []
    for etape in etapes_en_retard:
        if absences.couvre(etape.lead.owner_id, etape.due_date):
            continue                              # absence déclarée : excusée
        lignes.append((etape.lead.owner_id, _ligne_etape(
            etape, {'jours_de_retard': (today - etape.due_date).days})))
    return lignes


def _taches_en_attente(company, portee_ids, today):
    """TÂCHES ouvertes posées depuis ``TACHE_ATTENTE_JOURS`` jours ou plus,
    quelle que soit leur échéance : un report ne les en sort pas."""
    from .models import RelanceEtape
    from .suite_touche import q_tache

    seuil = _debut_du_jour(
        today - datetime.timedelta(days=TACHE_ATTENTE_JOURS - 1))
    etapes = (RelanceEtape.objects
              .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                      lead_id__in=portee_ids, created_at__lt=seuil)
              .filter(q_tache())
              .select_related('lead', 'lead__owner')
              .order_by('created_at', 'pk'))
    return [(etape.lead.owner_id, _ligne_etape(etape, {
        'ouverte_depuis_jours': (today - _jour_local(etape.created_at)).days,
    })) for etape in etapes]


def _reports(company, portee_ids):
    """Étapes OUVERTES repoussées ``REPORTS_MIN`` fois ou plus par un geste
    humain, la plus ancienne origine d'abord."""
    from django.db.models import F
    from django.db.models.functions import Coalesce

    from .models import RelanceEtape

    etapes = (RelanceEtape.objects
              .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                      lead_id__in=portee_ids, nb_reports__gte=REPORTS_MIN)
              .select_related('lead', 'lead__owner')
              .order_by(Coalesce('due_initial_at', 'due_at').asc(
                  nulls_last=True), F('due_date').asc(), 'pk'))
    return [(etape.lead.owner_id, _ligne_etape(etape, {
        'due_initial': (_jour_local(etape.due_initial_at).isoformat()
                        if etape.due_initial_at else None),
        'nb_reports': etape.nb_reports,
    })) for etape in etapes]


def _sans_prochaine_etape(company, portee, today):
    """Dossiers ACTIFS (ni archivés, ni perdus, ni « ne plus contacter », ni
    Signé, ni Froid — clés de ``STAGES.py``) qui ont DÉJÀ eu une étape et
    n'en ont plus aucune d'ouverte. Un ancien lead jamais placé reste
    l'affaire de la carte « Anciens leads à placer ».

    Ligne (contrat, ``exemple_alerte``) : ``stage`` (clé de ``STAGES.py``),
    ``derniere_etape_le`` (jour Casablanca de la clôture de sa dernière
    étape) et ``depuis_jours`` (jours calendaires écoulés depuis) ; triée par
    ``depuis_jours`` décroissant — le plus ancien d'abord."""
    from django.db.models import Exists, OuterRef, Subquery

    from . import stages
    from .models import RelanceEtape
    from .serializers import nom_affichable_lead, nom_affichable_responsable

    etapes = RelanceEtape.objects.filter(company=company,
                                         lead_id=OuterRef('pk'))
    derniere = (etapes.filter(traite_le__isnull=False)
                .order_by('-traite_le').values('traite_le')[:1])
    leads = (portee
             .filter(perdu=False, ne_plus_contacter=False)
             .exclude(stage__in=[stages.SIGNED, stages.COLD])
             .annotate(_a_eu_une_etape=Exists(etapes),
                       _une_ouverte=Exists(etapes.filter(
                           statut=RelanceEtape.Statut.A_FAIRE)),
                       _derniere_etape=Subquery(derniere))
             .filter(_a_eu_une_etape=True, _une_ouverte=False)
             # La portée d'un rôle restreint est un `DISTINCT` : on ne lit
             # que les colonnes servies.
             .select_related('owner')
             .only('id', 'nom', 'prenom', 'stage', 'owner',
                   'owner__username'))
    lignes = []
    for lead in leads:
        derniere_le = lead._derniere_etape
        jour = _jour_local(derniere_le) if derniere_le else None
        lignes.append((lead.owner_id, {
            'lead': lead.pk,
            'lead_nom': nom_affichable_lead(lead),
            'owner_nom': nom_affichable_responsable(lead.owner),
            'stage': lead.stage,
            'derniere_etape_le': jour.isoformat() if jour else None,
            'depuis_jours': (today - jour).days if jour else None,
        }))
    # Le plus ancien d'abord ; une étape jamais horodatée (aucune clôture
    # connue) en dernier, jamais un âge inventé.
    lignes.sort(key=lambda paire: (paire[1]['depuis_jours'] is None,
                                   -(paire[1]['depuis_jours'] or 0),
                                   paire[1]['lead']))
    return lignes


def _premier_contact_hors_delai(company, portee_ids, maintenant, sla):
    """Leads « Nouveau » jamais contactés au-delà du délai de la société : la
    règle de ``sla-breach`` (``selectors.leads_sla_depasse``, 0 = désactivé
    → liste vide), tranchée en HEURES OUVRÉES — le filtre calendaire n'est
    qu'un pré-filtre (une échéance ouvrée n'est jamais plus tôt). Le miroir
    Odoo, les leads perdus et « ne plus contacter » n'attendent personne."""
    if not sla:
        return []
    from . import horaires
    from .models import Lead
    from .selectors import leads_sla_depasse
    from .serializers import nom_affichable_lead, nom_affichable_responsable

    candidats = (leads_sla_depasse(company, now=maintenant, seuil_heures=sla)
                 .filter(id__in=portee_ids, perdu=False,
                         ne_plus_contacter=False)
                 .exclude(source=Lead.Source.ODOO_IMPORT_TEST)
                 .select_related('owner'))
    lignes = []
    for lead in candidats:
        minutes = horaires.minutes_ouvrees_entre(
            lead.date_creation, maintenant, company)
        if minutes < sla * 60:
            continue
        lignes.append((lead.owner_id, {
            'lead': lead.pk,
            'lead_nom': nom_affichable_lead(lead),
            'owner_nom': nom_affichable_responsable(lead.owner),
            'cree_le': _horodatage(lead.date_creation),
            'attend_depuis_heures': round(minutes / 60.0, 1),
        }))
    return lignes


# ── La mesure de la période ──────────────────────────────────────────────────

def _mesure_de_la_periode(etapes, today, absences, proprietaire):
    """``(cases_par_jour, verdict, par_type)`` sur les étapes dues de la
    période (déjà filtrées sur ``owner``, annulations exclues)."""
    from .suite_touche import type_etape_connu

    cases = {}
    verdict = _compteurs()
    par_type = {}
    for etape in etapes:
        jugement = _juger(etape, absences, proprietaire)
        case = cases.setdefault(etape.due_date, _compteurs())
        case['du'] += 1
        case[jugement] += 1
        if jugement == OUVERT and etape.due_date == today:
            continue                     # la journée n'est pas finie
        verdict['du'] += 1
        verdict[jugement] += 1
        ligne = par_type.setdefault(type_etape_connu(etape), {
            'compteurs': _compteurs(), 'reponses': {}})
        ligne['compteurs']['du'] += 1
        ligne['compteurs'][jugement] += 1
        if jugement in (A_TEMPS, EN_RETARD):
            cle = (etape.outcome or '').strip() or 'sans_issue'
            ligne['reponses'][cle] = ligne['reponses'].get(cle, 0) + 1
    return cases, verdict, par_type


def _a_temps_pct(etapes, absences, proprietaire):
    """La même mesure qu'au verdict, sur une période ENTIÈREMENT passée."""
    jugements = [_juger(e, absences, proprietaire) for e in etapes]
    return _pct(sum(1 for j in jugements if j == A_TEMPS), len(jugements))


def _lignes_par_type(par_type):
    """``par_type`` dans l'ORDRE de la table du parcours ; un type sans étape
    due n'est pas servi ; ``reponses`` par effectif décroissant."""
    from .suite_touche import TYPES_ORDONNES, TYPES_TACHE

    lignes = []
    for type_id in TYPES_ORDONNES:
        bloc = par_type.get(type_id)
        if not bloc or not bloc['compteurs']['du']:
            continue
        compteurs = bloc['compteurs']
        lignes.append({
            'type_etape': type_id,
            'est_tache': type_id in TYPES_TACHE,
            'du': compteurs['du'],
            A_TEMPS: compteurs[A_TEMPS],
            EN_RETARD: compteurs[EN_RETARD],
            SAUTEES: compteurs[SAUTEES],
            OUVERT: compteurs[OUVERT],
            'reponses': [
                {'cle': cle, 'n': n} for cle, n in sorted(
                    bloc['reponses'].items(),
                    key=lambda paire: (-paire[1], paire[0]))],
        })
    return lignes


def _premier_contact(portee, owner, debut, maintenant, sla, company):
    """Leads CRÉÉS sur la période (hors miroir Odoo) : délai création →
    premier contact en minutes OUVRÉES, médiane (jamais la moyenne), et la
    plus longue attente d'un lead « Nouveau » encore jamais contacté."""
    from . import horaires, stages
    from .models import Lead
    from .selectors import _mediane

    leads = (portee.filter(date_creation__gte=_debut_du_jour(debut))
             .exclude(source=Lead.Source.ODOO_IMPORT_TEST))
    if owner is not None:
        leads = leads.filter(owner_id=owner)
    nouveaux = 0
    delais = []
    attentes = []
    for lead in leads.only('id', 'date_creation', 'first_contacted_at',
                           'stage', 'perdu', 'ne_plus_contacter'):
        nouveaux += 1
        if lead.first_contacted_at is not None:
            delais.append(horaires.minutes_ouvrees_entre(
                lead.date_creation, lead.first_contacted_at, company))
        elif (lead.stage == stages.NEW and not lead.perdu
              and not lead.ne_plus_contacter):
            attentes.append(horaires.minutes_ouvrees_entre(
                lead.date_creation, maintenant, company))
    return {
        'nouveaux': nouveaux,
        'dans_le_delai': (sum(1 for minutes in delais if minutes < sla * 60)
                          if sla else 0),
        'mediane_minutes': _mediane(delais),
        'delai_heures': sla,
        'plus_longue_attente_heures': (round(max(attentes) / 60.0, 1)
                                       if attentes else None),
    }


def _resultats(company, portee, owner, debut):
    """Trois RÉSULTATS à lire À CÔTÉ de l'effort, lus par les sélecteurs des
    apps propriétaires (frontière M3) — jamais un classement."""
    from apps.ventes.selectors import resultats_devis_periode
    from apps.visites.selectors import nombre_visites_planifiees

    leads = portee if owner is None else portee.filter(owner_id=owner)
    ids = leads.values('id')
    devis = resultats_devis_periode(company, ids, depuis=_debut_du_jour(debut),
                                    depuis_jour=debut)
    return {
        'visites_planifiees': nombre_visites_planifiees(
            company, ids, depuis=_debut_du_jour(debut)),
        'devis_envoyes': devis['envoyes'],
        'devis_acceptes': devis['acceptes'],
    }


def _commerciaux(proprietaires):
    """``[{id, nom}]`` des responsables concernés, par nom — le nom par le
    helper de la file (``nom_affichable_responsable``), aucun prénom en dur."""
    from django.contrib.auth import get_user_model

    from .serializers import nom_affichable_responsable

    utilisateurs = get_user_model().objects.filter(
        pk__in=[pk for pk in proprietaires if pk is not None])
    lignes = [{'id': u.pk, 'nom': nom_affichable_responsable(u) or ''}
              for u in utilisateurs]
    return sorted(lignes, key=lambda ligne: (ligne['nom'], ligne['id']))


# ── LA lecture ───────────────────────────────────────────────────────────────

def controle_suivi(company, user, *, jours=JOURS_DEFAUT, owner=None,
                   maintenant=None):
    """Le bloc « Contrôle du suivi » — EXACTEMENT la forme de
    ``contract_samples/controle_suivi.json``.

    ``jours`` ∈ ``JOURS_AUTORISES`` et ``owner`` (un responsable de la portée,
    ou ``None``) sont validés par ``parametres_controle`` en amont.
    ``maintenant`` (instant aware) est injectable pour les tests ; le JOUR est
    celui d'Africa/Casablanca."""
    from django.utils import timezone

    from authentication.scoping import scope_queryset
    from core.dates import aujourd_hui_local

    from . import cadence_absence, horaires
    from .models import Lead, RelanceEtape
    from .services import lead_sla_hours

    maintenant = maintenant or timezone.now()
    today = aujourd_hui_local(maintenant)
    jours = int(jours)
    debut = today - datetime.timedelta(days=jours - 1)
    debut_precedent = debut - datetime.timedelta(days=jours)
    sla = lead_sla_hours(company)

    portee = scope_queryset(
        Lead.objects.filter(company=company, is_archived=False), user,
        ['owner'])
    portee_ids = portee.values('id')
    proprietaire = dict(portee.values_list('id', 'owner_id'))

    with horaires.cache_local():
        # Les étapes dues sur les DEUX périodes (courante et précédente),
        # annulations du moteur exclues du dénominateur.
        dues = list(
            RelanceEtape.objects
            .filter(company=company, lead_id__in=portee_ids,
                    due_date__gte=debut_precedent, due_date__lte=today)
            .exclude(statut=RelanceEtape.Statut.ANNULEE)
            .only('id', 'lead', 'statut', 'due_date', 'due_at',
                  'traite_le', 'created_at', 'cadence_depart', 'cle',
                  'libelle', 'cadence', 'canal', 'outcome'))
        etapes_en_retard = list(
            RelanceEtape.objects
            .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                    lead_id__in=portee_ids, due_date__lt=today)
            .select_related('lead', 'lead__owner')
            .order_by('due_date', 'due_at', 'pk'))
        # CAD35 — les absences déclarées, chargées UNE fois sur la fenêtre
        # que les chiffres couvrent réellement (jamais une durée inventée).
        absences = cadence_absence.couverture(
            company,
            min([debut_precedent] + [e.due_date for e in etapes_en_retard]),
            today)

        en_retard = _en_retard(etapes_en_retard, today, absences)
        taches = _taches_en_attente(company, portee_ids, today)
        reports = _reports(company, portee_ids)
        sans_etape = _sans_prochaine_etape(company, portee, today)
        hors_delai = _premier_contact_hors_delai(
            company, portee_ids, maintenant, sla)

        periode = [e for e in dues if e.due_date >= debut
                   and (owner is None or proprietaire.get(e.lead_id) == owner)]
        precedente = [e for e in dues if e.due_date < debut
                      and (owner is None
                           or proprietaire.get(e.lead_id) == owner)]
        cases, verdict, par_type = _mesure_de_la_periode(
            periode, today, absences, proprietaire)

        exceptions = {
            'en_retard': _liste(en_retard, owner),
            'taches_en_attente': _liste(taches, owner),
            'reports': _liste(reports, owner),
            'sans_prochaine_etape': _liste(sans_etape, owner),
            'premier_contact_hors_delai': _liste(hors_delai, owner),
        }
        retard_alerte = any(
            ligne['jours_de_retard'] >= RETARD_ALERTE_JOURS
            for proprietaire_id, ligne in en_retard
            if owner is None or proprietaire_id == owner)
        if (retard_alerte or exceptions['sans_prochaine_etape']['total']
                or exceptions['premier_contact_hors_delai']['total']):
            niveau = NIVEAU_ALERTE
        elif (exceptions['en_retard']['total']
              or exceptions['taches_en_attente']['total']
              or exceptions['reports']['total']):
            niveau = NIVEAU_ATTENTION
        elif not any(case['du'] for case in cases.values()):
            niveau = NIVEAU_VIDE
        else:
            niveau = NIVEAU_OK

        # Une case par jour calendaire, du plus ancien à aujourd'hui (« pas
        # encore de données » quand le verdict est vide : aucune case, comme
        # `exemple_vide`). `ouvre` : le calendrier de la société
        # (`notifications.calendar_utils`, mémorisé par `horaires`).
        frise = []
        if niveau != NIVEAU_VIDE:
            for decalage in range(jours):
                jour = debut + datetime.timedelta(days=decalage)
                case = cases.get(jour, _compteurs())
                frise.append({
                    'date': jour.isoformat(),
                    'ouvre': bool(horaires._jour_ouvre(jour, company)),
                    'aujourdhui': jour == today,
                    'du': case['du'],
                    A_TEMPS: case[A_TEMPS],
                    EN_RETARD: case[EN_RETARD],
                    SAUTEES: case[SAUTEES],
                    OUVERT: case[OUVERT],
                    'etat': _etat_du_jour(case, jour == today),
                })

        premier_contact = _premier_contact(
            portee, owner, debut, maintenant, sla, company)
        precedent_pct = _a_temps_pct(precedente, absences, proprietaire)

    concernes = {proprietaire.get(e.lead_id) for e in dues
                 if e.due_date >= debut}
    for lignes in (en_retard, taches, reports, sans_etape, hors_delai):
        concernes.update(proprietaire_id for proprietaire_id, _l in lignes)

    return {
        'periode_jours': jours,
        'owner': owner,
        'commerciaux': _commerciaux(concernes),
        'seuils': {
            'retard_alerte_jours': RETARD_ALERTE_JOURS,
            'tache_attente_jours': TACHE_ATTENTE_JOURS,
            'reports_min': REPORTS_MIN,
            'premier_contact_heures': sla,
        },
        'verdict': {
            'niveau': niveau,
            'du': verdict['du'],
            'a_temps': verdict[A_TEMPS],
            'en_retard': verdict[EN_RETARD],
            'sautees': verdict[SAUTEES],
            'ouvert': verdict[OUVERT],
            'a_temps_pct': _pct(verdict[A_TEMPS], verdict['du']),
            'precedent_a_temps_pct': precedent_pct,
        },
        'jours': frise,
        'exceptions': exceptions,
        'par_type': _lignes_par_type(par_type),
        'premier_contact': premier_contact,
        'resultats': _resultats(company, portee, owner, debut),
    }
