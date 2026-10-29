"""Attribution des leads par le responsable d'équipe (fondateur, 27/10/2026).

Quand l'équipe qui reçoit les nouveaux leads a « Le responsable confirme
chaque lead » coché (``EquipeCommerciale.confirmation_responsable``) :

1. ``leads_attribution.default_responsable_for`` rend le RESPONSABLE (le lead
   reste visible chez lui) MARQUÉ par ``marquer_en_attente`` ;
2. le récepteur ``post_save`` du lead (``receivers.py``) appelle
   ``appliquer_mise_en_attente`` : la ligne ``AttributionEnAttente`` est posée
   avec la PROPOSITION (règles de Paramètres → Leads dans l'ordre, sinon
   rotation équilibrée) et l'échéance en minutes OUVRÉES ;
3. le responsable confirme ou change (``attribuer``), ou la tâche Celery
   ``attribuer_echeances`` part sur la proposition une fois l'échéance passée.

Point CENTRAL : toutes les portes d'entrée (saisie, site, Meta, CTWA, OCR,
événements) passent déjà par ``default_responsable_for`` — aucune n'est
retouchée. Décoché (défaut) : rien de ce module ne s'exécute.
"""
import datetime
import logging
import unicodedata

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from core.conflit_etat import ConflitEtat

from . import horaires
from .leads_attribution import _leads_ouverts_count
from .models import Lead
from .models_clients import AttributionEnAttente, EquipeCommerciale, RegleAttribution

logger = logging.getLogger(__name__)

#: Attribut posé sur l'instance utilisateur rendue par
#: ``default_responsable_for`` : l'id de l'équipe dont le lead attend la
#: décision. Lu (puis retiré) par le récepteur ``post_save`` du lead.
MARQUE = '_dispatch_equipe_id'
RAISON_ROTATION = 'Rotation équilibrée'
RAISON_AUCUN = 'Aucun membre disponible'
PLAFOND_DEFAUT = 20


def nom_affiche(user):
    if user is None:
        return None
    return (user.get_full_name() or '').strip() or user.username


def _sans_accents(texte):
    texte = unicodedata.normalize('NFKD', str(texte or ''))
    return ''.join(c for c in texte if not unicodedata.combining(c)).strip().lower()


def _plafond(company_id):
    from apps.parametres.models import CompanyProfile
    profil = CompanyProfile.objects.filter(company_id=company_id).first()
    return profil.round_robin_plafond_leads_ouverts if profil else PLAFOND_DEFAUT


def confirmation_active(equipe):
    """Vrai si les leads de ``equipe`` attendent la décision de son responsable."""
    chef = equipe.responsable if equipe is not None else None
    return bool(equipe is not None and equipe.confirmation_responsable
                and chef is not None and chef.is_active
                and chef.company_id == equipe.company_id)


def marquer_en_attente(equipe):
    """Le responsable de ``equipe``, marqué pour la mise en attente du lead."""
    chef = equipe.responsable
    setattr(chef, MARQUE, equipe.pk)
    return chef


def membre_actif(equipe, user):
    """Membre actif de l'équipe — ou son RESPONSABLE (fondateur, 28/10/2026 :
    le responsable prend aussi des leads lui-même ; il est choisissable à
    l'écran et dans les règles, la rotation reste entre les membres)."""
    return (user is not None and user.is_active
            and user.company_id == equipe.company_id
            and (user.pk == equipe.responsable_id
                 or equipe.membres.filter(pk=user.pk).exists()))


def _choix_equipe(equipe, membres):
    """Les personnes choisissables : le responsable actif EN PREMIER (s'il
    n'est pas déjà membre), puis les membres actifs donnés."""
    choix = list(membres)
    resp = equipe.responsable
    if (resp is not None and resp.is_active
            and resp.company_id == equipe.company_id
            and all(m.pk != resp.pk for m in choix)):
        choix.insert(0, resp)
    return choix


def rotation(equipe):
    """Rotation ÉQUILIBRÉE de ``leads_attribution._prochain_membre_equipe``
    (moins chargé d'abord, départage par id, plafond du profil) où la charge
    compte AUSSI les propositions en attente : sans cela, tous les leads
    arrivés pendant le délai seraient proposés au même membre (ils sont
    encore au nom du responsable). None si personne d'éligible."""
    plafond = _plafond(equipe.company_id)
    charges = []
    for membre in equipe.membres.filter(
            is_active=True, company_id=equipe.company_id).order_by('id'):
        charge = _leads_ouverts_count(membre) + AttributionEnAttente.objects.filter(
            proposee=membre, company_id=equipe.company_id).count()
        if charge < plafond:
            charges.append((charge, membre.pk, membre))
    return min(charges)[2] if charges else None


def _regle_correspond(regle, lead):
    villes = [_sans_accents(v) for v in (regle.villes or '').split(',') if v.strip()]
    if villes and not ({_sans_accents(lead.ville), _sans_accents(lead.ville_reference)}
                       & set(villes)):
        return False
    types = regle.types_installation or []
    if types and lead.type_installation not in types:
        return False
    sources = regle.sources or []
    if sources and lead.canal not in sources:
        return False
    if regle.facture_min is None and regle.facture_max is None:
        return True
    facture = lead.facture_hiver
    if facture is None:
        return False
    return ((regle.facture_min is None or facture >= regle.facture_min)
            and (regle.facture_max is None or facture <= regle.facture_max))


def raison_regle(regle):
    """Texte lisible d'une règle (« Règle : ville Casablanca, … »)."""
    morceaux = []
    if (regle.villes or '').strip():
        morceaux.append('ville ' + ', '.join(
            v.strip() for v in regle.villes.split(',') if v.strip()))
    if regle.types_installation:
        libelles = dict(Lead.TypeInstallation.choices)
        morceaux.append('type ' + ', '.join(
            str(libelles.get(v, v)) for v in regle.types_installation))
    if regle.sources:
        libelles = dict(Lead.Canal.choices)
        morceaux.append('source ' + ', '.join(
            str(libelles.get(v, v)) for v in regle.sources))
    if regle.facture_min is not None or regle.facture_max is not None:
        bas = (f'{regle.facture_min.normalize():f}'
               if regle.facture_min is not None else '0')
        haut = (f'{regle.facture_max.normalize():f}'
                if regle.facture_max is not None else '∞')
        morceaux.append(f'facture {bas}–{haut} DH')
    return 'Règle : ' + (', '.join(morceaux) or 'tous les leads')


def proposer(equipe, lead):
    """(membre proposé ou None, raison) — première règle active qui
    correspond (son membre doit être un membre ACTIF de l'équipe), sinon la
    rotation équilibrée existante."""
    regles = RegleAttribution.objects.filter(
        equipe=equipe, company_id=equipe.company_id, actif=True,
    ).select_related('membre').order_by('ordre', 'id')
    for regle in regles:
        if membre_actif(equipe, regle.membre) and _regle_correspond(regle, lead):
            return regle.membre, raison_regle(regle)
    membre = rotation(equipe)
    return (membre, RAISON_ROTATION) if membre is not None else (None, RAISON_AUCUN)


def echeance_pour(equipe, depuis):
    """L'instant où le délai de l'équipe, compté en minutes OUVRÉES (horaires
    de la société), est écoulé depuis ``depuis``."""
    return horaires.echeance_en_temps_ouvre(
        depuis, datetime.timedelta(minutes=equipe.delai_attribution_minutes),
        equipe.company, canal='whatsapp')


def porte_une_marque(lead):
    """Vrai si le propriétaire du lead vient de ``marquer_en_attente`` (lu
    dans le cache de l'instance — aucune requête)."""
    owner = lead._state.fields_cache.get('owner')
    return getattr(owner, MARQUE, None) is not None


def appliquer_mise_en_attente(lead):
    """Récepteur ``post_save`` : pose l'attente si le propriétaire du lead a
    été choisi par ``marquer_en_attente``. Sans marque : rien (coût nul — le
    propriétaire est lu dans le cache de l'instance, jamais requêté)."""
    owner = lead._state.fields_cache.get('owner')
    equipe_id = getattr(owner, MARQUE, None)
    if equipe_id is None or lead.pk is None:
        return None
    delattr(owner, MARQUE)
    if AttributionEnAttente.objects.filter(lead_id=lead.pk).exists():
        return None
    equipe = EquipeCommerciale.objects.filter(
        pk=equipe_id, company_id=lead.company_id).select_related('company').first()
    if equipe is None:
        return None
    membre, raison = proposer(equipe, lead)
    return AttributionEnAttente.objects.create(
        company_id=lead.company_id, lead=lead, equipe=equipe, proposee=membre,
        raison=raison[:255], echeance=echeance_pour(equipe, timezone.now()))


def peut_regler(user, equipe):
    """Qui règle l'attribution automatique d'une équipe (fondateur,
    28/10/2026) : interrupteur « Le responsable confirme chaque lead », délai
    et règles de proposition. Direction/Admin (tous les droits), le
    responsable de l'équipe, et le directeur commercial = la tête du
    département de l'équipe. Personne d'autre ; toujours la même société."""
    if (user is None or equipe is None or not user.company_id
            or user.company_id != equipe.company_id):
        return False
    if getattr(user, 'is_admin_role', False):
        return True
    if equipe.responsable_id is not None and equipe.responsable_id == user.pk:
        return True
    departement = equipe.departement
    return bool(departement is not None
                and departement.company_id == equipe.company_id
                and departement.responsable_id == user.pk)


def equipes_reglables(user):
    """Équipes commerciales ACTIVES dont ``user`` peut régler l'attribution
    (contrat ``dispatch_leads.json`` → ``equipes_reglables``), par nom."""
    if not getattr(user, 'company_id', None):
        return []
    from django.contrib.auth import get_user_model
    from django.db.models import Prefetch
    # Membres ACTIFS fournis ici : un responsable au rôle Commercial n'a pas
    # accès à /crm/assignable-users/ (palier responsable) et l'éditeur de
    # règles en a besoin pour choisir le membre proposé. Une seule requête
    # pour toutes les équipes (la file est rafraîchie toutes les 30 s).
    actifs = get_user_model().objects.filter(
        is_active=True, company_id=user.company_id,
    ).order_by('first_name', 'username', 'id')
    equipes = (EquipeCommerciale.objects
               .filter(company_id=user.company_id, actif=True)
               .select_related('departement')
               .prefetch_related(Prefetch('membres', queryset=actifs,
                                          to_attr='membres_actifs'))
               .order_by('nom', 'id'))
    return [{**reglage_equipe(e), 'membres': [
        {'id': m.pk, 'nom': nom_affiche(m),
         'est_responsable': m.pk == e.responsable_id}
        for m in _choix_equipe(e, e.membres_actifs)]}
        for e in equipes if peut_regler(user, e)]


def reglage_equipe(equipe):
    return {'id': equipe.pk, 'nom': equipe.nom,
            'confirmation_responsable': equipe.confirmation_responsable,
            'delai_minutes': equipe.delai_attribution_minutes}


def modifier_reglages(user, equipe_id, valeurs):
    """Écrit l'interrupteur et/ou le délai d'une équipe — ces deux champs
    SEULS (le CRUD des équipes reste réservé à l'Admin, ACRM26). 404 hors
    société, 403 sans droit de réglage. Couper la confirmation ne bloque
    aucun lead : les attentes déjà posées gardent leur échéance et la tâche
    ``attribuer_echeances`` les attribue comme avant."""
    equipe = (EquipeCommerciale.objects.select_related('departement')
              .filter(pk=equipe_id, company_id=user.company_id).first()
              if user.company_id else None)
    if equipe is None:
        raise NotFound('Équipe introuvable.')
    if not peut_regler(user, equipe):
        raise PermissionDenied(
            "Seuls le responsable de l'équipe, le directeur commercial et la "
            "Direction règlent son attribution.")
    champs = []
    if 'confirmation_responsable' in valeurs:
        equipe.confirmation_responsable = valeurs['confirmation_responsable']
        champs.append('confirmation_responsable')
    if 'delai_minutes' in valeurs:
        equipe.delai_attribution_minutes = valeurs['delai_minutes']
        champs.append('delai_attribution_minutes')
    if champs:
        equipe.save(update_fields=champs)
    return reglage_equipe(equipe)


def _peut_tout_voir(user):
    # Direction/Admin seulement (revue Fable 27/10) : un rôle sans marqueur de
    # portée (Admin RH, compte légacy) ne voit pas les coordonnées en attente.
    return bool(getattr(user, 'is_admin_role', False))


def _deja_decide(attente):
    """Le lead a changé de main hors de cet écran (fiche du lead, admin) :
    la décision humaine prime, l'attente n'a plus d'objet. Équipe sans
    responsable : jamais « décidé » — la tâche attribue la proposition."""
    responsable_id = attente.equipe.responsable_id
    return (responsable_id is not None
            and attente.lead.owner_id != responsable_id)


def responsable_change(equipe, ancien_id):
    """Le responsable de l'équipe change (revue Fable 27/10) : les leads en
    attente chez l'ANCIEN passent au nouveau ; sans nouveau responsable, ils
    partent à leur proposition à la prochaine minute (échéance = maintenant).
    Sans cela, ils restaient orphelins chez l'ancien responsable."""
    from . import activity
    attentes = list(AttributionEnAttente.objects.filter(
        equipe=equipe).select_related('lead'))
    for attente in attentes:
        lead = attente.lead
        if lead.owner_id != ancien_id:
            continue  # déjà décidé à la main : on n'y touche pas
        if equipe.responsable_id is None:
            attente.echeance = timezone.now()
            attente.save(update_fields=['echeance'])
            continue
        Lead.objects.filter(pk=lead.pk).update(owner_id=equipe.responsable_id)
        activity.log_note(
            lead, None, "En attente d'attribution chez le nouveau "
            f'responsable : {nom_affiche(equipe.responsable)}')


def _finaliser(attente, owner, acteur, corps):
    """Pose ``owner`` (effets CAD54 compris), retire l'attente, trace."""
    from . import activity
    from .cadence_reponses import reattribuer_lead
    lead = Lead.objects.select_for_update().get(pk=attente.lead_id)
    if owner is not None:
        reattribuer_lead(lead, acteur, owner)
    attente.delete()
    # Note SYSTÈME (user=None) : une note d'un humain ferait avancer le lead
    # NEW → CONTACTED (récepteur QJ7) alors que personne ne l'a contacté.
    activity.log_note(lead, None, corps)
    return lead


def attribuer(user, lead_id, owner_id):
    """Décision du responsable (ou d'un admin). 404 hors société, 403 hors
    de son équipe, 409 si le lead n'attend plus, 400 si ``owner`` n'est ni un
    membre actif ni le responsable. Verrou de ligne : un double clic ou la
    tâche automatique ne peuvent pas écrire deux fois."""
    admin = bool(getattr(user, 'is_admin_role', False))
    if not admin and not EquipeCommerciale.objects.filter(
            company_id=user.company_id, responsable=user).exists():
        raise PermissionDenied(
            "Seul le responsable de l'équipe attribue ses leads.")
    if not Lead.objects.filter(pk=lead_id, company_id=user.company_id).exists():
        raise NotFound('Lead introuvable.')
    with transaction.atomic():
        attente = (AttributionEnAttente.objects.select_for_update()
                   .filter(lead_id=lead_id, company_id=user.company_id).first())
        if attente is None or _deja_decide(attente):
            raise ConflitEtat("Ce lead n'attend plus d'attribution.")
        equipe = attente.equipe
        if not (admin or equipe.responsable_id == user.pk):
            raise PermissionDenied(
                "Seul le responsable de l'équipe attribue ses leads.")
        owner = equipe.membres.filter(
            pk=owner_id, is_active=True, company_id=user.company_id).first()
        if owner is None and owner_id == equipe.responsable_id:
            owner = equipe.responsable
        if owner is None:
            raise ValidationError(
                {'owner': "Choisissez un membre actif de l'équipe."})
        corps = f'Attribué à {nom_affiche(owner)} par {nom_affiche(user)}'
        if owner.pk == attente.proposee_id:
            corps += ' (proposition confirmée)'
        return _finaliser(attente, owner, user, corps)


def attribuer_echeances(maintenant=None):
    """Tâche Celery (chaque minute) : les attentes échues partent au membre
    proposé (encore actif et membre), sinon à la rotation recalculée ; sans
    personne, le lead reste au responsable. ``skip_locked`` : une décision
    manuelle en cours n'est jamais doublée. Renvoie le nombre traité."""
    maintenant = maintenant or timezone.now()
    ids = list(AttributionEnAttente.objects.filter(
        echeance__lte=maintenant).values_list('pk', flat=True))
    traites = 0
    for pk in ids:
        try:
            with transaction.atomic():
                attente = (AttributionEnAttente.objects
                           .select_for_update(skip_locked=True)
                           .filter(pk=pk, echeance__lte=maintenant).first())
                if attente is None:
                    continue
                equipe = attente.equipe
                if _deja_decide(attente):
                    attente.delete()  # jamais défaire un choix humain
                    continue
                owner = attente.proposee
                if not membre_actif(equipe, owner):
                    owner = rotation(equipe)
                if owner is not None:
                    corps = (f'Attribué automatiquement à {nom_affiche(owner)} '
                             '(délai dépassé)')
                else:
                    corps = ('Reste au responsable : aucun membre disponible '
                             '(délai dépassé)')
                _finaliser(attente, owner, None, corps)
                traites += 1
        except Exception:  # noqa: BLE001 — une attente en échec ne bloque pas les suivantes (D-ENF22-BLE001)
            logger.warning('dispatch : attribution automatique échouée '
                           '(attente #%s)', pk, exc_info=True)
    return traites


def _iso(dt):
    return timezone.localtime(dt).isoformat() if dt is not None else None


def _ligne_lead(attente, maintenant):
    lead = attente.lead
    facture = lead.facture_hiver
    return {
        'id': lead.pk,
        'nom': ' '.join(p for p in (lead.prenom, lead.nom) if p) or None,
        'telephone': lead.telephone or None,
        'whatsapp': lead.whatsapp or None,
        'email': lead.email or None,
        'ville': lead.ville or None,
        'type_installation': lead.type_installation or None,
        'type_installation_label': (lead.get_type_installation_display()
                                    if lead.type_installation else None),
        'source': lead.canal or None,
        'source_label': lead.get_canal_display() if lead.canal else None,
        'facture_mensuelle_dh': float(facture) if facture is not None else None,
        'message': lead.note or None,
        'cree_le': _iso(lead.date_creation),
        'attente_minutes': horaires.minutes_ouvrees_entre(
            attente.created_at, maintenant, attente.company),
        'auto_le': _iso(attente.echeance),
        'propose': {
            'id': attente.proposee_id,
            'nom': nom_affiche(attente.proposee),
            'raison': attente.raison,
        },
    }


def _ligne_membre(user, plafond, responsable_id=None):
    ouverts = _leads_ouverts_count(user)
    return {
        'id': user.pk,
        'nom': nom_affiche(user),
        'fonction': (user.poste or '').strip() or None,
        'leads_ouverts': ouverts,
        'au_plafond': ouverts >= plafond,
        'est_responsable': user.pk == responsable_id,
    }


def file_attente(user):
    """La file du responsable (contrat ``dispatch_leads.json``) : leads en
    attente des équipes qu'il dirige (Direction/Admin : toutes), du plus
    ancien au plus récent, et les membres ACTIFS de l'équipe affichée."""
    vide = {'equipe': None, 'en_attente': 0, 'leads': [], 'membres': [],
            'equipes_reglables': equipes_reglables(user)}
    if not user.company_id:
        return vide
    # Équipes archivées comprises : la tâche attribue aussi leurs leads.
    equipes = EquipeCommerciale.objects.filter(company_id=user.company_id)
    if not _peut_tout_voir(user):
        equipes = equipes.filter(responsable=user)
    equipes = list(equipes)
    if not equipes:
        return vide
    attentes = list(AttributionEnAttente.objects.filter(
        company_id=user.company_id, equipe__in=equipes,
    ).select_related('lead', 'proposee', 'company').order_by('created_at', 'id'))
    attentes = [a for a in attentes if not _deja_decide(a)]
    confirmees = [e for e in equipes if e.confirmation_responsable and e.actif]
    # Une équipe à la fois : ses leads ET ses membres (revue Fable 27/10 —
    # jamais le lead d'une équipe avec les membres d'une autre).
    affichee = attentes[0].equipe if attentes else next(
        (e for e in confirmees if e.recoit_leads),
        confirmees[0] if confirmees else None)
    if affichee is None:
        return vide
    attentes = [a for a in attentes if a.equipe_id == affichee.pk]
    maintenant = timezone.now()
    plafond = _plafond(user.company_id)
    membres = affichee.membres.filter(
        is_active=True, company_id=user.company_id).order_by('first_name', 'username', 'id')
    return {
        'equipe': {'id': affichee.pk, 'nom': affichee.nom,
                   'delai_minutes': affichee.delai_attribution_minutes},
        'en_attente': len(attentes),
        'leads': [_ligne_lead(a, maintenant) for a in attentes],
        'membres': [_ligne_membre(m, plafond, affichee.responsable_id)
                    for m in _choix_equipe(affichee, membres)],
        'equipes_reglables': vide['equipes_reglables'],
    }
