"""CAD-I — CAD87 : mesurer ce qui prouverait que la cadence marche.

Audit L3 du 21/09/2026, section CAD-I. CKP3 sait déjà dire OÙ les dossiers
décrochent (agrégat par ordre de touche, ``selectors.kpi_adherence``), mais
personne ne peut répondre aux trois questions qui trancheraient le samedi, la
soirée de Ramadan et la densité du protocole sur des faits MAISON plutôt que
sur des repères occidentaux non transposables (CAD89) :

  1. à quelle HEURE et quel JOUR joint-on le plus, par touche et par canal ?
  2. combien de touches ont été consommées avant une signature ?
  3. quelle part des leads demande « WhatsApp uniquement » ou la darija ?

Ce module ne fait QUE lire. Aucun seuil, aucune couleur, aucune
recommandation : des dénombrements et des taux, le jugement reste humain — et
``null`` dès qu'un dénominateur est 0, jamais un 0 % qui se lirait comme un
échec là où il n'y a rien à mesurer (même règle que ``kpi_cadences``).

**Ce module ne change ni le nombre, ni l'ordre, ni le J+N des touches** : il
les observe.

Multi-tenant : toute lecture est bornée par ``company``, et la vue qui
l'expose passe ``request.user.company`` — jamais un identifiant reçu du
client.
"""
import datetime

#: Les issues qui valent « on a eu le client au bout du fil ». Reprises à
#: l'identique de ``kpi_cadences`` (``selectors.py``) et de la définition de
#: CAD131 (« issue joint ou intéressé ») : deux KPI qui comptent « joint »
#: autrement seraient impossibles à confronter. ``visite_acceptee`` en est
#: volontairement absente pour cette seule raison de comparabilité.
ISSUES_JOINT = ('joint', 'interesse')

#: Les statuts de touche CLOSE PAR UN HUMAIN (CKP3, ``_STATUTS_CLOS_HUMAIN``).
#: Une annulation MOTEUR (`annulee`) n'a jamais été tentée par personne : la
#: compter au dénominateur d'un taux de joint le ferait plonger sans qu'aucun
#: geste n'ait changé.
STATUTS_CLOS_HUMAIN = ('fait', 'sautee')

#: Nom de la colonne d'issue portée par ``RelanceEtape`` depuis CAD118. Tant
#: qu'elle n'existe pas, l'issue se retrouve par la fenêtre d'appariement
#: ci-dessous — c'est exactement le bricolage que CAD118 supprime.
CHAMP_ISSUE = 'outcome'

#: Fenêtre d'appariement de REPLI entre une touche close et la ligne de
#: chatter écrite par la MÊME requête (même valeur et même raisonnement que
#: ``selectors._JOURNAL_FENETRE`` : une requête HTTP, pas une journée). Elle
#: casse en silence dès qu'un traitement ralentit — d'où CAD118.
FENETRE_APPARIEMENT = datetime.timedelta(minutes=2)

#: Profondeur par défaut des mesures, en jours. 90 et non 30 : un agrégat
#: croisé (touche × heure × jour × canal) sur 30 jours n'a presque aucune
#: case peuplée. Bornée par la vue à [1, 365].
JOURS_MESURE_DEFAUT = 90


def _colonne_issue_disponible():
    """``True`` quand ``RelanceEtape`` porte la colonne d'issue de CAD118."""
    from .models import RelanceEtape
    return any(champ.name == CHAMP_ISSUE
               for champ in RelanceEtape._meta.get_fields())


def _issues_par_touche(touches, company):
    """``{id de touche: issue}`` pour un lot de touches closes.

    Deux chemins, un seul contrat de sortie :

    * la colonne d'issue existe (CAD118) → elle est lue telle quelle, en UNE
      requête ;
    * sinon → repli d'appariement : la ligne de chatter écrite par la même
      requête que la clôture (même lead, même auteur, à moins de deux minutes
      de ``traite_le``). Deux requêtes au total, jamais une par touche.
    """
    from .models import LeadActivity

    if _colonne_issue_disponible():
        return {ligne['id']: (ligne.get(CHAMP_ISSUE) or '')
                for ligne in touches.values('id', CHAMP_ISSUE)}

    closes = list(touches.values('id', 'lead_id', 'traite_par_id', 'traite_le'))
    if not closes:
        return {}
    instants = [c['traite_le'] for c in closes if c['traite_le'] is not None]
    if not instants:
        return {}
    activites = list(
        LeadActivity.objects
        .filter(company=company,
                lead_id__in={c['lead_id'] for c in closes},
                created_at__gte=min(instants) - FENETRE_APPARIEMENT,
                created_at__lte=max(instants) + FENETRE_APPARIEMENT)
        .exclude(outcome='')
        .values('lead_id', 'user_id', 'created_at', 'outcome'))
    par_lead = {}
    for activite in activites:
        par_lead.setdefault(activite['lead_id'], []).append(activite)

    issues = {}
    for close in closes:
        instant = close['traite_le']
        if instant is None:
            continue
        for activite in par_lead.get(close['lead_id'], ()):
            if activite['user_id'] != close['traite_par_id']:
                continue
            if abs(activite['created_at'] - instant) <= FENETRE_APPARIEMENT:
                issues[close['id']] = activite['outcome'] or ''
                break
    return issues


def _pct(numerateur, denominateur):
    """``null`` dès que le dénominateur est 0 — jamais un 0 % inventé."""
    if not denominateur:
        return None
    return round(100.0 * numerateur / denominateur, 1)


def taux_joint_par_creneau(company, *, jours=JOURS_MESURE_DEFAUT):
    """Taux de joint par (ordre de touche × heure × jour de semaine × canal).

    Le grain est celui de la QUESTION posée : « à quelle heure et quel jour
    joint-on le plus, et sur quel canal ? ». L'heure et le jour sont ceux de
    la CLÔTURE de la touche, lus à Casablanca (le geste a eu lieu là).

    Dénominateur : les touches closes par un HUMAIN. Numérateur : celles dont
    l'issue est « joint » ou « intéressé ». ``taux_joint_pct`` vaut ``null``
    sur un dénominateur vide.
    """
    from django.utils import timezone

    from . import horaires
    from .models import RelanceEtape

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    touches = RelanceEtape.objects.filter(
        company=company, traite_le__gte=depuis,
        statut__in=STATUTS_CLOS_HUMAIN)
    issues = _issues_par_touche(touches, company)

    cases = {}
    for ligne in touches.values('id', 'ordre', 'canal', 'traite_le'):
        instant = ligne['traite_le']
        if instant is None:
            continue
        local = instant.astimezone(horaires.CASABLANCA)
        cle = (ligne['ordre'], ligne['canal'], local.hour,
               local.weekday())
        case = cases.setdefault(cle, {
            'ordre': ligne['ordre'], 'canal': ligne['canal'],
            'heure': local.hour, 'jour_semaine': local.weekday(),
            'closes': 0, 'joints': 0})
        case['closes'] += 1
        if issues.get(ligne['id'], '') in ISSUES_JOINT:
            case['joints'] += 1

    lignes = []
    for case in sorted(cases.values(),
                       key=lambda c: (c['ordre'], c['canal'],
                                      c['jour_semaine'], c['heure'])):
        lignes.append({
            'ordre': case['ordre'], 'canal': case['canal'],
            'heure': case['heure'], 'jour_semaine': case['jour_semaine'],
            'closes': case['closes'], 'joints': case['joints'],
            'taux_joint_pct': _pct(case['joints'], case['closes']),
        })
    return lignes


def signatures_par_touches_consommees(company, *, jours=JOURS_MESURE_DEFAUT):
    """Combien de touches avaient été consommées avant chaque signature.

    Calculable AUJOURD'HUI sans rien ajouter au schéma : le passage d'étape
    vers SIGNED vit dans le chatter (``LeadActivity`` ``field='stage'``, comme
    ``kpi_cadences``) et les touches closes portent leur ``traite_le``. On
    compte, pour chaque signature, les touches closes par un humain AVANT
    elle.

    Rendu : une distribution ``[{touches, signatures}]`` triée par nombre de
    touches — pas une moyenne, qu'une queue de dossiers anciens suffirait à
    déplacer.
    """
    from django.utils import timezone

    from . import stages
    from .models import LeadActivity, RelanceEtape

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    signatures = list(
        LeadActivity.objects
        .filter(company=company, field='stage', created_at__gte=depuis,
                new_value=stages.STAGE_LABELS[stages.SIGNED])
        .values('lead_id', 'created_at'))
    if not signatures:
        return []

    closes = list(
        RelanceEtape.objects
        .filter(company=company,
                lead_id__in={s['lead_id'] for s in signatures},
                statut__in=STATUTS_CLOS_HUMAIN,
                traite_le__isnull=False)
        .values('lead_id', 'traite_le'))
    par_lead = {}
    for close in closes:
        par_lead.setdefault(close['lead_id'], []).append(close['traite_le'])

    distribution = {}
    for signature in signatures:
        consommees = sum(
            1 for instant in par_lead.get(signature['lead_id'], ())
            if instant <= signature['created_at'])
        distribution[consommees] = distribution.get(consommees, 0) + 1
    return [{'touches': touches, 'signatures': nombre}
            for touches, nombre in sorted(distribution.items())]


def part_contact_et_langue(company, *, jours=JOURS_MESURE_DEFAUT):
    """Part des leads qui demandent « WhatsApp uniquement » ou la darija.

    Deux champs DÉJÀ posés par le client lui-même (``contact_preference``,
    QW3, et ``langue_preferee``) que personne n'agrège : sans ce chiffre, le
    débat « faut-il des messages en darija / faut-il moins d'appels ? » se
    tient sans base. Le miroir Odoo est écarté (voir ``kpi_cadences``) : ses
    leads n'ont jamais répondu à ces deux questions.
    """
    from django.utils import timezone

    from .models import Lead

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    leads = (Lead.objects
             .filter(company=company, is_archived=False,
                     date_creation__gte=depuis)
             .exclude(source=Lead.Source.ODOO_IMPORT_TEST))
    nb_leads = leads.count()
    whatsapp_only = leads.filter(
        contact_preference=Lead.ContactPreference.WHATSAPP_ONLY).count()
    darija = leads.filter(
        langue_preferee=Lead.LanguePreferee.DARIJA).count()
    return {
        'nb_leads': nb_leads,
        'whatsapp_only': whatsapp_only,
        'whatsapp_only_pct': _pct(whatsapp_only, nb_leads),
        'darija': darija,
        'darija_pct': _pct(darija, nb_leads),
    }


def mesure_cadence(company, *, jours=JOURS_MESURE_DEFAUT):
    """Les trois mesures de CAD87, en une seule lecture (forme du contrat).

    ``source_issue`` dit d'où vient l'issue de chaque touche — ``colonne``
    quand CAD118 est en place, ``appariement_2min`` tant qu'il faut la
    retrouver dans le chatter. Un chiffre dont on ne sait pas comment il est
    fabriqué n'est pas un chiffre.
    """
    jours = int(jours)
    return {
        'jours': jours,
        'source_issue': ('colonne' if _colonne_issue_disponible()
                         else 'appariement_2min'),
        'taux_joint_par_creneau': taux_joint_par_creneau(
            company, jours=jours),
        'signatures_par_touches_consommees': signatures_par_touches_consommees(
            company, jours=jours),
        'part_contact_et_langue': part_contact_et_langue(company, jours=jours),
    }
