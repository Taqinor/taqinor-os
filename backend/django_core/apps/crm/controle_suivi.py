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
humain, CKP1). Les annulations du MOTEUR (``annulee``) sortent du
dénominateur.

LE RETARD SE COMPTE EN JOURS OUVRÉS (contrat v2, ``notes.retard``) : un JOUR
COMPTÉ est un jour ouvré de la société (``notifications.calendar_utils``)
que n'excuse aucune absence déclarée du responsable du lead
(``cadence_absence``, fermetures de société comprises) — ``_jours_comptes``,
LA fonction, écrite une fois. Une étape OUVERTE n'est « en retard » (jugée
« ouvert ») qu'à partir d'un jour compté après son échéance ; à 0 (du jour,
ou échue la veille d'un week-end, d'un férié ou d'une absence) elle n'est PAS
jugée : ni au verdict, ni au détail par type, ni aux exceptions — seule la
case de son jour la compte (« en cours »). L'ancienneté d'une TÂCHE se compte
de la même façon depuis sa pose. Les jours ouvrés sont lus EN LOT
(``calendar_utils.jours_ouvres_entre``) : le nombre de requêtes ne dépend ni
du nombre d'étapes, ni du nombre de dossiers.

LE DÉLAI DE PREMIER CONTACT (B9, ``notes.exceptions`` et
``notes.premier_contact``) a UNE horloge : les heures d'HORLOGE, jours non
ouvrés de la société retirés en entier (``horaires.
minutes_jours_ouvres_entre``) — un lead du lundi 10 h, délai 24 h, est hors
délai le mardi 10 h, comme sur la tuile « SLA premier contact » voisine ;
celui du vendredi 18 h, le lundi 18 h. Les absences personnelles n'y
retirent rien. Seule la médiane de VITESSE reste en minutes OUVRÉES.

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


#: AGR542 (contrat ``controle_suivi.json``) — les segments admis par
#: ``?segment=`` : les valeurs de ``crm.Lead.TypeInstallation`` puis
#: ``non_renseigne`` (type vide). Absent = tous les segments.
SEGMENTS_ADMIS = ('residentiel', 'commercial', 'industriel', 'agricole',
                  'non_renseigne')
SEGMENT_NON_RENSEIGNE = 'non_renseigne'


def parametre_segment(segment_brut=None):
    """AGR542 — ``(segment, erreur)`` depuis ``?segment=``.

    Absent ou vide → ``(None, None)`` (tous les segments, comportement
    inchangé) ; une valeur hors ``SEGMENTS_ADMIS`` → refus nommé (la vue le
    sert en 400 sous la clé ``segment``)."""
    brut = str(segment_brut if segment_brut is not None else '').strip()
    if not brut:
        return None, None
    if brut in SEGMENTS_ADMIS:
        return brut, None
    return None, (f'Segment inconnu : « {brut} ». Valeurs admises : '
                  + ', '.join(SEGMENTS_ADMIS) + '.')


def filtrer_par_segment(leads, segment):
    """AGR542 — restreint un queryset de leads à ``segment`` (``None`` =
    inchangé ; ``non_renseigne`` = type vide ou nul)."""
    from django.db.models import Q

    if not segment:
        return leads
    if segment == SEGMENT_NON_RENSEIGNE:
        return leads.filter(Q(type_installation__isnull=True)
                            | Q(type_installation=''))
    return leads.filter(type_installation=segment)


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


def _jours_comptes(apres, jusqu_a, owner_id, ouvres, absences):
    """LA règle du retard (contrat v2, ``notes.retard``) : le nombre de
    JOURS COMPTÉS ``d`` avec ``apres < d <= jusqu_a`` — un jour ouvré de la
    société (``ouvres``, lu en lot) que n'excuse aucune absence déclarée de
    ``owner_id`` (ni fermeture de la société). Pur : aucune requête."""
    compte = 0
    jour = apres + datetime.timedelta(days=1)
    while jour <= jusqu_a:
        if jour in ouvres and not absences.couvre(owner_id, jour):
            compte += 1
        jour += datetime.timedelta(days=1)
    return compte


def _juger(etape, today, absences, proprietaire, ouvres):
    """Le jugement d'une étape due (voir l'en-tête du module) : ``A_TEMPS``,
    ``EN_RETARD``, ``SAUTEES``, ``OUVERT`` (ouverte ET en retard d'au moins
    un jour compté), ou ``None`` — une étape ouverte pas encore en retard
    n'est pas jugée."""
    from .models import RelanceEtape
    from .selectors import _a_lheure_ou_excusee

    if etape.statut == RelanceEtape.Statut.FAIT:
        return (A_TEMPS if _a_lheure_ou_excusee(etape, absences, proprietaire)
                else EN_RETARD)
    if etape.statut == RelanceEtape.Statut.SAUTEE:
        return SAUTEES
    if _jours_comptes(etape.due_date, today, proprietaire.get(etape.lead_id),
                      ouvres, absences) >= 1:
        return OUVERT
    return None


# ── ALEA32 — LA définition publique de « en retard » ────────────────────────
#
# Une seule règle pour le badge ``overdue``, le drapeau ``touche_en_retard``,
# le scope ``overdue``, la chaîne commerciale, le digest de 08:30 et le
# cockpit : une étape OUVERTE est en retard dès qu'au moins UN jour COMPTÉ
# (``_jours_comptes`` : jour ouvré de la société, hors absence déclarée du
# responsable et hors fermeture de la société) sépare son échéance
# d'aujourd'hui. Une touche due le vendredi n'est donc pas en retard le
# dimanche ; elle l'est le lundi.

#: Taille d'une fenêtre de recherche du dernier jour compté (``seuil_retard``)
#: et nombre maximal de fenêtres lues (≈ un an) — une société sans aucun jour
#: ouvré sur un an n'a, par construction, rien « en retard ».
_SEUIL_FENETRE_JOURS = 31
_SEUIL_FENETRES_MAX = 12


def seuil_retard(company, aujourd_hui):
    """ALEA32 — le seuil des FILTRES SQL : une étape ``a_faire`` est en
    retard ssi ``due_date < seuil_retard(company, aujourd_hui)``.

    Le seuil est le dernier JOUR COMPTÉ du calendrier de la société (jour
    ouvré, hors fermeture de toute la société) au plus tard ``aujourd_hui`` :
    pour toute échéance ``d``, ``_jours_comptes(d, aujourd_hui, None, …) >= 1``
    ⇔ ``d < seuil``. Les absences PERSONNELLES ne peuvent pas entrer dans un
    filtre qui ne connaît pas le responsable : ``etape_en_retard`` les lit,
    étape par étape. Deux ou trois requêtes, jamais une par jour."""
    from apps.notifications.calendar_utils import jours_ouvres_entre

    from . import cadence_absence

    fin = aujourd_hui
    for _ in range(_SEUIL_FENETRES_MAX):
        debut = fin - datetime.timedelta(days=_SEUIL_FENETRE_JOURS - 1)
        ouvres = jours_ouvres_entre(company, debut, fin)
        fermetures = cadence_absence.couverture(
            company, debut, fin, utilisateurs=())
        jour = fin
        while jour >= debut:
            if jour in ouvres and not fermetures.couvre(None, jour):
                return jour
            jour -= datetime.timedelta(days=1)
        fin = debut - datetime.timedelta(days=1)
    return datetime.date.min


def etape_en_retard(etape, maintenant=None, *, memo=None, aujourd_hui=None):
    """ALEA32 — vrai ssi l'étape est OUVERTE (``a_faire``) et qu'au moins un
    jour COMPTÉ (``_jours_comptes`` : jour ouvré de la société, hors absence
    déclarée du responsable du lead et hors fermeture) sépare son échéance
    d'aujourd'hui (jour Africa/Casablanca de ``maintenant``, ou
    ``aujourd_hui`` quand l'appelant a déjà fixé le jour).

    ``memo`` (un ``dict`` facultatif, ex. le contexte d'un sérialiseur de
    liste) garde le calendrier et les absences déjà lus : une liste de N
    étapes ne relit pas N fois les mêmes jours ouvrés."""
    from core.dates import aujourd_hui_local

    from apps.notifications.calendar_utils import jours_ouvres_entre

    from . import cadence_absence
    from .models import RelanceEtape

    if etape.statut != RelanceEtape.Statut.A_FAIRE or etape.due_date is None:
        return False
    today = (aujourd_hui if aujourd_hui is not None
             else aujourd_hui_local(maintenant))
    if etape.due_date >= today:
        return False
    memo = {} if memo is None else memo
    cle = ('alea32', etape.company_id, today)
    lu = memo.get(cle)
    debut = etape.due_date + datetime.timedelta(days=1)
    if lu is None or lu[0] > debut:
        borne = debut if lu is None else min(debut, lu[0])
        lu = (borne,
              jours_ouvres_entre(etape.company_id, borne, today),
              cadence_absence.couverture(etape.company_id, borne, today))
        memo[cle] = lu
    _, ouvres, absences = lu
    return _jours_comptes(etape.due_date, today, etape.lead.owner_id,
                          ouvres, absences) >= 1


def _compteurs():
    return {'du': 0, A_TEMPS: 0, EN_RETARD: 0, SAUTEES: 0, OUVERT: 0}


def _etat_du_jour(case, ouvertes_en_retard):
    """``jours.etat`` (contrat, ``notes.jours.etat``) : ``rouge`` s'il reste
    une étape ouverte EN RETARD de ce jour-là, ``en_cours`` s'il en reste
    d'ouvertes dont aucune n'est encore en retard (aujourd'hui, ou un jour
    passé sans jour compté depuis)."""
    if not case['du']:
        return ETAT_VIDE
    if case[OUVERT]:
        return ETAT_ROUGE if ouvertes_en_retard else ETAT_EN_COURS
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
        # Contrat v2 — toute ligne d'étape porte ses reports humains.
        'nb_reports': etape.nb_reports,
    }
    ligne.update(extra)
    return ligne


def _liste(lignes, owner):
    """``{total, lignes}`` d'une liste d'exceptions ``[(owner_id, ligne)]``
    filtrée sur ``owner`` — ``total`` exact, 10 lignes au plus."""
    retenues = [ligne for proprietaire, ligne in lignes
                if owner is None or proprietaire == owner]
    return {'total': len(retenues), 'lignes': retenues[:LIGNES_MAX]}


def _liste_reports(lignes, owner):
    """``{total, plusieurs_fois, lignes}`` de la liste des étapes reportées :
    ``total`` = toutes (dès le premier report), ``plusieurs_fois`` = celles
    qui l'ont été ``REPORTS_MIN`` fois ou plus — c'est ce compte-là qui fait
    passer le verdict à « attention », un report unique est seulement listé."""
    retenues = [ligne for proprietaire, ligne in lignes
                if owner is None or proprietaire == owner]
    return {
        'total': len(retenues),
        'plusieurs_fois': sum(
            1 for ligne in retenues if ligne['nb_reports'] >= REPORTS_MIN),
        'lignes': retenues[:LIGNES_MAX],
    }


# ── Les exceptions de l'instant (toute la portée ; ``owner`` filtre après) ──

def _en_retard(etapes_echues, today, absences, ouvres):
    """Étapes ouvertes (touches ET tâches) en retard d'au moins UN jour
    compté ; ``jours_de_retard`` = ce nombre de jours OUVRÉS. Une étape échue
    pendant une absence devient en retard au premier jour compté après le
    retour — l'absence n'efface plus le retard, elle en retient les jours."""
    lignes = []
    for etape in etapes_echues:
        retard = _jours_comptes(etape.due_date, today, etape.lead.owner_id,
                                ouvres, absences)
        if retard < 1:
            continue                    # aucun jour compté : pas en retard
        lignes.append((etape.lead.owner_id, _ligne_etape(
            etape, {'jours_de_retard': retard})))
    return lignes


def _taches_ouvertes_anciennes(company, portee_ids, today):
    """Les TÂCHES ouvertes posées au plus tard l'avant-veille, par date de
    pose croissante — le pré-filtre SQL de ``taches_en_attente`` (un jour
    compté n'est jamais plus qu'un jour calendaire)."""
    from .models import RelanceEtape
    from .suite_touche import q_tache

    seuil = _debut_du_jour(
        today - datetime.timedelta(days=TACHE_ATTENTE_JOURS - 1))
    return list(RelanceEtape.objects
                .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                        lead_id__in=portee_ids, created_at__lt=seuil)
                .filter(q_tache())
                .select_related('lead', 'lead__owner')
                .order_by('created_at', 'pk'))


def _taches_en_attente(taches, today, absences, ouvres):
    """TÂCHES ouvertes posées depuis ``TACHE_ATTENTE_JOURS`` jours OUVRÉS ou
    plus (comptés comme le retard), quelle que soit leur échéance : un
    report ne les en sort pas."""
    lignes = []
    for etape in taches:
        attente = _jours_comptes(_jour_local(etape.created_at), today,
                                 etape.lead.owner_id, ouvres, absences)
        if attente < TACHE_ATTENTE_JOURS:
            continue
        lignes.append((etape.lead.owner_id, _ligne_etape(
            etape, {'ouverte_depuis_jours': attente})))
    return lignes


def _reports(company, portee_ids):
    """Étapes OUVERTES dont l'échéance a été repoussée AU MOINS UNE FOIS par
    un geste humain, la plus ancienne origine d'abord — toutes, dès le premier
    report : une étape en retard qu'on reporte quitte ``en_retard``, elle ne
    disparaît pas. Le NIVEAU, lui, ne bouge qu'à ``REPORTS_MIN`` reports
    (``plusieurs_fois``, compté dans ``controle_suivi``)."""
    from django.db.models import F
    from django.db.models.functions import Coalesce

    from .models import RelanceEtape

    etapes = (RelanceEtape.objects
              .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                      lead_id__in=portee_ids, nb_reports__gte=1)
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


def _candidats_premier_contact(company, portee_ids, maintenant, sla):
    """Le PRÉ-FILTRE de ``premier_contact_hors_delai`` : la règle de
    ``sla-breach`` (``selectors.leads_sla_depasse`` — heures calendaires,
    0 = désactivé → liste vide), le plus ancien d'abord. L'horloge du délai
    retire des jours, elle n'en ajoute jamais : aucun lead hors délai n'est
    perdu par ce pré-filtre. Le miroir Odoo, les leads perdus et « ne plus
    contacter » n'attendent personne."""
    if not sla:
        return []
    from .models import Lead
    from .selectors import leads_sla_depasse

    return list(leads_sla_depasse(company, now=maintenant, seuil_heures=sla)
                .filter(id__in=portee_ids, perdu=False,
                        ne_plus_contacter=False)
                .exclude(source=Lead.Source.ODOO_IMPORT_TEST)
                .select_related('owner')
                .order_by('date_creation', 'pk'))


def _premier_contact_hors_delai(candidats, company, maintenant, sla, ouvres):
    """Leads « Nouveau » jamais contactés dont l'ATTENTE atteint le délai de
    la société (contrat, ``notes.exceptions``) — l'attente en heures
    d'HORLOGE, jours NON ouvrés retirés (``horaires.
    minutes_jours_ouvres_entre``, B9) : un lead du vendredi 18 h, délai
    24 h, est hors délai lundi 18 h. Les absences personnelles ne retirent
    rien : un lead neuf doit être repris. ``attend_depuis_heures`` = cette
    attente."""
    from . import horaires
    from .serializers import nom_affichable_lead, nom_affichable_responsable

    lignes = []
    for lead in candidats:
        minutes = horaires.minutes_jours_ouvres_entre(
            lead.date_creation, maintenant, company, ouvres=ouvres)
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

def _mesure_de_la_periode(etapes, today, absences, proprietaire, ouvres):
    """``(cases_par_jour, ouvertes_en_retard_par_jour, verdict, par_type)``
    sur les étapes dues de la période (déjà filtrées sur ``owner``,
    annulations exclues).

    Une case compte TOUTES les étapes de son jour (jugées ou non) ; le
    verdict et le détail par type ne comptent que les étapes JUGÉES, et
    ``reportees`` = celles d'entre elles repoussées au moins une fois par un
    geste humain (``nb_reports`` ≥ 1) — un fait montré à côté du
    pourcentage, jamais retranché de lui."""
    from .models import RelanceEtape
    from .suite_touche import type_etape_connu

    cases = {}
    en_retard_du_jour = {}
    verdict = dict(_compteurs(), reportees=0)
    par_type = {}
    for etape in etapes:
        jugement = _juger(etape, today, absences, proprietaire, ouvres)
        case = cases.setdefault(etape.due_date, _compteurs())
        case['du'] += 1
        if jugement is None:
            # Ouverte, pas encore en retard : la case la compte, le
            # jugement non (contrat v2, `notes.retard`).
            if etape.statut == RelanceEtape.Statut.A_FAIRE:
                case[OUVERT] += 1
            continue
        case[jugement] += 1
        if jugement == OUVERT:
            en_retard_du_jour[etape.due_date] = (
                en_retard_du_jour.get(etape.due_date, 0) + 1)
        reportee = (etape.nb_reports or 0) >= 1
        verdict['du'] += 1
        verdict[jugement] += 1
        verdict['reportees'] += reportee
        ligne = par_type.setdefault(type_etape_connu(etape), {
            'compteurs': dict(_compteurs(), reportees=0), 'reponses': {}})
        ligne['compteurs']['du'] += 1
        ligne['compteurs'][jugement] += 1
        ligne['compteurs']['reportees'] += reportee
        if jugement in (A_TEMPS, EN_RETARD):
            cle = (etape.outcome or '').strip() or 'sans_issue'
            ligne['reponses'][cle] = ligne['reponses'].get(cle, 0) + 1
    return cases, en_retard_du_jour, verdict, par_type


def _a_temps_pct(etapes, today, absences, proprietaire, ouvres):
    """La même mesure qu'au verdict (même jugement, mêmes étapes non jugées
    écartées), sur la période précédente."""
    jugements = [j for j in (_juger(e, today, absences, proprietaire, ouvres)
                             for e in etapes) if j is not None]
    return _pct(sum(1 for j in jugements if j == A_TEMPS), len(jugements))


def _lignes_par_type(par_type):
    """``par_type`` dans l'ORDRE de la table du parcours ; un type sans étape
    JUGÉE n'est pas servi ; ``reportees`` comme au verdict ; ``reponses`` par
    effectif décroissant."""
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
            'reportees': compteurs['reportees'],
            'reponses': [
                {'cle': cle, 'n': n} for cle, n in sorted(
                    bloc['reponses'].items(),
                    key=lambda paire: (-paire[1], paire[0]))],
        })
    return lignes


def _premier_contact(portee, owner, debut, maintenant, sla, company, ouvres):
    """Leads CRÉÉS sur la période (hors miroir Odoo). Deux horloges, chacune
    à sa place (contrat, ``notes.premier_contact``) :

    * le DÉLAI (``dans_le_delai``, ``plus_longue_attente_heures``) : la
      même horloge que l'exception — heures d'horloge, jours non ouvrés
      retirés (``horaires.minutes_jours_ouvres_entre``, B9) ;
    * la VITESSE (``mediane_minutes``) : minutes OUVRÉES
      (``horaires.minutes_ouvrees_entre``) — le KPI « rappelé en moins de
      5 min ouvrées » ; la médiane, jamais la moyenne."""
    from . import horaires, stages
    from .models import Lead
    from .selectors import _mediane

    leads = (portee.filter(date_creation__gte=_debut_du_jour(debut))
             .exclude(source=Lead.Source.ODOO_IMPORT_TEST))
    if owner is not None:
        leads = leads.filter(owner_id=owner)
    nouveaux = 0
    delais = []
    dans_le_delai = 0
    attentes = []
    for lead in leads.only('id', 'date_creation', 'first_contacted_at',
                           'stage', 'perdu', 'ne_plus_contacter'):
        nouveaux += 1
        if lead.first_contacted_at is not None:
            delais.append(horaires.minutes_ouvrees_entre(
                lead.date_creation, lead.first_contacted_at, company))
            if sla and horaires.minutes_jours_ouvres_entre(
                    lead.date_creation, lead.first_contacted_at, company,
                    ouvres=ouvres) < sla * 60:
                dans_le_delai += 1
        elif (lead.stage == stages.NEW and not lead.perdu
              and not lead.ne_plus_contacter):
            attentes.append(horaires.minutes_jours_ouvres_entre(
                lead.date_creation, maintenant, company, ouvres=ouvres))
    return {
        'nouveaux': nouveaux,
        'dans_le_delai': dans_le_delai,
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
                   maintenant=None, segment=None):
    """Le bloc « Contrôle du suivi » — EXACTEMENT la forme de
    ``contract_samples/controle_suivi.json``.

    ``jours`` ∈ ``JOURS_AUTORISES`` et ``owner`` (un responsable de la portée,
    ou ``None``) sont validés par ``parametres_controle`` en amont.
    AGR542 — ``segment`` (validé par ``parametre_segment``) restreint la
    PORTÉE aux leads de ce segment : toutes les listes et tous les compteurs
    en découlent ; aucune règle de mesure ne change. Servi en écho.
    ``maintenant`` (instant aware) est injectable pour les tests ; le JOUR est
    celui d'Africa/Casablanca."""
    from django.utils import timezone

    from apps.notifications.calendar_utils import jours_ouvres_entre
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
        filtrer_par_segment(
            Lead.objects.filter(company=company, is_archived=False), segment),
        user, ['owner'])
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
                  'libelle', 'cadence', 'canal', 'outcome', 'nb_reports'))
        etapes_echues = list(
            RelanceEtape.objects
            .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                    lead_id__in=portee_ids, due_date__lt=today)
            .select_related('lead', 'lead__owner')
            .order_by('due_date', 'due_at', 'pk'))
        taches_anciennes = _taches_ouvertes_anciennes(
            company, portee_ids, today)
        candidats = _candidats_premier_contact(
            company, portee_ids, maintenant, sla)
        # CAD35 + calendrier de la société — chargés UNE fois, EN LOT, sur la
        # fenêtre que les chiffres couvrent réellement : la plus ancienne des
        # deux périodes, la plus ancienne échéance en retard, la plus
        # ancienne tâche ouverte, le plus ancien lead qui attend son premier
        # contact (jamais une durée inventée).
        borne = min([debut_precedent]
                    + [e.due_date for e in etapes_echues]
                    + [_jour_local(t.created_at) for t in taches_anciennes]
                    + [_jour_local(lead.date_creation) for lead in candidats])
        absences = cadence_absence.couverture(company, borne, today)
        ouvres = jours_ouvres_entre(company, borne, today)

        en_retard = _en_retard(etapes_echues, today, absences, ouvres)
        taches = _taches_en_attente(taches_anciennes, today, absences, ouvres)
        reports = _reports(company, portee_ids)
        sans_etape = _sans_prochaine_etape(company, portee, today)
        hors_delai = _premier_contact_hors_delai(
            candidats, company, maintenant, sla, ouvres)

        periode = [e for e in dues if e.due_date >= debut
                   and (owner is None or proprietaire.get(e.lead_id) == owner)]
        precedente = [e for e in dues if e.due_date < debut
                      and (owner is None
                           or proprietaire.get(e.lead_id) == owner)]
        cases, en_retard_du_jour, verdict, par_type = _mesure_de_la_periode(
            periode, today, absences, proprietaire, ouvres)

        exceptions = {
            'en_retard': _liste(en_retard, owner),
            'taches_en_attente': _liste(taches, owner),
            # Toutes les étapes reportées sont listées ; `plusieurs_fois` dit
            # combien l'ont été `REPORTS_MIN` fois ou plus (sur TOUTE la liste
            # du commercial lu, pas sur les seules lignes servies).
            'reports': _liste_reports(reports, owner),
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
              or exceptions['reports']['plusieurs_fois']):
            niveau = NIVEAU_ATTENTION
        elif (not any(case['du'] for case in cases.values())
              and not exceptions['reports']['total']):
            niveau = NIVEAU_VIDE
        else:
            niveau = NIVEAU_OK

        # Une case par jour calendaire, du plus ancien à aujourd'hui (« pas
        # encore de données » quand le verdict est vide : aucune case, comme
        # `exemple_vide`). `ouvre` : le calendrier de la société, lu en lot
        # (`notifications.calendar_utils.jours_ouvres_entre`).
        frise = []
        if niveau != NIVEAU_VIDE:
            for decalage in range(jours):
                jour = debut + datetime.timedelta(days=decalage)
                case = cases.get(jour, _compteurs())
                frise.append({
                    'date': jour.isoformat(),
                    'ouvre': jour in ouvres,
                    'aujourdhui': jour == today,
                    'du': case['du'],
                    A_TEMPS: case[A_TEMPS],
                    EN_RETARD: case[EN_RETARD],
                    SAUTEES: case[SAUTEES],
                    OUVERT: case[OUVERT],
                    'etat': _etat_du_jour(
                        case, en_retard_du_jour.get(jour, 0)),
                })

        premier_contact = _premier_contact(
            portee, owner, debut, maintenant, sla, company, ouvres)
        precedent_pct = _a_temps_pct(precedente, today, absences,
                                     proprietaire, ouvres)

    concernes = {proprietaire.get(e.lead_id) for e in dues
                 if e.due_date >= debut}
    for lignes in (en_retard, taches, reports, sans_etape, hors_delai):
        concernes.update(proprietaire_id for proprietaire_id, _l in lignes)

    return {
        'periode_jours': jours,
        'owner': owner,
        # AGR542 — écho du paramètre (``None`` = tous les segments).
        'segment': segment,
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
            'reportees': verdict['reportees'],
            'a_temps_pct': _pct(verdict[A_TEMPS], verdict['du']),
            'precedent_a_temps_pct': precedent_pct,
        },
        'jours': frise,
        'exceptions': exceptions,
        'par_type': _lignes_par_type(par_type),
        'premier_contact': premier_contact,
        'resultats': _resultats(company, portee, owner, debut),
    }
