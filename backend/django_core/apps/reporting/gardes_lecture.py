"""ADRG70 (C-ADRG-019, D-APFS-4) — gardes de LECTURE du module SOURCE des
rapports, hors des vues (patron ``apps/ventes/gardes_lecture.py``).

Un rapport ne vérifiait que ``IsResponsableOrAdmin`` sur le module
``reporting`` : tout rôle qui lit les rapports lisait aussi les ventes, le CRM,
les chantiers, le SAV et le stock qu'ils agrègent. ``lecture_source(module)``
exige en plus la lecture du module dont la vue SERT les données
(``LectureDuModule`` à module figé, APFS108 : superuser, palier administrateur
et comptes hérités sans rôle fin inchangés)."""
from authentication.permissions import LectureDuModule

_GARDES = {}


def lecture_source(module):
    """Classe de permission : au moins un code du module ``module``."""
    if module not in _GARDES:
        _GARDES[module] = type(
            f'LectureSource_{module}', (LectureDuModule,), {
                'module_fige': module,
                'message': f'Accès réservé aux rôles du module {module}.',
            })
    return _GARDES[module]
