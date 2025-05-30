"""
URL configuration for BiddingPlatform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from .views import NotificationTestView, TestNotificationAPI

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/User/", include("User.urls")),  # Include the User app's URLs
    path("api/Tender/", include("Tender.urls")),  # Include the Tender app's URLs
    path("api/Bit/", include("Bit.urls")),  # Include the Bit app's URLs
    path(
        "notification-test/", NotificationTestView.as_view(), name="notification_test"
    ),
    path(
        "api/test-notification/",
        TestNotificationAPI.as_view(),
        name="test_notification",
    ),
]
