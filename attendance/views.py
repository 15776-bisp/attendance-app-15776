from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib.auth.models import Group, User
from django.contrib import messages
from datetime import date, timedelta, datetime
from django.utils import timezone

from .models import Shift, AttendanceStatus, OffDay, Notification



def is_manager(user):
    return user.is_authenticated and user.groups.filter(name="Manager").exists()

@login_required
def home(request):
    profile = None
    if hasattr(request.user, "profile"):
        profile = request.user.profile

    return render(request, "attendance/home.html", {
        "is_manager_user": is_manager(request.user),
        "profile": profile,
    })

@login_required
def my_shifts(request):
    user_groups = request.user.groups.exclude(name="Manager")

    shifts = Shift.objects.filter(
        department__in=user_groups
    ).order_by("date", "shift_type")

    approved_off_days = list(
        OffDay.objects.filter(
            user=request.user,
            status="approved"
        ).values_list("date", flat=True)
    )

    my_offday_requests = {
        off.date: off.status
        for off in OffDay.objects.filter(user=request.user)
    }

    department_offdays = OffDay.objects.filter(
        user__groups__in=user_groups,
        status="approved"
    ).exclude(user=request.user).select_related("user").distinct()

    department_taken_days = {}

    for off in department_offdays:
        if off.date not in department_taken_days:
            department_taken_days[off.date] = []
        department_taken_days[off.date].append(off.user.username)

    if request.method == "POST":
        shift_id = request.POST.get("shift_id")
        status = request.POST.get("status")
        reason_text = request.POST.get("reason_text", "").strip()

        shift = Shift.objects.get(id=shift_id)

        if shift.department not in user_groups:
            return HttpResponseForbidden("You are not allowed to update this shift.")

        if shift.date != date.today():
            messages.error(request, "You can only update attendance for today's shift.")
            return redirect("my_shifts")

        if shift.date in approved_off_days:
            messages.error(request, "This is your approved day off. Attendance is not required.")
            return redirect("my_shifts")

        if status in ["absent", "late"] and not reason_text:
            messages.error(request, "Reason is required for absent or late status.")
            return redirect("my_shifts")

        if status == "present":
            reason_text = ""

        AttendanceStatus.objects.update_or_create(
            user=request.user,
            shift=shift,
            defaults={
                "status": status,
                "reason_text": reason_text
            }
        )

        if status in ["absent", "late"]:
            Notification.objects.update_or_create(
                user=request.user,
                shift=shift,
                notification_type=status,
                defaults={
                    "message": f"{request.user.username} marked {status} for {shift.date} ({shift.shift_type}).",
                    "is_read": False,
                }
            )
            Notification.objects.filter(
                user=request.user,
                shift=shift
            ).exclude(notification_type=status).update(is_read=True)

        if status == "present":
            Notification.objects.filter(
                user=request.user,
                shift=shift
            ).update(is_read=True)

        messages.success(request, "Attendance submitted successfully.")
        return redirect("my_shifts")

    attendance_map = {}
    existing_records = AttendanceStatus.objects.filter(
        user=request.user,
        shift__in=shifts
    )

    for record in existing_records:
        attendance_map[record.shift.id] = record

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]

    return render(request, "attendance/my_shifts.html", {
        "shifts": shifts,
        "attendance_map": attendance_map,
        "today": today,
        "is_manager_user": is_manager(request.user),
        "profile": request.user.profile if hasattr(request.user, "profile") else None,
        "week_days": week_days,
        "off_days": approved_off_days,
        "my_offday_requests": my_offday_requests,
        "department_taken_days": department_taken_days,
    })

@login_required
def request_day_off(request, off_date):
    selected_date = date.fromisoformat(off_date)
    today = date.today()

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    user_groups = request.user.groups.exclude(name="Manager")

    if selected_date < start_of_week or selected_date > end_of_week:
        messages.error(request, "You can only request a day off for the current week.")
        return redirect("my_shifts")

    if selected_date < today:
        messages.error(request, "You cannot request a past date as day off.")
        return redirect("my_shifts")

    existing_off_day_for_user = OffDay.objects.filter(
        user=request.user,
        date__gte=start_of_week,
        date__lte=end_of_week
    ).exclude(status="rejected").exists()

    if existing_off_day_for_user:
        messages.error(request, "You already have a day-off request for this week.")
        return redirect("my_shifts")

    same_department_approved = OffDay.objects.filter(
        user__groups__in=user_groups,
        date=selected_date,
        status="approved"
    ).exclude(user=request.user).exists()

    if same_department_approved:
        messages.error(request, "This date is already approved for someone in your department.")
        return redirect("my_shifts")

    offday, created = OffDay.objects.get_or_create(
        user=request.user,
        date=selected_date,
        defaults={"status": "pending"}
    )

    if not created:
        if offday.status == "rejected":
            offday.status = "pending"
            offday.reviewed_by = None
            offday.reviewed_at = None
            offday.save()
        else:
            messages.error(request, "You already requested this day.")
            return redirect("my_shifts")

    messages.success(request, "Day-off request submitted and is waiting for manager approval.")
    return redirect("my_shifts")

@login_required
def attendance_history(request):
    records = AttendanceStatus.objects.filter(user=request.user).select_related("shift", "shift__department").order_by("-shift__date")
    return render(request, "attendance/attendance_history.html", {"records": records})

@login_required
def manager_dashboard(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    departments = Group.objects.exclude(name="Manager").order_by("name")
    dept_id = request.GET.get("dept")
    date_filter = request.GET.get("date")

    selected_day = date.today()
    if date_filter:
        try:
            selected_day = datetime.strptime(date_filter, "%Y-%m-%d").date()
        except ValueError:
            selected_day = date.today()

    week_start = selected_day - timedelta(days=selected_day.weekday())
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    selected_departments = departments
    if dept_id:
        selected_departments = departments.filter(id=dept_id)

    records = AttendanceStatus.objects.select_related(
        "user", "shift", "shift__department"
    ).filter(
        shift__date__range=(week_start, week_end),
        shift__department__in=selected_departments
    ).order_by("-shift__date", "shift__department__name", "user__username")

    total_present = records.filter(status="present").count()
    total_absent = records.filter(status="absent").count()
    total_late = records.filter(status="late").count()

    off_day_records = OffDay.objects.select_related("user").prefetch_related(
        "user__groups"
    ).filter(
        date__range=(week_start, week_end),
        user__groups__in=selected_departments
    ).exclude(
        user__groups__name="Manager"
    ).distinct().order_by("date", "user__username")

    pending_offday_requests = OffDay.objects.select_related("user").prefetch_related(
        "user__groups"
    ).filter(
        status="pending",
        date__range=(week_start, week_end),
        user__groups__in=selected_departments
    ).exclude(
        user__groups__name="Manager"
    ).distinct().order_by("date", "user__username")

    employees = User.objects.filter(
        groups__in=selected_departments
    ).exclude(
        groups__name="Manager"
    ).distinct().order_by("username").prefetch_related("groups")

    attendance_records = AttendanceStatus.objects.select_related(
        "shift", "shift__department", "user"
    ).filter(
        user__in=employees,
        shift__date__range=(week_start, week_end),
        shift__department__in=selected_departments
    )

    off_days = OffDay.objects.filter(
        user__in=employees,
        date__range=(week_start, week_end),
        status="approved"
    )

    attendance_lookup = {}
    for record in attendance_records:
        key = (record.user_id, record.shift.date)
        if key not in attendance_lookup:
            attendance_lookup[key] = []
        attendance_lookup[key].append(record)

    offday_lookup = {}
    for off in off_days:
        offday_lookup[(off.user_id, off.date)] = off

    weekly_rows = []
    for employee in employees:
        employee_groups = ", ".join(
            g.name for g in employee.groups.exclude(name="Manager")
        ) or "No Department"

        cells = []
        for day in week_days:
            key = (employee.id, day)

            if key in offday_lookup:
                cells.append({
                    "type": "offday",
                    "label": "Approved Off",
                    "details": ""
                })
            elif key in attendance_lookup:
                day_records = attendance_lookup[key]
                statuses = []
                details = []

                for r in day_records:
                    statuses.append(r.status.title())
                    details.append(f"{r.shift.shift_type.title()}: {r.status.title()}")

                cells.append({
                    "type": "attendance",
                    "label": " / ".join(sorted(set(statuses))),
                    "details": ", ".join(details)
                })
            else:
                cells.append({
                    "type": "empty",
                    "label": "No Update",
                    "details": ""
                })

        weekly_rows.append({
            "username": employee.username,
            "department": employee_groups,
            "cells": cells
        })

    notifications = Notification.objects.select_related(
        "user", "shift", "shift__department"
    ).filter(
        shift__date__range=(week_start, week_end),
        shift__department__in=selected_departments,
        is_read=False
    ).order_by("-created_at")[:12]

    return render(
        request,
        "attendance/manager_dashboard.html",
        {
            "records": records,
            "departments": departments,
            "selected_date": selected_day.isoformat(),
            "selected_dept": dept_id,
            "total_present": total_present,
            "total_absent": total_absent,
            "total_late": total_late,
            "off_day_records": off_day_records,
            "pending_offday_requests": pending_offday_requests,
            "week_days": week_days,
            "weekly_rows": weekly_rows,
            "notifications": notifications,
        }
    )

@login_required
def create_shift(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    departments = Group.objects.all().order_by("name")

    if request.method == "POST":
        shift_date = request.POST.get("date")
        shift_type = request.POST.get("shift_type")
        department_id = request.POST.get("department")

        if shift_date and shift_type and department_id:
            department = Group.objects.get(id=department_id)

            if not Shift.objects.filter(
                date=shift_date,
                shift_type=shift_type,
                department=department
            ).exists():
                Shift.objects.create(
                    date=shift_date,
                    shift_type=shift_type,
                    department=department
                )

            messages.success(request, "Shift created successfully.")
            return redirect("manager_dashboard")

    return render(request, "attendance/create_shift.html", {"departments": departments})

@login_required
def shift_list(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    date_filter = request.GET.get("date")
    dept_id = request.GET.get("dept")

    shifts = Shift.objects.select_related("department").order_by("-date", "shift_type", "department__name")

    if date_filter:
        shifts = shifts.filter(date=date_filter)

    if dept_id:
        shifts = shifts.filter(department_id=dept_id)

    departments = Group.objects.all().order_by("name")

    return render(request, "attendance/shift_list.html", {
        "shifts": shifts,
        "departments": departments,
        "selected_date": date_filter,
        "selected_dept": dept_id,
    })

@login_required
def delete_shift(request, shift_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    shift = Shift.objects.get(id=shift_id)

    if request.method == "POST":
        shift.delete()
        messages.success(request, "Shift deleted successfully.")
        return redirect("shift_list")

    return render(request, "attendance/delete_shift.html", {"shift": shift})

@login_required
def edit_shift(request, shift_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    shift = Shift.objects.get(id=shift_id)
    departments = Group.objects.all().order_by("name")

    if request.method == "POST":
        shift_date = request.POST.get("date")
        shift_type = request.POST.get("shift_type")
        department_id = request.POST.get("department")

        if shift_date and shift_type and department_id:
            department = Group.objects.get(id=department_id)

            shift.date = shift_date
            shift.shift_type = shift_type
            shift.department = department
            shift.save()

            messages.success(request, "Shift updated successfully.")
            return redirect("shift_list")

    return render(request, "attendance/edit_shift.html", {
        "shift": shift,
        "departments": departments
    })

@login_required
def attendance_list(request):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    date_filter = request.GET.get("date")
    dept_id = request.GET.get("dept")
    status_filter = request.GET.get("status")

    records = AttendanceStatus.objects.select_related(
        "user", "shift", "shift__department"
    ).order_by("-shift__date", "user__username")

    if date_filter:
        records = records.filter(shift__date=date_filter)

    if dept_id:
        records = records.filter(shift__department_id=dept_id)

    if status_filter:
        records = records.filter(status=status_filter)

    departments = Group.objects.all().order_by("name")

    return render(request, "attendance/attendance_list.html", {
        "records": records,
        "departments": departments,
        "selected_date": date_filter,
        "selected_dept": dept_id,
        "selected_status": status_filter,
    })

@login_required
def delete_attendance(request, record_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    record = AttendanceStatus.objects.get(id=record_id)

    if request.method == "POST":
        record.delete()
        messages.success(request, "Attendance record deleted successfully.")
        return redirect("attendance_list")

    return render(request, "attendance/delete_attendance.html", {"record": record})

@login_required
def edit_attendance(request, record_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("You are not allowed to view this page.")

    record = AttendanceStatus.objects.select_related("shift", "shift__department", "user").get(id=record_id)

    if request.method == "POST":
        status = request.POST.get("status")
        reason_text = request.POST.get("reason_text")

        if status:
            record.status = status
            record.reason_text = reason_text
            record.save()
            messages.success(request, "Attendance updated successfully.")
            return redirect("attendance_list")

    return render(request, "attendance/edit_attendance.html", {"record": record})


@login_required
def mark_notification_read(request, notification_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("Not allowed")

    try:
        notification = Notification.objects.get(id=notification_id)
        notification.is_read = True
        notification.save()
    except Notification.DoesNotExist:
        pass

    return redirect("manager_dashboard")

@login_required
def approve_offday(request, offday_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("Not allowed")

    try:
        offday = OffDay.objects.select_related("user").get(id=offday_id)
    except OffDay.DoesNotExist:
        messages.error(request, "Request not found.")
        return redirect("manager_dashboard")

    user_groups = offday.user.groups.exclude(name="Manager")

    conflict_exists = OffDay.objects.filter(
        user__groups__in=user_groups,
        date=offday.date,
        status="approved"
    ).exclude(user=offday.user).exists()

    if conflict_exists:
        messages.error(request, "Cannot approve. Another employee in the same department already has this date approved.")
        return redirect("manager_dashboard")

    offday.status = "approved"
    offday.reviewed_by = request.user
    offday.reviewed_at = timezone.now()
    offday.save()

    messages.success(request, f"Approved day off for {offday.user.username}.")
    return redirect("manager_dashboard")


@login_required
def reject_offday(request, offday_id):
    if not is_manager(request.user):
        return HttpResponseForbidden("Not allowed")

    try:
        offday = OffDay.objects.get(id=offday_id)
    except OffDay.DoesNotExist:
        messages.error(request, "Request not found.")
        return redirect("manager_dashboard")

    offday.status = "rejected"
    offday.reviewed_by = request.user
    offday.reviewed_at = timezone.now()
    offday.save()

    messages.success(request, f"Rejected day off for {offday.user.username}.")
    return redirect("manager_dashboard")