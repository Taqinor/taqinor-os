"""L-QUEST (fondateur 25/08/2026) — « questionnaire envoyable au client ».

Règles MÉTIER du questionnaire, isolées ici pour être testables sans HTTP :
quelles sections existent, quels champs `Lead` chacune porte, laquelle est
MANQUANTE (le défaut des questions posées), quoi pré-remplir, et comment
enregistrer une section répondue.

Le contrat servi/consommé est figé dans
``apps/crm/contract_samples/questionnaire_lead.json`` (PACT10).

TROIS PRINCIPES NON NÉGOCIABLES :
  · **zéro chiffre inventé** — un pré-remplissage absent vaut ``None``, jamais
    un défaut forfaitaire ;
  · **on n'efface jamais** — une valeur déjà renseignée sur le lead n'est
    jamais remplacée par du vide, et une section n'écrit QUE ses propres
    champs (une réponse « contact » ne peut donc pas toucher le GPS) ;
  · **on ne REDEMANDE jamais** (ordre fondateur 25/08/2026) — une donnée que
    le lead porte DÉJÀ n'est jamais reposée à vide au client : elle revient
    pré-remplie (donc confirmable), et quand une AUTRE donnée déjà connue la
    couvre plus précisément, la question disparaît purement et simplement.
    Le cas qui a déclenché la règle : « you are adding the address while the
    client already have given its GPS position » — un repère GPS localise le
    toit au mètre ; redemander l'adresse postale, c'est refaire saisir au
    client, en MOINS précis, ce qu'il vient de donner. Le grain de cette
    décision est le CHAMP, pas la section : voir :func:`champs_a_poser`.
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


def _gps_connu(lead) -> bool:
    return lead.gps_lat is not None and lead.gps_lng is not None


#: Colonnes qu'une AUTRE donnée déjà connue du lead rend inutiles à demander.
#: Clé = colonne du questionnaire ; valeur = prédicat « l'information est déjà
#: couverte, et plus précisément, par autre chose que le lead porte ».
#:
#: ``adresse`` ← GPS : ordre fondateur du 25/08/2026 (voir l'en-tête du
#: module). Un couple (lat, lng) désigne le toit ; l'adresse postale, elle, est
#: approximative au Maroc (quartiers sans numérotation) — la redemander à
#: quelqu'un qui a déjà posé son repère est une régression de précision ET une
#: question en double. La ville, elle, N'EST PAS couverte : rien ici ne
#: géocode à l'envers, donc une ville inconnue reste une vraie question.
_COUVERT_PAR = {
    'adresse': _gps_connu,
}


def _couverte_ailleurs(lead, cle) -> bool:
    predicat = _COUVERT_PAR.get(cle)
    return bool(predicat and predicat(lead))


def _encore_a_obtenir(lead, cle) -> bool:
    """La réponse à ``cle`` est-elle encore à obtenir DU CLIENT ?

    Non si le lead la porte déjà (elle sera pré-remplie), non plus si une
    autre donnée connue la couvre (``_COUVERT_PAR``)."""
    return (_vide(getattr(lead, cle, None))
            and not _couverte_ailleurs(lead, cle))


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
        # `adresse` passe par `_encore_a_obtenir` : quand le GPS est déjà là,
        # elle ne compte PLUS comme une information manquante (sinon le
        # défaut des questions rouvrait un écran « Coordonnées » dont la
        # seule question restante était celle qu'on s'interdit de poser).
        'contact': (_vide(lead.email) or _encore_a_obtenir(lead, 'adresse')
                    or _vide(lead.ville)),
        'gps': not _gps_connu(lead),
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


def champs_a_poser(lead, sections) -> dict:
    """``{section: [colonnes à AFFICHER]}`` — le grain FIN du questionnaire.

    La section dit QUEL écran s'ouvre ; cette carte dit quelles questions cet
    écran a encore le droit de poser. Une colonne est servie quand :

      · le lead la porte déjà → elle revient PRÉ-REMPLIE (le client confirme
        ou corrige, il ne ressaisit pas) ; ou
      · elle est réellement inconnue ET qu'aucune autre donnée connue ne la
        couvre (``_COUVERT_PAR``).

    Une colonne à la fois VIDE et COUVERTE (l'adresse d'un lead qui a déjà
    donné son GPS) est ABSENTE de la carte : la page ne la dessine pas. Rien
    n'est jamais inventé ici — on ne fabrique pas l'adresse depuis le GPS, on
    se contente de ne pas la redemander.

    Les sections photo n'ont aucune colonne : leur liste est vide, ce qui ne
    veut PAS dire « rien à demander » (la réponse y est une pièce jointe) —
    d'où :func:`sections_a_servir`, seul endroit qui tranche ce cas."""
    return {
        section: [cle for cle in CHAMPS_PAR_SECTION.get(section, ())
                  if not (_vide(getattr(lead, cle, None))
                          and _couverte_ailleurs(lead, cle))]
        for section in sections
    }


def sections_a_servir(lead, sections):
    """Sections actives DONT il reste quelque chose à afficher.

    Garde-fou d'écran mort : si le commercial coche une section dont toutes
    les colonnes sont vides ET couvertes ailleurs, la page n'a plus rien à
    dessiner — mieux vaut ne pas ouvrir l'écran du tout que d'en montrer un
    vide. Les sections photo, elles, restent TOUJOURS servies : leur réponse
    n'est pas une colonne."""
    carte = champs_a_poser(lead, sections)
    return [section for section in sections
            if section in _SECTIONS_PHOTO or carte.get(section)]


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

    TOUJOURS construite sur l'origine du SITE PUBLIC (``PUBLIC_SITE_URL``),
    JAMAIS sur l'hôte de la requête. Revue critique du 25/08/2026, finding
    #6 : la page ``/questionnaire/<token>/`` vit dans ``apps/web`` (le site
    Astro) — l'ERP ne la sert nulle part. Le mint étant appelé depuis l'écran
    commercial, donc depuis l'hôte de l'API, ``build_absolute_uri`` fabriquait
    un lien sur l'API : le client recevait une URL MORTE.

    ``request`` est accepté et IGNORÉ : la signature reste celle des appelants
    existants, mais aucun hôte entrant ne peut plus décider où pointe un lien
    envoyé à un client (c'est aussi ce qui empêche un ``Host:`` forgé de
    fabriquer une URL de questionnaire sur un domaine tiers)."""
    from django.conf import settings

    base = (getattr(settings, 'PUBLIC_SITE_URL', '')
            or getattr(settings, 'SITE_URL', '') or '').rstrip('/')
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
