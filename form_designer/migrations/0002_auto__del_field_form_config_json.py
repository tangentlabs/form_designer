# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Form.config_json'
        db.delete_column('form_designer_form', 'config_json')


    def backwards(self, orm):
        # Adding field 'Form.config_json'
        db.add_column('form_designer_form', 'config_json',
                      self.gf('django.db.models.fields.TextField')(default='', blank=True),
                      keep_default=False)


    models = {
        'form_designer.form': {
            'Meta': {'object_name': 'Form'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'form_designer.formfield': {
            'Meta': {'ordering': "['ordering', 'id']", 'unique_together': "(('form', 'name'),)", 'object_name': 'FormField'},
            'choices': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'default_value': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'form': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'fields'", 'to': "orm['form_designer.Form']"}),
            'help_text': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_required': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'ordering': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '20'})
        },
        'form_designer.formsubmission': {
            'Meta': {'ordering': "('-submitted',)", 'object_name': 'FormSubmission'},
            'data': ('django.db.models.fields.TextField', [], {}),
            'form': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'submissions'", 'to': "orm['form_designer.Form']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'submitted': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['form_designer']
