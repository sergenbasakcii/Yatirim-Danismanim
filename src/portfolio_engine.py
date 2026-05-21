"""
HedgeFund AI — Portfolio Builder Engine
========================================
Kullanıcının risk profiline, bütçesine ve tercihlerine göre 3 portföy varyantı
(Korumacı / Dengeli / Agresif) + kullanıcı profili tam eşleşmesi üretir.

Desteklenen para birimleri : USD, TRY
Desteklenen risk profilleri: cok_dengeli, dengeli, dengeli_agresif,
                              orta_riskli, riskli, cok_riskli, ultra_agresif
"""

from __future__ import annotations

import copy
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# ── Kök dizin tespiti (frozen EXE desteği) ─────────────────────────────────
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = Path(__file__).parent.parent

_CONFIG_DIR = _ROOT / "config"

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AllocationConstraints:
    """Portföy inşa kısıtlamaları — institutional-grade."""
    max_single_asset_pct: float = 25.0        # tek varlık max ağırlık
    max_single_sector_pct: float = 40.0       # tek sektör max ağırlık
    max_crypto_pct: float = 50.0              # kripto max ağırlık
    cash_min_pct: float = 3.0                 # minimum nakit
    cash_max_pct: float = 30.0               # maximum nakit
    max_correlation_threshold: float = 0.75   # bu üstü korelasyonda pozisyon azalt
    drawdown_tolerance_pct: float = 20.0      # kullanıcının max tolere edebileceği DD
    volatility_target_pct: float = 15.0       # hedef portföy volatilitesi
    kelly_fraction: float = 0.25              # quarter-Kelly (tam Kelly'nin 1/4'ü)


@dataclass
class PortfolioMetrics:
    """Portföy düzeyinde kurumsal metrikler."""
    sharpe: float = 0.0
    sortino: float = 0.0
    var_95: float = 0.0           # %95 VaR (aylık kayıp %)
    cvar_95: float = 0.0          # Conditional VaR
    max_dd_estimate: float = 0.0  # tahmini max drawdown %
    correlation_score: float = 0.0  # 0-100, yüksek = iyi çeşitlendirme
    portfolio_volatility: float = 0.0


@dataclass
class PortfolioAsset:
    """Portföydeki tek bir varlığı temsil eder."""
    symbol: str
    name: str
    asset_type: str           # crypto / stock / bist / etf / nakit / altin / tahvil
    sector: str
    weight_pct: float         # portföydeki ağırlık yüzdesi
    amount: float             # para birimi cinsinden tutar
    risk_level: str           # cok_dusuk / dusuk / orta / orta_yuksek / yuksek / cok_yuksek / spekulatif
    expected_return_pct: float  # yıllık beklenen getiri (%)
    why_included: str         # bu varlığın portföyde neden olduğunun açıklaması
    # ── Institutional ──────────────────────────────────────────────────────
    conviction_score: float = 50.0           # 0-100
    allocation_confidence: float = 50.0      # 0-100
    kelly_weight: float = 0.0                # Kelly kriteri önerisi (%)
    volatility_adjusted_weight: float = 0.0  # volatilite ayarlı ağırlık (%)


@dataclass
class PortfolioAllocation:
    """Tek bir portföy varyantını (Korumacı / Dengeli / Agresif) temsil eder."""
    name: str                          # "Korumacı" / "Dengeli" / "Agresif"
    emoji: str
    description: str
    budget: float
    currency: str
    risk_profile: str
    assets: List[PortfolioAsset] = field(default_factory=list)
    total_invested: float = 0.0
    cash_reserved: float = 0.0
    cash_pct: float = 0.0
    expected_return_low_pct: float = 0.0
    expected_return_mid_pct: float = 0.0
    expected_return_high_pct: float = 0.0
    expected_max_loss_pct: float = 0.0
    diversification_score: float = 0.0  # 0-100
    num_assets: int = 0
    asset_class_distribution: Dict[str, float] = field(default_factory=dict)
    why_suitable: str = ""
    main_risks: List[str] = field(default_factory=list)
    rebalance_suggestion: str = ""
    monthly_addition_plan: str = ""
    # ── Institutional-grade ─────────────────────────────────────────────────
    allocation_confidence: float = 0.0       # 0-100 sistem güveni
    portfolio_sharpe_estimate: float = 0.0   # tahmini Sharpe oranı
    portfolio_var_95: float = 0.0            # %95 VaR (aylık %)
    portfolio_max_dd_scenario: float = 0.0   # tahmini max drawdown %
    correlation_score: float = 0.0           # 0-100 çeşitlendirme kalitesi
    portfolio_volatility: float = 0.0        # tahmini portföy volatilitesi %
    scenario_bull_return: float = 0.0
    scenario_base_return: float = 0.0
    scenario_bear_loss: float = 0.0
    scenario_bull_probability: int = 35
    scenario_base_probability: int = 45
    scenario_bear_probability: int = 20


@dataclass
class PortfolioBuilderResult:
    """build_portfolio() fonksiyonunun dönüş tipi."""
    conservative: PortfolioAllocation
    balanced: PortfolioAllocation
    aggressive: PortfolioAllocation
    user_preference: PortfolioAllocation   # kullanıcının tam profil eşleşmesi

    budget: float
    currency: str
    risk_profile: str
    horizon: str

    # Öneri
    recommendation: str          # hangi 3 varyantı seçmeli
    recommendation_reason: str


# ═══════════════════════════════════════════════════════════════════════════════
# RİSK SEVİYESİ & PROFİL YARDIMCILARI
# ═══════════════════════════════════════════════════════════════════════════════

# Risk seviyelerinin sıralanmış listesi (düşükten yükseğe)
_RISK_ORDER: List[str] = [
    "cok_dusuk", "dusuk", "orta", "orta_yuksek", "yuksek", "cok_yuksek", "spekulatif"
]

# Profil sırası (korumacıdan agresife)
_PROFILE_ORDER: List[str] = [
    "cok_dengeli", "dengeli", "dengeli_agresif",
    "orta_riskli", "riskli", "cok_riskli", "ultra_agresif"
]

# Her varlık tipi için beklenen yıllık getiri aralıkları (ortalama, %)
_EXPECTED_RETURNS: Dict[str, float] = {
    "nakit":   3.0,
    "tahvil":  6.0,
    "altin":   8.0,
    "etf":    14.0,
    "stock":  18.0,
    "bist":   22.0,
    "crypto": 55.0,
}

# Risk seviyesine göre beklenen getiri çarpanı
_RISK_RETURN_MULTIPLIER: Dict[str, float] = {
    "cok_dusuk":   0.6,
    "dusuk":       0.8,
    "orta":        1.0,
    "orta_yuksek": 1.2,
    "yuksek":      1.5,
    "cok_yuksek":  2.0,
    "spekulatif":  3.0,
}


# ═══════════════════════════════════════════════════════════════════════════════
# CURATED ASSET CATALOGUE
# ═══════════════════════════════════════════════════════════════════════════════
# Her giriş: (symbol, name, asset_type, sector, risk_level, why_template)
# why_template içinde {name} ve {symbol} kullanılabilir.

_ASSET_CATALOGUE: List[Dict] = [
    # ── Nakit / Para Piyasası ────────────────────────────────────────────────
    {
        "symbol": "CASH", "name": "Nakit / Para Piyasası Fonu",
        "asset_type": "nakit", "sector": "Nakit",
        "risk_level": "cok_dusuk",
        "why": "Portföyde likidite tamponu sağlar. Fırsat anında hızlı hareket imkânı verir.",
    },
    # ── Tahvil / Altın ETF ───────────────────────────────────────────────────
    {
        "symbol": "TLT", "name": "iShares 20Y+ Treasury Bond ETF",
        "asset_type": "etf", "sector": "Tahvil",
        "risk_level": "dusuk",
        "why": "Uzun vadeli ABD hazine tahvillerine erişim. Hisse senedi düşüşlerinde negatif korelasyon sağlayarak portföyü dengeler.",
    },
    {
        "symbol": "GLD", "name": "SPDR Gold Shares ETF",
        "asset_type": "etf", "sector": "Altın",
        "risk_level": "orta",
        "why": "Fiziksel altına en likit erişim aracı. Enflasyon ve makro belirsizliğe karşı güçlü koruma kalkanı.",
    },
    {
        "symbol": "HYG", "name": "iShares High Yield Bond ETF",
        "asset_type": "etf", "sector": "Tahvil",
        "risk_level": "orta",
        "why": "Yüksek getirili kurumsal tahviller. Tahvil getirisini artırırken portföye sabit gelir bileşeni ekler.",
    },
    # ── Savunmacı / Düşük Riskli ETF'ler ────────────────────────────────────
    {
        "symbol": "SPY", "name": "SPDR S&P 500 ETF",
        "asset_type": "etf", "sector": "ABD Geniş Piyasa",
        "risk_level": "dusuk",
        "why": "ABD geniş piyasa ETF'i. Portföye düşük maliyetle 500 şirket çeşitlendirmesi ve piyasa betası katıyor.",
    },
    {
        "symbol": "VOO", "name": "Vanguard S&P 500 ETF",
        "asset_type": "etf", "sector": "ABD Geniş Piyasa",
        "risk_level": "dusuk",
        "why": "Sektörün en düşük gider oranlı S&P 500 ETF'i. Uzun vadeli bileşik büyüme için ideal temel bileşen.",
    },
    {
        "symbol": "VNQ", "name": "Vanguard Real Estate ETF",
        "asset_type": "etf", "sector": "Gayrimenkul",
        "risk_level": "orta",
        "why": "Çeşitlendirilmiş gayrimenkul yatırım ortaklıkları. Portföye gayrimenkul getirisi ve temettü geliri katıyor.",
    },
    {
        "symbol": "EFA", "name": "iShares MSCI EAFE ETF",
        "asset_type": "etf", "sector": "Uluslararası Gelişmiş",
        "risk_level": "orta",
        "why": "Avrupa ve Japonya dahil gelişmiş piyasa çeşitlendirmesi. ABD konsantrasyonunu azaltır.",
    },
    {
        "symbol": "EEM", "name": "iShares MSCI Emerging Markets ETF",
        "asset_type": "etf", "sector": "Gelişmekte Olan Piyasalar",
        "risk_level": "orta_yuksek",
        "why": "Gelişmekte olan piyasalara geniş erişim. Uzun vadeli büyüme potansiyeli yüksek ancak döviz riski içerir.",
    },
    {
        "symbol": "IWM", "name": "iShares Russell 2000 ETF",
        "asset_type": "etf", "sector": "ABD Küçük Ölçekli",
        "risk_level": "orta_yuksek",
        "why": "ABD küçük ve orta ölçekli şirketler. Büyük ölçeklilere göre daha yüksek büyüme potansiyeli sunar.",
    },
    # ── Büyüme / Momentum ETF'leri ───────────────────────────────────────────
    {
        "symbol": "QQQ", "name": "Invesco Nasdaq-100 ETF",
        "asset_type": "etf", "sector": "Teknoloji",
        "risk_level": "orta",
        "why": "Nasdaq'ın büyük teknoloji şirketlerine konsantre erişim. Yapay zeka ve teknoloji büyümesinden faydalanır.",
    },
    {
        "symbol": "XLK", "name": "Technology Select SPDR ETF",
        "asset_type": "etf", "sector": "Teknoloji",
        "risk_level": "orta",
        "why": "S&P 500 teknoloji sektörü ETF'i. QQQ'ya kıyasla daha geniş sektör temsili sağlar.",
    },
    {
        "symbol": "XLE", "name": "Energy Select SPDR ETF",
        "asset_type": "etf", "sector": "Enerji",
        "risk_level": "orta",
        "why": "ABD büyük enerji şirketleri sepeti. Enflasyon koruma ve temettü geliri kombinasyonu sunar.",
    },
    {
        "symbol": "SOXX", "name": "iShares Semiconductor ETF",
        "asset_type": "etf", "sector": "Yarı İletken",
        "risk_level": "orta_yuksek",
        "why": "Küresel yarı iletken endüstrisine çeşitlendirilmiş erişim. AI altyapısının kritik üretim zincirini temsil eder.",
    },
    {
        "symbol": "ICLN", "name": "iShares Global Clean Energy ETF",
        "asset_type": "etf", "sector": "Temiz Enerji",
        "risk_level": "orta_yuksek",
        "why": "Yenilenebilir enerji geçişinden faydalanan şirket sepeti. Uzun vadeli yapısal büyüme teması.",
    },
    {
        "symbol": "ARKK", "name": "ARK Innovation ETF",
        "asset_type": "etf", "sector": "İnovasyon",
        "risk_level": "yuksek",
        "why": "Yıkıcı teknoloji şirketlerine konsantre aktif yönetim. Yüksek volatiliteye karşın asimetrik kazanç potansiyeli içerir.",
    },
    {
        "symbol": "IBB", "name": "iShares Biotechnology ETF",
        "asset_type": "etf", "sector": "Biyoteknoloji",
        "risk_level": "yuksek",
        "why": "Biyoteknoloji ve ilaç inovasyonu sepeti. Klinik onay riskine karşın yüksek getiri potansiyeli barındırır.",
    },
    {
        "symbol": "IBIT", "name": "iShares Bitcoin Trust ETF",
        "asset_type": "etf", "sector": "Kripto ETF",
        "risk_level": "cok_yuksek",
        "why": "Bitcoin'e düzenlenmiş ETF formatında erişim. Kripto volatilitesini portföye eklemenin en güvenli yolu.",
    },
    {
        "symbol": "TQQQ", "name": "ProShares UltraPro QQQ 3x Leveraged ETF",
        "asset_type": "etf", "sector": "Kaldıraçlı",
        "risk_level": "spekulatif",
        "why": "Nasdaq-100'ün 3 kat kaldıraçlı versiyonu. Kısa vadeli yükseliş dönemlerinde maksimum getiri hedefler; taşıma maliyeti yüksek.",
    },
    {
        "symbol": "SOXL", "name": "Direxion Daily Semiconductor 3x ETF",
        "asset_type": "etf", "sector": "Kaldıraçlı Yarı İletken",
        "risk_level": "spekulatif",
        "why": "Yarı iletken sektörünün 3 kat kaldıraçlı ETF'i. Yapay zeka ve chip döngüsüne spekülatif katılım sağlar.",
    },
    # ── ABD Hisseleri — Düşük/Orta Risk ─────────────────────────────────────
    {
        "symbol": "JNJ", "name": "Johnson & Johnson",
        "asset_type": "stock", "sector": "Sağlık",
        "risk_level": "cok_dusuk",
        "why": "130+ yıllık temettü artış sicili olan savunmacı sağlık devi. Portföye istikrar ve düzenli gelir katıyor.",
    },
    {
        "symbol": "V", "name": "Visa Inc.",
        "asset_type": "stock", "sector": "Finans",
        "risk_level": "cok_dusuk",
        "why": "Küresel ödeme altyapısının kalıcı tekelcisi. Düşük sermaye gerektiren varlık-hafif modeli üstün serbest nakit akışı sağlar.",
    },
    {
        "symbol": "MA", "name": "Mastercard Inc.",
        "asset_type": "stock", "sector": "Finans",
        "risk_level": "cok_dusuk",
        "why": "Dijital ödemelerin çift taraflı ağ etkisi. Visa ile birlikte küresel işlem altyapısının çift oligopolünü oluşturur.",
    },
    {
        "symbol": "WMT", "name": "Walmart Inc.",
        "asset_type": "stock", "sector": "Perakende",
        "risk_level": "cok_dusuk",
        "why": "Dünyanın en büyük perakendecisi. Resesyon dönemlerinde güçlenirken reklam ve fintech kollarıyla büyüme hikayesi genişliyor.",
    },
    {
        "symbol": "COST", "name": "Costco Wholesale",
        "asset_type": "stock", "sector": "Perakende",
        "risk_level": "dusuk",
        "why": "Üyelik tabanlı toptan perakende modeli. Müşteri bağlılığı ve yüksek yenileme oranı savunmacı büyüme sağlar.",
    },
    {
        "symbol": "AAPL", "name": "Apple Inc.",
        "asset_type": "stock", "sector": "Teknoloji",
        "risk_level": "dusuk",
        "why": "Donanım + yazılım + hizmetler ekosistemine sahip en değerli marka. Hizmet gelirlerinin büyümesi marj genişlemesi sağlıyor.",
    },
    {
        "symbol": "MSFT", "name": "Microsoft Corp.",
        "asset_type": "stock", "sector": "Teknoloji",
        "risk_level": "dusuk",
        "why": "Bulut (Azure) ve yapay zeka (Copilot/OpenAI) liderliği. Kurumsal yazılım geçiş maliyetleri güçlü yinelenen gelir yaratıyor.",
    },
    {
        "symbol": "GOOGL", "name": "Alphabet Inc.",
        "asset_type": "stock", "sector": "Teknoloji",
        "risk_level": "dusuk",
        "why": "Arama geliri + YouTube + Google Cloud üçlüsü. Gemini AI entegrasyonu reklam gelirlerine yeni katalizör ekliyor.",
    },
    {
        "symbol": "JPM", "name": "JPMorgan Chase",
        "asset_type": "stock", "sector": "Finans",
        "risk_level": "dusuk",
        "why": "Dünyanın en büyük yatırım bankası. Yüksek faiz ortamında net faiz marjı genişlerken güçlü sermaye yeterlilik oranları muhafaza ediliyor.",
    },
    {
        "symbol": "UNH", "name": "UnitedHealth Group",
        "asset_type": "stock", "sector": "Sağlık Sigortası",
        "risk_level": "dusuk",
        "why": "ABD sağlık sigortası piyasasının hakimi. Yaşlanan nüfus demografisi uzun vadeli yapısal talep büyümesi garantiliyor.",
    },
    {
        "symbol": "XOM", "name": "Exxon Mobil",
        "asset_type": "stock", "sector": "Enerji",
        "risk_level": "orta",
        "why": "Entegre enerji devi; üretim, rafineri ve kimyasal kollarla petrol döngüsüne karşı tampon sağlar. Güçlü temettü taahhüdü.",
    },
    {
        "symbol": "NVDA", "name": "NVIDIA Corp.",
        "asset_type": "stock", "sector": "Yarı İletken",
        "risk_level": "orta",
        "why": "AI donanım liderliği ve GPU mimarisinin fiili standardı. Veri merkezi büyümesi güçlü büyüme görünümü portföy getiri potansiyelini artırıyor.",
    },
    {
        "symbol": "AMZN", "name": "Amazon.com Inc.",
        "asset_type": "stock", "sector": "E-Ticaret/Bulut",
        "risk_level": "orta",
        "why": "AWS bulut ve e-ticaret reklamcılığının süper konumu. Lojistik ağı ve Prime üyeliği güçlü müşteri kilidi yaratıyor.",
    },
    {
        "symbol": "META", "name": "Meta Platforms",
        "asset_type": "stock", "sector": "Sosyal Medya",
        "risk_level": "orta",
        "why": "3 milyar+ kullanıcı tabanı ve reklam geliri makinesi. Llama AI ve AR/VR yatırımları gelecek büyüme vektörleri sunuyor.",
    },
    {
        "symbol": "LLY", "name": "Eli Lilly",
        "asset_type": "stock", "sector": "İlaç",
        "risk_level": "orta",
        "why": "GLP-1 obezite ilacı piyasasının lideri. Mounjaro ve Zepbound'un küresel genişlemesi onlarca yıllık büyüme fırsatı sunuyor.",
    },
    {
        "symbol": "AVGO", "name": "Broadcom Inc.",
        "asset_type": "stock", "sector": "Yarı İletken",
        "risk_level": "orta",
        "why": "AI özel chip (ASIC) ve ağ altyapısı liderliği. VMware entegrasyonu yazılım gelirlerini ve marjı güçlendiriyor.",
    },
    {
        "symbol": "AMD", "name": "Advanced Micro Devices",
        "asset_type": "stock", "sector": "Yarı İletken",
        "risk_level": "orta_yuksek",
        "why": "Veri merkezi GPU pazarında NVIDIA'ya alternatif. MI300X hızlandırıcılar ve EPYC sunucu işlemcilerle pazar payı kazanımı sürüyor.",
    },
    {
        "symbol": "CRWD", "name": "CrowdStrike Holdings",
        "asset_type": "stock", "sector": "Siber Güvenlik",
        "risk_level": "orta_yuksek",
        "why": "Bulut tabanlı uç nokta güvenliğinin lideri. Platform konsolidasyon trendi müşteri başına geliri yukarı taşıyor.",
    },
    {
        "symbol": "TSLA", "name": "Tesla Inc.",
        "asset_type": "stock", "sector": "Elektrikli Araç",
        "risk_level": "yuksek",
        "why": "Elektrikli araç pioneri ve enerji depolama şirketi. FSD yazılımı ve Robotaxi iş modeli uzun vadeli değer katalizörü.",
    },
    {
        "symbol": "PLTR", "name": "Palantir Technologies",
        "asset_type": "stock", "sector": "Veri/AI",
        "risk_level": "yuksek",
        "why": "Savunma ve kurumsal AI analitik platformu. AIP ürünü ticari müşteri büyümesini hızlandırırken ABD devlet sözleşmeleri gelir tabanı sağlıyor.",
    },
    {
        "symbol": "SHOP", "name": "Shopify Inc.",
        "asset_type": "stock", "sector": "E-Ticaret",
        "risk_level": "yuksek",
        "why": "KOBİ e-ticaret altyapısının küresel lideri. Payment ve lojistik kollarının büyümesi çok taraflı platform değerini artırıyor.",
    },
    {
        "symbol": "COIN", "name": "Coinbase Global",
        "asset_type": "stock", "sector": "Kripto Altyapı",
        "risk_level": "cok_yuksek",
        "why": "ABD'nin en büyük kripto borsası. Kripto döngüsüne kaldıraçlı katılım sağlarken lisanslı yapı kurumsal erişimi garantiliyor.",
    },
    {
        "symbol": "MSTR", "name": "MicroStrategy",
        "asset_type": "stock", "sector": "Bitcoin Proxy",
        "risk_level": "spekulatif",
        "why": "Kurumsal Bitcoin hazine stratejisinin öncüsü. Bitcoin'e kaldıraçlı maruz kalım arayan yatırımcılar için aşırı spekülatif araç.",
    },
    # ── Kripto ──────────────────────────────────────────────────────────────
    {
        "symbol": "BTC-USD", "name": "Bitcoin",
        "asset_type": "crypto", "sector": "Layer 1",
        "risk_level": "yuksek",
        "why": "Kripto sınıfının lideri ve dijital altın anlatısının merkezi. Makro koruma potansiyeli ve kurumsal adaptasyon ile portföy çeşitlendirmesi sağlar.",
    },
    {
        "symbol": "ETH-USD", "name": "Ethereum",
        "asset_type": "crypto", "sector": "Smart Contract",
        "risk_level": "yuksek",
        "why": "Akıllı sözleşme ekosisteminin altyapı katmanı. DeFi, NFT ve Layer 2 ağlarından servis geliri toplayan dijital bir petrol.",
    },
    {
        "symbol": "SOL-USD", "name": "Solana",
        "asset_type": "crypto", "sector": "Layer 1",
        "risk_level": "cok_yuksek",
        "why": "Yüksek hızlı ve düşük maliyetli Layer 1. Memecoin ve consumer uygulamaların ağına dönüşmesiyle kullanıcı tabanı hızla büyüyor.",
    },
    {
        "symbol": "BNB-USD", "name": "BNB",
        "asset_type": "crypto", "sector": "Exchange Token",
        "risk_level": "yuksek",
        "why": "Binance borsası ve BNB Chain ekosisteminin yakıtı. Exchange hacmine ve BSC aktivitesine bağlı sistematik talep dinamiği var.",
    },
    {
        "symbol": "XRP-USD", "name": "XRP",
        "asset_type": "crypto", "sector": "Payment",
        "risk_level": "yuksek",
        "why": "Sınır ötesi ödeme ağının kripto altyapısı. SEC davası kararı sonrası yasal belirsizlik azalması kurumsal adaptasyonu hızlandırabilir.",
    },
    {
        "symbol": "ADA-USD", "name": "Cardano",
        "asset_type": "crypto", "sector": "Layer 1",
        "risk_level": "cok_yuksek",
        "why": "Akademik araştırmaya dayalı Layer 1 platformu. Gerçek dünya varlık tokenizasyonu odağı uzun vadeli farklılaşma sunuyor.",
    },
    {
        "symbol": "AVAX-USD", "name": "Avalanche",
        "asset_type": "crypto", "sector": "Layer 1",
        "risk_level": "cok_yuksek",
        "why": "Subnet mimarisi ile özelleştirilebilir blok zinciri altyapısı. Kurumsal blockchain projeleri için tercih edilen platform olmaya çalışıyor.",
    },
    {
        "symbol": "LINK-USD", "name": "Chainlink",
        "asset_type": "crypto", "sector": "Oracle",
        "risk_level": "cok_yuksek",
        "why": "Blok zinciri oracle ağlarının tartışmasız lideri. DeFi büyümesiyle doğru orantılı kullanım artışı uzun vadeli değer birikimi sağlar.",
    },
    # ── BIST Hisseleri ───────────────────────────────────────────────────────
    {
        "symbol": "KCHOL.IS", "name": "Koç Holding",
        "asset_type": "bist", "sector": "Holding",
        "risk_level": "dusuk",
        "why": "Türkiye'nin en büyük holding şirketi. Enerji, otomotiv ve finans kolu TL bazlı enflasyon koruması sağlıyor.",
    },
    {
        "symbol": "SAHOL.IS", "name": "Sabancı Holding",
        "asset_type": "bist", "sector": "Holding",
        "risk_level": "dusuk",
        "why": "Çeşitlendirilmiş holdingi Yapısı. Çimento, banka, sigortaya ek yenilenebilir enerji yatırımları uzun vadeli değer katıyor.",
    },
    {
        "symbol": "BIMAS.IS", "name": "BİM Mağazalar",
        "asset_type": "bist", "sector": "Perakende",
        "risk_level": "dusuk",
        "why": "Türkiye'nin indirim perakendecisi. Enflasyon dönemlerinde müşteri tabanı güçlenir; düzenli temettü kalitesi öne çıkıyor.",
    },
    {
        "symbol": "ASELS.IS", "name": "Aselsan",
        "asset_type": "bist", "sector": "Savunma",
        "risk_level": "orta",
        "why": "Yerli savunma sanayiinin teknoloji lokomotifi. İhracat büyümesi ve artan savunma bütçesi uzun vadeli sipariş defteri sağlıyor.",
    },
    {
        "symbol": "EREGL.IS", "name": "Ereğli Demir Çelik",
        "asset_type": "bist", "sector": "Demir Çelik",
        "risk_level": "orta",
        "why": "Türkiye'nin en büyük çelik üreticisi. İnşaat ve ihracat döngüsünden faydalanırken yüksek temettü verimi cazip kılıyor.",
    },
    {
        "symbol": "GARAN.IS", "name": "Garanti BBVA",
        "asset_type": "bist", "sector": "Bankacılık",
        "risk_level": "orta_yuksek",
        "why": "BBVA ortaklığı ve güçlü dijital bankacılık altyapısıyla Türkiye'nin premium bankası. Faiz döngüsü normalleşmesinde kar marjı artışı bekleniyor.",
    },
    {
        "symbol": "THYAO.IS", "name": "Türk Hava Yolları",
        "asset_type": "bist", "sector": "Havacılık",
        "risk_level": "orta_yuksek",
        "why": "Küresel uçuş ağı ve hub stratejisiyle dünya genelinde büyüyen havacılık şirketi. Yolcu kapasitesi artışı gelir büyümesini destekliyor.",
    },
    {
        "symbol": "TCELL.IS", "name": "Turkcell",
        "asset_type": "bist", "sector": "Telekomünikasyon",
        "risk_level": "orta",
        "why": "Türkiye'nin dijital operatörü. 5G altyapı yatırımları ve finansal hizmetler kolunun büyümesi değer katıyor.",
    },
    {
        "symbol": "TUPRS.IS", "name": "Tüpraş",
        "asset_type": "bist", "sector": "Rafineri",
        "risk_level": "orta",
        "why": "Türkiye'nin tek büyük rafinerisi; ham petrol fiyatıyla arbitraj marjı korunuyor. Güçlü temettü politikası öne çıkıyor.",
    },
    {
        "symbol": "KOZAL.IS", "name": "Koza Altın",
        "asset_type": "bist", "sector": "Altın Madenci",
        "risk_level": "orta_yuksek",
        "why": "Yerli altın üreticisi. TL bazında altın fiyatına hem kur hem de emtia koruması ekleyerek çift koruma sağlar.",
    },
    {
        "symbol": "VESTL.IS", "name": "Vestel",
        "asset_type": "bist", "sector": "Elektronik",
        "risk_level": "yuksek",
        "why": "Beyaz eşya ve ekran teknolojisi üreticisi. İhracat gelirleri döviz kazancı sağlarken döngüsel sektör dinamiği risk getiriyor.",
    },
]

# Sembol → katalog girişi indeksi (hızlı erişim için)
_CATALOGUE_INDEX: Dict[str, Dict] = {a["symbol"]: a for a in _ASSET_CATALOGUE}


# ═══════════════════════════════════════════════════════════════════════════════
# INSTITUTIONAL-GRADE UTILITY FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════════════

import math as _math

# Varlık tipi bazında volatilite tahminleri (yıllık %)
_ASSET_VOL: Dict[str, float] = {
    "nakit":        0.5,
    "tahvil":       8.0,
    "altin":       15.0,
    "etf":         18.0,
    "stock":       25.0,
    "bist":        35.0,
    "crypto":      75.0,
}

# Risk seviyesine göre volatilite tahminleri
_RISK_VOL: Dict[str, float] = {
    "cok_dusuk":    5.0,
    "dusuk":       12.0,
    "orta":        20.0,
    "orta_yuksek": 30.0,
    "yuksek":      45.0,
    "cok_yuksek":  65.0,
    "spekulatif":  90.0,
}

# Statik korelasyon tablosu — varlık tipi çiftleri
_CORRELATION_TABLE: Dict[tuple, float] = {
    ("crypto",  "crypto"):  0.75,
    ("crypto",  "stock"):   0.35,
    ("crypto",  "etf"):     0.30,
    ("crypto",  "bist"):    0.40,
    ("crypto",  "altin"):   0.15,
    ("crypto",  "tahvil"): -0.10,
    ("crypto",  "nakit"):   0.00,
    ("stock",   "stock"):   0.55,
    ("stock",   "etf"):     0.80,
    ("stock",   "bist"):    0.25,
    ("stock",   "altin"):   0.05,
    ("stock",   "tahvil"): -0.20,
    ("stock",   "nakit"):   0.00,
    ("etf",     "etf"):     0.70,
    ("etf",     "bist"):    0.20,
    ("etf",     "altin"):   0.05,
    ("etf",     "tahvil"): -0.15,
    ("etf",     "nakit"):   0.00,
    ("bist",    "bist"):    0.65,
    ("bist",    "altin"):   0.10,
    ("bist",    "tahvil"):  0.05,
    ("bist",    "nakit"):   0.00,
    ("altin",   "altin"):   1.00,
    ("altin",   "tahvil"):  0.25,
    ("altin",   "nakit"):   0.00,
    ("tahvil",  "tahvil"):  0.80,
    ("tahvil",  "nakit"):   0.00,
    ("nakit",   "nakit"):   0.00,
}


def _estimate_correlation(type1: str, type2: str) -> float:
    """İki varlık tipi arasındaki korelasyonu statik tablodan tahmin et."""
    key = (type1, type2)
    if key in _CORRELATION_TABLE:
        return _CORRELATION_TABLE[key]
    key_rev = (type2, type1)
    if key_rev in _CORRELATION_TABLE:
        return _CORRELATION_TABLE[key_rev]
    return 0.30  # bilinmeyen çiftler için varsayılan


def _kelly_position_size(
    expected_return_pct: float,
    volatility_pct: float,
    kelly_fraction: float = 0.25,
) -> float:
    """
    Quarter-Kelly pozisyon büyüklüğü hesapla.
    Returns: önerilen ağırlık (%), [2, 35] aralığında.
    """
    if volatility_pct <= 0:
        return 5.0
    mu = expected_return_pct / 100.0
    rf = 0.05
    sigma = volatility_pct / 100.0
    sigma2 = sigma * sigma
    if sigma2 <= 0:
        return 5.0
    full_kelly = (mu - rf) / sigma2
    adjusted = full_kelly * kelly_fraction * 100.0  # → yüzde
    return round(float(max(2.0, min(35.0, adjusted))), 1)


def _calculate_portfolio_metrics(
    assets: List[PortfolioAsset],
    constraints: "AllocationConstraints",
) -> "PortfolioMetrics":
    """
    Portföy düzeyinde kurumsal metrikleri hesapla.
    Basitleştirilmiş analitik yaklaşım (canlı veri gerektirmez).
    """
    if not assets:
        return PortfolioMetrics()

    # Ağırlıkları normalize et
    total_w = sum(a.weight_pct for a in assets)
    if total_w <= 0:
        return PortfolioMetrics()

    weights = [a.weight_pct / total_w for a in assets]

    # Her varlık için volatilite tahmini
    vols = []
    for a in assets:
        v = _RISK_VOL.get(a.risk_level, _ASSET_VOL.get(a.asset_type, 20.0))
        vols.append(v / 100.0)  # ondalıklı

    # Portföy varyansı (matris çarpımı basitleştirilmiş)
    port_var = 0.0
    for i, (wi, vi) in enumerate(zip(weights, vols)):
        for j, (wj, vj) in enumerate(zip(weights, vols)):
            rho = 1.0 if i == j else _estimate_correlation(
                assets[i].asset_type, assets[j].asset_type)
            port_var += wi * wj * vi * vj * rho

    port_vol = (_math.sqrt(max(0.0, port_var)) * 100.0)  # yüzde

    # Ağırlıklı beklenen getiri
    weighted_ret = sum(w * a.expected_return_pct for w, a in zip(weights, assets))

    # Sharpe (risksiz oran %5)
    rf = 5.0
    sharpe = (weighted_ret - rf) / port_vol if port_vol > 0 else 0.0

    # Sortino (sadece negatif volatilite, basit tahmin: downside_vol = port_vol * 0.7)
    downside_vol = port_vol * 0.7
    sortino = (weighted_ret - rf) / downside_vol if downside_vol > 0 else 0.0

    # VaR %95 (aylık, normal dağılım)
    var_95 = port_vol / _math.sqrt(12) * 1.645  # aylık VaR %

    # CVaR ≈ 1.25 × VaR (normal dağılım approximation)
    cvar_95 = var_95 * 1.25

    # Max DD tahmini (portföy volatilitesi × 2.5, en basit heuristik)
    max_dd = port_vol * 2.5

    # Korelasyon skoru: çok korelasyonlu çift sayısına göre cezalandır
    corr_score = 100.0
    pair_count = 0
    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            rho = _estimate_correlation(assets[i].asset_type, assets[j].asset_type)
            if rho > 0.75:
                corr_score -= 15.0 * weights[i] * weights[j] * 10
            elif rho > 0.5:
                corr_score -= 7.0 * weights[i] * weights[j] * 10
            pair_count += 1

    corr_score = round(max(0.0, min(100.0, corr_score)), 1)

    return PortfolioMetrics(
        sharpe=round(sharpe, 3),
        sortino=round(sortino, 3),
        var_95=round(var_95, 2),
        cvar_95=round(cvar_95, 2),
        max_dd_estimate=round(max_dd, 1),
        correlation_score=corr_score,
        portfolio_volatility=round(port_vol, 1),
    )


def _apply_volatility_adjusted_weights(
    assets: List[PortfolioAsset],
    blend_factor: float = 0.4,
) -> List[PortfolioAsset]:
    """
    Risk paritesi (volatilite ağırlıklı) karışımı uygula.
    blend_factor: 0 = saf risk paritesi, 1 = orijinal ağırlıklar.
    Varsayılan: %60 orijinal + %40 risk paritesi.
    """
    if not assets:
        return assets

    vols = []
    for a in assets:
        v = _RISK_VOL.get(a.risk_level, _ASSET_VOL.get(a.asset_type, 20.0))
        vols.append(max(0.5, v))

    # Ters volatilite ağırlıkları (risk paritesi)
    inv_vols = [1.0 / v for v in vols]
    total_inv = sum(inv_vols)
    rp_weights = [iv / total_inv * 100.0 for iv in inv_vols]

    # Orijinal ağırlıklar
    total_orig = sum(a.weight_pct for a in assets)
    orig_weights = [a.weight_pct / total_orig * 100.0 for a in assets] if total_orig > 0 else rp_weights

    # Kelly ağırlıkları
    for i, a in enumerate(assets):
        kelly_w = _kelly_position_size(a.expected_return_pct, vols[i])
        # Karışım: orijinal + risk paritesi
        blended = orig_weights[i] * (1 - blend_factor) + rp_weights[i] * blend_factor
        a.volatility_adjusted_weight = round(blended, 2)
        a.kelly_weight = kelly_w
        # Conviction ve confidence basit tahminleri
        risk_idx = _RISK_ORDER.index(a.risk_level) if a.risk_level in _RISK_ORDER else 3
        a.conviction_score = round(max(30.0, 85.0 - risk_idx * 8), 1)
        a.allocation_confidence = round(max(30.0, 80.0 - risk_idx * 7), 1)

    return assets


def _enrich_allocation_metrics(
    alloc: "PortfolioAllocation",
    constraints: "AllocationConstraints",
) -> "PortfolioAllocation":
    """
    build_portfolio() sonrası kurumsal metrikleri doldur.
    """
    metrics = _calculate_portfolio_metrics(alloc.assets, constraints)
    alloc.assets = _apply_volatility_adjusted_weights(alloc.assets)

    alloc.portfolio_sharpe_estimate  = metrics.sharpe
    alloc.portfolio_var_95           = metrics.var_95
    alloc.portfolio_max_dd_scenario  = metrics.max_dd_estimate
    alloc.correlation_score          = metrics.correlation_score
    alloc.portfolio_volatility       = metrics.portfolio_volatility

    # Senaryo getirileri
    alloc.scenario_bull_return = round(alloc.expected_return_high_pct, 1)
    alloc.scenario_base_return = round(alloc.expected_return_mid_pct, 1)
    alloc.scenario_bear_loss   = round(-metrics.max_dd_estimate, 1)

    # Olasılık dağılımı (çeşitlendirme skoru yüksekse daha iyi base senaryo)
    div_bonus = int(alloc.diversification_score / 20)
    alloc.scenario_bull_probability = max(15, 35 - div_bonus)
    alloc.scenario_base_probability = min(60, 40 + div_bonus * 2)
    alloc.scenario_bear_probability = max(10, 100 - alloc.scenario_bull_probability - alloc.scenario_base_probability)

    # Tahsis güveni
    div_score = alloc.diversification_score
    corr_score = metrics.correlation_score
    sharpe_score = min(100.0, max(0.0, (metrics.sharpe) * 40 + 50))
    alloc.allocation_confidence = round(
        div_score * 0.3 + corr_score * 0.3 + sharpe_score * 0.4, 1
    )

    return alloc


def calculate_portfolio_metrics_public(
    allocation: "PortfolioAllocation",
) -> "PortfolioMetrics":
    """Belirli bir portföy tahsisi için metrikleri hesapla (public API)."""
    constraints = AllocationConstraints()
    return _calculate_portfolio_metrics(allocation.assets, constraints)


# ═══════════════════════════════════════════════════════════════════════════════
# YAML YÜKLEYICILER
# ═══════════════════════════════════════════════════════════════════════════════

def get_risk_profiles() -> dict:
    """Tüm risk profillerini YAML'dan yükler ve döndürür."""
    path = _CONFIG_DIR / "risk_profiles.yaml"
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data.get("profiles", {})
    except FileNotFoundError:
        logger.error("risk_profiles.yaml bulunamadı: %s", path)
        return {}
    except yaml.YAMLError as exc:
        logger.error("risk_profiles.yaml parse hatası: %s", exc)
        return {}


def get_profile_details(profile_id: str) -> dict:
    """
    Belirli bir risk profilinin detaylarını döndürür.
    Profil bulunamazsa boş dict döner.
    """
    profiles = get_risk_profiles()
    profile = profiles.get(profile_id)
    if profile is None:
        logger.warning("Bilinmeyen risk profili: '%s'", profile_id)
        return {}
    return profile


def _load_asset_universe() -> dict:
    """asset_universe.yaml dosyasını yükler."""
    path = _CONFIG_DIR / "asset_universe.yaml"
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logger.warning("asset_universe.yaml bulunamadı: %s — varsayılan katalog kullanılıyor.", path)
        return {}
    except yaml.YAMLError as exc:
        logger.error("asset_universe.yaml parse hatası: %s", exc)
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# ÇEŞİTLENDİRME SKORU
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_diversification_score(assets: List[PortfolioAsset]) -> float:
    """
    0-100 arasında çeşitlendirme skoru hesaplar.

    Bileşenler:
    1. Varlık sınıfı çeşitliliği  — 30 puan
    2. Tek pozisyon konsantrasyonu — 30 puan (maks pozisyon < %30 ise tam puan)
    3. Sektör dağılımı            — 25 puan
    4. Varlık sayısı              — 15 puan
    """
    if not assets:
        return 0.0

    # ── 1. Varlık sınıfı çeşitliliği (maks 30 puan) ──────────────────────────
    asset_types = {a.asset_type for a in assets}
    # Nakit dahil 6 farklı sınıf mümkün: nakit, tahvil/altin/etf, stock, bist, crypto
    # 3+ sınıf = tam puan
    type_score = min(len(asset_types) / 3.0, 1.0) * 30.0

    # ── 2. Konsantrasyon riski (maks 30 puan) ────────────────────────────────
    max_weight = max((a.weight_pct for a in assets), default=0.0)
    if max_weight <= 15.0:
        conc_score = 30.0
    elif max_weight <= 25.0:
        conc_score = 22.0
    elif max_weight <= 35.0:
        conc_score = 12.0
    else:
        conc_score = 0.0

    # ── 3. Sektör dağılımı (maks 25 puan) ───────────────────────────────────
    sectors = {}
    for a in assets:
        sectors[a.sector] = sectors.get(a.sector, 0.0) + a.weight_pct
    max_sector_weight = max(sectors.values(), default=0.0)
    num_sectors = len(sectors)
    # Sektör yoğunluğu cezası
    if max_sector_weight <= 30.0:
        sector_conc = 15.0
    elif max_sector_weight <= 50.0:
        sector_conc = 8.0
    else:
        sector_conc = 2.0
    # Sektör sayısı ödülü (3+ sektör = tam 10 puan)
    sector_count_score = min(num_sectors / 3.0, 1.0) * 10.0
    sector_score = sector_conc + sector_count_score

    # ── 4. Varlık sayısı (maks 15 puan) ─────────────────────────────────────
    n = len(assets)
    if n >= 10:
        count_score = 15.0
    elif n >= 6:
        count_score = 10.0
    elif n >= 3:
        count_score = 6.0
    else:
        count_score = 2.0

    total = type_score + conc_score + sector_score + count_score
    return round(min(total, 100.0), 1)


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFÖY ÖZET FORMATLAYICISI
# ═══════════════════════════════════════════════════════════════════════════════

def format_portfolio_summary(allocation: PortfolioAllocation) -> str:
    """
    PortfolioAllocation nesnesini okunabilir metin özetine dönüştürür.
    GUI bileşenlerinde veya rapor üretiminde kullanılabilir.
    """
    ccy = allocation.currency
    sep = "─" * 60

    lines = [
        f"{allocation.emoji}  {allocation.name} Portföyü",
        sep,
        f"Bütçe          : {allocation.budget:,.2f} {ccy}",
        f"Yatırılan      : {allocation.total_invested:,.2f} {ccy}  ({100 - allocation.cash_pct:.1f}%)",
        f"Nakit Rezervi  : {allocation.cash_reserved:,.2f} {ccy}  ({allocation.cash_pct:.1f}%)",
        f"Varlık Sayısı  : {allocation.num_assets}",
        f"Çeşitlendirme  : {allocation.diversification_score:.0f}/100",
        "",
        "Getiri Senaryoları (Yıllık):",
        f"  Düşük   : %{allocation.expected_return_low_pct:.1f}",
        f"  Orta    : %{allocation.expected_return_mid_pct:.1f}",
        f"  Yüksek  : %{allocation.expected_return_high_pct:.1f}",
        f"  Maks Kayıp: %{allocation.expected_max_loss_pct:.1f}",
        "",
        "Varlık Sınıfı Dağılımı:",
    ]

    for cls, pct in sorted(allocation.asset_class_distribution.items(), key=lambda x: -x[1]):
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        lines.append(f"  {cls:<12} {bar} {pct:.1f}%")

    lines += ["", "Varlıklar:"]
    for a in sorted(allocation.assets, key=lambda x: -x.weight_pct):
        lines.append(
            f"  {a.symbol:<14} %{a.weight_pct:5.1f}  {a.amount:>10,.2f} {ccy}  [{a.risk_level}]"
        )

    lines += [
        "",
        f"Neden Uygun    : {allocation.why_suitable}",
        "",
        "Ana Riskler:",
    ]
    for i, r in enumerate(allocation.main_risks, 1):
        lines.append(f"  {i}. {r}")

    lines += [
        "",
        f"Yeniden Denge  : {allocation.rebalance_suggestion}",
    ]
    if allocation.monthly_addition_plan:
        lines += ["", f"Aylık Ekleme   : {allocation.monthly_addition_plan}"]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# İÇ YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════════

def _profile_index(profile_id: str) -> int:
    """Profil ID'sinin _PROFILE_ORDER içindeki indeksini döner."""
    try:
        return _PROFILE_ORDER.index(profile_id)
    except ValueError:
        return 2  # dengeli_agresif varsayılanı


def _shift_profile(profile_id: str, delta: int) -> str:
    """
    Profili delta adım kaydırır (negatif = daha korumacı, pozitif = daha agresif).
    Sınırlar aşılırsa kenar profil döner.
    """
    idx = _profile_index(profile_id)
    new_idx = max(0, min(len(_PROFILE_ORDER) - 1, idx + delta))
    return _PROFILE_ORDER[new_idx]


def _risk_level_index(risk_level: str) -> int:
    """Risk seviyesinin _RISK_ORDER içindeki indeksini döner."""
    try:
        return _RISK_ORDER.index(risk_level)
    except ValueError:
        return 2  # orta varsayılanı


def _max_assets_for_budget(budget: float) -> int:
    """Bütçe büyüklüğüne göre maksimum varlık sayısı döner."""
    if budget < 1_000:
        return 4
    elif budget < 10_000:
        return 8
    elif budget < 50_000:
        return 12
    else:
        return 20


def _min_assets_for_budget(budget: float) -> int:
    """Bütçe büyüklüğüne göre minimum varlık sayısı döner."""
    if budget < 1_000:
        return 2
    elif budget < 10_000:
        return 4
    elif budget < 50_000:
        return 6
    else:
        return 8


def _get_rebalance_suggestion(profile: dict) -> str:
    """Profil yeniden denge önerisini döndürür."""
    freq = profile.get("rebalance_frequency", "2ay")
    freq_map = {
        "haftalik": "Her hafta",
        "2hafta":   "Her 2 haftada bir",
        "1ay":      "Her ay",
        "6hafta":   "Her 6 haftada bir",
        "2ay":      "Her 2 ayda bir",
        "3ay":      "Her çeyrekte bir (3 ayda bir)",
    }
    freq_label = freq_map.get(freq, f"Her {freq}")
    return (
        f"{freq_label} portföyü gözden geçirin. "
        "Hedef ağırlıktan %5'ten fazla sapan pozisyonları yeniden dengeleyin. "
        "Büyük piyasa hareketleri sonrasında ek kontrol yapın."
    )


def _build_monthly_plan(
    monthly_addition: float,
    currency: str,
    allocation: PortfolioAllocation,
) -> str:
    """Aylık DCA planı metni üretir."""
    if monthly_addition <= 0:
        return ""
    annual = monthly_addition * 12
    top_assets = sorted(allocation.assets, key=lambda a: -a.weight_pct)[:3]
    asset_names = ", ".join(a.symbol for a in top_assets)
    return (
        f"Aylık {monthly_addition:,.2f} {currency} ({annual:,.2f} {currency}/yıl) DCA stratejisi: "
        f"Her ay başında yeni tutarı mevcut portföy ağırlıklarına göre dağıtın. "
        f"Öncelik sırası: {asset_names}. "
        "Düşüş aylarında ağırlığı biraz artırarak düşük alım maliyetinden faydalanabilirsiniz."
    )


def _asset_class_distribution(assets: List[PortfolioAsset]) -> Dict[str, float]:
    """Varlık sınıfı bazında toplam ağırlık dağılımını hesaplar."""
    dist: Dict[str, float] = {}
    for a in assets:
        dist[a.asset_type] = round(dist.get(a.asset_type, 0.0) + a.weight_pct, 2)
    return dist


def _expected_return_for_asset(asset_type: str, risk_level: str) -> float:
    """Varlık tipi ve risk seviyesine göre yıllık beklenen getiri tahmin eder."""
    base = _EXPECTED_RETURNS.get(asset_type, 12.0)
    mult = _RISK_RETURN_MULTIPLIER.get(risk_level, 1.0)
    return round(base * mult, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# ASSET SEÇİM MATRİSİ
# ═══════════════════════════════════════════════════════════════════════════════

# Her profil için başlangıç varlık sepeti
# Tuple: (symbol, ağırlık_çarpanı)  — çarpanlar normalize edilecek
_PROFILE_ASSET_POOL: Dict[str, Dict[str, List[str]]] = {
    "cok_dengeli": {
        "nakit":          ["CASH"],
        "tahvil_altin":   ["TLT", "GLD"],
        "etf_savunmaci":  ["SPY", "VOO", "VNQ"],
        "hisse_dusuk_risk": ["JNJ", "V", "WMT", "COST"],
        "hisse_buyume":   ["AAPL", "MSFT"],
        "kripto":         [],
    },
    "dengeli": {
        "nakit":          ["CASH"],
        "tahvil_altin":   ["TLT", "GLD"],
        "etf_savunmaci":  ["SPY", "EFA"],
        "hisse_dusuk_risk": ["AAPL", "MSFT", "JPM", "V"],
        "hisse_buyume":   ["QQQ", "NVDA", "AMZN"],
        "kripto":         ["IBIT"],
    },
    "dengeli_agresif": {
        "nakit":          ["CASH"],
        "tahvil_altin":   ["GLD"],
        "etf_savunmaci":  ["SPY"],
        "hisse_dusuk_risk": ["AAPL", "MSFT", "JPM"],
        "hisse_buyume":   ["QQQ", "NVDA", "AMD", "AMZN", "META"],
        "kripto":         ["BTC-USD", "ETH-USD", "IBIT"],
    },
    "orta_riskli": {
        "nakit":          ["CASH"],
        "tahvil_altin":   ["GLD"],
        "etf_savunmaci":  [],
        "hisse_dusuk_risk": ["AAPL", "MSFT"],
        "hisse_buyume":   ["NVDA", "AMD", "TSLA", "PLTR", "CRWD", "QQQ", "SOXX"],
        "kripto":         ["BTC-USD", "ETH-USD", "SOL-USD"],
    },
    "riskli": {
        "nakit":          ["CASH"],
        "tahvil_altin":   [],
        "etf_savunmaci":  [],
        "hisse_dusuk_risk": ["NVDA"],
        "hisse_buyume":   ["TSLA", "PLTR", "COIN", "ARKK", "SOXX", "AMD"],
        "kripto":         ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "AVAX-USD"],
    },
    "cok_riskli": {
        "nakit":          ["CASH"],
        "tahvil_altin":   [],
        "etf_savunmaci":  [],
        "hisse_dusuk_risk": [],
        "hisse_buyume":   ["NVDA", "COIN", "MSTR", "TQQQ"],
        "kripto":         ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "BNB-USD"],
    },
    "ultra_agresif": {
        "nakit":          [],
        "tahvil_altin":   [],
        "etf_savunmaci":  [],
        "hisse_dusuk_risk": [],
        "hisse_buyume":   ["NVDA", "MSTR", "TQQQ", "SOXL", "COIN"],
        "kripto":         ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "XRP-USD", "BNB-USD"],
    },
}

# TRY (Türk yatırımcısı) için BIST ek katmanı
_BIST_ADDITIONS: Dict[str, List[str]] = {
    "cok_dengeli":    ["KCHOL.IS", "SAHOL.IS", "BIMAS.IS"],
    "dengeli":        ["KCHOL.IS", "BIMAS.IS", "ASELS.IS", "EREGL.IS"],
    "dengeli_agresif":["KCHOL.IS", "ASELS.IS", "EREGL.IS", "GARAN.IS", "THYAO.IS"],
    "orta_riskli":    ["ASELS.IS", "GARAN.IS", "THYAO.IS", "KOZAL.IS", "TUPRS.IS"],
    "riskli":         ["THYAO.IS", "GARAN.IS", "VESTL.IS", "KOZAL.IS"],
    "cok_riskli":     ["THYAO.IS", "VESTL.IS", "GARAN.IS"],
    "ultra_agresif":  ["VESTL.IS", "THYAO.IS"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFÖY İNŞA ALTYAPISI
# ═══════════════════════════════════════════════════════════════════════════════

def _select_assets(
    profile_id: str,
    profile_data: dict,
    currency: str,
    budget: float,
    included_types: Optional[List[str]],
    excluded_types: Optional[List[str]],
    max_assets: int,
    min_assets: int,
) -> List[str]:
    """
    Profil ve kısıtlamalara göre seçilecek varlık sembollerini döner.
    Sıralama: profilin havuzundan, her katmanı profil ağırlığıyla orantılı al.
    """
    pool = _PROFILE_ASSET_POOL.get(profile_id, _PROFILE_ASSET_POOL["dengeli"])
    alloc = profile_data.get("allocation", {})

    # Döviz TRY ise BIST katmanını ekle
    if currency == "TRY":
        bist_symbols = _BIST_ADDITIONS.get(profile_id, [])
        # hisse_buyume katmanına ekle
        existing = pool.get("hisse_buyume", [])
        pool = dict(pool)  # shallow copy before mutation
        pool["hisse_buyume"] = list(existing) + bist_symbols

    # excluded types varsayılanları
    excluded_types = excluded_types or []
    included_types = included_types  # None = hepsi dahil

    # Her katmandan kaç varlık alınacağını belirle
    selected: List[str] = []

    # Hangi katmanların aktif olduğunu profil ağırlıklarından belirle
    layer_map = {
        "nakit":            ["nakit"],
        "tahvil_altin":     ["tahvil", "altin", "etf"],
        "etf_savunmaci":    ["etf"],
        "hisse_dusuk_risk": ["stock", "bist"],
        "hisse_buyume":     ["stock", "bist"],
        "kripto":           ["crypto"],
    }

    # Profil ağırlığına göre katman seçim öncelikleri
    layer_weights = {
        "nakit":            alloc.get("nakit", 0),
        "tahvil_altin":     alloc.get("tahvil_altin", 0),
        "etf_savunmaci":    alloc.get("etf_savunmaci", 0),
        "hisse_dusuk_risk": alloc.get("hisse_dusuk_risk", 0),
        "hisse_buyume":     alloc.get("hisse_buyume", 0),
        "kripto":           alloc.get("kripto", 0),
    }
    total_alloc = sum(layer_weights.values()) or 1.0

    for layer_name, symbols in pool.items():
        if not symbols:
            continue
        layer_weight = layer_weights.get(layer_name, 0)
        if layer_weight == 0:
            continue

        # Bu katmana kaç slot düşüyor?
        frac = layer_weight / total_alloc
        slots = max(1, round(frac * max_assets))

        for sym in symbols[:slots]:
            if sym in selected:
                continue
            # Varlık tipi kısıt kontrolü
            cat_entry = _CATALOGUE_INDEX.get(sym)
            if cat_entry:
                atype = cat_entry["asset_type"]
                if included_types and atype not in included_types:
                    continue
                if atype in excluded_types:
                    continue
            selected.append(sym)

    # Nakit her zaman dahil (excluded değilse)
    if "CASH" not in selected and "nakit" not in excluded_types:
        if alloc.get("nakit", 0) > 0:
            selected.insert(0, "CASH")

    # Sınır uygula
    selected = selected[:max_assets]
    return selected


def _distribute_weights(
    symbols: List[str],
    profile_data: dict,
    budget: float,
    cash_preference_pct: float,
    max_single_position_pct: float,
) -> Dict[str, float]:
    """
    Seçilen varlıklar arasında ağırlık dağıtımı yapar.
    Profil katman ağırlıklarını ve kısıtları dikkate alır.
    Döner: {symbol: weight_pct}
    """
    alloc = profile_data.get("allocation", {})
    max_pos = min(max_single_position_pct, profile_data.get("max_single_position_pct", 30.0))

    # Sembol → katman eşlemesi
    layer_of: Dict[str, str] = {}
    for layer, syms in _PROFILE_ASSET_POOL.get(
        profile_data.get("id", "dengeli"), {}
    ).items():
        for s in syms:
            layer_of[s] = layer
    # BIST
    for sym in _CATALOGUE_INDEX:
        if sym.endswith(".IS"):
            layer_of.setdefault(sym, "hisse_buyume")
    layer_of["CASH"] = "nakit"

    # Her sembol için ham ağırlık
    layer_counts: Dict[str, int] = {}
    for sym in symbols:
        l = layer_of.get(sym, "hisse_buyume")
        layer_counts[l] = layer_counts.get(l, 0) + 1

    raw_weights: Dict[str, float] = {}
    for sym in symbols:
        l = layer_of.get(sym, "hisse_buyume")
        layer_pct = alloc.get(l, 5.0)
        count = layer_counts.get(l, 1)
        raw_weights[sym] = layer_pct / count

    # Nakit ağırlığını cash_preference_pct ile override et
    if "CASH" in raw_weights:
        raw_weights["CASH"] = max(raw_weights["CASH"], cash_preference_pct)

    # Normalize
    total = sum(raw_weights.values()) or 1.0
    weights = {sym: (w / total) * 100.0 for sym, w in raw_weights.items()}

    # Maksimum pozisyon kısıtı uygula
    for sym in list(weights.keys()):
        if weights[sym] > max_pos:
            excess = weights[sym] - max_pos
            weights[sym] = max_pos
            # Fazlayı diğerlerine dağıt (nakit hariç)
            others = [s for s in weights if s != sym and s != "CASH"]
            if others:
                share = excess / len(others)
                for o in others:
                    weights[o] += share

    # Yeniden normalize (%100'e yakın olsun)
    total2 = sum(weights.values()) or 1.0
    weights = {sym: round((w / total2) * 100.0, 2) for sym, w in weights.items()}

    # Küçük yuvarlama farkını en büyük pozisyona ekle
    diff = 100.0 - sum(weights.values())
    if weights:
        max_sym = max(weights, key=lambda s: weights[s])
        weights[max_sym] = round(weights[max_sym] + diff, 2)

    return weights


def _build_portfolio_assets(
    symbols: List[str],
    weights: Dict[str, float],
    budget: float,
    currency: str,
    invest_budget: float,  # cash hariç yatırılacak tutar
) -> List[PortfolioAsset]:
    """PortfolioAsset nesnelerini oluşturur."""
    assets: List[PortfolioAsset] = []
    for sym in symbols:
        w = weights.get(sym, 0.0)
        amount = round((w / 100.0) * budget, 2)
        entry = _CATALOGUE_INDEX.get(sym)
        if entry is None:
            logger.debug("Katalogda bulunamadı: %s — atlanıyor", sym)
            continue

        exp_ret = _expected_return_for_asset(entry["asset_type"], entry["risk_level"])

        assets.append(PortfolioAsset(
            symbol=sym,
            name=entry["name"],
            asset_type=entry["asset_type"],
            sector=entry["sector"],
            weight_pct=round(w, 2),
            amount=amount,
            risk_level=entry["risk_level"],
            expected_return_pct=exp_ret,
            why_included=entry["why"],
        ))
    return assets


def _build_why_suitable(
    profile_data: dict,
    horizon: str,
    currency: str,
    budget: float,
    priority: str,
) -> str:
    """Portföyün kullanıcı profiline neden uygun olduğunu açıklayan paragraf üretir."""
    pname = profile_data.get("name", "")
    target_ret = profile_data.get("target_annual_return_pct", 20)
    max_loss = abs(profile_data.get("max_loss_tolerance_pct", -15))
    suitable_for = profile_data.get("suitable_for", "")

    horizon_map = {"kisa": "kısa vadeli", "orta": "orta vadeli", "uzun": "uzun vadeli"}
    horizon_label = horizon_map.get(horizon, horizon)

    priority_map = {
        "buyume":   "sermaye büyümesi",
        "guvenlik": "sermaye koruması",
        "gelir":    "düzenli gelir elde etme",
        "firsat":   "fırsat yakalama",
    }
    priority_label = priority_map.get(priority, priority)

    currency_note = ""
    if currency == "TRY":
        currency_note = " TL bazlı yatırımcı için BIST hisseleri portföye dâhil edilerek yerel piyasa çeşitlendirmesi sağlanmıştır."

    return (
        f"Bu portföy '{pname}' profilindeki {horizon_label} yatırımcılar için tasarlanmıştır. "
        f"Temel öncelik {priority_label} olup yıllık %{target_ret} getiri hedeflenmektedir. "
        f"Maksimum kabul edilebilir kayıp eşiği -%{max_loss} olarak belirlenmiştir. "
        f"Uygun profil: {suitable_for}.{currency_note}"
    )


def _build_main_risks(
    profile_data: dict,
    asset_class_dist: Dict[str, float],
    currency: str,
) -> List[str]:
    """Portföy bileşimine özgü 3-5 ana risk maddesini üretir."""
    risks: List[str] = []
    crypto_pct = asset_class_dist.get("crypto", 0.0)
    etf_pct = asset_class_dist.get("etf", 0.0)
    stock_pct = asset_class_dist.get("stock", 0.0)
    bist_pct = asset_class_dist.get("bist", 0.0)

    vol = profile_data.get("volatility_max_pct", 20)
    risks.append(
        f"Piyasa volatilitesi: Portföy maksimum %{vol} yıllık oynaklık bandında çalışmaktadır. "
        "Beklenmedik makro şoklar kayıpları artırabilir."
    )

    if crypto_pct >= 30:
        risks.append(
            f"Kripto riski: Portföyün %{crypto_pct:.0f}'i kripto varlıklara tahsis edilmiştir. "
            "Düzenleyici değişiklikler ve likidite krizleri sert kayıplara yol açabilir."
        )
    elif crypto_pct > 0:
        risks.append(
            f"Kripto oynaklığı: %{crypto_pct:.0f} kripto ağırlığı portföy volatilitesini artırır; "
            "pozisyonları yakından takip edin."
        )

    if stock_pct + bist_pct >= 50:
        risks.append(
            "Hisse senedi konsantrasyonu: Yüksek hisse ağırlığı piyasa düzeltmelerinde "
            "portföyü orantısız etkiler; sektör çeşitlendirmesini koruyun."
        )

    if currency == "TRY":
        risks.append(
            "Kur ve enflasyon riski: TL bazlı portföyde döviz hareketleri ve yüksek enflasyon "
            "reel getiriyi aşındırabilir. USD/EUR varlıklar bu riski kısmen dengeler."
        )
    elif etf_pct >= 40:
        risks.append(
            "Döviz riski: USD bazlı ETF'lerin yüksek ağırlığı dolar/euro paritesindeki "
            "hareketlere duyarlılık yaratır."
        )

    risks.append(
        "Faiz oranı riski: Merkez bankası politika değişiklikleri özellikle tahvil ve "
        "büyüme hisselerindeki değerlemeleri olumsuz etkileyebilir."
    )

    if profile_data.get("id") in ("cok_riskli", "ultra_agresif"):
        risks.append(
            "Kaldıraç ve spekülatif araç riski: Portföydeki kaldıraçlı ürünler (3x ETF) "
            "süre uzadıkça bileşik kayıp yaratır; kısa vadeli araçlardır."
        )

    return risks[:5]


# ═══════════════════════════════════════════════════════════════════════════════
# ANA PORTFÖY OLUŞTURUCU
# ═══════════════════════════════════════════════════════════════════════════════

def _build_single_allocation(
    variant_name: str,
    variant_emoji: str,
    variant_description: str,
    profile_id: str,
    profiles: dict,
    budget: float,
    currency: str,
    horizon: str,
    priority: str,
    included_types: Optional[List[str]],
    excluded_types: Optional[List[str]],
    monthly_addition: float,
    max_single_position_pct: float,
    cash_preference_pct: float,
    loss_tolerance_pct: float,
) -> PortfolioAllocation:
    """
    Tek bir portföy varyantını (Korumacı / Dengeli / Agresif / Kullanıcı) inşa eder.
    """
    profile_data = profiles.get(profile_id, {})
    if not profile_data:
        logger.warning("Profil bulunamadı: %s — dengeli kullanılıyor", profile_id)
        profile_id = "dengeli"
        profile_data = profiles.get(profile_id, {})

    max_assets = _max_assets_for_budget(budget)
    min_assets = _min_assets_for_budget(budget)

    # Varlık seçimi
    symbols = _select_assets(
        profile_id=profile_id,
        profile_data=profile_data,
        currency=currency,
        budget=budget,
        included_types=included_types,
        excluded_types=excluded_types,
        max_assets=max_assets,
        min_assets=min_assets,
    )

    if not symbols:
        logger.error("Seçilen varlık yok — profil: %s, included_types: %s", profile_id, included_types)
        symbols = ["CASH"]

    # Ağırlık dağıtımı
    profile_cash_pct = profile_data.get("allocation", {}).get("nakit", cash_preference_pct)
    effective_cash_pct = max(cash_preference_pct, profile_cash_pct)

    weights = _distribute_weights(
        symbols=symbols,
        profile_data=profile_data,
        budget=budget,
        cash_preference_pct=effective_cash_pct,
        max_single_position_pct=max_single_position_pct,
    )

    # Nakit ayrımı
    cash_weight = weights.get("CASH", 0.0)
    cash_reserved = round((cash_weight / 100.0) * budget, 2)
    invest_budget = budget - cash_reserved

    # PortfolioAsset nesneleri
    portfolio_assets = _build_portfolio_assets(
        symbols=symbols,
        weights=weights,
        budget=budget,
        currency=currency,
        invest_budget=invest_budget,
    )

    # Getiri hesapları
    target_ret = profile_data.get("target_annual_return_pct", 20.0)
    max_loss_profile = abs(profile_data.get("max_loss_tolerance_pct", -20.0))
    max_loss_user = abs(loss_tolerance_pct)

    # Ufuk çarpanı
    horizon_multiplier = {"kisa": 0.7, "orta": 1.0, "uzun": 1.3}.get(horizon, 1.0)
    target_ret_adj = target_ret * horizon_multiplier

    exp_low = round(target_ret_adj * 0.5, 1)
    exp_mid = round(target_ret_adj * 1.0, 1)
    exp_high = round(target_ret_adj * 1.8, 1)
    exp_max_loss = -round(max(max_loss_profile, max_loss_user) * 1.2, 1)

    # Varlık sınıfı dağılımı
    ac_dist = _asset_class_distribution(portfolio_assets)

    # Çeşitlendirme skoru
    div_score = calculate_diversification_score(portfolio_assets)

    # Neden uygun / ana riskler / yeniden denge
    why_suitable = _build_why_suitable(profile_data, horizon, currency, budget, priority)
    main_risks = _build_main_risks(profile_data, ac_dist, currency)
    rebalance_sug = _get_rebalance_suggestion(profile_data)

    allocation = PortfolioAllocation(
        name=variant_name,
        emoji=variant_emoji,
        description=variant_description,
        budget=budget,
        currency=currency,
        risk_profile=profile_id,
        assets=portfolio_assets,
        total_invested=round(invest_budget, 2),
        cash_reserved=cash_reserved,
        cash_pct=round(cash_weight, 2),
        expected_return_low_pct=exp_low,
        expected_return_mid_pct=exp_mid,
        expected_return_high_pct=exp_high,
        expected_max_loss_pct=exp_max_loss,
        diversification_score=div_score,
        num_assets=len(portfolio_assets),
        asset_class_distribution=ac_dist,
        why_suitable=why_suitable,
        main_risks=main_risks,
        rebalance_suggestion=rebalance_sug,
        monthly_addition_plan="",  # sonradan doldurulacak
    )

    allocation.monthly_addition_plan = _build_monthly_plan(
        monthly_addition=monthly_addition,
        currency=currency,
        allocation=allocation,
    )

    return allocation


def _build_recommendation(
    conservative: PortfolioAllocation,
    balanced: PortfolioAllocation,
    aggressive: PortfolioAllocation,
    risk_profile: str,
    horizon: str,
    priority: str,
) -> tuple[str, str]:
    """
    Kullanıcıya hangi varyantı seçmesi gerektiğini önerir.
    Döner: (recommendation_key, recommendation_reason)
    """
    # Uzun vadeli + büyüme önceliği → dengeli veya agresif
    # Kısa vadeli + güvenlik → korumacı
    # Orta + gelir → dengeli

    if horizon == "kisa" or priority == "guvenlik":
        rec = "conservative"
        rec_name = conservative.name
        reason = (
            f"Kısa vade ve/veya güvenlik önceliğiniz göz önünde bulundurulduğunda "
            f"'{rec_name}' varyantı en uygun seçimdir. "
            "Sermaye koruması sağlarken makul getiri sunar."
        )
    elif horizon == "uzun" and priority in ("buyume", "firsat"):
        # Risk profili agresifse agresifi öner, değilse dengeliyi
        if _profile_index(risk_profile) >= _profile_index("orta_riskli"):
            rec = "aggressive"
            rec_name = aggressive.name
        else:
            rec = "balanced"
            rec_name = balanced.name
        reason = (
            f"Uzun vade ve büyüme odağınız için '{rec_name}' varyantı en yüksek "
            "bileşik büyüme potansiyeli sunar. Kısa vadeli dalgalanmaları tolere edebilirsiniz."
        )
    elif priority == "gelir":
        rec = "balanced"
        rec_name = balanced.name
        reason = (
            f"Düzenli gelir önceliğiniz için '{rec_name}' varyantı temettü ve kupon getirisi "
            "sağlayan varlıklara daha dengeli erişim sunar."
        )
    else:
        rec = "balanced"
        rec_name = balanced.name
        reason = (
            f"Risk-getiri dengesi açısından '{rec_name}' varyantı çoğu yatırım hedefi için "
            "en uygun başlangıç noktasıdır. İlerleyen dönemde profil ayarlanabilir."
        )

    return rec, reason


# ═══════════════════════════════════════════════════════════════════════════════
# ANA API
# ═══════════════════════════════════════════════════════════════════════════════

def build_portfolio(
    budget: float,
    currency: str = "USD",
    risk_profile: str = "dengeli",
    horizon: str = "orta",           # kisa / orta / uzun
    priority: str = "buyume",         # buyume / guvenlik / gelir / firsat
    included_types: Optional[List[str]] = None,
    excluded_types: Optional[List[str]] = None,
    monthly_addition: float = 0.0,
    max_single_position_pct: float = 25.0,
    cash_preference_pct: float = 10.0,
    loss_tolerance_pct: float = -20.0,
) -> PortfolioBuilderResult:
    """
    Kullanıcının profiline ve tercihlerine göre 4 portföy varyantı oluşturur:
    - Korumacı  (kullanıcı profilinden 1 adım daha güvenli)
    - Dengeli   (kullanıcının tam profili)
    - Agresif   (kullanıcı profilinden 1 adım daha riskli)
    - Kullanıcı Tercihi (kullanıcının seçtiği profil; Dengeli ile aynı olabilir)

    Parametreler
    ────────────
    budget                  : Toplam yatırım bütçesi
    currency                : "USD" veya "TRY"
    risk_profile            : Profil ID (bkz. risk_profiles.yaml)
    horizon                 : "kisa" / "orta" / "uzun"
    priority                : "buyume" / "guvenlik" / "gelir" / "firsat"
    included_types          : Sadece bu varlık tipleri dahil edilsin (None=hepsi)
    excluded_types          : Bu varlık tipleri hariç tutulsun
    monthly_addition        : Aylık eklenecek tutar (DCA)
    max_single_position_pct : Tek varlık maks ağırlığı (%)
    cash_preference_pct     : Nakit rezervi tercihi (%)
    loss_tolerance_pct      : Kullanıcının katlandığı max kayıp % (negatif)

    Döner
    ─────
    PortfolioBuilderResult
    """
    # ── Girdi Doğrulama ──────────────────────────────────────────────────────
    if budget <= 0:
        raise ValueError(f"Bütçe sıfırdan büyük olmalıdır, alınan: {budget}")
    if currency not in ("USD", "TRY"):
        logger.warning("Bilinmeyen para birimi '%s' — USD olarak devam edildi.", currency)
        currency = "USD"
    if risk_profile not in _PROFILE_ORDER:
        logger.warning("Bilinmeyen risk profili '%s' — 'dengeli' kullanılıyor.", risk_profile)
        risk_profile = "dengeli"
    if horizon not in ("kisa", "orta", "uzun"):
        logger.warning("Bilinmeyen ufuk '%s' — 'orta' kullanılıyor.", horizon)
        horizon = "orta"
    if loss_tolerance_pct > 0:
        loss_tolerance_pct = -loss_tolerance_pct  # negatif olmalı

    max_single_position_pct = max(5.0, min(max_single_position_pct, 50.0))
    cash_preference_pct = max(0.0, min(cash_preference_pct, 50.0))

    # ── Profilleri Yükle ─────────────────────────────────────────────────────
    profiles = get_risk_profiles()
    if not profiles:
        logger.error("Risk profilleri yüklenemedi — varsayılan profiller oluşturuluyor.")
        profiles = _build_fallback_profiles()

    # ── 3 Varyant için Profil ID'leri ────────────────────────────────────────
    conservative_profile_id = _shift_profile(risk_profile, -1)
    balanced_profile_id = risk_profile
    aggressive_profile_id = _shift_profile(risk_profile, +1)

    logger.info(
        "Portföy inşa ediliyor | Bütçe: %.2f %s | Profil: %s | Ufuk: %s | Öncelik: %s",
        budget, currency, risk_profile, horizon, priority,
    )
    logger.debug(
        "Varyantlar: Korumacı=%s / Dengeli=%s / Agresif=%s",
        conservative_profile_id, balanced_profile_id, aggressive_profile_id,
    )

    # ── Ortak Parametre Seti ─────────────────────────────────────────────────
    common_kwargs = dict(
        profiles=profiles,
        budget=budget,
        currency=currency,
        horizon=horizon,
        priority=priority,
        included_types=included_types,
        excluded_types=excluded_types,
        monthly_addition=monthly_addition,
        max_single_position_pct=max_single_position_pct,
        cash_preference_pct=cash_preference_pct,
        loss_tolerance_pct=loss_tolerance_pct,
    )

    # ── 3 Varyantı İnşa Et ───────────────────────────────────────────────────
    conservative_alloc = _build_single_allocation(
        variant_name="Korumacı",
        variant_emoji="🛡️",
        variant_description="Sermaye koruması ön planda, düşük volatilite.",
        profile_id=conservative_profile_id,
        **common_kwargs,
    )

    balanced_alloc = _build_single_allocation(
        variant_name="Dengeli",
        variant_emoji="⚖️",
        variant_description="Risk ve getiri dengesi, orta vadeli odak.",
        profile_id=balanced_profile_id,
        **common_kwargs,
    )

    aggressive_alloc = _build_single_allocation(
        variant_name="Agresif",
        variant_emoji="🚀",
        variant_description="Yüksek büyüme hedefli, yüksek volatilite toleransı.",
        profile_id=aggressive_profile_id,
        **common_kwargs,
    )

    # ── Kullanıcı Tercihi (tam profil eşleşmesi = Dengeli ile aynı profil) ──
    # Eğer kullanıcı profili dengeli_agresif ise balanced_alloc zaten onun profili.
    # Ayrıca kopyasını user_preference olarak döndürüyoruz (ileride farklılaşabilir).
    user_pref_alloc = copy.deepcopy(balanced_alloc)
    user_pref_alloc.name = "Kullanıcı Tercihi"
    user_pref_alloc.emoji = profiles.get(risk_profile, {}).get("emoji", "📊")
    user_pref_alloc.description = (
        f"Tam profilinize ({profiles.get(risk_profile, {}).get('name', risk_profile)}) "
        "göre kişiselleştirilmiş portföy."
    )

    # ── Öneri ────────────────────────────────────────────────────────────────
    rec_key, rec_reason = _build_recommendation(
        conservative=conservative_alloc,
        balanced=balanced_alloc,
        aggressive=aggressive_alloc,
        risk_profile=risk_profile,
        horizon=horizon,
        priority=priority,
    )

    # ── Kurumsal metrik zenginleştirme ───────────────────────────────────────
    constraints = AllocationConstraints(
        max_single_asset_pct=max_single_position_pct,
        drawdown_tolerance_pct=loss_tolerance_pct,
        cash_min_pct=max(3.0, cash_preference_pct * 0.5),
        kelly_fraction=0.25,
    )
    for alloc in (conservative_alloc, balanced_alloc, aggressive_alloc, user_pref_alloc):
        try:
            _enrich_allocation_metrics(alloc, constraints)
        except Exception as _exc:
            logger.warning("Metrik zenginleştirme hatası: %s", _exc)

    result = PortfolioBuilderResult(
        conservative=conservative_alloc,
        balanced=balanced_alloc,
        aggressive=aggressive_alloc,
        user_preference=user_pref_alloc,
        budget=budget,
        currency=currency,
        risk_profile=risk_profile,
        horizon=horizon,
        recommendation=rec_key,
        recommendation_reason=rec_reason,
    )

    logger.info(
        "Portföy tamamlandı | Korumacı: %d varlık | Dengeli: %d varlık | Agresif: %d varlık | Öneri: %s",
        conservative_alloc.num_assets,
        balanced_alloc.num_assets,
        aggressive_alloc.num_assets,
        rec_key,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# YEDEK PROFİL (YAML yüklenemezse)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_fallback_profiles() -> dict:
    """YAML yüklenemediğinde minimal profil setini döndürür."""
    return {
        "cok_dengeli": {
            "id": "cok_dengeli", "name": "Çok Dengeli", "emoji": "🛡️",
            "target_annual_return_pct": 10, "max_loss_tolerance_pct": -5,
            "volatility_max_pct": 10, "drawdown_tolerance_pct": -8,
            "allocation": {"nakit": 25, "tahvil_altin": 35, "etf_savunmaci": 25,
                           "hisse_dusuk_risk": 10, "hisse_buyume": 5, "kripto": 0},
            "max_single_position_pct": 15, "rebalance_frequency": "3ay",
            "suitable_for": "Sermaye korumacılar",
        },
        "dengeli": {
            "id": "dengeli", "name": "Dengeli", "emoji": "⚖️",
            "target_annual_return_pct": 18, "max_loss_tolerance_pct": -12,
            "volatility_max_pct": 18, "drawdown_tolerance_pct": -15,
            "allocation": {"nakit": 15, "tahvil_altin": 20, "etf_savunmaci": 20,
                           "hisse_dusuk_risk": 20, "hisse_buyume": 20, "kripto": 5},
            "max_single_position_pct": 20, "rebalance_frequency": "2ay",
            "suitable_for": "Orta vadeli yatırımcılar",
        },
        "dengeli_agresif": {
            "id": "dengeli_agresif", "name": "Dengeli-Agresif", "emoji": "📊",
            "target_annual_return_pct": 28, "max_loss_tolerance_pct": -20,
            "volatility_max_pct": 25, "drawdown_tolerance_pct": -22,
            "allocation": {"nakit": 10, "tahvil_altin": 10, "etf_savunmaci": 10,
                           "hisse_dusuk_risk": 20, "hisse_buyume": 35, "kripto": 15},
            "max_single_position_pct": 25, "rebalance_frequency": "6hafta",
            "suitable_for": "Büyüme arayan yatırımcılar",
        },
        "orta_riskli": {
            "id": "orta_riskli", "name": "Orta Riskli", "emoji": "📈",
            "target_annual_return_pct": 40, "max_loss_tolerance_pct": -28,
            "volatility_max_pct": 35, "drawdown_tolerance_pct": -30,
            "allocation": {"nakit": 8, "tahvil_altin": 5, "etf_savunmaci": 5,
                           "hisse_dusuk_risk": 15, "hisse_buyume": 42, "kripto": 25},
            "max_single_position_pct": 30, "rebalance_frequency": "1ay",
            "suitable_for": "Aktif yatırımcılar",
        },
        "riskli": {
            "id": "riskli", "name": "Riskli", "emoji": "🎯",
            "target_annual_return_pct": 65, "max_loss_tolerance_pct": -40,
            "volatility_max_pct": 50, "drawdown_tolerance_pct": -42,
            "allocation": {"nakit": 5, "tahvil_altin": 0, "etf_savunmaci": 0,
                           "hisse_dusuk_risk": 10, "hisse_buyume": 40, "kripto": 45},
            "max_single_position_pct": 35, "rebalance_frequency": "2hafta",
            "suitable_for": "Deneyimli yatırımcılar",
        },
        "cok_riskli": {
            "id": "cok_riskli", "name": "Çok Riskli", "emoji": "🔥",
            "target_annual_return_pct": 100, "max_loss_tolerance_pct": -55,
            "volatility_max_pct": 75, "drawdown_tolerance_pct": -60,
            "allocation": {"nakit": 5, "tahvil_altin": 0, "etf_savunmaci": 0,
                           "hisse_dusuk_risk": 5, "hisse_buyume": 30, "kripto": 60},
            "max_single_position_pct": 40, "rebalance_frequency": "haftalik",
            "suitable_for": "Spekülatörler",
        },
        "ultra_agresif": {
            "id": "ultra_agresif", "name": "Ultra Agresif", "emoji": "💀",
            "target_annual_return_pct": 200, "max_loss_tolerance_pct": -80,
            "volatility_max_pct": 150, "drawdown_tolerance_pct": -80,
            "allocation": {"nakit": 0, "tahvil_altin": 0, "etf_savunmaci": 0,
                           "hisse_dusuk_risk": 0, "hisse_buyume": 20, "kripto": 80},
            "max_single_position_pct": 50, "rebalance_frequency": "haftalik",
            "suitable_for": "Sadece deneyimli spekülatörler",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MODÜL KENDİ KENDİNE TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    print("=" * 70)
    print("  HedgeFund AI — Portfolio Engine Hızlı Test")
    print("=" * 70)

    # Test 1: Orta bütçe, dengeli profil, USD
    result = build_portfolio(
        budget=10_000,
        currency="USD",
        risk_profile="dengeli",
        horizon="orta",
        priority="buyume",
        monthly_addition=500,
    )
    print(f"\nKullanıcı Profili     : {result.risk_profile}")
    print(f"Öneri                 : {result.recommendation}")
    print(f"Öneri Gerekçesi       : {result.recommendation_reason[:80]}...")
    print()
    print(format_portfolio_summary(result.balanced))
    print()

    # Test 2: Büyük bütçe, riskli profil, TRY
    result2 = build_portfolio(
        budget=500_000,
        currency="TRY",
        risk_profile="riskli",
        horizon="uzun",
        priority="firsat",
        monthly_addition=10_000,
        cash_preference_pct=5,
    )
    print("\n" + "=" * 70)
    print(f"TRY Portföyü — Korumacı Varyant:")
    print(format_portfolio_summary(result2.conservative))

    # Test 3: Küçük bütçe, ultra agresif, kısa vade
    result3 = build_portfolio(
        budget=500,
        currency="USD",
        risk_profile="ultra_agresif",
        horizon="kisa",
        priority="firsat",
    )
    print("\n" + "=" * 70)
    print(f"Küçük Bütçe Agresif ({result3.budget} USD):")
    for a in result3.aggressive.assets:
        print(f"  {a.symbol:<14} %{a.weight_pct:.1f}  ${a.amount:,.2f}")
    print(f"  Çeşitlendirme Skoru: {result3.aggressive.diversification_score}")
