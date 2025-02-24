#!/usr/bin/python
__metaclass__ = type

DOCUMENTATION = r"""
---
module: iscsi_initiator
short_description: Manage iSCSI Initiators
description:
  - Create, manage, and delete iSCSI Initiators. Also supports query.
version_added: "1.4.3"
options:
  state:
    description:
      - Whether the initiator should exist, not exist, or be queried.
    type: str
    choices: [ absent, present, query ]
    default: present
  id:
    description:
      - ID of existing initiator (for update/delete/query).
    type: int
  initiators:
    description:
      - List of initiator hostnames (can be empty to allow all).
    type: list
    elements: str
  auth_network:
    description:
      - List of IP/CIDR addresses allowed (can be empty to allow all).
    type: list
    elements: str
  comment:
    description:
      - Comment for this initiator group.
    type: str
"""

EXAMPLES = r"""
- name: Create an iSCSI initiator
  iscsi_initiator:
    state: present
    initiators:
      - "iqn.1994-05.com.redhat:rhel7-client"
    auth_network:
      - "10.0.0.0/24"
    comment: "My RHEL client"

- name: Delete iSCSI initiator with ID=5
  iscsi_initiator:
    state: absent
    id: 5

- name: Query initiator with ID=5
  iscsi_initiator:
    state: query
    id: 5
"""

RETURN = r"""
initiator:
  description:
    - A data structure describing the iSCSI initiator (created/updated/queried).
  type: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.arensb.truenas.plugins.module_utils.middleware import (
    MiddleWare as MW,
)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(
                type="str", choices=["absent", "present", "query"], default="present"
            ),
            id=dict(type="int"),
            initiators=dict(type="list", elements="str"),
            auth_network=dict(type="list", elements="str"),
            comment=dict(type="str"),
        ),
        supports_check_mode=True,
    )

    mw = MW.client()
    result = dict(changed=False, msg="")

    params = module.params
    state = params["state"]
    initiator_id = params["id"]

    def find_initiator_by_id(iid):
        try:
            recs = mw.call("iscsi.initiator.query", [["id", "=", iid]])
            return recs[0] if recs else None
        except Exception as e:
            module.fail_json(msg=f"Error querying iSCSI initiator (id={iid}): {e}")

    existing = None
    if initiator_id:
        existing = find_initiator_by_id(initiator_id)

    # state=query
    if state == "query":
        if not initiator_id:
            module.fail_json(msg="id is required to query an iSCSI initiator.")
        if existing:
            result["initiator"] = existing
            module.exit_json(**result)
        else:
            module.fail_json(msg=f"No iSCSI initiator found with id={initiator_id}")

    # state=absent
    if state == "absent":
        if not initiator_id:
            module.fail_json(msg="id is required to delete an iSCSI initiator.")
        if not existing:
            result["changed"] = False
            result["msg"] = f"Initiator {initiator_id} does not exist."
        else:
            if module.check_mode:
                result["msg"] = f"Would have deleted iSCSI initiator {initiator_id}"
            else:
                try:
                    mw.call("iscsi.initiator.delete", initiator_id)
                    result["msg"] = f"Deleted iSCSI initiator {initiator_id}"
                except Exception as e:
                    module.fail_json(
                        msg=f"Error deleting initiator {initiator_id}: {e}"
                    )
            result["changed"] = True
        module.exit_json(**result)

    # state=present
    if existing:
        # Update
        updates = {}
        if params["initiators"] is not None and set(params["initiators"]) != set(
            existing["initiators"]
        ):
            updates["initiators"] = params["initiators"]
        if params["auth_network"] is not None and set(params["auth_network"]) != set(
            existing["auth_network"]
        ):
            updates["auth_network"] = params["auth_network"]
        if params["comment"] is not None and params["comment"] != existing["comment"]:
            updates["comment"] = params["comment"]

        if not updates:
            result["changed"] = False
            result["initiator"] = existing
            result["msg"] = "No changes needed."
        else:
            if module.check_mode:
                result["msg"] = (
                    f"Would have updated initiator {initiator_id} with {updates}"
                )
                result["changed"] = True
            else:
                try:
                    updated = mw.call("iscsi.initiator.update", initiator_id, updates)
                    result["initiator"] = updated
                    result["msg"] = f"Updated iSCSI initiator {initiator_id}"
                    result["changed"] = True
                except Exception as e:
                    module.fail_json(
                        msg=f"Error updating initiator {initiator_id}: {e}"
                    )
    else:
        # Create
        payload = {}
        if params["initiators"] is not None:
            payload["initiators"] = params["initiators"]
        if params["auth_network"] is not None:
            payload["auth_network"] = params["auth_network"]
        if params["comment"] is not None:
            payload["comment"] = params["comment"]

        if module.check_mode:
            result["msg"] = f"Would have created new iSCSI initiator: {payload}"
            result["changed"] = True
        else:
            try:
                created = mw.call("iscsi.initiator.create", payload)
                result["initiator"] = created
                result["msg"] = "Created new iSCSI initiator"
                result["changed"] = True
            except Exception as e:
                module.fail_json(msg=f"Error creating iSCSI initiator: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
