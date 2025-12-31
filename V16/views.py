from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.template import RequestContext
from django.contrib.auth.models import Group
from django.db.models import Q
from django.contrib import messages
from .models import Post, V16_Cardetails, V16_CardetailsAsset, V16_Chapters, V16_Cardetailsupdate
from .forms import V16_RegistrationForm, V16_ContactForm, V16_ContributeForm
from QRCode.models import QRCode
from EB.views import qr_contact
from .models import V16_Carimages
import datetime

def survivors(requests):
    chapters = V16_Chapters.objects.filter(superchapterid = 4)
    chapterheading = V16_Chapters.objects.get(pk = 4)
    return render(requests, 'V16/chapter_template.html', {'chapters':chapters, 'chapterheading':chapterheading, 'user': requests.user});

def statistics(request):        
    chapterheading = V16_Chapters.objects.get(chapterid=61)
    return render(request, 'V16/statistics.html',{'chapterheading': chapterheading,'user': request.user});


# Calculates the correct page number based on an engine number input 
# and redirects the user to that specific car in the registry
def search_by_engine(request, year):
    engine_raw = (request.GET.get('engine') or '').strip()
    if engine_raw.startswith('#'):
        engine_raw = engine_raw[1:].strip()
    
    if not engine_raw.isdigit():
        messages.warning(request, "Please enter a valid engine number.")
        return redirect(f"/survivors-registry/Sixteens/year-{year}/")

    engine_num = int(engine_raw)
    query_year = year
    # Align years with historical V16 production series
    if year in ['1935', '1936', '1937']:
        query_year = '1934'
    elif year in ['1939', '1940']:
        query_year = '1938'

    # Filter queryset based on series logic
    if query_year in ['1930', '1931']:
        cars_list = V16_Cardetails.objects.filter(caryear__in=[1930, 1931]).order_by('carnum')
    elif query_year == '1934':
        cars_list = V16_Cardetails.objects.filter(caryear=1934).order_by('carnum')
    elif query_year == '1938':
        cars_list = V16_Cardetails.objects.filter(caryear=1938).order_by('carnum')
    else:
        cars_list = V16_Cardetails.objects.filter(caryear=query_year).order_by('carnum')

    try:
        target = cars_list.get(carnum=engine_num)
    except V16_Cardetails.DoesNotExist:
        messages.warning(request, f"Engine number {engine_num} was not found in year {year}.")
        return redirect(f"/survivors-registry/Sixteens/year-{year}/")
        
    # Determine page number by counting cars with smaller carnums
    page = cars_list.filter(carnum__lt=target.carnum).count() + 1
    return redirect(f"/survivors-registry/Sixteens/year-{year}/?page={page}")

def cardisplay(request,year):
    showbuttonboolean = False
    
    # Simplified permission check for superusers and group members
    if request.user.is_authenticated:
        if request.user.is_superuser:
            showbuttonboolean = True
        else:
            group_name = year + "_V16s"
            try:
                group = Group.objects.get(name=group_name)
                showbuttonboolean = group in request.user.groups.all()
            except Group.DoesNotExist:
                showbuttonboolean = False
    
    original_year = year
    if year in ['1935', '1936', '1937']:
        year = '1934'
    elif year in ['1939', '1940']:
        year = '1938'
    
    if year in ['1930', '1931']:
        cars_list = V16_Cardetails.objects.filter(caryear__in=[1930, 1931]).order_by('carnum')
    elif year == '1934':
        cars_list = V16_Cardetails.objects.filter(caryear=1934).order_by('carnum')
    elif year == '1938':
        cars_list = V16_Cardetails.objects.filter(caryear=1938).order_by('carnum')
    else:
        cars_list = V16_Cardetails.objects.filter(caryear=year).order_by('carnum')
        
    endindex = cars_list.count()
    chapterheading = V16_Chapters.objects.get(chaptername = 'V16 Survivors')
    paginator = Paginator(cars_list, 1)

    # QR Code handling logic
    try:
        qr_id = int(request.GET.get('qr_id', '0'))
        qr = QRCode.objects.get(qr_appl_id=qr_id)
        current_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if qr.status == False:
            exp_date = qr.expiration_date.strftime("%Y-%m-%d %H:%M:%S")
            if exp_date < current_time: return redirect(qr_contact)
        qr.hits += 1
        qr.save()
    except: qr_id = 0

    # Pagination logic
    try: page = int(request.GET.get('page', '1'))
    except: page = 1

    survivordirection = request.GET.get('survivor')
    if survivordirection in ["nk", "pk"]:
        pass 

    try:
        cars = paginator.page(page)
    except(EmptyPage, InvalidPage):
        cars = paginator.page(paginator.num_pages)
    
    # Navigation bar calculation
    if cars.number < 5:
        minpage = 1
        maxpage = (5 - cars.number) + 5 + cars.number
    elif cars.number > (endindex - 5):
        minpage = cars.number - ((5 - (endindex - cars.number)) + 5)
        maxpage = endindex
    else:
        minpage = cars.number - (4 if year in ['1930', '1931'] else 5)
        maxpage = cars.number + (4 if year in ['1930', '1931'] else 5)
    
    # Fetch image metadata for the specific car record
    car_images = []
    for car in cars.object_list:
        car_images = list(V16_Carimages.objects.filter(carid=car.carid))
        break
        
    jalbum_link = None
    # Path to the Coming Soon JAlbum 
    DEFAULT_CS_ALBUM = "/jalbum/jalbum_defaults/1930_V16/ComingSoon/album/index.html"

    for car in cars.object_list:
        # Check V16_CardetailsAsset for newly imported/updated albums
        asset = V16_CardetailsAsset.objects.filter(carid=car.carid).exclude(
            Q(jalbumlink='placeholder') | Q(jalbumlink='') | Q(jalbumlink__isnull=True)
        ).order_by('-folder_name').first()
    
        if asset:
            raw = asset.jalbumlink
            jalbum_link = raw if raw.startswith('/static/') else f"/static{raw}"
        # Check main V16_Cardetails table
        elif car.jalbumlink and car.jalbumlink not in ['placeholder', '', None]:
            jalbum_link = car.jalbumlink
        # Fallback to Coming Soon default page
        else:
            jalbum_link = f"/static{DEFAULT_CS_ALBUM}"
        break

    folders = [(car, [Post(p) for p in V16_CardetailsAsset.objects.filter(
                Q(carid=car.carid) & Q(disable_from_timeline=False)).order_by('-folder_name')])
               for car in cars]
    
    current_date = datetime.date.today()
    
    return render(request, 'V16/car_template.html', {
        'showbuttonboolean': showbuttonboolean,
        'cars' : cars,
        'folders': folders,
        'chapterheading': chapterheading,
        'endindex' : endindex,
        'minpage': minpage,
        'maxpage': maxpage,
        'current_date': current_date,
        'year': year,
        'car_images': car_images,
        'jalbum_link': jalbum_link,
        'user': request.user});
        
def carupdates(request, year , carnum):
    update_list = V16_Cardetailsupdate.objects.filter(carnum=carnum).filter(caryear=year)
    endindex = update_list.count()
    chapid = 'Year '+ str(year)
    chapterheading = V16_Chapters.objects.get(chaptername = chapid)

    paginator = Paginator(update_list, 1)

    try:
        page = int(request.GET.get('page', '1'))
    except:
        page = 1

    try:
        updates = paginator.page(page)
    except(EmptyPage, InvalidPage):
        updates = paginator.page(paginator.num_pages)
    
    if updates.number < 6:
        minpage = 1
        maxpage = (6 - updates.number) + 6 + updates.number
    elif updates.number > (endindex - 6):
        minpage = updates.number - ((6 - (endindex - updates.number)) + 6)
        maxpage = endindex
    else:
        minpage = updates.number - 6
        maxpage = updates.number + 6

    return render(request, 'V16/carupdate_template.html', { 'updates' : updates, 'chapterheading':chapterheading,'endindex' : endindex, 'minpage':minpage, 'maxpage':maxpage, 'user': request.user}, context_instance=RequestContext(request));
    
    
    
# -- several functions below are not being used at this time (may be used later)
# -- (see EB.views for current working version), and so commented out
# -- 

# # Create your views here.
# def register(request):
#     if request.method == 'POST':
#         form = V16_RegistrationForm(request.POST)
#         if form.is_valid():
#             user = User.objects.create_user(
#             username=form.cleaned_data['username'],
#             password=form.cleaned_data['password1'],
#             email=form.cleaned_data['email']
#             )
#             #login(request, user)
#             return redirect('/register/success/')
#     else:
#         form = V16_RegistrationForm()
#     variables = RequestContext(request, {'form': form})
#  
#     return render(request, 'V16/register.html',variables,)

# def success(request):
#     return render(request, 'V16/success.html',)

# def logout_page(request):
#     logout(request)
#     return redirect('/')
#     #return render('V16/homepage.html',context_instance=RequestContext(request))

# def contact(request):
#     if request.method == 'GET':
#         form = V16_ContactForm()
#     else:
#         form = V16_ContactForm(request.POST)
#         if form.is_valid():
#             contact_name = form.cleaned_data['contact_name']
#             from_email = form.cleaned_data['from_email']
#             content = form.cleaned_data['content']
#             try:
#                 mail = EmailMessage(contact_name,content,from_email, ['mrcadillac@newcadillacdatabase.org'])
#                 mail.send()
#             except BadHeaderError:
#                 return HttpResponse('Invalid header found.')
#             return redirect('thanks')
#     return render(request, "V16/contact.html", {'form': form})

# def contribute(request):
#     user = request.user
#     if user.is_active : 
#         if request.method == 'GET':
#             form = V16_ContributeForm()
#         else:
#             form = V16_ContributeForm(request.POST, request.FILES)
#             if form.is_valid():
#                 contact_name = form.cleaned_data['contact_name']
#                 from_email = form.cleaned_data['from_email']
#                 content = form.cleaned_data['content']
#                 imagefile = request.FILES['image']
#                 try:
#                     mail = EmailMessage("Someone Contributed an Image for Cadillac Database","Sender: "+contact_name+"\n"+"Message: "+content,from_email, ['mrcadillac@newcadillacdatabase.org'])
#                     mail.attach(imagefile.name, imagefile.read(), imagefile.content_type)
#                     mail.send()
#                     template = 'V16/thanks.html'
#                 except:
#                     return HttpResponse('Attachment Error')
# 
#                 return render(template, {'form':form},context_instance=RequestContext(request))
#         return render(request, "V16/contribute.html", {'form': form})
#     else:
#         return redirect('/login')


# def thanks(request):
#     return render('V16/thanks.html',)

# def sitemap(request):
#     return render('V16/sitemap.txt',)
    
# def home(request):
#     chapters = V16_Chapters.objects.filter(superchapterid = 1)
#     chapterheading = V16_Chapters.objects.get(pk = 1)
# 
#     return render(request, 'V16/homepage.html', {'chapters':chapters, 'chapterheading':chapterheading, 'user': request.user});

# def ebparts(requests):
#     chapters = V16_Chapters.objects.filter(superchapterid = 10).order_by('chaptername')
#     chapterheading = V16_Chapters.objects.get(pk = 10)
#     superchapheading = chapterheading.superchapterid.chaptername
#     return render(requests, 'V16/chap_no_image.html', {'chapters':chapters, 'chapterheading':chapterheading, 'user': requests.user});

# def ebyear(requests):
#     chapters = V16_Chapters.objects.filter(superchapterid = 46).order_by('chapterid')
#     chapterheading = V16_Chapters.objects.get(pk = 46)
#     return render(requests, 'V16/chapter_template.html', {'chapters':chapters, 'chapterheading':chapterheading, 'user': requests.user});
