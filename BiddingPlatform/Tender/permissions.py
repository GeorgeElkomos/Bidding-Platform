from rest_framework import permissions


class IsSuperUser(permissions.BasePermission):
    """
    Custom permission to only allow superusers to access the view.
    """

    message = "Only superusers are allowed to perform this action."

    def has_permission(self, request, view):
        return request.user and request.user.is_superuser

class IsCompany(permissions.BasePermission):
    """
    Custom permission to only allow users with accepted company status to access the view.
    """

    message = "Only users with an accepted company are allowed to perform this action."

    def has_permission(self, request, view):
        return request.user and not request.user.is_superuser
