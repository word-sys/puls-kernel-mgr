<p>
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/puls-k_icon.svg" width="256" height="256" alt="PULS Kernel Manager Simgesi"/>
</p>

# PULS Kernel/GRUB Yöneticisi

> _"2 Gün önce, Debian 12'yi modern bir Acer sisteminde kullanmaya çalışırken, içinde gelen çekirdeğin Acer fan denetleyici yamasını barındırmadığını fark ettim. bookworm-backports'tan çekirdek kurmak beni 6.12.xx sürümünde durdurdu — peki neden daha ileri gitmeyeyelim?"_

PULS Kernel/GRUB Yöneticisi, sistemlerinin çekirdeği ve önyükleme süreci üzerinde ayrıntılı denetime ihtiyaç duyan Linux kullanıcıları için özel olarak geliştirilmiş bir araçtır. Anlık görüntüler ve Güvenli Önyükleme yönetimi aracılığıyla sistem güvenliğini sağlarken ana hat çekirdeklerin getirilmesini, derlenmesini ve kurulmasını kolaylaştırır.

<p align="center">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss0.png" width="49%">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss1.png" width="49%">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss2.png" width="49%">
  <img src="https://raw.githubusercontent.com/word-sys/puls-kernel-mgr/main/screenshots/ss3.png" width="49%">
</p>

> **Durum:** Yoğun geliştirme aşamasında — pürüzler ve hatalar olabilir, ancak çalışıyor!

> [!WARNING]
> **Sorumluluk Reddi & Yasal Uyarı**: Bu yazılım sistem çekirdeği dosyalarını ve GRUB önyükleme yapılandırmasını yönetir. GNU Genel Kamu Lisansı v3.0 kapsamında bu yazılım HERHANGİ BİR GARANTİ VERİLMEDEN dağıtılmaktadır. Geliştirici ve katkıda bulunanlar, olası sistem kararsızlıkları, önyükleme hataları veya veri kayıplarından sorumlu tutulamaz. Özel çekirdekler kurmadan önce sistem anlık görüntüsü (ör. Timeshift) almanız önerilir.

---

## Özellikler

### Gösterge Paneli
- Çalışan çekirdek sürümünün canlı genel görünümü
- Mevcut GRUB varsayılan girişinin tek bakışta görünümü
- `/boot` disk boş alanı
- Hızlı eylem düğmeleri: Anlık Görüntü Oluştur, Çekirdek Listesini Yenile

### Çekirdek Yönetimi
- **Paket Yöneticili Derleme (`bindeb-pkg`)**: Çekirdek derlemelerini doğrudan `.deb` paketlerine dönüştürür ve sistem paket veritabanı bütünlüğünü korumak için `apt`/`dpkg` ile kurar.
- **Ana Hat Getirme**: kernel.org'dan en güncel kararlı ve RC çekirdeklerini getirme
- **Linux-Zen Desteği**: Performans odaklı Linux-Zen çekirdeklerini getirme, derleme, paketleme ve kurma
- **Hazır DEB Çekirdekleri**: Önceden derlenmiş `.deb` çekirdek paketlerini indirme ve kurma (ör. `prebuiltkernels.com`)
- **GPG Doğrulama**: Açmadan önce şifreli imza denetimi
- **Özelleştirilmiş Derleme**: `localmodconfig` ile donanıma özgü, sade bir çekirdek oluşturma
- **menuconfig Desteği**: Derlemeden önce isteğe bağlı etkileşimli çekirdek yapılandırması
- **Paket Temizleme (Purge)**: Kurulu çekirdek paketlerini `apt-get purge` ile sistemden temizce kaldırma
- **Otomatik DKMS**: Yeni çekirdekler için modülleri (ör. NVIDIA) yeniden derleme
- **Bağımlılık Otomasyonu**: Derleme öncesinde gerekli tüm derleme araçlarını otomatik kurma

### Önyükleme & GRUB Denetimi
- **Parametre Ayarı**: Çekirdek parametrelerini ve GRUB ayarlarını değiştirme
- **Önyükleme Sırası Görüntüleyici**: Varsayılan ayar düğmeleriyle görselleştirilmiş önyükleme girişi yönetimi
- **Tek Seferlik Önyükleme**: Varsayılanı değiştirmeden tek seferlik önyükleme girişi belirleme (`grub-reboot`)
- **Güvenlik Yedeklemeleri**: Kuru çalıştırma doğrulamasıyla zaman damgalı GRUB yapılandırma yedekleri
- **Yedek Geçmişi**: Önceki GRUB yedeklerini görüntüleme ve geri yükleme

### Güvenlik & Emniyet
- **Sistem Anlık Görüntüleri**: Anlık görüntü geçmişiyle tümleşik Timeshift desteği
- **Bağımlılık Durumu**: Gerekli tüm araçlar için paket bazında Tamam/Hata gösterimi
- **Güvenli Önyükleme (MOK)**: Eksiksiz Makine Sahibi Anahtarı yönetimi
- **Panik Analizi**: `pstore` ve `kdump` kaynaklı çekirdek panik günlüklerini çıkarma ve analiz etme

---

## Kurulum

### Debian Paketi (.deb) Kurulumu — Önerilen

```bash
sudo apt update
sudo apt install ./puls-kernel-mgr_*.deb
```

### Kaynaktan Derleme

```bash
git clone https://github.com/word-sys/puls-kernel-mgr.git
cd puls-kernel-mgr
pip install .
```

### Bağımlılıklar

**Zorunlu:**
```
python3-gi  gir1.2-adw-1  gir1.2-gtk-4.0  pkexec  grub2-common
tar  wget  xz-utils  gpg  openssl  mokutil  dkms  librsvg2-common
```

**Derleme araçları (ilk çalıştırmada otomatik kurulur):**
```
build-essential  flex  bison  libncurses-dev  libssl-dev  libelf-dev  bc  rsync  fakeroot  dpkg-dev  debhelper  kmod
```

**İsteğe bağlı:**
```
timeshift  btrfs-progs  kdump-tools
```

---

## Kullanım

**Grafiksel Arayüz (GTK4/Libadwaita):**
```bash
puls-kernel-mgr-gtk
```

**Komut Satırı Arayüzü:**
```bash
puls-kernel-mgr                            
```

---

## Teşekkürler & Kaynaklar

- **[kernel.org](https://kernel.org)** — Ana hat Linux çekirdek kaynak arşivleri
- **[zen-kernel](https://github.com/zen-kernel/zen-kernel)** — Linux-Zen performans yamaları
- **[prebuiltkernels.com](https://prebuiltkernels.com)** — Derlenmiş hazır Debian/Ubuntu `.deb` çekirdek paketleri

---

**Geliştirici:** Barın Güzeldemirci  
**Lisans:** GPL-3.0  
