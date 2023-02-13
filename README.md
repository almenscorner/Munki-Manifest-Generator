<p align="center">
  <img src="https://user-images.githubusercontent.com/78877636/191977945-eb1c4e6f-85f7-429d-afa9-9acfc43d33c1.png" alt="mmg logo"/>
</p>
<p align="center">
  <img src="https://img.shields.io/pypi/l/Munki-Manifest-Generator?style=flat-square" alt=""/>
  <img src="https://img.shields.io/pypi/dm/Munki-Manifest-Generator?style=flat-square" alt=""/>
  <img src="https://img.shields.io/pypi/pyversions/Munki-Manifest-Generator?style=flat-square" alt=""/>
  <img src="https://img.shields.io/pypi/v/Munki-Manifest-Generator?style=flat-square" alt=""/>
  <img src="https://github.com/almenscorner/Munki-Manifest-Generator/actions/workflows/python-publish.yml/badge.svg" alt=""/>
</p>

This is a tool to generate Munki manifests for devices managed by Intune. Instead of manually managing manifests for each device, this tool uses the groups the user and/or device is a member of to determine which included manifests and catalogs the device should be a member of.

To do this, you create a JSON file and pass that when executing like this `munki-manifest-generator -j path_to_json`. The JSON needs to be spcified like below,

**NOTE:** Name of the manifest in Munki should match with the name of the group

```json
[
    {
        "id": "id_of_aad_group", // id of the group in Azure AD
        "name": "name_of_manifest", // name of manifest in Munki
        "catalog": "catalog_name", // name of catalog in Munki or null
        "type": "type_of_group" // valid values are "user" or "device"
    }
]
```

Let's say you have manifests and catalogs for testing, Beta and Pre-Production, you can specify the Azure AD groups the user or device needs to be part of in order to be included. If you then set this up to run on a schedule, the device's membership will update in Munki if the user or device is made a member or removed from a group.

```json
[
    {
        "id": "111-111-111-111",
        "name": "internal-testing",
        "catalog": "testing",
        "type": "device"
    },
    {
        "id": "222-222-222-222",
        "name": "Beta-users",
        "catalog": "Beta",
        "type": "user" 
    },
    {
        "id": "333-333-333-333",
        "name": "pre-production",
        "catalog": "preprod",
        "type": "device"
    }
]
```

If running this tool from an agent where it can be hazzle to pass a file, you can instead parse a list of dicts in script. The below example is running in an Azure Runbook where variables have been configured on the automation account, sensitive information like client secret and connection strings have been saved as encrypted variables. It's also prepared to be executed from a webhook targeting a specific device,

```python
#!/usr/bin/env python3

import os
import sys
import json
import automationassets

from automationassets import AutomationAssetNotFound
from munki_manifest_generator import main as mmg

webhook = False
# If executed from webhook, load json data and set webhook to True
if len(sys.argv) > 1 :
    data = sys.argv[1].split(",")
    w_data = data[1].replace("RequestBody:","")
    webhook_data = json.loads(w_data)
    webhook = True
    serial = webhook_data['serial']

# get  variables
os.environ['CLIENT_ID'] = automationassets.get_automation_variable("CLIENT_ID")
os.environ['CLIENT_SECRET'] = automationassets.get_automation_variable("CLIENT_SECRET")
os.environ['CONTAINER_NAME'] = automationassets.get_automation_variable("CONTAINER_NAME")
os.environ['AZURE_STORAGE_CONNECTION_STRING'] = automationassets.get_automation_variable("AZURE_STORAGE_CONNECTION_STRING")
os.environ['TENANT_NAME'] = automationassets.get_automation_variable("TENANT_NAME")

groups = [
    {
        "id": "id_of_aad_group_1",
        "name": "name_of_manifest_1",
        "catalog": "catalog_name_1",
        "type": "type_of_group_1"
    },
        {
        "id": "id_of_aad_group_2",
        "name": "name_of_manifest_2",
        "catalog": "catalog_name_2",
        "type": "type_of_group_2"
    }
]

if webhook is True:
	mmg.main(group_list=groups, serial_number=serial)
else:
	mmg.main(group_list=groups)
```

In addition to importing this package to your automation account when running from Azure Automation, you must also import the following packages,
- [msal](https://pypi.org/project/msal)
- [azure-core](https://pypi.org/project/azure-core/)
- [azure-storage-blob](https://pypi.org/project/azure-storage-blob/)
- [msrest](https://pypi.org/project/msrest/)
- [typing-extensions](https://pypi.org/project/typing-extensions/)

## Install this package
```python
pip install Munki-Manifest-Generator
```

## Update this package
```python
pip install Munki-Manifest-Generator --upgrade
```

## Get help
```python
Munki-Manifest-Generator --help
```

## Testing mode

To run this tool without making any changes to the manifests on Azure Storage, which can be useful to test the groups in a json file or validate nothing unwanted will happen in your environment. The only thing you'll have to do is add the `-t` parameter.

Running from command line:
```shell
munki-manifest-generator -j path_to_json -t
```

Running from a script: 
```python
mmg.main(group_list=groups, test=True)
```

## Environment variables

To use the tool, you must set a couple of environment variables that will be used to authenticate to Azure Storage and Microsoft Graph,
- CLIENT_ID - Azure AD App Registration client id
- CLIENT_SECRET - Azure AD App Registration client secret
- TENANT_NAME - Name of your Azure tenant, i.e. example.onmicrosoft.com
- CONTAINER_NAME - Name of your Azure Storage Container
- AZURE_STORAGE_CONNECTION_STRING - Connection string to your Azure Storage account

If using interactive authentication, the CLIENT_SECRET is not required.

If using certificate authentication, additional environment variables are required,
- THUMBPRINT - Thumbprint of the certificate on your app registration
- KEY_FILE - Path to the private key of the certificate on your app registation

## Azure AD app registration permissions
- DeviceManagementManagedDevices.Read.All
- Directory.Read.All
- GroupMember.Read.All
- Group.Read.All

## Generated manifest exmaple

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>catalogs</key>
	<array>
                <string>testing</string>
		<string>Production</string>
	</array>
	<key>display_name</key>
	<string>tobias’s Mac</string>
	<key>included_manifests</key>
	<array>
		<string>site_default</string>
		<string>internal-testing</string>
	</array>
	<key>managed_installs</key>
	<array/>
	<key>optional_installs</key>
	<array/>
	<key>serialnumber</key>
	<string>C07XXXXXXXXX</string>
	<key>user</key>
	<string>user@example.onmicrosoft.com</string>
</dict>
</plist>
```

## Example output
![mmg1](https://user-images.githubusercontent.com/78877636/191742519-35c316be-d5e7-4a87-b2ff-711a0519c624.jpg)

![mmg2](https://user-images.githubusercontent.com/78877636/191742531-13274273-098c-4b54-9d54-62c11776dcd5.jpg)

![mmg3](https://user-images.githubusercontent.com/78877636/191742547-a1bd061b-f3c7-4cf2-8c83-ff83aa9f09b5.jpg)

![mmg4](https://user-images.githubusercontent.com/78877636/191742563-c4ae2ea6-ad5a-4bfa-9ca9-a4536aaa5bce.jpg)
