import { Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Euler, Quaternion } from 'three'
import { useAnimations, useGLTF } from '@react-three/drei'

// Avatar Ready Player Me: tidak punya tulang rahang, tapi punya morph target jawOpen dan viseme_*.
// Animasi Idle diambil dari animations.glb (nama tulang sama dengan avatar).
const ANIMATIONS_URL = '/models/animations.glb'
// Bicara dengan gestur kesal (Ready Player Me), dipakai saat ekspresi 'tense'.
const TENSE_TALK_URL = '/animations/M_Talking_Variations_006.glb'
const TENSE_TALK = 'M_Talking_Variations_006'
const VISEME_WEIGHT = 0.85
// Bukaan rahang per viseme, dipadukan dengan bentuk bibir agar mulut tidak hanya "monyong".
const JAW_FOR_VISEME = {
  viseme_aa: 0.4, viseme_O: 0.3, viseme_E: 0.28, viseme_I: 0.2, viseme_U: 0.18,
  viseme_CH: 0.15, viseme_kk: 0.15, viseme_DD: 0.15, viseme_RR: 0.15, viseme_SS: 0.12,
  viseme_nn: 0.12, viseme_TH: 0.12, viseme_FF: 0.1, viseme_PP: 0,
}
const VISEMES = Object.keys(JAW_FOR_VISEME)
const BLINK_TARGETS = ['eyeBlinkLeft', 'eyeBlinkRight']
// Tulang yang diluruskan tiap frame (urutan dari pinggul ke kepala). Objek di bawah dipakai ulang tiap frame.
const POSTURE_BONES = ['Hips', 'Spine', 'Spine1', 'Spine2', 'Neck', 'Head']
const POSTURE = new Euler()
const MIRROR = new Quaternion()
// Talking_0 menoleh 5–12° ke satu sisi dan Talking_2 memutar badan 19–27°: klien tampak tidak menghadap konselor.
// Talking_1 menoleh seimbang kiri-kanan, jadi hanya itu yang dipakai untuk bicara biasa.
const TALKING = 'Talking_1'
// Ekspresi wajah (morph ARKit) per label dari backend. Bobot sedang agar tetap bisa bicara di atasnya.
const EXPRESSIONS = {
  neutral: {},
  happy: { mouthSmileLeft: 0.4, mouthSmileRight: 0.4, cheekSquintLeft: 0.25, cheekSquintRight: 0.25, eyeSquintLeft: 0.1, eyeSquintRight: 0.1 },
  sad: { browInnerUp: 0.55, mouthFrownLeft: 0.45, mouthFrownRight: 0.45, eyeLookDownLeft: 0.2, eyeLookDownRight: 0.2, mouthShrugLower: 0.2 },
  anxious: { browInnerUp: 0.45, eyeWideLeft: 0.25, eyeWideRight: 0.25, mouthPressLeft: 0.3, mouthPressRight: 0.3, mouthStretchLeft: 0.1, mouthStretchRight: 0.1 },
  tense: { browDownLeft: 0.5, browDownRight: 0.5, eyeSquintLeft: 0.3, eyeSquintRight: 0.3, mouthPressLeft: 0.4, mouthPressRight: 0.4, noseSneerLeft: 0.15, noseSneerRight: 0.15 },
}
const FACE_MORPHS = [...new Set(Object.values(EXPRESSIONS).flatMap(Object.keys))]

function setMorph(meshes, name, value) {
  for (const mesh of meshes) {
    const i = mesh.morphTargetDictionary?.[name]
    if (i !== undefined) mesh.morphTargetInfluences[i] = value
  }
}

// Mendekat ke target secara halus, tidak bergantung frame rate.
const approach = (current, target, rate, delta) => current + (target - current) * (1 - Math.exp(-rate * delta))

function Avatar({ url, getSpeech, expression }) {
  const group = useRef()
  const { scene } = useGLTF(url)
  const { animations: baseClips } = useGLTF(ANIMATIONS_URL)
  const { animations: tenseClips } = useGLTF(TENSE_TALK_URL)
  const animations = useMemo(() => [...baseClips, ...tenseClips], [baseClips, tenseClips])
  // animations.glb punya track ke "Armature" dan tulang ujung (*_end) yang tidak ada di avatar; buang agar tidak memicu peringatan.
  const clips = useMemo(
    () => animations.map((clip) => {
      const c = clip.clone()
      c.tracks = c.tracks.filter((t) => scene.getObjectByName(t.name.split('.')[0]))
      return c
    }),
    [animations, scene],
  )
  const { actions } = useAnimations(clips, group)
  const meshes = useMemo(() => {
    const found = []
    scene.traverse((o) => o.morphTargetDictionary && found.push(o))
    return found
  }, [scene])
  const head = useRef(null)
  const mouth = useRef({ jawOpen: 0, ...Object.fromEntries(VISEMES.map((v) => [v, 0])) })
  const talk = useRef(0) // 0 diam .. 1 bicara, untuk gerak kepala
  const blink = useRef({ next: 2, t: -1 })
  const face = useRef(Object.fromEntries(FACE_MORPHS.map((n) => [n, 0])))
  const pose = useRef('Idle') // animasi tubuh yang sedang jalan: Idle, atau Talking_* saat klien bicara

  const bones = useRef({})
  const mirrorPairs = useRef([]) // [tulang kiri, tulang kanan]
  const symmetry = useRef(1) // 1 = sisi kanan cermin sisi kiri (saat diam), 0 = mengikuti gestur bicara
  useEffect(() => {
    head.current = scene.getObjectByName('Head')
    bones.current = Object.fromEntries(POSTURE_BONES.map((n) => [n, scene.getObjectByName(n)]))
    const pairs = []
    scene.traverse((o) => {
      if (!o.isBone || !o.name.startsWith('Left')) return
      const right = scene.getObjectByName(`Right${o.name.slice(4)}`)
      if (right) pairs.push([o, right])
    })
    mirrorPairs.current = pairs
  }, [scene])

  useEffect(() => {
    const idle = actions.Idle
    idle?.reset().fadeIn(0.4).play()
    return () => idle?.fadeOut(0.3)
  }, [actions])

  useFrame((state, delta) => {
    const speech = getSpeech?.() ?? null
    const m = mouth.current

    // Tubuh: animasi bicara selama suara diputar (gestur kesal bila ekspresi 'tense'), Idle setelahnya.
    const next = !speech ? 'Idle' : expression === 'tense' ? TENSE_TALK : TALKING
    if (next !== pose.current && actions[next]) {
      actions[pose.current]?.fadeOut(0.5)
      actions[next].reset().fadeIn(0.5).play()
      pose.current = next
    }

    // Lip-sync: viseme dari cue ElevenLabs; bila cue tidak ada, pakai volume (rahang + "a").
    const targets = { jawOpen: 0 }
    if (speech?.hasCues && speech.viseme) {
      targets[speech.viseme] = VISEME_WEIGHT
      targets.jawOpen = JAW_FOR_VISEME[speech.viseme] ?? 0.1
    } else if (speech && !speech.hasCues) {
      targets.viseme_aa = speech.level * 0.7
      targets.jawOpen = speech.level * 0.55
    }
    for (const name of Object.keys(m)) {
      const target = targets[name] ?? 0
      m[name] = approach(m[name], target, target > m[name] ? 30 : 16, delta)
      setMorph(meshes, name, m[name])
    }

    // Postur tegak menghadap konselor. Animasi memutar pinggul (Idle ~5°, gestur kesal sampai 13°) dan
    // memiringkan punggung ke samping (~5° total di Idle, diimbangi kepala) sehingga bahu tampak naik sebelah.
    // Pinggul: putaran & kemiringan dinolkan. Punggung sampai kepala: kemiringan saja; condong depan tetap.
    for (const name of POSTURE_BONES) {
      const bone = bones.current[name]
      if (!bone) continue
      POSTURE.setFromQuaternion(bone.quaternion, 'YXZ')
      POSTURE.z = 0
      if (name === 'Hips') POSTURE.y = 0
      bone.quaternion.setFromEuler(POSTURE)
    }
    // Saat diam, sisi kanan = cermin sisi kiri: bahu & lengan Idle tidak simetris (5–7°) sehingga badan
    // tampak miring. Pose dasar ketiga avatar simetris sempurna, jadi cermin (x, -y, -z, w) aman.
    // Saat bicara, gestur animasi dipakai apa adanya (perpindahan halus ~0,5 detik).
    symmetry.current = approach(symmetry.current, pose.current === 'Idle' ? 1 : 0, 4, delta)
    if (symmetry.current > 0.001) {
      for (const [left, right] of mirrorPairs.current) {
        MIRROR.set(left.quaternion.x, -left.quaternion.y, -left.quaternion.z, left.quaternion.w)
        right.quaternion.slerp(MIRROR, symmetry.current)
      }
    }

    // Anggukan & miring kecil saat bicara, ditambahkan di atas animasi tubuh (mixer menimpa rotasi Head tiap frame).
    talk.current = approach(talk.current, speech ? 1 : 0, 4, delta)
    const t = state.clock.elapsedTime
    if (head.current && talk.current > 0.001) {
      head.current
        .rotateX((Math.sin(t * 3.2) * 0.035 + Math.sin(t * 1.6) * 0.015) * talk.current)
        .rotateZ(Math.cos(t * 2.1) * 0.025 * talk.current)
        .rotateY(Math.sin(t * 1.2) * 0.02 * talk.current)
    }

    // Ekspresi berpindah perlahan (~1 detik) agar tidak terlihat melompat.
    const preset = EXPRESSIONS[expression] || EXPRESSIONS.neutral
    for (const name of FACE_MORPHS) {
      face.current[name] = approach(face.current[name], preset[name] ?? 0, 3, delta)
      setMorph(meshes, name, face.current[name])
    }

    // Kedip setiap 2–5 detik, selama ~150 ms.
    const b = blink.current
    if (b.t < 0 && t > b.next) b.t = t
    let closed = 0
    if (b.t >= 0) {
      const p = (t - b.t) / 0.15
      closed = p < 1 ? Math.sin(p * Math.PI) : 0
      if (p >= 1) {
        b.t = -1
        b.next = t + 2 + Math.random() * 3
      }
    }
    BLINK_TARGETS.forEach((n) => setMorph(meshes, n, closed))
  })

  return <primitive ref={group} object={scene} position={[0, -1.52, 0]} />
}

export default function ClientAvatar({ url, getSpeech, expression = 'neutral' }) {
  return (
    // Kamera dekat & sejajar mata: klien terlihat dari dada ke atas, seperti duduk di seberang meja.
    // Latar transparan; ruangan dan meja berupa gambar di VirtualClientStage.
    <Canvas camera={{ position: [0, -0.05, 1.27], fov: 33 }} dpr={[1, 2]} gl={{ alpha: true, antialias: true }}>
      <ambientLight intensity={0.85} />
      <directionalLight position={[-1.5, 1.8, 2]} intensity={1.5} color="#fff4e2" />
      <directionalLight position={[2, 1, -1]} intensity={0.4} color="#f5b51b" />
      <Suspense fallback={null}>
        <Avatar url={url} getSpeech={getSpeech} expression={expression} />
      </Suspense>
    </Canvas>
  )
}
