import ventesApi from '../../api/ventesApi'

/* Aperçu WhatsApp d'une facture (modèle « facture » ou « relance »), commun à
   la liste des factures et à la page des relances : le serveur construit le
   message (FR/Darija) et consigne l'action au chatter ; l'écran montre ensuite
   l'aperçu avant d'ouvrir wa.me. `notifier` = le `toast` de l'écran appelant. */
export async function preparerApercuWhatsApp({ facture, params, setWaBusy, setWaPreview, notifier }) {
  setWaBusy(prev => ({ ...prev, [facture.id]: true }))
  try {
    const { data } = await ventesApi.whatsappFacture(facture.id, params)
    setWaPreview({ reference: facture.reference, message: data?.message ?? '', url: data?.url ?? '', wa_url: data?.wa_url ?? '' })
  } catch (err) {
    notifier.error(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
  } finally {
    setWaBusy(prev => ({ ...prev, [facture.id]: false }))
  }
}
