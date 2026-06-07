from flask import Flask, render_template, request, redirect
import sqlite3
import pandas as pd
import os

app = Flask(__name__)
DB_NAME = "havalimanı_operasyon.db"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SABIT_EKIP = ["ŞAHİN", "SENCER", "SERHAT", "MELİH", "TAHA", "ZEYNEP"]
RENK_SIRALAMASI = ["pers-mavi", "pers-kirmizi", "pers-yesil", "pers-sari", "pers-turkuaz", "pers-mor"]

def veritabanini_kur():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ucuslar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            havayolu TEXT,
            gelis_flight TEXT,
            sta TEXT,
            gidis_flight TEXT,
            std TEXT,
            park_pozisyonu TEXT,
            istasyon TEXT,
            tamamlandi INTEGER DEFAULT 0,
            personel_ad TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()

def saat_temizle(saat_verisi):
    val = str(saat_verisi).strip()
    if not val or val == 'nan' or val == '-': return ""
    if " " in val:
        val = val.split(" ")[-1]
    if ":" in val:
        parcalar = val.split(":")
        try:
            return f"{int(parcalar[0]):02d}:{int(parcalar[1]):02d}"
        except:
            return ""
    return ""

def zaman_aralikta_mi(saat_str, bas_s, bas_d, bit_s, bit_d):
    try:
        if not saat_str or ":" not in str(saat_str): return False
        h, m = map(int, str(saat_str).split(":"))
        ucus_dk = h * 60 + m
        b_dk, bit_dk = bas_s * 60 + bas_d, bit_s * 60 + bit_d
        if b_dk > bit_dk: return ucus_dk >= b_dk or ucus_dk < bit_dk
        return b_dk <= ucus_dk < bit_dk
    except: return False

def nobet_sirasi_anahtari(saat_str):
    if not saat_str or ":" not in saat_str: return 9999
    try:
        h, m = map(int, saat_str.split(":"))
        dakika = h * 60 + m
        if h >= 17:
            return dakika - (17 * 60)
        else:
            return dakika + (7 * 60)
    except:
        return 9999

# 🌍 İSTASYON PARÇALAMA MOTORU (Örn: AMS - ESB yapısını böler)
def istasyon_ayir(ist_str, tip):
    val = str(ist_str).strip()
    if not val or val == 'nan' or val == '-': return ""
    if "-" in val:
        parcalar = val.split("-")
        if tip == 'arrival':
            return parcalar[0].strip() # İlk kısım (Nereden geldiği)
        else:
            return parcalar[1].strip() # İkinci kısım (Nereye gittiği)
    return val

@app.route('/')
def ana_sayfa():
    bas_s = int(request.args.get('bas_s', 17))
    bas_d = int(request.args.get('bas_d', 0))
    bit_s = int(request.args.get('bit_s', 9))
    bit_d = int(request.args.get('bit_d', 0))

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    ucuslar_raw = cursor.execute('SELECT * FROM ucuslar').fetchall()
    
    personeller = []
    for idx, isim in enumerate(SABIT_EKIP):
        personeller.append({'ad_soyad': isim, 'renk': RENK_SIRALAMASI[idx]})
        
    perf = {isim: {'gunluk': 0, 'haftalik': 0, 'aylik': 0, 'tumu': 0} for isim in SABIT_EKIP}
    for u in ucuslar_raw:
        p_ad = u['personel_ad']
        if u['tamamlandi'] == 1 and p_ad in perf:
            perf[p_ad]['gunluk'] += 1
            perf[p_ad]['haftalik'] += 1
            perf[p_ad]['aylik'] += 1
            perf[p_ad]['tumu'] += 1

    duzenli_liste = []
    odak_count = 0
    
    for u in ucuslar_raw:
        p_renk = ""
        for p in personeller:
            if p['ad_soyad'] == u['personel_ad']: p_renk = p['renk']

        # Havayolu kodunun sadece iki harfli kısmını veya ilk parçasını alıyoruz (Örn: XQ / SXS -> XQ)
        h_kod = str(u['havayolu']).split("/")[0].strip() if u['havayolu'] else ""
        if h_kod == "nan": h_kod = ""

        # ARRIVALS (GELİŞLER)
        if u['gelis_flight'] and str(u['gelis_flight']).strip() != '' and str(u['gelis_flight']).strip() != 'nan':
            g_flight = str(u['gelis_flight']).strip()
            if g_flight.endswith('.0'): g_flight = g_flight[:-2]
            
            cleaned_sta = saat_temizle(u['sta'])
            if cleaned_sta:
                is_odak = zaman_aralikta_mi(cleaned_sta, bas_s, bas_d, bit_s, bit_d)
                if is_odak: odak_count += 1
                
                duzenli_liste.append({
                    'id': u['id'], 'havayolu_kod': h_kod, 'flight_no': g_flight,
                    'saat': cleaned_sta, 'tip': 'arrival', 'park': u['park_pozisyonu'],
                    'meydan': istasyon_ayir(u['istasyon'], 'arrival'),
                    'tamamlandi': u['tamamlandi'], 'personel_ad': u['personel_ad'], 
                    'personel_renk': p_renk, 'gece_mi': 1 if is_odak else 0
                })
            
        # DEPARTURES (GİDİŞLER)
        if u['gidis_flight'] and str(u['gidis_flight']).strip() != '' and str(u['gidis_flight']).strip() != 'nan':
            gi_flight = str(u['gidis_flight']).strip()
            if gi_flight.endswith('.0'): gi_flight = gi_flight[:-2]
            
            cleaned_std = saat_temizle(u['std'])
            if cleaned_std:
                is_odak = zaman_aralikta_mi(cleaned_std, bas_s, bas_d, bit_s, bit_d)
                if is_odak: odak_count += 1
                
                duzenli_liste.append({
                    'id': u['id'], 'havayolu_kod': h_kod, 'flight_no': gi_flight,
                    'saat': cleaned_std, 'tip': 'departure', 'park': u['park_pozisyonu'],
                    'meydan': istasyon_ayir(u['istasyon'], 'departure'),
                    'tamamlandi': u['tamamlandi'], 'personel_ad': u['personel_ad'], 
                    'personel_renk': p_renk, 'gece_mi': 1 if is_odak else 0
                })

    # ⏱️ AKŞAM 17:00'DEN SABAH 09:00'A KUSURSUZ NOBET SIRALAMASI
    duzenli_liste = sorted(duzenli_liste, key=lambda x: nobet_sirasi_anahtari(x['saat']))

    toplam_ucus = len(duzenli_liste)
    tamamlanan = len([u for u in duzenli_liste if u['tamamlandi'] == 1])
    conn.close()
    
    return render_template('index.html', ucuslar=duzenli_liste, personeller=personeller, 
                           toplam_ucus=toplam_ucus, gece_ucus=odak_count, tamamlanan_ucus=tamamlanan,
                           perf=perf, bas_s=bas_s, bas_d=bas_d, bit_s=bit_s, bit_d=bit_d)

@app.route('/excel-yukle', methods=['POST'])
def excel_yukle():
    if 'excel_file' not in request.files: return redirect('/')
    file = request.files['excel_file']
    if file.filename == '': return redirect('/')
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    try:
        df = pd.read_csv(filepath, skiprows=7) if file.filename.endswith('.csv') else pd.read_excel(filepath, skiprows=7)
    except:
        return "Excel okunamadı", 500
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for index, row in df.iterrows():
        if len(row) < 4: continue
        
        havayolu_arr = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ''
        gelis_no = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ''
        sta_saat = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else ''
        park_poz = str(row.iloc[4]).strip() if len(row) > 4 and not pd.isna(row.iloc[4]) else ''
        istasyon_ham = str(row.iloc[9]).strip() if len(row) > 9 and not pd.isna(row.iloc[9]) else ''
        
        if "AIRLINE" in havayolu_arr or "ARRIVAL" in havayolu_arr: 
            continue
            
        if gelis_no and gelis_no != 'nan' and gelis_no != '-':
            if gelis_no.endswith('.0'): gelis_no = gelis_no[:-2]
            if park_poz.endswith('.0'): park_poz = park_poz[:-2]
            
            cursor.execute('INSERT INTO ucuslar (havayolu, gelis_flight, sta, park_pozisyonu, gidis_flight, std, istasyon) VALUES (?, ?, ?, ?, "", "", ?)', 
                           (havayolu_arr, gelis_no, sta_saat, park_poz, istasyon_ham))

        if len(row) >= 8:
            havayolu_dep = str(row.iloc[5]).strip() if not pd.isna(row.iloc[5]) else ''
            gidis_no = str(row.iloc[6]).strip() if not pd.isna(row.iloc[6]) else ''
            std_saat = str(row.iloc[7]).strip() if not pd.isna(row.iloc[7]) else ''
            park_dep = str(row.iloc[8]).strip() if len(row) > 8 and not pd.isna(row.iloc[8]) else park_poz
            
            if "AIRLINE" in havayolu_dep or "DEPARTURE" in havayolu_dep:
                continue
                
            if (havayolu_dep == '' or havayolu_dep == 'nan') and havayolu_arr != '':
                havayolu_dep = havayolu_arr
                
            if gidis_no and gidis_no != 'nan' and gidis_no != '-':
                if gidis_no.endswith('.0'): gidis_no = gidis_no[:-2]
                if park_dep.endswith('.0'): park_dep = park_dep[:-2]
                
                cursor.execute('INSERT INTO ucuslar (havayolu, gelis_flight, sta, park_pozisyonu, gidis_flight, std, istasyon) VALUES (?, "", "", ?, ?, ?, ?)', 
                               (havayolu_dep, park_dep, gidis_no, std_saat, istasyon_ham))

    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/sistemi-sifirla', methods=['POST'])
def sistemi_sifirla():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ucuslar')
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/ucus-tamamla/<int:ucus_id>', methods=['POST'])
def ucus_tamamla(ucus_id):
    p_ad = request.form.get('personel_ad')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE ucuslar SET tamamlandi = 1, personel_ad = ? WHERE id = ?', (p_ad, ucus_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/ucus-geri-al/<int:ucus_id>', methods=['POST'])
def ucus_geri_al(ucus_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE ucuslar SET tamamlandi = 0, personel_ad = "" WHERE id = ?', (ucus_id,))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        open(DB_NAME, 'w').close()
    veritabanini_kur()
    app.run(host='0.0.0.0', port=5000, debug=False)
