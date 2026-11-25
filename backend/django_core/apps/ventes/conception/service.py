"""ADEV135 — L'ÉCRIVAIN UNIQUE des versions de conception (D-ACAL-97).

``relancer`` calcule par le moteur unique (``conception/moteur.py::
calculer_conception``, aucune écriture), compare l'empreinte à la version
courante du porteur — égale ⇒ RIEN n'est écrit, sauf ``forcer`` — puis range la
version suivante par la primitive ``ConceptionLead.ranger`` (plus haut + 1 sous
point de sauvegarde ; l'ancienne passe à ``courante=False``) et émet
``core.events.conception_recalculee`` APRÈS la validation de la transaction.
Rien d'autre dans le code n'écrit une ``ConceptionLead``.

Ce qui est rangé (contrat ``contract_samples/conception_lead.json``) : la
sortie du moteur, dont ``blocs`` = le contenu COMPLET de ``etude_params`` tel
que le devis automatique né de cette conception le porterait (sans les notes
vendeur ``journal_auto``), et ``declencheur`` dont la ``raison`` est LA phrase
que lit l'utilisateur (« Recalculé le 23/11 à 14 h 05 : Facture hiver 900 →
1 200 MAD »), recopiée telle quelle par le chatter du CRM. Aucune clé d'achat ni de
marge n'entre dans ``valeurs`` ni ``blocs`` (parcours récursif). Aucun devis
n'est lu ni écrit ici : un devis envoyé ou accepté ne bouge jamais.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import logging

logger = logging.getLogger(__name__)

#: Unité dite après « avant → après » (relecture m4 : « … 900 → 1 200 MAD ») ;
#: les colonnes en kWh portent déjà l'unité dans leur libellé.
UNITES = {'facture_hiver': 'MAD', 'facture_ete': 'MAD'}
#: Origines admises d'un déclencheur (contrat, clé ``declencheur.origine``).
ORIGINES = ('lead_entrees_modifiees', 'pose_enregistree', 'regles', 'remplissage', 'manuel', 'filet')
#: La fin de la phrase « pourquoi » quand aucun champ n'est nommé.
MOTIFS_ORIGINE = {
    'lead_entrees_modifiees': 'fiche du lead modifiée',
    'pose_enregistree': 'pose enregistrée sur le calepinage',
    'regles': 'règles de calcul mises à jour',
    'remplissage': 'premier calcul',
    'manuel': 'recalcul demandé',
    'filet': 'entrées du lead changées hors du chemin habituel',
}


@dataclass(frozen=True)
class Relance:
    """Ce que ``relancer`` rend : la version COURANTE du porteur après l'appel
    (``None`` si le porteur est refusé), ``ecrite`` (une version a-t-elle été
    rangée), le résultat du moteur (``None`` sans calcul) et le ``refus`` du
    PORTEUR (``{code, champ, message}``, ex. dossier d'appel d'offres)."""
    conception: object
    ecrite: bool
    resultat: object = None
    refus: object = None


def relancer(lead, *, company, declencheur, auteur=None, forcer=False, toit=None, calepinage_id=None,
             imposes=None):
    """La conception du porteur (de ``company`` seulement) recalculée et, si
    son empreinte a changé (ou ``forcer``), rangée en version suivante.

    Porteur (ADEV136, réponse Q3 du 23/11) : le ``lead`` ; sans lead, le
    calepinage ``calepinage_id`` lui-même (son lead s'il en a un, sinon la
    version est rangée sur ``calepinage_id`` avec ``lead=None``). Un dossier
    d'appel d'offres n'est PAS calculé : ses règles de cahier des charges
    restent hors du moteur (``Relance.refus``, rien n'est écrit).
    ``declencheur`` : ``{champs: [{champ, avant, apres}], origine}`` (``raison``
    est construite ici, une ``raison`` passée est remplacée) ; ``auteur`` :
    l'utilisateur (``None`` = tâche du moteur) ; ``toit`` : la pose servie (son
    ``empreinte`` et son ``plafond_panneaux`` entrent dans le calcul). Une
    empreinte égale n'appelle même pas le calcul (``Relance.resultat`` vaut
    alors ``None``).

    ``imposes`` (ADEV135, forme ``composition_imposee.CHAMPS_IMPOSES``) : la
    composition IMPOSÉE par un humain ; absente, celle que le calepinage
    ``calepinage_id`` porte (ACAL2013 : module / onduleur désignés à la main à
    l'étape Électrique, ``porte_calepinage.designations_du_calepinage``) — elle
    entre dans l'empreinte, donc une désignation changée range une version."""
    from django.utils import timezone

    from apps.ventes.conception.entrees import entrees_pour
    from apps.ventes.conception.moteur import calculer_conception, empreinte_conception, reglages_lus_sans_creer
    from apps.ventes.models import ConceptionLead

    from apps.crm.selectors import lead_efface

    debut = timezone.now()  # relecture E3 Q5 : avant toute lecture des entrées
    origine, champs = _declencheur_valide(declencheur)
    try:
        lead, porteur, refus = _porteur(lead, company, calepinage_id)
    except ValueError:
        if lead is None or calepinage_id is None:
            raise
        # Relecture E3 M1 — porteur LEAD : son calepinage archivé, illisible
        # ou relié à un autre lead n'est pas une erreur ; la conception du lead
        # continue SANS cette pose (sinon elle ne bougerait plus jamais).
        logger.warning('Conception du lead #%s : calepinage #%s archivé ou relié ailleurs, '
                       'recalcul sans cette pose', getattr(lead, 'pk', None), calepinage_id)
        calepinage_id, toit = None, None
        lead, porteur, refus = _porteur(lead, company, None)
    if refus is not None:
        return Relance(None, False, None, refus)
    if lead_efface(lead):  # relecture E3 B1 (loi 09-08) : rien calculé, rangé ni émis
        return Relance(None, False, None, dict(REFUS_LEAD_EFFACE))
    courante = _courante(ConceptionLead, company, porteur)
    if imposes is None and calepinage_id:
        from apps.ventes.conception.porte_calepinage import designations_du_calepinage
        imposes = designations_du_calepinage(company, calepinage_id) or None
    with reglages_lus_sans_creer(company):
        entrees = entrees_pour(lead, company, toit=toit)
        if courante is not None and courante.empreinte == empreinte_conception(entrees, imposes) and not forcer:
            return Relance(courante, False, None)
        resultat = calculer_conception(lead, company, entrees=entrees, toit=toit, calepinage_id=calepinage_id,
                                       imposes=imposes)
    origine, champs = _pourquoi(courante, entrees, origine, champs)
    maintenant = timezone.now()
    version = ConceptionLead.ranger(
        lead=porteur.get('lead'), calepinage_id=calepinage_id, company=company,
        calcule_le=maintenant, calcule_par=auteur,
        declencheur={'raison': phrase_du_declencheur(porteur.get('lead'), champs, origine, maintenant),
                     'champs': champs, 'origine': origine},
        empreinte_pose=entrees.empreinte_pose, sauf_empreinte=None if forcer else resultat.empreinte,
        garde=_garde_de_rangement(company, porteur.get('lead'), debut), **_champs_ranges(resultat))
    if version is None:  # lead effacé entre-temps, ou version plus récente déjà rangée : rien
        return Relance(None, False, resultat)
    if not version.ecrite:  # relance simultanée des mêmes entrées : déjà rangée (relecture m1)
        return Relance(version, False, resultat)
    _annoncer_apres_validation(version)
    return Relance(version, True, resultat)


def _pourquoi(courante, entrees, origine, champs):
    """Relecture E4 B1 — ce que la phrase DIT : les champs nommés par
    l'appelant, plus les réglages société changés depuis la version courante
    (« catalogue modifié », « TVA modifiée ») et, quand l'appelant n'en nomme
    aucun (filet, devis demandé), les entrées du lead changées (« Raccordement
    Monophasé → Triphasé »). Une version d'avant ce suivi, sans autre
    changement, est dite « règles de calcul mises à jour »."""
    from apps.ventes.conception.societe import changements, format_d_avant

    if courante is None:
        return origine, champs
    ancienne = courante.entrees_utilisees
    releves = changements(ancienne, entrees.entrees_utilisees, champs)
    if not champs and not releves and origine == 'filet' and format_d_avant(ancienne):
        return 'regles', champs
    return origine, champs + _declencheur_valide({'origine': origine, 'champs': releves})[1]


def _garde_de_rangement(company, lead, debut):
    """La garde de ``ConceptionLead.ranger``, SOUS sa transaction :

    * relecture E3 B1(b) — la ligne du lead est VERROUILLÉE et relue : effacé
      (ou disparu) pendant le calcul ⇒ rien n'est rangé (le scrub prend le
      même verrou : il passe avant ou après, jamais au milieu) ;
    * relecture E3 Q5 — une version courante calculée APRÈS le début de cette
      relance (une relance plus récente, d'autres entrées) n'est jamais
      recouverte par des entrées plus anciennes."""
    from apps.crm.selectors import lead_efface_sous_verrou

    def garde(deja):
        if lead is not None and lead_efface_sous_verrou(company, lead.pk):
            logger.info('Conception du lead #%s non rangée : lead effacé pendant le calcul', lead.pk)
            return False
        courante = deja.filter(courante=True).only('pk', 'calcule_le').first()
        if courante is not None and courante.calcule_le is not None and courante.calcule_le > debut:
            logger.info('Conception non rangée : la version #%s, plus récente, est déjà courante', courante.pk)
            return False
        return True
    return garde


def _courante(modele, company, porteur):
    """La version courante lue AVANT le calcul (sans verrou : la décision
    d'écrire est reprise sous verrou par ``ConceptionLead.ranger``)."""
    return modele.objects.filter(company=company, courante=True, **porteur).first()


CODE_APPEL_OFFRES = 'appel_offres_hors_moteur'
#: Relecture E3 B1 — un lead effacé (loi 09-08) n'a plus de conception : ses
#: entrées effacées ne sont jamais recopiées dans une version.
REFUS_LEAD_EFFACE = {'code': 'lead_efface', 'champ': 'nom',
                     'message': 'Lead effacé (loi 09-08) : aucune conception.'}


def _porteur(lead, company, calepinage_id, calepinage=None):
    """``(lead du calcul, filtre du porteur, refus)``. Un calepinage d'une
    autre société est introuvable (``ValueError``, comme un lead étranger).
    Résolution bornée à la SOCIÉTÉ seulement : pour les appelants système (la
    tâche du moteur n'a pas d'utilisateur). Une route passe ``calepinage``
    (et le lead) déjà résolus dans la portée de l'appelant (relecture B1)."""
    if calepinage is not None:
        calepinage_id = calepinage.pk
    if calepinage_id is None:
        if getattr(lead, 'company_id', None) != getattr(company, 'pk', None):
            raise ValueError('Lead hors de la société : aucune conception.')
        return lead, {'lead': lead}, None
    from apps.crm.selectors import get_company_lead
    from apps.ventes.selectors_calepinage import calepinage_de_societe

    calepinage = calepinage if calepinage is not None else calepinage_de_societe(calepinage_id, company)
    if calepinage is None or calepinage.company_id != company.pk:
        raise ValueError('Calepinage hors de la société : aucune conception.')
    if calepinage.appel_offre_id:
        return None, None, {
            'code': CODE_APPEL_OFFRES, 'champ': 'appel_offre_id',
            'message': "Dossier d'appel d'offres : ses règles de cahier des charges (16 modules par chaîne, "
                       "60 kWc par onduleur) restent hors du moteur unique."}
    lead = lead or (get_company_lead(company, calepinage.lead_id) if calepinage.lead_id else None)
    if lead is not None:
        if lead.company_id != company.pk or (calepinage.lead_id and calepinage.lead_id != lead.pk):
            raise ValueError("Ce lead n'est pas celui du calepinage : aucune conception.")
        return lead, {'lead': lead}, None
    from apps.ventes.conception.moteur import lead_du_calepinage
    return lead_du_calepinage(calepinage, company), {'lead__isnull': True, 'calepinage_id': calepinage.pk}, None


class SaisieRefusee(ValueError):
    """Une valeur tapée de l'aperçu inexploitable : ``champ`` la nomme."""

    def __init__(self, message, champ):
        super().__init__(message)
        self.champ = champ


def apercu_conception(lead, company, *, calepinage_id=None, calepinage=None, saisies=None, imposes=None):
    """ADEV137/ADEV152 — la sortie du moteur (contrat, clés ``CLES_SORTIE``)
    pour des valeurs TAPÉES et non enregistrées, SANS AUCUNE ÉCRITURE : le
    porteur (lead, ou calepinage sans lead) est copié en mémoire, ses colonnes
    d'entrée (``CHAMPS_ENTREES`` du marché) reçoivent ``saisies`` (provenance
    ``saisie``), ``imposes`` = champs imposés de ``POST devis/auto/``
    (``composition_imposee.CHAMPS_IMPOSES``, résidentiel). Rend ``(sortie,
    refus du porteur)`` ; ``SaisieRefusee`` pour une saisie hors liste ou
    illisible."""
    import copy

    from django.core.exceptions import ValidationError

    from apps.ventes.conception.champs import CHAMPS_ENTREES
    from apps.ventes.conception.entrees import marche_du_lead
    from apps.ventes.conception.moteur import calculer_conception, reglages_lus_sans_creer, sans_cles_interdites
    from apps.ventes.domain.composition_imposee import imposition_du_corps

    lead, _filtre, refus = _porteur(lead, company, calepinage_id, calepinage)
    if refus is not None:
        return None, refus
    copie, saisies = copy.copy(lead), dict(saisies or {})  # jamais enregistrée
    if 'type_installation' in saisies:
        copie.type_installation = saisies['type_installation']
    try:
        admis = CHAMPS_ENTREES[marche_du_lead(copie)]
    except ValueError as exc:
        raise SaisieRefusee(str(exc), 'type_installation')
    for champ, valeur in saisies.items():
        if champ not in admis:
            raise SaisieRefusee('« %s » n\'est pas une entrée du moteur pour ce marché.' % champ, champ)
        try:
            setattr(copie, champ, copie._meta.get_field(champ).to_python(valeur))
        except (ValidationError, TypeError, ValueError):
            raise SaisieRefusee('Valeur illisible pour « %s ».' % champ, champ)
    with reglages_lus_sans_creer(company):
        resultat = calculer_conception(copie, company, imposes=imposition_du_corps(imposes or {}) or None)
    for champ in saisies:
        resultat.entrees_utilisees[champ] = {'valeur': _en_json(getattr(copie, champ)), 'source': 'saisie'}
    return sans_cles_interdites(_en_json(resultat.sortie())), None


def _declencheur_valide(declencheur):
    declencheur = declencheur or {}
    origine = declencheur.get('origine')
    if origine not in ORIGINES:
        raise ValueError('Origine de relance inconnue : « %s » (admises : %s).' % (origine, ', '.join(ORIGINES)))
    champs = [{'champ': str(c['champ']), 'avant': _en_json(c.get('avant')), 'apres': _en_json(c.get('apres'))}
              for c in declencheur.get('champs') or []]
    return origine, champs


def _champs_ranges(resultat):
    """La sortie du moteur à la forme des colonnes (JSON pur, sans achat ni
    marge : ``moteur.sans_cles_interdites``, seule définition du paquet).
    ``blocs`` est celui du moteur (``etude_params`` complet)."""
    from apps.ventes.conception.moteur import sans_cles_interdites as _sans_achat_ni_marge
    return {
        'etat': resultat.etat, 'refus': _en_json(resultat.refus), 'marche': resultat.marche,
        'option_retenue': resultat.option_retenue or '',
        'valeurs': _sans_achat_ni_marge(_en_json(resultat.valeurs)),
        'blocs': _sans_achat_ni_marge(_en_json(resultat.blocs)),
        'entrees_utilisees': _en_json(resultat.entrees_utilisees),
        'suppositions': _en_json(resultat.suppositions),
        'empreinte': resultat.empreinte, 'niveau_regles': resultat.niveau_regles,
        'version_moteur': resultat.version_moteur,
    }


def _annoncer_apres_validation(version):
    """``conception_recalculee`` une fois la version validée en base."""
    from django.db import transaction

    from core.events import conception_recalculee

    def annoncer():
        conception_recalculee.send_robust(
            sender=type(version), company_id=version.company_id, lead_id=version.lead_id,
            calepinage_id=version.calepinage_id, version=version.version, declencheur=version.declencheur)
    transaction.on_commit(annoncer)
    if version.lead_id and version.etat == 'complet':
        # Relecture E4 M2 — ADEV147 après CHAQUE écriture, en tâche (jamais dans la requête).
        from apps.ventes.conception.receivers import mettre_suivi_en_file
        transaction.on_commit(lambda: mettre_suivi_en_file(version.company_id, version.lead_id))


# ── Relecture E5 B1 — la porte de LECTURE du calepinage (jamais une impasse) ─

def conception_ou_calcul(company, lead_id=None, *, calepinage_id=None):
    """``(conception, en_cours)`` du porteur : la version COURANTE à la forme du
    contrat (``selectors_conception.conception_courante``, qui reste une
    lecture) ; sans version rangée d'un LEAD, UNE relance dédupliquée part en
    file (``receivers.mettre_en_file``, le mécanisme du filet ADEV140 — jamais
    une seconde file, jamais un calcul dans la requête ; origine
    ``remplissage`` : « premier calcul ») et ``en_cours`` dit qu'elle est partie
    ou déjà en file. Un calepinage SANS lead n'en met aucune : le moteur le
    refuserait faute de lieu (``moteur.lead_du_calepinage`` ne porte ni ville
    ni GPS). Lue UNE fois par requête (mémo ``core.request_cache``), sans le suivi des
    devis (``ecart_devis`` / brouillons servis vides : le calepinage sert son propre écart)."""
    from core import request_cache

    if company is None or not getattr(company, 'pk', None):
        return None, False
    cle = ('ventes.conception.courante', company.pk, lead_id, None if lead_id else calepinage_id)
    return request_cache.memoize(cle, lambda: _conception_ou_calcul(company, lead_id, calepinage_id))


def _conception_ou_calcul(company, lead_id, calepinage_id):
    from apps.ventes.conception.receivers import mettre_en_file
    from apps.ventes.selectors_conception import conception_courante

    # Le calepinage sert lui-même l'écart du devis qu'il montre (``devis_retenu.bloc_conception``).
    conception = conception_courante(company, lead_id, calepinage_id=calepinage_id, suivi_des_devis=False)
    if conception is not None or not lead_id:
        return conception, False
    issue = mettre_en_file(company.pk, lead_id=lead_id, origine='remplissage', champs=[])
    return None, issue in ('lancee', 'deja_en_file')


# ── La phrase « pourquoi » (lue telle quelle au chatter du lead) ─────────────

def phrase_du_declencheur(lead, champs, origine, quand):
    """« Recalculé le 23/11 à 14 h 05 : Facture hiver 900 → 1 200 MAD » — date et
    heure locales, chaque champ changé sous le libellé que montrent la fiche et
    l'historique du lead (``crm.activity.TRACKED_FIELDS``), avant → après."""
    from django.utils import timezone

    moment = timezone.localtime(quand)
    debut = 'Recalculé le %s à %d h %02d' % (moment.strftime('%d/%m'), moment.hour, moment.minute)
    if not champs:
        return '%s : %s' % (debut, MOTIFS_ORIGINE[origine])
    return '%s : %s' % (debut, ' ; '.join(_morceau(lead, c) for c in champs))


def _morceau(lead, c):
    from apps.ventes.conception.societe import MOTIFS

    if c['champ'] in MOTIFS:  # relecture E4 B1 : un réglage société, dit en mots
        if c['avant'] is None or c['apres'] is None:
            return MOTIFS[c['champ']]
        return '%s (%s → %s %%)' % (MOTIFS[c['champ']], _lisible(lead, c['champ'], c['avant']),
                                    _lisible(lead, c['champ'], c['apres']))
    return ('%s %s → %s' % (libelle_champ(lead, c['champ']), _lisible(lead, c['champ'], c['avant']),
                            _lisible(lead, c['champ'], c['apres']))
            + (' ' + UNITES[c['champ']] if c['champ'] in UNITES else ''))


def _champ_du_modele(lead, champ):
    from django.core.exceptions import FieldDoesNotExist

    try:
        return lead._meta.get_field(champ) if lead is not None else None
    except FieldDoesNotExist:  # colonne inconnue du modèle : libellé brut
        return None


def libelle_champ(lead, champ):
    # Le libellé de l'historique du lead : la ligne « pourquoi » s'y pose (ALEA69).
    from apps.crm.selectors import libelle_champ_lead
    from apps.ventes.conception.societe import LIBELLES

    libelle = LIBELLES.get(champ) or libelle_champ_lead(champ)
    if libelle:
        return libelle
    modele = _champ_du_modele(lead, champ)
    return str(modele.verbose_name).capitalize() if modele is not None else champ


def _lisible(lead, champ, valeur):
    if valeur in (None, '', [], {}):
        return '—'
    if isinstance(valeur, bool):
        return 'Oui' if valeur else 'Non'
    choix = dict(getattr(_champ_du_modele(lead, champ), 'choices', None) or [])
    if not isinstance(valeur, (list, dict)) and valeur in choix:
        return str(choix[valeur])
    if isinstance(valeur, (int, float, Decimal)) or _nombre(valeur) is not None:
        return _nombre_francais(_nombre(valeur))
    if isinstance(valeur, list):
        return ', '.join(str(v) for v in valeur)
    return str(valeur)


def _nombre(valeur):
    try:
        nombre = Decimal(str(valeur))
    except (InvalidOperation, TypeError, ValueError):  # texte non numérique
        return None
    return nombre if nombre.is_finite() else None


def _nombre_francais(nombre):
    """1200 → « 1 200 » ; 1234.5 → « 1 234,5 » (zéros de fin retirés)."""
    entier = nombre == nombre.to_integral_value()
    texte = '{:,.0f}'.format(nombre) if entier else '{:,.2f}'.format(nombre).rstrip('0').rstrip('.')
    return texte.replace(',', ' ').replace('.', ',')


# ── JSON pur ────────────────────────────────────────────────────────────────

def _defaut_json(valeur):
    if isinstance(valeur, Decimal):
        return int(valeur) if valeur == valeur.to_integral_value() and valeur.as_tuple().exponent >= 0 \
            else float(valeur)
    if isinstance(valeur, (date, datetime)):
        return valeur.isoformat()
    return str(valeur)


def _en_json(valeur):
    return json.loads(json.dumps(valeur, default=_defaut_json))
