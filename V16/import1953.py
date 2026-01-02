#!/usr/bin/env python3
import os, sys, django, re, pytz
from bs4 import BeautifulSoup
from datetime import datetime

# Django setup
sys.path.append('/home/ncdbproj/CadillacDBProj')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CadillacDB.settings')
django.setup()
from EL_1953.models import EL_1953_Cardetails, EL_1953_CardetailsAsset, EL_1953_Carimages, EL_1953_Chapters

# Config
HTML_FILE = '/home/metacomp/NCDBContent/CDB/Dbas_txt/eld53srv.htm'
MIN_CAR = 1
MAX_CAR = 533
NO_INFO = """<p>It appears that there is no information available for this car at this time. However, information is still being migrated from the Old Cadillac Database registry, so an update may be imminent. We are also obtaining survivors' information updates from contributors and owners on an ongoing basis. We send regular update notifications via our main page ticker and our Facebook and Twitter feeds. We appreciate your interest and patience.</p>"""

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

def parse_htm(path):
    # Parse HTML and extract car data as dictionary
    print(f"  Parsing: {os.path.basename(path)}")
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    # Find The List marker
    start = None
    for elem in soup.find_all(text=True):
        txt = elem.strip()
        if 'those Swedes are a hardy race' in txt and 'Hej' in txt:
            par = elem.parent
            for sib in par.find_next_siblings():
                if 'The List' in sib.get_text().strip():
                    start = sib
                    break
            if start: break
    
    # search for List directly
    if not start:
        for elem in soup.find_all(['p', 'h1', 'h2', 'h3']):
            if 'The List' in elem.get_text().strip() and len(elem.get_text().strip()) < 30:
                start = elem
                break
    
    # Collect elements after marker
    collect = False
    elems = []
    for elem in soup.find_all(['p', 'table', 'div', 'span']):
        if elem == start:
            collect = True
            continue
        if collect: elems.append(elem)
    
    # Extract car data into dictionary
    cars = {}
    cur = None
    
    for elem in elems:
        txt = elem.get_text()
        # Look for Car #NNN 
        m = re.search(r'Car\s+#(\d+)', txt, re.IGNORECASE)
        
        if m:
            n = int(m.group(1))
            cur = n
            
            if n not in cars:
                cars[n] = {'desc': '', 'imgs': set()}
            
            # Add description
            clean = clean_txt(txt)
            if clean and len(clean) > 10 and clean not in cars[n]['desc']:
                cars[n]['desc'] = cars[n]['desc'] + ' ' + clean if cars[n]['desc'] else clean
            
            # Add images
            for img in elem.find_all('img'):
                src = img.get('src', '')
                if src and 'Dbas_eld' in src:
                    cars[n]['imgs'].add(src)
        
        elif cur is not None:
            # Continue adding to current car
            if elem.name == 'p':
                clean = clean_txt(txt)
                if clean and len(clean) > 10 and clean not in cars[cur]['desc']:
                    cars[cur]['desc'] += ' ' + clean
            
            for img in elem.find_all('img'):
                src = img.get('src', '')
                if src and 'Dbas_eld' in src:
                    cars[cur]['imgs'].add(src)
    
    # Convert sets to lists
    for n in cars:
        cars[n]['imgs'] = list(cars[n]['imgs'])
    
    tot_img = sum(len(cars[n]['imgs']) for n in cars)
    print(f"    Found {len(cars)} cars with data")
    print(f"    Found {tot_img} total images")
    
    return cars

def save_db(html_data):
    # Import all cars 1-533 to database
    chap = EL_1953_Chapters.objects.get(chapterid=59)
    tz = pytz.UTC
    now = tz.localize(datetime.now())
    
    # Get next image number
    maximg = EL_1953_Carimages.objects.latest('imagenum').imagenum if EL_1953_Carimages.objects.exists() else 0
    imgnum = maximg + 1
    
    cnt_data = cnt_empty = cnt_imgs = 0
    
    # Loop through all car numbers 1-533
    for n in range(MIN_CAR, MAX_CAR + 1):
        cid = f"1953-{n:03d}"
        ttl = f"#{n:03d}"
        
        # Check if HTML has data for this car
        if n in html_data:
            desc = html_data[n]['desc'][:800] if html_data[n]['desc'] else 'No description available'
            cont = f"<p><strong>Car #{n:03d}</strong></p><p>{desc}</p>"
            imgs = html_data[n]['imgs']
            stat = 'Survivor'
            cnt_data += 1
        else:
            cont = NO_INFO
            imgs = []
            stat = 'Unknown'
            cnt_empty += 1
        
        # Create folder name for timeline
        m = ((n - 1) % 12) + 1
        d = ((n - 1) % 28) + 1
        fld = f"1953.{m:02d}.{d:02d}"
        
        # Save main table
        EL_1953_Cardetails.objects.update_or_create(carid=cid, defaults={
            'caryear': 1953, 'carnum': n, 'title': ttl, 'content': cont,
            'chapterid': chap, 'status': stat, 'jalbumlink': 'placeholder',
            'createdate': now, 'lastupdatedate': now
        })
        
        # Save asset table
        EL_1953_CardetailsAsset.objects.update_or_create(carid=cid, defaults={
            'folder_name': fld, 'caryear': 1953, 'carnum': n, 'content': cont,
            'model': 'Eldorado', 'jalbumlink': 'placeholder', 'disable_from_timeline': False
        })
        
        # Clear and save images to avoid duplicates
        EL_1953_Carimages.objects.filter(carid=cid).delete()
        for ip in imgs:
            EL_1953_Carimages.objects.create(
                carid=cid, imagenum=imgnum, caryear=1953, carnum=n,
                carcategory='Eldorado', imagepath=ip, description='From eld53srv.htm',
                createdate=now, lastupdatedate=now
            )
            imgnum += 1
            cnt_imgs += 1
        
        # Progress output
        if n % 50 == 0:
            print(f"    [{n:3d}/{MAX_CAR}] Processed...")
        elif n in html_data and imgs:
            print(f"    [{n:3d}/{MAX_CAR}] Car #{n:03d} - {len(imgs)} images")
    
    return cnt_data, cnt_empty, cnt_imgs

def main():
    # Main execution
    print("\n" + "="*60 + "\n1953 ELDORADO - COMPLETE IMPORT (1-533)\n" + "="*60)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nParsing HTML file...")
    html_data = parse_htm(HTML_FILE)
    print(f"\nImporting all {MAX_CAR} cars to database...")
    cnt_data, cnt_empty, cnt_imgs = save_db(html_data)
    print("\n" + "="*60 + "\nIMPORT COMPLETE\n" + "="*60)
    print(f"Cars with data:    {cnt_data}")
    print(f"Cars without data: {cnt_empty}")
    print(f"Total cars:        {cnt_data + cnt_empty}")
    print(f"Total images:      {cnt_imgs}")
    print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()