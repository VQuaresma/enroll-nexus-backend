from django.urls import path
from .views import EnrollmentCreateView, EnrollmentListView

urlpatterns = [
    path('submit/', EnrollmentCreateView.as_view(), name='enrollment-submit'),
    path('list/', EnrollmentListView.as_view(), name='enrollment-list'),
]