# scripts/

UI geliştirme & görsel QA yardımcıları.

## snap.py — Visual Snapshot

Streamlit uygulamasından her sayfanın yüksek-çözünürlüklü PNG'sini alır.

### Kurulum (bir kez)
```bash
pip install playwright
playwright install chromium
```

Chromium tarayıcı ~150MB indirir. Kurulum tamamlanınca:

### Kullanım
```bash
# Streamlit'i ayrı terminalde aç:
streamlit run web_app.py

# Tüm sayfalar (1440x900, retina):
python scripts/snap.py

# Tek sayfa:
python scripts/snap.py --page dashboard

# Farklı viewport:
python scripts/snap.py --viewport 1920x1080

# Mobile breakpoint test:
python scripts/snap.py --viewport 414x896
```

Çıktı: `scripts/snapshots/dashboard_1440x900.png` vb.

### Workflow
1. UI değişikliği yap
2. `snap.py` çalıştır
3. Önceki snapshot'la görsel kıyas (Git diff PNG değil, gözle bak veya
   `compare` aracıyla diff)
4. Regresyon yoksa commit
