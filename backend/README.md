# Backend SafeSesi

Perintah di bawah dijalankan dari folder `backend/` dengan `DATABASE_URL` terisi di `.env`.

## Pemulihan akun admin (darurat)

Dipakai bila semua admin lupa kata sandi, atau untuk membuat admin pertama di production.
Dijalankan manual di server, bukan lewat API. Kata sandi diminta lewat prompt tersembunyi dua kali.

Atur ulang kata sandi akun yang ada (semua sesi login akun itu dicabut, akun diaktifkan bila belum):

```
python -m scripts.reset_user_password --email admin@kampus.ac.id
```

Buat admin pertama (hanya bila emailnya belum terdaftar):

```
python -m scripts.reset_user_password --email admin@kampus.ac.id --create-admin --name "Nama Admin"
```

Akun admin sengaja hanya bisa dipulihkan lewat skrip ini. Endpoint `reset-password` di API menolak akun
bertarget admin (403): kalau tidak, satu admin (atau sesi admin yang dicuri) bisa mengambil alih admin lain
cukup dengan menerbitkan tautan reset. Dengan skrip, pemulihan admin mengharuskan akses ke server.

Skrip menolak berjalan bila akun tidak ditemukan atau sudah dihapus, lalu mencetak email akun yang
diubah sebagai konfirmasi. Untuk pengguna biasa, admin memakai tombol/endpoint
`POST /api/v1/admin/users/{id}/reset-password`, bukan skrip ini.
