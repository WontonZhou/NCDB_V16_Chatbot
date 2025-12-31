# Admin UI for managing V16 survivor registries
# done by CLRCMRC 2025 team

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from V16.models import *


GENERATED_BADGE = mark_safe('<span style="color: red;">Generated</span>')
VERIFIED_BADGE = mark_safe('<span style="color: green;">Verified</span>')

# Admiin interface for V16Cardetails
# Define which fields appear in the list view
# Add filter sidebar on the right side of the list view
# Enable search functionality across selected fields
@admin.register(V16_Cardetails)
class V16CardetailsAdmin(admin.ModelAdmin):
    list_display = (
        'carid',
        'caryear',
        'carnum_display',
        'title',
        'status',
        'is_generated_display',
    )
    list_filter = ('caryear', 'is_generated_engine_number', 'status')
    search_fields = ('carid', 'carnum', 'title')
    list_per_page = 50
    readonly_fields = ('createdate', 'lastupdatedate')
    actions = ('mark_as_verified', 'mark_as_generated')
    
    # collapsible sections in individual editing
    fieldsets = (
        ('Basic', {
            'fields': ('carid', 'caryear', 'carnum', 'title', 'status')
        }),
        ('Engine Number', {
            'fields': ('is_generated_engine_number',),
            'description': 'Uncheck after manual verification.'
        }),
        ('Content', {
            'fields': ('content', 'chapterid'),
            'classes': ('collapse',)
        }),
        ('Meta', {
            'fields': ('jalbumlink', 'createdate', 'lastupdatedate'),
            'classes': ('collapse',)
        }),
    )
    
    # Auto-generated engine numbers are displayed in red with an asterisk (*)
    @admin.display(description='Engine Number', ordering='carnum')
    def carnum_display(self, obj):
        if not obj.is_generated_engine_number:
            return obj.carnum
        return format_html(
            # https://docs.djangoproject.com/en/6.0/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display
            '<span style="color: red; font-weight: 600;">{} *</span>',
            obj.carnum
        )

    @admin.display(description='Status', ordering='is_generated_engine_number')
    def is_generated_display(self, obj):
        return GENERATED_BADGE if obj.is_generated_engine_number else VERIFIED_BADGE
    
    # show only unverified records
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Default is generated only; add ?all=1 to url for all records
        return qs if 'all' in request.GET else qs.filter(is_generated_engine_number=True)
    
    # learned from the offical doc "Mark selected stories as published"
    # https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/
    @admin.action(description='Mark selected as verified')
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_generated_engine_number=False)
        self.message_user(request, f'{updated} record(s) marked as verified.')
    
    @admin.action(description='Mark selected as generated')
    def mark_as_generated(self, request, queryset):
        updated = queryset.update(is_generated_engine_number=True)
        self.message_user(request, f'{updated} record(s) marked as generated.')
        
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = (
            'V16 Survivors - All Records'
            if 'all' in request.GET
            else 'V16 Survivors - Generated Engine Numbers Only (?all=1 for all)'
        )
        return super().changelist_view(request, extra_context=extra_context)


# Admin interface for V16_CardetailsAsset model.
# This model stores detailed timeline content for survivor records.
@admin.register(V16_CardetailsAsset)
class V16CardetailsAssetAdmin(admin.ModelAdmin):
    list_display = (
        'carid',
        'folder_name',
        'caryear',
        'carnum',
        'model',
        'disable_from_timeline',
    )
    list_filter = ('caryear', 'disable_from_timeline')
    search_fields = ('carid', 'folder_name', 'model')
    list_per_page = 50

    fieldsets = (
        ('Identification', {
            'fields': ('carid', 'folder_name', 'caryear', 'carnum')
        }),
        ('Content', {
            'fields': ('content', 'model', 'jalbumlink')
        }),
        ('Display', {
            'fields': ('disable_from_timeline',)
        }),
    )

# Admin interface for V16_Carimages model
# Manages relationship between survivor records and their associated images
@admin.register(V16_Carimages)
class V16CarimagesAdmin(admin.ModelAdmin):
    list_display = (
        'imagenum',
        'carid',
        'caryear',
        'carnum',
        'imagepath_display',
        'createdate',
    )
    list_filter = ('caryear', 'carcategory')
    search_fields = ('carid', 'imagepath', 'description')
    list_per_page = 50
    readonly_fields = ('createdate', 'lastupdatedate')

    fieldsets = (
        ('Image', {
            'fields': ('imagenum', 'carid', 'caryear', 'carnum', 'carcategory')
        }),
        ('Details', {
            'fields': ('imagepath', 'description')
        }),
        ('Timestamps', {
            'fields': ('createdate', 'lastupdatedate'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Image Path')
    def imagepath_display(self, obj):
        path = obj.imagepath or ''
        return path if len(path) <= 50 else f'{path[:25]}...{path[-25:]}'


# Admin interface for V16_Chapters model
# chapter structure used for survivor records on the website
@admin.register(V16_Chapters)
class V16ChaptersAdmin(admin.ModelAdmin):
    list_display = ('chapterid', 'chaptername', 'superchapterid', 'description')
    list_filter = ('superchapterid',)
    search_fields = ('chaptername', 'description')
    list_per_page = 50

    fieldsets = (
        ('Chapter', {
            'fields': ('chapterid', 'chaptername', 'superchapterid')
        }),
        ('Content', {
            'fields': ('description', 'introduction', 'imagepath', 'url')
        }),
    )

# admin interface for update history
# legacy system for tracking updates to survivor records.
@admin.register(V16_Cardetailsupdate)
class V16CardetailsupdateAdmin(admin.ModelAdmin):
    list_display = ('carid', 'caryear', 'carnum', 'title', 'createdate')
    list_filter = ('caryear',)
    search_fields = ('carid', 'title', 'content')
    list_per_page = 50
    readonly_fields = ('createdate', 'lastupdatedate')

    fieldsets = (
        ('Update', {
            'fields': ('carid', 'caryear', 'carnum', 'title')
        }),
        ('Content', {
            'fields': ('content', 'jalbumlink')
        }),
        ('Timestamps', {
            'fields': ('createdate', 'lastupdatedate'),
            'classes': ('collapse',)
        }),
    )
