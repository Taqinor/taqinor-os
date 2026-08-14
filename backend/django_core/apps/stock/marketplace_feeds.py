"""NTRET20 — Flux produits pour places de marché (Avito, Google Shopping).

Génère le FICHIER prêt à importer / à pointer en flux URL. AUCUNE intégration
API poussée : ouvrir un compte marchand Avito ou Google Merchant est une étape
manuelle du fondateur (la tâche est marquée GATED pour cette raison). Ce module
ne fait donc jamais d'appel réseau et n'a besoin d'aucune clé.

RÈGLES DURES :
  * ``prix_achat`` n'entre JAMAIS dans un flux (c'est un flux PUBLIC) ;
  * seuls les produits marqués vendables en ligne sont exportés — le drapeau
    vit dans ``ecommerce_connect.ProduitSync.vendable_en_ligne`` (NTRET18/19),
    lu ici SANS importer les modèles de cette app (résolution paresseuse par
    ``apps.get_model``). Aucune synchro déclarée = flux VIDE, jamais « tout le
    catalogue » exporté par accident ;
  * pas de dépendance ajoutée : CSV via la stdlib, XML assemblé à la main.
"""
import csv
import io
from decimal import Decimal

FORMAT_AVITO = 'avito'
FORMAT_GOOGLE = 'google_shopping'
FORMATS = (FORMAT_AVITO, FORMAT_GOOGLE)

DEVISE = 'MAD'


def _esc_xml(value):
    return (str(value if value is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def produits_vendables_en_ligne(company):
    """Produits explicitement marqués vendables en ligne, ou liste VIDE.

    Le drapeau ``vendable_en_ligne`` appartient à ``ecommerce_connect``
    (``ProduitSync``, NTRET18/19). On le lit par ``apps.get_model`` — jamais
    un import de ses modèles (frontière inter-apps). App absente ou aucune
    ligne de synchro : le flux est VIDE. C'est volontaire : un flux PUBLIC ne
    doit jamais partir « tout coché » par défaut.
    """
    from django.apps import apps as django_apps

    from .models import Produit

    try:
        produit_sync = django_apps.get_model(
            'ecommerce_connect', 'ProduitSync')
    except Exception:  # noqa: BLE001 — app absente : aucun produit publiable
        return Produit.objects.none()

    ids = set(produit_sync.objects
              .filter(company=company, vendable_en_ligne=True)
              .values_list('produit_id', flat=True))
    if not ids:
        return Produit.objects.none()
    return (Produit.objects
            .filter(company=company, id__in=ids, is_archived=False)
            .select_related('categorie')
            .order_by('nom', 'id'))


def _lignes_flux(company):
    """Données communes aux deux formats — jamais ``prix_achat``."""
    from .selectors_negoce import atp_produit

    lignes = []
    for produit in produits_vendables_en_ligne(company):
        atp = atp_produit(company, produit)
        lignes.append({
            'id': produit.id,
            'sku': produit.sku or f'PRODUIT-{produit.id}',
            'titre': produit.nom,
            'description': (produit.description or produit.nom or ''),
            'marque': produit.marque or '',
            'categorie': getattr(produit.categorie, 'nom', '') or '',
            'prix_ttc': _dec(produit.prix_vente),
            'disponible': atp['disponible_maintenant'],
            'image_id': produit.photo_id,
        })
    return lignes


def flux_avito_csv(company):
    """Flux Avito : CSV UTF-8 (séparateur virgule, en-tête explicite)."""
    tampon = io.StringIO()
    writer = csv.writer(tampon, lineterminator='\n')
    writer.writerow([
        'sku', 'titre', 'description', 'prix', 'devise', 'categorie',
        'marque', 'quantite_disponible',
    ])
    for ligne in _lignes_flux(company):
        writer.writerow([
            ligne['sku'], ligne['titre'], ligne['description'],
            f"{ligne['prix_ttc']}", DEVISE, ligne['categorie'],
            ligne['marque'], ligne['disponible'],
        ])
    return tampon.getvalue()


def flux_google_shopping_xml(company, *, titre_flux='Catalogue',
                             lien_boutique=''):
    """Flux Google Shopping : RSS 2.0 + espace de noms ``g:`` (spec publique).

    ``titre_flux``/``lien_boutique`` viennent de l'APPELANT (profil de la
    société) — aucune marque n'est écrite en dur : le flux part chez un tiers.
    """
    articles = []
    for ligne in _lignes_flux(company):
        disponibilite = ('in stock' if ligne['disponible'] > 0
                         else 'out of stock')
        articles.append(
            '<item>'
            f'<g:id>{_esc_xml(ligne["sku"])}</g:id>'
            f'<title>{_esc_xml(ligne["titre"])}</title>'
            f'<description>{_esc_xml(ligne["description"])}</description>'
            f'<g:price>{_esc_xml(ligne["prix_ttc"])} {DEVISE}</g:price>'
            f'<g:availability>{disponibilite}</g:availability>'
            f'<g:condition>new</g:condition>'
            f'<g:brand>{_esc_xml(ligne["marque"])}</g:brand>'
            f'<g:product_type>{_esc_xml(ligne["categorie"])}</g:product_type>'
            '</item>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">'
        '<channel>'
        f'<title>{_esc_xml(titre_flux)}</title>'
        f'<link>{_esc_xml(lien_boutique)}</link>'
        f'<description>{_esc_xml(titre_flux)}</description>'
        f'{"".join(articles)}'
        '</channel></rss>'
    )


def generer_flux(company, cible, *, titre_flux='Catalogue',
                 lien_boutique=''):
    """Flux du format demandé : ``(contenu, content_type, nom_fichier)``."""
    if cible == FORMAT_AVITO:
        return (flux_avito_csv(company), 'text/csv; charset=utf-8',
                'flux-avito.csv')
    if cible == FORMAT_GOOGLE:
        return (
            flux_google_shopping_xml(
                company, titre_flux=titre_flux, lien_boutique=lien_boutique),
            'application/xml; charset=utf-8', 'flux-google-shopping.xml')
    raise ValueError(
        'Format inconnu : attendu « avito » ou « google_shopping ».')
