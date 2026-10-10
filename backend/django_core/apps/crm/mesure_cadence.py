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

CAD178 (audit CAD86, 24/09/2026) — cette mesure était 100 % DESKTOP : les
quatre écrans de cadence n'avaient aucune trace d'usage mobile.
``famille_appareil``/``enregistrer_geste_appareil``/``gestes_par_appareil``
ajoutent une QUATRIÈME question, comptée séparément (jamais mélangée aux
trois ci-dessus) : combien de gestes clés (Fait, Reporter, Appeler, WhatsApp)
partent de chaque famille d'appareil ? Compteur JOURNALIER agrégé
(``crm.GesteRelanceAppareil``), écrit en BEST-EFFORT depuis les vues — jamais
un événement par clic conservé indéfiniment, jamais l'IP ni le User-Agent brut.
"""
import datetime
import logging
import re

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

    COCKPIT-CONTRÔLE B6 (30/09/2026) — seuls les BARREAUX du protocole
    comptent (``suite_touche.q_barreau`` : prise de contact, suivi de
    proposition, réveil). Grouper par ``ordre`` rangeait les tâches
    ``generique`` d'ordre 1 et les gestes de visite (ordres 90-92) dans les
    cases des appels : « touche 1 » mélangeait un appel d'ouverture et un
    devis à préparer. La forme ne change pas.
    """
    from django.utils import timezone

    from . import horaires
    from .models import RelanceEtape
    from .suite_touche import q_barreau

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    touches = RelanceEtape.objects.filter(
        company=company, traite_le__gte=depuis,
        statut__in=STATUTS_CLOS_HUMAIN).filter(q_barreau())
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

    COCKPIT-CONTRÔLE B6 — une « touche » est un BARREAU du protocole
    (``suite_touche.q_barreau``) : préparer le devis, planifier la visite ou
    débriefer ne sont pas des relances, ils ne gonflent plus le compte.
    """
    from django.utils import timezone

    from . import stages
    from .models import LeadActivity, RelanceEtape
    from .suite_touche import q_barreau

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
        .filter(q_barreau())
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


#: CAD178 — classification GROSSIÈRE d'un User-Agent HTTP en famille
#: d'appareil, SANS dépendance externe (aucune bibliothèque de parsing tierce
#: à ajouter pour trois catégories). L'ordre compte : une tablette Android se
#: reconnaît d'abord à l'ABSENCE du jeton « Mobile » alors qu'elle contient
#: « Android » — testée AVANT le motif mobile générique.
_RE_TABLETTE = re.compile(
    r'iPad|Tablet|Nexus 7|Nexus 9|Nexus 10|SM-T|Kindle|Silk', re.IGNORECASE)
_RE_MOBILE = re.compile(
    r'Mobi|Android|iPhone|iPod|Windows Phone|BlackBerry', re.IGNORECASE)


def famille_appareil(user_agent):
    """CAD178 — ``'mobile' | 'tablette' | 'ordinateur' | 'inconnu'``.

    Répond à la seule question de CAD86 (« a-t-on une trace d'usage mobile
    sur les écrans de cadence ? »), pas à l'identification d'un modèle
    d'appareil : trois familles suffisent, une quatrième valeur neutre
    couvre l'absence de User-Agent (jamais un défaut « ordinateur » inventé)."""
    from .models import GesteRelanceAppareil

    ua = (user_agent or '').strip()
    if not ua:
        return GesteRelanceAppareil.FamilleAppareil.INCONNU
    if _RE_TABLETTE.search(ua):
        return GesteRelanceAppareil.FamilleAppareil.TABLETTE
    if _RE_MOBILE.search(ua):
        return GesteRelanceAppareil.FamilleAppareil.MOBILE
    return GesteRelanceAppareil.FamilleAppareil.ORDINATEUR


def enregistrer_geste_appareil(company, geste, user_agent):
    """CAD178 — incrémente le compteur du jour (Casablanca) pour
    ``(company, geste, famille_appareil)``. BEST-EFFORT, appelée depuis les
    vues APRÈS le geste métier : une erreur ici (société absente, colonne
    inconnue…) ne doit JAMAIS faire échouer la requête qui l'appelle."""
    from django.db.models import F
    from django.utils import timezone

    from . import horaires
    from .models import GesteRelanceAppareil

    try:
        jour = timezone.now().astimezone(horaires.CASABLANCA).date()
        famille = famille_appareil(user_agent)
        ligne, cree = GesteRelanceAppareil.objects.get_or_create(
            company=company, geste=geste, famille_appareil=famille,
            jour=jour, defaults={'total': 1})
        if not cree:
            GesteRelanceAppareil.objects.filter(pk=ligne.pk).update(
                total=F('total') + 1)
    except Exception:  # noqa: BLE001 — mesure best-effort, jamais bloquante
        logging.getLogger(__name__).warning(
            'CAD178: comptage du geste « %s » non enregistré', geste,
            exc_info=True)


def gestes_par_appareil(company, *, jours=JOURS_MESURE_DEFAUT):
    """CAD178 — ``[{geste, famille_appareil, total}]`` sur la fenêtre, triés
    comme ``taux_joint_par_creneau`` (lisible, jamais un ordre aléatoire de
    base). Liste VIDE tant qu'aucun geste n'a encore été compté — jamais une
    ligne à zéro inventée pour une combinaison qui n'existe pas."""
    from django.db.models import Sum
    from django.utils import timezone

    from .models import GesteRelanceAppareil

    depuis = (timezone.now() - datetime.timedelta(days=int(jours))).date()
    lignes = (GesteRelanceAppareil.objects
              .filter(company=company, jour__gte=depuis)
              .values('geste', 'famille_appareil')
              .annotate(total=Sum('total'))
              .order_by('geste', 'famille_appareil'))
    return [{'geste': ligne['geste'],
             'famille_appareil': ligne['famille_appareil'],
             'total': ligne['total']} for ligne in lignes]


#: AGR540 — l'ordre des entrées de ``par_segment`` (contrat
#: ``mesure_cadence.json``) : les valeurs de ``crm.Lead.TypeInstallation``
#: puis ``non_renseigne``, toujours toutes, même à zéro.
SEGMENTS_MESURE = ('residentiel', 'commercial', 'industriel', 'agricole')
SEGMENT_NON_RENSEIGNE = 'non_renseigne'
#: CIQ518 — les segments PRO (valeurs de ``crm.Lead.TypeInstallation``).
SEGMENTS_PRO_MESURE = ('commercial', 'industriel')


def _segment_de(type_installation):
    valeur = (type_installation or '').strip()
    return valeur if valeur in SEGMENTS_MESURE else SEGMENT_NON_RENSEIGNE


def _mediane_jours(durees):
    """Médiane en jours (1 décimale), ``None`` sur une liste vide."""
    import statistics
    if not durees:
        return None
    return round(statistics.median(durees), 1)


def _jours_entre(debut, fin):
    return (fin - debut).total_seconds() / 86400.0


#: CIQ518 — les CRÉNEAUX de la journée (heure locale de clôture, Casablanca)
#: sous lesquels ``par_segment`` compte les touches jointes : des COMPTES,
#: jamais un pourcentage (61 leads commerciaux, 1 industriel au 03/10/2026 :
#: un taux ne dirait rien). Bornes : matin < 12 h, midi 12 h-14 h, après-midi
#: 14 h-18 h, soir dès 18 h.
CRENEAUX_MESURE = ('matin', 'midi', 'apres_midi', 'soir')


def creneau_de_heure(heure):
    """CIQ518 — le créneau (``CRENEAUX_MESURE``) d'une heure locale 0-23."""
    if heure < 12:
        return 'matin'
    if heure < 14:
        return 'midi'
    if heure < 18:
        return 'apres_midi'
    return 'soir'


def par_segment(company, *, jours=JOURS_MESURE_DEFAUT):
    """AGR540 — les mesures de cadence DÉCOUPÉES par segment (contrat
    ``mesure_cadence.json``, bloc ``par_segment``), en LECTURE SEULE.

    Population : les leads créés sur la fenêtre (archivés et miroir Odoo
    écartés, comme ``part_contact_et_langue``). Les étapes viennent de
    STAGES.py (``stages.COLD`` / ``stages.SIGNED``, jamais un littéral) ; les
    devis, des sélecteurs de ``ventes`` (jamais ses modèles). Aucun seuil,
    aucun réglage : des comptes et des taux, ``None`` dès qu'un dénominateur
    est nul. Une entrée par segment, toujours dans le même ordre, même à 0.
    """
    from django.utils import timezone

    from apps.ventes.selectors import (
        devis_envoyes_par_lead, leads_avec_devis_de_mode,
    )

    from apps.parametres.models_relance import CadenceRelanceEtape

    from . import cadence_temps, horaires, stages
    from .models import Lead, LeadActivity, RelanceEtape
    # AGR520 — l'étiquette « En attente d'un accord » : source unique.
    from .cadence_messages import RAISONS_ATTENTE, TAG_ATTENTE_ACCORD
    from .cadence_reperes import _lead_porte_tag
    from .suite_touche import q_barreau

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    ordre = SEGMENTS_MESURE + (SEGMENT_NON_RENSEIGNE,)
    sortie = {s: {
        'segment': s, 'nb_leads': 0, 'devis_envoyes': 0,
        '_delais_devis': [], '_delais_signature': [], 'signatures': 0,
        '_froids': 0, '_closes': 0, '_joints': 0, '_par_mois': {},
        'en_attente_accord': 0, 'dossiers_subvention': {}, 'incoherents': 0,
        # CIQ518 — ce que le C&I ajoute (comptes seulement, aucun seuil).
        'attente_accord_par_raison': {r[0]: 0 for r in RAISONS_ATTENTE},
        'touches_converties': {'email': 0, 'appel': 0},
        '_creneaux': {c: 0 for c in CRENEAUX_MESURE},
    } for s in ordre}

    leads = list(
        Lead.objects
        .filter(company=company, is_archived=False,
                date_creation__gte=depuis)
        .exclude(source=Lead.Source.ODOO_IMPORT_TEST)
        .only('id', 'type_installation', 'stage', 'tags',
              'dossier_subvention', 'date_creation',
              # CIQ518 — de quoi rejouer la règle de conversion du fixe
              # (`cadence_temps.conversion_numero`, CIQ505).
              'telephone', 'whatsapp', 'email', 'contact_preference',
              'langue_preferee', 'client', 'company'))
    segment_du_lead = {}
    cree_le = {}
    for lead in leads:
        segment = _segment_de(lead.type_installation)
        segment_du_lead[lead.pk] = segment
        cree_le[lead.pk] = lead.date_creation
        bloc = sortie[segment]
        bloc['nb_leads'] += 1
        if lead.stage == stages.COLD:
            bloc['_froids'] += 1
        if _lead_porte_tag(lead, TAG_ATTENTE_ACCORD):
            bloc['en_attente_accord'] += 1
        # CIQ518 — la RAISON de l'attente : l'étiquette posée par CIQ508.
        for valeur, _libelle, etiquette in RAISONS_ATTENTE:
            if _lead_porte_tag(lead, etiquette):
                bloc['attente_accord_par_raison'][valeur] += 1
        if lead.dossier_subvention:
            etats = bloc['dossiers_subvention']
            etats[lead.dossier_subvention] = etats.get(
                lead.dossier_subvention, 0) + 1

    ids = list(segment_du_lead)
    premier_envoi = {}
    for devis in devis_envoyes_par_lead(company, ids):
        lead_id = devis['lead_id']
        sortie[segment_du_lead[lead_id]]['devis_envoyes'] += 1
        if lead_id not in premier_envoi:
            premier_envoi[lead_id] = devis['date_envoi']
    for lead_id, envoi in premier_envoi.items():
        if cree_le.get(lead_id) is not None:
            sortie[segment_du_lead[lead_id]]['_delais_devis'].append(
                max(0.0, _jours_entre(cree_le[lead_id], envoi)))

    non_agricoles = [i for i in ids if segment_du_lead[i] != 'agricole']
    for lead_id in leads_avec_devis_de_mode(company, non_agricoles,
                                            'agricole'):
        sortie[segment_du_lead[lead_id]]['incoherents'] += 1
    # CIQ518 — `incoherents` s'élargit au C&I (drapeau CIQ409 du contrat
    # `lead_pro.json`) : un devis commercial/industriel porté par un lead qui
    # n'est NI commercial NI industriel, compté sous le segment du DEVIS.
    non_pro = [i for i in ids
               if segment_du_lead[i] not in SEGMENTS_PRO_MESURE]
    for mode in SEGMENTS_PRO_MESURE:
        for _lead_id in leads_avec_devis_de_mode(company, non_pro, mode):
            sortie[mode]['incoherents'] += 1

    # Signatures : le passage d'étape vers SIGNED (chatter, STAGES.py fait
    # foi), sur les leads de la population.
    signatures = (LeadActivity.objects
                  .filter(company=company, field='stage',
                          created_at__gte=depuis, lead_id__in=ids,
                          new_value=stages.STAGE_LABELS[stages.SIGNED])
                  .order_by('lead_id', 'created_at')
                  .values('lead_id', 'created_at'))
    signes = set()
    for signature in signatures:
        lead_id = signature['lead_id']
        if lead_id in signes:
            continue
        signes.add(lead_id)
        bloc = sortie[segment_du_lead[lead_id]]
        bloc['signatures'] += 1
        mois = signature['created_at'].astimezone(
            horaires.CASABLANCA).strftime('%Y-%m')
        bloc['_par_mois'][mois] = bloc['_par_mois'].get(mois, 0) + 1
        envoi = premier_envoi.get(lead_id)
        if envoi is not None and signature['created_at'] >= envoi:
            bloc['_delais_signature'].append(
                _jours_entre(envoi, signature['created_at']))

    # Taux de joint : même définition que ``taux_joint_par_creneau``.
    touches = (RelanceEtape.objects
               .filter(company=company, traite_le__gte=depuis,
                       statut__in=STATUTS_CLOS_HUMAIN, lead_id__in=ids)
               .filter(q_barreau()))
    issues = _issues_par_touche(touches, company)
    for ligne in touches.values('id', 'lead_id', 'traite_le'):
        bloc = sortie[segment_du_lead[ligne['lead_id']]]
        bloc['_closes'] += 1
        if issues.get(ligne['id'], '') in ISSUES_JOINT:
            bloc['_joints'] += 1
            # CIQ518 — les joints par CRÉNEAU (compte, jamais un %).
            if ligne['traite_le'] is not None:
                heure = ligne['traite_le'].astimezone(
                    horaires.CASABLANCA).hour
                bloc['_creneaux'][creneau_de_heure(heure)] += 1

    # CIQ518 — les touches CONVERTIES sur numéro fixe (convention 8) : la
    # MÊME fonction pure que le moteur et l'écran. Une touche née WhatsApp au
    # protocole de la société, aujourd'hui e-mail ou appel avec sa clé, est
    # comptée UNE fois.
    protocole = {
        (cadence, rang): canal for cadence, rang, canal in
        CadenceRelanceEtape.objects.filter(company=company, actif=True)
        .values_list('cadence', 'ordre', 'canal')}
    leads_par_id = {lead.pk: lead for lead in leads}
    converties = (RelanceEtape.objects
                  .filter(company=company, lead_id__in=ids,
                          canal__in=(cadence_temps.CANAL_EMAIL,
                                     cadence_temps.CANAL_APPEL))
                  .exclude(template_cle='')
                  .values('lead_id', 'cadence', 'ordre', 'canal',
                          'template_cle'))
    for touche in converties:
        if protocole.get((touche['cadence'], touche['ordre'])) \
                != cadence_temps.CANAL_WHATSAPP:
            continue
        conversion = cadence_temps.conversion_numero(
            leads_par_id[touche['lead_id']], touche['template_cle'])
        if conversion is not None and conversion[0] == touche['canal']:
            sortie[segment_du_lead[touche['lead_id']]][
                'touches_converties'][touche['canal']] += 1

    resultat = []
    for segment in ordre:
        bloc = sortie[segment]
        resultat.append({
            'segment': segment,
            'nb_leads': bloc['nb_leads'],
            'devis_envoyes': bloc['devis_envoyes'],
            'delai_median_premier_devis_jours': _mediane_jours(
                bloc['_delais_devis']),
            'delai_median_signature_jours': _mediane_jours(
                bloc['_delais_signature']),
            'signatures': bloc['signatures'],
            'taux_froid_pct': _pct(bloc['_froids'], bloc['nb_leads']),
            'taux_joint_pct': _pct(bloc['_joints'], bloc['_closes']),
            'signatures_par_mois': [
                {'mois': mois, 'signatures': nombre}
                for mois, nombre in sorted(bloc['_par_mois'].items())],
            'en_attente_accord': bloc['en_attente_accord'],
            'dossiers_subvention': dict(sorted(
                bloc['dossiers_subvention'].items())),
            'incoherents': bloc['incoherents'],
            'attente_accord_par_raison': dict(
                bloc['attente_accord_par_raison']),
            'touches_converties': dict(bloc['touches_converties']),
            # `null` quand AUCUNE touche n'a été tentée (dénominateur nul),
            # jamais des zéros qui se liraient comme un échec.
            'joints_par_creneau': (dict(bloc['_creneaux'])
                                   if bloc['_closes'] else None),
            'delais_signature_jours': sorted(
                round(d, 1) for d in bloc['_delais_signature']),
        })
    return resultat


def mesure_cadence(company, *, jours=JOURS_MESURE_DEFAUT):
    """Les mesures de CAD87 (+ CAD178), en une seule lecture (forme du
    contrat).

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
        # CAD178 — additif : les 4 gestes clés, par famille d'appareil.
        'gestes_par_appareil': gestes_par_appareil(company, jours=jours),
        # AGR540 — additif : les mêmes mesures découpées par segment.
        'par_segment': par_segment(company, jours=jours),
    }
