from django.contrib import admin
from .models import Shift, AttendanceStatus, Profile, OffDay

admin.site.register(Shift)
admin.site.register(AttendanceStatus)
admin.site.register(Profile)
admin.site.register(OffDay)