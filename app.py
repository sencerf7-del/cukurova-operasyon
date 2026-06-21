from flask import Flask, render_template, request, redirect
import pandas as pd
import os
from supabase import create_client, Client

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SABIT_EKIP = ["ŞAHİN", "SENCER", "SERHAT", "MELİH", "TAHA", "ZEYNEP"]
RENK_SIRALAMASI = ["pers-mavi", "pers-kirmizi", "pers-yesil", "pers-sari", "pers-turkuaz", "pers-mor"]

# 🎯 BURADAKİ TIRNAKLARIN İÇİNE SUPABASE'DEKİ O YEŞİL BUTONDAN KOPYALADIĞIN UZUN ŞİFREYİ YAPIŞTIR KANKA
SUPABASE_URL = "https://y4wsofx8nd1hw3slnndr.supabase.co"
SUPABASE_KEY = "BURAYA_KOPYALADIGIN_UZUN_ANON_PUBLIC_SIFREYI_YAPISTIR"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def saat_temizle(saat_verisi):
    val = str(saat_verisi).strip().lower()
    if not val or val == 'nan' or val == '-' or val == 'nat': return ""
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
        if b_dk > bit_dk: 
            return ucus_dk >= b_dk or ucus_dk < bit_dk
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

def istasyon_ayir(ist_str, tip):
    val = str(ist_str).strip()
    if not val or val == 'nan' or val == '-': return ""
    if "-" in val:
        parcalar = val.split("-")
        if tip == 'arrival':
            return parcalar[0].strip()
        else:
            return parcalar[1].strip()
    return val

@app.route('/')
def ana_sayfa():
    bas_s = int(request.args.get('bas_s', 17))
    bas_d = int(request.args.get('bas_d', 0))
    bit_s = int(request.args.get('bit_s', 9))
    bit_d = int(request.args.get('bit_d', 0))

    try:
        response = supabase.table("ucuslar").select("*").execute()
        ucuslar_raw = response.data
    except Exception as e:
        return f"Supabase Baglanti Hatasi: {str(e)}", 500
    
    personeller = []
    for idx, isim in enumerate(SABIT_EKIP):
        personeller.append({'ad_soyad': isim, 'renk': RENK_SIRALAMASI[idx]})
        
    perf = {isim: 0 for isim in SABIT_EKIP}
    for u in ucuslar_raw:
        p_ad = u['personel_ad']
        if u['tamamlandi'] == 1 and p_ad in perf:
            perf[p_ad] += 1

    duzenli_liste = []
    odak_count = 0
    
    for u in ucuslar_raw:
        p_renk = ""
        for p in personeller:
            if p['ad_soyad'] == u['personel_ad']: p_renk = p['renk']

        h_kod = str(u['havayolu']).split("/")[0].strip() if u['havayolu'] else ""
        if h_kod.lower() == "nan" or h_kod == "-": h_kod = ""

        # ARRIVALS
        if u['gelis_flight'] and str(u['gelis_flight']).strip() != '' and str(u['gelis_flight']).strip().lower() != 'nan':
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
                    'personel_renk': p_renk, 'gece_mi': 1 if is_odak else 0,
                    'revize_mi': 1 if (u['degisti_saat'] == 1 or u['degisti_park'] == 1) else 0
                })
            
        # DEPARTURES
        if u['gidis_flight'] and str(u['gidis_flight']).strip() != '' and str(u['gidis_flight']).strip().lower() != 'nan':
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
                    'personel_renk': p_renk, 'gece_mi': 1 if is_odak else 0,
                    'revize_mi': 1 if (u['degisti_saat'] == 1 or u['degisti_park'] == 1) else 0
                })

    duzenli_liste = sorted(duzenli_liste, key=lambda x: nobet_sirasi_anahtari(x['saat']))
    toplam_ucus = len(duzenli_liste)
    tamamlanan = len([u for u in duzenli_liste if u['tamamlandi'] == 1])
    
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
        df = pd.read_csv(filepath, skiprows=7, dtype=str) if file.filename.endswith('.csv') else pd.read_excel(filepath, skiprows=7, dtype=str)
    except:
        return "Excel okunamadı", 500
    
    for index, row in df.iterrows():
        if len(row) < 9: continue
        
        havayolu_arr = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ''
        gelis_no = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ''
        sta_saat = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else ''
        park_poz = str(row.iloc[8]).strip() if not pd.isna(row.iloc[8]) else ''
        if park_poz.lower() == 'nan' or park_poz == '-': park_poz = ""
        istasyon_ham = str(row.iloc[9]).strip() if len(row) > 9 and not pd.isna(row.iloc[9]) else ''
        
        if "AIRLINE" in havayolu_arr or "ARRIVAL" in havayolu_arr or havayolu_arr.lower() == 'nan': 
            continue
            
        # ARRIVALS BULUT REVİZYON KONTROLÜ
        if gelis_no and gelis_no.lower() != 'nan' and gelis_no != '-':
            if gelis_no.endswith('.0'): gelis_no = gelis_no[:-2]
            if park_poz.endswith('.0'): park_poz = park_poz[:-2]
            
            mevcut = supabase.table("ucuslar").select("*").eq("gelis_flight", gelis_no).execute().data
            if mevcut:
                deg_saat = 1 if mevcut[0]['sta'] != sta_saat else 0
                deg_park = 1 if mevcut[0]['park_pozisyonu'] != park_poz else 0
                supabase.table("ucuslar").update({
                    "havayolu": havayolu_arr, "sta": sta_saat, "park_pozisyonu": park_poz, 
                    "istasyon": istasyon_ham, "degisti_saat": deg_saat, "degisti_park": deg_park
                }).eq("id", mevcut[0]['id']).execute()
            else:
                supabase.table("ucuslar").insert({
                    "havayolu": havayolu_arr, "gelis_flight": gelis_no, "sta": sta_saat, 
                    "park_pozisyonu": park_poz, "istasyon": istasyon_ham
                }).execute()

        # DEPARTURES BULUT REVİZYON KONTROLÜ
        gidis_no = str(row.iloc[5]).strip() if not pd.isna(row.iloc[5]) else ''
        std_saat = str(row.iloc[6]).strip() if not pd.isna(row.iloc[6]) else ''
        
        if gidis_no and gidis_no.lower() != 'nan' and gidis_no != '-':
            if gidis_no.endswith('.0'): gidis_no = gidis_no[:-2]
            if park_poz.endswith('.0'): park_poz = park_poz[:-2]
            
            mevcut_gidis = supabase.table("ucuslar").select("*").eq("gidis_flight", gidis_no).execute().data
            if mevcut_gidis:
                deg_saat = 1 if mevcut_gidis[0]['std'] != std_saat else 0
                deg_park = 1 if mevcut_gidis[0]['park_pozisyonu'] != park_poz else 0
                supabase.table("ucuslar").update({
                    "havayolu": havayolu_arr, "std": std_saat, "park_pozisyonu": park_poz, 
                    "istasyon": istasyon_ham, "degisti_saat": deg_saat, "degisti_park": deg_park
                }).eq("id", mevcut_gidis[0]['id']).execute()
            else:
                supabase.table("ucuslar").insert({
                    "havayolu": havayolu_arr, "gidis_flight": gidis_no, "std": std_saat, 
                    "park_pozisyonu": park_poz, "istasyon": istasyon_ham
                }).execute()

    return redirect('/')

@app.route('/sistemi-sifirla', methods=['POST'])
def sistemi_sifirla():
    supabase.table("ucuslar").delete().neq("id", 0).execute() 
    return redirect('/')

@app.route('/ucus-tamamla/<int:ucus_id>', methods=['POST'])
def ucus_tamamla(ucus_id):
    p_ad = request.form.get('personel_ad')
    supabase.table("ucuslar").update({"tamamlandi": 1, "personel_ad": p_ad}).eq("id", ucus_id).execute()
    return redirect('/')

@app.route('/ucus-geri-al/<int:ucus_id>', methods=['POST'])
def ucus_geri_al(ucus_id):
    supabase.table("ucuslar").update({"tamamlandi": 0, "personel_ad": ""}).eq("id", ucus_id).execute()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
