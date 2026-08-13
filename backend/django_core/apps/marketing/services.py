"""Services du module Marketing (``apps.marketing``).

ODX10 — ré-export TRANSITOIRE des fonctions de service marketing qui vivent
encore physiquement dans ``apps.compta.services`` (elles y étaient interleavées
avec la logique comptable ; les extraire du fichier de 500 Ko en un seul move
serait un risque de régression non vérifiable hors suite complète). Ce module
donne au reste du code (receivers marketing, urls, appelants cross-app) un point
d'accès ``apps.marketing.services`` stable ; ODX22 re-logera le corps des
fonctions ici et retirera ce shim.

``marketing`` ne lit crm/ventes QUE via leurs selectors/services ou par
référence opaque — jamais leurs ``models`` (invariant CLAUDE.md déjà tenu par
les fonctions ré-exportées, qui référencent lead_id/devis_id opaques).
"""

from apps.compta.services import (  # noqa: F401
    annuler_campagne,
    appliquer_mouvement_fidelite,
    approuver_envoi_campagne,
    campagnes_par_statut,
    clics_par_lien,
    compteurs_par_etape,
    cout_total_campagne,
    creer_enquete,
    decider_gagnant_ab,
    demander_ou_envoyer_campagne,
    dupliquer_campagne,
    enregistrer_ouverture_partage,
    enregistrer_relance_devis_abandonne,
    envelopper_liens_campagne,
    envoyer_campagne,
    envoyer_campagnes_planifiees,
    envoyer_enquete_nps,
    envoyer_test_campagne,
    executer_etapes_dues,
    inscrire_lead_sequence,
    leads_source_roi,
    nb_participants_actifs,
    participants_sequence,
    planifier_campagne,
    planifier_etapes_sequence,
    pousser_avis_google,
    precheck_sante_campagne,
    questions_visibles,
    recalculer_compteurs_campagne,
    rejeter_envoi_campagne,
    rendre_pour_lead,
    renvoyer_echecs_campagne,
    reporting_campagnes,
    repondre_enquete_nps,
    roi_campagne,
    score_nps,
    sortir_inscription,
    sortir_inscriptions_pour_lead,
    suggestions_upsell,
    traces_sequence,
    valider_questions_enquete,
    variante_pour_langue,
    webhook_brevo_evenement,
)


# ── WIR64 / FG206 — Capture de lead publique depuis un FormulaireIntake ──────
# Écrit dans le domaine crm UNIQUEMENT via ``apps.crm.services`` (jamais un
# import des modèles crm — invariant CLAUDE.md/M3). La société vient TOUJOURS
# du formulaire résolu côté serveur, jamais du corps de la requête publique.

# ── NTMKT22 — Centre de préférences self-service (public, tokenisé) ────────
# XMKT3 ne sait que DÉSINSCRIRE totalement. Ici le contact choisit PAR CANAL
# et PAR LISTE ce qu'il veut recevoir. Le registre de consentement est celui
# de la plateforme (``core.ConsentRecord``) — jamais un second registre — et
# les listes sont les ``AbonnementListe`` existantes (XMKT5).

_PREFERENCES_SALT = 'marketing.ntmkt22.preferences'

#: canaux exposés au contact, et leur finalité ``ConsentRecord`` (même
#: correspondance que XMKT4, pour que le prochain envoi respecte le choix).
CANAUX_PREFERENCES = (
    ('email', 'email'),
    ('sms', 'sms'),
    ('whatsapp', 'whatsapp'),
)


def generer_token_preferences(company_id, destinataire):
    """Jeton signé du centre de préférences (NTMKT22) — même modèle de
    confiance que le lien de désinscription XMKT3 (signature ``SECRET_KEY``,
    société + destinataire portés par le jeton, jamais par l'URL en clair)."""
    from django.core import signing
    return signing.dumps(
        {'company_id': company_id, 'destinataire': destinataire},
        salt=_PREFERENCES_SALT)


def lien_preferences(company, destinataire):
    """Chemin public du centre de préférences, à placer à côté du lien de
    désinscription dans le pied de campagne (``{lien_preferences}``)."""
    return f'/api/django/marketing/preferences/{generer_token_preferences(company.id, destinataire)}/'


def lire_token_preferences(token):
    """Résout un jeton de préférences en ``(company, destinataire)``.

    Jeton invalide/corrompu/société supprimée → ``(None, None)`` : l'appelant
    répond proprement, jamais une 500 ni une fuite d'existence.
    """
    from django.core import signing
    try:
        payload = signing.loads(token, salt=_PREFERENCES_SALT)
    except signing.BadSignature:
        return None, None
    from authentication.models import Company
    company = Company.objects.filter(id=payload.get('company_id')).first()
    destinataire = (payload.get('destinataire') or '').strip()
    if company is None or not destinataire:
        return None, None
    return company, destinataire


def preferences_actuelles(company, destinataire):
    """État courant des préférences d'un contact (NTMKT22).

    Un canal sans aucune entrée de consentement est considéré ACCORDÉ —
    comportement historique XMKT4 strictement préservé.
    """
    from core.models import ConsentRecord
    from .models import AbonnementListe, ListeDiffusion
    canaux = {}
    for canal, purpose in CANAUX_PREFERENCES:
        dernier = (ConsentRecord.objects
                   .filter(company=company, subject_identifier=destinataire,
                           purpose=purpose)
                   .order_by('-id').first())
        canaux[canal] = True if dernier is None else bool(dernier.granted)
    abonnements = {
        a.liste_id: a.statut
        for a in AbonnementListe.objects.filter(
            company=company, destinataire=destinataire)
    }
    listes = [
        {
            'id': liste.id,
            'nom': liste.nom,
            'abonne': abonnements.get(liste.id) == AbonnementListe.Statut.INSCRIT,
        }
        for liste in ListeDiffusion.objects.filter(company=company)
    ]
    return {'destinataire': destinataire, 'canaux': canaux, 'listes': listes}


def enregistrer_preferences(company, destinataire, data=None,
                            *, source='centre_preferences'):
    """Enregistre les choix du contact (NTMKT22).

    ``data`` = {'canaux': {'email': False, …}, 'listes': {'<id>': True, …}}.
    Chaque canal cité crée une entrée ``core.ConsentRecord`` (traçabilité
    loi 09-08 : le registre est un JOURNAL, jamais réécrit sur place) ; chaque
    liste citée bascule son ``AbonnementListe``. Une clé absente n'est pas
    touchée — couper l'email ne désinscrit jamais de WhatsApp.
    """
    from django.utils import timezone
    from core.models import ConsentRecord
    from .models import AbonnementListe, ListeDiffusion
    data = data or {}
    purposes = dict(CANAUX_PREFERENCES)
    choix_canaux = data.get('canaux') or {}
    for canal, valeur in choix_canaux.items():
        purpose = purposes.get(str(canal).strip().lower())
        if purpose is None:
            continue
        ConsentRecord.objects.create(
            company=company,
            subject_identifier=destinataire,
            purpose=purpose,
            granted=bool(valeur),
            source=source,
            occurred_at=timezone.now(),
        )
    choix_listes = data.get('listes') or {}
    for liste_id, valeur in choix_listes.items():
        try:
            liste_id = int(liste_id)
        except (TypeError, ValueError):
            continue
        liste = ListeDiffusion.objects.filter(
            company=company, id=liste_id).first()
        if liste is None:
            continue
        statut = (AbonnementListe.Statut.INSCRIT if valeur
                  else AbonnementListe.Statut.DESINSCRIT)
        AbonnementListe.objects.update_or_create(
            liste=liste, destinataire=destinataire,
            defaults={'company': company, 'statut': statut},
        )
    return preferences_actuelles(company, destinataire)


def derniere_version_publiee(formulaire):
    """NTMKT16 — dernière version PUBLIÉE d'une landing page, ou ``None``.

    La page publique n'affiche jamais un brouillon : tant qu'aucune version
    n'est publiée, le rendu reste EXACTEMENT celui d'avant NTMKT16.
    """
    return (formulaire.versions.filter(publie=True)
            .order_by('-version', '-id')
            .first())


def creer_version_formulaire(formulaire, data=None):
    """NTMKT16 — crée une nouvelle version BROUILLON du contenu de page.

    Le numéro de version est calculé côté serveur (plus haut utilisé + 1 —
    jamais un count(), qui régresse à la suppression) et n'est jamais accepté
    du corps de la requête ; la société vient du formulaire.
    """
    from django.db.models import Max
    from .models import VersionFormulaireIntake
    data = data or {}
    plus_haute = (formulaire.versions.aggregate(m=Max('version'))['m'] or 0)
    return VersionFormulaireIntake.objects.create(
        company=formulaire.company,
        formulaire=formulaire,
        version=plus_haute + 1,
        titre=data.get('titre') or '',
        pitch=data.get('pitch') or '',
        image_key=data.get('image_key') or '',
        publie=False,
    )


def publier_version_formulaire(version):
    """NTMKT16 — publie une version : la page publique bascule dessus.

    Les versions antérieures restent consultables (historique complet) ;
    seule la PLUS RÉCENTE publiée est rendue.
    """
    from django.utils import timezone
    if not version.publie:
        version.publie = True
        version.date_publication = timezone.now()
        version.save(update_fields=['publie', 'date_publication'])
    return version


def formulaire_intake_actif_par_slug(slug):
    """WIR64 — résout un FormulaireIntake ACTIF par son slug public (lookup
    par slug, cf. NTMKT16). Renvoie le formulaire ou ``None``. La société est
    portée par le formulaire trouvé — jamais lue d'un paramètre public."""
    from .models import FormulaireIntake
    return (FormulaireIntake.objects
            .filter(slug=slug, actif=True)
            .order_by('id')
            .first())


def creer_lead_depuis_intake(formulaire, data):
    """WIR64/FG206 — crée un lead depuis la soumission publique d'un
    ``FormulaireIntake``, via ``crm.services`` (jamais d'import des modèles
    crm). Le ``type_installation`` par défaut du formulaire pré-remplit le
    lead ; le ``tag_prefill`` est posé comme tag après création. ``nom`` est
    obligatoire (``ValueError`` sinon, remonté en 400 par la vue). La société
    est forcée depuis ``formulaire.company``."""
    from apps.crm.services import create_lead_from_public_api, poser_tag_lead
    data = data or {}
    fields = {
        'nom': data.get('nom'),
        'prenom': data.get('prenom'),
        'societe': data.get('societe'),
        'email': data.get('email'),
        'telephone': data.get('telephone'),
        'ville': data.get('ville'),
    }
    if formulaire.type_installation:
        fields['type_installation'] = formulaire.type_installation
    lead = create_lead_from_public_api(company=formulaire.company, fields=fields)
    if formulaire.tag_prefill:
        poser_tag_lead(lead, None, formulaire.tag_prefill)
    return lead


# ── NTMKT12 — Parcours en GRAPHE d'une séquence de relance ──────────────────
# Extension strictement ADDITIVE du moteur XMKT1 : une séquence SANS nœud n'est
# jamais vue par ce code (``sequence_a_graphe`` faux) et continue d'être
# déroulée à l'octet par ``compta.services.executer_etapes_dues``. Une séquence
# AVEC nœuds n'a pas d'``EtapeSequence`` : ses inscriptions portent
# ``etape_courante=None`` et sont donc naturellement ignorées par le moteur
# linéaire (qui filtre sur ``etape_courante__isnull=False``) — aucune double
# exécution possible.

# Garde-fou anti-boucle : un cycle dans le graphe ne doit jamais faire tourner
# le tick indéfiniment.
MAX_NOEUDS_PAR_TICK = 50


def sequence_a_graphe(sequence):
    """La séquence porte-t-elle un graphe de journey (NTMKT12) ?"""
    from .models import NoeudJourney
    return NoeudJourney.objects.filter(sequence=sequence).exists()


def noeud_initial(sequence):
    """Nœud d'entrée du graphe : le premier ``declencheur``, à défaut le nœud
    de plus petit id. ``None`` si la séquence n'a pas de graphe."""
    from .models import NoeudJourney
    noeuds = NoeudJourney.objects.filter(sequence=sequence).order_by('id')
    return (noeuds.filter(type_noeud=NoeudJourney.Type.DECLENCHEUR).first()
            or noeuds.first())


def _lead_du_parcours(inscription):
    """Lead de l'inscription, lu via le selector crm (jamais ses models)."""
    from apps.crm.selectors import get_company_lead
    try:
        return get_company_lead(inscription.company, inscription.lead_id)
    except Exception:
        return None


def _condition_arc_vraie(inscription, arc):
    """NTMKT12 — évalue la condition d'un arc sur les traces EXISTANTES
    (``EnvoiCampagne`` XMKT2 pour l'ouverture/le clic) et sur le lead lu via
    ``crm.selectors`` (score/tag). Toute condition inconnue est fausse."""
    from .models import ArcJourney, EnvoiCampagne
    condition = arc.condition or ArcJourney.Condition.TOUJOURS
    if condition == ArcJourney.Condition.TOUJOURS:
        return True
    if condition in (ArcJourney.Condition.A_OUVERT,
                     ArcJourney.Condition.A_CLIQUE):
        champ = ('ouvert_le' if condition == ArcJourney.Condition.A_OUVERT
                 else 'clique_le')
        filtre = {
            f'{champ}__isnull': False,
            f'{champ}__gte': inscription.declenchee_le,
        }
        return EnvoiCampagne.objects.filter(
            company=inscription.company,
            contact_ref=f'lead:{inscription.lead_id}',
            **filtre).exists()
    lead = _lead_du_parcours(inscription)
    if lead is None:
        return False
    if condition == ArcJourney.Condition.SCORE_SEUIL:
        try:
            seuil = float(arc.valeur)
        except (TypeError, ValueError):
            return False
        return float(getattr(lead, 'score', 0) or 0) >= seuil
    if condition == ArcJourney.Condition.TAG_PRESENT:
        tag = (arc.valeur or '').strip().lower()
        if not tag:
            return False
        tags = (getattr(lead, 'tags', '') or '').lower()
        return tag in [t.strip() for t in tags.split(',') if t.strip()]
    return False


def arc_suivant(inscription, noeud):
    """Premier arc sortant (par ``ordre``) dont la condition est vraie."""
    for arc in noeud.arcs_sortants.all().order_by('ordre', 'id'):
        if _condition_arc_vraie(inscription, arc):
            return arc
    return None


def prochaine_echeance_ouvree(depuis, company, *, heure=9, jour_semaine=None,
                              max_jours=60):
    """NTMKT14 — prochain créneau OUVRÉ à ``heure`` strictement après
    ``depuis``.

    Les jours fériés / non ouvrés et la nuit viennent de
    ``apps.notifications.selectors.est_hors_fenetre_silence`` (jamais un
    import des modèles ``notifications``). ``jour_semaine`` (0 = lundi) permet
    « le prochain lundi 9h » ; sans lui, c'est le prochain jour ouvré.
    """
    from django.utils import timezone
    from apps.notifications.selectors import est_hors_fenetre_silence
    heure = max(0, min(23, int(heure or 0)))
    candidat = timezone.localtime(depuis).replace(
        hour=heure, minute=0, second=0, microsecond=0)
    if candidat <= timezone.localtime(depuis):
        candidat += timezone.timedelta(days=1)
    for _ in range(max_jours):
        jour_ok = (jour_semaine is None
                   or candidat.weekday() == int(jour_semaine))
        if jour_ok and not est_hors_fenetre_silence(candidat, company):
            return candidat
        candidat += timezone.timedelta(days=1)
    return candidat


def echeance_noeud(inscription, noeud):
    """Instant à partir duquel le nœud d'attente est franchissable.

    ``attente``         = J+``config.delai_jours`` depuis l'entrée sur le nœud.
    ``attente_jusqu_a`` = NTMKT14, selon ``config.mode`` :
        * ``date``      -> date/heure absolue (``config.date``, ISO) ;
        * sinon         -> prochain créneau ouvré (``config.heure``, défaut 9h,
                           et ``config.jour_semaine`` optionnel, 0 = lundi).
    Tout autre type est franchissable immédiatement.
    """
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    from .models import NoeudJourney
    depuis = inscription.noeud_depuis or inscription.declenchee_le
    config = noeud.config or {}
    if noeud.type_noeud == NoeudJourney.Type.ATTENTE:
        try:
            jours = int(config.get('delai_jours') or 0)
        except (TypeError, ValueError):
            jours = 0
        return depuis + timezone.timedelta(days=max(jours, 0))
    if noeud.type_noeud == NoeudJourney.Type.ATTENTE_JUSQU_A:
        if (config.get('mode') or '') == 'date':
            brut = parse_datetime(str(config.get('date') or '')) or None
            if brut is None:
                return depuis
            if timezone.is_naive(brut):
                brut = timezone.make_aware(
                    brut, timezone.get_current_timezone())
            return brut
        jour_semaine = config.get('jour_semaine')
        try:
            jour_semaine = (None if jour_semaine in (None, '')
                            else int(jour_semaine))
        except (TypeError, ValueError):
            jour_semaine = None
        return prochaine_echeance_ouvree(
            depuis, inscription.company,
            heure=config.get('heure', 9), jour_semaine=jour_semaine)
    return depuis


def _tracer_noeud(inscription, noeud, *, resultat='planifie', canal='',
                  erreur=''):
    """Trace l'exécution d'un nœud dans le journal EXISTANT
    (``ExecutionEtapeSequence``) — jamais un second registre de traces."""
    from .models import ExecutionEtapeSequence
    return ExecutionEtapeSequence.objects.create(
        company=inscription.company,
        inscription=inscription,
        etape=None,
        noeud=noeud,
        canal=canal or '',
        resultat=resultat,
        erreur=erreur or '',
    )


def _positionner(inscription, noeud, *, maintenant):
    """Place l'inscription sur ``noeud`` (ou la termine si ``None``)."""
    from .models import InscriptionSequence
    if noeud is None:
        inscription.noeud_courant = None
        inscription.noeud_depuis = None
        inscription.statut = InscriptionSequence.Statut.TERMINE
        inscription.save(update_fields=[
            'noeud_courant', 'noeud_depuis', 'statut'])
        return
    inscription.noeud_courant = noeud
    inscription.noeud_depuis = maintenant
    inscription.save(update_fields=['noeud_courant', 'noeud_depuis'])


def avancer_journey(inscription, *, maintenant=None):
    """Fait avancer UNE inscription dans le graphe de sa séquence (NTMKT12).

    Renvoie la liste des traces créées. S'arrête sur un nœud d'attente non
    échu, sur un nœud de sortie, ou quand aucun arc sortant n'est empruntable
    (fin de parcours → inscription terminée).
    """
    from django.utils import timezone
    from .models import InscriptionSequence, NoeudJourney
    maintenant = maintenant or timezone.now()
    traces = []
    if inscription.statut != InscriptionSequence.Statut.ACTIF:
        return traces
    if inscription.noeud_courant is None:
        depart = noeud_initial(inscription.sequence)
        if depart is None:
            return traces
        _positionner(inscription, depart, maintenant=maintenant)
    for _ in range(MAX_NOEUDS_PAR_TICK):
        noeud = inscription.noeud_courant
        if noeud is None:
            break
        if noeud.type_noeud == NoeudJourney.Type.SORTIE:
            inscription.noeud_courant = None
            inscription.noeud_depuis = None
            inscription.statut = InscriptionSequence.Statut.TERMINE
            inscription.save(update_fields=[
                'noeud_courant', 'noeud_depuis', 'statut'])
            break
        if noeud.type_noeud in (NoeudJourney.Type.ATTENTE,
                                NoeudJourney.Type.ATTENTE_JUSQU_A):
            if maintenant < echeance_noeud(inscription, noeud):
                break
        elif noeud.type_noeud == NoeudJourney.Type.ACTION:
            config = noeud.config or {}
            traces.append(_tracer_noeud(
                inscription, noeud, canal=str(config.get('canal') or '')))
        arc = arc_suivant(inscription, noeud)
        _positionner(inscription, arc.cible if arc else None,
                     maintenant=maintenant)
        if arc is None:
            break
    return traces


def instancier_modele_journey(company, modele, *, nom=None,
                              stage_declencheur=''):
    """NTMKT15 — instancie un ``ModeleJourney`` en une NOUVELLE séquence
    éditable (nœuds + arcs NTMKT12), désactivée par défaut.

    Le graphe du modèle référence ses nœuds par une ``cle`` textuelle ; la
    correspondance clé → nœud créé est locale à cette instanciation (aucune
    fuite entre modèles, aucune modification du modèle source).
    """
    from .models import ArcJourney, NoeudJourney, SequenceRelance
    graphe = modele.graphe or {}
    sequence = SequenceRelance.objects.create(
        company=company,
        nom=nom or modele.nom,
        stage_declencheur=stage_declencheur or '',
        actif=False,
    )
    par_cle = {}
    for brut in graphe.get('noeuds') or []:
        noeud = NoeudJourney.objects.create(
            company=company,
            sequence=sequence,
            type_noeud=brut.get('type_noeud') or NoeudJourney.Type.ACTION,
            libelle=brut.get('libelle') or '',
            position_x=int(brut.get('position_x') or 0),
            position_y=int(brut.get('position_y') or 0),
            config=brut.get('config') or {},
        )
        if brut.get('cle'):
            par_cle[str(brut['cle'])] = noeud
    for brut in graphe.get('arcs') or []:
        source = par_cle.get(str(brut.get('source')))
        cible = par_cle.get(str(brut.get('cible')))
        if source is None or cible is None:
            continue
        ArcJourney.objects.create(
            company=company,
            source=source,
            cible=cible,
            condition=(brut.get('condition')
                       or ArcJourney.Condition.TOUJOURS),
            valeur=brut.get('valeur') or '',
            ordre=int(brut.get('ordre') or 1),
        )
    return sequence


def executer_journeys_dus(company, *, maintenant=None):
    """Tick des séquences EN GRAPHE d'une société (NTMKT12).

    Pendant graphe de ``compta.services.executer_etapes_dues`` (linéaire), qui
    reste la seule voie pour les séquences sans nœud.
    """
    from django.utils import timezone
    from .models import InscriptionSequence, NoeudJourney
    maintenant = maintenant or timezone.now()
    sequences_graphe = set(
        NoeudJourney.objects.filter(company=company)
        .values_list('sequence_id', flat=True))
    if not sequences_graphe:
        return []
    traces = []
    inscriptions = InscriptionSequence.objects.filter(
        company=company,
        statut=InscriptionSequence.Statut.ACTIF,
        sequence_id__in=sequences_graphe,
    ).select_related('sequence', 'noeud_courant')
    for inscription in inscriptions:
        traces.extend(avancer_journey(inscription, maintenant=maintenant))
    return traces
