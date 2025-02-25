#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_portal
short_description: Manage iSCSI Portals by numeric ID, ignoring `port` in the `listen` list.
description:
  - Create, update, or delete iSCSI Portals, identified strictly by integer ID.
  - If C(id) is not provided (and state=present), a new portal is created.
  - If C(id) is provided (and state=present), the portal is updated if it exists, or fails if not found.
  - If C(id) is provided (and state=absent), the portal is deleted if found, or no-op if not found.
  - The `listen` parameter is deep-compared ignoring ordering, key order, and any `port` property.
  - Optimized so that if an ID is given, the module queries only that portal with a filter C(["id","=",id])
    instead of listing all portals.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether the portal should exist (present) or not (absent).
    type: str
    choices: [ absent, present ]
    default: present
  id:
    description:
      - Numeric ID of the portal to update or delete.
      - If absent and C(state=present), a new portal is created.
      - If present but no existing portal with that ID is found, the module fails for C(state=present).
      - For C(state=absent), if no existing portal with that ID is found, no changes are made.
    type: int
  comment:
    description:
      - A descriptive comment for the portal.
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
      - A list of dictionaries describing how this portal should listen.
      - The module will ignore any `port` property when comparing current and desired config.
      - This means if the only difference is the port value, no update is triggered.
    type: list
    elements: dict

author:
  - Your Name <you@example.com>
"""

EXAMPLES = r"""
- name: Create a new iSCSI portal (no ID provided), ignoring any `port` differences
  iscsi_portal:
    state: present
    comment: "My new portal"
    discovery_authmethod: "NONE"
    listen:
      - ip: "0.0.0.0"
        port: 3261
      - ip: "::"
        port: 3262

- name: Update an existing portal with ID=5, ignoring the port property
  iscsi_portal:
    state: present
    id: 5
    comment: "Updated comment"
    listen:
      - ip: "192.168.1.10"
        port: 9999
      - ip: "192.168.1.11"

- name: Delete portal with ID=5
  iscsi_portal:
    state: absent
    id: 5
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

    p = module.params
    state = p["state"]
    portal_id = p["id"]

    # Helper: run iscsi.portal.query with ID=portal_id if we have it
    def get_portal_by_id(pid):
        try:
            # Filters: we pass [[["id","=",pid]]] as the first argument
            portals = mw.call("iscsi.portal.query", [["id", "=", pid]])
            return portals[0] if portals else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI portal {pid}: {e}")

    # Helper: ignore 'port' key, plus ordering of list and keys
    def normalize_list_of_dicts(lst):
        if not lst:
            return []
        normalized = []
        for item in lst:
            item_copy = {}
            for k, v in item.items():
                if k == "port":
                    # skip port
                    continue
                item_copy[k] = v

            sorted_pairs = tuple(sorted(item_copy.items()))
            normalized.append(sorted_pairs)

        normalized.sort()
        return normalized

    if state == "absent":
        if portal_id is None:
            module.fail_json(msg="id is required to delete an iSCSI portal.")
        existing = get_portal_by_id(portal_id)
        if not existing:
            result["changed"] = False
            result["msg"] = f"No portal found with id={portal_id}; nothing to delete."
            module.exit_json(**result)
        else:
            if module.check_mode:
                result["msg"] = f"Would delete iSCSI portal id={portal_id}"
            else:
                try:
                    mw.call("iscsi.portal.delete", portal_id)
                    result["msg"] = f"Deleted iSCSI portal id={portal_id}"
                except Exception as e:
                    module.fail_json(msg=f"Error deleting portal id={portal_id}: {e}")
            result["changed"] = True
            module.exit_json(**result)

    else:  # state=present
        if portal_id is None:
            # Create new portal
            payload = {}
            if p["comment"] is not None:
                payload["comment"] = p["comment"]
            if p["discovery_authmethod"] is not None:
                payload["discovery_authmethod"] = p["discovery_authmethod"]
            if p["discovery_authgroup"] is not None:
                payload["discovery_authgroup"] = p["discovery_authgroup"]
            if p["listen"] is not None:
                payload["listen"] = p["listen"]
            else:
                payload["listen"] = [{"ip": "0.0.0.0"}]

            if module.check_mode:
                result["msg"] = f"Would create new iSCSI portal: {payload}"
                result["changed"] = True
            else:
                try:
                    created = mw.call("iscsi.portal.create", payload)
                    result["portal"] = created
                    result["msg"] = "Created new iSCSI portal"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(msg=f"Error creating iSCSI portal: {e}")
            module.exit_json(**result)
        else:
            # Update existing portal if found
            existing = get_portal_by_id(portal_id)
            if not existing:
                module.fail_json(
                    msg=f"No portal found with id={portal_id}; cannot update."
                )

            updates = {}
            if p["comment"] is not None and p["comment"] != existing.get("comment"):
                updates["comment"] = p["comment"]
            if p["discovery_authmethod"] is not None and p[
                "discovery_authmethod"
            ] != existing.get("discovery_authmethod"):
                updates["discovery_authmethod"] = p["discovery_authmethod"]
            if p["discovery_authgroup"] is not None and p[
                "discovery_authgroup"
            ] != existing.get("discovery_authgroup"):
                updates["discovery_authgroup"] = p["discovery_authgroup"]

            # Compare listen ignoring 'port'
            if p["listen"] is not None:
                existing_listen_norm = normalize_list_of_dicts(existing.get("listen"))
                desired_listen_norm = normalize_list_of_dicts(p["listen"])
                if existing_listen_norm != desired_listen_norm:
                    updates["listen"] = p["listen"]

            if not updates:
                result["changed"] = False
                result["portal"] = existing
                result["msg"] = f"No changes needed for portal id={portal_id}"
            else:
                if module.check_mode:
                    result["msg"] = (
                        f"Would update iSCSI portal id={portal_id} with {updates}"
                    )
                    result["changed"] = True
                else:
                    try:
                        updated = mw.call("iscsi.portal.update", portal_id, updates)
                        result["portal"] = updated
                        result["msg"] = f"Updated iSCSI portal id={portal_id}"
                        result["changed"] = True
                    except Exception as e:
                        module.fail_json(
                            msg=f"Error updating portal id={portal_id}: {e}"
                        )

            module.exit_json(**result)


if __name__ == "__main__":
    main()
