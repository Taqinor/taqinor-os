"""Liste froide — la commerciale PREND elle-même ses appels de dossiers au Froid.

Décision du fondateur (17/11/2026) : les appels de la liste froide se font DANS
l'ERP, jamais sur une liste papier, et la commerciale les TIRE quand sa journée
le permet (« un bouton pour prendre d'anciens leads, selon sa charge ») — jamais
des étapes datées poussées sur des jours déjà pleins (108 étapes en retard en
production). Contrat : ``contract_samples/liste_froide.json``.

Le vivier, trois groupes, O avant A avant B :
  * O — reste de l'import Odoo (décision du fondateur, 20/11/2026 : « les avoir
    d'abord sur le bouton des leads froids ») : dossier importé d'Odoo, vivant,
    non signé, SANS responsable (108 en production ce jour-là, à des étapes
    actives, que personne ne voyait) — ou déjà à l'appelant par une prise (sa
    seconde tentative). Le prendre en fait SON dossier (``assigner_lead_a``) ;
    son étape n'est pas touchée à la prise : un « pas de réponse » le range au
    Froid par le chemin des réveils (``cloturer_reveils_sans_reponse``) ;
  * A — joint ET chiffré, sans décision : le seau K3 de ``seaux_reactivation`` ;
  * B — lead Meta jamais joint (seaux K5 / K6) au palier 1 du pilote d'appel
    D-CADV-2 (``palier_1_reactivation`` : facture ≥ 2 000 MAD hiver ou été, ou
    projet proche), le plus récent d'abord.
Une seule définition des seaux : ce module ne reclasse rien, il passe à
``seaux_reactivation`` son éligibilité d'APPEL (``motif_hors_liste``) puis ne
garde que les dossiers de l'appelant.

Même décision du 20/11/2026 : la commerciale CHOISIT combien elle prend (corps
``nombre``, 1..``PRISE_MAX``) ; l'écran propose ``PRISE_PROPOSEE``.

L'étape prise est un réveil HORS gabarit (cadence ``reveil``, clé
``CLE_LISTE_FROIDE``, rang ``LISTE_FROIDE_ORDRE``) : chaque réponse suit le
chemin du dernier appel de réveil d'un dossier au Froid, déjà câblé — joint ou
visite acceptée → le dossier sort du Froid et le filet pose la suite (récepteur
MRY9) ; pas de réponse → il reste au Froid, rien n'est posé (``cloturer_cadence``
→ ``cloturer_reveils_sans_reponse``, sans effet au Froid) ; « à rappeler le… »
→ rappel convenu (``est_dernier_reveil``) ; refus → reste au Froid.

Décision du fondateur (19/11/2026) : « garder deux essais et ajouter la raison
honnête après » — la SECONDE tentative close sans réponse écrit la raison de
parcage ``liste_froide_sans_reponse`` (``noter_deux_appels_sans_reponse``, appelée
par ``marquer_etape_relance``) pour que ces dossiers se voient et se comptent ;
le dossier reste au Froid, jamais perdu.
"""
import logging

from django.db import transaction
from django.utils import timezone

from core.dates import aujourd_hui_local

from . import stages
from .cadence_reperes import (
    CLE_LISTE_FROIDE, LIBELLE_LISTE_FROIDE, LISTE_FROIDE_ORDRE)

logger = logging.getLogger(__name__)

#: Plafond d'appels de la liste froide OUVERTS par personne : elle ne prend
#: que ce qu'elle va appeler.
PLAFOND_APPELS_OUVERTS = 30
#: Au plus ce nombre de dossiers par prise (corps ``nombre``, 1..30) : elle
#: choisit combien (fondateur, 20/11/2026 : « ne pas forcer 10 »).
PRISE_MAX = 30
#: Ce que l'écran propose avant qu'elle ne choisisse (et le corps sans ``nombre``).
PRISE_PROPOSEE = 10
#: Deux tentatives par dossier, jamais plus ; la seconde un autre jour.
TENTATIVES_MAX = 2
#: Les issues après lesquelles le dossier revient dans le vivier : « pas de
#: réponse » (et ses précisions), ou une étape sautée sans issue.
ISSUES_RETOUR_AU_VIVIER = ('', 'non_joint')

#: 19/11/2026 — la raison de parcage écrite à la seconde tentative sans réponse,
#: et la note du chatter quand le dossier porte déjà une autre raison.
RAISON_DEUX_APPELS_SANS_REPONSE = 'liste_froide_sans_reponse'
NOTE_DEUX_APPELS_SANS_REPONSE = 'Liste froide : deux appels sans réponse.'

GROUPE_ODOO = 'O'
GROUPE_CHIFFRE = 'A'
GROUPE_SANS_REPONSE = 'B'
#: Le script d'appel de chaque groupe (le rendu route ``appel_ouverture`` selon
#: l'origine du lead, ``cadence_messages._cle_identite_pour_lead``).
SCRIPT_PAR_GROUPE = {GROUPE_ODOO: 'appel_ouverture',
                     GROUPE_CHIFFRE: 'appel_reveil_devis',
                     GROUPE_SANS_REPONSE: 'appel_ouverture'}


class PriseRefusee(Exception):
    """Refus nommé d'une prise : ``champ`` (sous lequel l'écran l'affiche),
    ``message`` (une phrase), ``statut`` HTTP."""

    def __init__(self, champ, message, statut=409):
        super().__init__(message)
        self.champ, self.message, self.statut = champ, message, statut


def motif_hors_liste(lead, *, restes_odoo=False):
    """Ce qui écarte un dossier au Froid de la liste froide, ou ``None`` :
    archivé, perdu (quel que soit le motif), opposé, à l'état Archive, ancien
    contact importé d'Odoo, ou sans numéro marocain exploitable.
    ``restes_odoo`` : l'éligibilité du groupe O, où l'import Odoo n'écarte pas."""
    from apps.ventes.utils.phone import normalize_ma_phone

    from .models import Lead

    if lead.is_archived:
        return 'archivé'
    if lead.perdu:
        return 'perdu'
    if lead.ne_plus_contacter:
        return 'opposition'
    if (lead.parc_etat or '') == 'archive':
        return 'état Archive'
    if not restes_odoo and lead.source == Lead.Source.ODOO_IMPORT_TEST:
        return 'import Odoo'
    if not (normalize_ma_phone(lead.telephone) or normalize_ma_phone(lead.whatsapp)):
        return 'numéro'
    return None


def _ecartes_par_les_etapes(company, ids):
    """Les dossiers que leurs étapes sortent du vivier : une étape ouverte (il
    est déjà dans une file), deux tentatives de la liste froide, une tentative
    close AUJOURD'HUI (la seconde se fait un autre jour), ou une tentative close
    sur une autre réponse que « pas de réponse »."""
    from .models import RelanceEtape

    if not ids:
        return set()
    aujourd_hui = aujourd_hui_local()
    ecartes, tentatives = set(), {}
    lignes = RelanceEtape.objects.filter(company=company, lead_id__in=ids).filter(
        statut=RelanceEtape.Statut.A_FAIRE,
    ) | RelanceEtape.objects.filter(
        company=company, lead_id__in=ids, cle=CLE_LISTE_FROIDE,
        statut__in=(RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE))
    for lead_id, statut, outcome, traite_le in lignes.values_list(
            'lead_id', 'statut', 'outcome', 'traite_le'):
        if statut == RelanceEtape.Statut.A_FAIRE:
            ecartes.add(lead_id)
            continue
        tentatives[lead_id] = tentatives.get(lead_id, 0) + 1
        if ((outcome or '') not in ISSUES_RETOUR_AU_VIVIER
                or tentatives[lead_id] >= TENTATIVES_MAX
                or (traite_le and aujourd_hui_local(traite_le) == aujourd_hui)):
            ecartes.add(lead_id)
    return ecartes


def _q_restes_odoo(user):
    """Le filtre du groupe O : import Odoo non signé, sans responsable — ou
    déjà à ``user`` PAR une prise de la liste froide (sa seconde tentative,
    quelle que soit l'étape où le « pas de réponse » l'a laissé). Un import
    Odoo que ``user`` suit hors de la liste n'y entre pas."""
    from django.db.models import Q

    from .models import Lead, RelanceEtape

    deja_pris = RelanceEtape.objects.filter(
        cle=CLE_LISTE_FROIDE, lead__owner=user).values('lead_id')
    return (Q(source=Lead.Source.ODOO_IMPORT_TEST) & ~Q(stage=stages.SIGNED)
            & (Q(owner__isnull=True) | Q(owner=user, pk__in=deja_pris)))


def vivier(company, user):
    """Les dossiers à appeler par ``user``, dans l'ordre de prise : ``[(lead,
    groupe)]`` — O, puis A, puis B, le plus récent d'abord dans chaque groupe."""
    from .cadence_selectors import palier_1_reactivation, seaux_reactivation
    from .models import Lead

    seaux = seaux_reactivation(company, exclu=motif_hors_liste)
    jamais_joints = seaux['K5'] + seaux['K6_p1'] + seaux['K6_p2']
    leads = {lead.pk: lead for lead in Lead.objects.filter(
        company=company, owner=user, stage=stages.COLD,
        pk__in=seaux['K3'] + jamais_joints)}
    restes = [lead for lead in Lead.objects.filter(_q_restes_odoo(user),
                                                   company=company)
              if motif_hors_liste(lead, restes_odoo=True) is None]
    leads.update({lead.pk: lead for lead in restes})
    ecartes = _ecartes_par_les_etapes(company, list(leads))

    def groupe(ids, filtre=None):
        retenus = [leads[pk] for pk in ids if pk in leads and pk not in ecartes
                   and (filtre is None or filtre(leads[pk]))]
        return sorted(retenus, key=lambda lead: (lead.date_creation, lead.pk),
                      reverse=True)

    odoo = {lead.pk for lead in restes}
    return ([(lead, GROUPE_ODOO) for lead in groupe(odoo)]
            + [(lead, GROUPE_CHIFFRE) for lead in groupe(
                [pk for pk in seaux['K3'] if pk not in odoo])]
            + [(lead, GROUPE_SANS_REPONSE) for lead in groupe(
                [pk for pk in jamais_joints if pk not in odoo],
                palier_1_reactivation)])


def _appels_ouverts(company, user):
    from .models import RelanceEtape

    return RelanceEtape.objects.filter(
        company=company, cle=CLE_LISTE_FROIDE, lead__owner=user,
        statut=RelanceEtape.Statut.A_FAIRE).count()


def etat_liste_froide(company, user):
    """Ce que la carte du cockpit montre à ``user`` (GET du contrat)."""
    dossiers = vivier(company, user)
    ouverts = _appels_ouverts(company, user)
    chiffres = sum(1 for _lead, g in dossiers if g == GROUPE_CHIFFRE)
    odoo = sum(1 for _lead, g in dossiers if g == GROUPE_ODOO)
    prise_max = max(0, min(PRISE_MAX, PLAFOND_APPELS_OUVERTS - ouverts,
                           len(dossiers)))
    if ouverts >= PLAFOND_APPELS_OUVERTS:
        raison = (f'Vous avez déjà {ouverts} appels de la liste froide ouverts : '
                  'appelez-les avant d’en prendre d’autres.')
    elif not dossiers:
        raison = 'Aucun dossier de la liste froide ne vous attend aujourd’hui.'
    else:
        raison = ''
    return {
        'restes_odoo': odoo,
        'dossiers_chiffres': chiffres,
        'demandes_sans_reponse': len(dossiers) - chiffres - odoo,
        'appels_ouverts': ouverts,
        'plafond_appels_ouverts': PLAFOND_APPELS_OUVERTS,
        'prise_max': prise_max,
        'prise_proposee': min(PRISE_PROPOSEE, prise_max),
        'peut_prendre': prise_max > 0,
        'raison': raison,
    }


def _poser_appel(lead, user, groupe, quand):
    """UNE étape « Appeler — liste froide » sur ``lead`` (verrouillé et relu par
    l'appelant), la file recalée et la ligne SYSTÈME du chatter (poser une
    étape n'est pas un contact : garde QJ7)."""
    from . import horaires
    from .activity import journal_systeme
    from .cadence_plan import _recaler_file
    from .models import LeadActivity, RelanceEtape
    from .portee_selectors import peut_contacter

    if not peut_contacter(lead, RelanceEtape.Canal.APPEL):
        # ACRM50 — l'opposition est relue au moment d'écrire (déjà écartée par
        # ``motif_hors_liste``, la garde unique tient malgré tout).
        return None
    etape = RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence='reveil',
        ordre=LISTE_FROIDE_ORDRE, cle=CLE_LISTE_FROIDE,
        canal=RelanceEtape.Canal.APPEL, libelle=LIBELLE_LISTE_FROIDE,
        template_cle=SCRIPT_PAR_GROUPE[groupe], due_at=quand,
        due_initial_at=quand,
        due_date=quand.astimezone(horaires.CASABLANCA).date(),
        cadence_depart=timezone.now(),
        note='Prise dans la liste froide.')
    _recaler_file(lead, user)
    quand_local = quand.astimezone(horaires.CASABLANCA)
    nom = user.first_name or user.username
    journal_systeme(
        company=lead.company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=(f'Étape « {LIBELLE_LISTE_FROIDE} » posée pour le '
              f'{quand_local:%d/%m/%Y à %H:%M} — prise dans la liste froide '
              f'par {nom}.'))
    return etape


def prendre_dossiers(company, user, nombre):
    """POST du contrat : pose UN appel, au prochain créneau d'appel, sur chacun
    des ``nombre`` (1..``PRISE_MAX``) prochains dossiers du vivier de ``user``,
    sans jamais dépasser ``PLAFOND_APPELS_OUVERTS`` appels ouverts. Une
    transaction par dossier, relu sous verrou (une course ne pose jamais deux
    étapes, ni ne donne un reste d'Odoo à deux personnes). Un reste d'Odoo sans
    responsable devient le dossier de ``user``. Lève ``PriseRefusee`` quand rien
    ne peut être pris."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from . import horaires
    from .fiche_funnel import assigner_lead_a
    from .models import Lead, RelanceEtape

    if isinstance(nombre, bool) or not isinstance(nombre, int) or not 1 <= nombre <= PRISE_MAX:
        raise PriseRefusee(
            'nombre', f'Nombre de dossiers attendu entre 1 et {PRISE_MAX}.',
            statut=400)
    places = []
    with transaction.atomic():
        # Deux prises simultanées de la même personne passent l'une après
        # l'autre : le plafond est relu sous ce verrou.
        get_user_model().objects.select_for_update().filter(pk=user.pk).first()
        etat = etat_liste_froide(company, user)
        if not etat['peut_prendre']:
            raise PriseRefusee('nombre', etat['raison'])
        quand = horaires.prochain_creneau_appel(
            timezone.now(), company, canal='appel')
        for lead, groupe in vivier(company, user)[:min(nombre, etat['prise_max'])]:
            try:
                with transaction.atomic():
                    odoo = groupe == GROUPE_ODOO
                    verrouille = (Lead.objects.select_for_update().filter(
                        _q_restes_odoo(user) if odoo else
                        Q(owner=user, stage=stages.COLD),
                        pk=lead.pk, company=company).first())
                    if (verrouille is None
                            or motif_hors_liste(verrouille, restes_odoo=odoo)
                            or verrouille.relance_etapes.filter(
                                statut=RelanceEtape.Statut.A_FAIRE).exists()):
                        continue
                    if verrouille.owner_id is None:
                        assigner_lead_a(verrouille, user, user.pk)
                    etape = _poser_appel(verrouille, user, groupe, quand)
                    if etape is None:
                        continue
            except Exception:  # noqa: BLE001 — un dossier en échec n'arrête pas les autres (D-ENF22-BLE001)
                logger.warning('Liste froide : appel non posé (lead #%s)',
                               lead.pk, exc_info=True)
                continue
            places.append({
                'lead': verrouille.pk,
                'nom': f'{verrouille.nom} {verrouille.prenom or ""}'.strip(),
                'groupe': groupe, 'etape': etape.pk,
                'due_at': etape.due_at.astimezone(horaires.CASABLANCA).isoformat()})
    pour_le = aujourd_hui_local(quand)
    return {
        **etat_liste_froide(company, user),
        'places': places,
        'nombre_places': len(places),
        'pour_le': pour_le.isoformat(),
        'du_jour': pour_le == aujourd_hui_local(),
    }


def noter_deux_appels_sans_reponse(etape, user):
    """Fondateur 19/11/2026 — la SECONDE tentative de la liste froide close sans
    réponse dit pourquoi le dossier ne revient plus au vivier. ``etape`` vient
    d'être close par ``marquer_etape_relance`` (qui l'appelle, hors ``suite=False``).

    Déclenchée par une étape ``CLE_LISTE_FROIDE`` close sur une issue qui renvoie
    au vivier ; la raison n'est écrite que si le dossier totalise ``TENTATIVES_MAX``
    APPELS passés sans réponse (étape faite, issue « pas de réponse ») : une étape
    sautée n'est pas un appel, une réponse obtenue (joint, refus, rappel) non plus.

      * dossier SANS raison de parcage : ``parquer_lead`` la pose
        (``liste_froide_sans_reponse``, Nurture) — les deux appels EN SONT la
        touche (``exiger_touche=False``), la ligne du chatter est la sienne ;
      * dossier qui en porte DÉJÀ une (budget, trop cher, injoignable…) : elle
        reste, et UNE note système l'ajoute au chatter (jamais écrite deux fois).

    Le dossier reste au Froid : ni perdu, ni changement d'étape. Rien n'est écrit
    pour un dossier déjà sorti du Froid, perdu, archivé ou opposé. Best-effort :
    ne lève jamais. Renvoie ``True`` si quelque chose a été écrit."""
    from .activity import journal_systeme
    from .fiche_funnel import ParcRefuse, parquer_lead
    from .models import LeadActivity, RelanceEtape

    if (getattr(etape, 'cle', '') or '') != CLE_LISTE_FROIDE:
        return False
    if (etape.outcome or '') not in ISSUES_RETOUR_AU_VIVIER:
        return False
    lead = etape.lead
    try:
        with transaction.atomic():
            # La raison dit « deux APPELS » : seuls comptent les appels passés
            # (étape faite, issue « pas de réponse ») — une étape sautée n'en est pas un.
            sans_reponse = RelanceEtape.objects.filter(
                company=etape.company, lead=lead, cle=CLE_LISTE_FROIDE,
                statut=RelanceEtape.Statut.FAIT, outcome='non_joint').count()
            if sans_reponse < TENTATIVES_MAX:
                return False
            lead.refresh_from_db(fields=[
                'stage', 'perdu', 'is_archived', 'ne_plus_contacter',
                'parc_etat', 'parc_raison', 'parc_jusqu_au'])
            if (lead.stage != stages.COLD or lead.perdu or lead.is_archived
                    or lead.ne_plus_contacter):
                return False
            if not lead.parc_raison:
                parquer_lead(lead, RAISON_DEUX_APPELS_SANS_REPONSE, None, user,
                             exiger_touche=False)
                return True
            if (lead.parc_raison == RAISON_DEUX_APPELS_SANS_REPONSE
                    or lead.activites.filter(
                        body=NOTE_DEUX_APPELS_SANS_REPONSE).exists()):
                return False
            journal_systeme(
                company=lead.company, lead=lead, kind=LeadActivity.Kind.NOTE,
                body=NOTE_DEUX_APPELS_SANS_REPONSE)
            return True
    except ParcRefuse:
        return False
    except Exception:  # noqa: BLE001 — jamais bloquant pour le geste (D-ENF22-BLE001)
        logger.warning('Liste froide : raison non posée (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return False
