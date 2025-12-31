#!/usr/bin/env python3
# This is a script to use built in commands to generate jalbums for V16 survivor registry
import os, sys, django, shutil, pytz
from datetime import datetime

sys.path.append('/home/ncdbproj/CadillacDBProj')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CadillacDB.settings')
django.setup()

from V16.models import V16_Cardetails, V16_Carimages, V16_CardetailsAsset
from django.conf import settings

# Configurations
V2_CFG = '/home/ncdbproj/NCDBContent/jalbum-settings-v2.jap'
JALBUM = '/usr/local/jAlbum_v31/JAlbum.jar'
JAVA = '/usr/lib/jalbum/jre64/bin/java'
OUT_ROOT = getattr(settings, 'JALBUM_STORE_ROOT', '/home/ncdbproj/NCDBContent/jalbum')
IMG_SRC = '/home/metacomp/NCDBContent/CDB'

print("="*80 + "\nV16 building jalbums start here ... \n" + "="*80)
print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "="*80)

# Get all cars with images
all_cars = V16_Cardetails.objects.filter(caryear__in=[1930, 1932, 1933, 1934, 1938]).order_by('caryear', 'carnum')
cars_w_imgs = []
# add car images as tuple to the list, [(car1, [img1, img2]), (car2, [img3]), ...]
for c in all_cars:
    imgs = V16_Carimages.objects.filter(carid=c.carid)
    if imgs.exists():
        cars_w_imgs.append((c, list(imgs)))

# start counting total cars and images
tot_c = len(cars_w_imgs)
tot_i = sum(len(i) for _, i in cars_w_imgs)

print(f"\nFound {tot_c} cars with {tot_i} images")
print(f"Starting batch generation soon\n" + "="*80)

# start couting success and failed ones
ok = fail = 0
fails = []

for idx, (car, imgs) in enumerate(cars_w_imgs, 1):
    print(f"\n[{idx}/{tot_c}] Car {car.carid} (#{car.carnum}) - {len(imgs)} images")
    
    try:
        # Build paths
        yr_dir = f"{car.caryear}_V16"
        car_dir = f"{str(car.caryear)[2:]}V16{car.carnum}"
        tl_dir = f"timeline_albums/{car.carnum}"
        dt = datetime.now().strftime('%b.%d.%Y')
        alb_dir = f"{car.carnum}-{dt}"
        # for example /home/ncdbproj/NCDBContent/jalbum/1930_V16/30V16700003/timeline_albums/700003/700003-Dec.30.2025
        jpath = os.path.join(OUT_ROOT, yr_dir, car_dir, tl_dir, alb_dir)
        
        # Clean old
        if os.path.exists(jpath):
            shutil.rmtree(jpath)
        os.makedirs(jpath, exist_ok=True)
        
        # Copy images
        copied = 0
        for img in imgs:
            clean = img.imagepath.replace('../', '')
            src = os.path.join(IMG_SRC, clean)
            if os.path.exists(src):
                dst = os.path.join(jpath, os.path.basename(src))
                shutil.copy2(src, dst)
                copied += 1
            else:
                print(f"  images not found {src}")
        
        if copied == 0:
            print(f"  No images copied")
            fail += 1
            fails.append((car.carid, "No images"))
            continue
        
        print(f"  Copied {copied} images")
        
        # Generate JAlbum, give java 4GB ram
        cmd = f'{JAVA} -Xmx4000M -jar {JALBUM} -directory {jpath} -sameDirectory -projectFile {V2_CFG}'
        ret = os.system(f'{cmd} > /dev/null 2>&1')
        
        # if return is not zero then failed
        if ret != 0:
            print(f"  Building JAlbum failed ({ret})")
            fail += 1
            fails.append((car.carid, f"JAlbum {ret}"))
            continue
        
        # Verify output
        idx_html = os.path.join(jpath, 'album', 'index.html')
        if not os.path.exists(idx_html):
            print(f"  ERROR: index.html missing")
            fail += 1
            fails.append((car.carid, "No index.html"))
            continue
        
        # Update database
        # Construct jalbum url
        url = f"/jalbum/{yr_dir}/{car_dir}/{tl_dir}/{alb_dir}/album/index.html"
        asset = V16_CardetailsAsset.objects.filter(carid=car.carid).first()
        if asset:
            asset.jalbumlink = url
            asset.save()
        else:
        # if assest not exist then create one
            tz = pytz.UTC
            now = tz.localize(datetime.now())
            V16_CardetailsAsset.objects.create(
                carid=car.carid, folder_name=alb_dir,
                caryear=car.caryear, carnum=car.carnum,
                jalbumlink=url, disable_from_timeline=False
            )
        
        print(f"  SUCCESS")
        ok += 1
        
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        fail += 1
        fails.append((car.carid, str(e)))
        
# logging
print("\n" + "="*80 + "\nCOMPLETE\n" + "="*80)
print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\nResults: {tot_c} total, {ok} success, {fail} failed")

if fails:
    print(f"\nFailed cars:")
    for cid, rsn in fails:
        print(f"  {cid}: {rsn}")

print(f"\nAlbums at: {OUT_ROOT}")
print("="*80)