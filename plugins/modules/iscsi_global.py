#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_global
short_description: Manage global iSCSI configuration
description:
  - Update global iSCSI configuration (basically a single system-wide record).
version_added: "1.4.3"
options:
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
- name: Update global iSCSI configuration
  iscsi_global:
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
    - Updated global iSCSI configuration.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            basename=dict(type="str"),
            isns_servers=dict(type="list", elements="str", default=[]),
            pool_avail_threshold=dict(type="int"),
            alua=dict(type="bool"),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    try:
        current = mw.call("iscsi.global.config")
    except Exception as e:
        module.fail_json(msg=f"Error fetching iSCSI global config: {e}")

    params = module.params
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
            result["msg"] = f"Would update iSCSI global with {updates}"
            result["changed"] = True
            module.exit_json(**result)
        try:
            new_cfg = mw.call("iscsi.global.update", updates)
            result["iscsi_global"] = new_cfg
            result["msg"] = "Updated iSCSI global config."
            result["changed"] = True
        except Exception as e:
            module.fail_json(msg=f"Error updating iSCSI global config: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
