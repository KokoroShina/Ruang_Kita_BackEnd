Saya ingin kamu melakukan UI/UX refinement dan pengembangan halaman ADMIN pada project ini.

SEBELUM MULAI:
1. Baca dan pahami seluruh struktur project terlebih dahulu.
2. WAJIB membaca file `quickstart.md` sampai selesai.
3. Ikuti instruksi, arsitektur, struktur data, role/permission, endpoint, dan aturan yang dijelaskan di `quickstart.md`.
4. Jangan langsung mengubah kode sebelum memahami bagaimana aplikasi ini bekerja.
5. Identifikasi framework, routing, component structure, styling system, API/backend, authentication, dan database yang digunakan.
6. Cari tahu halaman mana yang merupakan halaman user dan mana yang nantinya menjadi area admin.
7. Jangan membuat mock data atau sistem baru jika sebenarnya functionality tersebut sudah tersedia di project.

==================================================
TUJUAN UTAMA
==================================================

Saya sudah memiliki desain frontend untuk aplikasi "Ruang Kita".

Secara visual desain sekarang sudah minimalis, tenang, dan cukup bagus, tetapi masalah utamanya adalah:

- antar-section terasa menyatu
- batas antara satu kelompok konten dengan kelompok lainnya kurang jelas
- terlalu banyak whitespace yang terasa "kosong" dan tidak memiliki fungsi
- hierarchy visual belum cukup kuat
- halaman terasa seperti kumpulan konten yang mengambang
- beberapa bagian membutuhkan section boundary yang lebih jelas
- saya ingin tetap mempertahankan kesan minimalis, calm, personal, editorial, dan wellness journal
- JANGAN mengubah desain menjadi dashboard SaaS yang penuh card
- JANGAN membuat semuanya menjadi card

Gunakan screenshot desain yang diberikan sebagai referensi visual utama.

Halaman yang perlu diperhatikan:

1. Beranda
2. Kenali
3. Pahami
4. Temukan
5. Detail jurnal/refleksi

==================================================
ARAH DESAIN BARU
==================================================

Pertahankan fondasi visual yang sudah ada:

- warm cream / off-white background
- serif typography untuk heading
- sans-serif untuk body
- muted brown sebagai accent
- subtle border
- rounded corner yang tidak berlebihan
- whitespace yang cukup
- desain tenang dan personal
- visual sederhana
- tidak menggunakan terlalu banyak icon
- tidak menggunakan gradient berlebihan
- tidak menggunakan warna mencolok

Tetapi perbaiki INFORMATION HIERARCHY.

Setiap halaman harus memiliki struktur visual yang jelas:

PAGE HEADER
    ↓
SECTION
    ↓
SECTION CONTENT
    ↓
SECTION DIVIDER
    ↓
SECTION BERIKUTNYA

Gunakan kombinasi:

- section label
- typography hierarchy
- horizontal divider
- subtle background variation
- grouping
- spacing yang konsisten
- card hanya ketika memang dibutuhkan

==================================================
1. SECTION HARUS TERASA SEBAGAI SECTION
==================================================

Jangan hanya memisahkan section dengan margin besar.

Gunakan divider tipis dan/atau subtle background change.

Contoh struktur:

PILAR KETIGA

Temukan
Deskripsi halaman...

────────────────────────────────────────

UNTUKMU

Deskripsi section...

[ Card ] [ Card ]
[ Card ] [ Card ]

────────────────────────────────────────

TOPIK LAINNYA

...

Divider harus sangat subtle, bukan garis hitam tebal.

Gunakan warna yang masih satu keluarga dengan palette aplikasi.

Tujuannya agar user secara visual langsung memahami:

"Ini sudah masuk bagian baru."

==================================================
2. KONSISTENSIKAN STRUKTUR 3 PILAR
==================================================

Aplikasi memiliki tiga pilar:

PILAR PERTAMA
Kenali

PILAR KEDUA
Pahami

PILAR KETIGA
Temukan

Buat ketiga halaman memiliki design language yang konsisten.

Misalnya:

[PILAR LABEL]

[PAGE TITLE]

[PAGE DESCRIPTION]

[PRIMARY ACTION]

────────────────────────────

[SECTION LABEL]

[SECTION DESCRIPTION]

[CONTENT]

Jangan membuat ketiga halaman terasa seperti template yang benar-benar identik.

Struktur boleh konsisten, tetapi masing-masing halaman tetap punya karakter.

==================================================
3. HALAMAN BERANDA
==================================================

Perbaiki hierarchy halaman Beranda.

Struktur yang diinginkan kira-kira:

Hero / Welcome
    ↓
Quick actions
    ↓
────────────────────────
HARI INI
    ↓
Mood + Journal summary
    ↓
────────────────────────
UNTUKMU
    ↓
Recommended activity/content

Jangan biarkan "Hari ini" dan "Untukmu" hanya terlihat seperti teks yang muncul setelah whitespace.

Berikan boundary visual yang jelas.

Quick action:

- Tulis jurnal
- Catat mood
- Ngobrol santai

tetap sederhana dan tidak terlalu besar.

==================================================
4. HALAMAN KENALI
==================================================

Struktur visual:

PILAR PERTAMA

Kenali

Deskripsi

[ Tulis entri baru ]

────────────────────────────

CATATAN TERAKHIR

[ Journal card ]

────────────────────────────

KEBIASAAN HARI INI

[ Mood tracker ]

Pastikan "Catatan terakhir" dan "Kebiasaan hari ini" terasa seperti section yang berbeda.

==================================================
5. HALAMAN PAHAMI
==================================================

Struktur:

PILAR KEDUA

Pahami

Deskripsi

[ Mulai refleksi baru ]

────────────────────────────

REFLEKSI TERAKHIR

[ Reflection item/card ]

Jika tidak ada data, tampilkan empty state yang tetap terasa intentional dan tidak seperti error.

==================================================
6. HALAMAN TEMUKAN
==================================================

Struktur:

PILAR KETIGA

Temukan

Deskripsi

────────────────────────────

UNTUKMU

Deskripsi

[ Card ] [ Card ]
[ Card ] [ Card ]

Jika ada section lain, pisahkan dengan divider.

Untuk content cards:

- tetap minimal
- jangan terlalu banyak shadow
- jangan terlalu banyak border
- gunakan typography hierarchy
- metadata kecil
- CTA sederhana
- jangan membuat card terlalu tinggi

==================================================
7. DETAIL JURNAL / REFLEKSI
==================================================

Halaman detail juga harus mempunyai hierarchy yang jelas.

Misalnya:

← Kembali

[Judul]
[Date]

────────────────────────────

[Isi jurnal]

────────────────────────────

REFLEKSI AI

[ AI reflection interface ]

Action seperti:

- Ubah
- Hapus
- Minta refleksi

harus memiliki hierarchy yang jelas.

Jangan membuat action destructive terlihat sama pentingnya dengan primary action.

==================================================
8. CARD SYSTEM
==================================================

Jangan menggunakan card untuk setiap elemen.

Gunakan card hanya untuk:

- journal entry
- reflection
- recommendation
- mood tracker
- content item

Untuk section heading, gunakan typography + divider.

Card harus terasa sebagai "container untuk sebuah objek", bukan sebagai cara utama untuk membagi seluruh halaman.

==================================================
9. SPACING SYSTEM
==================================================

Buat spacing system yang konsisten.

Jangan menggunakan margin/padding random di setiap halaman.

Gunakan spacing hierarchy:

small
medium
large
section

Section-to-section spacing harus lebih besar daripada spacing antar elemen di dalam section.

Namun jangan sampai halaman terasa kosong.

==================================================
10. CONTENT WIDTH
==================================================

Pastikan content width nyaman dibaca.

Untuk halaman berbasis teks:
gunakan max-width sekitar 900–960px.

Untuk halaman grid/recommendation:
gunakan max-width sekitar 1000–1100px jika memang dibutuhkan.

Jangan membuat teks terlalu panjang dalam satu baris.

==================================================
11. TYPOGRAPHY
==================================================

Pertahankan karakter editorial.

Heading:
- serif
- cukup besar
- tidak terlalu bold

Body:
- sans-serif
- readable
- muted

Section label:
- uppercase
- letter spacing
- ukuran kecil
- accent color

Gunakan hierarchy yang jelas antara:

Page title
Section title
Card title
Body
Metadata
CTA

==================================================
12. COLOR SYSTEM
==================================================

Jangan mengganti palette secara drastis.

Pertahankan warm/calm palette.

Gunakan beberapa level background:

Page background
→ warm cream

Section background
→ sedikit lebih terang/berbeda

Card background
→ putih/off-white

Border
→ sangat subtle

Accent
→ muted terracotta/brown

Tujuannya bukan membuat banyak warna.

Tujuannya membuat layering visual.

==================================================
13. ADMIN INTERFACE
==================================================

SETELAH memahami `quickstart.md`, buat juga tampilan untuk ADMIN.

WAJIB membaca `quickstart.md` terlebih dahulu untuk mengetahui:

- role admin
- authentication
- data yang tersedia
- endpoint/API
- struktur database
- fitur admin
- aturan akses

Jangan mengarang fitur admin yang bertentangan dengan `quickstart.md`.

Buat admin interface yang secara visual masih satu keluarga dengan Ruang Kita, tetapi boleh sedikit lebih utilitarian daripada user interface.

Admin tidak perlu terlihat seperti aplikasi yang sepenuhnya berbeda.

Admin harus memiliki:

- Admin layout
- Sidebar/navigation
- Header
- Dashboard
- Data management
- User management jika memang didukung oleh backend
- Journal/reflection/content management sesuai fitur yang tersedia
- Mood/content/activity management jika tersedia
- Statistik jika data yang dibutuhkan tersedia
- Empty state
- Loading state
- Error state
- Confirmation state untuk destructive action

Gunakan tabel untuk data yang memang lebih cocok ditampilkan sebagai tabel.

Gunakan card/statistik hanya untuk summary.

Jangan membuat admin dashboard hanya berisi banyak kotak statistik.

==================================================
14. ADMIN INFORMATION ARCHITECTURE
==================================================

Buat struktur admin berdasarkan functionality yang benar-benar tersedia.

Contoh struktur yang dapat digunakan jika sesuai dengan `quickstart.md`:

Dashboard

Users
    - User list
    - User detail

Content
    - Articles
    - Exercises
    - Recommendations

Journal / Reflection
    - Entries
    - Reflections

Mood / Activity
    - Mood data
    - Activity data

Settings

Namun:
JANGAN membuat menu yang tidak didukung oleh backend.

Jika sebuah fitur belum tersedia, jangan pura-pura membuat functionality lengkap.

Prioritaskan UI yang terhubung ke data nyata.

==================================================
15. RESPONSIVE DESIGN
==================================================

Semua halaman harus responsive.

Desktop:
- centered content
- comfortable width
- sidebar untuk admin

Tablet:
- layout menyesuaikan
- grid dapat berubah menjadi 1 atau 2 kolom

Mobile:
- navigation menjadi mobile navigation
- card menjadi single column
- typography menyesuaikan
- spacing lebih compact
- tidak ada horizontal overflow

==================================================
16. ACCESSIBILITY
==================================================

Pastikan:

- contrast cukup
- button memiliki state
- focus state tersedia
- semantic HTML digunakan
- form memiliki label
- interactive element dapat diakses keyboard
- jangan menggunakan warna sebagai satu-satunya indikator status

==================================================
17. JANGAN MERUSAK FUNCTIONALITY
==================================================

Ini SANGAT PENTING.

Sebelum mengubah komponen:

- pahami existing behavior
- pahami routing
- pahami API
- pahami state management
- pahami authentication

UI refinement tidak boleh merusak:

- login
- logout
- journal
- reflection
- mood
- recommendation
- navigation
- API integration
- database interaction
- authentication
- existing CRUD

Jika functionality sudah bekerja, pertahankan.

==================================================
18. JANGAN OVERENGINEERING
==================================================

Jangan:

- menambahkan library baru tanpa alasan
- mengganti framework
- mengganti architecture
- mengganti database
- membuat design system yang terlalu kompleks
- membuat abstraction yang tidak diperlukan

Gunakan component dan styling system yang sudah ada di project.

==================================================
19. IMPLEMENTATION PROCESS
==================================================

Kerjakan dalam urutan:

STEP 1
Audit project.

STEP 2
Baca `quickstart.md`.

STEP 3
Identifikasi existing UI structure.

STEP 4
Identifikasi masalah hierarchy dan section separation.

STEP 5
Buat design system kecil:
- colors
- typography
- spacing
- border
- radius
- section divider
- card

STEP 6
Refactor layout secara reusable.

STEP 7
Perbaiki:
- Beranda
- Kenali
- Pahami
- Temukan
- Detail journal/reflection

STEP 8
Implement admin interface berdasarkan `quickstart.md`.

STEP 9
Hubungkan admin dengan existing backend/API.

STEP 10
Test semua existing functionality.

STEP 11
Test responsive layout.

STEP 12
Periksa console untuk error.

STEP 13
Periksa route yang rusak.

STEP 14
Periksa authentication/authorization.

==================================================
20. HASIL AKHIR YANG SAYA INGINKAN
==================================================

Saya ingin ketika melihat aplikasi ini, kesan pertamanya adalah:

"Ini aplikasi personal journal/wellness yang tenang dan premium."

Bukan:

"Ini dashboard dengan banyak card."

DESAIN HARUS:

- minimalis
- tenang
- personal
- editorial
- memiliki hierarchy yang jelas
- section terasa terpisah
- whitespace tetap digunakan tetapi memiliki tujuan
- tidak terlalu ramai
- tidak terlalu banyak card
- tidak terlalu banyak warna
- konsisten antar halaman

Masalah utama yang harus diselesaikan adalah:

"Minimalis tetapi tidak terasa seperti semua elemen mengambang di ruang kosong."

Buat setiap section memiliki identitas visual yang jelas melalui:

- label
- typography
- divider
- spacing
- subtle background
- grouping

==================================================
SETELAH SELESAI
==================================================

Jangan hanya mengatakan "sudah selesai".

Berikan ringkasan:

1. Apa saja yang diubah pada user UI.
2. Apa saja yang diubah pada admin UI.
3. Component apa yang dibuat/refactor.
4. Route baru yang dibuat.
5. API yang digunakan.
6. Apakah ada functionality yang belum dapat diimplementasikan dan alasannya.
7. Apakah ada dependency baru.
8. Hasil testing.
9. Error yang ditemukan jika ada.

Dan yang paling penting:

JANGAN mengorbankan functionality demi visual.

Fokus utama:
VISUAL HIERARCHY + SECTION SEPARATION + CONSISTENCY + USABILITY.