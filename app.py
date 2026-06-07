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
    '''' lines)
    conn.commit()
    conn.close()

def zaman_aralikta_mi(saat_str, bas_s, bas_d, bit_s, bit_d):
    try:
        if not saat_str or ":" not in str(saat_str): return False
        h, m = map(int, str(saat_str).split(":"))
        ucus_dk = h * 60 + m
        b_dk, bit_dk = bas_s * 60 + bas_d, bit_s * 60 + bit_d
        if b_dk > bit_dk: return ucus_dk >= b_dk or ucus_dk < bit_dk
        return b_dk <= ucus_dk < bit_dk
    except: return False

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

    ucuslar = []
    odak_count = 0
    for u in ucuslar_raw:
        is_odak = zaman_aralikta_mi(u['sta'], bas_s, bas_d, bit_s, bit_d) or zaman_aralikta_mi(u['std'], bas_s, bas_d, bit_s, bit_d)
        if is_odak: odak_count += 1
        p_renk = ""
        for p in personeller:
            if p['ad_soyad'] == u['personel_ad']: p_renk = p['renk']
                
        ucuslar.append({
            'id': u['id'], 'havayolu': u['havayolu'], 'gelis_flight': u['gelis_flight'],
            'sta': u['sta'], 'gidis_flight': u['gidis_flight'], 'std': u['std'],
            'park_pozisyonu': u['park_pozisyonu'], 'istasyon': u['istasyon'],
            'tamamlandi': u['tamamlandi'], 'personel_ad': u['personel_ad'], 
            'personel_renk': p_renk, 'gece_mi': 1 if is_odak else 0
        })
    toplam_ucus = len(ucuslar)
    tamamlanan = len([u for u in ucuslar if u['tamamlandi'] == 1])
    conn.close()
    return render_template('index.html', ucuslar=ucuslar, personeller=personeller, 
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
        if len(row) < 10: continue
        havayolu = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ''
        gelis_flight = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ''
        sta = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else ''
        gidis_flight = str(row.iloc[5]).strip() if not pd.isna(row.iloc[5]) else ''
        std = str(row.iloc[6]).strip() if not pd.isna(row.iloc[6]) else ''
        park = str(row.iloc[8]).strip() if not pd.isna(row.iloc[8]) else ''
        istasyon = str(row.iloc[9]).strip() if not pd.isna(row.iloc[9]) else ''
        if "AIRLINE" in havayolu or "ARRIVAL" in havayolu or (not gelis_flight and not gidis_flight): continue
        if gelis_flight.endswith('.0'): gelis_flight = gelis_flight[:-2]
        if gidis_flight.endswith('.0'): gidis_flight = gidis_flight[:-2]
        if park.endswith('.0'): park = park[:-2]
        mevcut = cursor.execute('SELECT id FROM ucuslar WHERE havayolu=? AND gelis_flight=? AND gidis_flight=?', (havayolu, gelis_flight, gidis_flight)).fetchone()
        if mevcut:
            cursor.execute('UPDATE ucuslar SET sta=?, std=?, park_pozisyonu=?, istasyon=? WHERE id=?', (sta, std, park, istasyon, mevcut[0]))
        else:
            cursor.execute('INSERT INTO ucuslar (havayolu, gelis_flight, sta, gidis_flight, std, park_pozisyonu, istasyon) VALUES (?, ?, ?, ?, ?, ?, ?)', (havayolu, gelis_flight, sta, gidis_flight, std, park, istasyon))
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
