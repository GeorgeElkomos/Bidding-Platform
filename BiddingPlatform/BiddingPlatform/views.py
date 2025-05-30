from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from .consumers import notify_users


class NotificationTestView(TemplateView):
    template_name = "notification_test.html"


@method_decorator(csrf_exempt, name="dispatch")
class TestNotificationAPI(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            message = data.get("message", "Test notification")
            notify_users(message)
            return JsonResponse({"status": "success", "message": "Notification sent"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
