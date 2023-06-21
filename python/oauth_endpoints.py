from dataclasses import dataclass


@dataclass
class OAuthEndpoints:
    """
    Holds the URL for OAuth2 endpoints relevant to this demo.

    Attributes
    ----------
    device_authorize : str
        URL for requesting a device_code, user_code, and verification_uri
    token : str
        URL for requesting an access_token
    introspect : str
        URL for validating an access_token
    revoke : str
        URL for revoking an access_token
    user_info : str
        URL for getting info on a user given an access_token
    """

    device_authorize: str
    token: str
    introspect: str
    revoke: str
    user_info: str
