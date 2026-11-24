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
1 200 »), recopiée telle quelle par le chatter du CRM. Aucune clé d'achat ni de
marge n'entre dans ``valeurs`` ni ``blocs`` (parcours récursif). Aucun devis
n'est lu ni écrit ici : un devis envoyé ou accepté ne bouge jamais.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json

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


def relancer(lead, *, company, declencheur, auteur=None, forcer=False, toit=None, calepinage_id=None):
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
    alors ``None``)."""
    from django.utils import timezone

    from apps.ventes.conception.entrees import entrees_pour
    from apps.ventes.conception.moteur import calculer_conception, empreinte_conception, reglages_lus_sans_creer
    from apps.ventes.models import ConceptionLead

    origine, champs = _declencheur_valide(declencheur)
    lead, porteur, refus = _porteur(lead, company, calepinage_id)
    if refus is not None:
        return Relance(None, False, None, refus)
    courante = ConceptionLead.objects.filter(company=company, courante=True, **porteur).first()
    with reglages_lus_sans_creer(company):
        entrees = entrees_pour(lead, company, toit=toit)
        if courante is not None and courante.empreinte == empreinte_conception(entrees) and not forcer:
            return Relance(courante, False, None)
        resultat = calculer_conception(lead, company, entrees=entrees, toit=toit)
    maintenant = timezone.now()
    version = ConceptionLead.ranger(
        lead=porteur.get('lead'), calepinage_id=calepinage_id, company=company,
        calcule_le=maintenant, calcule_par=auteur,
        declencheur={'raison': phrase_du_declencheur(porteur.get('lead'), champs, origine, maintenant),
                     'champs': champs, 'origine': origine},
        empreinte_pose=entrees.empreinte_pose, **_champs_ranges(resultat))
    _annoncer_apres_validation(version)
    return Relance(version, True, resultat)


CODE_APPEL_OFFRES = 'appel_offres_hors_moteur'


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


# ── La phrase « pourquoi » (lue telle quelle au chatter du lead) ─────────────

def phrase_du_declencheur(lead, champs, origine, quand):
    """« Recalculé le 23/11 à 14 h 05 : Facture hiver 900 → 1 200 » — date et
    heure locales, chaque champ changé sous le libellé que montrent la fiche et
    l'historique du lead (``crm.activity.TRACKED_FIELDS``), avant → après."""
    from django.utils import timezone

    moment = timezone.localtime(quand)
    debut = 'Recalculé le %s à %d h %02d' % (moment.strftime('%d/%m'), moment.hour, moment.minute)
    if not champs:
        return '%s : %s' % (debut, MOTIFS_ORIGINE[origine])
    morceaux = ['%s %s → %s' % (libelle_champ(lead, c['champ']), _lisible(lead, c['champ'], c['avant']),
                                _lisible(lead, c['champ'], c['apres'])) for c in champs]
    return '%s : %s' % (debut, ' ; '.join(morceaux))


def _champ_du_modele(lead, champ):
    try:
        return lead._meta.get_field(champ) if lead is not None else None
    except Exception:  # noqa: BLE001 — colonne inconnue du modèle : libellé brut (D-ENF22-BLE001)
        return None


def libelle_champ(lead, champ):
    # Le libellé de l'historique du lead : la ligne « pourquoi » s'y pose (ALEA69).
    from apps.crm.activity import TRACKED_FIELDS

    if champ in TRACKED_FIELDS:
        return TRACKED_FIELDS[champ]
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
    except Exception:  # noqa: BLE001 — texte non numérique (D-ENF22-BLE001)
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
