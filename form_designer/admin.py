from django.contrib import admin
from django.utils.text import truncate_words

from . import models


class FormFieldAdmin(admin.TabularInline):
    extra = 0
    model = models.FormField
    prepopulated_fields = {'name': ('title',)}


class FormAdmin(admin.ModelAdmin):
    form = models.FormAdminForm
    inlines = [FormFieldAdmin]
    list_display = ('title',)


class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('form', 'path', 'submitted', 'data_summary')
    list_filter = ('form',)
    fields = ('form', 'path', 'submitted')
    readonly_fields = fields

    def data_summary(self, submission):
        return truncate_words(submission.formatted_data(), 15)

    def has_add_permission(self, request):
        return False


admin.site.register(models.Form, FormAdmin)
admin.site.register(models.FormSubmission, FormSubmissionAdmin)
