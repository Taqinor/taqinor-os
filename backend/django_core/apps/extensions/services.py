"""NTEXT14 — installation / désinstallation d'un package par tenant.

Le catalogue (``ExtensionPackage``, NTEXT13) décrit en JSON ce qu'un package
POSE ; ce module le MATÉRIALISE en objets réels scopés société, et sait le
retirer sans jamais toucher aux données saisies par l'utilisateur.

Registre de MATÉRIALISEURS
--------------------------
``extensions`` ne connaît AUCUNE app métier : chaque section du manifest est
prise en charge par un matérialiseur ENREGISTRÉ (même patron que
``core.data_explorer.register_dataset`` / ``core.retention.register_retention_policy``)::

    register_materializer('automation_rules', poser)

    poser(company, definition) -> (reference: str | None, cree: bool)

``reference`` est une chaîne ``'app_label.model:pk'``. ``cree`` dit si l'objet
a VRAIMENT été créé par cet appel : seul un objet créé est enregistré dans
``ExtensionInstall.objets_crees``, donc seul un objet créé sera retiré à la
désinstallation — un objet qui PRÉEXISTAIT (donnée de l'utilisateur) n'est
jamais supprimé. Une section sans matérialiseur enregistré est simplement
IGNORÉE (rien créé ⇒ rien à retirer) : les apps propriétaires branchent la
leur quand elles arrivent.

``extensions`` embarque UN matérialiseur natif : ``branded_templates`` →
``core.BrandedTemplate``, une brique de FONDATION (aucune frontière d'app
métier franchie).

Garanties
---------
* IDEMPOTENT — ré-installer ne duplique rien (``get_or_create`` côté
  matérialiseur + références dédupliquées côté installation) ;
* SCOPÉ SOCIÉTÉ — tout est créé dans la société passée en paramètre ;
* SANS ORPHELIN — désinstaller retire exactement les références posées ;
* DÉFENSIF — un matérialiseur en échec n'interrompt pas l'installation : la
  section est ignorée et l'installation passe en statut ``erreur``.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

_MATERIALIZERS = {}


# ── Registre ──────────────────────────────────────────────────────────────

def register_materializer(section, poser):
    """Enregistre le matérialiseur d'UNE section de manifest.

    ``poser(company, definition) -> (reference, cree)``. Le RETRAIT est
    universel (suppression par ``'app.model:pk'``, bornée à la société) : il
    n'y a volontairement pas de crochet de retrait par section — une
    référence porte déjà tout ce qu'il faut pour la supprimer, et un second
    mécanisme ouvrirait la porte à supprimer autre chose que ce qui a été posé.
    """
    if not section or not callable(poser):
        raise ValueError('Matérialiseur : section + fonction « poser » requis.')
    _MATERIALIZERS[section] = {'poser': poser}


def materializers():
    """Sections prises en charge (copie, pour inspection/tests)."""
    return dict(_MATERIALIZERS)


# ── Suppression générique par référence ────────────────────────────────────

def _supprimer_reference(reference, company=None):
    """Supprime l'objet désigné par ``'app_label.model:pk'``.

    Renvoie ``True`` si la référence n'existe plus après l'appel (supprimée OU
    déjà absente). La suppression est BORNÉE à ``company`` dès que le modèle
    cible porte une FK ``company`` : même avec un ``objets_crees`` altéré,
    l'objet d'un autre tenant n'est jamais atteint.
    """
    from django.apps import apps as django_apps

    try:
        label, _, brut_pk = str(reference or '').partition(':')
        app_label, _, model_name = label.partition('.')
        if not (app_label and model_name and brut_pk):
            return False
        model = django_apps.get_model(app_label, model_name)
        filtres = {'pk': brut_pk}
        if company is not None and any(
                f.name == 'company' for f in model._meta.concrete_fields):
            filtres['company'] = company
        model.objects.filter(**filtres).delete()
        return True
    except Exception:  # pragma: no cover - défensif (référence illisible)
        logger.warning('extensions: référence non supprimable %r', reference,
                       exc_info=True)
        return False


# ── Installation / désinstallation ─────────────────────────────────────────

def installer_package(company, package):
    """Installe ``package`` sur ``company`` et renvoie l'``ExtensionInstall``.

    IDEMPOTENT : ré-appeler reprend la même installation et ne recrée rien.
    """
    from .models import ExtensionInstall

    install, _cree = ExtensionInstall.objects.get_or_create(
        company=company, package=package,
        defaults={'version': package.version,
                  'statut': ExtensionInstall.Statut.INSTALLE,
                  'installe_le': timezone.now()})

    references = list(install.objets_crees or [])
    vues = set(references)
    en_erreur = False

    for section, definitions in (package.manifest or {}).items():
        materialiseur = _MATERIALIZERS.get(section)
        if materialiseur is None:
            continue
        if not isinstance(definitions, (list, tuple)):
            continue
        for definition in definitions:
            try:
                reference, cree = materialiseur['poser'](company, definition)
            except Exception:  # une section fautive n'annule pas les autres
                logger.warning(
                    'extensions: matérialisation %r en échec (package %s)',
                    section, package.pk, exc_info=True)
                en_erreur = True
                continue
            if cree and reference and reference not in vues:
                vues.add(reference)
                references.append(reference)

    install.objets_crees = references
    install.version = package.version
    install.statut = (ExtensionInstall.Statut.ERREUR if en_erreur
                      else ExtensionInstall.Statut.INSTALLE)
    install.installe_le = install.installe_le or timezone.now()
    install.save(update_fields=['objets_crees', 'version', 'statut',
                                'installe_le', 'updated_at'])
    return install


def desinstaller_package(install):
    """Retire EXACTEMENT ce que l'installation a posé. Renvoie l'installation.

    Les références sont retirées dans l'ordre INVERSE de leur pose (les
    dépendances éventuelles partent après ce qui s'appuie dessus). Une
    référence non supprimable est CONSERVÉE dans ``objets_crees`` (elle sera
    retentée), jamais perdue en silence.
    """
    from .models import ExtensionInstall

    restantes = []
    for reference in reversed(list(install.objets_crees or [])):
        if not _supprimer_reference(reference, install.company):
            restantes.append(reference)

    install.objets_crees = list(reversed(restantes))
    install.statut = ExtensionInstall.Statut.DESINSTALLE
    install.save(update_fields=['objets_crees', 'statut', 'updated_at'])
    return install


# ── Matérialiseur natif : branded_templates → core.BrandedTemplate ─────────

def poser_branded_template(company, definition):
    """Pose UN ``core.BrandedTemplate`` (fondation) pour la société.

    ``get_or_create`` sur la clé unique du modèle ``(company, kind, code)`` :
    un modèle déjà présent (donnée de l'utilisateur) est REPRIS tel quel et
    signalé « non créé » — il ne sera donc jamais supprimé à la
    désinstallation.
    """
    from core.models import BrandedTemplate

    definition = definition or {}
    code = str(definition.get('code') or '').strip()
    if not code:
        return None, False
    kind = str(definition.get('kind') or BrandedTemplate.KIND_EMAIL).strip()
    objet, cree = BrandedTemplate.objects.get_or_create(
        company=company, kind=kind, code=code,
        defaults={
            'nom': str(definition.get('nom') or code)[:160],
            'sujet': str(definition.get('sujet') or '')[:255],
            'corps': str(definition.get('corps') or ''),
        })
    return f'core.brandedtemplate:{objet.pk}', cree


register_materializer('branded_templates', poser_branded_template)
