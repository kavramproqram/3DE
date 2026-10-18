# KüpÇiz (3DE) — yalnızca küplerden oluşan 3B çizim aracı

## Dosyalar
| Dosya | Görev |
|---|---|
| `mkj_editorler.py` | **Çalıştırılan dosya.** Editörler + ana pencere |
| `mkj_cube_draw.py` | Sahne, 3B görünüm (OpenGL), küp editörü, renk penceresi, dosya işlemleri |
| `mkj_pencere.py` | Blender tarzı alan (pencere) sistemi — değişmedi |
| `requirements.txt` | Python bağımlılıkları |

## Kurulum
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Çalıştırma
```bash
python3 mkj_editorler.py              # boş sahne
python3 mkj_editorler.py dosya.mkj    # dosya açarak
python3 mkj_cube_draw.py              # sade tek pencere sürümü (alan sistemi yok)
```

## Derleme (tek dosya çalıştırılabilir)
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name KupCiz mkj_editorler.py
# çıktı: dist/KupCiz   (Windows: dist/KupCiz.exe)
```
Söz dizimi denetimi: `python3 -m py_compile mkj_cube_draw.py mkj_editorler.py mkj_pencere.py`

## Yeni özellikler
**Malzeme kaydırıcısı** — Küp Editörü → *Renk* → *Tek Renk Seç / Karışıma Renk Ekle*.
Siyahlık kaydırıcısının sağında 3 konumlu kaydırıcı:
* **+1 Saydam:** renkle karışık şeffaflık. Renk `#000000` ise tam saydam, renk açıldıkça opaklaşır.
* **0 Normal.**
* **−1 Ayna:** renkle karışık yansıma. Renk `#000000` ise tam yansıtıcı, renk açıldıkça rengine döner.
Seçim kalemle boyanan piksellere uygulanır (damlalık da malzemeyi okur). Malzeme, pikselin alfa
kanalında saklanır (255 normal, 254 saydam, 253 ayna); `.mkj` dosyalarıyla birlikte kaydedilir.

**Oyun modu (Space aç/kapa)** — görünmez, kusursuz bir küre kameradır; yürümez, küplerin üzerinde süzülür.
İlk eklenen küpün üstünden başlar. `W/A/S/D` süzül, `Shift` hızlı, fare sürükle veya ok tuşları ile bak,
`Space`/`Esc` çıkış. Küplerin dışına çıkarsa çıktığı noktadan önceki konuma geri döner.
Oyun modunda ızgara ve imleç çizgileri gizlenir; yalnızca küpler görünür.

**Yalnızca küp:** silindir, koni, küre, piramit, mesh/UV/malzeme-nesne kodu ve ilgili tüm menüler silindi.
Eski dosyalardaki `objects` / `object_instances` kayıtları yok sayılır.
