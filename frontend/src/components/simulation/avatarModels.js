// Avatar klien (file di public/models/). Dipisah dari ClientAvatar agar Three.js tetap lazy-loaded.
// avatarFile berasal dari persona (scenario_personas.avatar_file); bila kosong, dipilih menurut gender.
export const avatarUrl = (avatarFile, gender) => {
  if (avatarFile) return `/models/${avatarFile}`
  return /^(laki|pria|male)/i.test(gender || '') ? '/models/man1.glb' : '/models/girl1.glb'
}
