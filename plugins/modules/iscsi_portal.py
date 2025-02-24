#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_portal
short_description: Manage iSCSI Portals
description:
  - Create, update, and delete iSCSI Portals.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether this portal should exist or not.
    type: str
    choices: [ absent, present ]
    default: present
  id:
    description:
      - ID of the portal (for update/delete).
    type: int
  comment:
    description:
      - A comment for the portal.
    type: str
  discovery_authmethod:
    description:
      - Authentication method for discovery.
    type: str
    choices: [NONE, CHAP, CHAP_MUTUAL]
  discovery_authgroup:
    description:
      - Auth group ID for CHAP or CHAP_MUTUAL.
    type: int
  listen:
    description:
      - List of dicts describing listen addresses, e.g. {"ip": "0.0.0.0", "port": 3260}.
    type: list
    elements: dict
"""

EXAMPLES = r"""
- name: Create an iSCSI portal
  iscsi_portal:
    state: present
    comment: "My Portal"
    discovery_authmethod: "NONE"
    listen:
      - ip: "0.0.0.0"
        port: 3260
      - ip: "::"
        port: 3260

- name: Delete portal
  iscsi_portal:
    state: absent
    id: 6
"""

RETURN = r"""
portal:
  description:
    - A data structure describing the created or updated iSCSI portal.
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(type="str", choices=["absent", "present"], default="present"),
            id=dict(type="int"),
            comment=dict(type="str"),
            discovery_authmethod=dict(
                type="str", choices=["NONE", "CHAP", "CHAP_MUTUAL"]
            ),
            discovery_authgroup=dict(type="int"),
            listen=dict(type="list", elements="dict"),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    params = module.params
    state = params["state"]
    pid = params["id"]

    def find_portal_by_id(pid):
        try:
            recs = mw.call("iscsi.portal.query", [["id", "=", pid]])
            return recs[0] if recs else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI portal (id={pid}): {e}")

    existing = None
    if pid:
        existing = find_portal_by_id(pid)

    # state=absent
    if state == "absent":
        if not pid:
            module.fail_json(msg="id is required to delete a portal.")
        if not existing:
            result["changed"] = False
            result["msg"] = f"Portal {pid} does not exist."
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted iSCSI portal {pid}"
            else:
                try:
                    mw.call("iscsi.portal.delete", pid)
                    result["msg"] = f"Deleted iSCSI portal {pid}"
                except Exception as e:
                    module.fail_json(msg=f"Error deleting portal {pid}: {e}")
            result["changed"] = True
        module.exit_json(**result)

    # state=present
    if existing:
        # update
        updates = {}
        if (
            params["comment"] is not None
            and existing.get("comment") != params["comment"]
        ):
            updates["comment"] = params["comment"]
        if (
            params["discovery_authmethod"] is not None
            and existing.get("discovery_authmethod") != params["discovery_authmethod"]
        ):
            updates["discovery_authmethod"] = params["discovery_authmethod"]
        if (
            params["discovery_authgroup"] is not None
            and existing.get("discovery_authgroup") != params["discovery_authgroup"]
        ):
            updates["discovery_authgroup"] = params["discovery_authgroup"]
        if params["listen"] is not None and existing.get("listen") != params["listen"]:
            updates["listen"] = params["listen"]

        if not updates:
            result["changed"] = False
            result["portal"] = existing
            result["msg"] = "No changes needed."
        else:
            if module.check_mode:
                result["msg"] = f"Would have updated portal {pid} with {updates}"
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.portal.update", pid, updates)
                    result["portal"] = updated
                    result["msg"] = f"Updated portal {pid}"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error updating portal {pid}: {e}")
    else:
        # create
        payload = {}
        if params["comment"] is not None:
            payload["comment"] = params["comment"]
        if params["discovery_authmethod"] is not None:
            payload["discovery_authmethod"] = params["discovery_authmethod"]
        if params["discovery_authgroup"] is not None:
            payload["discovery_authgroup"] = params["discovery_authgroup"]
        if params["listen"] is not None:
            payload["listen"] = params["listen"]
        else:
            # Provide a default
            payload["listen"] = [{"ip": "0.0.0.0", "port": 3260}]

        if module.check_mode:
            result["msg"] = f"Would have created new portal: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.portal.create", payload)
                result["portal"] = created
                result["changed"] = True
                result["msg"] = "Created new iSCSI portal"
            except Exception as e:
                module.fail_json(msg=f"Error creating iSCSI portal: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
