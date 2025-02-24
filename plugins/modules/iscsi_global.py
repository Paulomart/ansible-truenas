#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_global
short_description: Manage global iSCSI configuration
description:
  - Retrieve or update global iSCSI configuration.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether to query or update the global config.
    type: str
    choices: [ query, present ]
    default: query
  basename:
    description:
      - Base name (IQN prefix).
    type: str
  isns_servers:
    description:
      - List of iSNS servers.
    type: list
    elements: str
    default: []
  pool_avail_threshold:
    description:
      - Threshold of free space.
    type: int
  alua:
    description:
      - Enable or disable ALUA (no-op on some systems).
    type: bool
"""

EXAMPLES = r"""
- name: Query global iSCSI configuration
  iscsi_global:
    state: query

- name: Update global iSCSI configuration
  iscsi_global:
    state: present
    basename: "iqn.2005-10.org.freenas.ctl"
    isns_servers:
      - "10.0.0.1"
      - "10.0.0.2"
    pool_avail_threshold: 1073741824
    alua: false
"""

RETURN = r"""
iscsi_global:
  description:
    - Data structure describing the global iSCSI configuration.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(type="str", choices=["query", "present"], default="query"),
            basename=dict(type="str"),
            isns_servers=dict(type="list", elements="str", default=[]),
            pool_avail_threshold=dict(type="int"),
            alua=dict(type="bool"),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    params = module.params
    state = params["state"]

    if state == "query":
        try:
            cfg = mw.call("iscsi.global.config")
            result["iscsi_global"] = cfg
            module.exit_json(**result)
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI global config: {e}")

    # state=present => update
    try:
        # We'll fetch current config to see if changes are needed
        current = mw.call("iscsi.global.config")
    except Exception as e:
        module.fail_json(msg=f"Error fetching iSCSI global config: {e}")

    updates = {}
    if params["basename"] is not None and current.get("basename") != params["basename"]:
        updates["basename"] = params["basename"]
    if (
        params["isns_servers"] is not None
        and current.get("isns_servers") != params["isns_servers"]
    ):
        updates["isns_servers"] = params["isns_servers"]
    if (
        params["pool_avail_threshold"] is not None
        and current.get("pool_avail_threshold") != params["pool_avail_threshold"]
    ):
        updates["pool_avail_threshold"] = params["pool_avail_threshold"]
    if params["alua"] is not None and current.get("alua") != params["alua"]:
        updates["alua"] = params["alua"]

    if not updates:
        result["changed"] = False
        result["iscsi_global"] = current
        result["msg"] = "No changes needed."
        module.exit_json(**result)
    else:
        if module.check_mode:
            result["msg"] = f"Would have updated iSCSI global config with {updates}"
            result["changed"] = True
            module.exit_json(**result)
        else:
            try:
                new_cfg = mw.call("iscsi.global.update", updates)
                result["iscsi_global"] = new_cfg
                result["msg"] = "Updated iSCSI global config."
                result["changed"] = True
                module.exit_json(**result)
            except Exception as e:
                module.fail_json(msg=f"Error updating iSCSI global config: {e}")


if __name__ == "__main__":
    main()
