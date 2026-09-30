"""QA-COHERENCE — le contexte d'audit d'UNE société (caches, rendu isolé).

Le contexte porte ce que plusieurs règles partagent pour un même objet, pour
ne le calculer qu'une fois : les données du document construit par le moteur
de devis (``quote_engine.builder.build_quote_data``) et le contexte tarifaire
de la société.

RENDU ISOLÉ. ``build_quote_data`` peut toucher la base (resynchronisations
paresseuses, caches) et va chercher la photo de toiture dans MinIO. Pendant
l'audit :
  * chaque construction tourne dans un POINT DE SAUVEGARDE, lui-même à
    l'intérieur de la transaction d'audit que le moteur ANNULE toujours
    (``set_rollback(True)``) — rien de ce que fait le constructeur ne survit ;
  * la photo de toiture et l'affiche du calepinage sont neutralisées
    (``''``) le temps de l'audit seulement (patch restauré à la sortie) :
    aucune règle ne lit d'image, et l'audit n'émet aucun accès réseau.
"""
from __future__ import annotations

import contextlib
import math
from unittest import mock


class ErreurRendu(Exception):
    """La construction des données du document a échoué pour ce devis."""


def num(v):
    """``float`` fini, ou ``None`` (NaN/inf/non numérique)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def frac(v):
    f = num(v)
    return f if (f is not None and 0 < f <= 1) else None


@contextlib.contextmanager
def rendu_sans_reseau():
    """Neutralise les deux lectures d'images MinIO du constructeur, le temps
    du bloc seulement (le prototype COUV-HOR patchait ``_roof_photo_data_uri``
    pour tout le processus ; ici le patch est RESTAURÉ — un worker Celery
    continue de rendre de vrais PDF après l'audit)."""
    from apps.ventes.quote_engine import builder
    with mock.patch.object(builder, '_roof_photo_data_uri',
                           lambda devis: ''), \
            mock.patch.object(builder, '_roof_render_data_uri',
                              lambda devis: ''):
        yield


def _construire(devis, options):
    from apps.ventes.quote_engine import builder
    return builder.build_quote_data(devis, options)


class ContexteAudit:
    """Caches d'UNE société pour UNE passe d'audit."""

    def __init__(self, company, *, constructeur=None):
        self.company = company
        self._constructeur = constructeur or _construire
        self._rendus = {}
        self._tarif = None

    # ── Données du document ────────────────────────────────────────────────
    def donnees_devis(self, devis, options=None):
        """Les données du document (dict), construites UNE fois par
        (devis, options). Lève :class:`ErreurRendu` si la construction a
        échoué — l'échec est mémorisé, jamais retenté dans la même passe."""
        from django.db import transaction
        cle = (devis.pk, repr(sorted((options or {}).items())))
        if cle not in self._rendus:
            try:
                with transaction.atomic():
                    self._rendus[cle] = ('ok', self._constructeur(
                        devis, options))
            except Exception as exc:  # noqa: BLE001 — isolé par devis
                self._rendus[cle] = (
                    'erreur', f'{type(exc).__name__}: {str(exc)[:200]}')
        etat, valeur = self._rendus[cle]
        if etat == 'erreur':
            raise ErreurRendu(valeur)
        return valeur

    def injecter_donnees(self, devis, donnees, options=None):
        """Pour les tests : fournit des données déjà construites."""
        cle = (devis.pk, repr(sorted((options or {}).items())))
        self._rendus[cle] = ('ok', donnees)

    # ── Contexte tarifaire (début de la tranche haute + charges fixes) ─────
    def tarif(self):
        """Porté du prototype : ``top_start`` (plafond de la dernière tranche
        bornée, kWh/mois) et ``fixed_mois`` (charges fixes MAD/mois) de la
        société ; repli prudent si les réglages sont illisibles."""
        if self._tarif is not None:
            return self._tarif
        ctx = {'tranches': None, 'charges_fixes': None, 'top_start': 510.0,
               'fixed_mois': 40.0, 'src': 'fallback'}
        try:
            from apps.ventes.etude_horaire import (_reglages_tarifaires,
                                                   part_non_solarisable)
            tr, cf = _reglages_tarifaires(self.company)
            ctx['tranches'], ctx['charges_fixes'] = tr, cf
            table = tr
            if table is None:
                from apps.ventes.quote_engine import pricing
                table = getattr(pricing, 'ONEE_TRANCHES', None)
            plafonds = []
            for entree in (table or []):
                try:
                    c = float(entree[0])
                except Exception:  # noqa: BLE001
                    continue
                if c < 1e6:
                    plafonds.append(c)
            if plafonds:
                ctx['top_start'] = max(plafonds)
                ctx['src'] = 'tranches'
            try:
                ctx['fixed_mois'] = float(
                    part_non_solarisable(cf)['montant_mad_mois'])
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
        self._tarif = ctx
        return ctx
