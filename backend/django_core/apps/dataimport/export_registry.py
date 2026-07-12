"""N97 — Registre des objets exportables (export configurable par société).

Distinct du module d'IMPORT (``services.py`` / ``views.py`` / ``exports_view.py``)
qu'il NE remplace PAS : c'est l'ossature de l'export & sauvegarde *configurable*
demandé par N97 (CSV / XLSX / JSON + bundle ZIP).

Chaque type d'objet déclare : son modèle, un libellé FR, et un ensemble de
champs SENSIBLES explicitement EXCLUS de l'export. L'export sérialise les
champs concrets locaux du modèle (via ``_meta``) MOINS cet ensemble — une
liste de refus, robuste à l'ajout de nouveaux champs.

RÈGLE NON NÉGOCIABLE : ``Produit.prix_achat`` (prix d'achat / marge) n'est
JAMAIS exporté. Il est listé dans ``SENSITIVE_FIELDS`` du produit et un test
garantit son absence de toute sortie (CSV, XLSX, JSON et ZIP).

Toutes les requêtes sont filtrées par société (``company``) côté serveur : un
utilisateur n'exporte que les enregistrements de SA société, jamais d'une autre.
"""
from collections import OrderedDict

from django.db import models

# Champs sensibles, jamais exportés, par (app_label, model_name).
# Centralise la garantie « aucun prix d'achat / marge ne sort ».
SENSITIVE_FIELDS = {
    ('stock', 'produit'): {'prix_achat'},
}


class ExportSpec:
    """Spécification d'un type d'objet exportable."""

    def __init__(self, key, label, model_path, order_by='id',
                 company_field='company'):
        self.key = key
        self.label = label
        self.model_path = model_path  # 'app_label.ModelName'
        self.order_by = order_by
        # Chemin de filtrage société. Direct ('company') pour la plupart ;
        # via le parent pour les lignes ('devis__company', 'facture__company').
        self.company_field = company_field
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from django.apps import apps as django_apps
            app_label, model_name = self.model_path.split('.')
            self._model = django_apps.get_model(app_label, model_name)
        return self._model

    @property
    def sensitive_fields(self):
        meta = self.model._meta
        return SENSITIVE_FIELDS.get((meta.app_label, meta.model_name), set())

    def field_names(self):
        """Champs concrets locaux à exporter (hors champs sensibles).

        On garde les colonnes simples + les clés étrangères (rendues via leur
        ``<champ>_id``). On exclut les relations inverses et M2M (un export plat
        n'aplatit pas les relations multivaluées — hors périmètre).
        """
        meta = self.model._meta
        sensitive = self.sensitive_fields
        names = []
        for f in meta.get_fields():
            # Relations inverses / M2M : ignorées (export plat).
            if f.auto_created and not f.concrete:
                continue
            if isinstance(f, models.ManyToManyField):
                continue
            if not getattr(f, 'concrete', False):
                continue
            name = f.name
            if name in sensitive:
                continue
            names.append(name)
        return names

    def header(self):
        """En-têtes de colonnes (FK rendues en ``<champ>_id``)."""
        meta = self.model._meta
        cols = []
        for name in self.field_names():
            f = meta.get_field(name)
            if isinstance(f, (models.ForeignKey, models.OneToOneField)):
                cols.append(f'{name}_id')
            else:
                cols.append(name)
        return cols

    def queryset(self, company):
        """Enregistrements de la société, jamais d'une autre.

        Le filtre société est TOUJOURS appliqué — directement via ``company``,
        ou via le parent (``devis__company`` / ``facture__company``) pour les
        lignes qui ne portent pas elles-mêmes le FK société.
        """
        qs = self.model.objects.all()
        qs = qs.filter(**{self.company_field: company})
        return qs.order_by(self.order_by)

    def rows(self, company):
        """Itère sur les lignes (listes de valeurs) prêtes à sérialiser."""
        meta = self.model._meta
        names = self.field_names()
        for obj in self.queryset(company).iterator():
            row = []
            for name in names:
                f = meta.get_field(name)
                if isinstance(f, (models.ForeignKey, models.OneToOneField)):
                    row.append(getattr(obj, f'{name}_id'))
                else:
                    row.append(getattr(obj, name))
            yield row


# Catalogue des objets exportables. Clés stables (identifiants anglais),
# libellés FR pour l'UI. Tous les modèles ci-dessous portent un FK ``company``,
# sauf les lignes (LigneDevis / LigneFacture) filtrées via leur parent.
_SPECS = [
    ExportSpec('clients', 'Clients', 'crm.Client'),
    ExportSpec('leads', 'Leads', 'crm.Lead'),
    ExportSpec('produits', 'Produits / Stock', 'stock.Produit'),
    ExportSpec('categories', 'Catégories produits', 'stock.Categorie'),
    ExportSpec('fournisseurs', 'Fournisseurs', 'stock.Fournisseur'),
    ExportSpec('mouvements_stock', 'Mouvements de stock', 'stock.MouvementStock'),
    ExportSpec('devis', 'Devis', 'ventes.Devis'),
    ExportSpec('lignes_devis', 'Lignes de devis', 'ventes.LigneDevis',
               order_by='id', company_field='devis__company'),
    ExportSpec('bons_commande', 'Bons de commande', 'ventes.BonCommande'),
    # ODX17 — Facture/LigneFacture/Paiement/Avoir ont déménagé de ``ventes``
    # vers ``facturation`` (même table physique, zéro SQL).
    ExportSpec('factures', 'Factures', 'facturation.Facture'),
    ExportSpec('lignes_facture', 'Lignes de facture', 'facturation.LigneFacture',
               order_by='id', company_field='facture__company'),
    ExportSpec('paiements', 'Paiements', 'facturation.Paiement'),
    ExportSpec('avoirs', 'Avoirs', 'facturation.Avoir'),
    ExportSpec('chantiers', 'Chantiers / Installations',
               'installations.Installation'),
    ExportSpec('interventions', 'Interventions', 'installations.Intervention'),
    ExportSpec('equipements', 'Équipements (parc)', 'sav.Equipement'),
    ExportSpec('tickets_sav', 'Tickets SAV', 'sav.Ticket'),
]

REGISTRY = OrderedDict((s.key, s) for s in _SPECS)


def available_objects():
    """Liste (key, label) des objets exportables — pour l'UI et les défauts."""
    return [{'key': s.key, 'label': s.label} for s in REGISTRY.values()]


# Sélection par défaut d'une « sauvegarde complète » : tous les objets.
DEFAULT_OBJECTS = list(REGISTRY.keys())


def declared_import_specs(company=None):
    """ARC32 — cibles d'IMPORT déclarées par les manifestes plateforme.

    Pont vers le registre (``core.platform.import_specs``) : chaque app
    propriétaire déclare ses cibles importables dans son ``apps/<x>/platform.py``
    (surface ``import_specs``) — la même source de vérité que
    ``dataimport.services.TARGETS`` unionne. Renvoie l'ensemble des clés
    déclarées (gaté société quand ``company`` est fourni : un module désactivé
    disparaît de la liste, comme les autres surfaces ARC29-34).

    Distinct de ``REGISTRY`` (le catalogue d'EXPORT, 17 objets richement typés
    avec chemin de modèle + champ société pour la sérialisation) : cet export
    reste piloté par ``REGISTRY``. Cette fonction expose la face IMPORT du même
    registre plateforme, sans dupliquer les mappings d'en-têtes (qui restent
    dans ``dataimport.services.FIELD_MAPS``). Robuste au registre indisponible
    (renvoie alors un ensemble vide, jamais d'exception)."""
    try:
        from core import platform
        return set(platform.import_specs(company=company))
    except Exception:  # pragma: no cover - registre indisponible
        return set()
