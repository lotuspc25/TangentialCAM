# TangentialCAM

TangentialCAM, CNC tangential knife (teğetsel bıçak) makineleri için
STL tabanlı otomatik yol üretimi yapan bir CAM yazılımıdır.

Bu yazılım:
- STL dosyasını işler
- Concave outline (dış kontur) çıkarır
- Tangential (A ekseni) açılarını hesaplar
- Z derinlikli veya Z’siz G-kodu üretir
- 2D ve 3D görsel önizleme sağlar

## 🚀 Özellikler

- STL yükleme ve 3D görüntüleme (OpenGL)
- Concave kontur çıkarma (Shapely + Trimesh)
- XY + Z + A ekseni yol oluşturma
- G54 parça orjini seçenekleri (sol alt / sağ üst / merkez vb.)
- Bıçak yönü ofseti (0°, 90°, 180° vs.)
- Z takibi olan ve olmayan G-kodu üretimi
- Renk temaları ve görünüm ayarları
- Tüm ayarların `tangential_cam.ini` içinde saklanması

## 📦 Kurulum

```bash
pip install -r requirements.txt
python main.py
