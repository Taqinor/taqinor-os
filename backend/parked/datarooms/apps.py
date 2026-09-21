from django.apps import AppConfig


class DataroomsConfig(AppConfig):
    """Groupe NTDOC (P2) — Salles de données sécurisées (data rooms).

    Une SALLE regroupe plusieurs documents GED déjà existants (levée de fonds,
    due diligence, appel d'offres) et les ouvre à des VIEWERS NOMMÉS, chacun
    avec son propre lien, sa propre expiration et son propre filigrane. C'est
    la brique que ``ged.PartageGed`` ne couvre pas : celui-ci est un lien PAR
    DOCUMENT, sans notion de collection ni de traçabilité par personne.

    Frontière avec ``ged`` : cette app ne DUPLIQUE aucun document et n'importe
    jamais ``ged.models`` — elle référence ``ged.Document`` par string-FK et lit
    la GED via ``apps.ged.selectors`` uniquement.

    Multi-société : chaque modèle hérite de ``core.models.TenantModel`` (FK
    ``company`` posée côté serveur, jamais lue du corps de requête).

    ODX2 — ``module_manifest`` collecté génériquement par
    ``core.modules.collect_manifests``.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.datarooms'
    verbose_name = 'Salles de données'

    module_manifest = {
        'key': 'datarooms',
        # ERP transverse (toute PME finit par ouvrir une due diligence ou un
        # dossier d'appel d'offres) — jamais un vertical.
        'sku': 'generic',
        'label': 'Salles de données',
        'icone': 'folder-lock',
        # La salle n'a aucun sens sans la GED : elle ne fait qu'y pointer.
        'depends': ['ged'],
        'description': (
            "Salles de données sécurisées : une collection thématique de "
            "documents GED ouverte à des viewers nommés, avec lien et "
            "expiration par personne, filigrane par viewer et journal de "
            "consultation."),
        # Vocabulaire FERMÉ de ``core.modules.CATEGORIES`` — même catégorie que
        # ``ged``/``contrats``, ses deux voisins de domaine.
        'categorie': 'Services',
    }
