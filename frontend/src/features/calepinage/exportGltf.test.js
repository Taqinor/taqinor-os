// ACAL537 — export glTF de la scène 3D. Fichier neuf : module neuf sans hôte de test.
import { describe, it, expect, vi } from 'vitest'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { groupeVersGlb } from '@roofpro/scene3d'
import { exporterSceneGltf, nomFichierGltf } from './exportGltf.js'

/** Une scène de `n` modules : un contour de pan + un InstancedMesh de panneaux. */
function sceneDeModules(n) {
  const racine = new THREE.Group()
  const pan = new THREE.Mesh(new THREE.PlaneGeometry(12, 6), new THREE.MeshStandardMaterial())
  pan.name = 'contour-du-pan'
  racine.add(pan)
  const modules = new THREE.InstancedMesh(new THREE.BoxGeometry(1.13, 2.28, 0.035), new THREE.MeshStandardMaterial(), n)
  for (let i = 0; i < n; i++) modules.setMatrixAt(i, new THREE.Matrix4().makeTranslation(i * 1.2, 0, 0.1))
  modules.instanceMatrix.needsUpdate = true
  racine.add(modules)
  return racine
}

async function relire(blob) {
  const tampon = await blob.arrayBuffer()
  const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(tampon, '', resolve, reject))
  const instances = []
  let maillages = 0
  gltf.scene.traverse((o) => {
    if (o.isInstancedMesh) instances.push(o.count)
    else if (o.isMesh) maillages += 1
  })
  return { instances, maillages }
}

describe('ACAL537 — exporter la scène 3D en glTF', () => {
  it('une scène de 12 modules relue par GLTFLoader : un maillage instancié à 12 instances et le contour du pan', async () => {
    const blob = await groupeVersGlb(sceneDeModules(12))
    const { instances, maillages } = await relire(blob)
    expect(instances).toEqual([12])
    expect(maillages).toBeGreaterThanOrEqual(1) // le contour du pan
  })

  it('télécharge `calepinage-<id>.glb`', async () => {
    const telecharger = vi.fn()
    const api = { exporterSceneGltf: async () => ({ blob: await groupeVersGlb(sceneDeModules(12)) }) }
    const res = await exporterSceneGltf(api, { reference: 42, telecharger })
    expect(res).toEqual({ ok: true, nom: 'calepinage-42.glb' })
    expect(telecharger).toHaveBeenCalledTimes(1)
    expect(telecharger.mock.calls[0][1]).toBe(nomFichierGltf(42))
  })

  it('scène vide ⇒ motif français, aucun fichier', async () => {
    const telecharger = vi.fn()
    const res = await exporterSceneGltf({ exporterSceneGltf: async () => null }, { reference: 1, telecharger })
    expect(res).toEqual({ ok: false, motif: 'Scène non rendable ici — aucun fichier produit.' })
    expect(telecharger).not.toHaveBeenCalled()
  })

  it('outil non prêt ⇒ motif, aucune exception', async () => {
    const res = await exporterSceneGltf(null, { reference: 1 })
    expect(res.ok).toBe(false)
  })
})
