"""L-QUEST (fondateur 25/08/2026) — « questionnaire envoyable au client ».

Règles MÉTIER du questionnaire, isolées ici pour être testables sans HTTP :
quelles sections existent, quels champs `Lead` chacune porte, laquelle est
MANQUANTE (le défaut des questions posées), quoi pré-remplir, et comment
enregistrer une section répondue.

Le contrat servi/consommé est figé dans
``apps/crm/contract_samples/questionnaire_lead.json`` (PACT10).

DEUX PRINCIPES NON NÉGOCIABLES :
  · **zéro chiffre inventé** — un pré-remplissage absent vaut ``None``, jamais
    un défaut forfaitaire ;
  · **on n'efface jamais** — une valeur déjà renseignée sur le lead n'est
    jamais remplacée par du vide, et une section n'écrit QUE ses propres
    champs (une réponse « contact » ne peut donc pas toucher le GPS).
"""
from .models import Lead, LeadActivity, QuestionnaireLien

#: Whitelist des sections — source unique, portée par le modèle.
SECTIONS = QuestionnaireLien.SECTIONS_CLES

#: Colonnes `crm.Lead` que chaque section a le droit d'écrire ET de
#: pré-remplir. Une clé hors de cette table n'est jamais lue ni écrite.
CHAMPS_PAR_SECTION = {
    'contact': ('email', 'adresse', 'ville'),
    'gps': ('gps_lat', 'gps_lng'),
    'energie': ('facture_hiver', 'facture_ete', 'ete_differente',
                'conso_mensuelle_kwh', 'tranche_onee', 'raccordement'),
    'toiture': ('type_toiture', 'surface_toiture_m2', 'roof_age', 'ownership'),
    'occupation': ('occupation_jour',),
    'equipements': (
        'equip_piscine', 'equip_piscine_pompe_kw',
        'equip_piscine_heures_jour', 'equip_piscine_creneau',
        'equip_voiture_electrique', 'equip_ve_km_semaine',
        'equip_ve_chargeur_kw', 'equip_ve_creneau',
        'equip_clim', 'equip_clim_pieces', 'equip_clim_kw',
        'equip_clim_creneau',
        'equip_chauffe_eau_electrique', 'equip_chauffe_eau_kw',
        'equip_chauffe_eau_creneau',
    ),
    # Sections PHOTO : aucune colonne — la réponse est une pièce jointe.
    'photo_facture': (),
    'photo_compteur': (),
    'photo_tableau': (),
}

#: Libellé français d'une section (chatter + écran commercial).
LIBELLE_SECTION = {
    'contact': 'coordonnées',
    'gps': 'localisation GPS',
    'energie': 'énergie',
    'photo_facture': 'photo de la facture',
    'photo_compteur': 'photo du compteur',
    'photo_tableau': 'photo du tableau électrique',
    'toiture': 'toiture',
    'occupation': 'présence en journée',
    'equipements': 'équipements',
}

#: Les trois booléens equip_* à TROIS ÉTATS : ``None`` = « jamais posée »,
#: ce qui est DIFFÉRENT de ``False`` (« le client a répondu non »). C'est ce
#: qui rend la section « équipements » manquante ou non.
_EQUIP_BOOLEENS = (
    'equip_piscine', 'equip_voiture_electrique', 'equip_clim',
    'equip_chauffe_eau_electrique',
)

# Sections photo → mots-clés reconnus dans le LIBELLÉ du fichier joint.
#
# APPROXIMATION ASSUMÉE : le magasin générique ``records.Attachment`` ne porte
# aucun type métier ; on reconnaît donc la nature d'une photo à son nom de
# fichier (celui que pose ``intake_photo.attach_capture_photo`` pour les
# captures du site, et celui que pose ce module pour les réponses du
# questionnaire). En cas de doute, la section est déclarée MANQUANTE — on
# repose la question plutôt que de supposer qu'on a déjà la photo.
_PHOTO_MOTS_CLES = {
    'photo_facture': ('facture', 'bill'),
    'photo_compteur': ('compteur', 'meter'),
    'photo_tableau': ('tableau', 'disjoncteur'),
}
_SECTIONS_PHOTO = tuple(_PHOTO_MOTS_CLES)

#: Extension retenue selon le type MIME annoncé par la data-URL du client.
#: Purement cosmétique (le nom affiché) : la vraie validation reste celle des
#: magic-bytes de ``records.storage``.
_EXT_PAR_MIME = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
}


class SectionInconnue(ValueError):
    """Section hors whitelist (ou non demandée sur ce lien)."""


def _vide(valeur) -> bool:
    """Une valeur « pas renseignée » : ``None`` ou une chaîne blanche.

    ``False`` et ``0`` ne sont PAS vides — ce sont des réponses."""
    if valeur is None:
        return True
    return isinstance(valeur, str) and not valeur.strip()


def _libelles_pieces_jointes(lead):
    """Noms de fichier des pièces jointes du lead (minuscules).

    Le lead est déjà company-scopé : le couple (content_type, object_id)
    désigne UNE fiche d'UNE société — aucune fuite inter-locataires."""
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment

    content_type = ContentType.objects.get_for_model(Lead)
    noms = Attachment.objects.filter(
        content_type=content_type, object_id=lead.pk,
    ).values_list('filename', flat=True)
    return [(nom or '').lower() for nom in noms]


def _photo_presente(section, libelles) -> bool:
    mots = _PHOTO_MOTS_CLES[section]
    return any(mot in nom for nom in libelles for mot in mots)


def manquantes(lead) -> dict:
    """Carte ``{section: bool}`` — l'information de la section est-elle
    (encore) inconnue ? C'est le DÉFAUT des questions posées au client.

    Fonction PURE au sens métier (une seule requête, pour les pièces
    jointes) : aucun effet de bord, aucun chiffre inventé."""
    from .devis_auto import champs_manquants

    libelles = _libelles_pieces_jointes(lead)

    # Énergie : la règle serveur du devis automatique (source de vérité
    # UNIQUE, jamais dupliquée) + les deux champs tarifaires que le
    # générateur n'exige pas mais que le commercial veut toujours.
    # NB : `ete_differente` n'est PAS un signal de « jamais posée » — sa
    # colonne est NOT NULL default False, donc elle vaut toujours Oui/Non.
    energie = bool(champs_manquants(lead))
    if not energie:
        energie = _vide(lead.tranche_onee) or _vide(lead.raccordement)

    return {
        'contact': (_vide(lead.email) or _vide(lead.adresse)
                    or _vide(lead.ville)),
        'gps': lead.gps_lat is None or lead.gps_lng is None,
        'energie': energie,
        'photo_facture': not _photo_presente('photo_facture', libelles),
        'photo_compteur': not _photo_presente('photo_compteur', libelles),
        'photo_tableau': not _photo_presente('photo_tableau', libelles),
        'toiture': (_vide(lead.type_toiture)
                    or lead.surface_toiture_m2 is None
                    or lead.roof_age is None
                    or _vide(lead.ownership)),
        'occupation': _vide(lead.occupation_jour),
        # Trois-états : AU MOINS UN booléen equip_* jamais posé (None).
        'equipements': any(getattr(lead, cle) is None
                           for cle in _EQUIP_BOOLEENS),
    }


def questions_par_defaut(lead) -> dict:
    """Carte EXPLICITE des questions posées quand le commercial n'en choisit
    aucune : « DÉFAUT = les informations manquantes » (ordre fondateur)."""
    return dict(manquantes(lead))


def valider_questions(brut) -> dict:
    """Normalise le corps ``questions`` du mint. Lève :class:`SectionInconnue`
    sur une clé hors whitelist — jamais un silence (une faute de frappe du
    commercial ne doit pas retirer une question sans le dire)."""
    if brut is None:
        return None
    if not isinstance(brut, dict):
        raise SectionInconnue('« questions » doit être un objet {section: '
                              'true/false}.')
    out = {}
    for cle, valeur in brut.items():
        if cle not in SECTIONS:
            raise SectionInconnue(f'Section inconnue : « {cle} ».')
        out[cle] = bool(valeur)
    return out


def prefill(lead, sections) -> dict:
    """Valeurs ACTUELLES du lead pour les champs des sections actives.

    ZÉRO CHIFFRE INVENTÉ : une valeur absente vaut ``None`` — jamais un
    défaut forfaitaire. Les ``Decimal`` sont rendus en ``float`` (JSON)."""
    from decimal import Decimal

    out = {}
    for section in sections:
        for cle in CHAMPS_PAR_SECTION.get(section, ()):
            valeur = getattr(lead, cle, None)
            if isinstance(valeur, Decimal):
                valeur = float(valeur)
            elif isinstance(valeur, str) and not valeur.strip():
                valeur = None
            out[cle] = valeur
    return out


def _extension_photo(brut) -> str:
    """Extension d'affichage déduite de l'en-tête data-URL, sinon ``.jpg``."""
    if isinstance(brut, str) and brut.startswith('data:'):
        entete = brut[5:brut.find(',')] if ',' in brut else ''
        mime = entete.split(';')[0].strip().lower()
        return _EXT_PAR_MIME.get(mime, '.jpg')
    return '.jpg'


def _enregistrer_photo(lead, section, photo):
    """Joint la photo d'une section photo_* au lead. Réutilise TEL QUEL le
    chemin de capture du site (``intake_photo.attach_capture_photo`` :
    base64/data-URL, magic-bytes, 10 Mo, MinIO, ``records.Attachment``
    company-scopé) — jamais un second magasin de fichiers.

    Le nom du fichier porte le mot-clé de la section pour que
    :func:`manquantes` la reconnaisse ensuite."""
    from .intake_photo import attach_capture_photo

    mot = _PHOTO_MOTS_CLES[section][0]
    nom = f'questionnaire-{mot}{_extension_photo(photo)}'
    return attach_capture_photo(
        lead, {'photo': photo, 'photoFilename': nom})


#: Colonnes que ``Lead.save()`` RECALCULE à chaque écriture (dédup QW10) et
#: que ``date_modification`` (auto_now) suit. Un ``update_fields`` qui les
#: omet les laisserait rassir : le lead garderait l'e-mail normalisé de
#: l'ancienne adresse et la dédup cesserait de le retrouver. On les ajoute
#: donc dès que leur source est écrite.
_COLONNES_DERIVEES = {
    'email': ('email_normalise',),
    'telephone': ('phone_normalise',),
}


def _colonnes_a_ecrire(champs):
    """``update_fields`` complet : les champs de la section + ce que
    ``Lead.save()`` en dérive + l'horodatage de modification."""
    colonnes = list(champs)
    for source, derivees in _COLONNES_DERIVEES.items():
        if source in champs:
            colonnes.extend(derivees)
    colonnes.append('date_modification')
    return colonnes


def appliquer_section(lien, section, reponses=None, photo=None):
    """Enregistre UNE section répondue par le client. Retourne la liste des
    clés réellement enregistrées (vide si rien d'exploitable).

    Garanties :
      · seule la section demandée est écrite (whitelist par section) ;
      · une valeur déjà renseignée n'est JAMAIS remplacée par du vide ;
      · l'historique du lead reçoit une note de section + une ligne
        ancienne→nouvelle valeur par champ suivi (mécanisme existant) ;
      · la progression du client est mémorisée sur le lien (reprise).
    """
    from django.utils import timezone

    from . import activity
    from .webhooks import champs_lead_depuis_reponses

    if section not in SECTIONS:
        raise SectionInconnue(f'Section inconnue : « {section} ».')
    if not lien.question_posee(section):
        raise SectionInconnue(
            f'Section non demandée sur ce lien : « {section} ».')

    lead = lien.lead
    enregistrees = []

    if section in _SECTIONS_PHOTO:
        if _enregistrer_photo(lead, section, photo) is not None:
            enregistrees.append('photo')
    else:
        champs = champs_lead_depuis_reponses(
            reponses, CHAMPS_PAR_SECTION[section])
        if champs:
            # Instantané AVANT écriture : le chatter compare l'ancien au
            # nouveau via le mécanisme existant (activity.log_changes).
            avant = Lead.objects.get(pk=lead.pk)
            for cle, valeur in champs.items():
                setattr(lead, cle, valeur)
            lead.save(update_fields=_colonnes_a_ecrire(champs))
            enregistrees = list(champs)
            activity.log_changes(avant, lead, None)

    if not enregistrees:
        return []

    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=('Questionnaire — section '
              f'{LIBELLE_SECTION[section]} répondue par le client'),
    )

    repondues = lien.sections_repondues
    if not isinstance(repondues, dict):
        repondues = {}
    repondues[section] = True
    lien.sections_repondues = repondues
    lien.derniere_reponse_at = timezone.now()
    lien.save(update_fields=['sections_repondues', 'derniere_reponse_at'])
    return enregistrees


# ── Cycle de vie du lien (mint côté commercial, résolution côté public) ────

class LienIndisponible(Exception):
    """Jeton inconnu ou expiré (la vue publique traduit en 404 générique)."""


def url_publique(token, *, request=None) -> str:
    """URL complète de la page questionnaire pour un jeton donné.

    Même construction de base que ``services.public_booking_url`` (l'hôte de
    la requête, sinon ``PUBLIC_SITE_URL``) — une seule convention d'URL
    publique dans l'app."""
    from django.conf import settings

    if request is not None:
        base = request.build_absolute_uri('/')[:-1]
    else:
        base = (getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
    return f'{base}/questionnaire/{token}/'


def mint_lien(lead, *, questions=None, user=None):
    """Crée — ou RÉUTILISE — le lien questionnaire d'un lead.

    IDEMPOTENT : tant qu'un lien non expiré existe pour ce lead, c'est LUI
    qui est renvoyé (ses ``questions`` sont simplement remises à jour) —
    jamais un second jeton, donc jamais deux liens vivants chez le client.

    ``questions=None`` (le commercial n'a rien coché) → les informations
    MANQUANTES, ordre fondateur. Multi-tenant : la société vient TOUJOURS du
    lead, jamais du corps de requête.

    Retourne ``(lien, change)`` — ``change`` est vrai quand le lien vient
    d'être créé OU que les questions posées ont réellement bougé (c'est ce
    qui mérite une trace dans l'historique ; un re-POST identique n'en
    laisse aucune)."""
    from django.utils import timezone

    maintenant = timezone.now()
    lien = (
        QuestionnaireLien.objects
        .filter(lead=lead, company=lead.company, expires_at__gt=maintenant)
        .order_by('-created_at')
        .first()
    )
    cree = lien is None
    if cree:
        lien = QuestionnaireLien(
            company=lead.company, lead=lead, created_by=user)
        avant = None
    else:
        avant = lien.questions if isinstance(lien.questions, dict) else {}

    lien.questions = (questions if questions is not None
                      else questions_par_defaut(lead))
    if cree:
        lien.save()
    else:
        lien.save(update_fields=['questions'])
    # Recalage fold 25/08 : troisième valeur ``cree`` — le dialogue ERP mint
    # SILENCIEUSEMENT à l'ouverture (pour lire manquantes/questions), et le
    # chatter ne doit jamais dire « envoyé » sur une simple ouverture ; le
    # libellé de la trace distingue donc création et mise à jour (l'envoi
    # WhatsApp réel n'est pas observable côté serveur — on ne l'affirme pas).
    return lien, cree or lien.questions != avant, cree


def resoudre(token):
    """Résout un jeton PUBLIC → ``(lien, interne)``.

    ``interne`` vaut True quand le jeton est celui du COMMERCIAL (aperçu) —
    l'appelant doit alors ne RIEN écrire ni journaliser. Lève
    :class:`LienIndisponible` si le jeton est inconnu ou expiré ; le lien
    n'est jamais « consommé » (magic-link : il se rouvre autant de fois que
    le client en a besoin, jusqu'à expiration)."""
    if not token:
        raise LienIndisponible('Introuvable.')
    lien = (QuestionnaireLien.objects
            .select_related('lead', 'company')
            .filter(token=token).first())
    interne = False
    if lien is None:
        lien = (QuestionnaireLien.objects
                .select_related('lead', 'company')
                .filter(token_interne=token).first())
        interne = lien is not None
    if lien is None or lien.is_expired:
        raise LienIndisponible('Introuvable.')
    # Un lead SUPPRIMÉ (soft-delete) ferme son lien : sans cette garde, la
    # page s'ouvrirait encore et l'écriture planterait plus loin
    # (``Lead.objects`` masque la corbeille). Un lead simplement ARCHIVÉ
    # reste ouvert — l'archivage est un rangement réversible du pipeline,
    # pas une raison de bloquer le client qui répond.
    if getattr(lien.lead, 'is_deleted', False):
        raise LienIndisponible('Introuvable.')
    return lien, interne
