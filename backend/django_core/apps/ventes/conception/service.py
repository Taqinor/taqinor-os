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


def relancer(lead, *, company, declencheur, auteur=None, forcer=False, toit=None):
    """La conception du ``lead`` (de ``company`` seulement) recalculée et, si
    son empreinte a changé (ou ``forcer``), rangée en version suivante.

    ``declencheur`` : ``{champs: [{champ, avant, apres}], origine}`` (``raison``
    est construite ici, une ``raison`` passée est remplacée) ; ``auteur`` :
    l'utilisateur (``None`` = tâche du moteur) ; ``toit`` : la pose servie (son
    ``empreinte`` et son ``plafond_panneaux`` entrent dans le calcul)."""
    from django.utils import timezone

    from apps.ventes.conception.entrees import entrees_pour
    from apps.ventes.conception.moteur import calculer_conception, reglages_lus_sans_creer
    from apps.ventes.models import ConceptionLead

    if getattr(lead, 'company_id', None) != getattr(company, 'pk', None):
        raise ValueError('Lead hors de la société : aucune conception.')
    origine, champs = _declencheur_valide(declencheur)
    with reglages_lus_sans_creer(company):
        entrees = entrees_pour(lead, company, toit=toit)
        resultat = calculer_conception(lead, company, entrees=entrees, toit=toit)
    courante = ConceptionLead.objects.filter(company=company, lead=lead, courante=True).first()
    if courante is not None and courante.empreinte == resultat.empreinte and not forcer:
        return Relance(courante, False, resultat)
    maintenant = timezone.now()
    version = ConceptionLead.ranger(
        lead=lead, calcule_le=maintenant, calcule_par=auteur,
        declencheur={'raison': phrase_du_declencheur(lead, champs, origine, maintenant),
                     'champs': champs, 'origine': origine},
        empreinte_pose=entrees.empreinte_pose, **_champs_ranges(resultat))
    _annoncer_apres_validation(version)
    return Relance(version, True, resultat)


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
    morceaux = ['%s %s → %s' % (_libelle(lead, c['champ']), _lisible(lead, c['champ'], c['avant']),
                                _lisible(lead, c['champ'], c['apres'])) for c in champs]
    return '%s : %s' % (debut, ' ; '.join(morceaux))


def _champ_du_modele(lead, champ):
    try:
        return lead._meta.get_field(champ) if lead is not None else None
    except Exception:  # noqa: BLE001 — colonne inconnue du modèle : libellé brut (D-ENF22-BLE001)
        return None


def _libelle(lead, champ):
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
