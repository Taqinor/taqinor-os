"""Écritures / orchestration de la Base de connaissances.

La société est TOUJOURS fournie par l'appelant (résolue côté serveur depuis
``request.user.company``) — jamais lue d'un corps de requête. Le numéro de
version est incrémental PAR article et calculé côté serveur (max(version)+1,
sous verrou — JAMAIS count()+1, qui collisionne sous concurrence).
"""
import logging

from django.db import transaction

from core.pdf import render_pdf

from .models import (
    KbArticle,
    KbArticleChunk,
    KbArticleVersion,
    KbFavori,
    KbLecture,
    KbRechercheVide,
    PartageArticleKb,
)

logger = logging.getLogger(__name__)


def marquer_lu(article, *, utilisateur):
    """Enregistre (idempotemment) la LECTURE d'un article par un utilisateur.

    Une seule ligne par (article, utilisateur) : un premier appel crée la ligne,
    les suivants rafraîchissent ``lu_le`` (``auto_now``) sans dupliquer. La
    société est forcée à celle de l'article (jamais du corps de requête) et
    l'utilisateur agissant est fourni par la vue (jamais du corps). Renvoie le
    couple ``(lecture, created)``.
    """
    with transaction.atomic():
        lecture, created = KbLecture.objects.get_or_create(
            article=article,
            utilisateur=utilisateur,
            defaults={'company': article.company},
        )
        if not created:
            # Rafraîchit l'horodatage de dernière lecture (auto_now) et
            # ré-aligne la société par sécurité si l'article a migré.
            lecture.company = article.company
            lecture.save(update_fields=['company', 'lu_le'])
    return lecture, created


def snapshot_article(article, *, auteur=None):
    """Fige titre + contenu de l'article dans une nouvelle ligne de version.

    Le numéro est calculé côté serveur (dernière version + 1) sous verrou, et la
    société est forcée à celle de l'article (jamais du corps de requête). Idempotent
    par appel : chaque appel crée exactement une version, sans toucher l'article.
    """
    with transaction.atomic():
        last = (KbArticleVersion.objects
                .select_for_update()
                .filter(article=article)
                .order_by('-version')
                .first())
        next_version = (last.version + 1) if last else 1
        return KbArticleVersion.objects.create(
            company=article.company,
            article=article,
            version=next_version,
            titre=article.titre,
            contenu=article.corps,
            auteur=auteur,
        )


# ── XKB12 — Gabarits d'articles utilisateur ─────────────────────────────────

def creer_depuis_gabarit(gabarit, *, auteur, company):
    """XKB12 — Crée un nouvel article BROUILLON pré-rempli depuis un gabarit.

    Copie titre + corps + format + catégorie/tags du gabarit ; le nouvel
    article N'EST PAS lui-même un gabarit (``est_gabarit=False``). La société
    et l'auteur sont fournis par l'appelant (résolus côté serveur, jamais du
    corps de requête) — jamais celle du gabarit si elle diffère (protège
    contre un gabarit d'une autre société, même si ce cas est déjà bloqué en
    amont par le scoping du queryset appelant).
    """
    return KbArticle.objects.create(
        company=company,
        titre=gabarit.titre,
        corps=gabarit.corps,
        corps_format=gabarit.corps_format,
        categorie=gabarit.categorie,
        tags=gabarit.tags,
        statut=KbArticle.Statut.BROUILLON,
        auteur=auteur,
        est_gabarit=False,
    )


# ── XKB16 — Statistiques KB & recherches infructueuses ──────────────────────

def incrementer_vues(article):
    """XKB16 — Incrémente le compteur de vues (DISTINCT de KbLecture — chaque
    consultation compte, même une relecture par la même personne).

    Utilise une expression F() pour éviter une race condition en écriture
    concurrente (pas de read-modify-write applicatif).
    """
    from django.db.models import F
    KbArticle.objects.filter(id=article.id).update(vues=F('vues') + 1)
    article.refresh_from_db(fields=['vues'])
    return article.vues


# ── XSAV22 — Déflection KB sur le portail client ────────────────────────────

def enregistrer_consultation_portail(company, article_id):
    """XSAV22 — Incrémente le compteur DÉDIÉ ``consultations_portail_ticket``
    quand un client consulte cet article depuis le formulaire d'ouverture de
    ticket du portail (distinct de ``incrementer_vues``, qui compte toute
    consultation interne).

    Point d'ÉCRITURE cross-app (``apps.portail``/``apps.compta``, frontière
    CLAUDE.md) : l'appelant fournit un ``article_id`` OPAQUE, jamais l'objet
    ORM ni un import de ``apps.kb.models`` — résolu ici, scopé à ``company``
    (aucune fuite cross-tenant possible). No-op silencieux (renvoie ``False``,
    ne lève jamais) si l'article n'existe pas / n'appartient pas à la société
    / n'est pas flagué ``visible_portail`` (on ne compte que ce qui est
    effectivement montré sur le portail)."""
    from django.db.models import F
    updated = KbArticle.objects.filter(
        id=article_id, company=company, visible_portail=True,
    ).update(consultations_portail_ticket=F('consultations_portail_ticket') + 1)
    return bool(updated)


def journaliser_recherche_vide(company, terme, *, utilisateur=None):
    """XKB16 — Journalise une recherche ``?search=`` SANS RÉSULTAT.

    Société posée côté serveur ; ``terme`` tronqué au ``max_length`` du champ
    pour ne jamais lever sur une entrée trop longue. Jamais bloquant.
    """
    terme = (terme or '').strip()
    if not terme:
        return None
    try:
        return KbRechercheVide.objects.create(
            company=company, terme=terme[:255], utilisateur=utilisateur)
    except Exception:  # pragma: no cover - défensif : jamais bloquer la recherche.
        logger.warning('journaliser_recherche_vide: échec', exc_info=True)
        return None


# ── XKB15 — Favoris (toggle) ─────────────────────────────────────────────────

def toggler_favori(article, *, utilisateur):
    """XKB15 — Favorise/défavorise ``article`` pour ``utilisateur`` (toggle).

    Crée la ligne si absente, la supprime si présente. Société posée côté
    serveur (celle de l'article). Renvoie ``(favori_actif, favori_ou_None)``.
    """
    with transaction.atomic():
        favori = KbFavori.objects.filter(
            article=article, utilisateur=utilisateur).first()
        if favori is not None:
            favori.delete()
            return False, None
        favori = KbFavori.objects.create(
            company=article.company, article=article, utilisateur=utilisateur)
        return True, favori


# ── XKB14 — Vérification, péremption & verrou ───────────────────────────────

def verifier_article(article, *, verificateur, horizon_jours=90):
    """XKB14 — Marque l'article VÉRIFIÉ par ``verificateur`` jusqu'à
    ``horizon_jours`` (défaut 90 j — l'appelant peut passer 7/30/90 ou tout
    autre horizon libre). Renvoie l'article sauvegardé.
    """
    from django.utils import timezone
    article.verifie_par = verificateur
    article.verifie_jusqua = timezone.now() + timezone.timedelta(
        days=horizon_jours)
    article.save(update_fields=['verifie_par', 'verifie_jusqua'])
    return article


def relancer_revues_perimees(company=None):
    """XKB14 — Notifie le vérificateur des articles PÉRIMÉS (re-revue due).

    Best-effort et jamais bloquant. ``company`` restreint à une seule société
    (sweep par société) ; ``None`` balaie toutes les sociétés actives.
    Renvoie le nombre de notifications émises.
    """
    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    from . import selectors

    companies = [company] if company is not None else _companies_actives()
    total = 0
    for co in companies:
        for entry in selectors.rapport_peremption(co):
            try:
                article = KbArticle.objects.filter(id=entry['id']).first()
                if article is None or not article.verifie_par_id:
                    continue
                notify(
                    article.verifie_par, EventType.DIGEST,
                    f'Re-revue due : {article.titre}',
                    body="Cet article est périmé et nécessite une re-revue.",
                    link=f'/kb/articles/{article.id}',
                    company=co,
                )
                total += 1
            except Exception:  # pragma: no cover - défensif
                logger.warning(
                    'relancer_revues_perimees: article %s échoué',
                    entry.get('id'), exc_info=True)
    return total


def _companies_actives():
    try:
        from authentication.models import Company
        return list(Company.objects.filter(actif=True))
    except Exception:  # pragma: no cover
        return []


# ── XKB17 — Export/import & sauvegarde (PDF/Markdown/ZIP société) ──────────

def article_to_markdown(article):
    """XKB17 — Rend un article en Markdown fidèle (titre + métadonnées + corps).

    Fonctionne pour un article ``texte`` (corps encapsulé tel quel) ou
    ``markdown`` (corps déjà Markdown). Renvoie une chaîne str prête à écrire
    dans un fichier ``.md``.
    """
    entete = f'# {article.titre}\n\n'
    meta = []
    if article.categorie:
        meta.append(f'Catégorie: {article.categorie}')
    if article.tags:
        meta.append(f'Tags: {article.tags}')
    meta.append(f'Statut: {article.statut}')
    bloc_meta = ('\n'.join(f'*{m}*' for m in meta) + '\n\n') if meta else ''
    return entete + bloc_meta + (article.corps or '')


def article_to_pdf(article):
    """XKB17 — Rend un article en PDF (mise en page d'impression propre).

    Utilise EXCLUSIVEMENT le service partagé ``core.pdf.render_pdf`` (ARC12 —
    plomberie WeasyPrint centralisée ; JAMAIS le moteur devis premium — rule
    #4 : `/proposal` reste l'unique chemin des PDF de devis client, sans
    rapport avec cet export documentaire interne). Aucun statut n'est modifié
    par cet export (lecture seule). Renvoie les octets PDF.
    """
    titre = (article.titre or 'Article').replace('<', '&lt;').replace('>', '&gt;')
    corps_html = (article.corps or '').replace('\n', '<br>')
    html_str = (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
        "<style>"
        "body{font-family:sans-serif;font-size:11pt;color:#1a1a1a;"
        "margin:2cm;line-height:1.5;}"
        "h1{font-size:16pt;border-bottom:2px solid #2b5cab;padding-bottom:6px;}"
        ".meta{color:#666;font-size:9pt;margin-bottom:12px;}"
        "</style></head><body>"
        f"<h1>{titre}</h1>"
        f"<div class='meta'>{article.categorie or ''} · {article.get_statut_display()}</div>"
        f"<div class='corps'>{corps_html}</div>"
        "</body></html>"
    )
    return render_pdf(html=html_str)


def importer_markdown(contenu, *, company, auteur=None):
    """XKB17 — Importe un fichier Markdown comme NOUVEL article brouillon.

    Le premier titre ATX (``# Titre``) du contenu devient le titre de
    l'article ; à défaut le titre est ``'Article importé'``. Le contenu entier
    est stocké dans ``corps`` avec ``corps_format='markdown'``. Société et
    auteur posés côté serveur (jamais du corps de requête).
    """
    contenu = contenu or ''
    titre = 'Article importé'
    for ligne in contenu.splitlines():
        ligne = ligne.strip()
        if ligne.startswith('# '):
            titre = ligne[2:].strip() or titre
            break
    return KbArticle.objects.create(
        company=company,
        titre=titre[:255],
        corps=contenu,
        corps_format=KbArticle.CorpsFormat.MARKDOWN,
        statut=KbArticle.Statut.BROUILLON,
        auteur=auteur,
    )


# ── XKB21 — Dupliquer un article (avec ou sans sous-articles) ──────────────

def dupliquer_article(article, *, auteur, company, avec_sous_articles=False):
    """XKB21 — Duplique ``article`` en une copie BROUILLON indépendante.

    Copie le contenu COURANT (titre, corps/format, catégorie/tags,
    visibilité) ; la copie est TOUJOURS ``brouillon`` (jamais publiée
    automatiquement) et n'est PAS elle-même un gabarit ni verrouillée, même
    si la source l'était. ``parent`` de la copie reste celui de la source
    (même emplacement dans l'arbre) — un ``deplacer`` explicite la
    replace ensuite si besoin.

    ``avec_sous_articles=True`` clone RÉCURSIVEMENT tout le sous-arbre : les
    enfants de la source sont dupliqués et rattachés à la NOUVELLE copie
    (jamais à l'original), préservant la hiérarchie relative. Société et
    auteur posés côté serveur (jamais du corps de requête) ; la copie est
    toujours de la MÊME société que la source (jamais celle d'un appelant
    d'une autre société, même si le scoping amont l'empêche déjà).

    Renvoie l'article copie (racine de la duplication).
    """
    with transaction.atomic():
        copie = KbArticle.objects.create(
            company=company,
            titre=f'{article.titre} (copie)',
            corps=article.corps,
            corps_format=article.corps_format,
            categorie=article.categorie,
            tags=article.tags,
            statut=KbArticle.Statut.BROUILLON,
            visibilite=article.visibilite,
            auteur=auteur,
            parent=article.parent,
            ordre=article.ordre,
            est_gabarit=False,
            est_verrouille=False,
        )
        if avec_sous_articles:
            for enfant in article.enfants.all().order_by('ordre', 'id'):
                _dupliquer_sous_arbre(
                    enfant, nouveau_parent=copie, auteur=auteur,
                    company=company)
    return copie


def _dupliquer_sous_arbre(article, *, nouveau_parent, auteur, company):
    """XKB21 — Clone récursivement UN sous-article sous ``nouveau_parent``.

    Fonction interne de ``dupliquer_article`` (avec_sous_articles=True) : ne
    duplique JAMAIS vers l'original — toujours sous la copie."""
    copie = KbArticle.objects.create(
        company=company,
        titre=article.titre,
        corps=article.corps,
        corps_format=article.corps_format,
        categorie=article.categorie,
        tags=article.tags,
        statut=KbArticle.Statut.BROUILLON,
        visibilite=article.visibilite,
        auteur=auteur,
        parent=nouveau_parent,
        ordre=article.ordre,
        est_gabarit=False,
        est_verrouille=False,
    )
    for enfant in article.enfants.all().order_by('ordre', 'id'):
        _dupliquer_sous_arbre(
            enfant, nouveau_parent=copie, auteur=auteur, company=company)
    return copie


# ── XKB18 — Articles multilingues FR/AR/EN ──────────────────────────────────

def creer_traduction(article_source, *, langue, auteur=None, company):
    """XKB18 — Crée la traduction ``langue`` d'``article_source``.

    Copie titre + corps + catégorie/tags de la source, marque le nouvel
    article de la langue cible et le rattache à la source
    (``traduction_de``). Statut ``brouillon`` (la traduction démarre à
    relire, jamais publiée automatiquement). Société posée côté serveur
    (jamais du corps de requête) et forcée à celle de la source.
    """
    return KbArticle.objects.create(
        company=company,
        titre=article_source.titre,
        corps=article_source.corps,
        corps_format=article_source.corps_format,
        categorie=article_source.categorie,
        tags=article_source.tags,
        statut=KbArticle.Statut.BROUILLON,
        auteur=auteur,
        langue=langue,
        traduction_de=article_source,
    )


def marquer_traductions_perimees(article):
    """XKB18 — Marque PÉRIMÉES toutes les traductions d'``article`` quand
    celui-ci (une source) vient d'être modifié.

    Appelé depuis la mise à jour de l'article (``perform_update``) : si
    ``article`` porte des traductions (``.traductions``), chacune passe
    ``traduction_perimee=True`` — l'indicateur « traduction à mettre à jour »
    de KB18. N'affecte jamais l'article source lui-même. Best-effort et
    idempotent (un ``update()`` en masse, pas de N+1).
    """
    article.traductions.update(traduction_perimee=True)


# ── XKB19 — Partage web public d'article (lien tokenisé) ────────────────────

PARTAGE_OK = 'ok'
PARTAGE_INTROUVABLE = 'introuvable'  # jeton inconnu ou révoqué → 404
PARTAGE_EXPIRE = 'expire'            # expiré → 410


def resolve_partage_public(token):
    """XKB19 — Résout un partage public d'article DEPUIS le seul jeton.

    Calqué sur ``ged.services.resolve_partage_public`` (GED20) : aucune
    identité/société n'est jamais lue de la requête, tout est résolu à partir
    du ``token`` (qui ne référence qu'un seul article d'une seule société).
    Renvoie ``(statut, partage_ou_None)`` :

      - PARTAGE_INTROUVABLE : jeton inconnu OU partage dépublié
        (``actif=False``) → 404, indistinct (pas de fuite « ce jeton a
        existé »).
      - PARTAGE_EXPIRE : partage expiré (``expires_at`` dépassé) → 410.
      - PARTAGE_OK : accès autorisé, ``partage.article`` est servable.
    """
    partage = (PartageArticleKb.objects
               .select_related('article', 'company')
               .filter(token=token)
               .first())
    if partage is None or not partage.actif:
        return PARTAGE_INTROUVABLE, None
    if partage.is_expired:
        return PARTAGE_EXPIRE, partage
    return PARTAGE_OK, partage


def consume_partage_consultation(partage):
    """XKB19 — Incrémente atomiquement le compteur de consultations publiques
    (F-expression : pas de race condition en écriture concurrente)."""
    from django.db.models import F
    PartageArticleKb.objects.filter(id=partage.id).update(
        consultations=F('consultations') + 1)


def exporter_zip_company(company):
    """XKB17 — Exporte TOUS les articles d'une société (+ pièces jointes) en ZIP.

    Contrôle des données loi 09-08 : sauvegarde/migration scopée STRICTEMENT à
    ``company`` — jamais un article ni une pièce jointe d'une autre société.
    Chaque article devient ``articles/<id>-<titre>.md`` ; ses pièces jointes
    (``records.Attachment`` génériques, content-type ``kb.kbarticle``) sont
    récupérées depuis MinIO (``records.storage.fetch_attachment`` — import
    fonction-local, ``records`` est une app fondation) et rangées sous
    ``articles/<id>-pieces-jointes/<filename>``. Renvoie les octets du ZIP.
    """
    import io
    import zipfile

    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.records.storage import fetch_attachment

    buffer = io.BytesIO()
    ct = ContentType.objects.get_for_model(KbArticle)
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for article in KbArticle.objects.filter(company=company).order_by('id'):
            slug = ''.join(
                c if c.isalnum() else '-' for c in (article.titre or '')
            ).strip('-') or 'article'
            zf.writestr(
                f'articles/{article.id}-{slug}.md',
                article_to_markdown(article))
            pjs = Attachment.objects.filter(
                content_type=ct, object_id=article.id, company=company)
            for pj in pjs:
                data, err = fetch_attachment(pj.file_key)
                if err or data is None:
                    continue
                zf.writestr(
                    f'articles/{article.id}-pieces-jointes/{pj.filename}',
                    data)
    return buffer.getvalue()


# ── XKB7 — Relance des non-lecteurs de lecture obligatoire ─────────────────

def relancer_lectures_obligatoires(company=None):
    """Relance (notify()) tous les non-lecteurs de lecture obligatoire.

    Best-effort et jamais bloquant : une notification qui échoue n'empêche pas
    les suivantes. ``company`` restreint à une seule société (sweep par
    société) ; ``None`` balaie toutes les sociétés actives. Import
    fonction-local des apps notifications (lecture de service, jamais de
    models/views directement — voir CLAUDE.md). Renvoie le nombre de relances
    émises.
    """
    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    from . import selectors
    from .models import KbArticle, KbLectureObligatoire

    qs = KbLectureObligatoire.objects.select_related('article')
    if company is not None:
        qs = qs.filter(company=company)
    total = 0
    for assignation in qs:
        article = assignation.article
        if article.statut != KbArticle.Statut.PUBLIE:
            continue
        try:
            deja_lu = set(
                KbLecture.objects.filter(article=article)
                .values_list('utilisateur_id', flat=True))
            for user in selectors.assignees_for_assignation(assignation):
                if user.id in deja_lu:
                    continue
                try:
                    notify(
                        user, EventType.DIGEST,
                        f'Lecture obligatoire : {article.titre}',
                        body="Cet article requiert votre lecture.",
                        link=f'/kb/articles/{article.id}',
                        company=assignation.company,
                    )
                    total += 1
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'relancer_lectures_obligatoires: notify échoué',
                        exc_info=True)
        except Exception:  # pragma: no cover - défensif
            logger.warning(
                'relancer_lectures_obligatoires: assignation %s échouée',
                getattr(assignation, 'pk', None), exc_info=True)
    return total


# ── KB6 — Source de contenu pour le RAG/DocQA (FG352, pgvector, no-op sans clé) ──

def indexer_article_kb(article):
    """KB6 — (Ré)indexe les fragments RAG/DocQA d'un article (no-op sans clé).

    Rend l'article de la base de connaissances exploitable par le pipeline
    RAG/DocQA déjà construit dans ``apps.ged`` (FG352). On RÉUTILISE les services
    de la GED via un import FONCTION-LOCAL — une lecture inter-app d'un *service*
    (autorisée par la frontière inter-app : on ne touche jamais aux
    ``models``/``views`` de la GED) plutôt que de réimplémenter le découpage ou
    l'embedding :

      * ``ged.services.embedding_enabled()`` — la MÊME porte clé-gated ;
      * ``ged.services.chunk_text(...)`` — le MÊME découpage chevauchant ;
      * ``ged.services.compute_embedding(...)`` — le MÊME provider d'embedding.

    Le texte indexé concatène le titre et le corps de l'article. Chaque fragment
    est stocké dans :class:`KbArticleChunk` — même type pgvector et même
    dimension que ``ged.DocumentChunk`` (pas un second magasin vectoriel).

    KEY-GATED : sans clé d'embedding, c'est un no-op TOTAL — aucun fragment écrit,
    aucun appel réseau, aucun coût, renvoie 0. Idempotent : remplace les fragments
    existants de l'article. Ne lève jamais (l'indexation ne doit pas casser une
    écriture documentaire). La company de chaque fragment est posée côté serveur
    (celle de l'article), jamais lue d'un corps de requête.

    Renvoie le nombre de fragments embeddés et stockés.
    """
    # Import FONCTION-LOCAL : lecture inter-app d'un SERVICE de la GED
    # (jamais ses models/views) — évite aussi tout cycle d'import au chargement.
    from apps.ged import services as ged_services

    if not ged_services.embedding_enabled():
        return 0
    texte = f'{article.titre}\n{article.corps or ""}'.strip()
    fragments = ged_services.chunk_text(texte)
    if not fragments:
        # Plus aucun contenu indexable : purge les anciens fragments.
        KbArticleChunk.objects.filter(article=article).delete()
        return 0
    lignes = []
    for idx, fragment in enumerate(fragments):
        try:
            vec = ged_services.compute_embedding(fragment)
        except Exception:  # pragma: no cover - robustesse : jamais bloquer.
            vec = None
        if vec is None:
            continue
        lignes.append(KbArticleChunk(
            company=article.company, article=article,
            chunk_index=idx, texte=fragment, embedding=vec))
    with transaction.atomic():
        KbArticleChunk.objects.filter(article=article).delete()
        if lignes:
            KbArticleChunk.objects.bulk_create(lignes)
    return len(lignes)
