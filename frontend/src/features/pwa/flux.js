/* Attache un flux caméra à un élément <video> (scanner de codes-barres, capture
   photo) : `playsinline` (iOS) puis lecture ; un autoplay bloqué est ignoré. */
export async function attacherFlux(video, stream) {
  if (!video) return
  video.srcObject = stream
  video.setAttribute('playsinline', 'true')
  await video.play().catch(() => { /* autoplay bloqué : ignore */ })
}
