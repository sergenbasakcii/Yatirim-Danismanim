"""
HedgeFund AI — Eğitim & Farkındalık Motoru  (v2 — Institutional Grade)
Her yatırım kararı yanında bağlamsal, üst düzey eğitim notları üretir.

Yeni v2 özellikleri:
  • Zamanlama kalitesi notları ("doğru varlık, yanlış zaman" analizi)
  • Conviction score eğitimi
  • Senaryo ağacı kavram açıklaması
  • Multi-dimensional (6 eksen) değerlendirme notları
  • Alternatif maliyet farkındalığı
  • Kurumsal seviye risk metrikleri (VaR, CVaR, Sortino)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BAĞLAMSAL NOTLAR
# ══════════════════════════════════════════════════════════════════════════════

_CONTEXT_NOTES: dict = {
    # ── Teknik Sinyaller ─────────────────────────────────────────────────────
    "rsi_oversold": (
        "RSI {rsi:.0f} — aşırı satım bölgesinde. Teknik toparlanma potansiyeli yüksek; "
        "ancak RSI tek başına sinyal değildir. Hacim onayı ve trend yönü ile birlikte "
        "değerlendirin. En güçlü alım sinyali: RSI oversold + EMA destek + yüksek hacim."
    ),
    "rsi_overbought": (
        "RSI {rsi:.0f} — aşırı alım bölgesi. Güçlü trendlerde bu seviye uzun süre korunabilir. "
        "Ancak yeni pozisyon için düzeltme beklemenizi öneririz. Mevcut pozisyon varsa "
        "trailing stop-loss ile kârları koruyun."
    ),
    "high_volatility": (
        "Volatilite %{vol:.0f} — yüksek oynaklık. Hem kazanç hem kayıp potansiyeli yüksek. "
        "Pozisyon büyüklüğünü portföyünüzün maksimum %{max_pos:.0f}'i ile sınırlayın. "
        "Yüksek volatiliteli varlıklarda stop-loss kullanımı kritik: duygusal kararları engeller."
    ),
    "macd_bullish": (
        "MACD histogram pozitife döndü — kısa vadeli momentum değişiminin ilk sinyali. "
        "Güçlü entry göstergesi; ama fiyatın önemli destek veya trend çizgisi üzerinde olması "
        "bu sinyali güçlendirir. MACD gecikmelidir — ani reversalda yanıltabilir."
    ),
    "macd_bearish": (
        "MACD histogram negatife döndü — momentum zayıflıyor. Mevcut pozisyonda "
        "stop-loss seviyesini gözden geçirin. Yeni alım için trend onayı bekleyin."
    ),
    "breakout": (
        "Direnç kırılımı tespit edildi. Gerçek kırılımlar yüksek hacimle desteklenir — "
        "hacim eşlik etmiyorsa 'sahte kırılım' riski var. Kırılım sonrası eski direnç, "
        "yeni destek olarak test edilebilir: ideal giriş fırsatı bu test anında."
    ),
    "drawdown_high": (
        "Geçmişte %{dd:.0f} maksimum düşüş yaşandı. Bu varlık size o kadar kayıp yaşatabilir. "
        "Tolere edebilir misiniz? Değilse pozisyon büyüklüğünü buna göre düzenleyin. "
        "Max drawdown, risk toleransınızı gerçekçi test eden en önemli metriktir."
    ),
    "diversification": (
        "Portföyde {n} farklı varlık var. Çeşitlendirme riski dağıtır; ama aşırı çeşitlendirme "
        "getirileri sulandırır. Kritik kural: birbiriyle yüksek korelasyonlu varlıklar gerçek "
        "çeşitlendirme sağlamaz. 10 teknoloji hissesi = 1 teknoloji hissesi riski."
    ),
    "dollar_cost_averaging": (
        "DCA stratejisi: büyük miktarı tek seferde değil, belirli aralıklarla alın. "
        "Volatilite riskini ortalama, psikolojik stresi azaltır. "
        "Özellikle belirsiz piyasalarda ve uzun vadeli birikimde en etkili strateji."
    ),
    "stop_loss": (
        "Stop-loss, disiplinli risk yönetiminin temel aracı. Duygusal 'beklerim çıkar' "
        "tuzağından korur ve maksimum kaybınızı önceden tanımlar. "
        "Başlangıç yatırımının %{pct:.0f}'inden fazla risk almamanızı öneririz."
    ),
    "sharp_drop": (
        "Son dönemde %{drop:.0f} düşüş var. 'Düşen bıçağı tutmak' tehlikelidir — "
        "stabilizasyon sinyali olmadan alım genellikle erken giriş demektir. "
        "RSI'ın dipten döndüğünü ve hacimin arttığını görene kadar bekleyin."
    ),
    "momentum_strong": (
        "Güçlü momentum — trend içinde bir varlık. Trend arkadaşınızdır ilkesini uygulayın. "
        "Ama momentum varlıkları hem hızlı yükselir hem hızlı tersine döner. "
        "Trailing stop-loss ile kârları kilitleyin; açgözlülük büyük kazançları geri alır."
    ),
    "crypto_specific": (
        "Kripto varlıklar 7/24 işlem görür ve geleneksel finansal analizden farklı dinamiklere sahip. "
        "Funding rate, open interest ve whale hareketleri de izlenmeli. "
        "Hafta sonu likiditesi düşük — büyük haberler bu dönemde sert etki yaratabilir."
    ),
    "bist_specific": (
        "BIST hisseleri TL bazlıdır. Kur değişimi, enflasyon ve TCMB kararları doğrudan etkiler. "
        "Döviz geliri olan şirketler (THYAO, EREGL, TUPRS) kur riski yerine kur avantajı sunar. "
        "Yabancı yatırımcı akışını ve swap maliyetlerini düzenli takip edin."
    ),
    "etf_advantage": (
        "ETF, tek işlemle düzinelerce varlığa erişim sağlar. Düşük TER (gider oranı) ve "
        "yüksek likidite en büyük avantajlardır. Pasif piyasa getirisi arayan uzun vadeli "
        "yatırımcılar için ideal: aktif fonların %80'inden daha iyi performans gösterir."
    ),
    "position_sizing": (
        "Pozisyon büyüklüğü en önemli risk kontrol aracınızdır. Tek varlığa portföyün "
        "%{pct:.0f}'inden fazlasını koymak konsantrasyon riski yaratır. "
        "Küçük pozisyonlar, büyük hatalar yapmaktan korur — bunu bir kural haline getirin."
    ),

    # ── Zamanlama Analizi (v2 yeni) ──────────────────────────────────────────
    "timing_good": (
        "⏰ Zamanlama İYİ — Teknik yapı şu anda alım için elverişli. RSI makul bölgede, "
        "fiyat destek yakınında ve trend olumlu. Bu durum, iyi bir varlık seçimini daha da "
        "güçlü bir fırsata dönüştürür. Giriş için uygun pencere açık."
    ),
    "timing_neutral": (
        "⏰ Zamanlama ORTA — Varlık kaliteli, ama giriş noktası ideal değil. "
        "Daha iyi bir giriş için biraz beklemek toplam getiriyi artırabilir. "
        "Kademeli giriş (DCA) bu belirsizliği yönetmenin akıllıca yolu."
    ),
    "timing_bad": (
        "⚠️ Doğru Varlık, Yanlış Zaman — Varlık uzun vadede değerli olabilir; "
        "ama şu an teknik yapı, fiyatın geri çekilme olasılığının yüksek olduğunu gösteriyor. "
        "Acele alım yapmak ortalama maliyetinizi yükseltir. İzle ve bekle modu önerilir."
    ),
    "timing_very_bad": (
        "🔴 Zamanlama OLUMSUZ — Fiyat kısa vadede aşırı uzamış veya düşüş trendi güçlü. "
        "En iyi varlık bile yanlış zamanda alındığında uzun süre olumsuz bölgede kalabilir. "
        "Teknik yapı düzelene kadar bu pozisyona girmeyin."
    ),
    "chasing_momentum": (
        "⚠️ Momentum Kovalama Riski — Varlık son {days} günde %{pct:.0f} yükseldi. "
        "Bu hareketi kaçırdıysanız, arkasından koşmak risk/ödül dengesini ciddi bozar. "
        "Yeni ATH yakınında alım yapmak istatistiksel olarak olumsuz beklenen değer sunabilir."
    ),
    "dip_opportunity": (
        "💡 Geri Çekilme Fırsatı — Varlık kısa vadeli geri çekilme yaşıyor. "
        "Uzun vadeli trend sağlıklıysa bu tür çekilmeler en iyi giriş noktalarını oluşturur. "
        "Destek seviyelerini ve RSI'ı teyit edin, sonra kademeli giriş değerlendirin."
    ),

    # ── Conviction & Karar (v2 yeni) ────────────────────────────────────────
    "high_conviction": (
        "🎯 Yüksek Güven Seviyesi — Bu fırsat, birden fazla bağımsız faktörde güçlü sinyal "
        "veriyor: teknik, momentum ve risk-ödül bir arada olumlu. Yüksek conviction fırsatlar "
        "için normal pozisyon büyüklüğünüzün 1.5x'ine kadar çıkabilirsiniz — ama hiçbir zaman "
        "tek pozisyona portföyün %20'sinden fazlasını koymayın."
    ),
    "low_conviction": (
        "❓ Düşük Güven Seviyesi — Sinyaller karışık veya yetersiz. Bu tür pozisyonlar için "
        "minimum pozisyon büyüklüğünü tercih edin. Düşük conviction fırsatları izleme listesinde "
        "tutun; güçlü bir tetikleyici sinyal geldiğinde büyütmeyi düşünün."
    ),

    # ── Senaryo Ağacı (v2 yeni) ──────────────────────────────────────────────
    "scenario_bull": (
        "📈 Boğa Senaryosu — En iyi durumda katalizörler devreye giriyor, "
        "trend güçlenip hedeflere ulaşılıyor. Bu senaryo gerçekleşirse ne yapacağınızı "
        "önceden belirleyin: kısmi kâr realizasyonu mu, trailing stop-loss mu, yoksa tutmaya mı devam?"
    ),
    "scenario_base": (
        "📊 Baz Senaryo — En olası sonuç: mevcut trend devam eder, makul getiri elde edilir. "
        "Pozisyonun büyük bölümünü bu senaryoya göre boyutlandırın."
    ),
    "scenario_bear": (
        "📉 Ayı Senaryosu — Kötü sonuç gerçekleşirse ne yaparsınız? Bu soruyu "
        "pozisyona girmeden önce yanıtlayın. Stop-loss seviyeniz ayı senaryosunu "
        "yönetmenin en rasyonel yoludur — duygusal değil, mekanik çalışır."
    ),

    # ── Risk Metrikleri (v2 yeni) ─────────────────────────────────────────────
    "var_explanation": (
        "📊 VaR (Value at Risk) %95 — Gelecek ay %{var:.1f} veya daha fazla kaybetme "
        "olasılığı %5. Yani 20 ayın birinde bu kayıptan fazlasını yaşayabilirsiniz. "
        "Bu rakamı tolere edip edemeyeceğinizi gerçekçi değerlendirin."
    ),
    "portfolio_sharpe": (
        "📐 Portföy Sharpe Oranı: {sharpe:.2f} — Her birim risk için {sharpe:.2f} birim fazla getiri. "
        "1.0 üzeri iyi, 1.5 üzeri çok iyi, 2.0 üzeri mükemmel kabul edilir. "
        "Bu oranı artırmak için düşük korelasyonlu varlıklar ekleyin."
    ),
    "correlation_warning": (
        "⚠️ Korelasyon Uyarısı — Portföydeki {asset1} ve {asset2} benzer koşullarda "
        "aynı yönde hareket etme eğiliminde. Bu, çeşitlendirmeden beklenen riski azaltma "
        "etkisini zayıflatır. Biri negatif korelasyonlu bir varlıkla (altın, tahvil) dengelenebilir."
    ),

    # ── Alternatif Maliyet (v2 yeni) ─────────────────────────────────────────
    "opportunity_cost": (
        "💰 Alternatif Maliyet — Bu paraya yatırım yaparken şunu sorun: 'Başka nerede kullanabilirdim?' "
        "Risk-free oran %5 (ABD Hazine). Bu yatırımın beklenen getirisi, risk toleransınızı "
        "göz önünde bulundurduğunuzda bu eşiği yeterince aşıyor mu?"
    ),
    "better_alternatives_exist": (
        "🔄 Daha İyi Alternatifler Mevcut — Aynı risk sınıfında şu an daha güçlü sinyal veren "
        "fırsatlar var. Bu varlığa yatırım yapmadan önce alternatif fırsatları karşılaştırın. "
        "Portföy optimizasyonunun özü: her pozisyon en iyi alternatife karşı değerlendirmeye tabi tutulur."
    ),

    # ── Portföy İnşa (v2 yeni) ───────────────────────────────────────────────
    "kelly_sizing": (
        "📐 Kelly Kriteri — Matematiksel optimal pozisyon büyüklüğü: %{kelly:.0f}. "
        "Pratikte 'Quarter-Kelly' (%{quarter:.0f}) kullanmanızı öneririz — tam Kelly "
        "büyük dalgalanma yaratabilir. Amaç: uzun vadeli bileşik büyümeyi maksimize etmek."
    ),
    "volatility_adjusted": (
        "⚖️ Volatilite Ağırlıklı Dağılım — Risk paritesi yaklaşımında her varlık, "
        "volatilitesiyle ters orantılı ağırlık alır: yüksek oynaklı varlık daha az ağırlık. "
        "Bu yöntem portföy riskini eşit dağıtır ve Sharpe oranını iyileştirir."
    ),
    "rebalancing_note": (
        "🔄 Yeniden Dengeleme — Piyasa hareketleri zamanla orijinal ağırlıkları bozar. "
        "Hedef ağırlıktan %5 veya daha fazla sapma görürseniz yeniden dengeleyin. "
        "Yılda 1-4 kez dengeleme genellikle en iyi maliyet-etkinlik dengesi sunar."
    ),
}

# ══════════════════════════════════════════════════════════════════════════════
# KAVRAM AÇIKLAMALARI  (v2 — genişletildi)
# ══════════════════════════════════════════════════════════════════════════════

_CONCEPTS: dict = {
    "rsi": {
        "title": "RSI (Göreceli Güç Endeksi)",
        "explanation": (
            "RSI 0-100 arasında momentum ölçer: son dönem kazanç ve kayıpları karşılaştırır. "
            "70 üzeri aşırı alım, 30 altı aşırı satım bölgesi. Trendlerde uzun süre bu "
            "seviyelerde kalabilir — tek başına yeterli değil."
        ),
        "example": "BTC RSI = 28 → Geçmişte bu bölge çoğunlukla teknik toparlanmaya zemin hazırladı.",
        "tip": "RSI + EMA pozisyonu + hacim onayı: üçü birlikte çok daha güvenilir sinyal.",
    },
    "macd": {
        "title": "MACD (Hareketli Ortalama Yakınsama/Iraksama)",
        "explanation": (
            "EMA12 - EMA26 farkı. Histogram pozitife döndüğünde yükseliş momentumu güçleniyor. "
            "Signal line kesişimleri alım/satım sinyali üretir. Gecikmelidir; ani hareketlerde yanıltabilir."
        ),
        "example": "MACD histogram 0'dan yukarı geçiş + yüksek hacim → güçlü alım sinyali.",
        "tip": "MACD daily grafikte çok daha güvenilir; 1 saatlik grafiklerde çok gürültülü.",
    },
    "ema": {
        "title": "EMA (Üstel Hareketli Ortalama)",
        "explanation": (
            "Son fiyatlara daha fazla ağırlık vererek trend yönünü gösterir. "
            "EMA20 kısa, EMA50 orta, EMA200 uzun vade. EMA200 üzeri = uzun vadeli yükseliş trendi."
        ),
        "example": "Fiyat > EMA20 > EMA50 > EMA200 → mükemmel bull alignment.",
        "tip": "EMA200 'altın kuralı': fiyat EMA200'ün altındayken yeni alımda dikkatli olun.",
    },
    "bollinger_bands": {
        "title": "Bollinger Bandı",
        "explanation": (
            "20 günlük ortalama ± 2 standart sapma bandı. Fiyat alt banda yaklaşınca aşırı satım, "
            "üst banda yaklaşınca aşırı alım değerlendirmesi yapılır. Bant daralması = sıkışma."
        ),
        "example": "BB alt bandı dokunuşu + hacim düşük + RSI oversold → potansiyel reversal.",
        "tip": "BB Squeeze (bantlar daraldığında) sonrası büyük kırılım gelir — yönü tahmin etmek zor.",
    },
    "sharpe_ratio": {
        "title": "Sharpe Oranı",
        "explanation": (
            "Alınan birim risk başına fazla getiri. (Getiri - Risksiz Oran) / Volatilite. "
            "1+ iyi, 2+ mükemmel, negatif: risk karşılıksız kalmış."
        ),
        "example": "Sharpe 1.8 → her birim risk için 1.8 birim net getiri üretiliyor.",
        "tip": "Sharpe sadece yukarı-aşağı volatiliteyi ölçer; Sortino (sadece aşağı) daha adil.",
    },
    "sortino_ratio": {
        "title": "Sortino Oranı",
        "explanation": (
            "Sharpe'ın gelişmiş versiyonu: yalnızca negatif volatiliteyi (downside deviation) "
            "cezalandırır. Pozitif oynaklığı risk olarak saymaz — çok daha adil bir ölçüt."
        ),
        "example": "Sortino 2.5 → negatif dalgalanmaya karşılık güçlü fazla getiri üretiyor.",
        "tip": "Kurumsal portföylerde Sharpe yerine Sortino tercih edilmesi giderek yaygınlaşıyor.",
    },
    "max_drawdown": {
        "title": "Maksimum Drawdown",
        "explanation": (
            "Tepe noktasından dip noktasına en büyük düşüş yüzdesi. "
            "Risk toleransınızı gerçek stresle test eden en önemli metrik."
        ),
        "example": "Max DD = -%45 → 10.000$'lık yatırım 5.500$'a düşebilir.",
        "tip": "Kendi toleransınızdan yüksek DD'li varlıklarda pozisyon büyüklüğünü küçütün.",
    },
    "volatility": {
        "title": "Volatilite (Oynaklık)",
        "explanation": (
            "Yıllıklaştırılmış standart sapma: fiyatın ortalamadan sapması. "
            "Yüksek volatilite = hem büyük kazanç hem büyük kayıp potansiyeli."
        ),
        "example": "Vol %80 → kripto seviyesi. Vol %12 → büyük cap hisse seviyesi.",
        "tip": "Volatilite tek başına risk değildir — pozisyon büyüklüğünüzü buna göre ayarlarsanız yönetilebilir.",
    },
    "var": {
        "title": "VaR (Riske Maruz Değer)",
        "explanation": (
            "Belirli güven aralığında maksimum beklenen kayıp. 95% VaR = %5 olasılıkla "
            "bu miktardan daha fazla kaybedebilirsiniz. Portföy risk ölçümünde standart."
        ),
        "example": "Aylık VaR %95 = %12 → 20 ayın birinde %12'den fazla kayıp yaşayabilirsiniz.",
        "tip": "VaR normal dağılım varsayar; kriz dönemlerinde 'tail risk' çok daha büyük.",
    },
    "momentum": {
        "title": "Momentum",
        "explanation": (
            "Bir varlığın belirli dönemdeki fiyat ivmesi. "
            "Güçlü momentum devam etme eğilimindedir — trend arkadaşınızdır."
        ),
        "example": "3 aylık getiri +35% → güçlü pozitif momentum, trend devam edebilir.",
        "tip": "Momentum tersine dönüşler hızlı ve sert olur; trailing stop-loss kritik.",
    },
    "stop_loss": {
        "title": "Stop-Loss (Zarar Kes)",
        "explanation": (
            "Belirlenen fiyata düşünce otomatik satış. Duygusal 'beklerim çıkar' tuzağından korur. "
            "Maksimum kaybınızı önceden tanımlarsınız."
        ),
        "example": "100$ alım, 92$ stop-loss → maksimum %8 kayıp önceden belirlendi.",
        "tip": "Stop-loss seviyenizi pozisyon girmeden çizin — girişten sonra değil.",
    },
    "diversification": {
        "title": "Çeşitlendirme",
        "explanation": (
            "Farklı varlık sınıfları ve sektörlere yayılarak riski dağıtma. "
            "Kritik: düşük korelasyonlu varlıklar gerçek çeşitlendirme sağlar."
        ),
        "example": "BTC + Altın + SPY + TLT → 4 farklı makro koşulda farklı tepkiler.",
        "tip": "10 teknoloji hissesi = 1 teknoloji hissesi riski. Sektör çeşitlendirmesine dikkat.",
    },
    "risk_reward": {
        "title": "Risk/Ödül Oranı",
        "explanation": (
            "Potansiyel kazancın potansiyel kayba oranı. "
            "1:2+ oranlar (1 birim risk → 2 birim kazanç) iyi işlem kriterleri."
        ),
        "example": "Stop %5 aşağı, hedef %15 yukarı → 1:3 risk/ödül.",
        "tip": "Düşük başarı oranı (%40) bile 1:3 risk/ödül ile kârlı strateji olabilir.",
    },
    "kelly_criterion": {
        "title": "Kelly Kriteri",
        "explanation": (
            "Uzun vadede bileşik büyümeyi maksimize eden matematiksel pozisyon büyüklüğü formülü. "
            "f* = (kazanma olasılığı × kazanç oranı - kaybetme olasılığı) / kazanç oranı."
        ),
        "example": "Full Kelly %40 öneriyorsa, Quarter-Kelly %10 kullanın — daha az dalgalanma.",
        "tip": "Full Kelly teorik optimaldir; pratikte kaldıraç etkisi yaratır. Quarter-Kelly tercih edin.",
    },
    "dca": {
        "title": "DCA (Dolar Maliyet Ortalama)",
        "explanation": (
            "Sabit aralıklarla sabit miktarda yatırım. Fiyat düşünce daha fazla, "
            "yükselince daha az birim alınır — zaman içinde maliyet dengelenir."
        ),
        "example": "Her ay 500$ BTC → 12 alımda ortalama maliyet piyasa ortalamasına yaklaşır.",
        "tip": "DCA psikolojik stresi azaltır, zamanlama hatalarına karşı korur. Uzun vade için ideal.",
    },
    "conviction_score": {
        "title": "Conviction Skoru",
        "explanation": (
            "Bir yatırım kararına olan toplam güven puanı. Fırsat kalitesi × zamanlama kalitesi "
            "ile hesaplanır. Yüksek conviction = hem fırsat hem zamanlama iyi. "
            "Düşük conviction = fırsat var, ama giriş noktası veya sinyal yetersiz."
        ),
        "example": "Conviction 82/100 → güçlü çok-faktörlü onay, uygun pozisyon büyütme alanı.",
        "tip": "Conviction skoruna göre pozisyon büyüklüğünü ayarlayın: 80+ tam, 60-80 yarım, <60 minimal.",
    },
    "catalyst_map": {
        "title": "Katalizör Haritası",
        "explanation": (
            "Bir varlığın fiyat hareketini tetikleyebilecek olayların yapılandırılmış listesi. "
            "Her katalizör olasılık ve etki büyüklüğü ile değerlendirilir."
        ),
        "example": "Kazanç raporu (yüksek olasılık, orta etki) + Fed kararı (orta olasılık, yüksek etki).",
        "tip": "Katalizörler gerçekleşmediğinde veya beklentilerin altında kalırsa 'sell the news' riski var.",
    },
    "scenario_tree": {
        "title": "Senaryo Ağacı",
        "explanation": (
            "Bir yatırımın üç olası geleceği: boğa (en iyi), baz (en olası), ayı (en kötü). "
            "Her senaryoya olasılık atanır. Pozisyon büyüklüğü baz senaryoya göre belirlenir."
        ),
        "example": "Boğa %30 (+45%), Baz %50 (+18%), Ayı %20 (-22%) → beklenen değer: +%13.6.",
        "tip": "Ayı senaryosunu her zaman en başta değerlendirin: 'Bu kaybı göze alabilir miyim?'",
    },
    "allocation_confidence": {
        "title": "Tahsis Güveni",
        "explanation": (
            "Sistemin bu tahsise olan güven seviyesi. Veri kalitesi, sinyal güçlülüğü ve "
            "portföy uyumu bir arada değerlendirilerek hesaplanır."
        ),
        "example": "Tahsis güveni %85 → çok faktörlü güçlü onay, yüksek kararlılık.",
        "tip": "Düşük tahsis güveni (<50) pozisyon büyüklüğünü yarıya indirin.",
    },
    "market_cap": {
        "title": "Piyasa Değeri",
        "explanation": (
            "Hisse sayısı × fiyat. Mega cap (>200B$) güvenli liman, "
            "small cap (<2B$) yüksek risk/getiri potansiyeli."
        ),
        "example": "Apple ~3T$ → mega cap, düşük likidite riski, savunmacı.",
        "tip": "Small cap hisselerde spread ve likidite riskini her zaman hesaba katın.",
    },
    "correlation": {
        "title": "Korelasyon",
        "explanation": (
            "-1 ile +1 arasında ölçülen ilişki katsayısı. +1: aynı yön, -1: zıt yön, 0: bağımsız. "
            "Düşük korelasyonlu varlıklar gerçek çeşitlendirme sağlar."
        ),
        "example": "BTC-ETH korelasyonu ≈ 0.75 → güçlü pozitif ilişki, birlikte düşer.",
        "tip": "Kriz dönemlerinde korelasyonlar 1'e yaklaşır; çeşitlendirme tam stres testinde zayıflar.",
    },
    "pe_ratio": {
        "title": "F/K Oranı (P/E Ratio)",
        "explanation": (
            "Hisse fiyatı / hisse başı kâr. Sektör ortalamasıyla karşılaştırın. "
            "Düşük F/K değer fırsatı veya sorunlu şirket işareti olabilir."
        ),
        "example": "F/K 10: ucuz mu yoksa sorunlu mu? F/K 40: büyüme beklentisi mi, balon mu?",
        "tip": "F/K sektöre göre anlam kazanır; teknoloji doğal olarak yüksek F/K taşır.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# FIRSAT TİPİ EĞİTİM  (v2 — genişletildi)
# ══════════════════════════════════════════════════════════════════════════════

_OPPORTUNITY_EDUCATION: dict = {
    "momentum": (
        "Momentum yatırımı: güçlü trende sahip varlıkları satın alma. Trend devam ettiği "
        "sürece kârlıdır; ama tersine dönüşler hızlı ve sert olur. Trailing stop-loss "
        "kullanın ve momentum zayıfladığında hızlı hareket edin. Kazananları tutun, kaybedenleri kesin."
    ),
    "deger": (
        "Değer yatırımı: içsel değerinin altında işlem gören varlıkları alma. "
        "Sabır gerektiren uzun vadeli strateji. Uyarı: 'ucuz görünen' varlık değer tuzağı da olabilir — "
        "neden ucuz olduğunu anlamak hayati önem taşır."
    ),
    "buyume": (
        "Büyüme yatırımı: yüksek büyüme potansiyeline sahip varlıklara prim ödeme. "
        "Yüksek değerleme katları taşır; kâr büyümesine çok duyarlıdır. "
        "Beklentilerin altında kalan her sonuç sert düşüşe yol açabilir."
    ),
    "savunmaci": (
        "Savunmacı yatırım: düşük volatilite, istikrarlı gelir, kriz dayanıklılığı. "
        "Sermaye koruma öncelikli portföylerde temel bileşen. "
        "Boğa piyasasında geri kalır; ayı piyasasında güçlü koruma sağlar — denge aracıdır."
    ),
    "yuksek_risk": (
        "Yüksek risk/ödül: büyük getiri potansiyeli ile büyük kayıp riski birlikte geliyor. "
        "Portföyün maksimum %5-10'unu bu tür pozisyonlara ayırın. "
        "Her pozisyon bağımsız bahis — kaybetmeye hazır olduğunuz kadar girin."
    ),
    "spekulatif": (
        "Spekülatif pozisyon: temel analizle desteklenmeyen, fiyat hareketi veya beklenti üzerine. "
        "Yatırım değil, spekülatif bahis kategorisi. "
        "Yalnızca tamamen kaybedebileceğiniz parayla girin — portföy kuralı."
    ),
    "izleme": (
        "İzleme listesi: henüz aksiyon almak için yeterli sinyal yok. "
        "Fiyat alarmı kurun, tetikleyici sinyalleri tanımlayın. "
        "İzleme disiplini 'pişmanlık değil disiplin': en iyi işlemler çoğunlukla beklenenlerdir."
    ),
    "birikim": (
        "Kademeli birikim: belirli fiyat aralığında parçalı alım. "
        "Her düşüşte ortalama maliyet düşer, risk zamana yayılır. "
        "Varlığın uzun vadeli tezine inancınız sağlamsa güçlü bir strateji."
    ),
    "momentum_breakout": (
        "Momentum Kırılımı: direnci kıran ve hacim onaylayan yükseliş. "
        "Kırılım hacmi normal hacimin en az 1.5x olmalı — aksi 'sahte kırılım' riski. "
        "Gerçek kırılımlarda eski direnç yeni destek olur: bu testi izleyin."
    ),
    "denge": (
        "Dengeli fırsat: ne güçlü momentum ne güçlü değer cazibesi, ama sağlıklı denge. "
        "Düşük sürpriz riski, makul beklenen getiri. "
        "Uzun vadeli portföy inşasının temel taşları bu tür varlıklardır."
    ),
}

# ══════════════════════════════════════════════════════════════════════════════
# PİYASA KOŞULU NOTLARI
# ══════════════════════════════════════════════════════════════════════════════

_MARKET_CONDITIONS: dict = {
    "bull_market": (
        "Boğa piyasasında momentum ve büyüme varlıkları öne çıkar. "
        "Uyarı: herkes iyimser olduğunda gerçek risk artıyor olabilir. "
        "Kâr realizasyonu planınızı şimdiden yapın."
    ),
    "bear_market": (
        "Ayı piyasasında nakit, altın ve savunmacı varlıklar değer kazanır. "
        "Dip avcılığı cazip görünebilir ama erken giriş yorucu. "
        "Uzun vadeli fırsat kapıları açılıyor — sabır ve nakit rezervi kritik."
    ),
    "high_vix": (
        "VIX yüksek → korku ve belirsizlik hâkim. Fiyatlar sert salınır. "
        "Pozisyon büyüklüğünü azaltın; 'ucuz' görünen varlıklar daha da düşebilir. "
        "Hedge stratejileri şimdi devreye alınabilir."
    ),
    "low_vix": (
        "VIX düşük → rehavet hâkim. Dikkat: krizler herkes rahat hissederken patlak verir. "
        "Hedge veya savunmacı varlıklar ucuzken değerlendirin."
    ),
    "rate_hike": (
        "Faiz artışı: büyüme hisseleri ve kripto olumsuz etkilenir. "
        "Finans sektörü ve kısa vadeli tahviller avantajlı. "
        "Yüksek borçlu şirketler finansman maliyeti arttığı için zarar görür."
    ),
    "rate_cut": (
        "Faiz indirimi: büyüme varlıkları, kripto ve uzun vadeli tahviller için olumlu. "
        "Reel faiz düşünce altın değer kazanır. Risk iştahı artar, likidite akar."
    ),
    "strong_dollar": (
        "Güçlü dolar: uluslararası varlıklar ve emtia baskı altında. "
        "BIST dahil gelişmekte olan piyasalar olumsuz etkilenebilir. "
        "ABD iç piyasa odaklı varlıklar görece avantajlı."
    ),
    "weak_dollar": (
        "Zayıf dolar: altın ve emtia değer kazanır. "
        "Gelişmekte olan piyasalar ve uluslararası varlıklar öne çıkabilir. "
        "Kripto tarihsel olarak zayıf dolar ortamında güçlenir."
    ),
    "stagflation": (
        "Stagflasyon: düşük büyüme + yüksek enflasyon. En zorlu makro ortam. "
        "Altın, emtia ve enflasyona endeksli tahviller (TIPS) en iyi korunmayı sağlar. "
        "Büyüme hisseleri ve uzun vadeli tahviller bu ortamda zarar görür."
    ),
    "recession_risk": (
        "Resesyon riski: GDP büyümesi yavaşlıyor. Savunmacı sektörler (sağlık, tüketim zorunlu) "
        "öne çıkar. Nakit pozisyonunu artırın. Borçlu şirketlerin hisseleri daha büyük risk taşır."
    ),
}

# ══════════════════════════════════════════════════════════════════════════════
# RİSK PROFİLİ NOTLARI  (v2 — conviction + timing eklendi)
# ══════════════════════════════════════════════════════════════════════════════

_PROFILE_NOTES: dict = {
    "cok_dengeli": [
        "Sermaye koruma önceliğiniz var; düşük volatiliteli araçlara odaklanıyoruz.",
        "Yüksek enflasyon döneminde bile negatif reel getiriye düşme riskiniz düşük.",
        "Kısa vadeli piyasa sarsıntıları sizi çok az etkiler; sabırlı kalabilirsiniz.",
        "Bu profilde tek varlığa portföyün %15'inden fazlasını koymaktan kaçının.",
        "Conviction skoru düşük varlıkları bu profil için önermiyor; yalnızca 70+ conviction'a bakın.",
    ],
    "dengeli": [
        "Risk-getiri dengesini sağlıyorsunuz; büyüme ile güvenlik arasında köprüdesiniz.",
        "Orta vadeli düzeltmelere (-%15 civarı) hazırlıklı olun; bu normal.",
        "Her 2 ayda bir portföyü gözden geçirip driftlenen pozisyonları yeniden dengeleyin.",
        "Temettü varlıklar ve ETF'ler bu profile iyi uyum sağlar.",
        "Conviction skoru 60+ olan fırsatları takip edin; altındakileri izleme listesinde tutun.",
    ],
    "dengeli_agresif": [
        "Büyüme odaklısınız; volatiliteyi kabul ediyorsunuz ama kontrol altında tutmak istiyorsunuz.",
        "Stop-loss disiplini bu profilde kritik — kararlı durun, eğitim kazası yaşamayın.",
        "Haber akışı ve makro gelişmelere düzenli göz atın; portföy hızlı hareket edebilir.",
        "Conviction 70+ olan fırsatlarda normal pozisyon büyüklüğünü kullanabilirsiniz.",
        "Zamanlama skoru 60'ın altındaysa DCA ile girin — tek seferde tam pozisyon almayın.",
    ],
    "orta_riskli": [
        "Aktif takip gerektiriyor; düzenli teknik analiz ve haber takibi şart.",
        "Kripto ağırlığı yükseliyor — bu sınıfın kendine özgü risklerini iyi anlayın.",
        "Kâr realizasyonu stratejisi geliştirin; 'sonsuza kadar tut' bu profilde işlemez.",
        "Conviction 65+ olan fırsatları tercih edin; timing skoru 55+ ile birlikte.",
        "Maksimum %30 drawdown kuralını asla ihlal etmeyin.",
    ],
    "riskli": [
        "Bu profil ciddi deneyim ve psikolojik dayanıklılık gerektiriyor.",
        "Portföyünüzün en az %5'ini nakit/stablecoin tutun; fırsat anında hareket etmek için.",
        "Günlük piyasa takibi zorunlu; geciken tepkiler bu profilde pahalıya mal olur.",
        "Senaryo ağacı analizi yapın: ayı senaryosu gerçekleşirse ne yapacaksınız?",
        "Yüksek conviction (75+) + iyi zamanlama (65+) olmadan büyük pozisyon almayın.",
    ],
    "cok_riskli": [
        "Spekülatif ağırlıklı portföy. Yalnızca kaybetmeye hazır olduğunuz parayla girin.",
        "Kaldıraçlı ETF ve kripto altcoin'ler hem hızlı kazandırır hem hızlı sıfırlar.",
        "Pozisyon süresi genellikle kısa; uzun vadeli beklentiler bu profilde çalışmaz.",
        "Her trade için risk/ödül oranını hesaplayın: minimum 1:2 altına girmeyin.",
        "Psikolojik baskıya hazır olun — %40-50 düşüşler yaşanabilir.",
    ],
    "ultra_agresif": [
        "Bu profil yatırım değil, aktif trading/spekülatif bahis sınıfındadır.",
        "Tüm varlığınızı bu profile koymayın — toplam portföyün max %20'si.",
        "Kaldıraç ve spekülatif araçlar tam likidasyona yol açabilir.",
        "Her pozisyon bağımsız bahis; hikayeye değil verilere ve conviction skoruna odaklanın.",
        "Günlük P&L takibi şart; duygusal kararları önleyen kural seti oluşturun.",
    ],
}

# ══════════════════════════════════════════════════════════════════════════════
# ÇOK BOYUTLU DEĞERLENDİRME NOTLARI  (v2 yeni)
# ══════════════════════════════════════════════════════════════════════════════

_DIMENSION_NOTES: dict = {
    "opportunity_quality": {
        "high":   "Fırsat kalitesi yüksek — teknik ve momentum sinyalleri güçlü, Sharpe oranı olumlu.",
        "medium": "Fırsat kalitesi orta — bazı sinyaller pozitif, bazıları nötr. Seçici olun.",
        "low":    "Fırsat kalitesi düşük — sinyaller zayıf veya karışık. Beklemeyi değerlendirin.",
    },
    "timing_quality": {
        "high":   "Zamanlama iyi — giriş noktası teknik olarak elverişli. Fırsatı kullanın.",
        "medium": "Zamanlama orta — ideal değil ama kabul edilebilir. DCA ile giriş mantıklı.",
        "low":    "Zamanlama kötü — doğru varlık olsa bile şu an iyi bir giriş noktası değil.",
    },
    "risk_reward": {
        "high":   "Risk/Ödül oranı çekici — potansiyel kazanç, riski belirgin şekilde aşıyor.",
        "medium": "Risk/Ödül dengeli — makul ama parlak değil. Diğer sinyallerle desteklenmeli.",
        "low":    "Risk/Ödül olumsuz — potansiyel kazanç, alınan riske değmiyor.",
    },
    "portfolio_fit": {
        "high":   "Portföy uyumu iyi — bu varlık mevcut portföye çeşitlendirme ve denge katıyor.",
        "medium": "Portföy uyumu orta — eklenebilir ama mevcut konsantrasyonu artırabilir.",
        "low":    "Portföy uyumu zayıf — bu pozisyon mevcut portföyle yüksek korelasyon taşıyor.",
    },
    "profile_fit": {
        "high":   "Profile uygun — bu varlığın risk seviyesi yatırımcı profilinizle uyumlu.",
        "medium": "Kısmen uygun — risk profil sınırında. Küçük pozisyon başlangıç için uygundur.",
        "low":    "Profile uygun değil — bu varlığın riski yatırımcı profilinizin ötesinde.",
    },
    "alternative_cost": {
        "high":   "Fırsat maliyeti düşük — bu yatırım benzer risk için en iyi seçenekler arasında.",
        "medium": "Fırsat maliyeti orta — başka seçenekler de değerlendirilebilir.",
        "low":    "Fırsat maliyeti yüksek — aynı risk sınıfında daha iyi seçenekler mevcut olabilir.",
    },
}


def get_dimension_note(dimension: str, score: float) -> str:
    """6 eksen değerlendirmesi için bağlamsal not döndür."""
    notes = _DIMENSION_NOTES.get(dimension, {})
    if not notes:
        return ""
    if score >= 65:
        return notes.get("high", "")
    elif score >= 45:
        return notes.get("medium", "")
    else:
        return notes.get("low", "")


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def get_education_note(context: str, **kwargs) -> str:
    """
    Bağlamsal eğitim notu döndür.

    Parametreler (context'e göre):
      rsi_oversold   : rsi (float)
      rsi_overbought : rsi (float)
      high_volatility: vol (float), max_pos (float, optional)
      drawdown_high  : dd (float)
      stop_loss      : pct (float, optional)
      sharp_drop     : drop (float)
      diversification: n (int)
      position_sizing: pct (float)
      chasing_momentum: days (int), pct (float)
      var_explanation: var (float)
      portfolio_sharpe: sharpe (float)
      correlation_warning: asset1 (str), asset2 (str)
      kelly_sizing   : kelly (float), quarter (float)
    """
    template = _CONTEXT_NOTES.get(context, "")
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def get_concept_explanation(concept: str) -> dict:
    """
    Yatırım kavramı açıklaması döndür.
    Returns: {"title": str, "explanation": str, "example": str, "tip": str}
    """
    return _CONCEPTS.get(concept.lower(), {})


def get_opportunity_education(opportunity_type: str) -> str:
    """Fırsat tipi için eğitim notu döndür."""
    return _OPPORTUNITY_EDUCATION.get(opportunity_type.lower(), "")


def get_market_condition_note(condition: str) -> str:
    """Piyasa koşuluna göre eğitim notu döndür."""
    return _MARKET_CONDITIONS.get(condition.lower(), "")


def get_portfolio_education_notes(profile_id: str) -> list:
    """Belirli risk profili için eğitim notu listesi döndür."""
    return _PROFILE_NOTES.get(profile_id.lower(), [
        "Portföyünüzü düzenli gözden geçirin.",
        "Çeşitlendirme ve stop-loss disiplinini koruyun.",
        "Risk toleransınızı zorlamayan kararlar alın.",
    ])


def get_timing_education(timing_score: float) -> str:
    """Zamanlama skoru için eğitim notu."""
    if timing_score >= 70:
        return _CONTEXT_NOTES.get("timing_good", "")
    elif timing_score >= 55:
        return _CONTEXT_NOTES.get("timing_neutral", "")
    elif timing_score >= 40:
        return _CONTEXT_NOTES.get("timing_bad", "")
    else:
        return _CONTEXT_NOTES.get("timing_very_bad", "")


def get_conviction_education(conviction_score: float) -> str:
    """Conviction skoru için eğitim notu."""
    if conviction_score >= 68:
        return _CONTEXT_NOTES.get("high_conviction", "")
    elif conviction_score < 50:
        return _CONTEXT_NOTES.get("low_conviction", "")
    return ""


def get_scenario_education(scenario_type: str) -> str:
    """Senaryo tipi için eğitim notu. scenario_type: 'bull'|'base'|'bear'"""
    mapping = {
        "bull": "scenario_bull",
        "base": "scenario_base",
        "bear": "scenario_bear",
    }
    key = mapping.get(scenario_type.lower(), "")
    return _CONTEXT_NOTES.get(key, "")


def get_multi_dimensional_notes(dims: dict) -> dict:
    """
    6 eksen için bağlamsal notlar üret.
    dims: {opp_quality, timing_quality, risk_reward, portfolio_fit, profile_fit, alt_cost}
    Returns: {dimension_key: note_string}
    """
    mapping = {
        "opp_quality":    "opportunity_quality",
        "timing_quality": "timing_quality",
        "risk_reward":    "risk_reward",
        "portfolio_fit":  "portfolio_fit",
        "profile_fit":    "profile_fit",
        "alt_cost":       "alternative_cost",
    }
    result = {}
    for key, dim_name in mapping.items():
        score = dims.get(key, 50.0)
        result[dim_name] = get_dimension_note(dim_name, score)
    return result


def list_available_concepts() -> list:
    """Tüm mevcut kavram anahtarlarını döndür."""
    return list(_CONCEPTS.keys())


def list_available_contexts() -> list:
    """Tüm mevcut bağlam anahtarlarını döndür."""
    return list(_CONTEXT_NOTES.keys())
