# Jio Fiber SIP Provisioner

A small Python utility for provisioning a software SIP client as a
JioFiber Voice authorized secondary device.

The utility communicates directly with the JioFiber router on the local
network. It does not require an Android phone, Android emulator,
JioJoin, additional hardware, or a separate VoIP account.

## Current status

The following flow has been verified against the JioFiber router:

-   `request_account` works.
-   `ParikaSIPProxy` deterministic MAC generation works.
-   Device `add` request works.
-   Jio sends the OTP by SMS.
-   `WITRCSeConfigCookie` is received.
-   OTP verification works.
-   SIP provisioning XML is returned.
-   SIP username, realm, password, and related values are extracted.
-   `.env` is generated automatically beside this script.
-   Device `remove` request works.
-   Removing the device and adding it again causes Jio to issue a fresh
    OTP.

## Files

Expected directory:

``` text
jio_call/
├── jio_fiber_sip_provisioner.py
├── .env
└── README.md
```

The `.env` file is created automatically in the same directory as the
Python script. No absolute project path is hardcoded.

## Requirements

-   Ubuntu/Linux
-   Python 3
-   Python packages:
    -   `requests`
    -   `urllib3`
-   A JioFiber connection/router exposing the local provisioning
    endpoints.
-   The computer running the script must be connected to the JioFiber
    network.

The script communicates with:

``` text
http://jiofiber.local.html:8080/request_account
https://jiofiber.local.html:8443/
```

If the hostname cannot be resolved, the script can fall back to the
router's LAN IP.

## Provisioning flow

The normal command is:

``` bash
python3 jio_fiber_sip_provisioner.py
```

The flow is:

``` text
request_account
      ↓
calculate deterministic MAC for ParikaSIPProxy
      ↓
send Jio device add request
      ↓
Jio sends OTP by SMS
      ↓
receive WITRCSeConfigCookie
      ↓
verify OTP using the provisioning cookie
      ↓
fetch SIP provisioning XML
      ↓
extract SIP credentials
      ↓
write .env
```

The current deterministic device identity is:

``` text
Hostname: ParikaSIPProxy
MAC: 00:00:26:21:44:37
```

Do not manually change the MAC unless the provisioning identity is
intentionally being changed.

## Remove an authorized device

The provisioner also supports removing the deterministic device from the
Jio authorized-device list:

``` bash
python3 jio_fiber_sip_provisioner.py --remove
```

A successful removal returns a Jio provisioning response containing:

``` text
You have successfully removed this device from this Jio Connection authorized devices list. #001
```

After removal, running the normal provisioning command again causes Jio
to start a new authorization flow and send a fresh OTP.

## Fresh credential cycle

To intentionally obtain a fresh SIP credential:

``` bash
python3 jio_fiber_sip_provisioner.py --remove
```

Then:

``` bash
python3 jio_fiber_sip_provisioner.py
```

Enter the OTP received by SMS.

The resulting SIP configuration is written to `.env`.

## Generated environment

The script generates values including:

``` text
CONTAINER_NAME
HOSTNAME_OVERRIDE
USER_AGENT
IPV4_ADDRESS
LOCAL_PORT
TLS_PORT
RTP_PORT
PUBLIC_ID
SIP_AUTH_USER
SIP_PASSWORD
SIP_REALM
REGISTRAR_HOST
REGISTRAR_PORT
PROXY_HOST
PROXY_PORT
DNS_SERVERS
LOG_LEVEL
KEEPALIVE
MAX_CALLS
TLS_VERIFY
```

### Security

`.env` contains the SIP password and must be treated as a secret.

Do not:

-   commit `.env` to Git.
-   paste `.env` contents into public issues or chats.
-   expose `SIP_PASSWORD` in logs.
-   share provisioning cookies.
-   share OTPs.

Recommended `.gitignore` entry:

``` gitignore
.env
.env.bak
```

If a SIP password is accidentally exposed, remove the authorized device
and provision it again to obtain a fresh credential.

## Cookie/session handling

The Jio `add` request is performed using the raw HTTPS request
implementation because this reproduces the router's known-working
provisioning request.

The response headers are normalized to lowercase.

The provisioning response's:

``` text
set-cookie
```

header is parsed and the `WITRCSeConfigCookie` is explicitly transferred
into the Python `requests.Session`.

The same session is then used for OTP verification.

This behavior is important because the OTP request must be associated
with the provisioning session.

## SIP configuration

After successful OTP verification, the script fetches the provisioning
XML and extracts values such as:

``` text
realm
username
userpwd
home_network_domain_name
address
private_user_identity
public_user_identity
```

The generated `.env` currently configures the Jio router as the SIP
registrar/proxy on TLS port `5068`.

The script does not itself make telephone calls. Its responsibility is
provisioning and credential generation.

## Current architecture

``` text
JioFiber Router
      │
      ├── HTTP :8080
      │     └── request_account
      │
      └── HTTPS :8443
            ├── add device
            ├── OTP session
            ├── OTP verification
            ├── SIP provisioning XML
            └── remove device
                     │
                     ▼
             jio_fiber_sip_provisioner.py
                     │
                     ▼
                  .env
                     │
                     ▼
              SIP client / proxy
                     │
                     ▼
                   PARIKA
```

## Important distinction

This project is currently a **JioFiber SIP provisioning utility**.

It does not yet implement the complete calling layer.

The next stage is to use the generated SIP credentials and Jio SIP/TLS
endpoint to establish SIP registration and place/receive calls from
Linux, after which PARIKA can control the calling interface.

## Troubleshooting

### OTP is not received

First verify that the router's provisioning endpoint is reachable:

``` bash
curl -sS --max-time 5 http://192.168.29.1:8080/request_account
```

Then verify that the Jio provisioning endpoint is reachable:

``` bash
curl -k -i --max-time 10 https://192.168.29.1:8443/
```

Do not repeatedly request OTPs unnecessarily.

### OTP verification fails

Make sure the `WITRCSeConfigCookie` generated by the same `add` request
is retained and used for verification.

If the device was already authorized, remove it first:

``` bash
python3 jio_fiber_sip_provisioner.py --remove
```

Then start a new provisioning cycle.

### Device is already authorized

Use:

``` bash
python3 jio_fiber_sip_provisioner.py --remove
```

A successful response confirms that the device has been removed.

## Verified Jio protocol behavior

The following behavior has been directly verified on the target JioFiber
router:

``` text
op_type=remove
```

with the complete provisioning parameters removes the authorized device.

The corresponding:

``` text
op_type=add
```

request starts the authorization flow and causes an OTP to be sent.

After OTP verification, the router returns SIP provisioning information
containing the SIP authentication credentials and Jio IMS configuration.

## License / attribution

The implementation follows the JioFiber SIP provisioning behavior
reverse-engineered from publicly available JioFiber
customization/reverse-engineering material.

Use this utility only with your own JioFiber connection and authorized
account.
