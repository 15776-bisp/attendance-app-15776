from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("offday/approve/<int:offday_id>/", views.approve_offday, name="approve_offday"),
    path("offday/reject/<int:offday_id>/", views.reject_offday, name="reject_offday"),
    path("notification/read/<int:notification_id>/", views.mark_notification_read, name="mark_notification_read"),
    path("request-day-off/<str:off_date>/", views.request_day_off, name="request_day_off"),
    path("edit-attendance/<int:record_id>/", views.edit_attendance, name="edit_attendance"),
    path("delete-attendance/<int:record_id>/", views.delete_attendance, name="delete_attendance"),
    path("attendance-list/", views.attendance_list, name="attendance_list"),
    path("edit-shift/<int:shift_id>/", views.edit_shift, name="edit_shift"),
    path("delete-shift/<int:shift_id>/", views.delete_shift, name="delete_shift"),
    path("shift-list/", views.shift_list, name="shift_list"),
    path("create-shift/", views.create_shift, name="create_shift"),
    path("attendance-history/", views.attendance_history, name="attendance_history"),
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="attendance/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("my-shifts/", views.my_shifts, name="my_shifts"),
    path("manager-dashboard/", views.manager_dashboard, name="manager_dashboard"),
]

