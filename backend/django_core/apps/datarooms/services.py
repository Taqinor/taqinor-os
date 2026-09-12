"""Écritures / orchestration du module ``apps.datarooms`` (groupe NTDOC, P2).

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête.
"""
from django.db import transaction
from django.utils import timezone

from .models import AccesSalleDonnees, SalleDeDonnees, SalleDeDonneesDocument

# NTDOC12 — issues de la résolution d'un jeton viewer PUBLIC. Introuvable et
# révoqué sont volontairement le MÊME code : un lien révoqué ne doit jamais
# révéler qu'il a existé.
ACCES_INTROUVABLE = 'introuvable'
ACCES_EXPIRE = 'expire'
ACCES_OK = 'ok'


class SalleFermee(ValueError):
    """Action impossible : la salle est fermée (message français)."""


@transaction.atomic
def ajouter_documents(salle, documents, *, visible=True):
    """NTDOC11 — Ajoute des documents GED à une salle (idempotent).

    ``documents`` est un itérable d'instances ``ged.Document`` DÉJÀ résolues et
    vérifiées côté appelant comme appartenant à la société de la salle (la vue
    le garantit ; ce service ne fait jamais confiance à un id brut de requête).

    Un document déjà présent n'est PAS dupliqué (contrainte d'unicité + ``
    get_or_create``) et son ordre existant est conservé. Renvoie la liste des
    lignes créées."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : son contenu est figé.")
    prochain = (SalleDeDonneesDocument.objects
                .filter(salle=salle)
                .order_by('-ordre')
                .values_list('ordre', flat=True)
                .first() or 0)
    creees = []
    for document in documents:
        prochain += 1
        ligne, cree = SalleDeDonneesDocument.objects.get_or_create(
            salle=salle, document=document,
            defaults={'company': salle.company, 'ordre': prochain,
                      'visible': visible})
        if cree:
            creees.append(ligne)
        else:
            prochain -= 1
    return creees


@transaction.atomic
def retirer_document(salle, document):
    """NTDOC11 — Retire un document de la salle SANS jamais toucher à la GED.

    Seule la ligne d'appartenance disparaît : le ``ged.Document`` reste intact,
    à sa place, avec ses versions. Renvoie True si une ligne a été retirée."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : son contenu est figé.")
    supprimees, _ = SalleDeDonneesDocument.objects.filter(
        salle=salle, document=document).delete()
    return bool(supprimees)


def creer_salle(*, company, nom, created_by=None, description='',
                deal_type='', dossier_source=None, expires_at=None):
    """NTDOC11 — Crée une salle de données (société posée côté serveur)."""
    return SalleDeDonnees.objects.create(
        company=company, nom=nom, description=description,
        deal_type=deal_type, dossier_source=dossier_source,
        expires_at=expires_at, created_by=created_by)


# ── NTDOC15 — Salle liée à un deal (Lead / Chantier / Contrat) ──────────────

def _carte_lead(company, source_id):
    """Fiche-carte d'un lead via ``crm.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``crm.models`` directement."""
    try:
        from apps.crm import selectors as crm_selectors
        return crm_selectors.lead_card(source_id, company)
    except Exception:  # pragma: no cover - défensif (app absente / cible KO)
        return None


def _carte_chantier(company, source_id):
    """Fiche-carte d'un chantier via ``installations.selectors`` (ou None)."""
    try:
        from apps.installations import selectors as inst_selectors
        return inst_selectors.chantier_card(source_id, company)
    except Exception:  # pragma: no cover - défensif
        return None


def _carte_contrat(company, source_id):
    """Fiche-carte d'un contrat via ``contrats.selectors`` (ou None)."""
    try:
        from apps.contrats import selectors as contrats_selectors
        return contrats_selectors.contrat_card(source_id, company)
    except Exception:  # pragma: no cover - défensif
        return None


#: Résolveurs par type de source. Une entrée n'existe QUE si l'app cible expose
#: un sélecteur de lecture exploitable — jamais d'import de ses ``models``.
_RESOLVEURS_SOURCE = {
    SalleDeDonnees.TypeSource.LEAD: _carte_lead,
    SalleDeDonnees.TypeSource.CHANTIER: _carte_chantier,
    SalleDeDonnees.TypeSource.CONTRAT: _carte_contrat,
}


def carte_source(company, source_type, source_id):
    """NTDOC15 — Fiche-carte ``{label, subtitle, url}`` de l'objet d'origine.

    Renvoie None si le type est inconnu, l'id absent, ou l'objet hors société
    (le sélecteur cible est scopé : un id d'ailleurs renvoie None, jamais une
    fuite)."""
    if not source_type or not source_id:
        return None
    resolveur = _RESOLVEURS_SOURCE.get(source_type)
    if resolveur is None:
        return None
    return resolveur(company, source_id)


def creer_salle_depuis_source(*, company, source_type, source_id,
                              created_by=None, nom='', description='',
                              deal_type='', expires_at=None):
    """NTDOC15 — Crée une salle PRÉ-NOMMÉE depuis un lead/chantier/contrat.

    Le nom par défaut vient du LIBELLÉ de l'objet source (résolu par le
    sélecteur de l'app cible) — jamais d'un libellé inventé. Un ``nom`` fourni
    par l'appelant l'emporte.

    Lève ``ValueError`` (message français) si la source est inconnue ou hors
    société : la vue la traduit en 404, sans jamais dire si l'objet existe
    ailleurs."""
    carte = carte_source(company, source_type, source_id)
    if carte is None:
        raise ValueError(
            "Cet objet est introuvable dans votre société.")
    libelle = (nom or '').strip() or (carte.get('label') or '').strip()
    if not libelle:
        raise ValueError("Impossible de nommer la salle depuis cet objet.")
    salle = SalleDeDonnees.objects.create(
        company=company, nom=libelle[:255], description=description,
        deal_type=deal_type, expires_at=expires_at, created_by=created_by,
        source_type=source_type, source_id=source_id)
    return salle


# ── NTDOC12 — Accès par viewer nommé ────────────────────────────────────────

def inviter_viewer(salle, *, nom, email='', expires_at=None, created_by=None):
    """NTDOC12 — Crée l'accès d'un viewer nommé (son lien lui est propre).

    La société vient TOUJOURS de la salle (jamais d'un corps de requête). Deux
    viewers de la même salle reçoivent deux jetons et deux expirations
    indépendants."""
    if not salle.est_ouverte:
        raise SalleFermee("Cette salle est fermée : aucun nouvel accès.")
    return AccesSalleDonnees.objects.create(
        company=salle.company, salle=salle, nom=nom, email=email,
        expires_at=expires_at, created_by=created_by)


def revoquer_acces(acces):
    """NTDOC12 — Révoque UN accès viewer (les autres ne bougent pas).

    Idempotent. Écriture ciblée : ne touche aucun autre champ."""
    if acces.revoque:
        return acces
    AccesSalleDonnees.objects.filter(pk=acces.pk).update(revoque=True)
    acces.revoque = True
    return acces


def resoudre_acces_public(token, *, now=None):
    """NTDOC12 — Résout un jeton viewer PUBLIC.

    Renvoie ``(statut, acces)`` où ``statut`` vaut ``ACCES_INTROUVABLE``
    (jeton inconnu OU révoqué — indistinct, pas de fuite), ``ACCES_EXPIRE``
    (expiration viewer ou salle dépassée, ou salle fermée) ou ``ACCES_OK``.

    Aucune identité ni société n'est lue de la requête : tout vient du jeton.
    Il n'existe AUCUN listing — seul un jeton exact résout quelque chose."""
    if not token:
        return ACCES_INTROUVABLE, None
    acces = (AccesSalleDonnees.objects
             .select_related('salle', 'salle__company', 'company')
             .filter(token=token)
             .first())
    if acces is None or acces.revoque:
        return ACCES_INTROUVABLE, None
    if not acces.salle.est_ouverte or acces.est_expire(now=now):
        return ACCES_EXPIRE, acces
    return ACCES_OK, acces


def lien_public_acces(acces):
    """NTDOC12 — Lien public d'un viewer (absolu si ``PUBLIC_SITE_URL`` posée).

    Réutilise LE réglage de base publique du projet — on n'en invente pas un
    second."""
    from django.conf import settings
    base = (getattr(settings, 'PUBLIC_SITE_URL', '') or '').rstrip('/')
    chemin = f'/api/django/datarooms/public/{acces.token}/'
    return f'{base}{chemin}' if base else chemin


def marquer_consultation(acces, *, now=None):
    """NTDOC12 — Horodate la dernière consultation d'un viewer (best-effort).

    Écriture ciblée, jamais bloquante : une panne d'écriture ne doit pas
    empêcher le viewer de consulter la salle."""
    horodatage = now or timezone.now()
    try:
        AccesSalleDonnees.objects.filter(pk=acces.pk).update(
            derniere_consultation=horodatage)
        acces.derniere_consultation = horodatage
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        pass
    return acces


# ── NTDOC13 — Filigrane dynamique PAR VIEWER ────────────────────────────────

def watermark_label_viewer(acces, *, now=None):
    """NTDOC13 — Étiquette de filigrane propre à UN viewer.

    ``ged.services.watermark_label`` (GED21) produit une étiquette de SOCIÉTÉ,
    identique pour tout le monde : elle ne permet pas de remonter d'une fuite
    jusqu'à la personne. Ici l'étiquette porte le NOM et l'EMAIL du viewer plus
    l'horodatage de la consultation — deux viewers d'un même document reçoivent
    donc deux fichiers visuellement différents.

    Tout segment absent est omis proprement (un viewer sans email reste
    identifiable par son nom)."""
    horodatage = now or timezone.now()
    parties = ['CONFIDENTIEL']
    nom = (getattr(acces, 'nom', '') or '').strip()
    if nom:
        parties.append(nom)
    email = (getattr(acces, 'email', '') or '').strip()
    if email:
        parties.append(email)
    parties.append(horodatage.strftime('%Y-%m-%d %H:%M'))
    return ' — '.join(parties)


def document_servable_pour(acces, document_id):
    """NTDOC13 — Ligne d'appartenance VISIBLE de ce document dans la salle.

    Renvoie None si le document n'est pas dans la salle du viewer ou s'il y est
    masqué — jamais un oracle sur l'existence du document ailleurs dans la
    GED."""
    return SalleDeDonneesDocument.objects.select_related('document').filter(
        salle=acces.salle, document_id=document_id, visible=True).first()


def servir_document_viewer(acces, ligne, *, now=None):
    """NTDOC13 — Octets d'un document filigranés AU NOM DU VIEWER.

    Le filigrane est un RENDU À LA VOLÉE : le binaire stocké en GED n'est
    JAMAIS modifié (même contrat que `ged.apply_watermark`, GED21). Sans la lib
    de rendu, on dégrade proprement en servant l'original.

    Renvoie ``(octets, mime, nom_fichier, erreur)`` — ``erreur`` est une chaîne
    française quand rien n'est servable."""
    from apps.ged.services import _WATERMARK_IMAGE_MIMES, apply_watermark
    from apps.records.storage import fetch_attachment

    from .selectors import version_courante

    document = ligne.document
    version = version_courante(document)
    if version is None:
        return None, '', '', "Aucun fichier disponible pour ce document."
    data, err = fetch_attachment(version.file_key)
    if err:
        return None, '', '', "Document indisponible pour le moment."

    mime = version.mime or 'application/octet-stream'
    nom_fichier = (version.filename or document.nom or 'document').replace(
        '"', '')
    # Le filigrane PAR VIEWER est systématique dans une salle de données : la
    # salle existe précisément pour pouvoir tracer une fuite jusqu'à une
    # personne.
    data, filigrane = apply_watermark(
        data, mime, watermark_label_viewer(acces, now=now))
    if filigrane and mime in _WATERMARK_IMAGE_MIMES:
        mime = 'image/png'
    return data, mime, nom_fichier, ''


# ── NTDOC14 — Journal de consultation par salle et par viewer ───────────────

def reference_acces(acces):
    """NTDOC14 — Référence opaque d'un accès viewer, pour `JournalAcces`.

    Format ``"datarooms.acces:<id>"`` — c'est ce qui rend une entrée d'audit
    ATTRIBUABLE à une personne précise sans que la GED (couche basse) n'ait à
    connaître ce module."""
    return f'datarooms.acces:{acces.pk}'


def journaliser_consultation(acces, document, *, type_acces=None,
                             adresse_ip=None):
    """NTDOC14 — Journalise un accès PUBLIC à un document de salle.

    Réutilise `ged.services.journaliser_acces` (GED35) — aucun nouveau modèle
    de journal n'est créé. L'entrée est taguée avec la référence du VIEWER
    d'origine. Best-effort : l'audit ne bloque jamais une lecture."""
    from apps.ged.services import journaliser_acces

    try:
        return journaliser_acces(
            document, utilisateur=None, type_acces=type_acces,
            adresse_ip=adresse_ip, source_ref=reference_acces(acces))
    except Exception:  # pragma: no cover - défensif, jamais bloquant.
        return None


def _duree_secondes(depart, arrivee):
    """Durée entre deux horodatages, bornée et jamais négative."""
    if depart is None or arrivee is None:
        return 0
    return max(int((arrivee - depart).total_seconds()), 0)


#: Au-delà de ce délai entre deux accès, on considère que le viewer a quitté la
#: salle : le temps passé sur le dernier document n'est plus comptabilisable
#: (sans quoi un onglet laissé ouvert une nuit fausserait tout le rapport).
SEUIL_SESSION_SECONDES = 30 * 60


def journal_de_salle(salle):
    """NTDOC14 — Journal de consultation d'une salle (QuerySet, chronologique).

    Lit la GED via son sélecteur (`ged.selectors.journal_acces_for_company`) —
    jamais d'import de `ged.models`. Ne remonte QUE les accès dont la source
    est un viewer de CETTE salle."""
    from apps.ged.selectors import journal_acces_for_company

    from .selectors import acces_de_salle

    refs = [f'datarooms.acces:{pk}' for pk in
            acces_de_salle(salle).values_list('pk', flat=True)]
    if not refs:
        from apps.ged.models import JournalAcces
        return JournalAcces.objects.none()
    return journal_acces_for_company(
        salle.company, source_refs=refs).order_by('created_at', 'id')


def journal_detaille_salle(salle):
    """NTDOC14 — Journal enrichi : qui a vu quoi, quand, et combien de temps.

    Le « temps passé » n'est pas mesurable directement (aucun battement de cœur
    côté navigateur) : il est DÉRIVÉ de l'écart entre deux accès successifs du
    MÊME viewer, et volontairement mis à 0 au-delà de
    `SEUIL_SESSION_SECONDES` (dernier document d'une session, ou onglet
    abandonné). C'est une estimation assumée, jamais une mesure.

    Renvoie ``(lignes, resume)`` où ``lignes`` est la liste chronologique des
    entrées et ``resume`` le total de secondes par document."""
    from .selectors import acces_de_salle

    viewers = {f'datarooms.acces:{a.pk}': a for a in acces_de_salle(salle)}
    entrees = list(journal_de_salle(salle))

    # Accès successifs PAR VIEWER : l'écart alimente le temps passé.
    suivant_par_viewer = {}
    for entree in reversed(entrees):
        ref = entree.source_ref
        prochain = suivant_par_viewer.get(ref)
        entree._duree = 0
        if prochain is not None:
            ecart = _duree_secondes(entree.created_at, prochain.created_at)
            entree._duree = ecart if ecart <= SEUIL_SESSION_SECONDES else 0
        suivant_par_viewer[ref] = entree

    lignes = []
    resume = {}
    for entree in entrees:
        viewer = viewers.get(entree.source_ref)
        lignes.append({
            'date': entree.created_at,
            'viewer_nom': getattr(viewer, 'nom', '') or '',
            'viewer_email': getattr(viewer, 'email', '') or '',
            'document_id': entree.document_id,
            'document_nom': getattr(entree.document, 'nom', '') or '',
            'type_acces': entree.type_acces,
            'duree_secondes': entree._duree,
        })
        cle = entree.document_id
        agrege = resume.setdefault(
            cle, {'document_id': cle,
                  'document_nom': getattr(entree.document, 'nom', '') or '',
                  'consultations': 0, 'duree_secondes': 0})
        agrege['consultations'] += 1
        agrege['duree_secondes'] += entree._duree
    return lignes, list(resume.values())
