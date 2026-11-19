"""Copilote vague 2 — les lectures COMPACTES des visites pour l'assistant.

L'agenda (``visites.agenda``, carte ``liste_visites``), la fiche d'une visite
(``visites.visite.resume``, carte ``fiche_visite``), la charge de l'équipe
(``visites.charge``, carte ``charge_equipe``) et le point du matin
(``selectors.brief_visites``) se construisent ICI, une fois : les vues du
viewset les relaient telles quelles, et les formes sont celles des
échantillons ``contract_samples/assistant_*.json`` (une clé de plus ou de moins
rougit ``check_api_shapes``).

Règles tenues partout :

* la PORTÉE est celle de l'écran (``selectors.visites_visibles``) — jamais un
  queryset ouvert ; société et rôle viennent de ``user``, jamais d'un paramètre ;
* les statuts sont ceux du modèle (``VisiteTerrain.Statut``), JAMAIS
  ``STAGES.py`` : la visite est son propre layer ;
* ni téléphone, ni adresse, ni GPS, ni e-mail, ni montant ; le texte saisi sur
  le terrain (retour terrain, mesures) est du CONTENU TIERS, rendu seulement
  dans les champs que l'échantillon désigne, jamais mêlé à un libellé ;
* un refus est ``{detail, field, code}`` et NOMME le champ fautif.
"""
import json
from datetime import datetime, timedelta

from django.db.models import Count, F, Min, Q
from django.utils import timezone

from . import selectors, services
from . import visite_checklist as checklist
from .models import VisiteTerrain

Statut = VisiteTerrain.Statut

#: Statuts « ouverts » : la visite n'a pas encore été rendue au bureau d'études.
OUVERTS = (Statut.BROUILLON, Statut.EN_COURS, Statut.A_REFAIRE)

#: Ensemble FERMÉ des filtres de l'agenda (échantillon ``assistant_agenda``).
FILTRES = ('tout', 'sans_technicien', 'a_valider', 'en_retard', 'a_refaire')

FENETRE_MAX_JOURS = 31
FENETRE_DEFAUT_JOURS = 7
LIMITE_DEFAUT, LIMITE_MAX = 10, 25

LIEN_TOUTES = '/visites/toutes'


class ErreurAssistant(Exception):
    """Un refus que le relais lit : ``{detail, field, code}``, rien d'autre."""

    def __init__(self, detail, champ, code, statut=400):
        super().__init__(detail)
        self.detail, self.champ, self.code, self.statut = detail, champ, code, statut

    def corps(self):
        return {'detail': self.detail, 'field': self.champ, 'code': self.code}


def _date(brut, champ):
    """La date ISO ``AAAA-MM-JJ`` de ``brut`` (``None`` si absent) ; illisible
    → 400 qui nomme le champ."""
    if brut in (None, ''):
        return None
    try:
        return datetime.strptime(str(brut).strip(), '%Y-%m-%d').date()
    except ValueError:
        raise ErreurAssistant(f'{champ} : date illisible, attendu AAAA-MM-JJ.',
                              champ, 'date_invalide')


def _entier(brut, champ, *, mini, maxi, defaut=None):
    """L'entier de ``brut`` dans [mini, maxi] (``defaut`` si absent) ; sinon
    400 qui nomme le champ."""
    if brut in (None, ''):
        return defaut
    texte = str(brut).strip()
    if not (texte.isascii() and texte.isdigit()) or not mini <= int(texte) <= maxi:
        raise ErreurAssistant(
            f'{champ} : un entier de {mini} à {maxi} est attendu.', champ,
            f'{champ}_invalide')
    return int(texte)


def plus_jours(jour, jours, champ):
    """``jour`` + ``jours`` ; une date au bord du calendrier (9999-12-31) est
    refusée en nommant ``champ`` au lieu de lever ``OverflowError`` (500)."""
    try:
        return jour + timedelta(days=jours)
    except OverflowError:
        raise ErreurAssistant(f'{champ} : date hors des limites du calendrier.',
                              champ, 'date_invalide')


def fenetre(params, aujourdhui):
    """``(du, au)`` : ``du`` vaut aujourd'hui par défaut, ``au`` ``du`` + 7 jours ;
    au plus 31 jours après ``du``."""
    du = _date(params.get('du'), 'du') or aujourdhui
    au = _date(params.get('au'), 'au') or plus_jours(du, FENETRE_DEFAUT_JOURS, 'du')
    if au < du:
        raise ErreurAssistant('au : la date de fin ne précède pas « du ».', 'au',
                              'fenetre_inversee')
    if au > plus_jours(du, FENETRE_MAX_JOURS, 'du'):
        raise ErreurAssistant(
            f'au : la fenêtre ne dépasse pas {FENETRE_MAX_JOURS} jours après « du ».',
            'au', 'fenetre_trop_longue')
    return du, au


def _nom_lead(lead):
    morceaux = ((lead.prenom or '').strip(), (lead.nom or '').strip())
    return ' '.join(m for m in morceaux if m) or (lead.nom or '')


def nom_personne(compte):
    """Le nom affichable d'un compte (prénom nom, sinon l'identifiant)."""
    return ((compte.get_full_name() or compte.username) or '').strip()


def commercial_de(visite):
    """``{id, nom}`` de l'assigné, ``None`` si personne ne fait la visite."""
    compte = visite.commercial
    return None if compte is None else {'id': compte.id, 'nom': nom_personne(compte)}


def a_faire(visite, complet):
    """La suite que la visite attend — ensemble FERMÉ : ``assigner`` (personne
    ne la fait), ``completer`` (terminée mais incomplète), ``valider`` (terminée
    et complète : le bureau d'études donne le feu vert), ``refaire`` (renvoyée
    au terrain), ``rien``."""
    statut = visite.statut
    if statut in (Statut.VALIDEE, Statut.ANNULEE):
        return 'rien'
    if statut == Statut.TERMINEE:
        return 'valider' if complet else 'completer'
    if visite.commercial_id is None:
        return 'assigner'
    return 'refaire' if statut == Statut.A_REFAIRE else 'rien'


def en_retard(visite, aujourdhui):
    """Vrai si la date prévue est PASSÉE (horloge serveur) et la visite encore
    ouverte ; une visite sans date n'est jamais en retard."""
    return (visite.date_prevue is not None and visite.date_prevue < aujourdhui
            and visite.statut in OUVERTS)


def _sans_technicien_q():
    return Q(commercial__isnull=True, statut__in=OUVERTS)


def _en_retard_q(aujourdhui):
    return Q(date_prevue__lt=aujourdhui, statut__in=OUVERTS)


def _filtre_q(filtre, aujourdhui):
    """Le critère d'un filtre de l'agenda ; ``a_traiter`` (interne, hors de
    ``FILTRES``) réunit ce que le point du matin met en avant."""
    return {
        'tout': Q(),
        'sans_technicien': _sans_technicien_q(),
        'a_valider': Q(statut=Statut.TERMINEE),
        'en_retard': _en_retard_q(aujourdhui),
        'a_refaire': Q(statut=Statut.A_REFAIRE),
        'a_traiter': (_sans_technicien_q() | Q(statut=Statut.TERMINEE)
                      | _en_retard_q(aujourdhui)),
    }[filtre]


def ligne_agenda(visite, aujourdhui):
    """UNE ligne de l'agenda (``assistant_agenda.json``) ; la complétude vient de
    ``visite_terrain_manquants`` (photos préchargées par l'appelant)."""
    manquants = selectors.visite_terrain_manquants(visite)
    realisee = (timezone.localtime(visite.date_realisee).date().isoformat()
                if visite.date_realisee else None)
    return {
        'id': visite.id,
        'lead': visite.lead_id,
        'lead_nom': _nom_lead(visite.lead),
        'ville': visite.lead.ville or '',
        'statut': visite.statut,
        'date_prevue': visite.date_prevue.isoformat() if visite.date_prevue else None,
        'date_realisee': realisee,
        'gabarit': visite.gabarit,
        'commercial': commercial_de(visite),
        'complet': not manquants,
        'manquants_count': len(manquants),
        'en_retard': en_retard(visite, aujourdhui),
        'a_faire': a_faire(visite, not manquants),
        'lien': f'/visites/{visite.id}',
    }


def perimetre_agenda(visites, du, au, aujourdhui):
    """Les visites qui regardent l'agenda d'une fenêtre ``[du, au]`` : celles
    dont la date y tombe, les terminées (à valider, quelle que soit leur date),
    les renvoyées au terrain et les ouvertes en retard — jamais une annulée."""
    return visites.filter(
        Q(date_prevue__range=(du, au)) | Q(statut__in=(Statut.TERMINEE, Statut.A_REFAIRE))
        | _en_retard_q(aujourdhui)).exclude(statut=Statut.ANNULEE)


def totaux_agenda(perimetre, du, au, aujourdhui):
    """Les cinq compteurs de l'agenda, en UN agrégat."""
    return perimetre.aggregate(
        planifiees=Count('id', filter=Q(date_prevue__range=(du, au))),
        sans_technicien=Count('id', filter=_sans_technicien_q()),
        a_valider=Count('id', filter=Q(statut=Statut.TERMINEE)),
        en_retard=Count('id', filter=_en_retard_q(aujourdhui)),
        a_refaire=Count('id', filter=Q(statut=Statut.A_REFAIRE)))


def lignes_agenda(perimetre, filtre, limite, aujourdhui):
    """Les ``limite`` premières lignes (date prévue croissante, les visites sans
    date en dernier) du ``filtre``."""
    visites = (perimetre.filter(_filtre_q(filtre, aujourdhui))
               .select_related('lead', 'commercial')
               .prefetch_related('medias__attachment')
               .order_by(F('date_prevue').asc(nulls_last=True), 'id')[:limite])
    return [ligne_agenda(visite, aujourdhui) for visite in visites]


def agenda(user, params, aujourdhui):
    """``GET visites/agenda/`` — paramètres ``du``, ``au``, ``filtre``,
    ``commercial``, ``limite`` (``params`` : la query string)."""
    du, au = fenetre(params, aujourdhui)
    filtre = (params.get('filtre') or 'tout').strip()
    if filtre not in FILTRES:
        raise ErreurAssistant(
            f'filtre : une valeur parmi {", ".join(FILTRES)} est attendue.',
            'filtre', 'filtre_invalide')
    limite = _entier(params.get('limite'), 'limite', mini=1, maxi=LIMITE_MAX,
                     defaut=LIMITE_DEFAUT)
    commercial = _entier(params.get('commercial'), 'commercial', mini=1,
                         maxi=2 ** 31 - 1)
    visites = selectors.visites_visibles(user)
    if commercial is not None:
        visites = visites.filter(commercial_id=commercial)
    perimetre = perimetre_agenda(visites, du, au, aujourdhui)
    return {
        'du': du.isoformat(),
        'au': au.isoformat(),
        'filtre': filtre,
        'totaux': totaux_agenda(perimetre, du, au, aujourdhui),
        'limite': limite,
        'lignes': lignes_agenda(perimetre, filtre, limite, aujourdhui),
        'lien': LIEN_TOUTES,
    }


# ── La fiche compacte d'une visite (``visites.visite.resume``) ───────────────

#: Taille maximale de la fiche, en octets de JSON compact (le modèle la lit à
#: chaque tour : ≤ 1,5 Ko, contrat ``assistant_visite_resume``).
BUDGET_FICHE_OCTETS = 1500

#: Bornes de texte à pleine échelle ; ``resume_visite`` les resserre ensemble
#: (× 0,6 puis × 0,35 puis × 0,2) tant que la fiche dépasse le budget.
BORNE_RETOUR, BORNE_MESURES, BORNE_PHRASE, BORNE_CONSEIL = 600, 300, 300, 200
NB_MANQUANTS, NB_A_REFAIRE, BORNE_LIBELLE = 10, 5, 60

_PREFIXES_MANQUANT = {
    checklist.MANQUE_PHOTO: 'Photo',
    checklist.MANQUE_MESURE: 'Mesure',
    checklist.MANQUE_PHOTO_A_REFAIRE: 'Photo à refaire',
}


def tronquer(texte, borne):
    """``texte`` rogné, et coupé à ``borne`` caractères au plus (« … » compris)."""
    texte = (texte or '').strip()
    return texte if len(texte) <= borne else texte[:max(borne - 1, 0)].rstrip() + '…'


def horodatage(valeur):
    """Un horodatage en heure locale (ISO), ``None`` si absent."""
    return None if valeur is None else timezone.localtime(valeur).isoformat()


def _mesures_cles(visite):
    """Les mesures SAISIES, sans l'en-tête « Visite technique validée… » du
    récapitulatif (il dirait « validée » d'une visite qui ne l'est pas) :
    ``recap_visite_terrain`` met l'en-tête avant `` : ``, les valeurs après."""
    _entete, separateur, reste = selectors.recap_visite_terrain(visite).partition(' : ')
    reste = reste.strip().rstrip('.') if separateur else ''
    return reste[:1].upper() + reste[1:]


def _libelle_manquant(manquant):
    prefixe = _PREFIXES_MANQUANT.get(manquant['type'], 'Manque')
    return f"{prefixe} : {manquant['libelle']}"


def _qualification(visite, facteur):
    q = visite.qualification
    phrase, conseil = selectors.phrase(q), selectors.conseil(q)
    if not (phrase or conseil):
        return None
    return {
        'phrase': tronquer(phrase, int(BORNE_PHRASE * facteur)),
        'conseil': tronquer(conseil, int(BORNE_CONSEIL * facteur)),
        'devis_a_reprendre': selectors.devis_a_reprendre(q),
    }


def _photos_a_refaire(visite, medias, facteur):
    refaire = [m for m in medias if m.a_refaire][:max(1, int(NB_A_REFAIRE * facteur))]
    borne = int(BORNE_LIBELLE * facteur)
    return [{'id': m.id,
             'slot': tronquer((checklist.slot(m.slot_code, visite.gabarit) or {}).get('libelle')
                              or m.slot_code, borne),
             'motif': tronquer(m.motif_refaire, borne)} for m in refaire]


def _fiche(visite, manquants, medias, facteur):
    """La fiche à l'échelle ``facteur`` (1 = pleine, plus petit = plus court)."""
    lead, complet = visite.lead, not manquants
    borne = int(BORNE_LIBELLE * facteur)
    retenus = manquants[:max(1, int(NB_MANQUANTS * facteur))]
    return {
        'id': visite.id,
        'lead': {'id': visite.lead_id, 'nom': _nom_lead(lead), 'ville': lead.ville or ''},
        'statut': visite.statut,
        'statut_libelle': visite.get_statut_display(),
        'gabarit': visite.gabarit,
        'date_prevue': visite.date_prevue.isoformat() if visite.date_prevue else None,
        'date_realisee': horodatage(visite.date_realisee),
        'commercial': commercial_de(visite),
        'jalons': {'en_route_le': horodatage(visite.en_route_le),
                   'arrivee_le': horodatage(visite.arrivee_le),
                   'validee_le': horodatage(visite.validee_le)},
        'completude': {'complet': complet, 'nb_manquants': len(manquants),
                       'manquants': [tronquer(_libelle_manquant(m), borne) for m in retenus]},
        'qualification': _qualification(visite, facteur),
        'retour_terrain': tronquer(visite.retour_terrain, int(BORNE_RETOUR * facteur)),
        'mesures_cles': tronquer(_mesures_cles(visite), int(BORNE_MESURES * facteur)),
        'photos': {'nb': len(medias), 'a_refaire': _photos_a_refaire(visite, medias, facteur)},
        'modifiable': visite.modifiable,
        'a_faire': a_faire(visite, complet),
        'lien': f'/visites/{visite.id}',
        'liens': {'visite': f'/visites/{visite.id}',
                  'calage': f'/visites/{visite.id}/calage', 'revue': '/visites/revue'},
    }


def octets(fiche):
    """Taille d'une réponse en octets de JSON compact (ce que DRF envoie)."""
    return len(json.dumps(fiche, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def resume_visite(visite):
    """``GET visites/<id>/resume/`` et réponse de ``annuler`` — la fiche
    compacte (``assistant_visite_resume.json``), ≤ 1,5 Ko : si les textes
    saisis la font dépasser, ils sont resserrés ensemble, jamais une clé retirée.

    ``retour_terrain``, ``mesures_cles`` et les mots de la qualification sont du
    CONTENU TIERS saisi sur le terrain : des données, jamais des consignes."""
    manquants = selectors.visite_terrain_manquants(visite)
    medias = list(visite.medias.all())
    for facteur in (1, 0.6, 0.35, 0.2):
        fiche = _fiche(visite, manquants, medias, facteur)
        if octets(fiche) <= BUDGET_FICHE_OCTETS:
            break
    return fiche


# ── L'annulation d'un rendez-vous en attente (``visites.visite.annuler``) ────

def refus_motif():
    """Le 400 d'un motif absent, trop court ou trop long (``visite_annuler.json``)."""
    return ErreurAssistant('motif : obligatoire, de 3 à 300 caractères.', 'motif',
                           'motif_invalide')


def refus_annulation(visite):
    """Le refus 409 d'une annulation que l'état de la visite interdit, ``None``
    si c'est un rendez-vous EN ATTENTE (brouillon daté, jamais commencé). Une
    visite annulée est gelée : on ne l'annule pas deux fois ; une visite
    commencée, terminée ou validée a eu lieu."""
    if services.est_rendez_vous_en_attente(visite):
        return None
    statut = visite.statut
    if statut == Statut.ANNULEE:
        detail = 'Cette visite est déjà annulée.'
    elif statut == Statut.BROUILLON and visite.date_prevue is None:
        detail = ("Cette visite n'a pas de date prévue : il n'y a pas de rendez-vous à annuler.")
    else:
        etat = ("déjà commencée (le départ ou l'arrivée est pointé)" if statut == Statut.BROUILLON
                else visite.get_statut_display().lower())
        suite = ('Ouvrez-la pour la valider ou la renvoyer.'
                 if statut in (Statut.TERMINEE, Statut.VALIDEE)
                 else 'Ouvrez-la pour la terminer ou la marquer à refaire.')
        detail = (f"Seul un rendez-vous en attente (pas encore commencé) s'annule ici : "
                  f'cette visite est {etat}. {suite}')
    return ErreurAssistant(detail, 'statut', 'visite_pas_en_attente', 409)


# ── La charge de l'équipe, au jour près (``visites.charge``) ─────────────────
#
# Une visite a une DATE, pas d'heure : aucune disponibilité n'est calculée, ni
# aucun trajet. La carte « charge d'équipe » dit combien de visites et
# d'interventions de chantier chacun porte chaque jour, et si une indisponibilité
# est déclarée — jamais un « créneau libre ».

JOURS_CHARGE_DEFAUT, JOURS_CHARGE_MAX = 7, 14
MAX_ASSIGNABLES = 20
NOTE_CHARGE = 'Charge au jour près ; aucune heure ni trajet calculés.'
LIEN_PLANIFIER = '/visites/planifier'


def _voit_toute_l_equipe(user):
    """D-W2-VIS-5 — la charge de TOUTE l'équipe pour qui valide les visites ou
    modifie le CRM ; les autres ne voient que la leur."""
    from core.permissions import _user_has_or_legacy

    return (_user_has_or_legacy(user, 'visites_valider')
            or _user_has_or_legacy(user, 'crm_modifier'))


def assignables(user):
    """Les comptes ACTIFS de la société de ``user`` qui peuvent faire une visite
    (rôle fin portant ``visites_modifier``, ou compte sans rôle fin au palier
    responsable/administrateur — la règle de ``notifier_valideurs_visite``),
    ``MAX_ASSIGNABLES`` au plus, par nom."""
    from django.contrib.auth import get_user_model

    return list(
        get_user_model().objects
        .filter(company_id=user.company_id, is_active=True)
        .filter(Q(role__permissions__contains=['visites_modifier'])
                | Q(role__isnull=True, role_legacy__in=['admin', 'responsable']))
        .distinct().order_by('first_name', 'last_name', 'id')[:MAX_ASSIGNABLES])


def _visites_par_jour(company_id, ids, du, fin):
    """``{(compte, jour): nombre}`` de visites planifiées (hors annulées) — UN
    agrégat."""
    lignes = (VisiteTerrain.objects
              .filter(company_id=company_id, commercial_id__in=ids,
                      date_prevue__range=(du, fin))
              .exclude(statut=Statut.ANNULEE)
              .values_list('commercial_id', 'date_prevue').annotate(n=Count('id'))
              .order_by())
    return {(compte, jour): n for compte, jour, n in lignes}


def _interventions_par_jour(company, ids, du, fin):
    """``{(compte, jour): nombre}`` d'interventions de chantier actives (membre
    d'équipe ou technicien) — lues par ``installations.selectors``, la notion
    « ressource occupée » de la planification."""
    from apps.installations import selectors as installations

    comptes = set(ids)
    par_jour = {}
    for intervention in installations.interventions_actives(company, du, fin).only(
            'id', 'technicien_id', 'date_prevue', 'equipe_ref_id'):
        for membre in installations.membres_intervention(intervention) & comptes:
            cle = (membre, intervention.date_prevue)
            par_jour[cle] = par_jour.get(cle, 0) + 1
    return par_jour


def _jours_indisponibles(company, ids, jours):
    """``{compte: {jour…}}`` : un contrôle sur la fenêtre par compte, puis jour
    par jour seulement pour qui est indisponible quelque part (≤ 20 + 14 × n)."""
    from apps.installations import selectors as installations

    sortie = {}
    for compte in ids:
        if installations.ressource_indisponible(company, compte, jours[0], jours[-1]):
            sortie[compte] = {j for j in jours
                              if installations.ressource_indisponible(company, compte, j, j)}
    return sortie


def charge_equipe(user, params, aujourdhui):
    """``GET visites/charge/`` — paramètres ``du`` (défaut aujourd'hui) et
    ``jours`` (1 à 14, défaut 7). Les comptes lus sont ``assignables`` pour qui
    voit l'équipe, sinon le compte lui-même."""
    du = _date(params.get('du'), 'du') or aujourdhui
    nombre = _entier(params.get('jours'), 'jours', mini=1, maxi=JOURS_CHARGE_MAX,
                     defaut=JOURS_CHARGE_DEFAUT)
    jours = [plus_jours(du, i, 'du') for i in range(nombre)]
    comptes = assignables(user) if _voit_toute_l_equipe(user) else [user]
    ids = [compte.id for compte in comptes]
    visites = _visites_par_jour(user.company_id, ids, jours[0], jours[-1])
    interventions = _interventions_par_jour(user.company, ids, jours[0], jours[-1])
    absences = _jours_indisponibles(user.company, ids, jours)
    sans_technicien = (selectors.visites_visibles(user)
                       .filter(_sans_technicien_q(), date_prevue__range=(jours[0], jours[-1]))
                       .exists())
    return {
        'du': du.isoformat(),
        'jours': nombre,
        'note': NOTE_CHARGE,
        'lignes': [{
            'id': compte.id,
            'nom': nom_personne(compte),
            'moi': compte.id == user.id,
            'par_jour': [{
                'date': jour.isoformat(),
                'visites': visites.get((compte.id, jour), 0),
                'interventions': interventions.get((compte.id, jour), 0),
                'indisponible': jour in absences.get(compte.id, ()),
            } for jour in jours],
        } for compte in comptes],
        'a_faire': 'assigner_visites' if sans_technicien else 'rien',
        'lien': LIEN_PLANIFIER,
    }


# ── Pour le point du matin (``crm.digest_matin``, lane BRF) ──────────────────
#
# Deux lectures PUBLIQUES de l'app (``selectors.brief_visites`` et
# ``selectors.visites_validees_sans_calepinage``) : le CRM les appelle, il
# n'importe jamais les modèles de cette app ; le calepinage n'est jamais lu ici
# (frontière M3 : ``apps.visites`` ne dépend pas de ``apps.calepinage``).

BRIEF_LIGNES = 5
LIEN_REVUE = '/visites/revue'
VALIDEES_LIMITE = 200


def brief_visites(user, aujourdhui):
    """Le bloc ``visites_equipe`` du point du matin : ``{sans_technicien,
    a_valider, en_retard, plus_ancienne_a_valider_le, lignes[≤ 5], lien}``, pour
    qui valide les visites (``visites_valider``) ; ``None`` sinon. Mêmes
    définitions que l'agenda (fenêtre d'aujourd'hui à + 7 jours, retards et
    visites à valider quelle que soit leur date), même portée que l'écran ;
    les lignes sont celles de l'agenda (``assistant_agenda.json``). Deux
    agrégats + au plus 5 lignes : aucune complétude calculée hors de elles."""
    from core.permissions import _user_has_or_legacy

    if not _user_has_or_legacy(user, 'visites_valider'):
        return None
    fin = plus_jours(aujourdhui, FENETRE_DEFAUT_JOURS, 'du')
    perimetre = perimetre_agenda(selectors.visites_visibles(user), aujourdhui, fin, aujourdhui)
    totaux = totaux_agenda(perimetre, aujourdhui, fin, aujourdhui)
    ancienne = perimetre.filter(statut=Statut.TERMINEE).aggregate(
        premiere=Min('date_realisee'))['premiere']
    return {
        'sans_technicien': totaux['sans_technicien'],
        'a_valider': totaux['a_valider'],
        'en_retard': totaux['en_retard'],
        'plus_ancienne_a_valider_le': (timezone.localtime(ancienne).date().isoformat()
                                       if ancienne else None),
        'lignes': lignes_agenda(perimetre, 'a_traiter', BRIEF_LIGNES, aujourdhui),
        'lien': LIEN_REVUE,
    }


def visites_validees(company, depuis):
    """Les visites VALIDÉES depuis ``depuis`` (une date, ou un horodatage) dans
    ``company`` — au plus une par lead (la plus récente), la plus récente d'abord,
    ``VALIDEES_LIMITE`` au plus : ``[{visite_id, lead_id, lead_nom, validee_le,
    a_faire: 'preparer_calepinage', lien}]``. La date du feu vert (``validee_le``)
    est celle posée par le serveur à la validation : une visite validée avant son
    introduction n'en a pas et n'est jamais datée après coup."""
    depart = ({'validee_le__gte': depuis} if isinstance(depuis, datetime)
              else {'validee_le__date__gte': depuis})
    visites = (VisiteTerrain.objects
               .filter(company=company, statut=Statut.VALIDEE, validee_le__isnull=False, **depart)
               .select_related('lead').order_by('-validee_le', '-id'))
    lignes, vus = [], set()
    for visite in visites[:VALIDEES_LIMITE]:
        if visite.lead_id in vus:
            continue
        vus.add(visite.lead_id)
        lignes.append({
            'visite_id': visite.id,
            'lead_id': visite.lead_id,
            'lead_nom': _nom_lead(visite.lead),
            'validee_le': horodatage(visite.validee_le),
            'a_faire': 'preparer_calepinage',
            'lien': f'/crm/leads/{visite.lead_id}',
        })
    return lignes
