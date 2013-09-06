"""Exceptions used by the Vyatta plugin."""

from neutron.common import exceptions


class VRouterConnectFailure(exceptions.NeutronException):
    """Couldn't connect to instance."""
    message = _("Couldn't connect to vRouter [%(ip_address)s].")


class VRouterOperationError(exceptions.NeutronException):
    """Internal Vyatta vRouter failure."""
    message = _("Internal vRouter failure [%(ip_address)s]: failed to "
                "%(action)s router, HTTP error %(code)s: %(message)s.")


class InvalidNumberIPsOnPort(exceptions.NeutronException):
    """
    Invalid number of IP addresses assigned to port to be used as router
    gateway.
    """
    message = _("Invalid number of IP addresses assigned to port to be used "
                "as router gateway.")
