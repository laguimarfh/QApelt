# Register your models here.
from django.contrib import admin
from .models import CarData

@admin.register(CarData)
class CarDataAdmin(admin.ModelAdmin):
    list_display = ('body_no', 'date', 'latest', 'primer', 'colour_code')
