class ConnectorError(Exception):
    code = "connector_error"
    transient = False


class TransientConnectorError(ConnectorError):
    code = "transient_provider_error"
    transient = True


class PermanentConnectorError(ConnectorError):
    code = "permanent_provider_error"
