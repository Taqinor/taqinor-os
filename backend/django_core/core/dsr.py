"""FG394 — Consentement & DSR (loi 09-08 / CNDP), orchestration.

Couche de FONDATION : orchestre les demandes de personnes concernées (accès =
export, effacement) SANS que ``core`` n'importe une app métier (contrat
import-linter ``core-foundation-is-a-base-layer``). Chaque app détenant des
données personnelles ENREGISTRE un « fournisseur DSR » :

    register_dsr_provider(name, export=fn_export, erase=fn_erase)

où ``fn_export(company, subject_identifier) -> dict`` renvoie les données de la
personne pour cette app (déjà scopées société), et ``fn_erase(company,
subject_identifier) -> int`` efface/anonymise et renvoie le nombre d'éléments
traités. ``core`` agrège simplement les fournisseurs — il ne sait RIEN des
modèles métier.
"""
from __future__ import annotations

from django.utils import timezone

# Registre en mémoire : { name: {export: fn|None, erase: fn|None} }.
_PROVIDERS: dict[str, dict] = {}


def register_dsr_provider(name, *, export=None, erase=None):
    """Enregistre un fournisseur DSR pour une app (idempotent).

    Au moins un de ``export`` / ``erase`` doit être fourni.
    """
    if not name or (export is None and erase is None):
        raise ValueError('Fournisseur DSR : nom + export et/ou erase requis.')
    _PROVIDERS[name] = {'export': export, 'erase': erase}


def list_dsr_providers():
    """Noms des fournisseurs DSR enregistrés (rendu stable)."""
    return sorted(_PROVIDERS.keys())


def exporter(company, subject_identifier):
    """Agrège l'export de tous les fournisseurs pour une personne concernée.

    Renvoie ``{provider_name: data}``. Un fournisseur qui lève est isolé
    (``{'erreur': ...}``) pour ne pas faire échouer tout l'export.
    """
    out = {}
    for name, prov in sorted(_PROVIDERS.items()):
        fn = prov.get('export')
        if fn is None:
            continue
        try:
            out[name] = fn(company, subject_identifier)
        except Exception as exc:  # noqa: BLE001 - isolation par fournisseur
            out[name] = {'erreur': str(exc)}
    return out


def effacer(company, subject_identifier):
    """Déclenche l'effacement chez tous les fournisseurs pour une personne.

    Renvoie ``{provider_name: nb_traite}``. Un fournisseur qui lève est isolé.
    """
    out = {}
    for name, prov in sorted(_PROVIDERS.items()):
        fn = prov.get('erase')
        if fn is None:
            continue
        try:
            out[name] = fn(company, subject_identifier)
        except Exception as exc:  # noqa: BLE001 - isolation par fournisseur
            out[name] = {'erreur': str(exc)}
    return out


def traiter_demande(request):
    """Exécute une ``DataSubjectRequest`` (accès → export, effacement → erase).

    Met à jour ``resultat`` / ``statut`` / ``traitee_le``. Multi-tenant : la
    société de la demande borne tous les fournisseurs.
    """
    from .models import DataSubjectRequest

    company = request.company
    subject = request.subject_identifier
    if request.kind == DataSubjectRequest.KIND_ACCESS:
        request.resultat = exporter(company, subject)
    elif request.kind == DataSubjectRequest.KIND_ERASURE:
        request.resultat = effacer(company, subject)
    else:
        # XPLT23 — rectification : workflow MANUEL. On n'exécute aucune
        # opération automatique ; on renvoie l'export des données actuelles
        # comme contexte de correction et on laisse le traitement au responsable
        # (champs demandés + trace). La demande reste « traitée » (contexte
        # fourni) mais aucune donnée n'est modifiée automatiquement.
        request.resultat = {
            'rectification': True,
            'donnees_actuelles': exporter(company, subject),
            'note': 'Correction à traiter manuellement par le responsable.',
        }
    request.statut = DataSubjectRequest.STATUT_TRAITEE
    request.traitee_le = timezone.now()
    request.save(update_fields=['resultat', 'statut', 'traitee_le',
                                'updated_at'])
    return request
