"""VAO26 — rétention et purge du SAS de veille.

Ce que la purge touche, et ce qu'elle ne touchera JAMAIS
--------------------------------------------------------
Un avis **`nouveau`** ou **`ignoré`** dont la date limite est dépassée depuis
N mois n'a plus aucune valeur : personne ne le rouvrira, et le garder noie
l'écran. Il est purgé.

Un avis **`retenu`** ou **`converti`** — et, par prudence, tout avis LIÉ à un
appel d'offres — n'est **jamais** purgé, quel que soit son âge. Il porte
l'historique commercial ET la mesure d'attribution de VAO31 (« d'où vient
réellement le chiffre d'affaires ») : effacer un avis converti reviendrait à
effacer la preuve qu'un canal fonctionne, ce qui est exactement l'inverse du
but du groupe. Un avis `expiré` n'est pas purgé non plus tant qu'il a été
retenu — l'expiration est un statut de fin de course, pas un verdict humain.

Le registre partagé (``core.retention``, YOPSB10) fournit le cadre : cette
app y enregistre SA politique dans son ``apps.py ready()``. Le contrat du
registre impose de respecter ``apply_`` — en DRY-RUN (le défaut) on COMPTE
sans rien supprimer.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Fenêtre par défaut, en MOIS, après la date limite de remise.
DEFAUT_RETENTION_MOIS = 12

#: Les statuts qu'une purge a le droit de toucher. Volontairement une liste
#: POSITIVE (ce qui est purgeable) et non une liste d'exclusions : oublier
#: d'exclure un statut effacerait des données ; oublier d'en inclure un ne
#: fait que garder trop longtemps.
STATUTS_PURGEABLES = ('nouveau', 'ignore')

#: 1 mois ≈ 30 jours. Approximation ASSUMÉE : la rétention est une politique
#: de ménage, pas une échéance légale — un écart de deux jours sur douze mois
#: n'a aucune conséquence, et une arithmétique de calendrier exacte n'en
#: aurait aucune valeur ici.
JOURS_PAR_MOIS = 30


def avis_purgeables(now=None, mois=None):
    """Le queryset des avis que la politique a le droit de supprimer.

    Lecture PURE (aucune écriture) : c'est ce qui rend le dry-run honnête —
    le mode « compter » et le mode « supprimer » regardent exactement le même
    ensemble, jamais deux requêtes qui pourraient diverger.

    Scopé par la POLITIQUE, pas par société : le balayage est transverse, et
    chaque avis porte déjà sa société. Aucun avis d'aucune société n'est
    touché s'il est retenu, converti ou lié à un appel d'offres.
    """
    from datetime import timedelta

    from .models import AvisMarche

    mois = DEFAUT_RETENTION_MOIS if mois is None else int(mois)
    if mois <= 0:
        return AvisMarche.objects.none()

    limite = (now or timezone.now()) - timedelta(days=mois * JOURS_PAR_MOIS)
    return AvisMarche.objects.filter(
        statut__in=STATUTS_PURGEABLES,
        date_limite_remise__isnull=False,
        date_limite_remise__lt=limite,
        # Ceinture ET bretelles : un avis qui a produit une affaire n'est
        # jamais purgeable, même si son statut a dérivé.
        appel_offre_id__isnull=True,
    )


def purger_avis(now=None, apply_=False, mois=None):
    """Politique de rétention du sas — signature du registre YOPSB10.

    ``apply_=False`` (le défaut du balayage) COMPTE sans rien supprimer.
    Renvoie le nombre d'avis concernés dans les deux modes : c'est ce qui
    permet de mesurer l'effet d'un réglage AVANT de l'appliquer.
    """
    from django.conf import settings

    if mois is None:
        mois = getattr(settings, 'VEILLE_AO_RETENTION_MOIS',
                       DEFAUT_RETENTION_MOIS)

    queryset = avis_purgeables(now=now, mois=mois)
    combien = queryset.count()
    if not apply_ or not combien:
        return combien

    supprimes, _detail = queryset.delete()
    logger.info('veille_ao: rétention — %s avis purgés (fenêtre %s mois)',
                combien, mois)
    return combien
