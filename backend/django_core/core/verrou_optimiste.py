"""NTPLT17 — verrou optimiste OPT-IN des objets chauds (Devis, Facture, Lead,
Produit, Intervention).

Deux commerciaux ouvrent le même devis ; le second enregistre sans savoir que
le premier vient de le faire et écrase son travail en silence. Le modèle porte
``lock_version`` (``core.champs_plateforme.VerrouOptimisteMixin``, +1 à chaque
``save()``), servi en LECTURE SEULE par le sérialiseur. Un client qui veut être
protégé RENVOIE dans son PATCH/PUT la ``lock_version`` qu'il a lue :

* égale à la base → l'écriture passe (et la version avance) ;
* différente → **409** ``{detail, code: 'conflit_version', lock_version,
  actuel}`` : ``actuel`` est l'état courant complet, pour que l'écran propose
  de recharger ou de fusionner ; rien n'est écrit ;
* ABSENTE (ou vide) → comportement d'avant, strictement inchangé (opt-in,
  zéro rupture pour les écrans et intégrations existants).

La vérification a lieu deux fois : tôt (``is_valid``, avant tout effet de
bord de ``perform_update``) puis sous ``SELECT … FOR UPDATE`` dans ``save()``
(deux requêtes simultanées porteuses de la même version : une seule passe).

Couche de FONDATION : aucune importation d'app domaine.
"""
from django.db import transaction
from rest_framework import serializers

from core.conflit_etat import ConflitEtat

CHAMP_VERSION = 'lock_version'
CODE_CONFLIT_VERSION = 'conflit_version'
MESSAGE_CONFLIT_VERSION = (
    "Cet enregistrement a été modifié par quelqu'un d'autre depuis son "
    "ouverture. Rechargez-le avant d'enregistrer.")
MESSAGE_VERSION_INVALIDE = (
    '« lock_version » : un entier positif ou nul est attendu.')


class ConflitVersion(ConflitEtat):
    """409 — la version envoyée par le client n'est plus celle de la base.

    Le corps est posé TEL QUEL (``detail`` brut) : la conversion standard de
    DRF transformerait chaque nombre de l'état courant en chaîne."""

    default_code = 'version_conflict'

    def __init__(self, charge):
        super().__init__(charge.get('detail'))
        self.detail = charge


def version_envoyee(donnees):
    """La ``lock_version`` envoyée par le client, ou ``None`` (opt-in).

    Une valeur présente mais illisible est refusée (400 qui nomme le champ),
    jamais ignorée : le client CROIT être protégé."""
    if not hasattr(donnees, 'get'):
        return None
    brut = donnees.get(CHAMP_VERSION)
    if brut is None or brut == '':
        return None
    try:
        if isinstance(brut, bool):
            raise ValueError(brut)
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        valeur = -1
    if valeur < 0:
        raise serializers.ValidationError(
            {CHAMP_VERSION: [MESSAGE_VERSION_INVALIDE]})
    return valeur


class VerrouOptimisteSerializerMixin:
    """À placer AVANT ``serializers.ModelSerializer`` dans les bases.

    N'agit qu'en mise à jour (``self.instance`` posé) et seulement si le corps
    porte ``lock_version`` ; ne modifie ni les champs ni la validation des
    sous-classes."""

    def _version_en_base(self, verrouiller=False):
        modele = type(self.instance)
        qs = modele._base_manager.filter(pk=self.instance.pk)
        if verrouiller:
            qs = qs.select_for_update()
        return qs.values_list(CHAMP_VERSION, flat=True).first()

    def _conflit(self, actuelle):
        frais = type(self.instance)._base_manager.get(pk=self.instance.pk)
        return ConflitVersion({
            'detail': MESSAGE_CONFLIT_VERSION,
            'code': CODE_CONFLIT_VERSION,
            CHAMP_VERSION: actuelle,
            'actuel': type(self)(frais, context=self.context).data,
        })

    def _verifier_version(self, verrouiller=False):
        """``None`` si rien n'est demandé ; sinon la version en base (lève
        ``ConflitVersion`` si elle diffère de celle envoyée)."""
        if self.instance is None or getattr(self.instance, 'pk', None) is None:
            return None
        envoyee = version_envoyee(getattr(self, 'initial_data', None))
        if envoyee is None:
            return None
        actuelle = self._version_en_base(verrouiller=verrouiller)
        if actuelle is not None and actuelle != envoyee:
            raise self._conflit(actuelle)
        return actuelle

    def is_valid(self, *args, **kwargs):
        valide = super().is_valid(*args, **kwargs)
        if valide:
            self._verifier_version()
        return valide

    def save(self, **kwargs):
        if version_envoyee(getattr(self, 'initial_data', None)) is None \
                or self.instance is None:
            return super().save(**kwargs)
        with transaction.atomic():
            actuelle = self._verifier_version(verrouiller=True)
            if actuelle is not None:
                # La version d'où l'on repart est celle de la base (verrouillée),
                # jamais celle d'une instance chargée plus tôt.
                setattr(self.instance, CHAMP_VERSION, actuelle)
            return super().save(**kwargs)
