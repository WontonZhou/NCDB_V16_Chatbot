#!/usr/bin/env python3
import os, sys, django, shutil, re
from pathlib import Path
from datetime import datetime
import pytz
from django.db import connections

# Django setup
sys.path.append('/home/ncdbproj/CadillacDBProj')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CadillacDB.settings')
django.setup()

import ContributionPublishing.views as cp_views
from V16.models import V16_Cardetails, V16_CardetailsAsset, V16_Carimages
from ContributionPublishing.models import CarDetail, ContributionApplContent, ContributionComment, ContributionImageFile
from django.contrib.auth.models import User
from django.conf import settings

# Suppress verbose output
import logging
logging.getLogger('ContributionPublishing').setLevel(logging.ERROR)
# Bypass the Social Media API it kept crashing
cp_views.auto_post_to_socialmedia = lambda *args, **kwargs: None

def get_raw(cid):
    # Fetch original content from backup table
    with connections['V16'].cursor() as cur:
        cur.execute("SELECT Content FROM V16_CarDetails_BACKUP_20251231 WHERE id = %s", [cid])
        row = cur.fetchone()
        return row[0] if row and row[0] else None

def clean_txt(raw):
    # Sanitize HTML to make sure string slicing logic in
    # publish_contribution function does not break HTML tags.
    # Remove timestamps and wrapper divs from content
    if not raw:
        return '<p>V16 Survivor information.</p>'
    
    txt = re.sub(r'\[(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.\d{2}\.\d{4}\]', '', raw)
    txt = txt.replace('v style="padding: 15px;">', '')
    txt = re.sub(r'<div[^>]*>', '', txt).replace('</div>', '')
    
    # Extract paragraphs
    pars = re.findall(r'<p[^>]*>(.*?)</p>', txt, re.DOTALL)
    if pars:
        clean = ' '.join(p.strip() for p in pars if p.strip())
    else:
        clean = re.sub(r'<[^>]+>', '', txt)
        clean = re.sub(r'\s+', ' ', clean).strip()
    
    return f'<p>{clean}</p>' if clean else '<p>V16 Survivor information.</p>'

def build_all():
    # Build JAlbum galleries for all V16 cars
    print("\n" + "="*60 + "\nV16 SURVIVORS - JALBUM BUILD\n" + "="*60)
    
    # Get admin user
    db = ContributionApplContent.objects.db
    adm = User.objects.using(db).filter(is_superuser=True).first()
    if not adm:
        print("ERROR: No admin user")
        sys.exit(1)
    
    tz = pytz.UTC
    now = tz.localize(datetime.now())
    
    # Get all V16 cars
    cars = V16_Cardetails.objects.filter(caryear__in=[1930, 1932, 1933, 1934, 1938]).order_by('caryear', 'carnum')
    
    tot = len(cars)
    print(f"Queue: {tot} cars")
    print(f"Start: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    cnt_img = cnt_nia = cnt_err = 0
    
    for i, car in enumerate(cars, 1):
        yr_dir = f"{car.caryear}_V16"
        print(f"[{i:3d}/{tot}] {car.carid}", end=' ', flush=True)
        
        try:
            # Get clean content
            raw = get_raw(car.carid) or car.content
            clean = clean_txt(raw)
            
            # Clear existing records
            ContributionImageFile.objects.filter(carid=car.carid).delete()
            ContributionComment.objects.filter(carid=car.carid).delete()
            ContributionApplContent.objects.filter(carid=car.carid).delete()
            V16_CardetailsAsset.objects.filter(carid=car.carid).delete()
            
            # Update main record
            car.content = clean
            car.save()
            
            # Check for existing image files
            imgs = V16_Carimages.objects.filter(carid=car.carid)
            real_imgs = []
            for img in imgs:
                src = f'/home/metacomp/NCDBContent/CDB/{img.imagepath.replace("../", "")}'
                if os.path.exists(src):
                    real_imgs.append(img)
            
            # Create coming_soon template 
            V16_CardetailsAsset.objects.create(
                carid=car.carid, folder_name='coming_soon',
                caryear=car.caryear, carnum=car.carnum, content=clean,
                jalbumlink=f'/static/jalbum_defaults/{yr_dir}/CX_CS/index.html',
                disable_from_timeline=True
            )
            
            if not real_imgs:
                # No images set NIA placeholder
                # NIA for summary, CS for timeline
                car.jalbumlink = f"/static/jalbum_defaults/{yr_dir}/CX_NIA/album/index.html"
                car.save()
                
                V16_CardetailsAsset.objects.filter(
                    carid=car.carid, folder_name='coming_soon'
                ).update(disable_from_timeline=False)
                
                print("NIA")
                cnt_nia += 1
                
            else:
                # Has images then build JAlbum
                fts = tz.localize(datetime.now()).strftime('%Y.%m.%d.%H.%M.%S')
                # Create contribution records
                # We emulate a full user contribution by populating the four core tables
                # 1. CarDetail, 2. ApplContent, 3. ContributionComment, 4. ImageFile
                det, _ = CarDetail.objects.get_or_create(
                    carid=car.carid,
                    defaults={'caryear': car.caryear, 'carnum': car.carnum, 'cartype': 'V16'}
                )
                
                apl = ContributionApplContent.objects.create(
                    carid=car.carid, foldername=fts,
                    ownername='V16 Migration', username=adm.username, user_id=adm.id,
                    cardetailid=det, pendingapproval=False, submitteddate=tz.localize(datetime.now())
                )
                
                ContributionComment.objects.create(
                    carid=car.carid, content=clean, foldername=fts,
                    postid=apl, approved=True
                )
                
                # Copy images to storage
                sub = f'{str(car.caryear)[2:]}V16{car.carnum}'
                sto = Path(settings.IMAGE_STORE_ROOT) / yr_dir / sub / fts
                sto.mkdir(parents=True, exist_ok=True)
                
                db_imgs = []
                for img in real_imgs:
                    src = f'/home/metacomp/NCDBContent/CDB/{img.imagepath.replace("../", "")}'
                    fn = os.path.basename(src)
                    shutil.copy2(src, sto / fn)
                    
                    obj = ContributionImageFile.objects.create(
                        carid=car.carid, postid=apl, foldername=fts,
                        imageurl=f'{yr_dir}/{sub}/{fts}/{fn}',
                        approved=True, filetype=fn.split('.')[-1]
                    )
                    db_imgs.append(obj)
                
                # Build JAlbum with suppressed output
                old_out, old_err = sys.stdout, sys.stderr
                sys.stdout = sys.stderr = open(os.devnull, 'w')
                # we use code directly from contributionpublisher/views.py
                try:
                    # Execute make_timeline_album to build the dated subdirectory
                    cp_views.make_timeline_album(apl, det, db_imgs)
                    # Execute publish_contribution to build the Summary album and link the DB assets.
                    cp_views.publish_contribution(apl.id)
                finally:
                    sys.stdout, sys.stderr = old_out, old_err
                
                V16_CardetailsAsset.objects.filter(
                    carid=car.carid, folder_name='coming_soon'
                ).update(disable_from_timeline=True)
                
                V16_CardetailsAsset.objects.filter(
                    carid=car.carid
                ).exclude(folder_name='coming_soon').update(disable_from_timeline=False)
                
                print(f"Built ({len(db_imgs)})")
                cnt_img += 1
                
        except Exception as e:
            print(f"ERROR: {str(e)[:50]}")
            cnt_err += 1
    
    # Summary
    end = tz.localize(datetime.now())
    dur = (end - now).total_seconds()
    
    print("\n" + "="*60 + "\nBUILD COMPLETE\n" + "="*60)
    print(f"Total:        {tot}")
    print(f"With images:  {cnt_img}")
    print(f"No images:    {cnt_nia}")
    print(f"Errors:       {cnt_err}")
    print(f"Duration:     {dur/60:.1f} min")
    print("="*60 + "\n")

if __name__ == '__main__':
    build_all()