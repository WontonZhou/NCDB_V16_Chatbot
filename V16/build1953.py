#!/usr/bin/env python3
import os, sys, django, shutil
from pathlib import Path
from datetime import datetime
import pytz
from django.db import connections

# Django setup
sys.path.append('/home/ncdbproj/CadillacDBProj')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CadillacDB.settings')
django.setup()

import ContributionPublishing.views as cp_views
from EL_1953.models import EL_1953_Cardetails, EL_1953_CardetailsAsset, EL_1953_Carimages
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
    with connections['EL_1953'].cursor() as cur:
        cur.execute("SELECT Content FROM EL_1953_CarDetails_BACKUP_20260102 WHERE id = %s", [cid])
        row = cur.fetchone()
        return row[0] if row and row[0] else None

def build_all():
    # Build JAlbum galleries for all 1953 Eldorado cars
    print("\n" + "="*60 + "\n1953 ELDORADO - JALBUM BUILD\n" + "="*60)
    
    # Get admin user
    db = ContributionApplContent.objects.db
    adm = User.objects.using(db).filter(is_superuser=True).first()
    if not adm:
        print("ERROR: No admin user")
        sys.exit(1)
    
    tz = pytz.UTC
    now = tz.localize(datetime.now())
    pth = '1953_Eldorado'
    
    # Get all cars
    cars = EL_1953_Cardetails.objects.all().order_by('carnum')
    # cars = EL_1953_Cardetails.objects.all().order_by('carnum')[:3]
    tot = len(cars)
    print(f"Queue: {tot} cars")
    print(f"Start: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    cnt_img = cnt_nia = cnt_err = 0
    
    for i, car in enumerate(cars, 1):
        print(f"[{i:3d}/{tot}] {car.carid}", end=' ', flush=True)
        
        try:
            # Get original content
            raw = get_raw(car.carid) or car.content
            
            # Clear existing records
            ContributionImageFile.objects.filter(carid=car.carid).delete()
            ContributionComment.objects.filter(carid=car.carid).delete()
            ContributionApplContent.objects.filter(carid=car.carid).delete()
            EL_1953_CardetailsAsset.objects.filter(carid=car.carid).delete()
            
            # Update main record
            car.content = raw
            car.save()
            
            # Create coming_soon template 
            EL_1953_CardetailsAsset.objects.create(
                carid=car.carid, folder_name='coming_soon',
                caryear=1953, carnum=car.carnum, content=raw,
                jalbumlink=f'/static/jalbum_defaults/{pth}/CX_CS/index.html',
                disable_from_timeline=True
            )
            
            # Check for images
            imgs = EL_1953_Carimages.objects.filter(carid=car.carid)
            
            if not imgs.exists():
                # No images then set NIA placeholder
                # NIA for summary, CS for timeline
                EL_1953_CardetailsAsset.objects.filter(
                    carid=car.carid, folder_name='coming_soon'
                ).update(disable_from_timeline=False)
                
                car.jalbumlink = f"/static/jalbum_defaults/{pth}/CX_NIA/album/index.html"
                car.save()
                
                print("NIA")
                cnt_nia += 1
                
            else:
                # Has images then build JAlbum
                fts = now.strftime('%Y.%m.%d.%H.%M.%S')
                
                # Create contribution records
                # We emulate a full user contribution by populating the four core tables
                # 1. CarDetail, 2. ApplContent, 3. ContributionComment, 4. ImageFile
                det, _ = CarDetail.objects.get_or_create(
                    carid=car.carid,
                    defaults={'caryear': 1953, 'carnum': car.carnum, 'cartype': 'Eldorado'}
                )
                
                apl = ContributionApplContent.objects.create(
                    carid=car.carid, foldername=fts,
                    ownername='Database Migration', username=adm.username, user_id=adm.id,
                    cardetailid=det, pendingapproval=False, submitteddate=now
                )
                
                ContributionComment.objects.create(
                    carid=car.carid, content=raw, foldername=fts,
                    postid=apl, approved=True
                )
                
                # Copy images to storage
                sub = f"53EL{car.carnum:03d}"
                sto = Path(settings.IMAGE_STORE_ROOT) / pth / sub / fts
                sto.mkdir(parents=True, exist_ok=True)
                
                db_imgs = []
                for img in imgs:
                    src = f'/home/metacomp/NCDBContent/CDB/{img.imagepath.replace("../", "")}'
                    if os.path.exists(src):
                        fn = os.path.basename(src)
                        shutil.copy2(src, sto / fn)
                        
                        obj = ContributionImageFile.objects.create(
                            carid=car.carid, postid=apl, foldername=fts,
                            imageurl=f'{pth}/{sub}/{fts}/{fn}',
                            approved=True, filetype=fn.split('.')[-1]
                        )
                        db_imgs.append(obj)
                
                # Build JAlbum with suppressed output
                if db_imgs:
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
                    
                    # Cleanup
                    EL_1953_CardetailsAsset.objects.filter(
                        carid=car.carid, folder_name='coming_soon'
                    ).delete()
                    
                    EL_1953_CardetailsAsset.objects.filter(
                        carid=car.carid
                    ).update(disable_from_timeline=False)
                    
                    # Update jalbumlink
                    ast = EL_1953_CardetailsAsset.objects.filter(carid=car.carid).first()
                    if ast and ast.jalbumlink:
                        import re
                        summary_link = ast.jalbumlink.replace('timeline_albums', 'summary_albums')
                        summary_link = re.sub(r'/(\d+)/[^/]+/album/', r'/\1/album/', summary_link)
                        car.jalbumlink = summary_link
                        car.save()
                    
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