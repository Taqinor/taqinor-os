"""Signal d'intérêt salle de vente, parrainage et partenaires (SPL19, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging

from django.utils import timezone

from . import stages
from .leads_doublons import normalize_email, normalize_phone
from .leads_socle import _company_fallback_managers
from .models import Client, LeadActivity

logger = logging.getLogger(__name__)


SEUIL_VUES_SIGNAL_INTERET = 3
FENETRE_SIGNAL_INTERET_HEURES = 48


def detecter_signal_interet_salle_vente(salle):
    """NTCRM27 — Si ``salle`` (une ``crm.SalleVente``) est liée à un lead en
    stage QUOTE_SENT et a reçu ``SEUIL_VUES_SIGNAL_INTERET`` vues ou plus en
    moins de ``FENETRE_SIGNAL_INTERET_HEURES``, journalise une note NOTE
    informationnelle « signal d'intérêt fort » sur le chatter du lead
    (JAMAIS un changement de stage automatique) et émet
    ``core.events.salle_vente_signal_interet``. Idempotent PAR JOUR : une
    nouvelle vue au-delà du seuil le même jour ne duplique pas la note.
    Best-effort — appelé depuis la vue publique, ne doit jamais lever.

    CRX31 — le comptage est DÉDUPLIQUÉ PAR APPAREIL ET PAR JOUR. Il portait sur
    les vues BRUTES : trois rechargements de la page par le MÊME visiteur dans
    la même minute déclenchaient « signal d'intérêt fort », et le commercial
    rappelait un client qui n'avait rien fait de plus qu'appuyer sur F5. On
    compte désormais les couples DISTINCTS (empreinte de visiteur, jour local) —
    donc des visites RÉELLEMENT distinctes. Les vues sans empreinte exploitable
    (IP illisible) partagent la clé vide : elles comptent pour UNE, jamais pour
    trois — sous-compter est le bon sens du doute, sur-compter ne l'est pas.
    """
    from django.db.models.functions import TruncDate

    from core.dates import TZ_METIER

    try:
        lead = getattr(salle, 'lead', None)
        if lead is None or lead.stage != stages.QUOTE_SENT:
            return None
        depuis = timezone.now() - timezone.timedelta(hours=FENETRE_SIGNAL_INTERET_HEURES)
        vues_fenetre = salle.vues.filter(created_at__gte=depuis)
        # Jour LOCAL (Africa/Casablanca, CRX26) : le découpage journalier du
        # signal doit être celui du terrain, pas celui d'UTC.
        # `.order_by()` OBLIGATOIRE : ``SalleVenteVue.Meta.ordering`` vaut
        # ``['-created_at']``, et Django ajoute les colonnes de tri au SELECT
        # d'un `.distinct()` — chaque vue redeviendrait alors « distincte » et
        # la déduplication serait un no-op silencieux.
        nb_vues = (vues_fenetre
                   .annotate(jour=TruncDate('created_at', tzinfo=TZ_METIER))
                   .order_by()
                   .values('ip_hash', 'jour')
                   .distinct()
                   .count())
        if nb_vues < SEUIL_VUES_SIGNAL_INTERET:
            return None
        # ALEA3 — idempotence PAR JOUR LOCAL ET PAR SALLE : borne explicite
        # « minuit à Casablanca » (jamais le ``__date`` du fuseau actif, qui
        # dépend de la requête) et la salle nommée en fin de note.
        from core.dates import maintenant_local
        debut_jour = maintenant_local().replace(
            hour=0, minute=0, second=0, microsecond=0)
        deja_note = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='signal d\'intérêt fort',
            body__endswith=f'(salle de vente « {salle.titre} »)',
            created_at__gte=debut_jour,
        ).exists()
        if deja_note:
            return None
        note = LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(
                f"signal d'intérêt fort — {nb_vues} consultations distinctes "
                f"en {FENETRE_SIGNAL_INTERET_HEURES}h "
                f"(salle de vente « {salle.titre} »)"
            ),
        )
        try:
            from core.events import salle_vente_signal_interet
            salle_vente_signal_interet.send(
                sender=type(salle), lead=lead, salle=salle, company=lead.company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'NTCRM27: émission salle_vente_signal_interet échouée pour le lead #%s',
                lead.pk, exc_info=True)
        return note
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTCRM27: détection signal intérêt échouée pour la salle #%s',
            getattr(salle, 'pk', '?'), exc_info=True)
        return None


PARRAINAGE_SIGNUP_MARKER = 'auto — filleul détecté (utm_source=parrainage)'
PARRAINAGE_IGNORED_MARKER = '2e code de parrainage ignoré'
PARRAINAGE_DEJA_ENREGISTRE_MARKER = (
    'Parrainage déjà enregistré pour ce filleul')


def _format_date_fr(valeur):
    """Date FR courte (JJ/MM/AAAA) pour une note chatter, en heure locale.
    Tolérant : toute valeur non datable est rendue telle quelle (une note ne
    casse jamais le flux qui l'écrit)."""
    try:
        return timezone.localtime(valeur).strftime('%d/%m/%Y')
    except Exception:  # noqa: BLE001 — jamais bloquant pour une note
        return str(valeur)


def handle_parrainage_signup(lead) -> None:
    """QX35 — Wire la promesse de la page /parrainage : un lead capté avec
    ``utm_source=parrainage`` crée automatiquement un ``Parrainage`` en
    attente, rattaché au CLIENT parrain identifié par son code (porté par
    ``utm_campaign`` — voir ``apps/web/src/pages/parrainage.astro``, le lien
    personnel est `?utm_source=parrainage&utm_campaign=<code>`).

    Idempotent PAR FILLEUL (18/08/2026 — décision fondateur). Depuis que
    chaque soumission du site CRÉE un nouveau ``Lead`` (règle fondateur du
    18/08/2026), le même filleul qui re-soumet /parrainage obtient une fiche
    DIFFÉRENTE à chaque fois — la seule garde ``Parrainage.objects.filter(
    filleul_lead=lead)`` (idempotente PAR LEAD, conservée ci-dessous pour le
    replay du MÊME lead) ne voit donc plus ces reprises et laissait créer un
    2e ``Parrainage en_attente`` pour la même personne. Le filleul est donc
    aussi identifié par TÉLÉPHONE/E-MAIL normalisés parmi tous les
    ``Parrainage`` déjà posés pour la société :
      - même filleul, MÊME parrain → aucun 2e ``Parrainage``, mais une note
        chatter sobre sur le NOUVEAU lead (jamais une sortie silencieuse :
        une recommandation qui ne laisse aucune trace est une
        recommandation perdue) ;
      - même filleul, parrain DIFFÉRENT → cas ambigu : on GARDE le premier
        parrainage (jamais réattribué) et on pose une note chatter sur le
        NOUVEAU lead expliquant que son code a été ignoré.

    no-op (comportement inchangé) si ``utm_source`` n'est pas
    ``'parrainage'``, si le code de parrain est absent/inconnu, ou en cas
    d'auto-parrainage (le filleul est déjà le même téléphone/email que le
    parrain — anti-abus minimal). Notifie les managers de la société (repli
    ``_company_fallback_managers``, pas de owner dédié à ce stade).
    Best-effort — jamais d'exception propagée."""
    try:
        if (getattr(lead, 'utm_source', None) or '').strip().lower() != 'parrainage':
            return
        from .models import Parrainage

        if Parrainage.objects.filter(filleul_lead=lead).exists():
            return  # déjà traité (idempotent — visiteur revenant, replay).

        code = (getattr(lead, 'utm_campaign', None) or '').strip()
        if not code:
            return
        parrain = Client.objects.filter(
            company=lead.company, code_parrainage=code).first()
        if parrain is None:
            return  # code inconnu/périmé — jamais bloquant, jamais d'erreur.

        # Anti auto-parrainage minimal : même téléphone/email normalisé que
        # le parrain → on ne crée rien (le parrain ne peut pas se parrainer
        # lui-même, ni un dossier déjà connu sous une autre forme — promesse
        # affichée sur /parrainage).
        lead_phone = normalize_phone(getattr(lead, 'telephone', None))
        lead_email = normalize_email(getattr(lead, 'email', None))
        parrain_phone = normalize_phone(getattr(parrain, 'telephone', None))
        parrain_email = normalize_email(getattr(parrain, 'email', None))
        if ((lead_phone and lead_phone == parrain_phone)
                or (lead_email and lead_email == parrain_email)):
            return

        # Idempotence PAR FILLEUL (voir docstring) : cherche un Parrainage
        # déjà posé pour la société dont le filleul_lead partage le téléphone
        # OU l'e-mail normalisé du lead courant — le PREMIER (plus ancien)
        # fait foi.
        existing_signup = None
        if lead_phone or lead_email:
            from django.db.models import Q
            contact_q = Q()
            if lead_phone:
                contact_q |= Q(filleul_lead__phone_normalise=lead_phone)
            if lead_email:
                contact_q |= Q(filleul_lead__email_normalise=lead_email)
            existing_signup = (
                Parrainage.objects
                .filter(company=lead.company)
                .exclude(filleul_lead__isnull=True)
                .filter(contact_q)
                .order_by('date_creation')
                .first()
            )
        if existing_signup is not None:
            if existing_signup.parrain_id == parrain.pk:
                # Même filleul, MÊME parrain : rien à recréer — mais plus de
                # sortie SILENCIEUSE. Deux salariés d'un même client (adresse
                # `contact@societe.ma` partagée) ou un foyer au même mobile
                # tombent ici : sans trace, la 2e recommandation disparaissait
                # du CRM sans que personne ne puisse savoir qu'elle a existé.
                # Une note sobre sur le NOUVEAU lead, jamais un 2e Parrainage.
                LeadActivity.objects.create(
                    company=lead.company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'{PARRAINAGE_DEJA_ENREGISTRE_MARKER} (parrain '
                          f'{parrain.nom}, '
                          f'{_format_date_fr(existing_signup.date_creation)}) '
                          '— pas de doublon créé.'),
                )
                return
            # Parrain DIFFÉRENT sur re-soumission : cas ambigu — on GARDE le
            # premier parrainage (jamais réattribué), on note l'ignoré.
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=(f'{PARRAINAGE_IGNORED_MARKER} (déjà parrainé par '
                      f'{existing_signup.parrain.nom}).'),
            )
            return

        Parrainage.objects.create(
            company=lead.company, parrain=parrain,
            filleul_lead=lead, filleul_nom=lead.nom or '',
            statut=Parrainage.Statut.EN_ATTENTE,
        )
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'{PARRAINAGE_SIGNUP_MARKER} — parrain : {parrain.nom}.',
        )

        managers = _company_fallback_managers(lead.company)
        if managers:
            from apps.notifications.services import notify_many
            nom = (lead.nom or '').strip() or 'Un prospect'
            notify_many(
                managers,
                'lead_new',
                f'🤝 Parrainage : {parrain.nom} recommande {nom}',
                body=(f'{nom} est arrivé via le lien de parrainage de '
                      f'{parrain.nom} (code {code}).'),
                link=f'/crm/parrainage?parrain={parrain.pk}',
                company=lead.company,
            )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QX35: handle_parrainage_signup échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


# ── NTMIG28 — miroir du compteur de déploiements d'un partenaire ────────────


def poser_compteur_deploiements(partenaire_id, company, nb_reussis):
    """Pose le nombre de déploiements RÉUSSIS reconnus d'un partenaire.

    Point d'entrée d'ÉCRITURE pour ``apps.migration`` (qui possède la table des
    déploiements) : la fiche partenaire vit ici, donc c'est ici qu'on l'écrit —
    jamais un ``Partenaire.objects.update()`` depuis une autre app.

    Le compteur est un MIROIR dénormalisé, jamais la source : l'appelant fournit
    le total qu'il vient de recompter sur SA table, on ne le devine pas ici.
    Renvoie le partenaire mis à jour, ou ``None`` si l'id ne désigne aucun
    partenaire de cette société (jamais une écriture cross-tenant).
    """
    from .models import Partenaire

    partenaire = Partenaire.objects.filter(
        pk=partenaire_id, company=company).first()
    if partenaire is None:
        return None
    nb_reussis = max(0, int(nb_reussis or 0))
    if partenaire.nb_deploiements_reussis != nb_reussis:
        partenaire.nb_deploiements_reussis = nb_reussis
        partenaire.save(update_fields=['nb_deploiements_reussis'])
    return partenaire


# ── NTMIG31 — spécialité proposée par un parcours de formation partenaire ───

def ajouter_specialite_partenaire(partenaire_id, company, specialite):
    """Ajoute UNE spécialité à la fiche partenaire si elle n'y est pas déjà.

    Point d'entrée d'ÉCRITURE pour ``apps.migration`` (qui possède le parcours
    de certification NTMIG31) : la fiche partenaire vit ici, donc c'est ici
    qu'on l'écrit — jamais un ``Partenaire.objects.update()`` depuis une
    autre app. N'ajoute QUE si la clé appartient au référentiel FERMÉ
    (``Partenaire.SPECIALITES_CLES``) — une spécialité hors liste rendrait
    l'annuaire des certifiés (NTMIG29) infiltrable par une clé libre.
    L'action reste une PROPOSITION validée explicitement par un admin en
    amont (jamais un effet de bord automatique de fin de parcours) ; cette
    fonction ne fait qu'exécuter la validation déjà décidée. Idempotent :
    une spécialité déjà présente n'est jamais dupliquée. Renvoie le
    partenaire mis à jour, ou ``None`` si l'id ne désigne aucun partenaire de
    cette société (jamais une écriture cross-tenant).
    """
    from .models import Partenaire

    partenaire = Partenaire.objects.filter(
        pk=partenaire_id, company=company).first()
    if partenaire is None:
        return None
    if specialite not in Partenaire.SPECIALITES_CLES:
        return partenaire
    specialites = list(partenaire.specialites or [])
    if specialite not in specialites:
        specialites.append(specialite)
        partenaire.specialites = specialites
        partenaire.save(update_fields=['specialites'])
    return partenaire


# ── NTPRT28 — Deal registration : soumission d'un lead par un partenaire ────
#
# Point d'entrée d'ÉCRITURE pour ``apps.portail`` (le portail partenaire
# authentifié) : la fiche partenaire et ses soumissions vivent ici, donc c'est
# ici qu'on les écrit — jamais un ``SoumissionLeadPartenaire.objects.create()``
# depuis une autre app.

#: NTPRT28 — fenêtre pendant laquelle une re-soumission du MÊME prospect par le
#: MÊME partenaire est traitée comme un doublon (critère d'acceptation).
FENETRE_DOUBLON_SOUMISSION_JOURS = 30


def soumission_partenaire_deja_faite(company, partenaire_id, email_prospect,
                                     fenetre_jours=None,
                                     telephone_prospect=None):
    """NTPRT28 — soumission RÉCENTE du même prospect par le même partenaire.

    Renvoie la soumission existante, ou ``None``. La comparaison se fait sur
    l'email du prospect, normalisé (casse/espaces) quand il est fourni.

    ADOC145 (C-ADOC-057) — quand l'email est VIDE, la clé est le téléphone
    du prospect, normalisé par ``normalize_phone`` (la MÊME normalisation que
    la déduplication des leads CRM — jamais une seconde) : '0611111111' et
    '+212 611111111' sont le même prospect. Sans email NI téléphone
    exploitable, jamais de doublon — deux prospects anonymes distincts ne
    s'annulent pas, et deux téléphones différents restent deux soumissions.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import SoumissionLeadPartenaire

    email = (email_prospect or '').strip().lower()
    telephone = normalize_phone(telephone_prospect)
    if company is None or not partenaire_id or not (email or telephone):
        return None
    jours = (FENETRE_DOUBLON_SOUMISSION_JOURS if fenetre_jours is None
             else fenetre_jours)
    depuis = timezone.now() - timedelta(days=jours)
    recentes = (SoumissionLeadPartenaire.objects
                .filter(company=company, partenaire_id=partenaire_id,
                        date_soumission__gte=depuis)
                .order_by('-date_soumission'))
    if email:
        return recentes.filter(email_prospect__iexact=email).first()
    # Le téléphone est stocké tel que saisi : la normalisation se fait ici,
    # sur les seules soumissions récentes de CE partenaire (ensemble borné).
    for soumission in recentes.exclude(telephone_prospect=''):
        if normalize_phone(soumission.telephone_prospect) == telephone:
            return soumission
    return None


def soumettre_lead_partenaire(company, partenaire_id, donnees):
    """NTPRT28 — enregistre la soumission d'un prospect par un partenaire.

    Renvoie ``(soumission, doublon)`` :

    * ``(None, None)`` — le partenaire n'existe pas dans CETTE société (jamais
      d'écriture cross-tenant) ;
    * ``(None, existante)`` — une soumission du MÊME prospect par le MÊME
      partenaire date de moins de 30 jours : RIEN n'est créé, l'appelant
      signale « déjà soumis » (jamais de doublon silencieux) ;
    * ``(creee, None)`` — nominal.

    ``company`` et ``partenaire`` sont posés par le serveur ; seuls les champs
    de coordonnées du prospect sont lus de ``donnees``. Le statut naît
    ``SOUMIS`` : la qualification (et la création du lead réel, référencé par
    ``lead_id`` — la piste de traçabilité pour la commission) reste un acte
    INTERNE, jamais un effet de bord de la soumission.
    """
    from .models import Partenaire, SoumissionLeadPartenaire

    if company is None or not partenaire_id:
        return None, None
    partenaire = (Partenaire.objects
                  .filter(company=company, pk=partenaire_id).first())
    if partenaire is None:
        return None, None

    donnees = donnees or {}
    email = str(donnees.get('email_prospect') or '').strip()
    existante = soumission_partenaire_deja_faite(
        company, partenaire.id, email,
        telephone_prospect=donnees.get('telephone_prospect'))
    if existante is not None:
        return None, existante

    soumission = SoumissionLeadPartenaire.objects.create(
        company=company,
        partenaire=partenaire,
        nom_prospect=str(donnees.get('nom_prospect') or '').strip()[:200],
        telephone_prospect=str(
            donnees.get('telephone_prospect') or '').strip()[:30],
        email_prospect=email[:254],
        ville=str(donnees.get('ville') or '').strip()[:120],
        note=str(donnees.get('note') or '').strip()[:4000],
        statut=SoumissionLeadPartenaire.Statut.SOUMIS,
    )
    return soumission, None
