## Requirements

### Operating system

- Linux
- A working JioFiber connection
- The computer must be connected to the same JioFiber LAN as the router

### Python

Python 3.14 is the currently verified Python version.


### PJSUA2

The SIP registration test uses the Python PJSUA2 bindings.

The repository contains the PJSIP/PJSUA2 source tree under:

```text
https://github.com/JFC-Group/JFC-pjproject.git
```

---

## JioFiber Network Endpoints

The provisioner communicates with the JioFiber router through the local provisioning endpoints:

```text
http://jiofiber.local.html:8080/request_account
https://jiofiber.local.html:8443/
```

The router's commonly used LAN address is:

```text
192.168.29.1
```

If the local hostname is not resolvable, the provisioner can use the router's LAN address.

The SIP service is provisioned separately and is exposed by the router on TLS port:

```text
5068
```

---

## Initial Setup

Clone the repository and enter it:

```bash
git clone <repository-url>
cd sys-sip
```

run the installer:

```bash
python3 setup.py
```

## Provision a SIP Credential

Run the provisioner:

The normal provisioning flow is:

```text
request_account
      │
      ▼
generate deterministic secondary-device identity
      │
      ▼
send Jio device add request
      │
      ▼
Jio sends OTP by SMS
      │
      ▼
receive WITRCSeConfigCookie
      │
      ▼
verify OTP using the same provisioning session
      │
      ▼
fetch SIP provisioning XML
      │
      ▼
extract SIP credentials and IMS configuration
```
---

# License / Attribution

The implementation is based on reverse-engineering and testing of JioFiber's locally exposed provisioning and SIP behavior.

Use the project only with a JioFiber connection and account that you are authorized to use.

Do not use it to access, provision, impersonate, or place calls through accounts or devices that you do not control or have permission to use.
