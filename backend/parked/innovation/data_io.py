"""NTIDE24 — sérialisation JSON des idées (dev/test uniquement).

Format volontairement PLAT (liste de dict), un seul format partagé par la
commande d'export (``export_ideas``) et celle d'import (``import_ideas``) —
jamais deux formats à maintenir en synchro. ``auteur``/``company`` sont
sérialisés par référence STABLE (``username``/``slug``), jamais par id
numérique (les ids diffèrent d'un environnement à l'autre).

L'import est IDEMPOTENT : rejoué sur le même fichier, il ne duplique jamais
une idée déjà présente pour le triplet (titre, company, auteur) — c'est la
même règle qui rend ``manage.py seed_catalogue`` sûr à ré-exécuter.
"""
from dataclasses import dataclass, field

# Champs copiés tels quels entre le modèle ``Idee`` et le JSON (pas de
# transformation) — ``company``/``auteur``/``created_at`` sont sérialisés à
# part (référence stable / lecture seule).
IDEE_FIELDS = (
    'titre', 'description', 'contexte', 'statut', 'votes_count',
    'linked_type', 'linked_id', 'draft', 'archived',
)


def idee_to_dict(idee):
    """Une idée → dict JSON-sérialisable (NTIDE24)."""
    data = {f: getattr(idee, f) for f in IDEE_FIELDS}
    data['company'] = idee.company.slug
    data['auteur'] = getattr(idee.auteur, 'username', None) if idee.auteur_id else None
    data['created_at'] = idee.created_at.isoformat() if idee.created_at else None
    return data


def export_ideas(company=None):
    """Liste de dicts (NTIDE24) — ``company`` (instance) filtre, sinon toutes
    les sociétés (usage dev/test uniquement — jamais depuis une route HTTP)."""
    from .models import Idee

    qs = Idee.objects.select_related('company', 'auteur').all()
    if company is not None:
        qs = qs.filter(company=company)
    return [idee_to_dict(i) for i in qs.order_by('company_id', 'id')]


@dataclass
class ImportResult:
    created: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)


def import_ideas(records, *, company=None):
    """Réimporte ``records`` (liste de dicts au format ``idee_to_dict``).

    ``company`` (instance, optionnelle) SURCHARGE le ``record['company']`` de
    chaque enregistrement — permet de rejouer un export d'une société DANS une
    autre (fixtures dev/démo) ; sans surcharge, chaque enregistrement résout sa
    propre société via son slug.

    Idempotent : une idée déjà présente pour (titre, company, auteur) est
    comptée dans ``skipped``, jamais recréée/dupliquée. Un enregistrement dont
    la société est introuvable (ou absente sans ``--company``) est journalisé
    dans ``errors`` et sauté — n'interrompt jamais le reste de l'import."""
    from django.contrib.auth import get_user_model

    from authentication.models import Company

    from .models import Idee

    User = get_user_model()
    result = ImportResult()
    company_cache = {}

    for record in records:
        target_company = company
        if target_company is None:
            slug = record.get('company')
            if not slug:
                result.errors.append(
                    f"Idée « {record.get('titre')} » : aucune société "
                    "(champ 'company' vide et --company non fourni).")
                continue
            if slug not in company_cache:
                company_cache[slug] = Company.objects.filter(slug=slug).first()
            target_company = company_cache[slug]
            if target_company is None:
                result.errors.append(f'Société introuvable : {slug}')
                continue

        auteur = None
        auteur_username = record.get('auteur')
        if auteur_username:
            auteur = User.objects.filter(
                company=target_company, username=auteur_username).first()

        titre = record.get('titre') or ''
        deja_present = Idee.objects.filter(
            company=target_company, titre=titre, auteur=auteur).exists()
        if deja_present:
            result.skipped += 1
            continue

        Idee.objects.create(
            company=target_company,
            auteur=auteur,
            titre=titre,
            description=record.get('description') or '',
            contexte=record.get('contexte') or '',
            statut=record.get('statut') or Idee.Statut.OUVERT,
            votes_count=record.get('votes_count') or 0,
            linked_type=record.get('linked_type') or '',
            linked_id=record.get('linked_id'),
            draft=bool(record.get('draft')),
            archived=bool(record.get('archived')),
        )
        result.created += 1
    return result
