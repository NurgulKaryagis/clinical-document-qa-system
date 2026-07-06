# ADR-001: Chunking Strategy — Section Boundary Detection

## Status
Accepted

## Context
Klinik protokoller, ilaç prospektüsleri ve tıbbi kılavuzlar bölüm bazlı
yapılandırılmış dokümanlardır (Endikasyonlar, Dozaj, Yan Etkiler, vb.).
Sistemin temel kuralı: bölüm içerikleri chunk'lara karışmamalı, her chunk
tek bir bölümden gelmeli, bölüm başlığı metadata olarak saklanmalı.

Soru: Unstructured.io çıktısından bölüm sınırlarını nasıl tespit edeceğiz?

## Decision
Unstructured.io'nun kendi element tiplerine güveniyoruz.
`Title` elementi → yeni chunk başlat.
`NarrativeText` ve `Table` elementleri → mevcut bölüme ekle.
Ekstra post-processing yok.

## Options Considered

### Option A: Unstructured element tiplerine güven (Seçilen)
- Pros:
  - Kod minimal, bakım yükü düşük
  - Klinik dokümanlar genellikle iyi yapılandırılmış — Unstructured tespiti yeterli
  - Hızlı itere edilebilir; sorun çıkarsa B'ye geçmek kolay
- Cons:
  - Kötü taranmış veya düzensiz PDF'lerde `Title` tespiti hatalı olabilir
  - Unstructured'ın kararlarına bağımlıyız

### Option B: Unstructured + özel post-processing
- Pros:
  - Daha kontrollü: kısa `Title`'lar gerçek başlık, `Table`'lar her zaman ayrı chunk
  - Unstructured hatalı tespit etse bile düzeltilebilir
- Cons:
  - Ekstra kod = ekstra karmaşıklık
  - Klinik dokümanlar için şu an gerekli değil

### Option C: Kural tabanlı (regex + karakter analizi)
- Pros:
  - Unstructured'a bağımlılık yok
- Cons:
  - Kırılgan — her PDF formatı için ayrı kural
  - Bakım maliyeti yüksek

### Neden Semantic Chunking Değil?
Semantic chunking anlam kaymasına göre sınır koyar, başlıklara göre değil.
Klinik dokümanlarda "Metformin günde 2 kez alınır" ve "Böbrek yetmezliğinde
kontrendikedir" cümleleri anlamca yakın görünebilir — ama biri Dozaj,
diğeri Kontrendikasyon bölümünde. Semantic chunking bunları birleştirebilir.
Bu projenin hard rule'u: bölüm içerikleri karışmamalı. Semantic chunking bu
kuralı ihlal etme riskini taşıdığı için değerlendirmeye alınmadı.

## Reasoning
Klinik dokümanlar yapılandırılmış belgelerdir ve Unstructured.io bu tür
belgeler için optimize edilmiştir. Şu an için A yeterli; eğer gerçek
dokümanlarla test sırasında `Title` tespiti yetersiz kalırsa B'ye geçmek
kolaydır. Gereksiz erken karmaşıklıktan kaçınıyoruz.

## Consequences
- Unstructured.io'nun element tespiti pipeline'ın doğruluğunu doğrudan etkiler
- İlk testlerde `Title` elementlerini gözlemleyerek tespit kalitesini doğrulamak gerekir
- Post-processing eklemek her zaman mümkün — bu karar geri alınabilir

## What Would Break If We Changed This
B veya C'ye geçersek: chunking katmanındaki tüm birim testleri ve
Unstructured çıktısına dayanan entegrasyon testleri yeniden yazılmalı.
Weaviate'e yüklenen chunk formatı değişmez, ama chunk sınırları değişir —
RAGAS faithfulness skorları etkilenebilir.
