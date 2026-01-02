# V16 Survivors Registry 

Data migration and management system for NCDB V16 Survivors Registry (1930-1940). 
Migrates 824+ historical vehicle records from legacy HTML files to a Django web application with automated photo galleries and admin interfaces.

## File Structure

**`import_all.py`** - Master data import script for V16. Parses HTML files, extracts vehicle data, assigns missing engine numbers, generates Bootstrap-styled content.

**`import_1953.py`** - data import script for EL1953. Parses HTML files, extracts vehicle data, use dictionary to collect all cars information.

**`buildV16.py`** - JAlbum batch generator. Processes 800 V16 vehicles with 2000+ images, use /home/ncdbproj/CadillacDBProj/ContributionPublishing/views.py admin built in commands to generate jalbums, 
populate the 4 databases of ContributionPublishing, also generate nested albums as requested, use java and jap from the .env files directly.

**`build1953.py`** - Album batch generator. Processes 1953 vehicles with 203 images, use /home/ncdbproj/CadillacDBProj/ContributionPublishing/views.py admin built in commands to generate jalbums, 
populate the 4 databases of ContributionPublishing, also generate nested albums as requested, use java and jap from the .env files directly.

**`models.py`** - Django data models for V16_Cardetails, V16_CardetailsAsset, V16_Carimages, V16_Chapters. Includes `is_generated_engine_number` field.

**`views.py`** - View controllers with search_by_engine(), cardisplay() for pagination, year consolidation

**`admin.py`** - Custom admin with color-coded badges, batch verification, filtered views, collapsible fieldsets.

**`car_template.html`** - Frontend template with form-based search, merged year display.

### Activation
```bash
cd /home/ncdbproj/CadillacDBProj
source /home/metacomp/python_virtualenv/py3.11.4/bin/activate
```

**Import Data:**
```bash
python3 import_all.py 
```

**Generate Albums:**
```bash
python3 buildV16.py  
```

**Admin Access:**
```
http://184.168.29.112:8000/admin/
Default: Shows only unverified records
Add ?all=1 to view all records
```

**Frontend:**
```
http://184.168.29.112:8000/survivors-registry/Sixteens/year-1930/
Search by engine number (e.g., "700003" or "#700003")
```

