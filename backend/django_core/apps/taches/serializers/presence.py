"""Formes de la présence iPhone (reference/api.md §3.4, annexe A `jeton.json`, `jetons_liste.json`).

Un jeton n'est JAMAIS servi par son empreinte ; son clair ne l'est qu'une fois, dans la réponse de sa
création (`forme_jeton_cree`), avec l'adresse qu'il ouvre.
"""
from django.urls import reverse
from rest_framework import serializers

from apps.taches.choix import UsageJeton

MESSAGE_USAGE = 'Valeur inconnue.'
MESSAGE_REQUIS = 'Requis.'
MESSAGE_LIBELLE = '60 caractères au plus.'
#: L'adresse qu'ouvre chaque usage (le flux porte le jeton dans son chemin).
ROUTE_USAGE = {UsageJeton.CAPTURE: 'taches-capture', UsageJeton.TUILE: 'taches-tuile'}
SUFFIXE_CAPTURE = '?reponse=texte'


class JetonEntreeSerializer(serializers.Serializer):
    """Corps de `POST jetons/` : `{"usage","libelle"?}`."""

    usage = serializers.ChoiceField(choices=UsageJeton.choices, error_messages={
        'invalid_choice': MESSAGE_USAGE, 'required': MESSAGE_REQUIS, 'null': MESSAGE_REQUIS})
    libelle = serializers.CharField(max_length=60, allow_blank=True, required=False, default='',
                                    error_messages={'max_length': MESSAGE_LIBELLE})


class JetonSerializer(serializers.Serializer):
    """Une ligne de `jetons_liste.json` : jamais l'empreinte ni le clair."""

    id = serializers.IntegerField()
    usage = serializers.CharField()
    prefixe = serializers.CharField()
    libelle = serializers.CharField()
    created_at = serializers.DateTimeField()
    dernier_usage_le = serializers.DateTimeField(allow_null=True)
    revoque_le = serializers.DateTimeField(allow_null=True)


def adresses(request, usage, clair):
    """`(url, webcal)` qu'ouvre le jeton : le flux `…/flux/<clair>.ics` (et son `webcal://`), la
    capture `…/capture/?reponse=texte`, la tuile `…/tuile/` (sans le jeton : il voyage en en-tête)."""
    if usage == UsageJeton.FLUX:
        url = request.build_absolute_uri(reverse('taches-flux', kwargs={'jeton': clair}))
        return url, 'webcal://' + url.split('://', 1)[1]
    url = request.build_absolute_uri(reverse(ROUTE_USAGE[UsageJeton(usage)]))
    return (url + SUFFIXE_CAPTURE if usage == UsageJeton.CAPTURE else url), None


def forme_jeton_cree(request, jeton, clair):
    """`jeton.json` : la ligne + le clair (rendu UNE fois) + l'adresse qu'il ouvre."""
    url, webcal = adresses(request, jeton.usage, clair)
    return {**JetonSerializer(jeton).data, 'jeton': clair, 'url': url, 'webcal': webcal}
