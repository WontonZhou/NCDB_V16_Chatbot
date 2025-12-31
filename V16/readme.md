# V16 Survivors Registry 

Data migration and management system for NCDB V16 Survivors Registry (1930-1940). 
Migrates 824+ historical vehicle records from legacy HTML files to a Django web application with automated photo galleries and admin interfaces.

## File Structure

**`import_all.py`** - Master data import script. Parses HTML files, extracts vehicle data, assigns missing engine numbers, generates Bootstrap-styled content.

**`buildV16.py`** - JAlbum batch generator. Processes 400+ vehicles with 2000+ images, executes JAlbum Java application, updates database URLs.

**`models.py`** - Django data models for V16_Cardetails, V16_CardetailsAsset, V16_Carimages, V16_Chapters. Includes `is_generated_engine_number` field.

**`views.py`** - View controllers with search_by_engine(), cardisplay() for pagination, year consolidation, three-tier JAlbum fallback logic.

**`admin.py`** - Custom admin with color-coded badges, batch verification, filtered views, collapsible fieldsets.

**`car_template.html`** - Frontend template with Bootstrap 5 layout, form-based search, JAlbum iframe integration, merged year display.

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

## Known Issues (TA Feedback)

### Issues Identified by Joanna

**1. Configuration Path Management and .jap setting problem**
The .env file defines specific paths for Java and .jap configuration files, 
but the current code (buildV16.py) may not be using these paths consistently across different user accounts.
Also generated jalbums don't match production visual styles.

**2. Directory Structure**
The physical directory structure created by `buildV16.py` doesn't match JAlbum's expected hierarchy.
So there are missing backgrounds and broken links.

**3. Code Reuse and work flow integration**
TA suggests to call existing `make_timeline_album()` and `batch_generate_albums()` from `ContributionPublishing/views.py`
Also JAlbum generation is disconnected from contribution workflow,
 TA suggests to integrate with existing logic in ContributionPublishing/views.py for dynamic album management
