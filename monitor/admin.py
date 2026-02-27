from django.contrib import admin
from .models import SessionLog , FatigueLog, BurnoutRisk
# Register your models here.

admin.site.register(SessionLog)
admin.site.register(FatigueLog)
admin.site.register(BurnoutRisk)

# superadmin
# superadmin@cognitiveload.com
# superadmin123