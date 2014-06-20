import re

from django import forms
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models
from django.db.models.fields import BLANK_CHOICE_DASH
from django.template import RequestContext
from django.template.loader import render_to_string
from django.template.defaultfilters import slugify
from django.template.defaultfilters import filesizeformat
from django.utils.datastructures import SortedDict
from django.utils.functional import curry
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def split_emails(value):
    return re.split('[,;\s]+', value)


def create_form_submission(model_instance, form_instance, request, **kwargs):
    return FormSubmission.objects.create(
        form=model_instance,
        data=repr(form_instance.cleaned_data),
        path=request.path)


def remove_attachment_data(form_instance):
    """ Remove uploaded files from the form. """
    attachment_fields = [
        field for field in form_instance.fields if isinstance(
            form_instance.fields[field], forms.FileField
        )
    ]
    for field in attachment_fields:
        form_instance.fields.pop(field)
        form_instance.cleaned_data.pop(field)

    return form_instance


def send_as_mail(model_instance, form_instance, request, **kwargs):
    # Don't save user uploaded data in the DB, only attach it to the email
    form_instance = remove_attachment_data(form_instance)
    submission = create_form_submission(model_instance, form_instance, request, **kwargs)
    attachments = request.FILES.values()
    recipients = split_emails(model_instance.recipient)

    mail = EmailMessage(
        model_instance.title,
        submission.formatted_data(),
        settings.DEFAULT_FROM_EMAIL,
        recipients
    )

    for attachment in attachments:
        mail.attach(
            attachment.name,
            attachment.read(),
            attachment.content_type
        )

    mail.send(fail_silently=True)
    return _('Thank you, your input has been received.')


def validate_multiple_emails(value):
    for email in split_emails(value):
        try:
            validate_email(email)
        except ValidationError:
            msg = ugettext('"{0}" is not a valid email address.')
            raise ValidationError(msg.format(email))


class Form(models.Model):
    title = models.CharField(_('title'), max_length=100)
    recipient = models.TextField(_('Recipients'), default="",
                                 help_text=_("Comma separated list of recipients"),
                                 validators=[validate_multiple_emails])

    class Meta:
        verbose_name = _('form')
        verbose_name_plural = _('forms')

    def __unicode__(self):
        return self.title

    def form(self):
        fields = SortedDict((
            ('required_css_class', 'required'),
            ('error_css_class', 'error'),
        ))

        for field in self.fields.all():
            field.add_formfield(fields, self)

        return type('Form%s' % self.pk, (forms.Form,), fields)

    def process(self, form, request):
        return send_as_mail(
            model_instance=self,
            form_instance=form,
            request=request)


class FormAdminForm(forms.ModelForm):
    """ AdminForm to add validation for the number of attachment
    fields when creating the form. """
    class Meta:
        model = Form

    def clean(self):
        number_of_attachment_fields = len(
            [val for val in self.data.values() if val == 'attachment']
        )
        if number_of_attachment_fields > 3:
            raise forms.ValidationError(
                _('Maximum 3 attachment fields allowed.')
            )

        return self.cleaned_data


class RestrictedFileField(forms.FileField):
    """ FileField restricted to specified filetypes and file size. """

    def __init__(self, *args, **kwargs):
        # MIME types, keys only used for validation error message
        self.content_types = {
            'JPEG': 'image/jpeg',
            'GIF': 'image/gif',
            'TIFF': 'image/tiff',
            'PDF': 'application/pdf',
            'DOC': 'application/msword',
            'DOCX': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'XLS': 'application/vnd.ms-excel',
            'XLSX': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }

        # 1 MB = 1048576
        self.max_upload_size = 10485760

        super(RestrictedFileField, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        uploaded_file = super(RestrictedFileField, self).clean(*args, **kwargs)

        if uploaded_file:
            if uploaded_file.content_type in self.content_types.values():
                if uploaded_file._size > self.max_upload_size:
                    raise forms.ValidationError(
                        _('Maximum allowed filesize: %s. Current filesize: %s.') % (
                            filesizeformat(self.max_upload_size),
                            filesizeformat(uploaded_file._size)
                        )
                    )
            else:
                raise forms.ValidationError(
                    _('Filetype not supported.\n Supported filetypes: %s') % ', '.join(self.content_types.keys())
                )

        return uploaded_file


class FormField(models.Model):
    FIELD_TYPES = [
        ('text', _('text'), forms.CharField),
        ('email', _('e-mail address'), forms.EmailField),
        ('attachment', _('attachment'),
            curry(RestrictedFileField, required=False)),
        ('longtext', _('long text'),
            curry(forms.CharField, widget=forms.Textarea)),
        ('checkbox', _('checkbox'), curry(forms.BooleanField, required=False)),
        ('select', _('select'), curry(forms.ChoiceField, required=False)),
        ('radio', _('radio'),
            curry(forms.ChoiceField, widget=forms.RadioSelect)),
        ('multiple-select', _('multiple select'),
            curry(forms.MultipleChoiceField, widget=forms.CheckboxSelectMultiple)),
        ('hidden', _('hidden'), curry(forms.CharField, widget=forms.HiddenInput)),
    ]

    form = models.ForeignKey(Form, related_name='fields', verbose_name=_('form'))
    ordering = models.IntegerField(_('ordering'), default=0)

    title = models.CharField(_('title'), max_length=100)
    name = models.CharField(_('name'), max_length=100)
    type = models.CharField(
        _('type'), max_length=20, choices=[r[:2] for r in FIELD_TYPES])
    choices = models.CharField(
        _('choices'), max_length=1024, blank=True,
        help_text=_('Comma-separated'))
    help_text = models.CharField(
        _('help text'), max_length=1024, blank=True,
        help_text=_('Optional extra explanatory text beside the field'))
    default_value = models.CharField(
        _('default value'), max_length=255, blank=True,
        help_text=_('Optional default value of the field'))
    is_required = models.BooleanField(_('is required'), default=True)

    class Meta:
        ordering = ['ordering', 'id']
        unique_together = (('form', 'name'),)
        verbose_name = _('form field')
        verbose_name_plural = _('form fields')

    def __unicode__(self):
        return self.title

    def clean(self):
        if self.choices and not isinstance(self.get_type(), forms.ChoiceField):
            raise forms.ValidationError(
                _("You can't specify choices for %s fields") % self.type)

    def get_choices(self):
        get_tuple = lambda value: (slugify(value.strip()), value.strip())
        choices = [get_tuple(value) for value in self.choices.split(',')]
        if not self.is_required and self.type == 'select':
            choices = BLANK_CHOICE_DASH + choices
        return tuple(choices)

    def get_type(self, **kwargs):
        types = dict((r[0], r[2]) for r in self.FIELD_TYPES)
        return types[self.type](**kwargs)

    def add_formfield(self, fields, form):
        fields[self.name] = self.formfield()

    def formfield(self):
        kwargs = dict(label=self.title, required=self.is_required, initial=self.default_value)
        if self.choices:
            kwargs['choices'] = self.get_choices()
        if self.help_text:
            kwargs['help_text'] = self.help_text
        return self.get_type(**kwargs)


class FormSubmission(models.Model):
    submitted = models.DateTimeField(auto_now_add=True)
    form = models.ForeignKey(
        Form, verbose_name=_('form'), related_name='submissions')
    data = models.TextField()
    path = models.CharField(max_length=255)

    class Meta:
        ordering = ('-submitted',)

    def sorted_data(self, include=()):
        """ Return SortedDict by field ordering and using titles as keys.

        `include` can be a tuple containing any or all of 'date', 'time',
        'datetime', or 'path' to include additional meta data.
        """
        data_dict = eval(self.data)
        data = SortedDict()
        field_names = []
        for field in self.form.fields.all():
            data[field.title] = data_dict.get(field.name)
            field_names.append(field.name)
        # append any extra data (form may have changed since submission, etc)
        for field_name in data_dict:
            if not field_name in field_names:
                data[field_name] = data_dict[field_name]
        if 'datetime' in include:
            data['submitted'] = self.submitted
        if 'date' in include:
            data['date submitted'] = self.submitted.date()
        if 'time' in include:
            data['time submitted'] = self.submitted.time()
        if 'path' in include:
            data['form path'] = self.path
        return data

    def formatted_data(self, html=False):
        formatted = ""
        for key, value in self.sorted_data().items():
            if html:
                formatted += "<dt>%s</dt><dd>%s</dd>\n" % (key, value)
            else:
                formatted += "%s: %s\n" % (key, value)
        return formatted if not html else "<dl>%s</dl>" % formatted

    def formatted_data_html(self):
        return self.formatted_data(html=True)


class FormContent(models.Model):
    form = models.ForeignKey(Form, verbose_name=_('form'),
                             related_name='%(app_label)s_%(class)s_related')
    show_form_title = models.BooleanField(_('show form title'), default=True)
    success_message = models.TextField(
        _('success message'), help_text=
        _("Custom message to display after valid form is submitted"))

    template = 'content/form/form.html'

    class Meta:
        abstract = True
        verbose_name = _('form')
        verbose_name_plural = _('forms')


    def process_valid_form(self, request, form_instance, **kwargs):
        """ Process form and return response (hook method). """
        process_result = self.form.process(form_instance, request)
        context = RequestContext(
            request, {
                'content': self,
                'message': self.success_message or process_result or u''})
        return render_to_string(self.template, context)

    def render(self, request, **kwargs):
        form_class = self.form.form()
        prefix = 'fc%d' % self.id
        formcontent = request.POST.get('_formcontent')

        if request.method == 'POST' and (not formcontent or formcontent == unicode(self.id)):
            form_class.base_fields['customer_id'] = forms.CharField()
            form_instance = form_class(request.POST, request.FILES, prefix=prefix)

            if form_instance.is_valid():
                return self.process_valid_form(request, form_instance, **kwargs)
        else:
            form_instance = form_class(prefix=prefix)

        context = RequestContext(
            request, {'content': self, 'form': form_instance})
        return render_to_string(self.template, context)
