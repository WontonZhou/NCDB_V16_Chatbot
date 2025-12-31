#!/usr/bin/env python3
import os, sys, django, re, pytz
from bs4 import BeautifulSoup
from datetime import datetime

# Django setup
sys.path.append('/home/ncdbproj/CadillacDBProj')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CadillacDB.settings')
django.setup()
from V16.models import V16_Cardetails, V16_CardetailsAsset, V16_Carimages, V16_Chapters

# Config
HTML_DIR = '/home/metacomp/NCDBContent/CDB/Dbas_txt/'
YR_CFG = {
    "1930": {"html_files": ['V6srv30.htm', 'V6srv30a-sambeat.htm', 'V6srv30b.htm'], "range": (700001, 703252), "caryear": 1930},
    "1932": {"html_files": ['V6srv32old.htm'], "range": (1400000, 1400298), "caryear": 1932},
    "1933": {"html_files": ['V6srv33.htm'], "range": (5000000, 5000117), "caryear": 1933},
    "1934_37": {"html_files": ['V6srv34.htm'], "range": (5100000, 5130349), "caryear": 1934},
    "1938_40": {"html_files": ['V6srv38.htm', 'V6SRV38b.HTM'], "range": (5270000, 5320412), "caryear": 1938}
}

def clean_txt(txt):
    # Remove HTML and normalize whitespace
    if not txt: return ''
    txt = re.sub(r'<[^>]+>', '', str(txt))
    txt = txt.replace('&nbsp;', ' ').replace('\xa0', ' ').replace('&eacute;', 'e').replace('&amp;', '&')
    txt = txt.replace('&#147;', '"').replace('&#148;', '"').replace('&#146;', "'").replace('&#150;', '-').replace('&quot;', '"')
    txt = re.sub(r'\s+', ' ', txt).strip()
    # Remove problematic non-ASCII chars for MySQL
    txt = txt.encode('ascii', 'ignore').decode('ascii')
    return txt

def get_engine(txt, rng):
    # Extract and validate engine number
    if not txt: return (None, '')
    clean = clean_txt(txt)
    # look for 6-7 digit numbers
    for m in re.findall(r'(\d{6,7})', clean):
        try:
            n = int(m)
            if rng[0] <= n <= rng[1]: return (n, clean)
        except: continue
    return (None, clean)

def parse_htm(path, rng):
    # Parse HTM
    recs = []
    if not os.path.exists(path):
        print(f"  Warning: {path} not found")
        return recs
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    cur = None
    for tbl in soup.find_all('table'):
        rows = tbl.find_all('tr')
        # skip rows less then 3
        if len(rows) < 3: continue
        
        for row in rows:
            # look for <td> if not then skip
            cells = row.find_all('td')
            if not cells: continue
            
            # Image only row are colspan or single cell
            # After having we can get a lot more images
            if len(cells) == 1 or cells[0].get('colspan'):
                if cur:
                    for img in row.find_all('img'):
                        src = img.get('src', '')
                        if src: cur['imgs'].append(src)
                continue
            
            # Skip header
            c0 = cells[0].get_text()
            if 'Body' in c0 and ('Style' in c0 or 'Number' in c0): continue
            
            # Data row
            if len(cells) >= 3:
                eng, etxt = get_engine(cells[2].get_text(), rng)
                cur = {
                    'bstyle': clean_txt(cells[0].get_text()), # Body Style
                    'bnum': clean_txt(cells[1].get_text()) if len(cells) > 1 else '', # Body Number
                    'eng': eng, 'etxt': etxt, # Engine number
                    'desc': clean_txt(cells[3].get_text()) if len(cells) > 3 else '', # description
                    'imgs': [], 'src': os.path.basename(path)
                }
                # if tehre are images in description cell
                if len(cells) > 3:
                    for img in cells[3].find_all('img'):
                        src = img.get('src', '')
                        if src: cur['imgs'].append(src)
                recs.append(cur)
    return recs

def assign_engs(recs, cfg):
    # Assign missing engine numbers from available range
    rng = cfg['range']
    # we have 2 groups, the ones have engine nums and the ones have no eng nums
    has = [r for r in recs if r['eng']]
    none = [r for r in recs if not r['eng']]
    # the engine numbers used already and the available ones
    used = set(r['eng'] for r in has)
    avail = sorted([n for n in range(rng[0], rng[1]+1) if n not in used])
    
    # loop through non and assign engine numbers
    for i, r in enumerate(none):
        if i < len(avail):
            r['eng'] = avail[i]
            r['etxt'] = f"{avail[i]} (assigned)"
            r['gen'] = True
        else:
        # if  avail numbers are out then use this logic
            r['eng'] = 999000 + i + 1
            r['etxt'] = f"Unknown-{i+1}"
            r['gen'] = True
    
    # flag those already have engine numbers
    for r in has: r['gen'] = False
    return has + none

def save_db(recs, cfg):
    # Import records to V16 database, 63 is V16
    chap = V16_Chapters.objects.get(chapterid=63)
    # create a timezone because django needs it
    tz = pytz.UTC
    now = tz.localize(datetime.now())
    
    # Get next image number
    maximg = V16_Carimages.objects.latest('imagenum').imagenum if V16_Carimages.objects.exists() else 0
    imgnum = maximg + 1
    
    yr = cfg['caryear']
    cnt_cars = cnt_imgs = 0
    
    # loop and create car_id 
    for i, r in enumerate(recs, 1):
        eng = r['eng']
        gen = r.get('gen', False)
        cid = f"{yr}-{eng}"
        
        # crate folder names for timeline
        if eng and eng < 900000:
        # for example if eng = 700003, off = 0003, m = (0 // 100) % 12 + 1 = 1, d = (03 % 100) % 28 + 1 = 4
            off = eng % 10000
            m = (off // 100) % 12 + 1
            d = (off % 100) % 28 + 1
            fld = f"{yr}.{m:02d}.{d:02d}"
        else:
            fld = f"{yr}.12.{(i % 28) + 1:02d}"
        
        # create titles
        ttl = f"#{eng} - {r['bstyle']}"[:30] if eng and r['bstyle'] else f"#{eng}"[:30]
        
        # Engine display with asterisk
        edisp = f"<td>{r['etxt']}"
        if gen: edisp += " <span style='color: red; font-style: italic;'>*</span>"
        edisp += "</td>"
        
        # Detail content
        detail = f"""
                <div class="survivor-info" style="padding: 20px;">
                    <div class="alert alert-info">
                        <strong>Note:</strong> This record was imported from the {yr} registry database. Photo gallery integration pending.
                    </div>
        
                    <h3>{yr} V16 Survivor Information</h3>
        
                    <table class="table table-bordered survivor-details" style="width: 100%; margin: 20px 0;">
                        <tbody>
                            <tr>
                                <td width="30%" style="background: #f5f5f5;"><strong>Body Style:</strong></td>
                                <td>{r['bstyle']}</td>
                            </tr>
                            <tr>
                                <td style="background: #f5f5f5;"><strong>Body Number:</strong></td>
                                <td>{r['bnum']}</td>
                            </tr>
                            <tr>
                                <td style="background: #f5f5f5;"><strong>Engine Number:</strong></td>
                                {edisp}
                            </tr>
                        </tbody>
                    </table>
        
                    {f'''<div class="alert alert-warning" style="margin-top: 15px;">
                        <strong>Note:</strong> Engine numbers marked with <span style="color: red; font-style: italic;">*</span> are unknown and temporary engine numbers are assigned pending discovery of the actual number.
                    </div>''' if gen else ''}
        
                    <h4>Description</h4>
                    <div class="description-text" style="line-height: 1.6; margin: 15px 0;">
                        <p>{r['desc']}</p>
                    </div>
        
                    {f'<div class="alert alert-success"><strong>Images:</strong> {len(r["imgs"])} image(s) stored</div>' 
                     if r['imgs'] else 
                     '<div class="alert alert-warning"><strong>Images:</strong> None available</div>'}
        
                    <p class="source-info" style="margin-top: 20px; font-size: 0.9em; color: #666;">
                        <em>Source: {r['src']}</em>
                    </p>
                </div>
                """
        
        # Summary for main view
        summ = f"""
                <div style="padding: 15px;">
                    <p>
                        <strong>Engine:</strong> {r['etxt']} {'<span style="color: red; font-style: italic;">*</span>' if gen else ''} 
                        | <strong>Body:</strong> {r['bstyle']}
                    </p>
        
                    <p style="margin: 10px 0;">
                        {r['desc'][:400]}{'...' if len(r['desc']) > 400 else ''}
                    </p>
        
                    <div class="alert alert-info" style="margin-top: 15px;">
                        <strong>Full Details:</strong> Click "Timeline" button to view complete survivor information.
                    </div>
                </div>
                """
        
        # Save main table
        V16_Cardetails.objects.update_or_create(carid=cid, defaults={
            'caryear': yr, 'carnum': eng, 'title': ttl, 'content': summ,
            'chapterid': chap, 'status': 'Survivor', 'jalbumlink': 'placeholder',
            'createdate': now, 'lastupdatedate': now, 'is_generated_engine_number': gen
        })
        
        # Save asset table
        V16_CardetailsAsset.objects.update_or_create(carid=cid, defaults={
            'folder_name': fld, 'caryear': yr, 'carnum': eng, 'content': detail,
            'model': r['bstyle'][:30] if r['bstyle'] else None,
            'jalbumlink': 'placeholder', 'disable_from_timeline': False
        })
        
        # clear and save images to avoid repeat images
        V16_Carimages.objects.filter(carid=cid).delete()
        for ip in r['imgs']:
            V16_Carimages.objects.create(
                carid=cid, imagenum=imgnum, caryear=yr, carnum=eng,
                carcategory='V16', imagepath=ip, description=f'From {r["src"]}',
                createdate=now, lastupdatedate=now
            )
            imgnum += 1
            cnt_imgs += 1
        cnt_cars += 1
    
    return cnt_cars, cnt_imgs

def proc_yr(grp, cfg):
    # Process one year group at a time
    print(f"\n{'='*60}\nProcessing: {grp} (Year {cfg['caryear']})\n{'='*60}")
    
    all_r = []
    for htm in cfg['html_files']:
        path = os.path.join(HTML_DIR, htm)
        print(f"  Parsing: {htm}")
        rs = parse_htm(path, cfg['range'])
        print(f"    Found {len(rs)} records")
        all_r.extend(rs)
    
    print(f"\n  Total records: {len(all_r)}")
    tot_img = sum(len(r['imgs']) for r in all_r)
    print(f"  Total images: {tot_img}")
    
    # assign engine numbers
    print(f"\n  Assigning missing engine numbers...")
    final = assign_engs(all_r, cfg)
    final.sort(key=lambda x: x['eng'])

    real = sum(1 for r in final if not r.get('gen', False))
    gen = sum(1 for r in final if r.get('gen', False))
    print(f"    Real engines: {real}")
    print(f"    Generated: {gen}")
    
    print(f"\n  Importing to database...")
    c, i = save_db(final, cfg)
    
    print(f"\n  {grp} Complete: {c} cars, {i} images (avg {i/c:.1f})")
    return c, i

def main():
    # Main execution
    print("\n" + "="*60 + "\nV16 import and extract all V16 old files\n" + "="*60)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # count total cars and images found
    tot_c = tot_i = 0
    for grp, cfg in YR_CFG.items():
        try:
            c, i = proc_yr(grp, cfg)
            tot_c += c
            tot_i += i
        except Exception as e:
            print(f"\n ERROR {grp}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "="*60 + "\nIMPORT COMPLETE\n" + "="*60)
    print(f"Total: {tot_c} cars, {tot_i} images (avg {tot_i/tot_c:.1f})")
    print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()