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
from datetime import datetime, timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from . import selectors
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
    return {
        'tout': Q(),
        'sans_technicien': _sans_technicien_q(),
        'a_valider': Q(statut=Statut.TERMINEE),
        'en_retard': _en_retard_q(aujourdhui),
        'a_refaire': Q(statut=Statut.A_REFAIRE),
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
