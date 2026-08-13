"""NTEXT24 — import/export de la CONFIGURATION de plateforme (blueprint tenant).

``exporter_blueprint(company)`` sérialise TOUT ce qu'un admin a construit sans
code pour une société — objets personnalisés + leurs champs, règles
d'automatisation (avec leurs étapes), définitions de rapport, vues de liste,
gabarits de document — et ``importer_blueprint(company, blueprint)`` le recrée
à l'identique dans une AUTRE société. C'est la base du « clonage de setup ».

Garanties :

* **CONFIG SEULEMENT, jamais les données.** Aucun ``CustomRecord``, aucun
  enregistrement métier, aucun journal n'est exporté ni importé.
* **IDEMPOTENT.** L'import s'appuie sur la CLÉ NATURELLE de chaque section
  (``code``, ``(module, code)``, ``nom``, ``titre``, ``(cible, nom)``) :
  ré-importer le même blueprint met à jour, ne duplique jamais.
* **Multi-tenant strict.** ``company`` est TOUJOURS celle passée en paramètre ;
  aucune valeur de société, de propriétaire ni d'identifiant technique du
  blueprint n'est jamais réutilisée.
* **Aucun import statique cross-app.** Les modèles des autres apps sont résolus
  à l'exécution par ``django.apps.apps.get_model`` (libellé ``app.Modele``) :
  ce module ne crée AUCUNE arête d'import entre apps.
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ['SECTIONS', 'exporter_blueprint', 'importer_blueprint',
           'VERSION_BLUEPRINT']

#: Version du format — un import refuse une version majeure inconnue.
VERSION_BLUEPRINT = 1


class Section:
    """Une section du blueprint : un modèle, ses champs, sa clé naturelle.

    ``parent`` (optionnel) désigne la section dont dépend celle-ci : la valeur
    du champ ``parent_champ`` est alors RÉÉCRITE à l'import vers l'objet
    recréé dans la société cible (jamais l'id d'origine).
    """

    __slots__ = ('cle', 'label_modele', 'champs', 'cle_naturelle',
                 'enfants', 'tri')

    def __init__(self, cle, label_modele, champs, cle_naturelle, *,
                 enfants=None, tri=('id',)):
        self.cle = cle
        self.label_modele = label_modele
        self.champs = tuple(champs)
        self.cle_naturelle = tuple(cle_naturelle)
        self.enfants = enfants or ()
        self.tri = tuple(tri)


class SousSection:
    """Lignes filles d'une ligne de section (ex. les étapes d'une règle)."""

    __slots__ = ('cle', 'label_modele', 'champs', 'champ_parent', 'tri')

    def __init__(self, cle, label_modele, champs, champ_parent,
                 tri=('ordre', 'id')):
        self.cle = cle
        self.label_modele = label_modele
        self.champs = tuple(champs)
        self.champ_parent = champ_parent
        self.tri = tuple(tri)


#: Ordre SIGNIFICATIF : les objets personnalisés avant leurs champs.
SECTIONS = (
    Section(
        'objets', 'customfields.CustomObjectDef',
        ('code', 'libelle', 'icone', 'actif'), ('code',), tri=('code',)),
    Section(
        'champs', 'customfields.CustomFieldDef',
        ('module', 'code', 'libelle', 'type', 'options', 'obligatoire',
         'visible_liste', 'ordre', 'actif', 'relation_module', 'conditions',
         'ia_prompt'),
        ('module', 'code'), tri=('module', 'ordre', 'code')),
    Section(
        'regles', 'automation.AutomationRule',
        ('nom', 'enabled', 'trigger_type', 'trigger_config', 'action_type',
         'action_config', 'requires_approval', 'approval_threshold', 'ordre'),
        ('nom',), tri=('ordre', 'nom'),
        enfants=(
            SousSection('etapes', 'automation.AutomationStep',
                        ('ordre', 'action_type', 'action_config'), 'rule'),
        )),
    Section(
        'rapports', 'reporting.RapportDefinition',
        ('titre', 'dataset', 'spec', 'pivot_spec', 'partage'),
        ('titre',), tri=('titre',)),
    Section(
        'vues', 'core.VuePersonnalisee',
        ('cible', 'nom', 'config', 'partage', 'equipe', 'est_defaut',
         'role_tier'),
        ('cible', 'nom'), tri=('cible', 'nom')),
    Section(
        'gabarits', 'parametres.GabaritDocumentCustom',
        ('code', 'nom', 'cible', 'corps', 'actif'), ('code',), tri=('code',)),
)


def _modele(label):
    from django.apps import apps as django_apps

    app_label, nom = label.split('.', 1)
    return django_apps.get_model(app_label, nom)


def _valeur_exportable(valeur):
    """Valeur JSON-sérialisable (les décimaux sortent en chaîne)."""
    if valeur is None or isinstance(valeur, (str, int, float, bool, list,
                                             dict)):
        return valeur
    return str(valeur)


def exporter_blueprint(company):
    """Blueprint JSON-sérialisable de TOUTE la config de ``company``.

    Ne lève jamais pour une section indisponible (app absente/désinstallée) :
    la section est simplement vide, l'export reste exploitable.
    """
    blueprint = {'version': VERSION_BLUEPRINT, 'sections': {}}
    for section in SECTIONS:
        try:
            modele = _modele(section.label_modele)
            lignes = []
            for objet in (modele.objects.filter(company=company)
                          .order_by(*section.tri)):
                ligne = {champ: _valeur_exportable(getattr(objet, champ, None))
                         for champ in section.champs}
                for enfant in section.enfants:
                    modele_enfant = _modele(enfant.label_modele)
                    ligne[enfant.cle] = [
                        {champ: _valeur_exportable(getattr(fils, champ, None))
                         for champ in enfant.champs}
                        for fils in (modele_enfant.objects
                                     .filter(**{enfant.champ_parent: objet})
                                     .order_by(*enfant.tri))
                    ]
                lignes.append(ligne)
            blueprint['sections'][section.cle] = lignes
        except Exception:  # pragma: no cover - app absente / modèle retiré
            logger.warning('blueprint: section %s non exportable', section.cle,
                           exc_info=True)
            blueprint['sections'][section.cle] = []
    return blueprint


def importer_blueprint(company, blueprint):
    """Recrée la config d'un blueprint DANS ``company``. Idempotent.

    Renvoie un compte par section : ``{'objets': {'crees': n, 'majs': m}, …}``.
    ``company`` est toujours celle passée ici — jamais une valeur du blueprint.
    Lève ``ValueError`` si le format est inconnu (version majeure future).
    """
    if not isinstance(blueprint, dict):
        raise ValueError('Blueprint illisible : objet JSON attendu.')
    version = blueprint.get('version', VERSION_BLUEPRINT)
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise ValueError('Blueprint illisible : version invalide.')
    if version > VERSION_BLUEPRINT:
        raise ValueError(
            f'Blueprint en version {version} : ce serveur lit au plus la '
            f'version {VERSION_BLUEPRINT}.')

    sections = blueprint.get('sections') or {}
    if not isinstance(sections, dict):
        raise ValueError('Blueprint illisible : « sections » attendu.')

    resultat = {}
    for section in SECTIONS:
        lignes = sections.get(section.cle) or []
        crees = majs = 0
        if not isinstance(lignes, list):
            lignes = []
        try:
            modele = _modele(section.label_modele)
        except Exception:  # pragma: no cover - app absente
            logger.warning('blueprint: section %s non importable', section.cle,
                           exc_info=True)
            resultat[section.cle] = {'crees': 0, 'majs': 0}
            continue
        for ligne in lignes:
            if not isinstance(ligne, dict):
                continue
            recherche = {'company': company}
            for champ in section.cle_naturelle:
                recherche[champ] = ligne.get(champ)
            if any(valeur in (None, '') for champ, valeur in recherche.items()
                   if champ != 'company'):
                continue  # clé naturelle incomplète : ligne ignorée
            defauts = {
                champ: ligne.get(champ) for champ in section.champs
                if champ not in section.cle_naturelle
            }
            objet, cree = modele.objects.update_or_create(
                defaults=defauts, **recherche)
            crees += 1 if cree else 0
            majs += 0 if cree else 1
            for enfant in section.enfants:
                _importer_enfants(enfant, objet, ligne.get(enfant.cle) or [])
        resultat[section.cle] = {'crees': crees, 'majs': majs}
    return resultat


def _importer_enfants(enfant, parent, lignes):
    """Remplace À L'IDENTIQUE les lignes filles d'un parent (idempotent).

    Les étapes d'une règle n'ont pas de clé naturelle stable : on reconstruit
    la séquence complète (supprimer puis recréer) pour que ré-importer donne
    exactement la même séquence, jamais une séquence doublée.
    """
    modele = _modele(enfant.label_modele)
    modele.objects.filter(**{enfant.champ_parent: parent}).delete()
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        modele.objects.create(
            **{enfant.champ_parent: parent},
            **{champ: ligne.get(champ) for champ in enfant.champs})
