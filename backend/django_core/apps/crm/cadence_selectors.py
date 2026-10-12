"""Lectures cadence (SPL83, scission de `selectors.py`) : KPI, adhérence,
cockpit, file du jour, journal, chaîne commerciale, cadences échues.

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.
"""
import datetime

from .portee_selectors import (
    portee_leads, leads_visibles,
)


#: MRY21 — la promesse mesurée : joindre le prospect dans les 5 jours OUVRÉS.
JOURS_OUVRES_JOINDRE = 5


def _minutes_ouvrees_de_5_jours(creation, company, *, fins=None):
    """Le seuil « 5 jours ouvrés », EXPRIMÉ en minutes ouvrées.

    Comparer des minutes ouvrées à ``5 * 24 * 60`` mélangeait deux unités :
    7 200 minutes de calendrier valent ~10 jours ouvrés de 11 h 30, soit le
    DOUBLE de la promesse — le KPI se donnait deux fois plus de temps qu'il
    n'en annonçait. On mesure donc la même chose des deux côtés : les minutes
    ouvrées séparant la création de la FERMETURE du 5ᵉ jour ouvré suivant.

    ``fins`` (facultatif) est un dictionnaire ``{date locale: fermeture du
    5ᵉ jour ouvré}`` que l'appelant réutilise d'un lead à l'autre :
    ``ajouter_jours_ouvres`` recharge les jours ouvrés et trois années de
    fériés À CHAQUE APPEL (4 requêtes), et ce calcul ne dépend QUE de la date
    de création — mémoriser par date rend le coût indépendant du nombre de
    leads. Sans ``fins``, comportement identique à avant."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from . import horaires

    local = creation.astimezone(horaires.CASABLANCA)
    fin = fins.get(local.date()) if fins is not None else None
    if fin is None:
        jour_fin = ajouter_jours_ouvres(
            local.date(), JOURS_OUVRES_JOINDRE, company)
        fenetre = horaires.fenetre_du_jour(jour_fin, company)
        fermeture = fenetre[1] if fenetre else datetime.time(20, 0)
        fin = datetime.datetime.combine(
            jour_fin, fermeture, tzinfo=horaires.CASABLANCA)
        if fins is not None:
            fins[local.date()] = fin
    return horaires.minutes_ouvrees_entre(creation, fin, company)


def kpi_cadences(company, *, jours=30):
    """MRY21 — Les sept chiffres du bilan de cadence (forme `kpi_cadences`).

    Lus à la fois par le panneau du Cockpit et par le bilan hebdomadaire du
    lundi. Trois règles les rendent honnêtes :

    * ``null`` dès que le DÉNOMINATEUR est 0 — jamais un 0 % qui se lirait
      comme un échec là où il n'y a simplement rien à mesurer ;
    * les devis sont comptés via ``apps.ventes.selectors``, JAMAIS un import
      de ``ventes.models`` (frontière M3) ;
    * les tentatives comptées sont HUMAINES (MRY20) — une moyenne gonflée par
      les lignes système ne dirait rien de l'effort réel.
    """
    from django.db.models import Count, Min, Q
    from django.utils import timezone

    from . import horaires, stages
    from .models import Lead, LeadActivity, RelanceEtape

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    # CAD87 — le miroir Odoo et les archivés sont ÉCARTÉS, comme les deux KPI
    # voisins le font déjà (`kpi_premier_contact`, `kpi_adherence`). Sans ce
    # filtre, un import de rattrapage faisait plonger « joints sous 5 jours »
    # trente jours durant sans qu'aucun comportement n'ait changé : ces leads
    # ne sont pas une file que la commerciale doit rappeler (`services.py`
    # les exclut d'ailleurs de toute cadence automatique). L'exclusion porte
    # sur la SOURCE Odoo seule, et non sur « source = créé dans TAQINOR » :
    # les leads du site et de Meta, eux, SONT dans la file du jour.
    leads = (Lead.objects
             .filter(company=company, is_archived=False,
                     date_creation__gte=depuis)
             .exclude(source=Lead.Source.ODOO_IMPORT_TEST))
    nb_leads = leads.count()

    # « Joint » = une issue d'appel joint/intéressé dans les 5 jours OUVRÉS
    # suivant la création. Le délai est OUVRÉ pour la même raison que le KPI
    # de premier contact : un week-end n'est pas du temps perdu. Le SEUIL doit
    # l'être aussi : comparer des minutes OUVRÉES à `5 * 24 * 60` (7 200
    # minutes de calendrier) revenait à accorder ~10 jours ouvrés de 11 h 30 —
    # deux fois la promesse. Le seuil est donc lui-même compté en minutes
    # ouvrées, jusqu'à la fermeture du 5ᵉ jour ouvré.
    # CAD87 — une seule requête GROUPÉE pour les premières issues, là où le
    # code interrogeait la base UNE FOIS PAR LEAD : sur 900 leads le panneau
    # du Cockpit tirait 900 requêtes. La fenêtre ouvrée, elle, reste calculée
    # en Python (elle dépend des horaires de la société).
    premieres_issues = dict(
        LeadActivity.objects
        .filter(company=company, lead_id__in=leads.values('id'),
                outcome__in=('joint', 'interesse'), user__isnull=False)
        .values('lead_id').annotate(premiere=Min('created_at'))
        .values_list('lead_id', 'premiere'))
    joints = 0
    # CAD87 (correctif de budget) — la fenêtre ouvrée se calcule en Python,
    # mais chacun de ses appels RELISAIT la base : profil société, jours
    # ouvrés et fériés étaient rechargés pour chaque lead et chaque jour
    # parcouru (~34 requêtes par lead joint — le compte du panneau grandissait
    # encore avec le nombre de leads, ce que la requête groupée ci-dessus
    # était censée arrêter). `cache_local()` est exactement l'outil prévu par
    # `horaires` pour une opération longue (profil/jours ouvrés/fériés
    # mémorisés le temps du bloc, oubliés ensuite) ; `fins` mémorise le 5ᵉ
    # jour ouvré par DATE de création, seul paramètre dont il dépend.
    fins_5e_jour = {}
    with horaires.cache_local():
        # CAD119 — `date_creation_origine` chargée avec le reste : le délai se
        # compte depuis la naissance du dossier (`Lead.date_origine`), jamais
        # depuis l'heure d'une synchronisation.
        for lead in leads.only('id', 'date_creation',
                               'date_creation_origine'):
            premiere = premieres_issues.get(lead.id)
            if premiere is None:
                continue
            naissance = lead.date_origine
            minutes = horaires.minutes_ouvrees_entre(
                naissance, premiere, company)
            seuil = _minutes_ouvrees_de_5_jours(
                naissance, company, fins=fins_5e_jour)
            if minutes <= seuil:
                joints += 1

    touches = RelanceEtape.objects.filter(company=company,
                                          traite_le__gte=depuis)
    # « Cadence menée à son terme » = ce lead a des touches `contact`
    # TRAITÉES sur la période et plus AUCUNE ouverte. Écrit en deux requêtes
    # simples plutôt qu'en une agrégation à double traversée : le chiffre
    # doit être lisible par qui le relit, sinon personne ne peut le vérifier.
    traites = set(
        touches.filter(cadence='contact', statut=RelanceEtape.Statut.FAIT)
        .values_list('lead_id', flat=True))
    encore_ouverts = set(
        RelanceEtape.objects.filter(
            company=company, cadence='contact',
            statut=RelanceEtape.Statut.A_FAIRE,
            lead_id__in=traites).values_list('lead_id', flat=True))
    cadences_completes = len(traites - encore_ouverts)
    # CKP1 — le proxy s'appuie désormais sur le STATUT structuré : seule une
    # touche ANNULÉE (moteur) peut venir d'un arrêt de cadence. Avant, un
    # commercial qui sautait une touche à la main en notant « pas joint »
    # gonflait ce chiffre ; et la note reste filtrée parce que le moteur
    # annule aussi pour « lead signé », « reprise : déjà passée », etc.
    cadences_arretees_joint = touches.filter(
        statut=RelanceEtape.Statut.ANNULEE, note__icontains='joint').count()

    perdus = leads.filter(perdu=True)
    nb_perdus = perdus.count()
    perdus_avec_motif = perdus.exclude(
        Q(motif_perte__isnull=True) | Q(motif_perte='')).count()

    signatures = LeadActivity.objects.filter(
        company=company, field='stage', created_at__gte=depuis,
        new_value=stages.STAGE_LABELS[stages.SIGNED]).count()

    try:
        from apps.ventes.selectors import devis_envoyes_periode
        devis_envoyes = devis_envoyes_periode(
            company, date_debut=depuis.date()).count()
    except Exception:  # noqa: BLE001 — un KPI ne casse jamais sur ce point
        devis_envoyes = 0

    # Moyenne de tentatives des leads passés au FROID sur la période — la
    # seule population où « avant abandon » veut dire quelque chose.
    refroidis = list(
        leads.filter(stage=stages.COLD)
        .annotate(tentatives=Count(
            'activites',
            filter=Q(activites__kind__in=[
                LeadActivity.Kind.APPEL, LeadActivity.Kind.WHATSAPP,
                LeadActivity.Kind.EMAIL],
                activites__user__isnull=False),
            distinct=True))
        .values_list('tentatives', flat=True))

    return {
        'joints_sous_5j_pct': (round(100.0 * joints / nb_leads, 1)
                               if nb_leads else None),
        'cadences_completes': cadences_completes,
        'cadences_arretees_joint': cadences_arretees_joint,
        'perdus_avec_motif_pct': (
            round(100.0 * perdus_avec_motif / nb_perdus, 1)
            if nb_perdus else None),
        'signatures': signatures,
        'devis_envoyes': devis_envoyes,
        'tentatives_moy_avant_abandon': (
            round(sum(refroidis) / len(refroidis), 1) if refroidis else None),
    }


# ── CKP3 — ADHÉRENCE AU PROTOCOLE (cockpit CRM « suivre les étapes ») ────────
#
# Fondateur 2026-09-10 : « moi et Meryem on ne voit pas assez ce qu'elle fait
# et si elle le fait bien — je parle du suivi des étapes ». TRANSPARENCE
# TOTALE (décision actée) : les deux agrégats ci-dessous sont lisibles par
# TOUS les rôles, seule la mise en page diffère à l'écran.
#
# Trois règles les rendent honnêtes, et aucune n'est négociable :
#   * une ANNULATION MOTEUR (statut `annulee`, CKP1) n'est JAMAIS comptée
#     comme un saut humain, ni au dénominateur de l'adhérence : une cadence
#     arrêtée parce que le client a répondu n'est pas un manquement ;
#   * dénominateur 0 → `null`, jamais un 0 % qui se lirait comme un échec là
#     où il n'y a rien à mesurer ;
#   * AUCUN seuil rouge/vert côté serveur : des valeurs et des tendances, le
#     jugement reste humain (et le couple « à-l'heure % + conversion » est
#     servi ensemble, anti-Goodhart).

#: Le grain de l'« à-l'heure » est le JOUR, pas la minute : une touche due à
#: 09:00 et faite à 17:00 le même jour A ÉTÉ FAITE. Mesurer à la minute
#: transformerait un KPI de suivi en chronomètre de surveillance — exactement
#: ce que la recherche (HBR) dit de ne pas faire.
#: Le DÉNOMINATEUR de l'adhérence = les touches closes PAR UN HUMAIN sur la
#: période (faites + sautées). Les annulations moteur en sont exclues.
_STATUTS_CLOS_HUMAIN = ('fait', 'sautee')


#: Plafond de la liste actionnable `leads_sans_touche` : au-delà, ce n'est
#: plus une file de travail mais un export — et la page mettrait dix secondes.
LEADS_SANS_TOUCHE_MAX = 100


def _lundi(jour):
    """Le lundi de la semaine de ``jour`` — la clé des tendances hebdo."""
    return jour - datetime.timedelta(days=jour.weekday())


def _pct(numerateur, denominateur):
    """``null`` dès que le dénominateur est 0 — jamais un 0 % inventé."""
    if not denominateur:
        return None
    return round(100.0 * numerateur / denominateur, 1)


def _mediane_decimale(valeurs):
    """Médiane DÉCIMALE — distincte du ``_mediane`` entier défini plus bas,
    qui arrondit des minutes : la vitesse de premier contact se lit en heures
    avec une décimale (3,4 h), et un arrondi à l'entier effacerait justement
    l'écart que la tendance hebdo cherche à montrer."""
    valeurs = sorted(valeurs)
    if not valeurs:
        return None
    milieu = len(valeurs) // 2
    if len(valeurs) % 2:
        return valeurs[milieu]
    return (valeurs[milieu - 1] + valeurs[milieu]) / 2.0


def _a_lheure(etape):
    """Une touche FAITE le jour où elle était due, ou AVANT (heure locale
    Casablanca).

    CAD22 — deux situations ne sont PAS des manquements d'adhérence et ne
    doivent pas en être comptées comme tels :

      * TRAITÉE EN AVANCE — une touche due jeudi et faite mercredi a bien été
        faite ; l'égalité stricte la comptait en manquement, ce qui punissait
        exactement le geste qu'on attend (prendre de l'avance) ;
      * NÉE EN RETARD — une touche matérialisée APRÈS son échéance
        (`cadence_temps.nee_en_retard`) n'a jamais donné la chance de la faire
        à l'heure. CAD22 empêche désormais une telle naissance, mais les
        lignes déjà en base restent, et les accuser serait faux.
    """
    from . import cadence_temps, horaires

    if etape.statut != 'fait' or etape.traite_le is None:
        return False
    if (etape.traite_le.astimezone(horaires.CASABLANCA).date()
            <= etape.due_date):
        return True
    return cadence_temps.nee_en_retard(etape)


def _a_lheure_ou_excusee(etape, absences, proprietaire):
    """CAD22 + CAD35 — à l'heure, ou excusée sans rien inventer.

    Excusée = née en retard (CAD22), ou échue un jour couvert par une
    ABSENCE déclarée de la personne responsable du lead (CAD35) : personne
    n'était là, l'accuser reviendrait à lui reprocher son congé.

    Fonction de MODULE, jamais une fermeture définie dans ``kpi_adherence`` :
    ``scripts/check_api_shapes.py`` lit TOUS les ``return`` d'une vue par
    ``ast.walk`` — un ``return`` non-dictionnaire imbriqué fait sortir
    l'endpoint entier du contrat versionné.
    """
    if _a_lheure(etape):
        return True
    return absences.couvre(
        proprietaire.get(etape.lead_id), etape.due_date)


def _conversion_par_stage(company, leads_visibles, depuis):
    """Le funnel APPARIÉ à l'adhérence (anti-Goodhart) — sur les clés de
    ``STAGES.py``, jamais une liste en dur.

    « Entré » dans une étape = le lead l'a ATTEINTE (son étape courante est à
    ce rang ou au-delà, ou son historique porte le passage). L'historique
    compte parce qu'un lead redescendu au Froid a bel et bien traversé le
    funnel : ne lire que l'étape courante ferait disparaître tous les dossiers
    parqués et gonflerait mécaniquement les taux.

    ``COLD`` est un PARKING (rang hors échelle) : il n'entre pas dans
    l'échelle de conversion — il n'y a pas de « suivant » après un parking.
    """
    from .models import LeadActivity
    from . import stages

    echelle = [s for s in stages.STAGES if s != stages.COLD]
    rang = {cle: i for i, cle in enumerate(echelle)}
    label_vers_cle = {stages.STAGE_LABELS[cle]: cle for cle in echelle}

    leads = list(leads_visibles.filter(date_creation__gte=depuis)
                 .values_list('id', 'stage'))
    atteint = {pk: rang.get(stage, -1) for pk, stage in leads}
    if atteint:
        for lead_id, valeur in LeadActivity.objects.filter(
                company=company, field='stage', lead_id__in=list(atteint),
        ).values_list('lead_id', 'new_value'):
            cle = label_vers_cle.get((valeur or '').strip())
            if cle is not None:
                atteint[lead_id] = max(atteint[lead_id], rang[cle])

    lignes = []
    for i, cle in enumerate(echelle):
        entres = sum(1 for r in atteint.values() if r >= i)
        passes = sum(1 for r in atteint.values() if r >= i + 1)
        lignes.append({
            'stage': cle,
            'entres': entres,
            'passes_au_suivant': passes,
            'taux_pct': _pct(passes, entres),
        })
    return lignes


# ── Chaîne commerciale — les trois compteurs du cockpit ──────────────────────
#
# Décision fondateur du 25/09/2026 (« regarde aussi le cockpit, que tout soit
# bien fait maintenant que la cadence est bien faite ») : la chaîne appel →
# visite → devis → suivi de proposition a trois états intermédiaires que le
# cockpit ne montrait nulle part. Forme : contrat
# ``contract_samples/chaine_commerciale.json``.

#: La limite servie (fixe) : l'écran dit « et N autres » sans la deviner.
CHAINE_COMMERCIALE_LIMITE = 5


def _chaine_bloc(lignes, limite):
    return {'total': len(lignes), 'leads': lignes[:limite]}


def _chaine_identite(lead, masquer):
    """Identité d'un dossier de la chaîne — téléphone masqué comme la file
    du jour (``lead_pii_masquee``)."""
    return {
        'id': lead.pk,
        'nom': lead.nom or '',
        'prenom': lead.prenom or '',
        'telephone': '' if masquer else (lead.telephone or ''),
    }


def _chaine_devis_partis(company, ids):
    """Les leads de ``ids`` pour lesquels UN DEVIS EST PARTI — la règle de
    ``services.aucun_devis_parti``, en lot : un devis sorti du brouillon dans
    l'ERP (lu par le sélecteur de ventes, frontière M3, jamais une requête par
    lead) OU un suivi de proposition déjà démarré (barreau ``apres_devis`` hors
    gestes de visite : la trace d'un devis parti HORS ERP, TREADMILL-1538).
    Décision du 25/09/2026 : un client qui a reçu son devis par WhatsApp
    depuis un téléphone n'est pas « joint sans devis »."""
    if not ids:
        return set()
    from apps.ventes.selectors import leads_ayant_recu_un_devis
    from . import cadence_config
    from .models import RelanceEtape
    partis = set(leads_ayant_recu_un_devis(company, ids))
    suivis = set(
        RelanceEtape.objects
        .filter(company=company, lead_id__in=list(ids), cadence='apres_devis')
        .exclude(cadence_config.q_etape(*cadence_config.CLES_VISITE))
        .values_list('lead_id', flat=True))
    return partis | suivis


def chaine_commerciale(user, company, *, limite=CHAINE_COMMERCIALE_LIMITE):
    """Les trois compteurs PERSONNELS de la chaîne commerciale (forme
    ``chaine_commerciale``), chacun avec ses ``limite`` dossiers les plus
    urgents et son ``total`` exact — jamais un classement entre commerciaux.

    Même portée que la file du jour (``relance_etapes_dues`` :
    ``scope_queryset`` par responsable, transparence CKP5 — le manager voit la
    même chose), mêmes téléphones masqués (``lead_pii_masquee``). Aucun
    chiffre calculé côté écran : comptes et dates viennent d'ici.

    * ``joints_sans_devis`` — leads ACTIFS (ni perdu, ni archivé, ni « ne
      plus contacter », étape hors Signé/Froid) dont la DERNIÈRE issue saisie
      par un humain (``LeadActivity.outcome``, tous canaux) est « joint »,
      « intéressé » ou « visite acceptée » (``services.ISSUES_CLIENT_JOINT``)
      et pour lesquels AUCUN devis n'est parti (ni sorti du brouillon dans
      l'ERP, ni suivi de proposition démarré — la règle de
      ``services.aucun_devis_parti``, lue en lot par
      ``_chaine_devis_partis``). ``joint_le`` = la date
      locale de cette issue ; ``prochaine_etape``/``prochaine_le`` = la
      prochaine étape à faire du lead, ``None`` si aucune — un TROU, rangé en
      tête, jamais masqué ;
    * ``visites_a_venir`` — leads actifs dont ``visite_prevue_le`` est
      aujourd'hui ou plus tard et ``visite_effectuee`` faux ; ``sans_devis``
      dit si la visite précède le devis (CAD123) ; ``assignee`` = le
      commercial de la visite (``visites.selectors``, lu pour les seuls
      dossiers servis) ;
    * ``devis_a_preparer`` — les étapes « Préparer et envoyer le devis »
      encore à faire (par leur CLÉ ``devis``, PARAM-CADENCE — une société
      peut la renommer), une ligne par lead ; ``apres_visite`` =
      ``Lead.visite_effectuee``.

    Tri : en retard d'abord, puis échéance croissante (visites : date
    croissante). Coût : une requête par compteur, une pour les prochaines
    étapes, une par lot de devis — jamais une par lead (sauf l'assigné des
    ``limite`` visites servies)."""
    from django.db.models import F, OuterRef, Subquery

    from authentication.scoping import scope_queryset
    from core.dates import aujourd_hui_local

    from . import horaires, stages
    from .cadence_config import CLE_DEVIS, q_etape
    from .models import Lead, LeadActivity, RelanceEtape
    from .controle_suivi import etape_en_retard, seuil_retard
    from .serializers import pii_masquee_pour
    from .cadence_plan import ISSUES_CLIENT_JOINT

    today = aujourd_hui_local()
    # ALEA32 — LA définition unique de « en retard » (jours COMPTÉS).
    seuil = seuil_retard(company, today)
    memo_retard = {}
    masquer = pii_masquee_pour(user)
    visibles = scope_queryset(
        Lead.objects.filter(company=company), user, ['owner'])
    actifs = visibles.filter(perdu=False, is_archived=False,
                             ne_plus_contacter=False)

    # ── 1. Joints sans devis ────────────────────────────────────────────────
    derniere_issue = (LeadActivity.objects
                      .filter(lead=OuterRef('pk'), user__isnull=False)
                      .exclude(outcome='')
                      .order_by('-created_at', '-pk'))
    joints = list(
        actifs.exclude(stage__in=[stages.SIGNED, stages.COLD])
        .annotate(
            derniere_issue=Subquery(derniere_issue.values('outcome')[:1]),
            derniere_issue_le=Subquery(
                derniere_issue.values('created_at')[:1]))
        .filter(derniere_issue__in=ISSUES_CLIENT_JOINT)
        .only('id', 'nom', 'prenom', 'telephone'))
    partis = _chaine_devis_partis(company, [lead.pk for lead in joints])
    joints = [lead for lead in joints if lead.pk not in partis]
    prochaines = {}
    if joints:
        for lead_id, libelle, due_date in (
                RelanceEtape.objects
                .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                        lead_id__in=[lead.pk for lead in joints])
                .order_by('lead_id', F('due_at').asc(nulls_last=True),
                          'due_date', 'ordre')
                .values_list('lead_id', 'libelle', 'due_date')):
            prochaines.setdefault(lead_id, (libelle, due_date))
    lignes_joints = []
    for lead in joints:
        libelle, prochaine_le = prochaines.get(lead.pk, ('', None))
        joint_le = lead.derniere_issue_le
        ligne = _chaine_identite(lead, masquer)
        ligne.update({
            'joint_le': (joint_le.astimezone(horaires.CASABLANCA).date()
                         .isoformat() if joint_le else None),
            'prochaine_etape': ((libelle or '').strip() or None
                                if prochaine_le is not None else None),
            'prochaine_le': (prochaine_le.isoformat()
                             if prochaine_le is not None else None),
            # ALEA32 — le seuil unique (jours COMPTÉS de la société).
            'en_retard': bool(prochaine_le is not None
                              and prochaine_le < seuil),
        })
        lignes_joints.append(ligne)
    # Un trou (aucune prochaine étape) d'abord, puis le retard, puis la date.
    lignes_joints.sort(key=lambda ligne: (
        ligne['prochaine_le'] is not None, not ligne['en_retard'],
        ligne['prochaine_le'] or '', ligne['id']))

    # ── 2. Visites à venir ──────────────────────────────────────────────────
    visites = list(
        actifs.filter(visite_prevue_le__gte=today, visite_effectuee=False)
        .order_by('visite_prevue_le', 'pk')
        .only('id', 'nom', 'prenom', 'telephone', 'visite_prevue_le',
              'company_id'))
    avec_devis = _chaine_devis_partis(company,
                                      [lead.pk for lead in visites])
    lignes_visites = []
    for rang, lead in enumerate(visites):
        ligne = _chaine_identite(lead, masquer)
        ligne.update({
            'visite_prevue_le': lead.visite_prevue_le.isoformat(),
            'assignee': (_assigne_de_la_visite(lead)
                         if rang < limite else ''),
            'sans_devis': lead.pk not in avec_devis,
        })
        lignes_visites.append(ligne)

    # ── 3. Devis à préparer ─────────────────────────────────────────────────
    etapes = (RelanceEtape.objects
              .filter(q_etape(CLE_DEVIS), company=company,
                      statut=RelanceEtape.Statut.A_FAIRE,
                      lead_id__in=visibles.filter(is_archived=False)
                      .values('id'))
              .select_related('lead')
              .order_by('due_date', F('due_at').asc(nulls_last=True), 'pk'))
    lignes_devis, vus = [], set()
    for etape in etapes:
        if etape.lead_id in vus:
            continue
        vus.add(etape.lead_id)
        ligne = _chaine_identite(etape.lead, masquer)
        ligne.update({
            'prochaine_le': etape.due_date.isoformat(),
            # ALEA32 — LA définition unique (jours ouvrés + absences).
            'en_retard': etape_en_retard(etape, memo=memo_retard,
                                         aujourd_hui=today),
            'apres_visite': bool(etape.lead.visite_effectuee),
        })
        lignes_devis.append(ligne)
    lignes_devis.sort(key=lambda ligne: (
        not ligne['en_retard'], ligne['prochaine_le'], ligne['id']))

    return {
        'joints_sans_devis': _chaine_bloc(lignes_joints, limite),
        'visites_a_venir': _chaine_bloc(lignes_visites, limite),
        'devis_a_preparer': _chaine_bloc(lignes_devis, limite),
        'limite': limite,
    }


def _assigne_de_la_visite(lead):
    """Le commercial de la visite À VENIR la plus proche du lead (sélecteur
    de l'app visites — jamais ses modèles), ``''`` s'il n'y en a pas.
    Best-effort : une lecture en échec rend ``''``."""
    try:
        from apps.visites.selectors import visites_pour_lead

        jour = lead.visite_prevue_le.isoformat()
        lignes = [ligne for ligne in visites_pour_lead(lead)
                  if (ligne.get('date_prevue') or '') >= jour]
    except Exception:  # noqa: BLE001 — jamais bloquant
        return ''
    if not lignes:
        return ''
    lignes.sort(key=lambda ligne: (ligne['date_prevue'], ligne['id']))
    return lignes[0].get('commercial_nom') or ''


#: Profondeur maximale de la remontée de la série : au-delà, la « série » ne
#: dit plus rien d'actionnable et la requête coûterait plus qu'elle ne vaut.
SERIE_JOURS_MAX = 60


def _serie_jours_sans_retard(company, mes_touches, today, absences=None,
                             utilisateur=None):
    """Jours OUVRÉS consécutifs TERMINÉS sans laisser une touche en retard.

    Un jour est « propre » si chaque touche qui y était due a été close ce
    jour-là au plus tard. On repart du dernier jour ouvré TERMINÉ (jamais
    d'aujourd'hui : la journée n'est pas finie, compter ses touches encore
    ouvertes comme des retards serait faux) et on remonte.

    CAD35 — un jour couvert par une absence déclarée (``absences``) est
    propre par construction : une série ne se casse pas sur un congé.
    """
    from . import horaires

    dues = {}
    debut = today - datetime.timedelta(days=SERIE_JOURS_MAX)
    for etape in mes_touches.filter(
            due_date__gte=debut, due_date__lt=today,
    ).only('due_date', 'statut', 'traite_le'):
        propre = (etape.statut in ('fait', 'sautee', 'annulee')
                  and etape.traite_le is not None
                  and etape.traite_le.astimezone(horaires.CASABLANCA).date()
                  <= etape.due_date)
        if not propre and absences is not None:
            propre = absences.couvre(utilisateur, etape.due_date)
        dues.setdefault(etape.due_date, []).append(propre)

    serie = 0
    jour = today - datetime.timedelta(days=1)
    while jour >= debut:
        if horaires._jour_ouvre(jour, company):
            if not all(dues.get(jour, [])):
                break
            serie += 1
        jour -= datetime.timedelta(days=1)
    return serie


def _mediane(valeurs):
    """Médiane entière, ou ``None`` sur une liste vide (jamais un 0 inventé)."""
    if not valeurs:
        return None
    ordonnees = sorted(valeurs)
    milieu = len(ordonnees) // 2
    if len(ordonnees) % 2:
        return int(ordonnees[milieu])
    return int((ordonnees[milieu - 1] + ordonnees[milieu]) / 2)


# ── VX83 — « Ma file » : items commerciaux pour la file de travail unique ────

def relances_du_jour(company, user, scope='today', today=None):
    """VX83 — File de relance d'un utilisateur, EXTRAITE de
    ``LeadViewSet.relances`` (FG31, ``apps/crm/views.py``) pour être consommée
    par la « Ma file » cross-module (``records`` ne fabrique jamais sa propre
    union — convention selectors, jamais forker/appeler une vue).

    Mêmes règles que l'action d'origine : leads non archivés portant une
    ``relance_date``, filtrés par ``scope`` (``overdue`` / ``today`` / ``week``),
    ordonnés par échéance puis nom. La PORTÉE DE VISIBILITÉ de l'utilisateur est
    respectée à l'identique (``scope_queryset(..., ['owner'])`` — Feature F : un
    rôle restreint ne voit que ses leads). Lecture seule, scopée société.
    """
    import datetime
    from core.dates import aujourd_hui_local
    from .models import Lead

    today = today or aujourd_hui_local()
    qs = Lead.objects.filter(
        company=company, is_archived=False, relance_date__isnull=False)
    qs = portee_leads(qs, user)  # ACRM28 — + périmètre d'entités
    if scope == 'overdue':
        qs = qs.filter(relance_date__lt=today)
    elif scope == 'week':
        # CRX28 — la borne BASSE manquait : sans ``__gte=today``, « cette
        # semaine » ramenait TOUT le passé (un retard de six mois s'affichait
        # comme une relance de la semaine) et doublonnait le scope ``overdue``,
        # qui existe précisément pour montrer les retards. La semaine, c'est
        # aujourd'hui → aujourd'hui + 6 jours, bornes incluses.
        week_end = today + datetime.timedelta(days=6)
        qs = qs.filter(relance_date__gte=today, relance_date__lte=week_end)
    else:  # today
        qs = qs.filter(relance_date=today)
    # APRF18 — préchargement de ce que la sérialisation lit par lead
    # (responsable, client, devis et leurs lignes) : la file « Relances »
    # et « Ma file » ne paient plus une requête par carte.
    return (qs.select_related('owner', 'client')
            .prefetch_related('devis', 'devis__lignes')
            .order_by('relance_date', 'nom'))


# ── RELANCE FOUNDATION — file des étapes de cadence de relance dues ─────────

def relance_etapes_dues(company, user, *, scope='today', owner=None, today=None):
    """RELANCE FOUNDATION — étapes de relance (``RelanceEtape``) DUES, pour le
    panneau « Relances du jour ».

    Distinct de ``relances_du_jour`` ci-dessus (leads via ``relance_date``,
    granularité lead) : ici la granularité est l'ÉTAPE de plan structuré
    (canal + statut propres). ``scope`` = ``overdue`` (en retard, strictement
    avant aujourd'hui) / ``today`` (échéance aujourd'hui, défaut) / ``all``
    (aujourd'hui + en retard, l'union affichée par le panneau). Seules les
    étapes ``a_faire`` sont candidates — jamais une étape déjà traitée. La
    portée de visibilité de l'utilisateur est respectée (``scope_queryset``
    via le lead) ; ``owner`` filtre en plus sur le responsable du lead.

    MRY30 — deux scopes S'AJOUTENT, sans rien changer aux trois précédents :
    ``tomorrow`` (échéance DEMAIN, ce que la file du jour ne montre jamais —
    Meryem prépare sa journée la veille) et ``week``.

    COCKPIT-CONTRÔLE (fondateur, 30/09/2026) — la file du cockpit SUIT LA
    CADENCE : une TÂCHE (préparer le devis, planifier la visite, décider la
    suite, devis modifié, question de prix) est « possible dès maintenant »,
    quelle que soit son échéance. ``all`` (« maintenant ») = les échéances
    d'aujourd'hui et en retard PLUS les tâches ouvertes à toute date ;
    ``tomorrow`` et ``week`` n'en reprennent AUCUNE — jamais un doublon entre
    segments. ``week`` = les 7 prochains jours HORS « maintenant » (demain
    compris) : le retard n'y est plus, il est déjà sous les yeux dans
    « maintenant » (avant : « retard + 7 jours », qui le doublait). La
    reconnaissance SQL d'une tâche est ``suite_touche.q_tache`` — la seule.
    """
    import datetime as _dt

    from django.db.models import Q

    from core.dates import aujourd_hui_local
    from .models import RelanceEtape
    from .suite_touche import q_tache

    today = today or aujourd_hui_local()
    qs = RelanceEtape.objects.filter(
        company=company, statut=RelanceEtape.Statut.A_FAIRE,
        lead__is_archived=False,
    ).select_related('lead', 'lead__owner', 'devis')
    if scope == 'overdue':
        # ALEA32 — « en retard » = au moins un jour COMPTÉ depuis l'échéance
        # (le seuil unique, ``controle_suivi.seuil_retard``).
        from .controle_suivi import seuil_retard
        qs = qs.filter(due_date__lt=seuil_retard(company, today))
    elif scope == 'all':
        qs = qs.filter(Q(due_date__lte=today) | q_tache())
    elif scope == 'tomorrow':
        qs = qs.filter(due_date=today + _dt.timedelta(days=1)).exclude(
            q_tache())
    elif scope == 'week':
        qs = qs.filter(due_date__gt=today,
                       due_date__lte=today + _dt.timedelta(days=7)).exclude(
            q_tache())
    else:  # today
        qs = qs.filter(due_date=today)

    # Portée de visibilité : mêmes leads que scope_queryset(..., ['owner'])
    # appliqué à Lead, traduit ici en filtre sur `lead_id`.
    # ACRM28 — portée propriétaire ET périmètre d'entités.
    visibles = leads_visibles(user, company)
    qs = qs.filter(lead_id__in=visibles.values('id'))

    if owner:
        qs = qs.filter(lead__owner_id=owner)
    # MRY5 — tri à la MINUTE, les lignes d'avant MRY5 (sans heure) EN DERNIER
    # de leur journée. CAD83 — le départage à heure ÉGALE passe par
    # `trier_file_du_jour` (priorité puis score), sans jamais précéder
    # l'heure cible. COCKPIT-CONTRÔLE — le jour D'ABORD : en retard (la plus
    # ancienne d'abord), puis aujourd'hui à l'heure, puis les tâches à venir.
    return trier_file_du_jour(qs)


def file_du_cockpit(company, user, *, owner=None, today=None):
    """COCKPIT-CONTRÔLE (30/09/2026) — le bloc ``file`` de la liste des
    touches (contrat ``relance_etape_v2``, note ``cockpit_controle``), servi
    quand ``scope`` est demandé : combien de touches dans chaque segment de
    la file du cockpit, dans la MÊME portée que la liste (société, portée de
    visibilité via le lead, leads archivés exclus, ``owner`` en plus).

    ``maintenant`` / ``demain`` / ``semaine`` sont LES MÊMES requêtes que la
    liste (``relance_etapes_dues``, scopes ``all`` / ``tomorrow`` /
    ``week``) : un segment ne peut pas compter autrement que la liste qu'il
    ouvre. ``traitees_aujourdhui`` = les étapes closes « fait » aujourd'hui
    (jour Africa/Casablanca) — un « fait » est toujours un geste humain
    (CKP1 : le moteur n'écrit que ``annulee``). Quatre requêtes COUNT."""
    import datetime as _dt

    from core.dates import aujourd_hui_local
    from . import horaires
    from .models import RelanceEtape

    today = today or aujourd_hui_local()
    debut = _dt.datetime.combine(today, _dt.time(0, 0),
                                 tzinfo=horaires.CASABLANCA)
    faites = RelanceEtape.objects.filter(
        company=company, statut=RelanceEtape.Statut.FAIT,
        lead__is_archived=False,
        traite_le__gte=debut, traite_le__lt=debut + _dt.timedelta(days=1),
        # ACRM28 — portée propriétaire ET périmètre d'entités.
        lead_id__in=leads_visibles(user, company).values('id'))
    if owner:
        faites = faites.filter(lead__owner_id=owner)
    return {
        'maintenant': relance_etapes_dues(
            company, user, scope='all', owner=owner, today=today).count(),
        'demain': relance_etapes_dues(
            company, user, scope='tomorrow', owner=owner,
            today=today).count(),
        'semaine': relance_etapes_dues(
            company, user, scope='week', owner=owner, today=today).count(),
        'traitees_aujourdhui': faites.count(),
    }


#: MRY30 — le statut VIRTUEL du suivi : « en retard » n'existe pas en base
#: (c'est un ``a_faire`` dont l'échéance est passée), mais c'est l'onglet que
#: Meryem ouvre en premier. Le nommer ici évite qu'il soit recalculé — donc
#: défini autrement — dans la vue puis dans l'écran.
STATUT_EN_RETARD = 'en_retard'


#: Les quatre valeurs acceptées par ``?statut=`` de l'action « suivi ».
#: CKP1 — ``annulee`` s'AJOUTE (aucune valeur retirée : les écrans qui
#: envoient ``statut=sautee`` continuent de fonctionner à l'identique).
STATUTS_SUIVI = ('a_faire', 'fait', 'sautee', 'annulee', STATUT_EN_RETARD)


#: Écart MAXIMAL entre les deux bornes du suivi. Au-delà, la requête cesse
#: d'être une « période de travail » et devient un export : 400 plutôt qu'une
#: page qui met dix secondes à s'afficher.
SUIVI_JOURS_MAX = 62


def relance_etapes_periode(company, user, *, date_debut, date_fin, owner=None,
                           statut=None, today=None):
    """MRY30 — TOUTES les touches de relance dont ``due_date`` tombe dans
    ``[date_debut, date_fin]``, TOUS statuts confondus — l'écran « Suivi des
    relances ».

    Distinct de ``relance_etapes_dues`` ci-dessus, qui ne sert QUE la file du
    jour (statut ``a_faire``, échéance relative à aujourd'hui) : ici on
    regarde EN ARRIÈRE autant qu'en avant — ce qui a été fait, ce qui a été
    sauté, ce qui reste — jour par jour, sur une période choisie.

    Renvoie ``(etapes, resume)`` — un COUPLE, délibérément :

      * ``resume`` = ``{a_faire, en_retard, fait, sautee, annulee}`` compté sur la
        période et le filtre ``owner`` mais **AVANT** le filtre ``statut``.
        L'écran affiche les quatre chiffres quel que soit l'onglet ouvert ;
        les compter après le filtre donnerait « fait : 12, sauté : 0 » sur
        l'onglet « fait ». Rendre le couple d'un seul appel rend cet ordre
        STRUCTUREL : l'appelant ne peut plus l'inverser par inadvertance.
      * ``en_retard`` est un SOUS-ENSEMBLE de ``a_faire`` (échéance
        strictement avant aujourd'hui, date de Casablanca), jamais une
        cinquième colonne qui s'ajouterait aux trois autres.

    Portée identique à la file du jour : ``scope_queryset`` via le lead (un
    lead hors portée n'apparaît jamais, pas même en 403 qui confirmerait son
    existence), leads archivés exclus, ``owner`` en filtre supplémentaire.
    """
    from django.db.models import Count, F, Q

    from core.dates import aujourd_hui_local
    from .controle_suivi import seuil_retard
    from .models import RelanceEtape

    today = today or aujourd_hui_local()
    # ALEA32 — « en retard » = au moins un jour COMPTÉ depuis l'échéance.
    seuil = seuil_retard(company, today)
    qs = RelanceEtape.objects.filter(
        company=company, lead__is_archived=False,
        due_date__gte=date_debut, due_date__lte=date_fin,
    ).select_related('lead', 'lead__owner', 'devis', 'traite_par')

    # ACRM28 — portée propriétaire ET périmètre d'entités.
    visibles = leads_visibles(user, company)
    qs = qs.filter(lead_id__in=visibles.values('id'))
    if owner:
        qs = qs.filter(lead__owner_id=owner)

    a_faire = Q(statut=RelanceEtape.Statut.A_FAIRE)
    resume = qs.aggregate(
        a_faire=Count('pk', filter=a_faire),
        en_retard=Count('pk', filter=a_faire & Q(due_date__lt=seuil)),
        fait=Count('pk', filter=Q(statut=RelanceEtape.Statut.FAIT)),
        sautee=Count('pk', filter=Q(statut=RelanceEtape.Statut.SAUTEE)),
        # CKP1 — colonne SÉPARÉE, ajoutée À CÔTÉ de `sautee` (jamais fondue
        # dedans) : une cadence arrêtée par le moteur parce que le client a
        # répondu n'est pas un manquement, et `sautee` reste ce qu'il était
        # (compat : aucune clé retirée).
        annulee=Count('pk', filter=Q(statut=RelanceEtape.Statut.ANNULEE)),
    )

    if statut == STATUT_EN_RETARD:
        qs = qs.filter(a_faire, due_date__lt=seuil)
    elif statut:
        qs = qs.filter(statut=statut)

    # Tri de LECTURE (le jour d'abord), et non le tri d'urgence de la file du
    # jour : l'écran groupe par journée. `due_at` départage à la minute, les
    # lignes d'avant MRY5 (sans heure) EN DERNIER de leur journée.
    etapes = qs.order_by(
        'due_date', F('due_at').asc(nulls_last=True), 'ordre')
    return etapes, resume


# ── RLC2 — LE JOURNAL « CE QUI S'EST PASSÉ » DU PLAN DE RELANCE ─────────────
#
# Relevé fondateur du 08/09/2026 : « on ne voit pas d'un coup d'œil ce qui s'est
# passé dans le plan de relance ». La réponse n'est PAS un nouveau journal —
# ``LeadActivity`` et ``RelanceEtape`` portent déjà tout — c'est une LECTURE qui
# les fusionne en UNE histoire où chaque ligne dit sa CAUSE.
#
# Deux règles de construction :
#   * la colonne vertébrale, ce sont les TOUCHES traitées (``RelanceEtape``) :
#     la ligne de chatter qu'une clôture écrit n'est donc jamais rendue comme
#     une ligne de plus — elle sert à retrouver l'ISSUE saisie, et rien d'autre ;
#   * tout le reste (message ouvert, rappel reporté, arrêt/redémarrage de
#     cadence avec son motif, filet posé, changement d'étape du funnel,
#     annulation RLC1) vient du chatter, reconnu par des PRÉFIXES écrits dans
#     ``services`` — jamais devinés depuis un texte libre.

#: Les natures de ligne du journal. NOMMÉES côté serveur pour que l'écran ne
#: déduise jamais la nature d'une ligne de son texte.
JOURNAL_TYPES = (
    'touche_faite', 'touche_sautee', 'touche_annulee', 'annulation',
    'message_ouvert', 'rappel_reporte', 'cadence_demarree', 'cadence_arretee',
    'filet_pose', 'devis_suivi', 'etape_funnel',
)


#: Fenêtre d'appariement entre une touche close et la ligne de chatter écrite
#: par la MÊME requête (voir ``services._ANNULATION_FENETRE_EFFETS`` : même
#: raisonnement, même ordre de grandeur — une requête HTTP, pas une journée).
_JOURNAL_FENETRE = datetime.timedelta(minutes=2)


#: Préfixes de chatter → nature de ligne. L'ORDRE compte : le premier préfixe
#: qui correspond gagne (« Cadence de relance non initialisée » est un refus de
#: démarrage, pas un arrêt).
_JOURNAL_PREFIXES = (
    ('WhatsApp ouvert — touche', 'message_ouvert'),
    ('Rappel demandé le', 'rappel_reporte'),
    ('Plan de relance initialisé', 'cadence_demarree'),
    ('Cadence de relance non initialisée', 'cadence_demarree'),
    ('Cadence après devis déjà en cours', 'cadence_demarree'),
    ('Cadence ', 'cadence_arretee'),
    ('Étape « ', 'filet_pose'),
    ('Annulation par ', 'annulation'),
)


def _journal_cause_apres_deux_points(body):
    """Le motif d'une note de chatter — ce qui suit le dernier « : ».

    ``arreter_cadence`` écrit « Cadence contact arrêtée (3 touche(s)) : lead
    signé. » : la CAUSE est « lead signé ». Sans « : », la note entière fait
    office de cause plutôt qu'un vide."""
    texte = (body or '').strip()
    if ' : ' in texte:
        return texte.split(' : ', 1)[1].strip().rstrip('.')
    return texte.rstrip('.')


def journal_relance(company, user, lead_id):
    """RLC2 — « ce qui s'est passé » dans le plan de relance d'UN lead, et son
    ÉTAT courant en une phrase. LECTURE PURE : aucune écriture, aucun effet.

    Renvoie ``{'lead', 'etat', 'lignes'}`` — ``lignes`` en ordre
    CHRONOLOGIQUE (du plus ancien au plus récent : le plan se lit comme une
    histoire, et l'état du moment est servi à part, en tête). ``None`` quand le
    lead n'existe pas OU sort de la portée de visibilité du demandeur : les deux
    cas sont indistinguables exprès (un 404 ne doit jamais confirmer
    l'existence d'un lead qu'on n'a pas le droit de voir).

    Chaque ligne porte ``{quand, type, titre, cause, par}`` : ``type`` est une
    valeur de ``JOURNAL_TYPES``, ``par`` est vide quand le geste est celui du
    MOTEUR (arrêt de cadence, filet, annulation moteur — CKP1 : jamais un nom
    d'humain sur un geste automatique).

    Coût : trois requêtes (le lead, ses touches, la tranche PERTINENTE de son
    chatter), quel que soit le nombre de lignes rendues."""
    from django.db.models import Q

    from authentication.scoping import scope_queryset
    from core.dates import aujourd_hui_local

    from . import stages
    from .controle_suivi import etape_en_retard
    from .models import Lead, LeadActivity, RelanceEtape
    from .cadence_reperes import prefixe_activite_touche

    lead = scope_queryset(
        Lead.objects.filter(company=company, pk=lead_id), user,
        ['owner']).first()
    if lead is None:
        return None

    etapes = list(lead.relance_etapes
                  .select_related('traite_par', 'devis')
                  .order_by('created_at', 'pk'))
    pertinentes = Q(kind=LeadActivity.Kind.MODIFICATION, field='stage')
    pertinentes |= Q(body__startswith='Touche « ')
    for prefixe, _type in _JOURNAL_PREFIXES:
        pertinentes |= Q(body__startswith=prefixe)
    activites = list(lead.activites.filter(pertinentes)
                     .select_related('user').order_by('created_at', 'pk'))
    outcome_labels = dict(LeadActivity.OUTCOMES)

    def _issue_de(etape):
        """L'issue SAISIE à la clôture de cette touche, lue sur la ligne de
        chatter écrite au même instant (appariement par préfixe + fenêtre —
        deux touches de même libellé ne se confondent donc pas)."""
        prefixe = prefixe_activite_touche(etape)
        borne = etape.traite_le + _JOURNAL_FENETRE
        for activite in activites:
            if (activite.created_at is not None
                    and etape.traite_le <= activite.created_at <= borne
                    and (activite.body or '').startswith(prefixe)):
                return activite.outcome or ''
        return ''

    lignes = []
    statut_type = {
        RelanceEtape.Statut.FAIT: 'touche_faite',
        RelanceEtape.Statut.SAUTEE: 'touche_sautee',
        RelanceEtape.Statut.ANNULEE: 'touche_annulee',
    }
    devis_vus = set()
    for etape in etapes:
        libelle = (etape.libelle or '').strip() or etape.get_canal_display()
        # Le DÉMARRAGE d'un suivi de proposition : la première touche créée
        # pour ce devis dit, à sa date, que le devis est parti.
        reference = getattr(etape.devis, 'reference', '') or ''
        if (etape.cadence == 'apres_devis' and etape.devis_id
                and etape.devis_id not in devis_vus):
            devis_vus.add(etape.devis_id)
            lignes.append({
                'quand': etape.created_at,
                'type': 'devis_suivi',
                'titre': ('Suivi de proposition démarré'
                          + (f' — devis {reference}' if reference else '')),
                'cause': 'devis envoyé',
                'par': '',
            })
        nature = statut_type.get(etape.statut)
        if nature is None or etape.traite_le is None:
            continue
        if etape.statut == RelanceEtape.Statut.FAIT:
            issue = _issue_de(etape)
            cause = outcome_labels.get(issue, issue) if issue else ''
            if etape.note:
                cause = f'{cause} — {etape.note}' if cause else etape.note
        else:
            # Sautée (décision humaine) comme annulée (retrait moteur) : le
            # POURQUOI est la note — c'est là qu'``arreter_cadence`` écrit son
            # motif (« joint », « lead signé »…).
            cause = etape.note or ''
        lignes.append({
            'quand': etape.traite_le,
            'type': nature,
            'titre': (f'Touche « {libelle} » ({etape.get_canal_display()}, '
                      f'cadence {etape.cadence}) '
                      + ('faite' if nature == 'touche_faite'
                         else 'sautée' if nature == 'touche_sautee'
                         else 'retirée du plan')),
            'cause': cause,
            # CKP1 — un retrait MOTEUR ne porte aucun nom d'humain.
            'par': getattr(etape.traite_par, 'username', '') or '',
        })

    for activite in activites:
        corps = (activite.body or '').strip()
        if corps.startswith('Touche « '):
            continue  # l'écho d'une touche : déjà rendue ci-dessus.
        if (activite.kind == LeadActivity.Kind.MODIFICATION
                and activite.field == 'stage'):
            lignes.append({
                'quand': activite.created_at,
                'type': 'etape_funnel',
                'titre': ('Étape du lead : '
                          f'{activite.old_value or "—"} → '
                          f'{activite.new_value or "—"}'),
                'cause': corps,
                'par': getattr(activite.user, 'username', '') or '',
            })
            continue
        nature = next((t for prefixe, t in _JOURNAL_PREFIXES
                       if corps.startswith(prefixe)), None)
        if nature is None:
            continue
        lignes.append({
            'quand': activite.created_at,
            'type': nature,
            'titre': corps,
            'cause': (_journal_cause_apres_deux_points(corps)
                      if nature in ('cadence_arretee', 'cadence_demarree')
                      else ''),
            'par': getattr(activite.user, 'username', '') or '',
        })

    lignes.sort(key=lambda ligne: (ligne['quand'], ligne['type']))

    # ── L'ÉTAT COURANT, en une phrase ────────────────────────────────────────
    aujourdhui = aujourd_hui_local()
    ouvertes = [e for e in etapes
                if e.statut == RelanceEtape.Statut.A_FAIRE]
    # La PROCHAINE touche = la plus proche dans le temps, les lignes sans heure
    # (d'avant MRY5) en DERNIER — la même règle que `_prochaine_touche_a_faire`
    # côté services et que le cockpit, jamais une troisième.
    prochaine = min(
        ouvertes,
        key=lambda e: (e.due_at is None, e.due_at or aujourdhui, e.ordre),
        default=None)
    dernier = next(
        (a for a in reversed(activites)
         if a.kind in (LeadActivity.Kind.APPEL, LeadActivity.Kind.WHATSAPP,
                       LeadActivity.Kind.EMAIL)), None)
    devis = next((e.devis for e in reversed(etapes) if e.devis_id), None)

    etat = {
        'stage': lead.stage,
        'stage_libelle': stages.STAGE_LABELS.get(lead.stage, lead.stage),
        'cadence_active': prochaine.cadence if prochaine is not None else '',
        'prochaine_touche': None if prochaine is None else {
            'id': prochaine.pk,
            'libelle': ((prochaine.libelle or '').strip()
                        or prochaine.get_canal_display()),
            'canal': prochaine.canal,
            'cadence': prochaine.cadence,
            'due_at': prochaine.due_at,
            'due_date': prochaine.due_date,
            # ALEA32 — LA définition unique (jours ouvrés + absences).
            'en_retard': etape_en_retard(prochaine, aujourd_hui=aujourdhui),
        },
        'dernier_echange': None if dernier is None else {
            'quand': dernier.created_at,
            'quoi': dernier.get_kind_display(),
            'issue': (outcome_labels.get(dernier.outcome, dernier.outcome)
                      if dernier.outcome else ''),
            'par': getattr(dernier.user, 'username', '') or '',
        },
        'devis_en_cours': None if devis is None else {
            'id': devis.pk,
            'reference': getattr(devis, 'reference', '') or '',
            'statut': getattr(devis, 'statut', '') or '',
        },
    }
    etat['phrase'] = _journal_phrase(etat)
    return {'lead': lead.pk, 'etat': etat, 'lignes': lignes}


def _journal_phrase(etat):
    """RLC2 — l'état courant en UNE phrase lisible.

    Règle des faits VÉRIFIÉS : un morceau inconnu est OMIS — jamais un « — »
    ni un « 0 » qui laisserait croire à une information."""
    from . import horaires

    morceaux = [f'Étape {etat["stage_libelle"]}']
    if etat['cadence_active']:
        morceaux.append(f'cadence « {etat["cadence_active"]} » active')
    prochaine = etat['prochaine_touche']
    if prochaine:
        quand = prochaine['due_at']
        moment = (f'{quand.astimezone(horaires.CASABLANCA):%d/%m à %H:%M}'
                  if quand else f'{prochaine["due_date"]:%d/%m}')
        morceaux.append(
            f'prochaine touche « {prochaine["libelle"]} » le {moment}'
            + (' (en retard)' if prochaine['en_retard'] else ''))
    else:
        morceaux.append('aucune touche ouverte')
    echange = etat['dernier_echange']
    if echange:
        quand = echange['quand'].astimezone(horaires.CASABLANCA)
        morceaux.append(
            f'dernier échange : {echange["quoi"].lower()} du '
            f'{quand:%d/%m}'
            + (f' ({echange["issue"]})' if echange['issue'] else ''))
    devis = etat['devis_en_cours']
    if devis and devis['reference']:
        morceaux.append(
            f'devis {devis["reference"]}'
            + (f' ({devis["statut"]})' if devis['statut'] else ''))
    return ' · '.join(morceaux) + '.'


def prochaine_touche_par_lead(company, lead_ids):
    """MRY5 — ``{lead_id: (due_at, due_date, cadence, canal)}`` de la prochaine
    touche À FAIRE de chaque lead demandé.

    Une seule requête pour N leads (le badge « touche due » de la liste et du
    kanban ne peut pas coûter une requête par carte). Un lead sans touche
    ouverte est simplement ABSENT du dictionnaire — jamais une entrée vide."""
    from django.db.models import F

    from .models import RelanceEtape

    if not lead_ids:
        return {}
    lignes = (RelanceEtape.objects
              .filter(company=company, lead_id__in=list(lead_ids),
                      statut=RelanceEtape.Statut.A_FAIRE)
              .order_by('lead_id', F('due_at').asc(nulls_last=True),
                        'due_date', 'ordre')
              .values_list('lead_id', 'due_at', 'due_date', 'cadence',
                           'canal'))
    out = {}
    for lead_id, due_at, due_date, cadence, canal in lignes:
        # La première ligne rencontrée par lead est la plus proche (tri
        # ci-dessus) — les suivantes sont ignorées.
        out.setdefault(lead_id, (due_at, due_date, cadence, canal))
    return out


def devis_a_cadence_active(devis_id):
    """MRY7 — ce devis porte-t-il une cadence MRY encore À FAIRE ?

    Consommé par ``ventes.domain.recouvrement`` pour SUPPRIMER la relance
    vendeur QJ4 sur un devis déjà suivi par le moteur de Meryem : sans cette
    porte, le client recevrait deux relances pour le même devis, le même jour,
    de deux systèmes différents. Lecture seule ; ``ventes`` l'appelle par ce
    sélecteur, jamais en important ``crm.models``."""
    from .models import RelanceEtape

    if not devis_id:
        return False
    return RelanceEtape.objects.filter(
        devis_id=devis_id, statut=RelanceEtape.Statut.A_FAIRE).exists()


def leads_chauds_non_contactes(company, user, seuil_score=None):
    """VX83 — Leads « chauds » (score élevé) JAMAIS contactés, pour la file de
    travail. Un lead à fort potentiel dont ``first_contacted_at`` est NULL est
    une opportunité qui dort. Portée de visibilité de l'utilisateur respectée
    (``scope_queryset(..., ['owner'])``). Lecture seule, scopée société.

    ``seuil_score`` par défaut = 60 (« chaud » sur l'échelle 0-100 de QJ6). Un
    lead archivé/perdu/déjà signé est exclu (funnel via STAGES.py — règle #2).
    """
    from . import stages as stage_mod
    from .models import Lead

    seuil = 60 if seuil_score is None else seuil_score
    qs = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        first_contacted_at__isnull=True, score__gte=seuil,
    ).exclude(stage__in=(stage_mod.SIGNED, stage_mod.COLD))
    qs = portee_leads(qs, user)  # ACRM28 — + périmètre d'entités
    return qs.order_by('-score', 'date_creation')


def devis_expirant_bientot(company, user, dans_jours=7, today=None):
    """VX83 — Devis au statut ``envoye`` dont la validité expire dans les
    ``dans_jours`` prochains jours (ou déjà expirés mais encore ``envoye``),
    pour la file de travail. Lu via la relation ``lead.devis`` déjà dans le
    domaine crm (JAMAIS un import de ``apps.ventes.models`` — même patron que
    ``attribution_leads``/``revenu_attribue_campagne``). Portée de visibilité
    respectée (le devis suit le ``owner`` de son lead). Lecture seule.

    Renvoie une liste de dicts ``{devis_id, reference, lead_id, lead_nom,
    date_expiration, total_ttc}``.

    ACRM29 — l'échéance lue est la date EFFECTIVE de ventes
    (``apps.ventes.selectors.date_validite_effective`` : ``date_validite``,
    sinon création + ``quote_validity_days``) — celle qu'imprime le PDF
    ``/proposal`` du même devis. Un devis envoyé sans ``date_validite``
    apparaît donc à son échéance réelle au lieu d'être ignoré.
    """
    import datetime
    from core.dates import aujourd_hui_local
    from apps.ventes.selectors import devis_envoyes_expirant
    from .models import Lead

    today = today or aujourd_hui_local()
    limite = today + datetime.timedelta(days=dans_jours)
    # ACRM28 — portée propriétaire ET périmètre d'entités.
    lead_ids = portee_leads(
        Lead.objects.filter(company=company, is_archived=False),
        user).values_list('id', flat=True)

    # APRF23 — seuls les devis ENVOYÉS qui expirent avant la limite, filtrés
    # EN SQL par le sélecteur ventes (date effective ACRM29), totaux
    # préchargés : requêtes constantes.
    out = []
    for ligne in devis_envoyes_expirant(company, limite, lead_ids):
        devis = ligne['devis']
        lead = devis.lead
        exp = ligne['date_expiration']
        out.append({
            'devis_id': devis.id,
            'reference': getattr(devis, 'reference', '') or f'#{devis.id}',
            'lead_id': lead.id,
            'lead_nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
            'date_expiration': exp,
            'total_ttc': str(getattr(devis, 'total_ttc', None) or ''),
        })
    out.sort(key=lambda d: (d['date_expiration'], d['reference']))
    return out


def leads_rappel_demande(company, user):
    """VX223 — Leads ayant demandé un RAPPEL téléphonique
    (``contact_preference=='phone_ok'``), le signal le plus chaud du pipeline
    jusqu'ici réduit à un badge PASSIF sur ``LeadCard`` (aucune file ne
    l'alimentait). Exclut perdu/archivé (funnel via STAGES.py — règle #2).
    Portée de visibilité de l'utilisateur respectée (``scope_queryset(...,
    ['owner'])``, même convention que ``relances_du_jour``/
    ``leads_chauds_non_contactes``). Lecture seule, scopée société.
    """
    from .models import Lead

    qs = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        contact_preference='phone_ok',
    )
    qs = portee_leads(qs, user)  # ACRM28 — + périmètre d'entités
    return qs.order_by('-date_creation')


def ma_file_commercial_items(company, user, today=None):
    """VX83 — Items COMMERCIAUX normalisés de la « Ma file » d'un utilisateur,
    prêts pour l'union cross-module de ``records`` (aucun agrégateur dupliqué
    côté records : il consomme CE point d'entrée). Chaque item est un dict
    ``{kind, title, due, link, urgency, montant?}`` — contrat commun à toutes
    les familles de la file. Lecture seule, scopée société + visibilité.

    Quatre familles réunies :
      * relances dues (FG31, ``relances_du_jour`` scope ``overdue`` — en retard
        seulement, l'urgence de la file) ;
      * leads chauds jamais contactés (``leads_chauds_non_contactes``) ;
      * devis ``envoye`` proches d'expiration (``devis_expirant_bientot``) ;
      * VX223 — rappels demandés (``leads_rappel_demande``), famille que VX83
        n'énumérait pas : ``kind='rappel'``, ``urgency='high'`` (ni
        ``overdue`` ni ``today`` — un rappel demandé n'a pas d'échéance
        propre ; le tri de ``records.views.ActivityViewSet.ma_file`` retombe
        sur son rang par défaut pour toute urgence inconnue — hors périmètre
        de cette tâche, cf. ``FilterBar.jsx`` qui expose le même signal en
        chip dédiée, cliquable indépendamment de « Ma file »).
    """
    from core.dates import aujourd_hui_local
    today = today or aujourd_hui_local()
    items = []

    # APRF23 — les familles « lead » ne lisent que id/nom/prénom/relance :
    # aucun préchargement de devis/lignes ni colonne inutile.
    def _leger(qs):
        return (qs.select_related(None).prefetch_related(None)
                .only('id', 'nom', 'prenom', 'relance_date'))

    for lead in _leger(relances_du_jour(
            company, user, scope='overdue', today=today)):
        nom = f'{lead.nom} {lead.prenom or ""}'.strip() or f'Lead #{lead.id}'
        items.append({
            'kind': 'relance',
            'title': f'Relancer {nom}',
            'due': lead.relance_date,
            'link': f'/crm/leads?lead={lead.id}',
            'urgency': 'overdue',
        })

    for lead in _leger(leads_chauds_non_contactes(company, user)):
        nom = f'{lead.nom} {lead.prenom or ""}'.strip() or f'Lead #{lead.id}'
        items.append({
            'kind': 'lead_chaud',
            'title': f'Contacter {nom} (chaud, jamais contacté)',
            'due': None,
            'link': f'/crm/leads?lead={lead.id}',
            'urgency': 'today',
        })

    for d in devis_expirant_bientot(company, user, today=today):
        expire = d['date_expiration'] < today
        items.append({
            'kind': 'devis_expire',
            'title': f'Devis {d["reference"]} — {d["lead_nom"]} '
                     f'{"expiré" if expire else "expire bientôt"}',
            'due': d['date_expiration'],
            'link': f'/crm/leads?lead={d["lead_id"]}',
            'urgency': 'overdue' if expire else 'today',
            'montant': d['total_ttc'] or None,
        })

    # VX223 — rappels demandés : signal le plus chaud du pipeline (un client a
    # explicitement demandé un rappel), jusqu'ici un badge passif jamais
    # remonté dans aucune file.
    for lead in _leger(leads_rappel_demande(company, user)):
        nom = f'{lead.nom} {lead.prenom or ""}'.strip() or f'Lead #{lead.id}'
        items.append({
            'kind': 'rappel',
            'title': f'Rappeler {nom} (rappel demandé)',
            'due': None,
            'link': f'/crm/leads?lead={lead.id}',
            'urgency': 'high',
        })

    return items


# ── CAD-G ── CAD75 — cadences échues à CLORE (liste, jamais une clôture) ────

#: CAD75 — cadences qui peuvent finir « échues » et qu'un humain doit clore.
#: ``reveil`` en est EXCLUE : ``cloturer_cadence`` refuse déjà de clore un
#: plan de réveil (sinon un dormant sans réponse tournerait en boucle), donc
#: une touche de réveil en retard n'a pas de clôture à proposer.
CADENCES_CLOTURABLES = ('contact', 'apres_devis', 'generique')


def cadences_echues_a_clore(company, user, *, jours, today=None, limit=200):
    """CAD75 — les dossiers dont la cadence est ÉCHUE et que PERSONNE n'a clos.

    Le constat (audit L3 du 21/09/2026) : ``cloturer_cadence`` n'a qu'un seul
    appelant, ``marquer_etape_relance`` — tant que l'issue de la DERNIÈRE
    touche n'est pas saisie, le lead n'entre jamais au Froid, ne reçoit ni
    étiquette ni réveil J30/J60, et reste au milieu du pipeline avec une
    touche en retard. Aucune tâche planifiée ne clôt une cadence échue. Le
    dossier réellement abandonné est donc plus mal loti que celui qu'on clôt
    proprement.

    Ce sélecteur ne corrige PAS le moteur : il rend ces dossiers VISIBLES.
    **Il ne clôt rien, n'écrit rien, ne pose aucune étiquette** — la clôture
    reste une décision humaine (garde-fou de la tâche). C'est une LECTURE
    pure, destinée au digest du matin / au cockpit.

    ``jours`` est le seuil de retard, en jours, et il est OBLIGATOIRE : ni le
    texte de la tâche ni aucun réglage société ne porte ce nombre, et la règle
    « zéro chiffre inventé » interdit d'en écrire un ici. L'appelant (digest,
    cockpit) fournit la valeur qu'il affiche à l'écran.

    Renvoie une liste de dicts triés du plus ancien retard au plus récent :
    ``{'etape_id', 'lead_id', 'lead', 'ville', 'stage', 'owner', 'cadence',
    'ordre', 'canal', 'libelle', 'due_date', 'jours_de_retard'}``.
    """
    import datetime as _dt

    from core.dates import aujourd_hui_local
    from .models import RelanceEtape
    from .stages import COLD

    try:
        seuil = int(jours)
    except (TypeError, ValueError):
        raise ValueError(
            'CAD75 — « jours » (seuil de retard) doit être un nombre de '
            'jours.')
    if seuil < 0:
        raise ValueError(
            'CAD75 — « jours » (seuil de retard) ne peut pas être négatif.')

    today = today or aujourd_hui_local()
    limite = max(int(limit or 0), 0)
    if not limite:
        return []

    # Une cadence est ÉCHUE quand une touche encore OUVERTE traîne depuis plus
    # de `jours`. Les archivés et les perdus n'ont rien à clore ; les leads
    # déjà au Froid non plus (ils SONT le résultat de la clôture).
    qs = (RelanceEtape.objects
          .filter(company=company,
                  statut=RelanceEtape.Statut.A_FAIRE,
                  cadence__in=CADENCES_CLOTURABLES,
                  due_date__lt=today - _dt.timedelta(days=seuil),
                  lead__is_archived=False,
                  lead__perdu=False)
          .exclude(lead__stage=COLD)
          .select_related('lead', 'lead__owner'))

    # ACRM28 — portée propriétaire ET périmètre d'entités.
    visibles = leads_visibles(user, company)
    qs = qs.filter(lead_id__in=visibles.values('id'))

    lignes = []
    vus = set()
    for etape in qs.order_by('due_date', 'lead_id', 'ordre')[:limite * 4]:
        # Un lead peut porter plusieurs touches ouvertes (deux plans) : on ne
        # le propose qu'UNE fois, sur son retard le plus ancien.
        if etape.lead_id in vus:
            continue
        vus.add(etape.lead_id)
        lead = etape.lead
        nom = f"{lead.nom or ''} {lead.prenom or ''}".strip()
        if lead.owner_id:
            responsable = (lead.owner.get_full_name()
                           or lead.owner.username or '')
        else:
            responsable = ''
        lignes.append({
            'etape_id': etape.id,
            'lead_id': lead.id,
            'lead': nom,
            'ville': lead.ville or '',
            'stage': lead.stage or '',
            'owner': responsable,
            'cadence': etape.cadence,
            'ordre': etape.ordre,
            'canal': etape.canal,
            'libelle': etape.libelle or '',
            'due_date': etape.due_date.isoformat() if etape.due_date else '',
            'jours_de_retard': ((today - etape.due_date).days
                                if etape.due_date else 0),
        })
        if len(lignes) >= limite:
            break
    return lignes


# ── CAD-I ── CAD87 ──────────────────────────────────────────────────────────
# Les trois mesures qui manquaient à côté de CKP3 (« à quelle heure et quel
# jour joint-on ? », « combien de touches avant une signature ? », « quelle
# part de WhatsApp-seulement et de darija ? ») vivent dans un module à part,
# `apps/crm/mesure_cadence.py` : ce fichier passe déjà 4 800 lignes, et un
# agrégat croisé n'a rien à faire au milieu des lectures de la fiche lead.
# Ce renvoi existe pour que qui cherche un KPI de cadence le trouve ICI.
def mesure_cadence(company, *, jours=None):
    """CAD87 — voir ``apps.crm.mesure_cadence``. Lecture seule."""
    from .mesure_cadence import JOURS_MESURE_DEFAUT
    from .mesure_cadence import mesure_cadence as _mesure
    return _mesure(company,
                   jours=JOURS_MESURE_DEFAUT if jours is None else jours)


# ── CAD-H ── CAD83 — départage de la file du jour ────────────────────────────
#: Rang de tri de ``Lead.priorite``. La colonne est un ``CharField`` : trié tel
#: quel, Postgres rendrait « basse » AVANT « haute ». Le rang explicite met la
#: priorité haute en tête et laisse la basse en fin de tranche.
PRIORITE_RANG_FILE = {'haute': 0, 'normale': 1, 'basse': 2}


#: Rang appliqué à une priorité vide ou inconnue : celui de « normale », pour
#: qu'un lead sans priorité ne soit ni promu ni relégué.
PRIORITE_RANG_DEFAUT = 1


def trier_file_du_jour(qs):
    """CAD83 — ordonne la file du jour (``RelanceEtape``) en utilisant enfin
    les deux signaux DÉJÀ affichés sur la ligne : le badge de priorité et le
    ``ScoreBadge``.

    L'ordre est un ordre d'AFFICHAGE, en DÉPARTAGE seulement :

    1. ``due_date`` croissant — le JOUR d'abord (COCKPIT-CONTRÔLE,
       30/09/2026) : en retard, la plus ancienne en tête, puis aujourd'hui,
       puis les TÂCHES à venir (possibles dès maintenant) par échéance. Avant,
       ``due_at`` passait en premier, si bien qu'une touche en retard SANS
       heure (d'avant MRY5) tombait derrière les tâches à venir.
    2. ``due_at`` croissant, les touches sans heure en dernier DE LEUR
       JOURNÉE — l'ordre à la minute de MRY5, inchangé à jour égal
       (``due_date`` est la date locale de ``due_at``).
    3. **priorité** (haute → normale → basse), puis **score** décroissant
       (les touches sans score en dernier) : ils n'interviennent qu'à heure
       STRICTEMENT égale, donc jamais avant une ``heure_cible``. Un rendez-vous
       pris avec le client à 10 h reste à 10 h, quelle que soit la priorité du
       dossier de 11 h.
    4. ``ordre`` — le barreau du plan, dernier mot (deux touches du même lead
       ont la même priorité et le même score).

    MRY32 reste intact : aucune touche n'est ajoutée, retirée ni déplacée dans
    le temps ; seul l'ordre de lecture intra-tranche change.
    """
    from django.db.models import Case, F, IntegerField, Value, When

    rangs = [
        When(lead__priorite=valeur, then=Value(rang))
        for valeur, rang in PRIORITE_RANG_FILE.items()
    ]
    return qs.annotate(
        cad83_priorite_rang=Case(
            *rangs,
            default=Value(PRIORITE_RANG_DEFAUT),
            output_field=IntegerField(),
        ),
    ).order_by(
        'due_date',
        F('due_at').asc(nulls_last=True),
        'cad83_priorite_rang',
        F('lead__score').desc(nulls_last=True),
        'ordre',
    )
