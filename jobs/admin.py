from django.contrib import admin
from django.utils.html import format_html

from .models import Company, EmailSubscription, Job, JobAlertDelivery, JobSyncRun


admin.site.site_header = 'MENA Tech Careers Control Center'
admin.site.site_title = 'MENA Tech Careers Admin'
admin.site.index_title = 'Operations overview'
admin.site.index_template = 'admin/index.html'


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    search_fields = ('name', 'location')
    list_display = ('name', 'location')
    list_per_page = 30
    ordering = ('name',)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'category', 'location', 'type_badge', 'source_badge', 'posted_at', 'open_listing')
    list_filter = ('category', 'job_type', 'source', 'posted_at')
    search_fields = ('title', 'company__name', 'location', 'description', 'requirement')
    autocomplete_fields = ('company',)
    date_hierarchy = 'posted_at'
    list_select_related = ('company',)
    list_per_page = 30
    ordering = ('-posted_at',)
    readonly_fields = ('open_listing',)

    @admin.display(description='Type', ordering='job_type')
    def type_badge(self, obj):
        return format_html('<span class="pc-badge pc-badge-neutral">{}</span>', obj.job_type)

    @admin.display(description='Source', ordering='source')
    def source_badge(self, obj):
        css = {
            'Wuzzuf': 'blue',
            'Mourjan': 'green',
            'Bayt': 'orange',
            'LinkedIn': 'blue',
        }.get(obj.source, 'neutral')
        return format_html('<span class="pc-badge pc-badge-{}">{}</span>', css, obj.source or 'Unknown')

    @admin.display(description='Listing')
    def open_listing(self, obj):
        if not obj or not obj.job_url:
            return '—'
        return format_html(
            '<a class="pc-external" href="{}" target="_blank" rel="noopener">Open ↗</a>',
            obj.job_url,
        )


@admin.register(EmailSubscription)
class EmailSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('email', 'location_preference', 'frequency', 'is_active', 'welcome_email_sent', 'last_alert_sent_at', 'created_at')
    list_filter = ('is_active', 'welcome_email_sent', 'location_preference', 'frequency')
    search_fields = ('email',)
    ordering = ('-created_at',)
    list_per_page = 30
    actions = ('activate_subscriptions', 'deactivate_subscriptions')
    readonly_fields = ('manage_token', 'last_alert_sent_at', 'last_email_error')

    @admin.action(description='Activate selected subscriptions')
    def activate_subscriptions(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Deactivate selected subscriptions')
    def deactivate_subscriptions(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(JobAlertDelivery)
class JobAlertDeliveryAdmin(admin.ModelAdmin):
    list_display = ('subscriber', 'job', 'sent_at')
    search_fields = ('subscriber__email', 'job__title')
    list_filter = ('sent_at', 'job__category', 'job__source')
    readonly_fields = ('subscriber', 'job', 'sent_at')
    date_hierarchy = 'sent_at'

    def has_add_permission(self, request):
        return False


@admin.register(JobSyncRun)
class JobSyncRunAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'status_badge', 'trigger', 'finished_at', 'jobs_removed')
    list_filter = ('status', 'trigger', 'started_at')
    search_fields = ('output', 'error')
    readonly_fields = ('status', 'trigger', 'started_at', 'finished_at', 'jobs_removed', 'output', 'error')
    date_hierarchy = 'started_at'
    ordering = ('-started_at',)

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        css = {
            'success': 'green', 'running': 'blue', 'failed': 'red', 'skipped': 'orange',
        }.get(obj.status, 'neutral')
        return format_html('<span class="pc-badge pc-badge-{}">{}</span>', css, obj.get_status_display())

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
